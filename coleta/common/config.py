from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

BASELINE_START = date(2011, 5, 18)
BASELINE_END = date(2026, 5, 18)
DEFAULT_DEV_DATA_DIR = Path("data/dev")
PROD_DATA_ROOT_ENV = "FALANDO_NELA_DATA_ROOT"


@dataclass(frozen=True)
class RuntimeConfig:
    data_inicio: date
    data_fim: date
    mode: str
    output_dir: Path
    sample: bool
    sample_limit: int | None
    resume: bool
    run_id: str


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Data invalida: {value}. Use AAAA-MM-DD.") from exc


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def format_senado_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def month_windows(data_inicio: date, data_fim: date) -> Iterator[tuple[str, date, date]]:
    if data_inicio > data_fim:
        raise ValueError("data_inicio nao pode ser posterior a data_fim")

    current = data_inicio
    while current <= data_fim:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)

        end = min(data_fim, next_month - timedelta(days=1))
        yield f"{current.year:04d}-{current.month:02d}", current, end
        current = end + timedelta(days=1)


def apply_sample_window(windows: list[tuple[str, date, date]], sample: bool) -> list[tuple[str, date, date]]:
    if not sample:
        return windows
    return windows[:1]
