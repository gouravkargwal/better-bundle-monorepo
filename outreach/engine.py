"""
BetterBundle Outreach Engine
Handles: CSV import → Elastic Email sending → Gmail reply polling → classification → follow-ups
"""

import os, re, json, time, sqlite3, imaplib, email, requests
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, formataddr
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.dev"))

# ---------- CONFIG ----------
DAILY_CAP = int(os.getenv("DAILY_SEND_CAP", "15"))
FOLLOWUP2_DAYS = 3
FOLLOWUP3_DAYS = 7
# Elastic Email REST API key (sending + event tracking).
# .env.dev ships this as ELASTICMAILPASS; ELASTIC_EMAIL_API_KEY is canonical.
EE_API_KEY = os.getenv("ELASTIC_EMAIL_API_KEY") or os.getenv("ELASTICMAILPASS")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "gourav@betterbundle.site")
SENDER_NAME = os.getenv("SENDER_NAME", "Gourav | BetterBundle")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach.db")

EE_API_URL = "https://api.elasticemail.com/v4"
IMAP_SERVER = "imap.gmail.com"


_genai_client = None


def _client():
    """Google AI Studio client, built once and reused."""
    global _genai_client
    if _genai_client is None:
        from google import genai

        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def llm(prompt: str, retries: int = 2) -> str:
    """Gemini call via Google AI Studio.

    Raises on failure. Callers must not swallow it — a silent fallback here is
    what sent 45 templated emails.
    """
    from google.genai import types

    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    last = None
    for attempt in range(retries + 1):
        try:
            resp = _client().models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config
            )
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError(f"empty response (finish_reason={resp.candidates[0].finish_reason if resp.candidates else 'none'})")
            return text
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(2**attempt)

    raise RuntimeError(f"Gemini {GEMINI_MODEL} failed after {retries + 1} attempts: {last}") from last


# ---------- DB ----------
_db_conn = None

