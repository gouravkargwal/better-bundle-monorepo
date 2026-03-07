#!/usr/bin/env python
"""
Startup script for BetterBundle Admin Dashboard
Uses environment variables for port and host configuration
"""

import os
import sys
from pathlib import Path
import django
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    # Load .env.dev if it exists
    env_file = Path(__file__).parent / ".env.dev"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)

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
