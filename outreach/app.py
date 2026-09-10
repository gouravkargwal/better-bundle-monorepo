"""
Skuvio Outreach UI — Human-in-the-loop during warmup.
Run: streamlit run app.py
"""

import streamlit as st
from datetime import datetime, timedelta, date
import engine

st.set_page_config(page_title="Skuvio Outreach", page_icon="🚀", layout="wide")

st.title("🚀 Skuvio Outreach Engine")
st.caption(
    f"Daily cap: {engine.DAILY_CAP} emails · Warmup mode: human approves all sends"
)


# ---------- CACHED DATA LOADING ----------
@st.cache_data(ttl=60, show_spinner=False)
def _cached_pipeline_report(date_filter):
    return engine.get_pipeline_report(date_filter=date_filter)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_delivery_stats(date_filter):
    return engine.get_delivery_stats(date_filter=date_filter)

@st.cache_data(ttl=60, show_spinner=False)
def _cached_followups_due():
    return engine.get_followups_due()

def _clear_cache():
    _cached_pipeline_report.clear()
    _cached_delivery_stats.clear()
    _cached_followups_due.clear()


# ---------- DATE FILTER (sidebar) ----------
with st.sidebar:
    st.markdown("### 📅 Date Filter")

    # Initialize date offset in session state
    if "date_offset" not in st.session_state:
        st.session_state.date_offset = 0

    # Show 7 days per page, starting from today - offset
    today = date.today()
    page_start = today - timedelta(days=st.session_state.date_offset)

    # Date pills for this page
    dates = [(page_start - timedelta(days=i)) for i in range(7)]

    # Pagination arrows
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("◀ Older", key="date_older"):
            st.session_state.date_offset += 7
            st.rerun()
    with col_next:
        if st.session_state.date_offset > 0:
            if st.button("Newer ▶", key="date_newer"):
                st.session_state.date_offset = max(0, st.session_state.date_offset - 7)
                st.rerun()

    # Date pills as buttons
    for d in dates:
        label = d.strftime("%d %b")
        if d == today:
            label += " (today)"
        if d == today - timedelta(days=1):
            label += " (yesterday)"
        # Highlight selected date
        is_selected = st.session_state.get("selected_date") == d.isoformat()
        if st.button(label, key=f"date_{d.isoformat()}", type="primary" if is_selected else "secondary"):
            st.session_state.selected_date = d.isoformat()
            _clear_cache()
            st.rerun()

    # Show "All time" option
    if st.button("🌐 All Time", key="date_all", type="primary" if st.session_state.get("selected_date") is None else "secondary"):
        st.session_state.selected_date = None
        _clear_cache()
        st.rerun()

    selected_date = st.session_state.get("selected_date")

    st.divider()

    # Pipeline stats (filtered by date) — cached
    report = _cached_pipeline_report(selected_date)

    st.markdown("### 📊 Pipeline")
    st.metric("Total prospects", report["total_prospects"])
    st.metric("Sent today", f"{report['sent_today']} / {report['daily_cap']}")

    st.markdown("**Status breakdown**")
    for status, count in report["by_status"].items():
        st.write(f"• {status}: {count}")

    st.divider()

    st.markdown("### ⚙️ Settings")
    st.write(f"Elastic Email API: {'✅' if engine.EE_API_KEY else '❌'}")
    st.write(f"Gmail: {'✅' if engine.GMAIL_APP_PASS else '❌'}")
    st.write(f"Gemini: {'✅' if engine.GEMINI_API_KEY else '❌'}")

# ---------- MAIN TABS ----------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📤 Send", "🔥 Hot Leads", "📝 Drafts", "📧 Follow-ups", "📈 Reports", "🧪 Test"]
)

# TAB 1: Send
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Import prospects.csv")
        if st.button("📥 Import CSV"):
            result = engine.import_prospects()
            _clear_cache()
            st.session_state["import_msg"] = (
                f"✅ Imported {result['imported']} · Skipped {result['skipped']}"
                + (f" · Dup email: {result.get('dup_email', 0)}" if result.get('dup_email') else "")
                + (f" · Dup domain: {result.get('dup_domain', 0)}" if result.get('dup_domain') else "")
            )
            st.rerun()

    # Show import message if set
    if "import_msg" in st.session_state:
        st.success(st.session_state.pop("import_msg"))

    with col2:
        st.markdown("### Check Gmail replies")
        if st.button("📬 Poll Replies"):
            with st.spinner("Checking Gmail..."):
                result = engine.check_replies()
            _clear_cache()
            if "error" in result:
                st.error(f"Error: {result['error']}")
            elif result["count"] > 0:
                st.success(f"Found {result['count']} new replies!")
                for r in result["replies"]:
                    with st.expander(f"{r['company']} — {r['classification']}"):
                        st.write(f"**Email:** {r['email']}")
                        st.write(f"**Reply:** {r['reply_preview']}")
                        if r["rebuttal"]:
                            st.write(f"**Draft rebuttal:** {r['rebuttal']}")
            else:
                st.info("No new replies.")

