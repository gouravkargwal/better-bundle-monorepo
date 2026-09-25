import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app.core.config.settings import settings
from app.shared.helpers import now_utc

router = APIRouter(tags=["Logs"])

# Ceiling on how many caller-supplied keys one browser record may turn into
# stream columns. ponytail: flat cap, make it a per-extension allowlist if an
# extension ever legitimately needs more.
MAX_EXTENSION_FIELDS = 20


async def _forward_to_openobserve(
    logs: List[Dict[str, Any]],
    source: str,
    batch_timestamp: str,
) -> None:
    """Forward extension browser logs to OpenObserve JSON ingestion API.

    Field names deliberately match what the OTLP exporters write into the
    `default` stream — `body`, `severity`, `service_name` — rather than the
    `message`/`level`/`source` this used to emit. Same concepts under three
    different column names meant no single query, dashboard panel or alert
    could span the browser extensions and the services they talk to; you had
    to know which vocabulary a given record spoke before you could filter it.

    The stream stays separate from `default` on purpose. These records are
    unauthenticated browser input, and every distinct key in one becomes a
    column in the stream's schema — pointed at `default` a buggy or hostile
    extension could blow out the schema that every other service shares.
    Separate stream, identical vocabulary: a UNION across the two works, and
    the blast radius of bad input stops at this stream.
    """
    base = settings.OPENOBSERVE_ENDPOINT.rstrip("/")
    url = f"{base}/api/{settings.OPENOBSERVE_ORG}/extension_logs/_json"

    records = []
    for entry in logs:
        level = "info"
        if isinstance(entry, dict):
            level = entry.get("level", entry.get("logLevel", "info"))
            message = entry.get("message", entry.get("msg", str(entry)))
            extra = {
                k: v
                for k, v in entry.items()
                if k not in ("level", "logLevel", "message", "msg")
            }
        else:
            message = str(entry)
            extra = {}

        # pino-browser sends level as a number (10=trace … 50=error)
        if isinstance(level, int):
            level = {10: "trace", 20: "debug", 30: "info", 40: "warn", 50: "error"}.get(
                level, "info"
            )

        ts_raw = entry.get("timestamp", entry.get("time")) if isinstance(entry, dict) else None
        if ts_raw:
            try:
                if isinstance(ts_raw, (int, float)):
                    ts = float(ts_raw)
                else:
                    from datetime import datetime, timezone

                    dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    ts = dt.timestamp()
            except (ValueError, TypeError):
                ts = time.time()
        else:
            ts = time.time()

        record = {
            "body": message,
            "severity": str(level).upper(),
            "service_name": source,
            "timestamp": ts,
            # OTLP records carry this from the Resource; set it here so an
            # environment filter covers the extensions too.
            "deployment_environment_name": settings.ENVIRONMENT,
        }

        # Caller fields are promoted to top-level columns, matching how the
        # Python and Node loggers emit theirs — `attributes` as a nested blob
        # was queryable only by a prefixed, lowercased key.
        #
        # Capped because this is untrusted input: an extension looping over a
        # cart could otherwise mint a new column per product id and exhaust
        # the stream's schema. Reserved names are never overwritten.
        if extra:
            for key, value in list(extra.items())[:MAX_EXTENSION_FIELDS]:
                safe = str(key)[:64]
                if safe not in record:
                    record[safe] = value

        records.append(record)

    if not records:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json=records,
                headers={"Authorization": f"Basic {settings.OPENOBSERVE_API_KEY}"},
            )
            if resp.status_code >= 400:
                # Don't let a logging failure bubble up to the caller
                import logging

                logging.getLogger(__name__).warning(
                    "OpenObserve log ingestion returned %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to forward extension logs to OpenObserve: %s", exc
        )


@router.post("/logs")
async def receive_extension_logs(request: Request, background_tasks: BackgroundTasks):
    """Receive batched browser logs from client extensions and forward them
    to OpenObserve.

    Extensions POST a payload like::

        {
            "logs": [...],
            "source": "phoenix-extension",
            "timestamp": "2026-09-16T..."
        }

    The forwarding happens in a background task so the extension gets a fast
    200 and we don't block on OpenObserve latency.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    logs = body.get("logs") or []
    source = body.get("source", "unknown")
    batch_timestamp = body.get("timestamp", now_utc().isoformat())

    if logs:
        background_tasks.add_task(_forward_to_openobserve, logs, source, batch_timestamp)

    return JSONResponse(status_code=200, content={"status": "ok"})
