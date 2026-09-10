#!/usr/bin/env python3
"""Build a candidate domain pool for outreach/discovery-skill.md prospecting.

Output: outreach/discovery-skill.md candidate pool file or handoff, depending on
your request. By default this script does NOT send email and does NOT call SMTP.
It only assembles a pool and qualifies by what is cheaply observable.

This is a scaffold. It does not replace the per-prospect loop in discovery-skill.md.
"""

import json
from pathlib import Path

# Placeholder: fill this from your own research/queries, or replace with a search
# step that emits candidate domains. The skill says do the work directly, so the real
# content here should come from whatever discovery approach we pick.
CANDIDATES = [
    # Add candidate domains here. No free-mail domains. Prefer US/UK targets.
    # Exclude obvious competitors and enterprise up front if known.
]

BANNED_COMPETITORS = {
    "rebuyengine.com",
    "limespot.com",
    "codeblackbelt.com",
    "logbase.com",
    "reconvert.com",
    "aftersell.com",
    "zoorix.com",
    "glood.com",
    "nosto.com",
    "klevu.com",
    "boostcommerce.com",
    "searchspring.com",
    "dynamicyield.com",
    "algolia.com",
    "wiser.com",
    "selleasy.com",
}

FREE_MAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "yahoo.com",
    "hotmail.com",
    "icloud.com",
    "gmx.com",
    "aol.com",
}

def normalize_domain(d: str) -> str:
    d = d.strip().lower()
    if d.startswith("https://"):
        d = d.split("://", 1)[1]
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0].split(":")[0]

def is_free_mail_domain(d: str) -> bool:
    return d.split(".")[-2:] == list(FREE_MAIL_DOMAINS)  # naive; adjust as needed

def main() -> None:
    out = []
    for raw in CANDIDATES:
        d = normalize_domain(raw)
        if not d:
            continue
        if d in BANNED_COMPETITORS:
            continue
        out.append({"domain": d, "candidate": True})

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