# TAB 2: Hot Leads
with tab2:
    if selected_date:
        st.caption(f"📅 Showing data for: **{datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d %b %Y')}**")
    else:
        st.caption("📅 Showing all data")

    if report["interested"]:
        st.success(
            f"🔥 {len(report['interested'])} INTERESTED LEADS — reply personally NOW"
        )
        for lead in report["interested"]:
            with st.expander(f"**{lead['company']}** — {lead['email']}"):
                st.write(f"**Contact:** {lead['contact_name'] or 'N/A'}")
                st.markdown("**Their reply:**")
                st.info(lead["reply_text"][:500])
                st.link_button(
                    "✉️ Reply in Gmail",
                    f"https://mail.google.com/mail/?view=cm&to={lead['email']}",
                )
    else:
        st.info("No interested leads yet. Send more emails and wait for replies.")

    if report["objections"]:
        st.divider()
        st.warning(f"⚠️ {len(report['objections'])} OBJECTIONS — review rebuttals")
        for obj in report["objections"]:
            with st.expander(f"**{obj['company']}** — {obj['email']}"):
                st.markdown("**Their objection:**")
                st.info(obj["reply_text"][:300])
                if obj["rebuttal_draft"]:
                    st.markdown("**Draft rebuttal (edit before sending):**")
                    st.code(obj["rebuttal_draft"])

