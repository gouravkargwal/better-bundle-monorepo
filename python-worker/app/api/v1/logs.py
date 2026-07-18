"""
Logging API endpoint for extension logging
Forwards logs from browser extensions to OpenObserve
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# OpenObserve configuration — from pydantic-settings with env fallback
OPENOBSERVE_ENDPOINT = os.getenv("OPENOBSERVE_ENDPOINT", settings.OPENOBSERVE_ENDPOINT)
OPENOBSERVE_ORG = os.getenv("OPENOBSERVE_ORG", settings.OPENOBSERVE_ORG)
OPENOBSERVE_API_KEY = os.getenv(
    "OPENOBSERVE_API_KEY", settings.OPENOBSERVE_API_KEY or ""
)


async def forward_to_openobserve(logs_data: Dict[str, Any]) -> bool:
    """
    Forward logs to OpenObserve JSON HTTP API
    """
    if not OPENOBSERVE_ENDPOINT:
        logger.info("OpenObserve endpoint not configured, skipping")
        return True

    try:
        logs = logs_data.get("logs", [])
        source = logs_data.get("source", "unknown")
        timestamp = logs_data.get("timestamp", datetime.utcnow().isoformat())

        # Build payload — OpenObserve JSON API expects an array of records
        payload: list[dict] = []
        if logs and len(logs) > 0:
            for entry in logs:
                record = {
                    **entry,
                    "_source": source,
                    "_timestamp": entry.get("time", timestamp),
                }
                payload.append(record)
        else:
            # Send a heartbeat so we still see extension activity
            payload.append(
                {
                    "source": source,
                    "timestamp": timestamp,
                    "msg": "heartbeat",
                    "service": "better-bundle-extension",
                    "level": 30,
                }
            )

        url = (
            f"{OPENOBSERVE_ENDPOINT}/api/{OPENOBSERVE_ORG}"
            f"/betterbundle-extensions/_json"
        )
        headers = {"Content-Type": "application/json"}
        if OPENOBSERVE_API_KEY:
            headers["Authorization"] = f"Bearer {OPENOBSERVE_API_KEY}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                logger.info(f"Forwarded {len(payload)} log entries to OpenObserve")
                return True
            else:
                logger.error(
                    f"OpenObserve returned status {response.status_code}: "
                    f"{response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Failed to forward logs to OpenObserve: {str(e)}")
        return False


@router.post("/logs")
async def receive_logs(request: Request):
    """
    Receive logs from extension and forward to OpenObserve
    """
    try:
        # Parse request body
        body = await request.json()

        # Validate request
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Log the request for debugging
        log_count = len(body.get("logs", []))
        source = body.get("source", "unknown")
        logger.info(f"Received logs from {source}: {log_count} entries")

        # Debug: Log the service name being used
        logs = body.get("logs", [])
        if logs and len(logs) > 0:
            first_log = logs[0]
            service_name = first_log.get("service", "unknown")
            env_name = first_log.get("env", "unknown")
            logger.info(f"Log service: {service_name}, env: {env_name}")

        # Forward to OpenObserve
        openobserve_success = await forward_to_openobserve(body)

        # Return success if OpenObserve received the logs
        if openobserve_success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Logs forwarded",
                    "openobserve": openobserve_success,
                },
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Failed to forward logs to OpenObserve",
                },
            )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"Error processing logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/logs/health")
async def logs_health():
    """
    Health check for logging service
    """
    # Probe OpenObserve reachability
    openobserve_reachable = False
    if OPENOBSERVE_ENDPOINT:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OPENOBSERVE_ENDPOINT}/health", timeout=5.0)
                openobserve_reachable = resp.status_code < 500
        except Exception:
            openobserve_reachable = False

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "openobserve_enabled": bool(OPENOBSERVE_ENDPOINT),
            "openobserve_endpoint": OPENOBSERVE_ENDPOINT,
            "openobserve_reachable": openobserve_reachable,
            "openobserve_org": OPENOBSERVE_ORG,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
