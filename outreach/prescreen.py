#!/usr/bin/env python3
"""Pre-screen domains: is the MX reachable, and is it a catch-all?
Only non-catchall + reachable domains are worth researching a name for."""
import sys, time
sys.path.insert(0, "/Users/gouravkargwal/asin-upc/leads")
from verify_email import rcpt, BOGUS

for d in sys.argv[1:]:
    code = rcpt(f"{BOGUS}@{d}")
    if isinstance(code, str):
        verdict = f"UNREACHABLE ({code})"
    elif code == 250:
        verdict = "CATCHALL"
    else:
        verdict = f"GOOD (probe={code})"
    print(f"{d:<38} {verdict}")
    time.sleep(1)
