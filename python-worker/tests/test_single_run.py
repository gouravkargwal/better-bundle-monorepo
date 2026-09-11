"""Lock-key derivation for the background-job mutex.

No DB here on purpose — this suite has no database fixture. The behaviour that
needs Postgres (mutual exclusion, release on exception, no leaked locks) is
exercised against the real thing; this covers the one piece that is pure, and
the one that would fail silently and catastrophically if it regressed.
"""

from app.core.single_run import lock_key


def test_key_is_stable_across_calls():
    assert lock_key("ingestion_backstop") == lock_key("ingestion_backstop")


def test_key_differs_by_job_name():
    names = ["enrichment_sweeper", "attribution_reconciler",
             "fx_refresher", "ingestion_backstop"]
    assert len({lock_key(n) for n in names}) == len(names)


def test_key_fits_a_signed_bigint():
    """pg_try_advisory_lock takes bigint; an unsigned value >= 2^63 is rejected."""
    for n in ["enrichment_sweeper", "attribution_reconciler",
              "fx_refresher", "ingestion_backstop", "", "x" * 500]:
        assert -(2**63) <= lock_key(n) < 2**63


def test_key_is_not_process_salted():
    """The failure this guards against is silent and total.

    Python's built-in hash() is salted per process (PYTHONHASHSEED), so if this
    were ever swapped for hash(), every worker would derive a different key for
    the same job, every one of them would acquire "its own" lock, and all of
    them would run — which is exactly the duplication the lock exists to stop,
    with no error anywhere.

    Hardcoded expectation, so it fails if the derivation changes at all.
    """
    assert lock_key("ingestion_backstop") == -7378033758311228930
