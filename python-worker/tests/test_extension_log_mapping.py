"""Extension browser logs must speak the same vocabulary as OTLP records.

Before this, they arrived as `message`/`level`/`source` in their own stream
while every other service wrote `body`/`severity`/`service_name`. Same three
concepts, three column names, so no single query, panel or alert could cover
a storefront extension and the worker it calls.
"""

import httpx
import pytest

from app.routes import logs_routes


def _capture(monkeypatch):
    sent = {}

    class _Resp:
        status_code = 200
        text = ""

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            sent["url"] = url
            sent["records"] = json
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return sent


@pytest.mark.asyncio
async def test_fields_match_the_otlp_vocabulary(monkeypatch):
    sent = _capture(monkeypatch)
    await logs_routes._forward_to_openobserve(
        [{"level": 50, "message": "checkout blew up", "cartToken": "abc"}],
        "phoenix-extension",
        "2026-09-25T00:00:00Z",
    )
    rec = sent["records"][0]
    assert rec["body"] == "checkout blew up"
    assert rec["severity"] == "ERROR"
    assert rec["service_name"] == "phoenix-extension"
    assert "deployment_environment_name" in rec
    # the old names must be gone, or both vocabularies exist at once
    assert "message" not in rec and "level" not in rec and "source" not in rec


@pytest.mark.asyncio
async def test_caller_fields_are_promoted_to_top_level_columns(monkeypatch):
    sent = _capture(monkeypatch)
    await logs_routes._forward_to_openobserve(
        [{"level": 30, "message": "m", "cartToken": "abc", "surface": "cart"}],
        "ext",
        "t",
    )
    rec = sent["records"][0]
    assert rec["cartToken"] == "abc"
    assert rec["surface"] == "cart"
    assert "attributes" not in rec  # nested blob was queryable only by prefix


@pytest.mark.asyncio
async def test_field_count_is_capped_against_untrusted_input(monkeypatch):
    # An extension looping over a cart could otherwise mint a column per
    # product id and exhaust the stream schema.
    sent = _capture(monkeypatch)
    noisy = {f"k{i}": i for i in range(200)}
    noisy.update({"level": 30, "message": "m"})
    await logs_routes._forward_to_openobserve([noisy], "ext", "t")
    rec = sent["records"][0]
    reserved = {"body", "severity", "service_name", "timestamp",
                "deployment_environment_name"}
    assert len(set(rec) - reserved) <= logs_routes.MAX_EXTENSION_FIELDS


@pytest.mark.asyncio
async def test_reserved_columns_cannot_be_overwritten_by_a_browser(monkeypatch):
    sent = _capture(monkeypatch)
    await logs_routes._forward_to_openobserve(
        [{"level": 50, "message": "real", "body": "spoofed",
          "service_name": "python-worker"}],
        "ext", "t",
    )
    rec = sent["records"][0]
    assert rec["body"] == "real"
    assert rec["service_name"] == "ext"  # cannot impersonate another service


@pytest.mark.asyncio
async def test_pino_numeric_levels_map_to_otel_severity_names(monkeypatch):
    for numeric, expected in ((10, "TRACE"), (20, "DEBUG"), (30, "INFO"),
                              (40, "WARN"), (50, "ERROR")):
        sent = _capture(monkeypatch)
        await logs_routes._forward_to_openobserve(
            [{"level": numeric, "message": "m"}], "ext", "t")
        assert sent["records"][0]["severity"] == expected