# TAB 3: Drafts (Approval)
with tab3:
    st.markdown("### ✍️ Pending Emails — Edit & Approve Before Send")
    st.caption("Edit subject/body, then approve to send immediately.")

    drafts = engine.get_drafts()

    # --- Verify addresses before any of these go out ---
    unchecked = engine.count_unverified_drafts()
    total_drafts = engine.count_queued_drafts()   # not len(drafts): get_drafts() pages at 20
    # Once everything is checked the button becomes a re-check rather than going
    # dead — addresses go stale, and a run can be interrupted part way through.
    recheck = unchecked == 0
    vcol1, vcol2 = st.columns([1, 2])
    with vcol1:
        verify_clicked = st.button(
            f"🔁 Re-verify all {total_drafts}" if recheck
            else f"🔍 Verify emails ({unchecked} unchecked)",
            disabled=total_drafts == 0,
            help="SMTP-checks each address against a catch-all control probe. "
                 "Verified and published drafts stay; unconfirmed ones are held "
                 "back, not sent.",
        )
    with vcol2:
        last = engine.last_verified_at()
        if recheck and last:
            st.caption(f"All {total_drafts} drafts checked (last run {last}). "
                       "Re-verify to check them again.")
        else:
            st.caption("~5s per address. Catch-all domains answer 250 for any "
                       "address, so a plain check cannot confirm them — those are "
                       "held back unless published on their own site.")

    if verify_clicked:
        bar = st.progress(0.0, text="Starting…")

        def _tick(i, total, company):
            bar.progress(i / total if total else 1.0, text=f"{i}/{total} — {company}")

        result = engine.verify_queued(force=recheck, progress=_tick)
        bar.empty()
        _clear_cache()
        st.session_state["draft_msg"] = (
            f"✅ Checked {result['checked']}: kept {result['kept']} verified, "
            f"held back {result['held']}"
        )
        if result["held"]:
            st.session_state["draft_held"] = [
                d for d in result["details"] if d["verdict"] != "VERIFIED"
            ]
        st.rerun()

    if "draft_held" in st.session_state:
        held = st.session_state.pop("draft_held")
        with st.expander(f"⛔ {len(held)} held back — not sent", expanded=True):
            for h in held:
                st.write(f"- **{h['company']}** · {h['email']} · `{h['verdict']}`")

    if not drafts:
        st.info("No pending drafts. Import more prospects from CSV.")
    else:
        remaining = report["remaining_today"]
        st.warning(
            f"⚠️ Can send {remaining} more emails today (cap: {engine.DAILY_CAP})"
        )

        for draft in drafts:
            with st.expander(
                f"**{draft['company']}** → {draft['email']} "
                f"({draft['confidence']} confidence)"
            ):
                # Editable fields
                new_subject = st.text_input(
                    "Subject",
                    value=draft["subject"],
                    key=f"subject_{draft['id']}",
                )
                new_body = st.text_area(
                    "Body",
                    value=draft["body"],
                    height=200,
                    key=f"body_{draft['id']}",
                )

                col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
                with col1:
                    if st.button(f"💾 Save Draft", key=f"save_{draft['id']}"):
                        result = engine.update_draft(
                            draft["id"], new_subject, new_body
                        )
                        if result["success"]:
                            st.session_state["draft_msg"] = "✅ Draft saved"
                            st.rerun()
                        else:
                            st.error(f"Error: {result.get('error')}")
                with col2:
                    if st.button(f"🔄 Regenerate", key=f"regen_{draft['id']}"):
                        with st.spinner(f"Re-rolling draft for {draft['company']}..."):
                            res = engine.regenerate_draft(draft["id"])
                        _clear_cache()
                        if res["success"]:
                            # Push the new copy straight into the widget keys.
                            # A keyed text_input reads from session_state, so
                            # setting the keys is what actually moves the boxes.
                            st.session_state[f"subject_{draft['id']}"] = res["subject"]
                            st.session_state[f"body_{draft['id']}"] = res["body"]
                            st.session_state["draft_msg"] = (
                                f"🔄 New draft for {draft['company']} — "
                                f"review the boxes above, then Save or Approve"
                            )
                            st.rerun()
                        else:
                            st.error(f"Error: {res.get('error')}")
                with col3:
                    if st.button(f"🚫 Reject", key=f"reject_{draft['id']}"):
                        result = engine.reject_prospect(draft["id"])
                        if result["success"]:
                            _clear_cache()
                            st.session_state["draft_msg"] = f"🚫 Rejected {result['company']}"
                            st.rerun()
                        else:
                            st.error(f"Error: {result.get('error')}")
                with col4:
                    if st.button(
                        f"✅ Approve & Send",
                        key=f"approve_{draft['id']}",
                        type="primary",
                    ):
                        if remaining <= 0:
                            st.error("Daily cap reached. Try again tomorrow.")
                        else:
                            # Save any edits first, then send
                            engine.update_draft(
                                draft["id"], new_subject, new_body
                            )
                            result = engine.send_approved(draft["id"])
                            if result["success"]:
                                _clear_cache()
                                st.session_state["draft_msg"] = f"✅ Sent to {result['company']}"
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")

        # Show draft message if set
        if "draft_msg" in st.session_state:
            st.success(st.session_state.pop("draft_msg"))

    # ---- Rejected leads (accidental rejects are recoverable here) ----
    rejected = engine.get_rejected()
    if rejected:
        st.divider()
        with st.expander(f"⛔ {len(rejected)} rejected — click to restore", expanded=False):
            st.caption(
                "Rejected leads sit out of the send queue. Restore one to put it "
                "back as a pending draft."
            )
            for r in rejected:
                rc1, rc2 = st.columns([5, 1])
                rc1.write(f"**{r['company']}** · {r['email']} · {r['contact_name'] or 'N/A'}")
                if rc2.button("♻️ Restore", key=f"restore_{r['id']}"):
                    res = engine.restore_prospect(r["id"])
                    if res["success"]:
                        _clear_cache()
                        st.session_state["draft_msg"] = (
                            f"♻️ Restored {res['company']} — it is back in the draft queue"
                        )
                        st.rerun()
                    else:
                        st.error(f"Error: {res.get('error')}")

