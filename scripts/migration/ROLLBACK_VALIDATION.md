# Rollback Validation Checklist

## Rollback Principles

- Source database is never modified by migration scripts.
- Rollback is performed on target DB only.
- Safe rerun is guaranteed by idempotent inserts (`skip-if-exists`).

## If Validation Fails

1. Stop migration execution immediately.
2. Do not cut over traffic.
3. Inspect migration logs for failed rows.
4. Fix mapping or data handling issue.
5. Wipe target DB data if needed.
6. Re-run migration from phase 1.

## Post-Rollback Checks

- Confirm source row counts are unchanged.
- Confirm source checksums/samples match pre-run snapshot.
- Confirm target DB is either clean or consistent for rerun.
- Confirm no orphan records in target for already-run phases.
- Re-run 5-record spot-check for each completed phase before continuing.

