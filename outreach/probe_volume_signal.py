#!/usr/bin/env python3
"""Conservative sales-volume signal probe for the discovery-skill.md playbook.

This is observation only. It does NOT claim a live social follower count unless we
can read an explicit number from the page, and it does NOT fetch private APIs.
"""

import json
from pathlib import Path

def probe_volume_signal(page_text: str, reviews_count: int | None, social_count: int | None) -> dict:
    """Return a structured observation suitable for website_info and volume-gate tracking."""
    hit = None
    if reviews_count is not None and reviews_count >= 100:
        hit = {"kind": "review_widget_total", "value": reviews_count}
    elif social_count is not None and social_count >= 10000:
        hit = {"kind": "social_follower_total", "value": social_count}
    else:
        # weak/no signal
        hit = {"kind": "no_volume_signal", "value": None}
    return {"hit": hit, "page_text_len": len(page_text)}


def main() -> None:
    print(json.dumps({
        "note": "Stub probe for volume signal; fill from real page observations.",
        "implemented": False,
    }))


if __name__ == "__main__":
    main()
