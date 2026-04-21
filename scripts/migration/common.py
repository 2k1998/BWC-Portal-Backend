import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import create_engine, text


SOURCE_URL = os.getenv("SOURCE_DB_URL")
TARGET_URL = os.getenv("TARGET_DB_URL")

MIGRATION_NAMESPACE = uuid.UUID("9f668e8c-d3cb-46db-9ec6-c78f9a4da89b")


@dataclass
class Counters:
    inserted: int = 0
    skipped: int = 0
    errors: int = 0


def require_urls() -> tuple[str, str]:
    if not SOURCE_URL:
        raise RuntimeError("SOURCE_DB_URL is required")
    if not TARGET_URL:
        raise RuntimeError("TARGET_DB_URL is required")
    return SOURCE_URL, TARGET_URL


def build_engines():
    source_url, target_url = require_urls()
    return create_engine(source_url), create_engine(target_url)


def map_uuid(entity: str, source_id: Any) -> uuid.UUID:
    # Stable deterministic mapping for repeatable reruns.
    return uuid.uuid5(MIGRATION_NAMESPACE, f"{entity}:{source_id}")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def print_summary(name: str, counters: Counters) -> None:
    print(
        f"{name}: inserted={counters.inserted}, "
        f"skipped={counters.skipped}, errors={counters.errors}"
    )


def scalar_count(conn, table_name: str) -> int:
    row = conn.execute(text(f"SELECT COUNT(*) AS c FROM {table_name}")).first()
    return int(row.c) if row else 0


def chunked(items: Iterable[Any], size: int):
    bucket = []
    for item in items:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket

