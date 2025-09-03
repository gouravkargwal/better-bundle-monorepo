#!/usr/bin/env python3
"""
Database Reset Script for Gorse
Clears all Gorse-related tables from Render PostgreSQL
"""

import psycopg2
import sys
from datetime import datetime

# Database connection details
DB_CONFIG = {
    "host": "dpg-d2qpjbemcj7s73cegbv0-a.singapore-postgres.render.com",
    "database": "better_bundle",
    "user": "better_bundle_user",
    "password": "6eV4BA1YcoeFedPRJEJ0oDYlMOgFwTnF",
    "port": 5432,
}


def reset_gorse_database():
    """Reset all Gorse-related tables"""

    print("🗄️  Starting Gorse database reset...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # Connect to database
        print("🔌 Connecting to Render PostgreSQL...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Connected successfully!")

        # List of Gorse tables to drop
        gorse_tables = [
            "items",
            "users",
            "feedback",
            "item_neighbors",
            "user_neighbors",
            "cache",
            "meta",
        ]

        print("\n🗑️  Dropping Gorse tables...")
        for table in gorse_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"   ✅ Dropped table: {table}")
            except Exception as e:
                print(f"   ⚠️  Could not drop {table}: {e}")

        # Commit changes
        conn.commit()
        print("\n💾 Database changes committed!")

        # Verify tables are gone
        print("\n🔍 Verifying tables are removed...")
        cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('items', 'users', 'feedback')
        """
        )

        remaining_tables = cursor.fetchall()
        if remaining_tables:
            print(f"   ⚠️  Some tables still exist: {[t[0] for t in remaining_tables]}")
        else:
            print("   ✅ All Gorse tables successfully removed!")

        print("\n🎯 Database reset complete!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    finally:
        if "conn" in locals():
            cursor.close()
            conn.close()
            print("🔌 Database connection closed")


if __name__ == "__main__":
    reset_gorse_database()
