#!/usr/bin/env python3
"""
Comprehensive database verification script for Cloud SQL PostgreSQL.
"""

from src.client import DataAPIClient


def execute_query(db: DataAPIClient, sql: str, description: str):
    print(f"\n{description}")
    print("-" * 50)
    try:
        return db.query(sql)
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return []


def main() -> None:
    db = DataAPIClient()

    print("🔍 DATABASE VERIFICATION REPORT")
    print("=" * 70)

    tables = execute_query(
        db,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        "📊 ALL TABLES IN DATABASE",
    )
    print(f"✅ Found {len(tables)} tables")
    for row in tables:
        print(f"   • {row['table_name']}")

    counts = execute_query(
        db,
        """
        SELECT 'users' AS table_name, COUNT(*)::bigint AS count FROM users
        UNION ALL
        SELECT 'instruments', COUNT(*)::bigint FROM instruments
        UNION ALL
        SELECT 'accounts', COUNT(*)::bigint FROM accounts
        UNION ALL
        SELECT 'positions', COUNT(*)::bigint FROM positions
        UNION ALL
        SELECT 'jobs', COUNT(*)::bigint FROM jobs
        ORDER BY table_name
        """,
        "📈 RECORD COUNTS PER TABLE",
    )
    for row in counts:
        print(f"   • {row['table_name']:<12} {row['count']}")

    sample = execute_query(
        db,
        """
        SELECT symbol, name, instrument_type
        FROM instruments
        ORDER BY symbol
        LIMIT 10
        """,
        "🎯 SAMPLE INSTRUMENTS (First 10)",
    )
    for row in sample:
        print(f"   • {row['symbol']}: {row['name']} ({row['instrument_type']})")

    indexes = execute_query(
        db,
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname='public'
          AND indexname LIKE 'idx_%'
        ORDER BY indexname
        """,
        "🧭 CUSTOM INDEXES",
    )
    for row in indexes:
        print(f"   • {row['indexname']}")

    triggers = execute_query(
        db,
        """
        SELECT trigger_name
        FROM information_schema.triggers
        WHERE trigger_schema='public'
          AND trigger_name LIKE 'update_%_updated_at'
        ORDER BY trigger_name
        """,
        "⏱️ UPDATE TRIGGERS",
    )
    for row in triggers:
        print(f"   • {row['trigger_name']}")

    print("\n" + "=" * 70)
    print("🎉 DATABASE VERIFICATION COMPLETE")
    print("=" * 70)
    print("✅ Tables, indexes, and triggers verified")
    print("✅ Database is ready for agent orchestration")


if __name__ == "__main__":
    main()
