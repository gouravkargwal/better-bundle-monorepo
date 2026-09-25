"""Sampling for INFO-level logs on the OpenObserve export path.

Volume control, and only that: nothing here changes what the console shows, so
local debugging is unaffected and a production container's stdout still has the
full picture for `docker logs`.

Two rules the implementation exists to enforce:

1. NOTHING AT WARNING OR ABOVE IS EVER DROPPED. Sampling errors defeats the
   reason the logs are shipped at all — the one record that explains an
   incident is exactly the one a 10% sampler would throw away 9 times out of
   10. Only DEBUG and INFO are eligible.

2. THE DECISION IS PER-TRACE, NOT PER-RECORD. Hashing the trace id means every
   log line belonging to one request shares a single keep/drop verdict, so a
   sampled request is *fully* logged. Sampling each record independently would
   instead give every request a random 10% of its own lines — the worst
   outcome, because clicking into a trace would show a fragment of the story
   with no indication anything was missing.
"""

import logging
import random

from opentelemetry import trace

# 2**32; trace ids are 128-bit, and the low 32 bits are uniformly distributed.
_HASH_SPACE = 1 << 32


class InfoSampler(logging.Filter):
    """Drop a fraction of DEBUG/INFO records. Warnings and errors always pass."""

    def __init__(self, rate: float):
        super().__init__()
        self.rate = min(max(rate, 0.0), 1.0)

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        if self.rate >= 1.0:
            return True
        if self.rate <= 0.0:
            return False

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            keep = (span_context.trace_id % _HASH_SPACE) < self.rate * _HASH_SPACE
        else:
            # Background loops and startup log outside any span; there is no
            # trace to be consistent with, so fall back to per-record.
            keep = random.random() < self.rate

        if keep:
            # Counting sampled logs requires knowing the divisor. Without this,
            # a "log volume by service" panel silently reports a tenth of
            # reality and reads as a service that went quiet.
            record.log_sample_rate = self.rate
        return keep


def rate_for(settings) -> float:
    """Sampling rate for this environment.

    Defaults to 10% in production and 100% everywhere else — dev volume is
    small and complete logs are worth more there than the storage they cost.
    `LOG_SAMPLE_RATE` overrides both, so a production incident can be widened
    to 1.0 without a code change.
    """
    from app.shared.constants.app import ENVIRONMENT_PRODUCTION

    configured = getattr(settings.logging, "LOG_SAMPLE_RATE", None)
    if configured is not None:
        return min(max(float(configured), 0.0), 1.0)
    return 0.1 if settings.ENVIRONMENT == ENVIRONMENT_PRODUCTION else 1.0
