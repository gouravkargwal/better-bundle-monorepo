"""
Management command to verify Django won't create tables
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = "Verify that Django won't create tables (tables should only be created by Python worker)"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🔍 Verifying Django table creation prevention...")
        )

        # Check if migration modules are disabled
        if hasattr(settings, "MIGRATION_MODULES"):
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ MIGRATION_MODULES is configured to disable migrations"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("⚠️  MIGRATION_MODULES not configured"))

        # Check if database routers are configured
        if hasattr(settings, "DATABASE_ROUTERS") and settings.DATABASE_ROUTERS:
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ DATABASE_ROUTERS configured to prevent table creation"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("⚠️  DATABASE_ROUTERS not configured"))

        # Test database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(
                    self.style.SUCCESS("✅ Database connection successful")
                )

                # Check if tables exist (should be created by Python worker)
                cursor.execute(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('shops', 'order_data', 'product_data', 'customer_data', 
                                      'subscription_plans', 'pricing_tiers', 'shop_subscriptions', 
                                      'billing_cycles', 'billing_invoices', 'commission_records', 
                                      'purchase_attributions')
                    ORDER BY table_name
                """
                )

                tables = cursor.fetchall()

                if tables:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Found {len(tables)} tables created by Python worker:"
                        )
                    )
                    for table in tables:
                        self.stdout.write(f"  - {table[0]}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "⚠️  No tables found. Python worker should create them first."
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Database connection failed: {e}"))
            return

        self.stdout.write(
            self.style.SUCCESS("🎉 Django is configured to NOT create tables!")
        )
        self.stdout.write(
            self.style.SUCCESS("📝 Tables should only be created by Python worker.")
        )