def get_db():
    global _db_conn
    if _db_conn is None:
        # timeout: a second writer waits its turn instead of raising "database is
        # locked". WAL: readers never block on a writer, which matters because the
        # Streamlit app polls while a verification run is writing.
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        _db_conn.row_factory = sqlite3.Row
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA busy_timeout=30000")
        _db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT, domain TEXT, contact_name TEXT,
            email TEXT UNIQUE, person_title TEXT,
            email_type TEXT, email_confidence TEXT, email_method TEXT,
            website_info TEXT, niche TEXT,
            status TEXT DEFAULT 'new',
            emails_sent INTEGER DEFAULT 0,
            last_sent_at TEXT,
            first_subject TEXT,
            body TEXT,
            reply_text TEXT,
            reply_classification TEXT,
            rebuttal_draft TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER,
            seq INTEGER,
            subject TEXT,
            body TEXT,
            sent_at TEXT,
            message_id TEXT,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        );
        CREATE INDEX IF NOT EXISTS idx_prospect_status ON prospects(status);
        CREATE INDEX IF NOT EXISTS idx_prospect_email ON prospects(email);
        """)
        # Migration: add body column if missing (for existing DBs created before this column)
        try:
            _db_conn.execute("ALTER TABLE prospects ADD COLUMN body TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        _migrate(_db_conn)
        _db_conn.commit()
    return _db_conn


def close_db():
    global _db_conn
    if _db_conn:
        _db_conn.close()
        _db_conn = None


def _migrate(con):
    for col, typ in [("delivered", "INTEGER DEFAULT 0"),
                     ("opened",   "INTEGER DEFAULT 0"),
                     ("proxy_open", "INTEGER DEFAULT 0"),
                     ("unsubscribed", "INTEGER DEFAULT 0"),
                     ("bounce_type", "TEXT"),
                     ("bounced",  "INTEGER DEFAULT 0"),
                     ("last_event", "TEXT"),
                     ("last_event_at", "TEXT")]:
        try:
            con.execute(f"ALTER TABLE emails ADD COLUMN {col} {typ}")
        except Exception:
            pass
    # Frozen record of what we knew and what we said, used to write follow-ups.
    for col, typ in [("followup_context", "TEXT"), ("verified_at", "TEXT")]:
        try:
            con.execute(f"ALTER TABLE prospects ADD COLUMN {col} {typ}")
        except Exception:
            pass
    # Pending follow-up draft columns (human-in-the-loop follow-ups).
    for col, typ in [("pending_followup_subject", "TEXT"),
                     ("pending_followup_body", "TEXT"),
                     ("pending_followup_seq", "INTEGER")]:
        try:
            con.execute(f"ALTER TABLE prospects ADD COLUMN {col} {typ}")
        except Exception:
            pass


# ---------- ELASTIC EMAIL EVENT SYNC ----------
# Elastic Email doesn't filter /events by a client-supplied id, so we pull a
# rolling date window and match each event to the sent row via the MessageID
# EE assigns at send time. Bounces can land up to 48h out (EE retries for two
# days), hence the 3-day window.
def elastic_fetch_events(days: int = 3, max_events: int = 30000) -> list:
    """Fetch Elastic Email events for the last `days`, paging by offset (1000/page)."""
    if not EE_API_KEY:
        return []
    from_dt = datetime.now(timezone.utc) - timedelta(days=days)
    headers = {
        "X-ElasticEmail-ApiKey": EE_API_KEY,
        "Accept": "application/json",
        "User-Agent": "skuvio-outreach/1.0",
    }
    events, offset = [], 0
    while len(events) < max_events:
        params = {
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "orderBy": "DateAscending",
            "limit": 1000,
            "offset": offset,
        }
        try:
            r = requests.get(f"{EE_API_URL}/events", headers=headers,
                             params=params, timeout=30)
            if r.status_code != 200:
                print(f"⚠ Elastic Email events HTTP {r.status_code}: {r.text[:160]}")
                break
            data = r.json()
        except Exception as e:
            print(f"⚠ Elastic Email events error at offset {offset}: {e}")
            break
        page = data if isinstance(data, list) else data.get("events", data.get("results", []))
        if not page:
            break
        events.extend(page)
        offset += len(page)
        if len(page) < 1000:
            break
    return events


def _ee_flags(events: list) -> dict:
    """Collapse a message's Elastic Email events into local status flags.

    v4 EventType is one of: Submission, FailedAttempt, Error, Sent, Open,
    Click, Unsubscribe, Complaint, Bounce, TransactionalUnsubscribe, Suppress.
    There is no Delivered event (Sent *is* the delivery confirmation) and no
    hard/soft bounce split -- that comes from MessageCategory on the event.
    """
    types = {_ee_type(e) for e in events}
    bounce_evs = [e for e in events if _ee_type(e) in ("bounce", "error", "complaint")]
    btype = None
    if bounce_evs:
        cats = {(e.get("MessageCategory") or "").lower() for e in bounce_evs}
        # Permanent: no such mailbox, blacklisted, spam-flagged, SPF/DNS broken.
        hard_cats = {"nomailbox", "blacklisted", "spam", "spfproblem",
                     "dnsproblem", "notdeliveredcancelled", "manualcancel"}
        btype = "hard" if (cats & hard_cats or "complaint" in types) else "soft"
    return {"delivered": 1 if "sent" in types else 0,
            "opened": 1 if types & {"open", "click"} else 0,
            "proxy_open": 0,
            "bounced": 1 if bounce_evs else 0,
            "bounce_type": btype,
            "unsubscribed": 1 if types & {"unsubscribe", "transactionalunsubscribe"} else 0}


def _ee_type(ev: dict) -> str:
    return (ev.get("EventType") or "").lower()


def _ee_last_event(ev: dict, btype: str = None) -> str:
    """Normalize an event to the literal the suppress SQL expects."""
    t = _ee_type(ev)
    if t == "complaint" or (t in ("bounce", "error") and btype == "hard"):
        return "hardBounces"
    if t in ("bounce", "error"):
        return "softBounces"
    if t in ("unsubscribe", "transactionalunsubscribe"):
        return "unsubscribed"
    return ev.get("EventType") or ""


def _ee_date(ev: dict) -> str:
    return ev.get("EventDate") or ""


def sync_email_status() -> dict:
    """Pull Elastic Email events for every sent email and store status locally."""
    con = get_db()
    rows = con.execute("""
        SELECT id, message_id FROM emails
        WHERE message_id IS NOT NULL AND message_id != ''
    """).fetchall()

    if not rows:
        return {"updated": 0}

    # Build a map of MessageID (without angle brackets) -> email id
    msg_map = {r["message_id"].strip("<>"): r["id"] for r in rows}

    events = elastic_fetch_events()

    from collections import defaultdict
    events_by_msg = defaultdict(list)
    for e in events:
        mid = (e.get("MsgID") or "").strip("<>")
        if mid in msg_map:
            events_by_msg[mid].append(e)

    updated = 0
    for mid, msg_events in events_by_msg.items():
        flags = _ee_flags(msg_events)
        last = max(msg_events, key=lambda x: _ee_date(x))
        last_at = _ee_date(last)
        con.execute("""
            UPDATE emails
            SET delivered=?, opened=?, proxy_open=?, bounced=?, bounce_type=?,
                unsubscribed=?, last_event=?, last_event_at=?
            WHERE id=?
        """, (flags["delivered"], flags["opened"], flags["proxy_open"],
              flags["bounced"], flags["bounce_type"], flags["unsubscribed"],
              _ee_last_event(last, flags["bounce_type"]), last_at, msg_map[mid]))
        updated += 1

    con.commit()
    return {"updated": updated}


STALE_AFTER_HOURS = 24


def _stale_cutoff() -> str:
    return (datetime.now() - timedelta(hours=STALE_AFTER_HOURS)).isoformat()


def list_stale_sends() -> list:
    """Sends accepted by Elastic Email but never produced an event — no event after a day."""
    return get_db().execute("""
        SELECT e.id, e.seq, e.subject, e.body, e.sent_at, e.message_id,
               p.email, p.contact_name, p.company
        FROM emails e JOIN prospects p ON p.id = e.prospect_id
        WHERE e.last_event IS NULL AND e.sent_at < ?
        ORDER BY e.sent_at
    """, (_stale_cutoff(),)).fetchall()


def resend_stale() -> dict:
    """Re-send the stale rows and repoint them at the new messageId.

    The body already lives on the row, so this resends the exact mail that was
    dropped rather than regenerating a different one.
    """
    con = get_db()
    sent, failed = 0, []
    for r in list_stale_sends():
        if con.execute(
            f"SELECT 1 FROM prospects p WHERE p.id = "
            f"(SELECT prospect_id FROM emails WHERE id = ?) AND {_suppress_sql('p')}",
            (r["id"],),
        ).fetchone() is None:
            failed.append((r["email"], "bounced or unsubscribed since"))
            continue
        res = send_email_elastic(r["email"], r["contact_name"], r["subject"], r["body"])
        if not res["success"]:
            failed.append((r["email"], res["error"]))
            continue
        con.execute("UPDATE emails SET message_id=?, sent_at=? WHERE id=?",
                    (res.get("message_id", ""), datetime.now().isoformat(), r["id"]))
        sent += 1
    con.commit()
    return {"sent": sent, "failed": failed}


# ---------- AGGREGATE STATS ----------
def get_delivery_stats(date_filter: str = None) -> dict:
    con = get_db()
    if date_filter:
        sent      = con.execute("SELECT COUNT(*) FROM emails WHERE date(sent_at) = ?", (date_filter,)).fetchone()[0]
        delivered = con.execute("SELECT COUNT(*) FROM emails WHERE delivered=1 AND bounced=0 AND date(sent_at) = ?", (date_filter,)).fetchone()[0]
        opened    = con.execute("SELECT COUNT(*) FROM emails WHERE opened=1 AND date(sent_at) = ?", (date_filter,)).fetchone()[0]
        bounced   = con.execute("SELECT COUNT(*) FROM emails WHERE bounced=1 AND date(sent_at) = ?", (date_filter,)).fetchone()[0]
    else:
        sent      = con.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        delivered = con.execute("SELECT COUNT(*) FROM emails WHERE delivered=1 AND bounced=0").fetchone()[0]
        opened    = con.execute("SELECT COUNT(*) FROM emails WHERE opened=1").fetchone()[0]
        bounced   = con.execute("SELECT COUNT(*) FROM emails WHERE bounced=1").fetchone()[0]
    proxy = con.execute(
        "SELECT COUNT(*) FROM emails WHERE proxy_open=1"
        + (" AND date(sent_at) = ?" if date_filter else ""),
        (date_filter,) if date_filter else (),
    ).fetchone()[0]
    replies = con.execute(
        "SELECT COUNT(*) FROM prospects WHERE reply_text IS NOT NULL AND reply_text != ''"
    ).fetchone()[0]
    def count(where):
        return con.execute(
            f"SELECT COUNT(*) FROM emails WHERE {where}"
            + (" AND date(sent_at) = ?" if date_filter else ""),
            (date_filter,) if date_filter else (),
        ).fetchone()[0]

    hard_bounced = count("bounce_type='hard'")
    soft_bounced = count("bounce_type='soft'")
    unsubscribed = count("unsubscribed=1")
    # Elastic Email returns a MessageID immediately; if no event arrives within
    # 24h the mail was dropped/infinite-queued, not delayed. Events normally
    # land in minutes, so anything still silent after a day was dropped.
    cutoff = _stale_cutoff()
    pending = count(f"last_event IS NULL AND sent_at >= '{cutoff}'")
    stale   = count(f"last_event IS NULL AND sent_at <  '{cutoff}'")
    return {
        "stale": stale,
        "sent": sent, "delivered": delivered,
        "opened": opened, "proxy_opened": proxy, "bounced": bounced,
        "hard_bounced": hard_bounced, "soft_bounced": soft_bounced,
        "unsubscribed": unsubscribed, "pending": pending,
        "replies": replies,
        # Opens are soft: privacy proxies fire the pixel unread, so treat this as
        # an upper bound. Reply rate is the metric that cannot be faked.
        "open_rate":   round(opened / delivered * 100, 1) if delivered else 0,
        "reply_rate":  round(replies / delivered * 100, 1) if delivered else 0,
        "bounce_rate": round(bounced / sent * 100, 1) if sent else 0,
    }


# ---------- PER-PROSPECT DELIVERY REPORT ----------
def get_delivery_report(date_filter: str = None) -> list:
    con = get_db()
    if date_filter:
        rows = con.execute("""
            SELECT p.company, p.email, e.seq, e.subject, e.sent_at,
                   e.delivered, e.opened, e.proxy_open, e.bounced, e.bounce_type,
                   e.unsubscribed, e.last_event
            FROM emails e JOIN prospects p ON p.id = e.prospect_id
            WHERE date(e.sent_at) = ?
            ORDER BY e.sent_at DESC
        """, (date_filter,)).fetchall()
    else:
        rows = con.execute("""
            SELECT p.company, p.email, e.seq, e.subject, e.sent_at,
                   e.delivered, e.opened, e.proxy_open, e.bounced, e.bounce_type,
                   e.unsubscribed, e.last_event
            FROM emails e JOIN prospects p ON p.id = e.prospect_id
            ORDER BY e.sent_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ---------- CSV IMPORT ----------
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prospects.csv")

