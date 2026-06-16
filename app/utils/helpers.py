import uuid
from datetime import datetime
from typing import Optional


def generate_archive_index(category_code: str, fonds_code: str, year: int, sequence: int) -> str:
    seq_str = str(sequence).zfill(6)
    return f"{category_code}-{fonds_code}-{year}-{seq_str}"


def generate_unique_id() -> str:
    return uuid.uuid4().hex[:16].upper()


def generate_task_code(prefix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{timestamp}-{random}"


def get_season_by_date(date: Optional[datetime] = None) -> int:
    if date is None:
        date = datetime.now()
    return (date.month - 1) // 3 + 1
