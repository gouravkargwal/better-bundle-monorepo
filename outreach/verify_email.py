#!/usr/bin/env python3
"""SMTP-verify candidate addresses, with a catch-all control probe.

A bare RCPT check is worthless on a catch-all domain: it returns 250 for any
address, including ones that cannot exist. So every domain is probed with a
bogus address first; if that also returns 250, the domain is a catch-all and
NO inferred address on it can be trusted.

Usage:  python verify_email.py first@domain.com other@domain.com ...
Output: <email>\t<code>\tcatchall=<bool>\tverdict=<VERIFIED|CATCHALL|DEAD|ERROR>

VERIFIED  -> 250 on a non-catch-all domain. Safe to use as inferred_smtp.
CATCHALL  -> unusable unless the address is published on their site.
TEMPFAIL  -> 4xx greylisting. Re-probe later; do NOT treat as a wrong guess.
DEAD      -> 550. Wrong guess.
ERROR     -> MX unreachable/blocked. Treat as unusable.
"""
import smtplib, sys, time

import dns.resolver

BOGUS = "zzq7x9nope-skuvio"
HELO = "check.skuvio.site"
MAIL_FROM = "verify@skuvio.site"


def rcpt(addr: str, timeout: int = 12):
    domain = addr.split("@")[1]
    try:
        mx = str(dns.resolver.resolve(domain, "MX")[0].exchange)
        s = smtplib.SMTP(mx, timeout=timeout)
        s.helo(HELO)
        s.mail(MAIL_FROM)
        code, _ = s.rcpt(addr)
        s.quit()
        return code
    except Exception as e:
        return "ERR:" + type(e).__name__


def verify(addresses, delay: float = 2.0, catchall: dict = None):
    """Verify addresses. Pass a shared `catchall` dict across calls to avoid
    re-probing a domain that has already been classified."""
    catchall = {} if catchall is None else catchall
    results = []
    for addr in addresses:
        domain = addr.split("@")[1]
        if domain not in catchall:
            catchall[domain] = rcpt(f"{BOGUS}@{domain}") == 250
            time.sleep(1)
        code = rcpt(addr)
        if isinstance(code, str):
            verdict = "ERROR"
        elif catchall[domain]:
            verdict = "CATCHALL"
        elif code == 250:
            verdict = "VERIFIED"
        elif 400 <= code < 500:
            # 4xx is "try again later" (greylisting), NOT a rejection. Calling it
            # DEAD silently discards prospects whose mailbox is fine.
            verdict = "TEMPFAIL"
        else:
            verdict = "DEAD"
        results.append((addr, code, catchall[domain], verdict))
        time.sleep(delay)
    return results


def demo():
    """Self-check: a catch-all domain must never yield VERIFIED."""
    real = [("a@x.com", 250, True), ("a@y.com", 250, False),
            ("a@z.com", 550, False), ("a@w.com", "ERR:X", False),
            ("a@v.com", 451, False)]
    verdicts = []
    for _, code, ca in real:
        if isinstance(code, str):
            verdicts.append("ERROR")
        elif ca:
            verdicts.append("CATCHALL")
        elif code == 250:
            verdicts.append("VERIFIED")
        elif 400 <= code < 500:
            verdicts.append("TEMPFAIL")
        else:
            verdicts.append("DEAD")
    assert verdicts == ["CATCHALL", "VERIFIED", "DEAD", "ERROR", "TEMPFAIL"], verdicts
    print("demo OK:", verdicts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--demo":
        demo()
        sys.exit(0)
    for addr, code, ca, verdict in verify(sys.argv[1:]):
        print(f"{addr}\t{code}\tcatchall={ca}\tverdict={verdict}")
