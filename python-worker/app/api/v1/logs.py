"""
Logging API endpoint for client-side logs
Forwards logs from browser to Loki
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# OpenObserve configuration (Loki-compatible API)
OPENOBSERVE_URL = os.getenv("OPENOBSERVE_URL", "http://localhost:5080")
OPENOBSERVE_ORG_ID = os.getenv("OPENOBSERVE_ORG_ID", "default")
OPENOBSERVE_EMAIL = os.getenv("OPENOBSERVE_EMAIL", "")
OPENOBSERVE_PASSWORD = os.getenv("OPENOBSERVE_PASSWORD", "")
OPENOBSERVE_ENABLED = os.getenv("OPENOBSERVE_ENABLED", "true").lower() == "true"


async def forward_to_openobserve(logs_data: Dict[str, Any]) -> bool:
    """
    Forward logs to OpenObserve via Loki-compatible API
    """
    if not OPENOBSERVE_ENABLED:
        logger.info("OpenObserve logging disabled, skipping log forward")
        return True

    try:
        # Extract logs from the payload
        logs = logs_data.get("logs", {})
        source = logs_data.get("source", "unknown")
        timestamp = logs_data.get("timestamp", datetime.utcnow().isoformat())

        # Extract service and env from the logs if available
        service_name = "betterbundle-extension"  # Default
        env_name = "development"  # Default

        if logs and len(logs) > 0:
            # Try to extract service and env from the first log entry
            first_log = logs[0]
            service_name = first_log.get("service", "betterbundle-extension")
            env_name = first_log.get("env", "development")

        # Transform to Loki-compatible format
        payload = {
            "streams": [
                {
                    "stream": {
                        "service": service_name,
                        "source": source,
                        "env": env_name,
                    },
                    "values": [],
                }
            ]
        }

        # Process each log entry
        if logs and len(logs) > 0:
            for log_entry in logs:
                # Convert log entry to Loki format
                timestamp_ns = str(
                    int(
                        datetime.fromisoformat(
                            log_entry.get("time", timestamp).replace("Z", "+00:00")
                        ).timestamp()
                        * 1000000000
                    )
                )
                log_message = json.dumps(log_entry)
                payload["streams"][0]["values"].append([timestamp_ns, log_message])

        # Parse base URL
        base_url = OPENOBSERVE_URL.rstrip("/")
        endpoint = f"{base_url}/api/{OPENOBSERVE_ORG_ID}/loki/api/v1/push"

        # Build auth header if credentials configured
        headers = {"Content-Type": "application/json"}
        auth = None
        if OPENOBSERVE_EMAIL and OPENOBSERVE_PASSWORD:
            import base64

            auth_str = f"{OPENOBSERVE_EMAIL}:{OPENOBSERVE_PASSWORD}"
            headers["Authorization"] = (
                f"Basic {base64.b64encode(auth_str.encode()).decode()}"
            )

        # Send to OpenObserve
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
            )

            if response.status_code == 204:
                logger.info(
                    f"Successfully forwarded {len(payload['streams'][0]['values'])} log entries to OpenObserve"
                )
                return True
            else:
                logger.error(
                    f"OpenObserve returned status {response.status_code}: {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Failed to forward logs to OpenObserve: {str(e)}")
        return False


@router.post("/logs")
async def receive_logs(request: Request):
    """
    Receive logs from extensions and forward to OpenObserve
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
        success = await forward_to_openobserve(body)

        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "Logs forwarded to OpenObserve"},
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
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "openobserve_enabled": OPENOBSERVE_ENABLED,
            "openobserve_url": OPENOBSERVE_URL,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
