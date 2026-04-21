from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, print_summary


def migrate_teams() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        member_rows = src.execute(
            text("SELECT group_id, user_id FROM group_members ORDER BY group_id, user_id")
        ).fetchall()
        fallback_head_by_group = {}
        for member in member_rows:
            fallback_head_by_group.setdefault(member.group_id, member.user_id)

        groups = src.execute(
            text("SELECT id, name, head_id FROM groups ORDER BY id")
        ).fetchall()

        for group in groups:
            team_id = map_uuid("teams", group.id)
            exists = tgt.execute(
                text("SELECT id FROM teams WHERE id = :id"),
                {"id": team_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                source_head_id = group.head_id if group.head_id is not None else fallback_head_by_group.get(group.id)
                head_user_id = map_uuid("users", source_head_id) if source_head_id is not None else None
                if not head_user_id:
                    raise ValueError(f"group {group.id} has no head_id")

                tgt.execute(
                    text(
                        """
                        INSERT INTO teams (id, name, head_user_id, created_by_user_id, created_at, updated_at)
                        VALUES (:id, :name, :head_user_id, :created_by_user_id, NOW(), NOW())
                        """
                    ),
                    {
                        "id": team_id,
                        "name": group.name,
                        "head_user_id": head_user_id,
                        "created_by_user_id": head_user_id,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating group {group.id}: {exc}")

        memberships = member_rows

        for member in memberships:
            team_member_id = map_uuid("team_members", f"{member.group_id}:{member.user_id}")
            exists = tgt.execute(
                text("SELECT id FROM team_members WHERE id = :id"),
                {"id": team_member_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                team_id = map_uuid("teams", member.group_id)
                user_id = map_uuid("users", member.user_id)
                is_head = tgt.execute(
                    text("SELECT 1 FROM teams WHERE id = :team_id AND head_user_id = :user_id"),
                    {"team_id": team_id, "user_id": user_id},
                ).first()

                tgt.execute(
                    text(
                        """
                        INSERT INTO team_members (id, team_id, user_id, role)
                        VALUES (:id, :team_id, :user_id, :role)
                        """
                    ),
                    {
                        "id": team_member_id,
                        "team_id": team_id,
                        "user_id": user_id,
                        "role": "head" if is_head else "member",
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating group_member {member.group_id}/{member.user_id}: {exc}")

        tgt.commit()

    print_summary("Teams", counters)
    return counters


if __name__ == "__main__":
    migrate_teams()

