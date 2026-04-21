from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, print_summary
from scripts.migration.mapping import map_user_type


def migrate_users() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        rows = src.execute(
            text(
                """
                SELECT id, email, hashed_password, first_name, surname, birthday, role, is_active
                FROM users
                ORDER BY id
                """
            )
        ).fetchall()

        for row in rows:
            user_id = map_uuid("users", row.id)
            exists = tgt.execute(
                text("SELECT id FROM users WHERE id = :id"),
                {"id": user_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                first_name = row.first_name or "Unknown"
                last_name = row.surname or "Unknown"
                username = (row.email.split("@")[0] if row.email else f"user_{row.id}")[:255]
                tgt.execute(
                    text(
                        """
                        INSERT INTO users (
                            id, email, username, first_name, last_name, hashed_password,
                            user_type, is_active, force_password_change, manager_id
                        )
                        VALUES (
                            :id, :email, :username, :first_name, :last_name, :hashed_password,
                            :user_type, :is_active, :force_password_change, :manager_id
                        )
                        """
                    ),
                    {
                        "id": user_id,
                        "email": row.email,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "hashed_password": row.hashed_password,
                        "user_type": map_user_type(row.role),
                        "is_active": bool(row.is_active),
                        "force_password_change": True,
                        "manager_id": None,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating user {row.id}: {exc}")

        tgt.commit()

    print_summary("Users", counters)
    return counters


if __name__ == "__main__":
    migrate_users()

