"""
Management command to check system status
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from apps.core.utils import get_system_stats, get_health_status


class Command(BaseCommand):
    help = "Check system status and health"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🔍 Checking BetterBundle Admin System...")
        )

        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(
                    self.style.SUCCESS("✅ Database connection successful")
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Database connection failed: {e}"))
            return

        # Check system stats
        try:
            stats = get_system_stats()
            self.stdout.write(self.style.SUCCESS("📊 System Statistics:"))
            self.stdout.write(f"  - Total Shops: {stats['total_shops']}")
            self.stdout.write(f"  - Active Shops: {stats['active_shops']}")
            self.stdout.write(f"  - Total Revenue: ${stats['total_revenue']:.2f}")
            self.stdout.write(f"  - Pending Invoices: {stats['pending_invoices']}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Could not get system stats: {e}"))

        # Check health status
        try:
            health = get_health_status()
            self.stdout.write(self.style.SUCCESS("🏥 System Health:"))
            for service, status in health.items():
                if service != "last_check":
                    color = (
                        "success"
                        if status in ["healthy", "connected", "running", "active"]
                        else "warning"
                    )
                    self.stdout.write(
                        getattr(self.style, color.upper())(
                            f"  - {service.title()}: {status}"
                        )
                    )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"⚠️  Could not get health status: {e}")
            )

        self.stdout.write(self.style.SUCCESS("🎉 System check completed!"))
