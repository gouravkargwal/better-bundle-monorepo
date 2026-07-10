"""
OpenObserve logging handler for Django admin.
Sends structured JSON logs to OpenObserve's Loki-compatible API.
"""

import json
import logging
import os
import requests
from requests.auth import HTTPBasicAuth


class OpenObserveLogHandler(logging.Handler):
    """Custom handler that sends log records to OpenObserve via Loki-compatible API."""

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080").rstrip("/")
        self.email = os.getenv("OPENOBSERVE_EMAIL", "")
        self.password = os.getenv("OPENOBSERVE_PASSWORD", "")
        self.org_id = os.getenv("OPENOBSERVE_ORG_ID", "default")
        self.endpoint = f"{self.base_url}/api/{self.org_id}/loki/api/v1/push"
        self.auth = HTTPBasicAuth(self.email, self.password) if self.email and self.password else None
        self._session = requests.Session()

    def emit(self, record: logging.LogRecord):
        try:
            # Format the message
            message = self.format(record)

            # Build Loki-compatible stream entry
            labels = {
                "service": "django-admin",
                "level": record.levelname.lower(),
                "logger": record.name,
                "module": record.module or "",
                "env": os.getenv("NODE_ENV", "production"),
            }

            timestamp_ns = int(record.created * 1_000_000_000)

            payload = {
                "streams": [
                    {
                        "stream": labels,
                        "values": [[str(timestamp_ns), message]],
                    }
                ]
            }

            self._session.post(
                self.endpoint,
                json=payload,
                auth=self.auth,
                timeout=5,
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            # Never let logging errors crash the app
            self.handleError(record)
