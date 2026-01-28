import os

from sqlalchemy import create_engine, text


def _normalize_db_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+pg8000://", 1)
    return raw_url


def main() -> None:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise RuntimeError("DATABASE_URL is not set.")

    engine = create_engine(_normalize_db_url(raw_url))

    with engine.begin() as conn:
        company_rows = conn.execute(
            text("SELECT id FROM companies WHERE name = 'Best Solution Cars';")
        ).fetchall()
        if not company_rows:
            raise RuntimeError("Company 'Best Solution Cars' not found.")

        target_company_id = company_rows[0][0]
        print(f"Best Solution Cars id: {target_company_id}")

        car_company_ids = conn.execute(
            text("SELECT DISTINCT company_id FROM cars ORDER BY company_id;")
        ).fetchall()
        print("car company_ids:", [row[0] for row in car_company_ids])

        update_result = conn.execute(
            text(
                "UPDATE cars "
                "SET company_id = :target_company_id "
                "WHERE company_id IS NOT NULL "
                "AND company_id != :target_company_id"
            ),
            {"target_company_id": target_company_id},
        )

        print(f"cars updated: {update_result.rowcount}")

        final_company_ids = conn.execute(
            text("SELECT DISTINCT company_id FROM cars ORDER BY company_id;")
        ).fetchall()
        print("final car company_ids:", [row[0] for row in final_company_ids])


if __name__ == "__main__":
    main()
