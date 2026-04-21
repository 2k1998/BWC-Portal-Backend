from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, print_summary
from scripts.migration.mapping import map_priority, map_task_status, map_urgency_label


def _resolve_assignment(row):
    assigned_user_id = None
    assigned_team_id = None

    if row.group_id:
        assigned_team_id = map_uuid("teams", row.group_id)
    else:
        assigned_user_id = map_uuid("users", row.owner_id)

    return assigned_user_id, assigned_team_id


def migrate_tasks() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        tasks = src.execute(
            text(
                """
                SELECT
                    id, title, description, start_date, deadline,
                    urgency, important, status, owner_id, group_id, company_id, created_at, updated_at
                FROM tasks
                ORDER BY id
                """
            )
        ).fetchall()

        for row in tasks:
            task_id = map_uuid("tasks", row.id)
            exists = tgt.execute(
                text("SELECT id FROM tasks WHERE id = :id"),
                {"id": task_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                assigned_user_id, assigned_team_id = _resolve_assignment(row)
                company_id = map_uuid("companies", row.company_id) if row.company_id else None
                owner_user_id = map_uuid("users", row.owner_id)
                if not company_id:
                    raise ValueError(f"task {row.id} has NULL company_id")

                tgt.execute(text("SAVEPOINT sp_task"))
                tgt.execute(
                    text(
                        """
                        INSERT INTO tasks (
                            id, title, description, company_id, department, priority, urgency_label,
                            start_date, deadline, owner_user_id, assigned_user_id, assigned_team_id,
                            status, created_at, updated_at
                        )
                        VALUES (
                            :id, :title, :description, :company_id, :department, :priority, :urgency_label,
                            :start_date, :deadline, :owner_user_id, :assigned_user_id, :assigned_team_id,
                            :status, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": task_id,
                        "title": row.title,
                        "description": row.description,
                        "company_id": company_id,
                        "department": "General",
                        "priority": map_priority(row.urgency, row.important),
                        "urgency_label": map_urgency_label(row.urgency, row.important),
                        "start_date": row.start_date.date() if row.start_date else row.created_at.date(),
                        "deadline": row.deadline.date() if row.deadline else row.created_at.date(),
                        "owner_user_id": owner_user_id,
                        "assigned_user_id": assigned_user_id,
                        "assigned_team_id": assigned_team_id,
                        "status": map_task_status(row.status),
                        "created_at": row.created_at,
                        "updated_at": row.updated_at or row.created_at,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.execute(text("ROLLBACK TO SAVEPOINT sp_task"))
                counters.errors += 1
                print(f"Error migrating task {row.id}: {exc}")

        histories = src.execute(
            text(
                """
                SELECT id, task_id, changed_by_id, timestamp, status_from, status_to, comment
                FROM task_histories
                ORDER BY id
                """
            )
        ).fetchall()

        for row in histories:
            log_id = map_uuid("activity_logs", f"task_histories:{row.id}")
            exists = tgt.execute(
                text("SELECT id FROM activity_logs WHERE id = :id"),
                {"id": log_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(text("SAVEPOINT sp_log"))
                tgt.execute(
                    text(
                        """
                        INSERT INTO activity_logs (
                            id, entity_type, entity_id, action_type, performed_by_user_id, old_value, new_value, created_at, updated_at
                        )
                        VALUES (
                            :id, 'Task', :entity_id, 'STATUS_CHANGE', :performed_by_user_id,
                            CAST(:old_value AS jsonb), CAST(:new_value AS jsonb), :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": log_id,
                        "entity_id": map_uuid("tasks", row.task_id),
                        "performed_by_user_id": map_uuid("users", row.changed_by_id),
                        "old_value": (
                            f'{{"status":"{map_task_status(row.status_from)}","comment":"{(row.comment or "").replace(chr(34), chr(39))}"}}'
                            if row.status_from
                            else "{}"
                        ),
                        "new_value": (
                            f'{{"status":"{map_task_status(row.status_to)}","comment":"{(row.comment or "").replace(chr(34), chr(39))}"}}'
                            if row.status_to
                            else "{}"
                        ),
                        "created_at": row.timestamp,
                        "updated_at": row.timestamp,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.execute(text("ROLLBACK TO SAVEPOINT sp_log"))
                counters.errors += 1
                print(f"Error migrating task history {row.id}: {exc}")

        tgt.commit()

    print_summary("Tasks", counters)
    return counters


if __name__ == "__main__":
    migrate_tasks()