def import_prospects(csv_path: str = CSV_PATH) -> dict:
    """Import prospects from CSV. Returns stats with dedup info."""
    import csv

    if not os.path.exists(csv_path):
        return {"imported": 0, "skipped": 0, "error": f"CSV not found: {csv_path}"}

    con = get_db()
    imported, skipped, dup_email, dup_domain, dup_company = 0, 0, 0, 0, 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                email = row.get("email", "").strip().lower()
                domain = row.get("domain", "").strip().lower()
                company = row.get("company", "").strip().lower()
                
                if not email or "@" not in email:
                    skipped += 1
                    continue

                # Check if email already exists
                existing_email = con.execute(
                    "SELECT id FROM prospects WHERE LOWER(email) = ?", (email,)
                ).fetchone()
                if existing_email:
                    dup_email += 1
                    continue

                # Check if domain already exists
                existing_domain = con.execute(
                    "SELECT id FROM prospects WHERE LOWER(domain) = ?", (domain,)
                ).fetchone()
                if existing_domain:
                    dup_domain += 1
                    continue

                # Check if company name already exists
                existing_company = con.execute(
                    "SELECT id FROM prospects WHERE LOWER(company) = ?", (company,)
                ).fetchone()
                if existing_company:
                    dup_company += 1
                    continue

                con.execute(
                    """
                    INSERT INTO prospects 
                    (company, domain, contact_name, email, person_title,
                     email_type, email_confidence, email_method,
                     website_info, niche, first_subject, body, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
                """,
                    (
                        row.get("company", ""),
                        row.get("domain", ""),
                        row.get("contact_name", ""),
                        email,
                        row.get("person_title", ""),
                        row.get("email_type", ""),
                        row.get("email_confidence", ""),
                        row.get("email_method", ""),
                        row.get("website_info", ""),
                        row.get("niche", ""),
                        row.get("subject", ""),
                        row.get("body", ""),
                    ),
                )
                imported += 1
            except Exception as e:
                print(f"  ⚠ Error on row: {e}")
                skipped += 1

    con.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "dup_email": dup_email,
        "dup_domain": dup_domain,
        "dup_company": dup_company,
    }


