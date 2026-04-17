#!/usr/bin/env python3
"""
Cloud SQL connection smoke test.
Retains legacy filename for backwards compatibility with existing guide steps.
"""

from src.client import DataAPIClient


def main() -> None:
    print("🚀 Cloud SQL Connection Test")
    print("=" * 60)

    db = DataAPIClient()

    print("\n1) Testing basic query...")
    rows = db.query("SELECT 1 AS test_value, NOW()::text AS server_time")
    if not rows:
        raise SystemExit("❌ Failed to execute test query")

    print("✅ Successfully connected to PostgreSQL")
    print(f"   Test value: {rows[0]['test_value']}")
    print(f"   Server time: {rows[0]['server_time']}")

    print("\n2) Checking table visibility...")
    tables = db.query(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name
        """
    )
    print(f"✅ Found {len(tables)} tables in public schema")
    for row in tables:
        print(f"   • {row['table_name']}")

    print("\n3) Checking database version...")
    version_rows = db.query("SELECT version() AS version")
    print(f"✅ Database version: {version_rows[0]['version']}")

    print("\n🎉 Connection test complete")


if __name__ == "__main__":
    main()
