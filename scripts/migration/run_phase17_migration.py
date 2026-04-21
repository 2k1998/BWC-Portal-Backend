from sqlalchemy import text

from scripts.migration.common import build_engines
from scripts.migration.migrate_cars import migrate_cars
from scripts.migration.migrate_companies import migrate_companies
from scripts.migration.migrate_payments import migrate_payments
from scripts.migration.migrate_tasks import migrate_tasks
from scripts.migration.migrate_teams import migrate_teams
from scripts.migration.migrate_users import migrate_users
from scripts.migration.validate_phase import run_phase_validation


SOURCE_FINGERPRINT_TABLES = [
    "users",
    "companies",
    "groups",
    "group_members",
    "tasks",
    "task_histories",
    "payments",
    "cars",
    "car_incomes",
    "car_expenses",
]


def print_source_fingerprint() -> None:
    source_engine, _ = build_engines()
    with source_engine.connect() as src:
        print("Source fingerprint (live Render schema):")
        for table_name in SOURCE_FINGERPRINT_TABLES:
            row = src.execute(text(f"SELECT COUNT(*) AS c FROM {table_name}")).first()
            count = int(row.c) if row else 0
            print(f"- {table_name}: {count}")


def main() -> None:
    print_source_fingerprint()

    steps = [
        ("users", migrate_users),
        ("companies", migrate_companies),
        ("teams", migrate_teams),
        ("tasks", migrate_tasks),
        ("payments", migrate_payments),
        ("cars", migrate_cars),
    ]

    for phase_name, func in steps:
        print(f"\n=== Migrating {phase_name} ===")
        func()
        ok = run_phase_validation(phase_name)
        if not ok:
            raise RuntimeError(f"Validation failed for phase: {phase_name}")

    print("\nPhase 17 migration completed successfully.")


if __name__ == "__main__":
    main()

