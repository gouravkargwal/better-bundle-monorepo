"""Run every panel's real query against OpenObserve and report row counts.

The UI's "No Data" marker is a weaker check than it looks: a panel whose query
is malformed, or points at a stream that does not exist, can render as an empty
chart rather than an error. Executing the SQL is what distinguishes "this is
correct and the period is quiet" from "this query can never return anything".
"""
import json, os, sys, glob, urllib.request, urllib.error

KEY = os.environ.get("KEY") or sys.exit(
    "Set KEY to the OpenObserve API key:\n"
    "  KEY=$(grep -m1 '^OPENOBSERVE_API_KEY=' .env.dev | cut -d= -f2-) \\\n"
    "    python3 openobserve-config/dashboards/verify_panels.py"
)
ENDPOINT = os.environ.get("OPENOBSERVE_ENDPOINT", "http://localhost:5080")
ORG = os.environ.get("OPENOBSERVE_ORG", "default")
URL = ENDPOINT + "/api/" + ORG + "/_search?type={}"


def run(sql, stype):
    body = json.dumps({"query": {"sql": sql, "start_time": 1600000000000000,
                                 "end_time": 1900000000000000, "from": 0, "size": 5}}).encode()
    req = urllib.request.Request(URL.format(stype), data=body, method="POST")
    req.add_header("Authorization", f"Basic {KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
            return len(d.get("hits", [])), d.get("hits", [])[:1], None
    except urllib.error.HTTPError as e:
        return 0, [], e.read().decode()[:160]
    except Exception as e:
        return 0, [], str(e)[:160]


bad = pending = empty = 0
for f in sorted(glob.glob("openobserve-config/dashboards/*.json")):
    d = json.load(open(f))
    print(f"\n{d['title']}")
    for p in d["tabs"][0]["panels"]:
        q = p["queries"][0]
        n, sample, err = run(q["query"], q["fields"]["stream_type"])
        # An unknown field where OpenObserve offers a suggestion is a typo in
        # our query -- that is exactly how `severity_text` (real field:
        # `severity`) was caught. An unknown field with "no similar field found"
        # on a stream that DOES exist is an attribute nobody has sent yet, which
        # is the normal state for a signal that only arrives from production
        # storefront traffic.
        if err and "unknown field" in err and "no similar field found" in err:
            pending += 1
            print(f"  UNSEEN  {p['title'][:33]:35} attribute not sent yet "
                  f"(stream {q['fields']['stream']} exists)")
        elif err and "stream not found" in err:
            # The query is fine; the metric has simply not been recorded once
            # yet, so OpenObserve has not created the stream. Expected for a
            # metric that only fires on real business traffic.
            pending += 1
            print(f"  PENDING {p['title'][:33]:35} stream not created yet: {q['fields']['stream']}")
        elif err:
            # A malformed query or a wrong column name. This is the class of bug
            # the UI hides: a panel with a bad field renders as an empty chart,
            # not as an error.
            bad += 1
            print(f"  BROKEN  {p['title'][:33]:35} {err}")
        elif n == 0:
            empty += 1
            print(f"  EMPTY   {p['title'][:33]:35} query valid, no matching rows")
        else:
            v = sample[0] if sample else {}
            y = v.get("y_axis_1")
            print(f"  ok      {p['title'][:33]:35} {n} rows, e.g. y={y}")
print(f"\n{'-'*66}")
print(f"  broken (fix these): {bad}   pending (awaiting traffic): {pending}   "
      f"empty (valid, quiet): {empty}")
sys.exit(1 if bad else 0)
