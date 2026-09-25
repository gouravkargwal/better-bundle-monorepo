"""The contract that makes logs queryable in OpenObserve.

Regressing any of this reverts the symptom that motivated it: every log line
arriving as one free-text body with no field you can filter, group or alert on.
"""

import logging

from app.core.logging.formatters import (
    ConsoleFormatter,
    extract_extra,
    sanitize_extra,
)
from app.core.logging.logger import StructuredLogger


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _log_once(**kwargs):
    raw = logging.getLogger("test.structured")
    raw.handlers = []
    raw.propagate = False
    raw.setLevel(logging.DEBUG)
    cap = _Capture()
    raw.addHandler(cap)
    StructuredLogger(raw).info("order processed", **kwargs)
    return cap.records[0]


def test_kwargs_become_record_attributes_not_message_text():
    # This is the whole point: the OTel LoggingHandler copies non-reserved
    # LogRecord attributes into log-record attributes, which is what becomes a
    # queryable column. A value concatenated into the message is invisible.
    rec = _log_once(shop_id="shop_42", order_id=999)
    assert rec.getMessage() == "order processed"
    assert rec.shop_id == "shop_42"
    assert rec.order_id == 999


def test_reserved_names_are_renamed_rather_than_crashing_the_call_site():
    # logging raises KeyError if `extra` shadows a LogRecord attribute, which
    # would take down the code being logged about.
    rec = _log_once(module="billing", message="x", lineno=7)
    assert rec.ctx_module == "billing"
    assert rec.ctx_message == "x"
    assert rec.ctx_lineno == 7
    assert rec.module != "billing"  # the stdlib's own value survives


def test_none_values_are_dropped():
    assert sanitize_extra({"a": 1, "b": None}) == {"a": 1}


def test_console_still_shows_the_fields_to_a_human():
    rec = _log_once(shop_id="shop_42", note="two words")
    out = ConsoleFormatter().format(rec)
    assert "order processed" in out
    assert "shop_id=shop_42" in out
    assert 'note="two words"' in out  # spaces quoted, so the pair stays readable


def test_extract_extra_returns_only_caller_fields():
    rec = _log_once(shop_id="shop_42")
    assert extract_extra(rec) == {"shop_id": "shop_42"}


def test_exc_info_still_reaches_logging_and_is_not_turned_into_a_field():
    # ~30 call sites pass exc_info=True on error paths. If it were swept into
    # kwargs the traceback would be dropped and replaced by a ctx_exc_info
    # field, losing the stack exactly where the log line exists to carry it.
    raw = logging.getLogger("test.excinfo")
    raw.handlers = []
    raw.propagate = False
    raw.setLevel(logging.DEBUG)
    cap = _Capture()
    raw.addHandler(cap)
    log = StructuredLogger(raw)
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("sweep failed", exc_info=True, shop_id="shop_1")
    rec = cap.records[0]
    assert rec.exc_info is not None
    assert rec.exc_info[0] is ValueError
    assert rec.shop_id == "shop_1"
    assert not hasattr(rec, "ctx_exc_info")


def test_exception_helper_captures_the_stack():
    raw = logging.getLogger("test.exchelper")
    raw.handlers = []
    raw.propagate = False
    cap = _Capture()
    raw.addHandler(cap)
    try:
        raise KeyError("k")
    except KeyError:
        StructuredLogger(raw).exception("boom", shop_id="s")
    assert cap.records[0].exc_info[0] is KeyError


def test_extra_dict_is_merged_not_nested():
    # 25 call sites use logging's own `extra={...}`. Nested, it arrives in
    # OpenObserve as one unfilterable `extra` column.
    rec = _log_once(extra={"reconciler": "ingestion_backstop", "missing": 0})
    assert rec.reconciler == "ingestion_backstop"
    assert rec.missing == 0
    assert not hasattr(rec, "extra")


def test_extra_and_kwargs_can_be_mixed():
    rec = _log_once(shop_id="s1", extra={"reconciler": "rollover"})
    assert rec.shop_id == "s1"
    assert rec.reconciler == "rollover"


def test_non_dict_extra_is_kept_as_a_plain_field():
    rec = _log_once(extra="just a string")
    assert rec.extra == "just a string"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all structured-logging checks passed")
