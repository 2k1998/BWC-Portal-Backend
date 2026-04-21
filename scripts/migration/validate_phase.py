from dataclasses import dataclass

from sqlalchemy import text

from scripts.migration.common import build_engines, map_uuid


@dataclass
class ValidationResult:
    ok: bool
    message: str


PHASE_TABLES = {
    "users": ("users", "users"),
    "companies": ("companies", "companies"),
    "teams": ("groups", "teams"),
    "tasks": ("tasks", "tasks"),
    "payments": ("payments", "payments"),
    "cars": ("cars", "cars"),
}


def _count(conn, table_name: str) -> int:
    row = conn.execute(text(f"SELECT COUNT(*) AS c FROM {table_name}")).first()
    return int(row.c) if row else 0


def validate_counts(phase: str) -> ValidationResult:
    source_table, target_table = PHASE_TABLES[phase]
    source_engine, target_engine = build_engines()

    with source_engine.connect() as src, target_engine.connect() as tgt:
        src_count = _count(src, source_table)
        tgt_count = _count(tgt, target_table)

    if tgt_count < src_count:
        return ValidationResult(False, f"{phase}: target_count={tgt_count} < source_count={src_count}")
    return ValidationResult(True, f"{phase}: source_count={src_count}, target_count={tgt_count}")


def validate_fk_orphans(phase: str) -> ValidationResult:
    _, target_engine = build_engines()
    checks = {
        "teams": """
            SELECT COUNT(*) AS c
            FROM team_members tm
            LEFT JOIN teams t ON t.id = tm.team_id
            LEFT JOIN users u ON u.id = tm.user_id
            WHERE t.id IS NULL OR u.id IS NULL
        """,
        "tasks": """
            SELECT COUNT(*) AS c
            FROM tasks t
            LEFT JOIN users uo ON uo.id = t.owner_user_id
            LEFT JOIN companies c ON c.id = t.company_id
            WHERE uo.id IS NULL OR c.id IS NULL
        """,
        "payments": """
            SELECT COUNT(*) AS c
            FROM payments p
            LEFT JOIN companies c ON c.id = p.company_id
            LEFT JOIN users u ON u.id = p.created_by_user_id
            WHERE c.id IS NULL OR u.id IS NULL
        """,
        "cars": """
            SELECT COUNT(*) AS c
            FROM car_incomes ci
            LEFT JOIN cars c ON c.id = ci.car_id
            WHERE c.id IS NULL
        """,
    }
    sql = checks.get(phase)
    if not sql:
        return ValidationResult(True, f"{phase}: no fk check defined")

    with target_engine.connect() as tgt:
        row = tgt.execute(text(sql)).first()
        orphan_count = int(row.c) if row else 0

    if orphan_count > 0:
        return ValidationResult(False, f"{phase}: orphan_count={orphan_count}")
    return ValidationResult(True, f"{phase}: orphan_count=0")


def validate_spot_check(phase: str) -> ValidationResult:
    if phase not in {"users", "companies", "tasks", "payments", "cars"}:
        return ValidationResult(True, f"{phase}: no spot-check defined")

    source_engine, target_engine = build_engines()
    with source_engine.connect() as src, target_engine.connect() as tgt:
        source_rows = src.execute(
            text(f"SELECT id FROM {PHASE_TABLES[phase][0]} ORDER BY random() LIMIT 5")
        ).fetchall()
        for source_row in source_rows:
            target_id = map_uuid(PHASE_TABLES[phase][1], source_row.id)
            exists = tgt.execute(
                text(f"SELECT id FROM {PHASE_TABLES[phase][1]} WHERE id = :id"),
                {"id": target_id},
            ).first()
            if not exists:
                return ValidationResult(False, f"{phase}: missing mapped id for source id {source_row.id}")

    return ValidationResult(True, f"{phase}: 5-row spot-check passed")


def run_phase_validation(phase: str) -> bool:
    count_result = validate_counts(phase)
    fk_result = validate_fk_orphans(phase)
    spot_result = validate_spot_check(phase)
    print(count_result.message)
    print(fk_result.message)
    print(spot_result.message)
    return count_result.ok and fk_result.ok and spot_result.ok

