from sqlalchemy import text

from scripts.migration.common import Counters, build_engines, map_uuid, now_utc, print_summary


def migrate_cars() -> Counters:
    source_engine, target_engine = build_engines()
    counters = Counters()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        cars = src.execute(
            text("SELECT id, manufacturer, model, license_plate FROM cars ORDER BY id")
        ).fetchall()

        for row in cars:
            car_id = map_uuid("cars", row.id)
            exists = tgt.execute(
                text("SELECT id FROM cars WHERE id = :id"),
                {"id": car_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(
                    text(
                        """
                        INSERT INTO cars (
                            id, make, model, license_plate, year, purchase_date, purchase_price, status, notes, created_at, updated_at
                        )
                        VALUES (
                            :id, :make, :model, :license_plate, :year, NULL, NULL, 'available', NULL, NOW(), NOW()
                        )
                        """
                    ),
                    {
                        "id": car_id,
                        "make": row.manufacturer,
                        "model": row.model,
                        "license_plate": row.license_plate,
                        "year": 2000,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating car {row.id}: {exc}")

        # Ensure one maintenance row per car (idempotent).
        for row in cars:
            maintenance_id = map_uuid("car_maintenance", row.id)
            car_id = map_uuid("cars", row.id)
            exists = tgt.execute(
                text("SELECT id FROM car_maintenance WHERE id = :id"),
                {"id": maintenance_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(
                    text(
                        """
                        INSERT INTO car_maintenance (
                            id, car_id, last_service_date, next_service_date, last_kteo_date, next_kteo_date, last_tyre_change_date, updated_at
                        )
                        VALUES (
                            :id, :car_id, NULL, NULL, NULL, NULL, NULL, :updated_at
                        )
                        """
                    ),
                    {"id": maintenance_id, "car_id": car_id, "updated_at": now_utc()},
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error creating maintenance row for car {row.id}: {exc}")

        incomes = src.execute(
            text(
                """
                SELECT id, car_id, customer_name, amount, transaction_date, description, created_at
                FROM car_incomes
                ORDER BY id
                """
            )
        ).fetchall()

        for row in incomes:
            income_id = map_uuid("car_incomes", row.id)
            exists = tgt.execute(
                text("SELECT id FROM car_incomes WHERE id = :id"),
                {"id": income_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(
                    text(
                        """
                        INSERT INTO car_incomes (
                            id, car_id, customer_name, amount, income_type, transaction_date, description, created_at
                        )
                        VALUES (
                            :id, :car_id, :customer_name, :amount, 'rental', :transaction_date, :description, :created_at
                        )
                        """
                    ),
                    {
                        "id": income_id,
                        "car_id": map_uuid("cars", row.car_id),
                        "customer_name": row.customer_name,
                        "amount": row.amount,
                        "transaction_date": row.transaction_date,
                        "description": row.description,
                        "created_at": row.created_at,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating car income {row.id}: {exc}")

        expenses = src.execute(
            text(
                """
                SELECT id, car_id, service_type, amount, transaction_date, description, created_at
                FROM car_expenses
                ORDER BY id
                """
            )
        ).fetchall()

        for row in expenses:
            expense_id = map_uuid("car_expenses", row.id)
            exists = tgt.execute(
                text("SELECT id FROM car_expenses WHERE id = :id"),
                {"id": expense_id},
            ).first()
            if exists:
                counters.skipped += 1
                continue

            try:
                tgt.execute(
                    text(
                        """
                        INSERT INTO car_expenses (
                            id, car_id, expense_type, amount, transaction_date, description, created_at
                        )
                        VALUES (
                            :id, :car_id, :expense_type, :amount, :transaction_date, :description, :created_at
                        )
                        """
                    ),
                    {
                        "id": expense_id,
                        "car_id": map_uuid("cars", row.car_id),
                        "expense_type": row.service_type,
                        "amount": row.amount,
                        "transaction_date": row.transaction_date,
                        "description": row.description,
                        "created_at": row.created_at,
                    },
                )
                counters.inserted += 1
            except Exception as exc:
                tgt.rollback()
                counters.errors += 1
                print(f"Error migrating car expense {row.id}: {exc}")

        tgt.commit()

    print_summary("Cars", counters)
    return counters


if __name__ == "__main__":
    migrate_cars()

