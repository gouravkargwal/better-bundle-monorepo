#!/usr/bin/env python3
"""
Real-time log monitoring script for BetterBundle Python Worker
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime


def watch_logs(log_file: str = "logs/consumer.log", lines: int = 50):
    """Watch log files in real-time"""

    log_path = Path(log_file)

    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        print("Available log files:")
        logs_dir = Path("logs")
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                print(f"  - {log_file}")
        return

    print(f"📊 Watching logs: {log_path}")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Get initial file size
    file_size = log_path.stat().st_size

    try:
        with open(log_path, "r") as f:
            # Read last N lines
            lines_content = f.readlines()
            for line in lines_content[-lines:]:
                print(line.rstrip())

            # Watch for new content
            while True:
                current_size = log_path.stat().st_size

                if current_size > file_size:
                    # New content added
                    with open(log_path, "r") as f:
                        f.seek(file_size)
                        new_content = f.read()
                        if new_content:
                            print(new_content.rstrip())

                    file_size = current_size

                time.sleep(0.1)  # Check every 100ms

    except KeyboardInterrupt:
        print("\n👋 Log watching stopped")
    except Exception as e:
        print(f"❌ Error watching logs: {e}")


def show_log_summary():
    """Show a summary of recent log activity"""
    logs_dir = Path("logs")

    if not logs_dir.exists():
        print("❌ No logs directory found")
        return

    print("📊 Log Summary")
    print("=" * 50)

    for log_file in logs_dir.glob("*.log"):
        if log_file.exists():
            stat = log_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(stat.st_mtime)

            print(f"📄 {log_file.name}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"   Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")

            # Count lines
            try:
                with open(log_file, "r") as f:
                    line_count = sum(1 for _ in f)
                print(f"   Lines: {line_count:,}")
            except:
                print("   Lines: Error reading")

            print()


def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "summary":
            show_log_summary()
        elif command == "watch":
            log_file = sys.argv[2] if len(sys.argv) > 2 else "logs/consumer.log"
            lines = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            watch_logs(log_file, lines)
        else:
            print("Usage:")
            print("  python watch_logs.py summary          - Show log summary")
            print("  python watch_logs.py watch            - Watch consumer logs")
            print("  python watch_logs.py watch <file>     - Watch specific log file")
            print(
                "  python watch_logs.py watch <file> <N> - Watch with N initial lines"
            )
    else:
        # Default: watch consumer logs
        watch_logs()


if __name__ == "__main__":
    main()
