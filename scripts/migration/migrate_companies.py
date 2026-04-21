from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, print_summary


def migrate_companies() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        rows = src.execute(
            text(
                """
                SELECT id, name, vat_number, occupation, creation_date, description
                FROM companies
                ORDER BY id
                """
            )
        ).fetchall()

        for row in rows:
            company_id = map_uuid("companies", row.id)
            exists = tgt.execute(
                text("SELECT id FROM companies WHERE id = :id"),
                {"id": company_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(text("SAVEPOINT sp_company"))
                tgt.execute(
                    text(
                        """
                        INSERT INTO companies (
                            id, name, vat_number, occupation, creation_date, description, deleted_at, created_at, updated_at
                        )
                        VALUES (
                            :id, :name, :vat_number, :occupation, :creation_date, :description, NULL, NOW(), NOW()
                        )
                        """
                    ),
                    {
                        "id": company_id,
                        "name": row.name,
                        "vat_number": row.vat_number,
                        "occupation": row.occupation,
                        "creation_date": row.creation_date,
                        "description": row.description,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.execute(text("ROLLBACK TO SAVEPOINT sp_company"))
                counters.errors += 1
                print(f"Error migrating company {row.id}: {exc}")

        tgt.commit()

    print_summary("Companies", counters)
    return counters


if __name__ == "__main__":
    migrate_companies()

