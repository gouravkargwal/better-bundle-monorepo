"""
Management command to check database connection and existing tables
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = "Check database connection and existing tables (Django NEVER creates tables - only Python worker does)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Checking database connection..."))
        self.stdout.write(
            self.style.WARNING(
                "⚠️  IMPORTANT: Django NEVER creates tables - only Python worker does!"
            )
        )

        try:
            with connection.cursor() as cursor:
                # Test database connection
                cursor.execute("SELECT 1")
                self.stdout.write(
                    self.style.SUCCESS("✅ Database connection successful")
                )

                # Check if tables exist (created by Python worker)
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('shops', 'order_data', 'product_data', 'customer_data', 
                                      'subscription_plans', 'shop_subscriptions', 
                                      'billing_cycles', 'billing_invoices', 
                                      'purchase_attributions')
                    ORDER BY table_name
                """)

                tables = cursor.fetchall()

                if tables:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Found {len(tables)} existing tables:")
                    )
                    for table in tables:
                        self.stdout.write(f"  - {table[0]}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "⚠️  No existing tables found. Make sure Python worker has created them."
                        )
                    )

                # Check Django auth tables
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'auth_%'
                    ORDER BY table_name
                """)

                auth_tables = cursor.fetchall()

                if auth_tables:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Found {len(auth_tables)} Django auth tables"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "⚠️  No Django auth tables found. You may need to run migrations for Django auth."
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Database connection failed: {e}"))
            return

        self.stdout.write(self.style.SUCCESS("🎉 Database check completed!"))
