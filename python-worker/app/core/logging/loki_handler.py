"""
Grafana Loki logging handler for BetterBundle Python Worker
Sends structured logs directly to Loki
"""

import json
import logging
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth


class LokiHandler(logging.Handler):
    """Custom logging handler that sends logs to Grafana Loki"""

    def __init__(
        self,
        url: str,
        username: str = "",
        password: str = "",
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ):
        super().__init__()
        self.url = url
        self.username = username
        self.password = password
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Batch storage
        self._batch: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        # Start background flush thread
        self._flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._flush_thread.start()

        # Set up authentication
        self.auth = None
        if username and password:
            self.auth = HTTPBasicAuth(username, password)

    def emit(self, record: logging.LogRecord):
        """Emit a log record to Loki"""
        try:
            # Convert log record to Loki format
            loki_entry = self._format_log_record(record)

            with self._lock:
                self._batch.append(loki_entry)

                # Flush if batch is full
                if len(self._batch) >= self.batch_size:
                    self._flush_batch()
        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)

    def _format_log_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Format a log record for Loki"""
        # Get timestamp in nanoseconds
        timestamp_ns = int(record.created * 1_000_000_000)

        # Create log message
        message = self.format(record)

        # Extract labels from record
        labels = {
            "service": "python-worker",
            "level": record.levelname.lower(),
            "logger": record.name,
        }

        # Add any extra fields from the record
        if hasattr(record, "extra_fields"):
            for key, value in record.extra_fields.items():
                if isinstance(value, (str, int, float, bool)):
                    labels[key] = str(value)

        # Add module and function info
        if record.module:
            labels["module"] = record.module
        if record.funcName:
            labels["function"] = record.funcName

        # Add thread info
        if record.thread:
            labels["thread"] = str(record.thread)
        if record.threadName:
            labels["thread_name"] = record.threadName

        # Add process info
        if record.process:
            labels["process"] = str(record.process)
        if record.processName:
            labels["process_name"] = record.processName

        return {"stream": labels, "values": [[str(timestamp_ns), message]]}

    def _flush_worker(self):
        """Background worker to flush logs periodically"""
        while True:
            time.sleep(self.flush_interval)
            with self._lock:
                if self._batch:
                    self._flush_batch()

    def _flush_batch(self):
        """Flush the current batch to Loki"""
        if not self._batch:
            return

        try:
            # Group logs by stream (labels)
            streams = {}
            for entry in self._batch:
                stream_key = json.dumps(entry["stream"], sort_keys=True)
                if stream_key not in streams:
                    streams[stream_key] = {"stream": entry["stream"], "values": []}
                streams[stream_key]["values"].extend(entry["values"])

            # Create Loki payload
            payload = {"streams": list(streams.values())}

            # Send to Loki
            headers = {
                "Content-Type": "application/json",
                "X-Scope-OrgID": "python-worker",  # Optional: for multi-tenant setups
            }

            response = requests.post(
                self.url, json=payload, headers=headers, auth=self.auth, timeout=10
            )

            if response.status_code == 204:
                # Success - clear the batch
                self._batch.clear()
            else:
                print(
                    f"Warning: Loki returned status {response.status_code}: {response.text}"
                )

        except Exception as e:
            print(f"Warning: Failed to send logs to Loki: {e}")
        finally:
            # Clear batch even on error to prevent memory buildup
            self._batch.clear()

    def flush(self):
        """Flush any pending logs"""
        with self._lock:
            if self._batch:
                self._flush_batch()

    def close(self):
        """Close the handler and flush any remaining logs"""
        self.flush()
        super().close()
