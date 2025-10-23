#!/usr/bin/env python
"""
Startup script for BetterBundle Admin Dashboard
Uses environment variables for port and host configuration
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    # Get port and host from environment
    port = os.environ.get("PORT", "8000")
    host = os.environ.get("HOST", "127.0.0.1")

    print(f"🚀 Starting BetterBundle Admin Dashboard...")
    print(f"📍 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🌐 URL: http://{host}:{port}")
    print(f"👤 Admin: http://{host}:{port}/admin")
    print("=" * 50)

    # Start the server
    execute_from_command_line(["manage.py", "runserver", f"{host}:{port}"])