# TAB 4: Follow-ups
with tab4:
    st.markdown("### 📧 Follow-ups Due")
    st.caption(
        "Prospects scheduled for Day 3 bump or Day 7 breakup. "
        "Click **Create Draft** to generate a follow-up, review/edit it, then send."
    )

    # ---- PENDING DRAFTS (already generated, awaiting edit & send) ----
    pending = engine.get_pending_followups()
    if pending:
        st.markdown("#### ✏️ Pending Follow-up Drafts — Edit & Send")
        for d in pending:
            seq_label = "#2 — Day 3 Bump" if d["pending_followup_seq"] == 2 else "#3 — Day 7 Breakup"
            with st.expander(
                f"✏️ **{d['company']}** → {d['email']} · Follow-up {seq_label}",
                expanded=True,
            ):
                st.write(f"**Contact:** {d['contact_name'] or 'N/A'}")
                st.write(f"**Last sent:** {d['last_sent_at'][:10] if d['last_sent_at'] else 'N/A'}")

                edit_subject = st.text_input(
                    "Subject",
                    value=d["pending_followup_subject"],
                    key=f"fu_sub_{d['id']}",
                )
                edit_body = st.text_area(
                    "Body",
                    value=d["pending_followup_body"],
                    height=220,
                    key=f"fu_body_{d['id']}",
                )

                scol1, scol2, scol3, scol4 = st.columns([1, 1, 1, 2])
                with scol1:
                    if st.button("💾 Save", key=f"fu_save_{d['id']}"):
                        res = engine.save_followup_draft(d["id"], edit_subject, edit_body)
                        if res["success"]:
                            st.session_state["fu_msg"] = f"💾 Draft saved for {d['company']}"
                            st.rerun()
                        else:
                            st.error(f"Error: {res.get('error')}")
                with scol2:
                    if st.button("🚫 Discard", key=f"fu_discard_{d['id']}"):
                        engine.clear_followup_draft(d["id"])
                        _clear_cache()
                        st.session_state["fu_msg"] = f"🗑️ Draft discarded for {d['company']}"
                        st.rerun()
                with scol3:
                    if st.button("🔄 Regenerate", key=f"fu_regen_{d['id']}"):
                        with st.spinner(f"Re-rolling follow-up for {d['company']}..."):
                            res = engine.regenerate_followup_draft(d["id"])
                        _clear_cache()
                        if res["success"]:
                            st.session_state[f"fu_sub_{d['id']}"] = res["subject"]
                            st.session_state[f"fu_body_{d['id']}"] = res["body"]
                            st.session_state["fu_msg"] = (
                                f"🔄 New draft for {d['company']} — review & send above"
                            )
                            st.rerun()
                        else:
                            st.error(f"Error: {res.get('error')}")
                with scol4:
                    if st.button("✅ Save & Send", key=f"fu_send_{d['id']}", type="primary"):
                        # Save edits first, then send
                        engine.save_followup_draft(d["id"], edit_subject, edit_body)
                        res = engine.send_followup_draft(d["id"])
                        if res["success"]:
                            _clear_cache()
                            st.session_state["fu_msg"] = f"✅ Sent follow-up to {d['company']}"
                            st.rerun()
                        else:
                            st.error(f"Error: {res.get('error')}")

        st.divider()

    # ---- DUE PROSPECTS (not yet drafted) ----
    due = _cached_followups_due()

    def _tier(p):
        """(badge, note) — genuine lead, cold, or poisoned by the fallback template."""
        if p["fallback"]:
            return ("☠️", "opened the broken template — needs new copy, not a thread"
                          if p["human_open"] else "got the broken template — needs new copy")
        if p["human_open"]:
            return ("🔥", "GENUINE LEAD — real copy, human open")
        return ("📭", "real copy, no open yet")

    all_due = due["followup2"] + due["followup3"]
    if all_due:
        st.markdown(
            f"🔥 **{sum(p['genuine'] for p in all_due)} genuine** · "
            f"📭 {sum(not p['genuine'] and not p['fallback'] for p in all_due)} unopened · "
            f"☠️ {sum(p['fallback'] for p in all_due)} got the broken template"
        )

    # Follow-up #2 (Day 3)
    st.markdown(f"#### 📬 Follow-up #2 — Day 3 Bump ({len(due['followup2'])} due)")
    if due["followup2"]:
        for p in due["followup2"]:
            badge, note = _tier(p)
            with st.expander(f"{badge} **{p['company']}** → {p['email']} · sent {p['days_since']:.0f}d ago"):
                st.caption(note)
                st.write(f"**Contact:** {p['contact_name'] or 'N/A'}")
                st.write(f"**Original subject:** {p['first_subject']}")
                st.write(f"**Last sent:** {p['last_sent_at'][:10] if p['last_sent_at'] else 'N/A'}")
                if st.button(f"📧 Create Follow-up #2 Draft", key=f"fu2_{p['id']}", type="primary"):
                    with st.spinner(f"Generating follow-up for {p['company']}..."):
                        res = engine.generate_followup_preview(p["id"], seq=2)
                    _clear_cache()
                    if res["success"]:
                        st.session_state["fu_msg"] = f"✏️ Draft created for {p['company']} — review & send above"
                        st.rerun()
                    else:
                        st.error(f"Error generating draft: {res.get('error')}")
    else:
        st.info("No follow-ups #2 due today.")

    st.divider()

    # Follow-up #3 (Day 7)
    st.markdown(f"#### 🔚 Follow-up #3 — Day 7 Breakup ({len(due['followup3'])} due)")
    if due["followup3"]:
        for p in due["followup3"]:
            badge, note = _tier(p)
            with st.expander(f"{badge} **{p['company']}** → {p['email']} · sent {p['days_since']:.0f}d ago"):
                st.caption(note)
                st.write(f"**Contact:** {p['contact_name'] or 'N/A'}")
                st.write(f"**Original subject:** {p['first_subject']}")
                st.write(f"**Last sent:** {p['last_sent_at'][:10] if p['last_sent_at'] else 'N/A'}")
                if st.button(f"🔚 Create Breakup Draft", key=f"fu3_{p['id']}", type="primary"):
                    with st.spinner(f"Generating breakup for {p['company']}..."):
                        res = engine.generate_followup_preview(p["id"], seq=3)
                    _clear_cache()
                    if res["success"]:
                        st.session_state["fu_msg"] = f"✏️ Breakup draft created for {p['company']} — review & send above"
                        st.rerun()
                    else:
                        st.error(f"Error generating draft: {res.get('error')}")
    else:
        st.info("No follow-ups #3 due today.")

    # Show follow-up message if set
    if "fu_msg" in st.session_state:
        st.success(st.session_state.pop("fu_msg"))

