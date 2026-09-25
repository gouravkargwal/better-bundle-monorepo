"""INFO-log sampling on the OpenObserve export path.

The two properties that make sampling safe to run in production: errors are
never dropped, and a sampled trace keeps all of its lines rather than a random
fraction of them.
"""

import logging
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.logging.sampling import InfoSampler, rate_for
from app.shared.constants.app import ENVIRONMENT_PRODUCTION


def _record(level: int) -> logging.LogRecord:
    return logging.LogRecord("t", level, "f.py", 1, "m", None, None)


def test_warnings_and_errors_are_never_sampled():
    # The whole point: at 0% nothing INFO survives, but the records that
    # explain an incident still do.
    sampler = InfoSampler(0.0)
    for level in (logging.WARNING, logging.ERROR, logging.CRITICAL):
        assert sampler.filter(_record(level)) is True
    assert sampler.filter(_record(logging.INFO)) is False
    assert sampler.filter(_record(logging.DEBUG)) is False


def test_full_rate_keeps_everything():
    sampler = InfoSampler(1.0)
    assert all(sampler.filter(_record(l)) for l in
               (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR))


def test_rate_is_clamped_to_a_probability():
    assert InfoSampler(5.0).rate == 1.0
    assert InfoSampler(-1.0).rate == 0.0


def test_kept_records_carry_the_divisor():
    # Without it a volume panel reports a tenth of reality and reads as a
    # service that went quiet.
    sampler = InfoSampler(1.0)
    rec = _record(logging.INFO)
    sampler.filter(rec)
    assert not hasattr(rec, "log_sample_rate")  # unsampled, no divisor needed

    sampler = InfoSampler(0.5)
    kept = [r for r in (_record(logging.INFO) for _ in range(200))
            if sampler.filter(r)]
    assert kept, "0.5 should keep something"
    assert all(r.log_sample_rate == 0.5 for r in kept)


def test_every_log_in_one_trace_shares_one_verdict():
    # A sampled request must be logged in full. Per-record sampling would give
    # each trace a random fraction of its own lines, which is unreadable.
    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)
    sampler = InfoSampler(0.5)

    mixed = False
    for _ in range(40):
        with tracer.start_as_current_span("req"):
            verdicts = {sampler.filter(_record(logging.INFO)) for _ in range(25)}
            assert len(verdicts) == 1, "one trace produced both keeps and drops"
            mixed = mixed or verdicts == {True}
    assert mixed, "at 50% some traces should have been kept"


def test_records_outside_a_span_still_get_sampled():
    # Background loops log with no trace context; they must not all be kept.
    sampler = InfoSampler(0.1)
    kept = sum(sampler.filter(_record(logging.INFO)) for _ in range(3000))
    assert 100 < kept < 500, f"expected roughly 10% of 3000, got {kept}"


class _Settings:
    def __init__(self, env, rate=None):
        self.ENVIRONMENT = env
        self.logging = type("L", (), {"LOG_SAMPLE_RATE": rate})()


def test_production_defaults_to_ten_percent_and_dev_to_all():
    assert rate_for(_Settings(ENVIRONMENT_PRODUCTION)) == 0.1
    assert rate_for(_Settings("development")) == 1.0
    assert rate_for(_Settings("staging")) == 1.0


def test_explicit_override_wins_in_either_direction():
    # So a production incident can be widened without a deploy.
    assert rate_for(_Settings(ENVIRONMENT_PRODUCTION, 1.0)) == 1.0
    assert rate_for(_Settings("development", 0.25)) == 0.25
