from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, print_summary
from scripts.migration.mapping import map_payment_type


def migrate_payments() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        payments = src.execute(
            text(
                """
                SELECT
                    id, title, description, amount, currency, payment_type, due_date,
                    employee_id, company_id, category, created_by_id, created_at, updated_at
                FROM payments
                ORDER BY id
                """
            )
        ).fetchall()

        # Fallback creator for legacy rows with NULL created_by_id.
        fallback_creator = tgt.execute(
            text("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")
        ).first()
        fallback_creator_id = fallback_creator.id if fallback_creator else None

        for row in payments:
            payment_id = map_uuid("payments", row.id)
            exists = tgt.execute(
                text("SELECT id FROM payments WHERE id = :id"),
                {"id": payment_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                creator_id = (
                    map_uuid("users", row.created_by_id)
                    if row.created_by_id is not None
                    else fallback_creator_id
                )
                if creator_id is None:
                    raise ValueError("No created_by_user_id and no fallback user found")

                tgt.execute(
                    text(
                        """
                        INSERT INTO payments (
                            id, title, description, amount, currency, payment_type, payment_category,
                            payment_date, is_income, employee_user_id, company_id, created_by_user_id,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :title, :description, :amount, :currency, :payment_type, :payment_category,
                            :payment_date, :is_income, :employee_user_id, :company_id, :created_by_user_id,
                            :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": payment_id,
                        "title": row.title,
                        "description": row.description,
                        "amount": row.amount,
                        "currency": row.currency or "EUR",
                        "payment_type": map_payment_type(row.payment_type),
                        "payment_category": row.category,
                        "payment_date": row.due_date,
                        "is_income": bool(
                            (row.payment_type or "").lower()
                            in {"car_rental_income", "other_income"}
                        ),
                        "employee_user_id": (
                            map_uuid("users", row.employee_id) if row.employee_id else None
                        ),
                        "company_id": (
                            map_uuid("companies", row.company_id) if row.company_id else None
                        ),
                        "created_by_user_id": creator_id,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at or row.created_at,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating payment {row.id}: {exc}")

        tgt.commit()

    print_summary("Payments", counters)
    return counters


if __name__ == "__main__":
    migrate_payments()

