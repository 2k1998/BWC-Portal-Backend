# Phase 17 Migration Scripts

This folder contains data migration scripts for PRD Phase 17.

## Source of Truth

- Source DB: Render live Postgres (`bwc.db`)
- Expected scope tables:
  - `users`
  - `companies`
  - `groups`
  - `group_members`
  - `tasks`
  - `task_histories`
  - `payments`
  - `cars`
  - `car_incomes`
  - `car_expenses`

## Required Environment Variables

- `SOURCE_DB_URL`: live source connection string (read-only usage)
- `TARGET_DB_URL`: new BWT Task Manager connection string

## Run All Phases

```bash
python -m scripts.migration.run_phase17_migration
```

## Individual Scripts

- `migrate_users.py`
- `migrate_companies.py`
- `migrate_teams.py`
- `migrate_tasks.py`
- `migrate_payments.py`
- `migrate_cars.py`

Each script:
- checks existing target rows by `id`
- inserts only missing rows
- reports `inserted/skipped/errors`

## Validation

Validation runs after each phase from `validate_phase.py`:
- count comparison (source vs target)
- orphan FK checks for key relations
- 5-row random spot-check using deterministic ID mapping

