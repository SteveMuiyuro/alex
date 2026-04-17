#!/usr/bin/env python3
"""
Migration runner for Cloud SQL PostgreSQL.
Executes SQL migration files using the shared DataAPIClient compatibility wrapper.
"""

from pathlib import Path

from src.client import DataAPIClient


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL script into statements while preserving function bodies."""
    statements: list[str] = []
    current: list[str] = []
    in_dollar_block = False

    for line in sql.splitlines():
        stripped = line.strip()

        if "$$" in line:
            in_dollar_block = not in_dollar_block

        current.append(line)

        if stripped.endswith(";") and not in_dollar_block:
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []

    tail = "\n".join(current).strip()
    if tail:
        statements.append(tail)

    return [s for s in statements if s and not s.startswith("--")]


def run_migration_file(db: DataAPIClient, migration_file: Path) -> tuple[int, int]:
    print(f"\nStarting migration: {migration_file.name}")
    sql = migration_file.read_text(encoding="utf-8")
    statements = split_sql_statements(sql)

    success_count = 0
    error_count = 0

    for index, stmt in enumerate(statements, start=1):
        label = stmt.splitlines()[0][:80]
        try:
            db.execute(stmt)
            print(f"  ✅ [{index}/{len(statements)}] {label}")
            success_count += 1
        except Exception as exc:  # keep verbose for student debugging
            print(f"  ❌ [{index}/{len(statements)}] {label}")
            print(f"     {exc}")
            error_count += 1

    return success_count, error_count


def main() -> None:
    print("🚀 Running database migrations (Cloud SQL)")
    print("=" * 50)

    db = DataAPIClient()
    migration_dir = Path("migrations")
    migration_files = sorted(migration_dir.glob("*.sql"))

    if not migration_files:
        raise FileNotFoundError("No migration files found in ./migrations")

    total_success = 0
    total_errors = 0

    for migration_file in migration_files:
        success, errors = run_migration_file(db, migration_file)
        total_success += success
        total_errors += errors

    print("\n" + "=" * 50)
    print(f"Migration summary: {total_success} successful, {total_errors} failed")

    if total_errors == 0:
        print("✅ All migrations completed successfully")
        print("Next steps:")
        print("1. uv run seed_data.py")
        print("2. uv run verify_database.py")
    else:
        raise SystemExit("⚠️ Some migration statements failed")


if __name__ == "__main__":
    main()
