#!/usr/bin/env python3
"""
Import OpenObserve configuration — idempotently.

    SLACK_WEBHOOK_URL=https://... ./import.py <endpoint> <org> <api_key>

Runs on every deploy, so it cannot simply POST. `POST /api/{org}/dashboards`
creates a NEW dashboard each time it is called, so the previous POST-only
script would have left the org with one more copy of every dashboard after
every deploy. Each resource is therefore matched against what is already there
— dashboards by title, alerts and templates and destinations by name — and
updated in place when it exists.

Python rather than bash+jq: this runs on the production host over SSH, where
python3 ships with Ubuntu and jq does not. Standard library only, no pip
install in the deploy path.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ImportError_(Exception):
    """A single resource failed to import. Raised rather than exiting, so the
    caller can decide whether one failure should stop the run."""


def request(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Basic {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise ImportError_(f"HTTP {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise ImportError_(f"unreachable: {e.reason}")


def wait_for(url, key, attempts=30, delay=2):
    """Block until OpenObserve answers, or give up.

    The importer runs as a one-shot container alongside OpenObserve, which has
    no healthcheck to depend on, and it takes a few seconds to open its port on
    a cold start. Without this the very first deploy after a reboot races the
    database and imports nothing — silently, because the container exits 1 and
    nothing downstream is watching.
    """
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Basic {key}")
            urllib.request.urlopen(req, timeout=5).read()
            return
        except Exception:
            if i == attempts - 1:
                raise SystemExit(f"OpenObserve did not answer at {url} after {attempts} tries")
            time.sleep(delay)


FAILURES: list = []


def load(subdir):
    """Every .json in a subdirectory, sorted so import order is reproducible."""
    return sorted((HERE / subdir).glob("*.json"))


def sync(label, files, existing, create, update, render=None, tolerant=False):
    """Create what is missing, update what is not, and say which happened.

    `existing` maps name -> whatever `update` needs to address the resource.
    Saying "updated" vs "created" out loud is the point: a deploy log that says
    "created" for a dashboard that already existed is the duplicate bug
    announcing itself.
    """
    print(f"{label}:")
    for path in files:
        body = json.loads(path.read_text())
        if render:
            body = render(body)
        name = body.get("title") or body.get("name") or path.stem
        try:
            if name in existing:
                update(existing[name], body)
                print(f"  updated: {name}")
            else:
                create(body)
                print(f"  created: {name}")
        except ImportError_ as e:
            if not tolerant:
                raise SystemExit(f"  FAILED {label[:-1].lower()} {name}: {e}")
            # Tolerated for alerts only. OpenObserve refuses an alert whose
            # stream does not exist yet, and a metric stream is not created
            # until the metric fires once -- so a freshly renamed metric makes
            # its alert unimportable until real traffic arrives. Failing the
            # whole deploy over that would mean one cold metric blocks every
            # other alert, and the next import fixes it by itself.
            FAILURES.append((label, name, str(e)))
            print(f"  SKIPPED: {name} -- {str(e).splitlines()[0][:110]}")


def do_alerts(endpoint, org, key):
    alerts = {
        a["name"]: a["alert_id"]
        for a in (request("GET", f"{endpoint}/api/v2/{org}/alerts", key).get("list") or [])
        if a.get("name") and a.get("alert_id")
    }
    sync(
        "Alerts",
        load("alerts"),
        alerts,
        lambda b: request("POST", f"{endpoint}/api/v2/{org}/alerts", key, b),
        lambda i, b: request("PUT", f"{endpoint}/api/v2/{org}/alerts/{i}", key, b),
        tolerant=True,
    )


def do_dashboards(api, key):
    # A dashboard update needs both its id and its current hash — OpenObserve
    # uses the hash for optimistic concurrency and rejects a PUT without it.
    dash = {
        d["title"]: (d["dashboard_id"], d.get("hash", ""))
        for d in request("GET", f"{api}/dashboards", key).get("dashboards", [])
        if d.get("title")
    }
    sync(
        "Dashboards",
        load("dashboards"),
        dash,
        lambda b: request("POST", f"{api}/dashboards", key, b),
        lambda ref, b: request("PUT", f"{api}/dashboards/{ref[0]}?hash={ref[1]}", key, b),
    )


def main():
    # Argv wins, environment is the fallback. The env path is what the compose
    # service uses: `${VAR}` inside a compose `command:` is interpolated by
    # Compose from the host shell, NOT from `env_file`, so passing the key as an
    # argument there would silently hand the container an empty string.
    def arg(i, env, default=""):
        if len(sys.argv) > i and sys.argv[i]:
            return sys.argv[i]
        return os.environ.get(env, default)

    endpoint = arg(1, "OPENOBSERVE_ENDPOINT", "http://localhost:5080").rstrip("/")
    org = arg(2, "OPENOBSERVE_ORG", "default")
    key = arg(3, "OPENOBSERVE_API_KEY")
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")

    if not key:
        raise SystemExit("Error: API key is required. Usage: import.py [endpoint] [org] <api_key>")

    api = f"{endpoint}/api/{org}"
    wait_for(f"{api}/streams", key)

    names = lambda rows: {r["name"]: r["name"] for r in rows if r.get("name")}

    # Order matters: alerts reference destinations, destinations reference
    # templates. Creating an alert before its destination exists is rejected.
    sync(
        "Templates",
        load("templates"),
        names(request("GET", f"{api}/alerts/templates", key) or []),
        lambda b: request("POST", f"{api}/alerts/templates", key, b),
        lambda n, b: request("PUT", f"{api}/alerts/templates/{n}", key, b),
    )

    existing_dests = names(request("GET", f"{api}/alerts/destinations", key) or [])

    # A missing webhook means we cannot CREATE the Slack destination -- it is the
    # one field that only the secret can supply. It does not mean we should skip
    # the alerts: if the destination already exists in this org (imported
    # earlier, or created by hand) the alert definitions are importable and
    # should be, because an alert left pointing at a renamed stream does not
    # error, it just silently never fires.
    if not webhook:
        print("Destinations: SKIPPED - SLACK_WEBHOOK_URL is not set.")
        if existing_dests:
            print(f"  Existing destination(s) found ({', '.join(existing_dests)}); "
                  "alerts will still be imported against them.")
        else:
            print("  No destination exists either, so alerts are skipped too: an "
                  "alert with nowhere to fire is worse than no alert.")
        do_dashboards(api, key)
        if existing_dests:
            do_alerts(endpoint, org, key)
        report()
        return

    sync(
        "Destinations",
        load("destinations"),
        names(request("GET", f"{api}/alerts/destinations", key) or []),
        lambda b: request("POST", f"{api}/alerts/destinations", key, b),
        lambda n, b: request("PUT", f"{api}/alerts/destinations/{n}", key, b),
        # The webhook is a secret, so the file carries a placeholder and the
        # real URL is substituted here rather than being committed.
        render=lambda b: json.loads(
            json.dumps(b).replace("SLACK_WEBHOOK_URL_PLACEHOLDER", webhook)
        ),
    )

    do_dashboards(api, key)

    do_alerts(endpoint, org, key)

    report()


def report():
    if FAILURES:
        print(f"\nDone, with {len(FAILURES)} skipped:")
        for label, name, err in FAILURES:
            print(f"  {label[:-1]} {name}")
        print("  These re-import on the next run once their streams exist.")
    else:
        print("Done!")


if __name__ == "__main__":
    main()