# TAB 5: Reports
with tab5:
    # Show active filter
    if selected_date:
        st.caption(f"📅 Showing data for: **{datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d %b %Y')}**")
    else:
        st.caption("📅 Showing all data")

    st.markdown("### 📡 Delivery Stats")

    if st.button("🔄 Sync status"):
        with st.spinner("Fetching delivery events..."):
            res = engine.sync_email_status()
        _clear_cache()
        st.session_state["sync_msg"] = f"✅ Synced {res['updated']} messages"
        st.rerun()

    # Show sync success message if set
    if "sync_msg" in st.session_state:
        st.success(st.session_state.pop("sync_msg"))

    stats = _cached_delivery_stats(selected_date)

    # Replies first: it is the only metric here that cannot be faked by a machine.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sent", stats["sent"])
    c2.metric("Delivered", stats["delivered"],
              help="Accepted and did not later bounce.")
    c3.metric("Replies", stats["replies"], f"{stats['reply_rate']}% reply rate")
    c4.metric("Bounced", stats["bounced"], f"{stats['bounce_rate']}%",
              delta_color="inverse",
              help="Keep under 3%. Above 5% risks the sending domain.")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Opened (human)", stats["opened"], f"{stats['open_rate']}% — soft metric",
              help="Upper bound only. Privacy proxies fire the tracking pixel "
                   "with nobody reading the mail, and not all of them are "
                   "detectable. Judge the campaign on replies, not this.")
    d2.metric("Proxy opens", stats["proxy_opened"],
              help="Apple Mail Privacy Protection and security scanners "
                   "pre-fetching the pixel. Detected machines, excluded from "
                   "the open count. The real number is higher.")
    d3.metric("Hard / soft bounces", f"{stats['hard_bounced']} / {stats['soft_bounced']}",
              help="Hard = address does not exist, suppressed permanently. "
                   "Soft = transient.")
    d4.metric("Unsubscribed", stats["unsubscribed"],
              help="Suppressed permanently. Re-mailing these is a CAN-SPAM "
                   "violation.")

    if stats["bounce_rate"] > 5:
        st.error(f"⚠️ Bounce rate {stats['bounce_rate']}% — above the 5% threshold "
                 "where providers start throttling. Verify addresses before sending.")
    if stats["pending"]:
        st.caption(f"{stats['pending']} sends have no events yet — click Sync.")
    if stats["stale"]:
        st.warning(
            f"❌ {stats['stale']} sends were accepted by Elastic Email but never "
            f"produced an event — no event after {engine.STALE_AFTER_HOURS}h. These never reached anyone."
        )
        if st.button(f"📤 Resend {stats['stale']} dropped sends"):
            with st.spinner("Resending..."):
                res = engine.resend_stale()
            _clear_cache()
            st.session_state["sync_msg"] = f"✅ Resent {res['sent']}" + (
                f" — failed: {res['failed']}" if res["failed"] else "")
            st.rerun()

    st.divider()
    st.markdown("### 📈 Pipeline & Delivery — Unified View")

    import pandas as pd
    con = engine.get_db()
    date_clause = "AND date(p.created_at) = ?" if selected_date else ""
    params = (selected_date,) if selected_date else ()

    df = pd.read_sql_query(
        f"""
        SELECT
            p.company,
            p.domain,
            p.email,
            p.contact_name,
            p.email_confidence,
            p.status,
            p.emails_sent,
            p.last_sent_at,
            p.reply_classification,
            e.seq,
            e.subject      AS last_subject,
            e.sent_at,
            e.delivered,
            e.opened,
            e.proxy_open,
            e.bounced,
            e.bounce_type,
            e.unsubscribed,
            e.last_event
        FROM prospects p
        LEFT JOIN emails e ON e.prospect_id = p.id
            AND e.id = (
                SELECT MAX(e2.id) FROM emails e2
                WHERE e2.prospect_id = p.id
            )
        WHERE 1=1 {date_clause}
        ORDER BY
            CASE p.status
                WHEN 'interested' THEN 0
                WHEN 'objection'  THEN 1
                WHEN 'emailed'    THEN 2
                WHEN 'new'        THEN 3
                ELSE 4
            END,
            p.last_sent_at DESC
        """,
        con,
        params=params,
    )

    if not df.empty:
        # Computed delivery-status column
        def _status(row):
            if row["unsubscribed"] == 1:
                return "🚫 unsubscribed"
            if row["bounced"] == 1:
                return f"❌ {row['bounce_type'] or ''} bounce".strip()
            if row["opened"] == 1 and row["proxy_open"] != 1:
                return "🔥 opened (human)"
            if row["proxy_open"] == 1:
                return "🤖 proxy open"
            if row["delivered"] == 1:
                return "✅ delivered"
            if pd.notna(row["sent_at"]):
                return "⏳ sent, no event"
            if row["status"] == "new":
                return "📝 draft"
            return row["status"] or ""

        df.insert(0, "delivery", df.apply(_status, axis=1))

        # Drop raw int columns now that we have the human-readable status
        df.drop(columns=["delivered", "opened", "proxy_open", "bounced",
                         "bounce_type", "unsubscribed"], inplace=True, errors="ignore")

        st.dataframe(df, width="stretch", height=min(400, 35 * len(df) + 40))
        st.download_button("⬇️ Download CSV", df.to_csv(index=False),
                           "skuvio_pipeline_report.csv", "text/csv")

        # Warm leads hint
        warm = df[df["delivery"].str.contains("opened \(human\)", na=False)]
        replied = set(l["email"] for l in report["interested"])
        warm_no_reply = warm[~warm["email"].isin(replied)]
        if not warm_no_reply.empty:
            st.info(
                f"👀 **{len(warm_no_reply)} opened but haven't replied yet** — warm leads. "
                "Follow-up #2 lands Day 3; don't nudge manually before that."
            )
    else:
        st.info("No data for this date. Import prospects or pick another date.")

# TAB 6: Test
with tab6:
    st.markdown("### End-to-end smoke test")
    st.caption(
        "Sends ONE real email, then waits for the Elastic Email event and checks "
        "it landed in the IMAP inbox. Point it at an address you own."
    )
    to = st.text_input("Send test to", value=engine.GMAIL_USER or "")
    wait = st.slider("Seconds to wait for the delivery event", 30, 180, 90, 15)
    if st.button("🧪 Run smoke test", type="primary", disabled=not to):
        for ok, label, detail in engine.smoke_test(to, wait_secs=wait):
            (st.success if ok else st.error)(f"**{label}** — {detail}")
        _clear_cache()

# ---------- FOOTER ----------
st.divider()
st.caption("""
**Warmup protocol (first 30 days):**
- Week 1: 10/day · Week 2: 15/day · Week 3: 20/day · Week 4: 30/day
- All sends require human approval above
- After warmup: remove approval requirement for autonomous mode
""")