# ---------- ELASTIC EMAIL SEND ----------
def send_email_elastic(to_email: str, to_name: str, subject: str, body: str) -> dict:
    """Send via Elastic Email REST API. Returns {success, message_id} or {success: False, error}.

    Auth is the API key (header X-ElasticEmail-ApiKey). The response's MessageID
    is the value we later match against /events for open/delivery/bounce tracking.
    NOTE: SENDER_EMAIL must be a verified sender on the Elastic Email account.
    The transactional API takes recipient emails as a string list, so a per-
    recipient display name can't be set here; the From-name comes from the
    verified sender profile in the Elastic Email account.
    """
    html = body.replace("\n", "<br>")
    payload = {
        "Recipients": {"To": [formataddr((to_name, to_email)) if to_name else to_email]},
        "Content": {
            "Body": [
                {"ContentType": "HTML", "Content": html, "Charset": "utf-8"},
                {"ContentType": "PlainText", "Content": body, "Charset": "utf-8"},
            ],
            "From": formataddr((SENDER_NAME, SENDER_EMAIL)),
            "ReplyTo": SENDER_EMAIL,
            "Subject": subject,
        },
    }

    try:
        r = requests.post(
            f"{EE_API_URL}/emails/transactional",
            headers={
                "X-ElasticEmail-ApiKey": EE_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {"success": True,
                    "message_id": data.get("MessageID")
                    or data.get("TransactionID") or ""}
        else:
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------- ADDRESS VERIFICATION ----------
def count_unverified_drafts() -> int:
    """Queued drafts whose address has not been SMTP-checked yet."""
    return get_db().execute(
        "SELECT COUNT(*) FROM prospects WHERE status='new' "
        "AND (verified_at IS NULL OR verified_at='')"
    ).fetchone()[0]


def count_queued_drafts() -> int:
    """All prospects awaiting a first send, not just the page shown in the UI."""
    return get_db().execute(
        "SELECT COUNT(*) FROM prospects WHERE status='new'"
    ).fetchone()[0]


def last_verified_at() -> str:
    """Most recent verification timestamp across queued drafts."""
    row = get_db().execute(
        "SELECT MAX(verified_at) FROM prospects WHERE status='new'"
    ).fetchone()
    return row[0] or ""


def verify_queued(prospect_ids=None, force: bool = False, progress=None) -> dict:
    """SMTP-verify queued drafts and hold back anything unconfirmed.

    Every domain is probed with a bogus address first: on a catch-all domain a
    250 proves nothing, so those addresses are parked at status='unverified'
    rather than sent. Bounces on inferred addresses are what put this account
    at a 15.6% bounce rate.
    """
    import csv as _csv

    import verify_email

    con = get_db()
    sql = ("SELECT id, company, domain, email, email_method FROM prospects "
           "WHERE status = 'new'")
    params = []
    if not force:
        sql += " AND (verified_at IS NULL OR verified_at = '')"
    if prospect_ids:
        sql += f" AND id IN ({','.join('?' * len(prospect_ids))})"
        params += list(prospect_ids)
    rows = con.execute(sql, params).fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reasons = {
        "CATCHALL": "catchall — 250 for any address, cannot confirm",
        "DEAD": "smtp_550 — address rejected",
        "ERROR": "mx_unreachable — could not verify",
    }
    log_path = os.path.join(os.path.dirname(DB_PATH), "processed_log.csv")
    cache, kept, held, details = {}, 0, 0, []

    for i, r in enumerate(rows):
        if progress:
            progress(i, len(rows), r["company"])

        # SMTP call happens OUTSIDE any transaction. Holding one open across the
        # network locked the database for the whole run and broke the UI.
        addr, code, ca, verdict = verify_email.verify([r["email"]], catchall=cache)[0]

        # An address printed on the company's own site is evidenced by publication,
        # not by SMTP. On a catch-all domain the probe proves nothing either way, so
        # it must not overturn that evidence. A hard 550 still does — that is a real
        # contradiction, not an absence of signal.
        published = (r["email_method"] or "").startswith("published")
        if published and verdict == "CATCHALL":
            verdict = "PUBLISHED"

        details.append({"company": r["company"], "email": addr, "verdict": verdict})

        # One short write per address, committed immediately, so the run is also
        # resumable: whatever was checked stays checked if it is interrupted.
        if verdict in ("VERIFIED", "PUBLISHED"):
            con.execute(
                "UPDATE prospects SET verified_at = ? WHERE id = ?", (now, r["id"])
            )
            kept += 1
        else:
            con.execute(
                "UPDATE prospects SET status = 'unverified', verified_at = ? WHERE id = ?",
                (now, r["id"]),
            )
            held += 1
        con.commit()

        if verdict not in ("VERIFIED", "PUBLISHED"):
            with open(log_path, "a", newline="") as f:
                _csv.DictWriter(f, fieldnames=[
                    "company", "domain", "email", "status", "added_at", "batch", "reason"
                ]).writerow({
                    "company": r["company"], "domain": r["domain"], "email": r["email"],
                    "status": "skipped", "added_at": now, "batch": "verify_queued",
                    "reason": reasons.get(verdict, verdict),
                })

    if progress:
        progress(len(rows), len(rows), "done")
    return {"checked": len(rows), "kept": kept, "held": held, "details": details}


# ---------- SUPPRESSION ----------
def _suppress_sql(alias: str = "prospects") -> str:
    """Return the NOT EXISTS clause that filters out bounced / unsubscribed.

    ``alias`` is the table alias used in the outer query (e.g. 'p' or 'prospects').
    """
    return f"""NOT EXISTS (
    SELECT 1 FROM emails e2 WHERE e2.prospect_id = {alias}.id
      AND (e2.bounced = 1 OR e2.last_event IN ('hardBounces', 'unsubscribed'))
)"""


# Legacy constant — works only when the table is NOT aliased.
SUPPRESS_SQL = _suppress_sql("prospects")


def suppress_bad_addresses() -> dict:
    """Take bounced and unsubscribed prospects out of every send queue.

    Run after sync_email_status(). Re-mailing a hard bounce compounds the
    reputation damage; re-mailing an unsubscribe is a CAN-SPAM violation.
    """
    con = get_db()
    unsub = con.execute("""
        UPDATE prospects SET status = 'unsubscribed'
        WHERE status IN ('new', 'emailed')
          AND EXISTS (SELECT 1 FROM emails e WHERE e.prospect_id = prospects.id
                        AND e.last_event = 'unsubscribed')
    """).rowcount
    bounced = con.execute("""
        UPDATE prospects SET status = 'bounced'
        WHERE status IN ('new', 'emailed')
          AND EXISTS (SELECT 1 FROM emails e WHERE e.prospect_id = prospects.id
                        AND (e.bounced = 1 OR e.last_event = 'hardBounces'))
    """).rowcount
    con.commit()
    return {"bounced": bounced, "unsubscribed": unsub}


# ---------- SEND ORCHESTRATION ----------
def sent_today_count() -> int:
    con = get_db()
    count = con.execute("""
        SELECT COUNT(*) FROM emails 
        WHERE date(sent_at) = date('now', 'localtime')
    """).fetchone()[0]
    return count


def send_pending_emails(dry_run: bool = True) -> dict:
    """
    Send emails to 'new' prospects.
    dry_run=True = draft only (human approves via UI)
    dry_run=False = actually send
    """
    con = get_db()
    budget = max(0, DAILY_CAP - sent_today_count())

    if budget == 0:
        return {"sent": 0, "remaining_budget": 0, "details": []}

    # Get new prospects (prefer HIGH confidence first)
    prospects = con.execute(f"""
        SELECT * FROM prospects 
        WHERE status = 'new'
          AND {SUPPRESS_SQL}
        ORDER BY 
            CASE email_confidence 
                WHEN 'HIGH' THEN 1 
                WHEN 'MEDIUM' THEN 2 
                ELSE 3 
            END,
            created_at ASC
    """).fetchall()

    sent = []
    for p in prospects[:budget]:
        try:
            subject, body = generate_email(p)
        except MissingCopy as e:
            print(f"⚠ skipping {p['company']}: {e}")
            sent.append({"action": "error", "company": p["company"], "error": str(e)})
            continue

        if dry_run:
            sent.append(
                {
                    "action": "draft",
                    "prospect_id": p["id"],
                    "company": p["company"],
                    "contact": p["contact_name"] or p["email"],
                    "email": p["email"],
                    "confidence": p["email_confidence"],
                    "subject": subject,
                    "body": body,
                }
            )
        else:
            result = send_email_elastic(
                p["email"], p["contact_name"] or p["company"], subject, body
            )

            if result["success"]:
                con.execute(
                    """
                    UPDATE prospects 
                    SET status='emailed', 
                        emails_sent = emails_sent + 1,
                        last_sent_at = ?,
                        first_subject = ?
                    WHERE id = ?
                """,
                    (datetime.now().isoformat(), subject, p["id"]),
                )

                con.execute(
                    """
                    INSERT INTO emails (prospect_id, seq, subject, body, sent_at, message_id)
                    VALUES (?, 1, ?, ?, ?, ?)
                """,
                    (
                        p["id"],
                        subject,
                        body,
                        datetime.now().isoformat(),
                        result.get("message_id", ""),
                    ),
                )
                save_followup_context(con, p["id"])

                sent.append(
                    {
                        "action": "sent",
                        "company": p["company"],
                        "email": p["email"],
                        "subject": subject,
                    }
                )
            else:
                sent.append(
                    {
                        "action": "error",
                        "company": p["company"],
                        "error": result["error"],
                    }
                )

    con.commit()

    return {
        "sent": len([s for s in sent if s.get("action") == "sent"]),
        "drafted": len([s for s in sent if s.get("action") == "draft"]),
        "errors": len([s for s in sent if s.get("action") == "error"]),
        "remaining_budget": budget
        - len([s for s in sent if s.get("action") == "sent"]),
        "details": sent,
    }


def send_approved(prospect_id: int) -> dict:
    """Send one approved prospect by ID."""
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()

    if not p:
        return {"success": False, "error": "Prospect not found"}

    if p["status"] != "new":
        return {"success": False, "error": f"Already in status: {p['status']}"}

    # Use stored draft if available, otherwise generate
    try:
        subject, body = generate_email(p)
    except MissingCopy as e:
        return {"success": False, "error": str(e)}

    result = send_email_elastic(
        p["email"], p["contact_name"] or p["company"], subject, body
    )

    if result["success"]:
        con.execute(
            """
            UPDATE prospects 
            SET status='emailed', 
                emails_sent = emails_sent + 1,
                last_sent_at = ?,
                first_subject = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), subject, p["id"]),
        )

        con.execute(
            """
            INSERT INTO emails (prospect_id, seq, subject, body, sent_at, message_id)
            VALUES (?, 1, ?, ?, ?, ?)
        """,
            (
                p["id"],
                subject,
                body,
                datetime.now().isoformat(),
                result.get("message_id", ""),
            ),
        )
        save_followup_context(con, p["id"])
        con.commit()
        return {"success": True, "company": p["company"]}
    else:
        return {"success": False, "error": result["error"]}


class MissingCopy(Exception):
    """A prospect reached the sender with no researched copy."""


# Sign-off is enforced here, not trusted to the CSV. Most rows written before
# batch9 have no sign-off at all; the old fallback template supplied one, so
# making CSV copy authoritative would have shipped unsigned emails.
SIGNATURE = "Thanks,\nGourav\nFounder, BetterBundle"


def ensure_signature(body: str) -> str:
    """Guarantee every outgoing email ends with the sign-off, exactly once."""
    body = (body or "").rstrip()
    if "Founder, BetterBundle" in body:
        return body
    return f"{body}\n\n{SIGNATURE}"


# Sentence boundary: a terminator, whitespace, then something that starts a new
# sentence. Requiring the lookahead keeps "$1M-$10M" and "2,416" intact.
_SENTENCE = re.compile(r'(?<=[.?!])\s+(?=[A-Z0-9£€"\u201c])')

# Role-address disclaimer from the old skill. It was written as an opener, which
# buries the hook under an apology; it belongs at the end if it appears at all.
_DISCLAIMER = "If this isn't yours, forward to whoever runs your Shopify store"


def format_email(body: str, contact_name: str = "") -> str:
    """Greeting, paragraphs, sign-off.

    Whitespace and ordering only — never changes a word of the researched copy,
    because that copy is the deliverable and no LLM touches the first email.
    """
    body = (body or "").strip()
    if not body:
        return body

    # Drop an existing sign-off; it is re-added last.
    for marker in ("Thanks,\nGourav", "\nGourav\nFounder"):
        if marker in body:
            body = body[: body.index(marker)].rstrip()

    already_greeted = body.lower().startswith(("hi ", "hey ", "hello "))

    sentences = [x.strip() for x in _SENTENCE.split(body) if x.strip()]

    # Move the forward-me disclaimer out of the opening slot.
    disclaimer = ""
    for i, sent in enumerate(sentences):
        if _DISCLAIMER in sent:
            disclaimer = sentences.pop(i)
            break

    if not sentences:
        return ensure_signature(body)

    # The closing question stands alone; everything else pairs up.
    tail = sentences.pop() if sentences[-1].endswith("?") else ""
    paras = [" ".join(sentences[i : i + 2]) for i in range(0, len(sentences), 2)]
    if tail:
        paras.append(tail)
    if disclaimer:
        paras.append(disclaimer)

    out = "\n\n".join(paras)
    if not already_greeted:
        first = (contact_name or "").strip().split(" ")[0]
        out = f"Hi {first},\n\n{out}" if first else f"Hi there,\n\n{out}"
    return ensure_signature(out)


def _demo_format_email():
    """Self-check: greeting added, paragraphs split, disclaimer moved, sign-off once."""
    raw = ("If this isn't yours, forward to whoever runs your Shopify store "
           "— I'll owe you a coffee. MTC Kitchen lists 2,416 products on Shopify. "
           "Your product pages recommend by collection, not by what actually sells "
           "together. At 2,400+ products that is a lot of missed pairings. "
           "Want the bundle report?")
    out = format_email(raw, "Dan Kowalski")
    assert out.startswith("Hi Dan,\n\n"), out[:30]
    assert out.count("Founder, BetterBundle") == 1
    assert "\n\n" in out and out.count("\n\n") >= 4
    assert "2,416" in out and "2,400+" in out          # numbers survive intact
    assert out.index("Want the bundle report") < out.index(_DISCLAIMER)  # disclaimer demoted
    assert format_email(out, "Dan Kowalski") == out    # idempotent
    assert format_email("", "Dan") == ""
    print("format_email demo OK")


def generate_email(p) -> tuple:
    """Return the researched subject/body for a prospect.

    Deliberately does NOT call an LLM. The discovery skill writes subject/body
    into prospects.csv and those ship verbatim; Gemini is for follow-ups only.
    Raising here is the point: a prospect with no copy must be skipped loudly,
    never papered over with a template.
    """
    subject = (p["first_subject"] or "").strip()
    body = (p["body"] or "").strip()
    if not subject or not body:
        raise MissingCopy(
            f"{p['company']}: no researched copy. Run Import CSV, or write "
            f"subject/body for this row in prospects.csv."
        )
    return subject, format_email(body, p["contact_name"])


# ---------- FOLLOW-UP CONTEXT ----------
# Signature of the fallback template that shipped to the first 45 prospects.
FALLBACK_MARKER = "is impressive. But feed tools format data"

def build_followup_context(p, first_email=None) -> str:
    """Freeze what we knew about a prospect and what we actually said to them."""
    parts = [
        f"Company: {p['company']} ({p['domain']})",
        f"Contact: {p['contact_name'] or 'unknown'} - {p['person_title'] or 'unknown title'}",
        f"Prospect type: {p['niche'] or 'store'}",
        f"Researched facts, from their own site: {p['website_info'] or 'none recorded'}",
    ]
    if first_email:
        body = first_email["body"] or ""
        parts.append(
            "--- ALREADY SENT TO THEM. Do not repeat, quote or paraphrase any of it. "
            "It is here only so the follow-up says something different. ---"
        )
        if FALLBACK_MARKER in body:
            parts.append(
                "WARNING: this email shipped from a broken template. Its text is cut "
                "off mid-sentence and is NOT a reliable source of facts about them. "
                "Draw every claim from the researched facts above, never from here."
            )
        parts.append(f"Email 1 subject: {first_email['subject']}")
        parts.append(f"Email 1 body:\n{body}")
    return "\n".join(parts)


def save_followup_context(con, prospect_id: int) -> str:
    """Persist the context for a prospect. Called once email 1 is away."""
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    e = con.execute(
        "SELECT subject, body FROM emails WHERE prospect_id = ? AND seq = 1 ORDER BY id LIMIT 1",
        (prospect_id,),
    ).fetchone()
    ctx = build_followup_context(p, e)
    con.execute(
        "UPDATE prospects SET followup_context = ? WHERE id = ?", (ctx, prospect_id)
    )
    return ctx


def backfill_followup_context() -> int:
    """Build context for prospects emailed before this existed."""
    con = get_db()
    rows = con.execute(
        """SELECT id FROM prospects
           WHERE status != 'new'
             AND (followup_context IS NULL OR followup_context = '')"""
    ).fetchall()
    for r in rows:
        save_followup_context(con, r["id"])
    con.commit()
    return len(rows)


# ---------- FOLLOW-UPS ----------
FOLLOWUP_RULES = """Hard rules:
- NEVER invent numbers, percentages, case studies, client names, results or
  timelines. Use only facts present in the context above. If you have no number,
  write the sentence without one.
- NO FLATTERY. Never write "is impressive", "love what you're doing", "caught my
  eye", "great work", or any compliment. State the observation flat and move on.
- No links.
- Plain text. No markdown, no bullet points, no subject line.
- No greeting line. Start with the first sentence; the greeting is added later.
- No CRM-speak. Never write "closing this file", "reaching out regarding your
  <anything> needs", "circling back", "touching base", or "moving forward".
- Signature exactly:
Thanks,
Gourav
Founder, BetterBundle"""


def _followup_prompt(ctx: str, seq: int, niche: str = "store") -> str:
    # Stores own the lost revenue directly; an agency is talking about a client's.
    catalog = "one client store" if niche == "agency" else "their store"
    if seq == 2:
        return f"""Write follow-up email #2 for BetterBundle, a Shopify app that reads a
store's own order history to find which products genuinely sell together, then
shows those pairings on product pages, in the cart and at checkout. Offer: a
free bundle report on {catalog}, built from their public catalog, no install
needed.

CONTEXT
{ctx}

This email MUST STAND ALONE. Assume they never opened email 1. Do not say
"following up", "bumping this", "as I mentioned", or refer to the earlier email
in any way. Lead with a different fact from the context than email 1 used.

Structure, 70 words maximum:
1. One specific, true observation from the context.
2. The gap: most stores recommend by collection or tag, which is a guess about
   what goes together. Real co-purchase data is already sitting in their order
   history and nothing is reading it. For a store, the missed revenue is theirs
   directly — never say "your clients" to a store.
3. The free bundle report on {catalog}, and that it needs no install.
4. An easy out: tell them to reply "no thanks" and you will stop.

{FOLLOWUP_RULES}

Return ONLY the body text."""

    return f"""Write a short breakup email for BetterBundle, a Shopify app that
recommends products based on what a store's own orders show selling together.

CONTEXT
{ctx}

They have not replied. Close the loop gracefully and stop asking for anything.

Structure, 50 words maximum, in this exact order:
1. State plainly that you will stop reaching out.
2. One line on what BetterBundle does, so it is memorable if the problem shows up
   later, noting there is no monthly fee — it bills only on revenue it can
   attribute to its own recommendations.
3. LAST SENTENCE: a genuine, non-pushy sign-off wishing them well. The email must
   NOT end on the offer or on anything resembling an ask. No new question.

{FOLLOWUP_RULES}

Return ONLY the body text."""


# Numbers that come from our own offer, not from the prospect's research.
# The only number our own offer contributes. There is deliberately no price
# here: commission_rate is a runtime value and has never been fixed, so any
# rate or cap quoted in an email would be fabricated.
OFFER_NUMBERS = {"5"}

# CRM-speak the model reaches for when told to close a loop. Prompt-banned above;
# checked here too, because a banned phrase is as deterministic as a bad number.
BANNED_PHRASES = (
    "closing this file", "circling back", "circle back", "touching base",
    "touch base", "moving forward", "reach out regarding your",
    "reaching out regarding your",
)


def banned_phrases(body: str) -> list:
    low = body.lower()
    return [p for p in BANNED_PHRASES if p in low]


def _demo_followup_review():
    """Self-check: the two draft rejections, and the greeting the model no longer writes."""
    sent = "I am closing this file and will not reach out again."
    assert banned_phrases(sent) == ["closing this file"]
    assert banned_phrases("I will stop reaching out. BetterBundle finds bundles.") == []
    assert invented_numbers("We fixed 4,000 SKUs.", "Catalog: 900 items") == ["4,000"]
    assert invented_numbers("The report covers 5 pairings.", "Catalog: 900") == []
    out = format_email("I will stop reaching out. BetterBundle only bills on "
                       "revenue it can attribute. Best of luck with the year.",
                       "Tony Sambell")
    assert out.startswith("Hi Tony,\n\n"), out[:30]
    assert out.count("Founder, BetterBundle") == 1
    print("followup_review demo OK")


def invented_numbers(body: str, ctx: str) -> list:
    """Numbers asserted in `body` that appear nowhere in `ctx`.

    A cheap guard against the model inventing metrics. Numbers are the highest
    risk claim in a cold email and the easiest to check deterministically.
    """
    def nums(text):
        # Trailing punctuation is sentence grammar, not part of the number:
        # "$1,000,000." and "$1,000,000/month" are the same claim.
        return {m.strip(".,") for m in re.findall(r"\d[\d,.]*", text) if m.strip(".,")}

    return sorted(nums(body) - nums(ctx) - OFFER_NUMBERS)


def generate_followup(p, seq: int, attempts: int = 2) -> str:
    """Write follow-up `seq` for a prospect from its saved context.

    Rejects any draft asserting a number absent from the context or using banned
    CRM-speak. Raises if the model fails or keeps doing it. Greeting and paragraph
    breaks come from format_email, same as email 1 — the model never writes them.
    """
    ctx = (p["followup_context"] or "").strip() or build_followup_context(p)
    prompt = _followup_prompt(ctx, seq, (p["niche"] or "store").strip().lower())

    retry = None
    for attempt in range(attempts):
        body = llm(prompt if attempt == 0 else prompt + f"\n\n{retry}")
        bad_nums = invented_numbers(body, ctx)
        bad_words = banned_phrases(body)
        if not bad_nums and not bad_words:
            return format_email(body, p["contact_name"])
        if bad_nums:
            retry = (
                f"Your previous draft asserted {', '.join(bad_nums)}, which appears "
                f"nowhere in the context. Rewrite it using no numbers beyond those "
                f"in the context."
            )
        else:
            retry = (
                f"Your previous draft used the banned phrase(s) "
                f"{', '.join(bad_words)}. Rewrite it in plain, direct language."
            )
        print(f"⚠ follow-up #{seq} for {p['company']}: {retry.splitlines()[0]}")

    raise RuntimeError(f"{p['company']}: follow-up #{seq} failed review — {retry}")


def send_followups(dry_run: bool = True, prospect_id: int = None) -> dict:
    """Send scheduled follow-ups (Day 3 = Email 2, Day 7 = Email 3).

    prospect_id=None sends every due prospect; set it to send exactly one.
    Each body is generated per prospect from its saved context. A generation
    failure skips that prospect and is reported; nothing generic is ever sent.
    """
    con = get_db()
    budget = max(0, DAILY_CAP - sent_today_count())
    results = []

    for seq, days, terminal in ((2, FOLLOWUP2_DAYS, False),
                                (3, FOLLOWUP3_DAYS - FOLLOWUP2_DAYS, True)):
        if budget <= 0:
            break

        due = con.execute(
            f"""
            SELECT * FROM prospects
            WHERE status='emailed'
              AND emails_sent = ?
              AND julianday('now','localtime') - julianday(last_sent_at) >= ?
              AND (? IS NULL OR id = ?)
              AND {SUPPRESS_SQL}
            ORDER BY last_sent_at ASC
        """,
            (seq - 1, days, prospect_id, prospect_id),
        ).fetchall()

        for p in due[:budget]:
            try:
                body = generate_followup(p, seq)
            except Exception as e:
                print(f"⚠ follow-up #{seq} generation failed for {p['company']}: {e}")
                results.append(
                    {"action": "error", "seq": seq, "company": p["company"],
                     "error": str(e)[:200]}
                )
                continue

            # Thread onto email 1 only if that exact subject really went out.
            # For the prospects whose email 1 shipped the fallback template, their
            # researched subject was never seen — send it fresh, not as a reply.
            base = p["first_subject"] or f"{p['company']} and product feeds"
            was_sent = con.execute(
                "SELECT 1 FROM emails WHERE prospect_id = ? AND subject = ? LIMIT 1",
                (p["id"], base),
            ).fetchone()
            subject = base if not was_sent or base.lower().startswith("re:") else f"Re: {base}"

            if dry_run:
                results.append(
                    {"action": "draft", "seq": seq, "company": p["company"],
                     "email": p["email"], "subject": subject, "body": body}
                )
                continue

            result = send_email_elastic(p["email"], p["contact_name"], subject, body)
            if not result["success"]:
                results.append(
                    {"action": "error", "seq": seq, "company": p["company"],
                     "error": result["error"]}
                )
                continue

            con.execute(
                """
                UPDATE prospects
                SET emails_sent = ?, last_sent_at = ?, status = ?
                WHERE id = ?
            """,
                (seq, datetime.now().isoformat(),
                 "dead" if terminal else "emailed", p["id"]),
            )
            con.execute(
                """
                INSERT INTO emails (prospect_id, seq, subject, body, sent_at, message_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (p["id"], seq, subject, body, datetime.now().isoformat(),
                 result.get("message_id", "")),
            )
            results.append(
                {"action": "sent_breakup" if terminal else "sent_followup2",
                 "seq": seq, "company": p["company"], "subject": subject}
            )
            budget -= 1

    con.commit()
    sent = [r for r in results if str(r.get("action", "")).startswith("sent")]
    return {
        "followups": results,
        "count": len(sent),
        "drafted": len([r for r in results if r.get("action") == "draft"]),
        "errors": len([r for r in results if r.get("action") == "error"]),
    }


# A prospect is a genuine lead only if a human opened AND the copy they saw was
# researched. An open on the fallback template is the opposite of warm: they read
# a truncated blurb ending in "is impressive" and closed it.
_DUE_SQL = f"""
    SELECT p.id, p.company, p.contact_name, p.email, p.first_subject, p.last_sent_at,
           julianday('now','localtime') - julianday(p.last_sent_at) as days_since,
           COALESCE(ev.human_open, 0) as human_open,
           COALESCE(ev.fallback, 0)   as fallback,
           COALESCE(ev.human_open AND NOT ev.fallback, 0) as genuine
    FROM prospects p
    LEFT JOIN (
        SELECT prospect_id,
               MAX(opened AND NOT proxy_open)      as human_open,
               MAX(seq = 1 AND body LIKE :marker)  as fallback
        FROM emails GROUP BY prospect_id
    ) ev ON ev.prospect_id = p.id
    WHERE p.status='emailed'
      AND p.emails_sent = :sent
      AND julianday('now','localtime') - julianday(p.last_sent_at) >= :days
      AND {_suppress_sql('p')}
    ORDER BY genuine DESC, human_open DESC, p.last_sent_at ASC
"""


def get_followups_due() -> dict:
    """Prospects due for follow-up #2 and #3 (without sending).

    Each row carries human_open / fallback / genuine so the UI can rank real
    leads above the ones that only ever saw the broken template.
    """
    con = get_db()
    marker = f"%{FALLBACK_MARKER}%"

    def due(sent, days):
        rows = con.execute(_DUE_SQL, {"marker": marker, "sent": sent, "days": days})
        return [dict(r) for r in rows]

    return {
        "followup2": due(1, FOLLOWUP2_DAYS),
        "followup3": due(2, FOLLOWUP3_DAYS - FOLLOWUP2_DAYS),
    }


def _demo_followups_due():
    """Self-check: genuine leads sort first, fallback opens are not genuine."""
    rows = get_followups_due()["followup2"]
    if not rows:
        print("followups demo skipped (none due)")
        return
    for r in rows:
        assert r["genuine"] == (r["human_open"] and not r["fallback"]), r["company"]
    keys = [(-r["genuine"], -r["human_open"]) for r in rows]
    assert keys == sorted(keys), "genuine leads must sort first"
    print(f"followups demo OK ({sum(r['genuine'] for r in rows)} genuine of {len(rows)})")


# ---------- REPLY MONITORING ----------
def get_body(msg) -> str:
    """Extract body from email message."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(errors="ignore")
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return re.sub("<[^>]+>", " ", payload.decode(errors="ignore"))
    return ""


def check_replies() -> dict:
    """Poll Gmail for replies and classify them."""
    if not GMAIL_USER or not GMAIL_APP_PASS:
        return {"error": "GMAIL_USER or GMAIL_APP_PASS not set"}

    con = get_db()
    replies_found = []

    try:
        M = imaplib.IMAP4_SSL(IMAP_SERVER)
        M.login(GMAIL_USER, GMAIL_APP_PASS)
        M.select("INBOX")

        # Look for emails from the last 7 days
        since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")

        # Get all prospects we've emailed
        prospects = con.execute(
            "SELECT * FROM prospects WHERE status='emailed'"
        ).fetchall()
        prospect_emails = {p["email"].lower(): p for p in prospects}

        # Search for replies from these addresses
        for email_addr, p in prospect_emails.items():
            _, data = M.search(None, f'FROM "{email_addr}" SINCE {since}')

            for num in data[0].split()[-2:]:  # Last 2 messages
                _, msg_data = M.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                body = get_body(msg)
                if not body or len(body) < 5:
                    continue

                # Skip if we've already processed this (simple check)
                if p["reply_text"] and body[:50] in p["reply_text"]:
                    continue

                # Classify with LLM
                prompt = f"""Classify this email reply into EXACTLY one category:

INTERESTED — wants the bundle report, asks for more info, says yes
OBJECTION — has concerns (price, timing, not sure)
DECLINED — clear no, unsubscribe, not interested
UNREADABLE — can't tell, needs human review

Reply: {body[:500]}

Return ONLY the category name."""

                try:
                    classification = llm(prompt).upper()
                    if classification not in (
                        "INTERESTED",
                        "OBJECTION",
                        "DECLINED",
                        "UNREADABLE",
                    ):
                        classification = "UNREADABLE"
                except:
                    classification = "UNREADABLE"

                # Update DB
                new_status = {
                    "INTERESTED": "interested",
                    "OBJECTION": "objection",
                    "DECLINED": "dead",
                    "UNREADABLE": "emailed",  # Keep as emailed for manual review
                }.get(classification, "emailed")

                rebuttal = ""
                if classification == "OBJECTION":
                    try:
                        rebuttal = llm(
                            f"""Write a 60-word friendly rebuttal for BetterBundle, a
Shopify app that recommends products based on what a store's own orders show
selling together.
Objection: {body[:300]}
Include: the bundle report is free and needs no install, and the app carries no
monthly fee - it bills only on revenue it can attribute.
Never state a percentage, rate, cap or dollar figure: the rate is not fixed."""
                        )
                    except:
                        rebuttal = ""

                con.execute(
                    """
                    UPDATE prospects 
                    SET status = ?, 
                        reply_text = ?,
                        reply_classification = ?,
                        rebuttal_draft = ?,
                        last_sent_at = ?
                    WHERE id = ?
                """,
                    (
                        new_status,
                        body,
                        classification,
                        rebuttal,
                        datetime.now().isoformat(),
                        p["id"],
                    ),
                )

                replies_found.append(
                    {
                        "company": p["company"],
                        "email": p["email"],
                        "classification": classification,
                        "reply_preview": body[:200],
                        "rebuttal": rebuttal[:200] if rebuttal else None,
                    }
                )

        M.logout()
    except Exception as e:
        return {"error": str(e), "replies": replies_found}

    con.commit()
    return {"replies": replies_found, "count": len(replies_found)}


# ---------- REPORTING ----------
def get_pipeline_report(date_filter: str = None) -> dict:
    """Get full pipeline status. Optional date_filter = 'YYYY-MM-DD'."""
    con = get_db()

    if date_filter:
        total = con.execute("SELECT COUNT(*) FROM prospects WHERE date(created_at) = ?", (date_filter,)).fetchone()[0]
        by_status = con.execute("""
            SELECT status, COUNT(*) as count 
            FROM prospects 
            WHERE date(created_at) = ?
            GROUP BY status
        """, (date_filter,)).fetchall()
    else:
        total = con.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        by_status = con.execute("""
            SELECT status, COUNT(*) as count 
            FROM prospects 
            GROUP BY status
        """).fetchall()

    interested = con.execute("""
        SELECT company, email, contact_name, reply_text 
        FROM prospects 
        WHERE status='interested'
        AND date(last_sent_at) = COALESCE(?, date(last_sent_at))
        ORDER BY last_sent_at DESC
    """, (date_filter,)).fetchall()

    objections = con.execute("""
        SELECT company, email, contact_name, reply_text, rebuttal_draft
        FROM prospects 
        WHERE status='objection'
        AND date(last_sent_at) = COALESCE(?, date(last_sent_at))
        ORDER BY last_sent_at DESC
    """, (date_filter,)).fetchall()

    today_sent = con.execute("""
        SELECT COUNT(*) FROM emails 
        WHERE date(sent_at) = COALESCE(?, date('now', 'localtime'))
    """, (date_filter,)).fetchone()[0]


    return {
        "total_prospects": total,
        "by_status": dict(by_status),
        "interested": [dict(r) for r in interested],
        "objections": [dict(r) for r in objections],
        "sent_today": today_sent,
        "daily_cap": DAILY_CAP,
        "remaining_today": DAILY_CAP - today_sent,
    }


def get_drafts() -> list:
    """Get pending emails to approve. Generates email once, stores in DB."""
    con = get_db()
    new_prospects = con.execute("""
        SELECT * FROM prospects 
        WHERE status='new'
        ORDER BY 
            CASE email_confidence 
                WHEN 'HIGH' THEN 1 
                WHEN 'MEDIUM' THEN 2 
                ELSE 3 
            END
        LIMIT 20
    """).fetchall()

    drafts = []
    for p in new_prospects:
        subject = (p["first_subject"] or "").strip()
        body = (p["body"] or "").strip()
        # No copy means the CSV was never imported for this row. Say so in the
        # UI rather than inventing something — that is what shipped 45 templates.
        if not subject or not body:
            subject = subject or "⚠ NO COPY — run Import CSV"
            body = body or (
                f"No researched copy for {p['company']}. Its subject/body are in "
                f"prospects.csv but were never imported. Click Import CSV, or paste "
                f"the copy here before approving."
            )
        drafts.append(
            {
                "id": p["id"],
                "company": p["company"],
                "contact_name": p["contact_name"],
                "email": p["email"],
                "confidence": p["email_confidence"],
                "subject": subject,
                # Show the sign-off the sender will add, so the preview is the email.
                "body": format_email(body, p["contact_name"]),
            }
        )

    return drafts


def update_draft(prospect_id: int, subject: str, body: str) -> dict:
    """Update the draft subject/body for a prospect before sending."""
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"success": False, "error": "Prospect not found"}
    if p["status"] != "new":
        return {"success": False, "error": f"Cannot edit draft — already {p['status']}"}

    con.execute(
        """
        UPDATE prospects 
        SET first_subject = ?, body = ?
        WHERE id = ?
    """,
        (subject, body, prospect_id),
    )
    con.commit()
    return {"success": True}


def reject_prospect(prospect_id: int) -> dict:
    """Reject a prospect — mark as 'rejected' so never sent to again."""
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"success": False, "error": "Prospect not found"}
    if p["status"] != "new":
        return {"success": False, "error": f"Cannot reject — already {p['status']}"}

    con.execute("UPDATE prospects SET status='rejected' WHERE id = ?", (prospect_id,))
    con.commit()
    return {"success": True, "company": p["company"]}


# ---------- FOLLOW-UP DRAFT (human-in-the-loop) ----------
def generate_followup_preview(prospect_id: int, seq: int) -> dict:
    """Generate a follow-up draft via LLM and store it in the DB.

    Returns the draft so the UI can display it for editing before sending.
    seq=2 for Day 3 bump, seq=3 for Day 7 breakup.
    """
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"success": False, "error": "Prospect not found"}
    # Skip bounced / unsubscribed — never generate a follow-up for them.
    has_bounce_or_unsub = not con.execute(
        f"SELECT 1 FROM prospects WHERE id = ? AND {SUPPRESS_SQL}",
        (prospect_id,),
    ).fetchone()
    if has_bounce_or_unsub:
        return {"success": False, "error": "Prospect has bounced or unsubscribed — skipped"}

    try:
        body = generate_followup(p, seq)
    except Exception as e:
        return {"success": False, "error": str(e)}

    base = p["first_subject"] or f"{p['company']} and product feeds"
    was_sent = con.execute(
        "SELECT 1 FROM emails WHERE prospect_id = ? AND subject = ? LIMIT 1",
        (p["id"], base),
    ).fetchone()
    subject = base if not was_sent or base.lower().startswith("re:") else f"Re: {base}"

    # Store the pending draft in the DB
    con.execute(
        """UPDATE prospects
        SET pending_followup_subject = ?, pending_followup_body = ?, pending_followup_seq = ?
        WHERE id = ?""",
        (subject, body, seq, prospect_id),
    )
    con.commit()

    return {
        "success": True,
        "prospect_id": prospect_id,
        "company": p["company"],
        "email": p["email"],
        "contact_name": p["contact_name"],
        "seq": seq,
        "subject": subject,
        "body": body,
    }


def get_pending_followups() -> list:
    """Return prospects that have a pending follow-up draft saved in the DB."""
    con = get_db()
    rows = con.execute("""
        SELECT id, company, email, contact_name,
               pending_followup_subject, pending_followup_body, pending_followup_seq,
               first_subject, last_sent_at,
               julianday('now','localtime') - julianday(last_sent_at) as days_since
        FROM prospects
        WHERE pending_followup_subject IS NOT NULL
          AND pending_followup_subject != ''
          AND pending_followup_body IS NOT NULL
          AND pending_followup_body != ''
          AND pending_followup_seq IS NOT NULL
          AND status = 'emailed'
        ORDER BY last_sent_at ASC
    """).fetchall()
    return [dict(r) for r in rows]


def save_followup_draft(prospect_id: int, subject: str, body: str) -> dict:
    """Save edits to a pending follow-up draft."""
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"success": False, "error": "Prospect not found"}
    if not p["pending_followup_seq"]:
        return {"success": False, "error": "No pending follow-up draft"}

    con.execute(
        "UPDATE prospects SET pending_followup_subject = ?, pending_followup_body = ? WHERE id = ?",
        (subject, body, prospect_id),
    )
    con.commit()
    return {"success": True}


def clear_followup_draft(prospect_id: int) -> None:
    """Clear the pending follow-up draft columns after sending or discarding."""
    con = get_db()
    con.execute(
        "UPDATE prospects SET pending_followup_subject = NULL, pending_followup_body = NULL, pending_followup_seq = NULL WHERE id = ?",
        (prospect_id,),
    )
    con.commit()


def send_followup_draft(prospect_id: int) -> dict:
    """Send the pending follow-up draft for a prospect via Elastic Email."""
    con = get_db()
    p = con.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
    if not p:
        return {"success": False, "error": "Prospect not found"}

    subject = (p["pending_followup_subject"] or "").strip()
    body = (p["pending_followup_body"] or "").strip()
    seq = p["pending_followup_seq"]

    if not subject or not body or not seq:
        return {"success": False, "error": "No pending follow-up draft found"}

    # Refuse to send to bounced / unsubscribed addresses.
    has_bounce_or_unsub = not con.execute(
        f"SELECT 1 FROM prospects WHERE id = ? AND {SUPPRESS_SQL}",
        (prospect_id,),
    ).fetchone()
    if has_bounce_or_unsub:
        clear_followup_draft(prospect_id)
        return {"success": False, "error": "Prospect has bounced or unsubscribed — draft discarded"}

    result = send_email_elastic(p["email"], p["contact_name"], subject, body)
    if not result["success"]:
        return {"success": False, "error": result["error"]}

    terminal = (seq >= 3)
    con.execute(
        """UPDATE prospects
        SET emails_sent = ?, last_sent_at = ?, status = ?,
            pending_followup_subject = NULL, pending_followup_body = NULL, pending_followup_seq = NULL
        WHERE id = ?""",
        (seq, datetime.now().isoformat(), "dead" if terminal else "emailed", prospect_id),
    )
    con.execute(
        """INSERT INTO emails (prospect_id, seq, subject, body, sent_at, message_id)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (prospect_id, seq, subject, body, datetime.now().isoformat(),
         result.get("message_id", "")),
    )
    con.commit()
    return {"success": True, "company": p["company"], "seq": seq}


# ---------- SMOKE TEST ----------
def smoke_test(to_email: str, wait_secs: int = 90):
    """Exercise the whole send path once against a real address.

    Generator of (ok, label, detail) so the UI can stream progress. Sends one
    real email — point it at your own inbox.
    """
    yield bool(EE_API_KEY), "Elastic Email API key", "set" if EE_API_KEY else "missing"
    yield bool(GEMINI_API_KEY), "Gemini API key", "set" if GEMINI_API_KEY else "missing"
    yield (bool(GMAIL_USER and GMAIL_APP_PASS), "Gmail IMAP creds",
           GMAIL_USER or "missing")

    # Sender domain must be authenticated or everything lands in spam.
    try:
        r = requests.get(f"{EE_API_URL}/domains", timeout=20,
                         headers={"X-ElasticEmail-ApiKey": EE_API_KEY})
        dom = SENDER_EMAIL.split("@")[-1].lower()
        hit = next((d for d in r.json() if dom in (d.get("Domain") or "").lower()), None)
        if hit:
            miss = [k for k in ("Spf", "Dkim", "MX", "DMARC") if not hit.get(k)]
            yield not miss, f"Sender domain {dom}", "SPF/DKIM/MX/DMARC ok" if not miss \
                else f"unverified: {', '.join(miss)}"
        else:
            yield False, f"Sender domain {dom}", "not on the Elastic Email account"
    except Exception as e:
        yield False, "Sender domain", str(e)

    try:
        yield True, "Gemini call", llm("Reply with the single word: ok")[:40]
    except Exception as e:
        yield False, "Gemini call", str(e)

    stamp = datetime.now().strftime("%H:%M:%S")
    res = send_email_elastic(to_email, "", f"BetterBundle smoke test {stamp}",
                             f"Smoke test at {stamp}. Reply to this to test reply polling.")
    if not res["success"]:
        yield False, "Send via Elastic Email", res["error"]
        return
    mid = res["message_id"]
    yield True, "Send via Elastic Email", f"MessageID {mid}"

    # The real check: does /events come back keyed by a MsgID we can match?
    deadline = time.time() + wait_secs
    seen = []
    while time.time() < deadline:
        seen = [e for e in elastic_fetch_events(days=1)
                if (e.get("MsgID") or "").strip("<>") == mid.strip("<>")]
        if seen:
            break
        time.sleep(10)
    if not seen:
        yield False, "Event sync", f"no event for {mid} within {wait_secs}s"
        return
    flags = _ee_flags(seen)
    yield True, "Event sync", (f"{len(seen)} event(s): "
                               f"{', '.join(sorted({_ee_type(e) for e in seen}))} → {flags}")

    try:
        M = imaplib.IMAP4_SSL(IMAP_SERVER)
        M.login(GMAIL_USER, GMAIL_APP_PASS)
        M.select("INBOX")
        typ, data = M.search(None, 'SUBJECT', f'"smoke test {stamp}"')
        M.logout()
        hits = len(data[0].split()) if data and data[0] else 0
        yield hits > 0, "Inbox delivery (IMAP)", \
            f"{hits} matching message(s) in {GMAIL_USER}" if hits else \
            "not in inbox yet — check spam, or re-run in a minute"
    except Exception as e:
        yield False, "Inbox delivery (IMAP)", str(e)
