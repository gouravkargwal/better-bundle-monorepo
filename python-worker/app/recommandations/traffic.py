"""Which requests count as a real shopper seeing an offer.

Recommendations are served to everyone — a crawler that renders the widget and
a merchant previewing their theme should both see a working page. What they must
not do is write an `offer_impressions` row, because that row is the denominator
of the conversion rate the merchant is billed against. Every bot fetch and every
theme-preview reload inflates "offers shown" with impressions no human ever saw,
which drags the measured conversion rate down and understates the app's lift.
"""

import re
from typing import Optional

# Substrings that identify non-human traffic, matched case-insensitively.
#
# Deliberately conservative and substring-based rather than a full bot database:
# a false positive silently drops a real shopper's impression and loses billable
# revenue, which is far worse than letting an unusual crawler through. These
# cover the crawlers that actually execute JavaScript and therefore reach this
# endpoint at all.
_BOT_PATTERNS = (
    "bot",  # Googlebot, bingbot, AhrefsBot, Applebot, and most others
    "crawler",
    "spider",
    "slurp",  # Yahoo
    "headlesschrome",  # Puppeteer/Playwright defaults
    "phantomjs",
    "puppeteer",
    "playwright",
    "selenium",
    "lighthouse",  # PageSpeed / Web Vitals audits
    "pagespeed",
    "gtmetrix",
    "pingdom",
    "uptimerobot",
    "curl/",
    "wget/",
    "python-requests",
    "postmanruntime",
    "facebookexternalhit",  # link unfurlers
    "slackbot",
    "twitterbot",
    "whatsapp",
    "telegrambot",
    "discordbot",
    "embedly",
    "preview",  # generic link-preview fetchers
)

_BOT_RE = re.compile("|".join(re.escape(p) for p in _BOT_PATTERNS), re.IGNORECASE)


def is_bot(user_agent: Optional[str]) -> bool:
    """True when the User-Agent looks automated.

    A missing User-Agent counts as a bot: every real browser sends one, and an
    absent header is a script or a probe.
    """
    if not user_agent or not user_agent.strip():
        return True
    return bool(_BOT_RE.search(user_agent))


def demo() -> None:
    real = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    )
    bots = (
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (Macintosh) HeadlessChrome/140.0.0.0 Safari/537.36",
        "curl/8.4.0",
        "facebookexternalhit/1.1",
        "python-requests/2.32.0",
        None,
        "",
        "   ",
    )
    for ua in real:
        assert not is_bot(ua), f"false positive: {ua}"
    for ua in bots:
        assert is_bot(ua), f"missed bot: {ua!r}"
    print("traffic demo ok")


if __name__ == "__main__":
    demo()
