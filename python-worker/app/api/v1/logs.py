"""
Logging API endpoint for Phoenix extension
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

# Loki configuration
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
LOKI_ENABLED = os.getenv("LOKI_ENABLED", "true").lower() == "true"


async def forward_to_loki(logs_data: Dict[str, Any]) -> bool:
    """
    Forward logs to Loki
    """
    if not LOKI_ENABLED:
        logger.info("Loki logging disabled, skipping log forward")
        return True

    try:
        # Extract logs from the payload
        logs = logs_data.get("logs", {})
        source = logs_data.get("source", "unknown")
        timestamp = logs_data.get("timestamp", datetime.utcnow().isoformat())

        # Extract service and env from the logs if available
        service_name = "phoenix-extension"  # Default
        env_name = "development"  # Default

        if logs and len(logs) > 0:
            # Try to extract service and env from the first log entry
            first_log = logs[0]
            service_name = first_log.get("service", "phoenix-extension")
            env_name = first_log.get("env", "development")

        # Transform to Loki format
        loki_payload = {
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
                loki_payload["streams"][0]["values"].append([timestamp_ns, log_message])

        # Send to Loki
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{LOKI_URL}/loki/api/v1/push",
                json=loki_payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 204:
                logger.info(
                    f"Successfully forwarded {len(loki_payload['streams'][0]['values'])} log entries to Loki"
                )
                return True
            else:
                logger.error(
                    f"Loki returned status {response.status_code}: {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Failed to forward logs to Loki: {str(e)}")
        return False


@router.post("/logs")
async def receive_logs(request: Request):
    """
    Receive logs from Phoenix extension and forward to Loki
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

        # Forward to Loki
        success = await forward_to_loki(body)

        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "Logs forwarded to Loki"},
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to forward logs to Loki"},
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
            "loki_enabled": LOKI_ENABLED,
            "loki_url": LOKI_URL,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
