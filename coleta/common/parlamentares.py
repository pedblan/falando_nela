from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class ParlamentarPeriodo:
    parlamentar_id: str
    nome: str | None
    vigencia_inicio: date
    vigencia_fim: date
    source: str
    intervalo_fonte: str | None = None


def load_parlamentares_periodos(
    data_root: Path,
    *,
    source: str,
    data_inicio: date,
    data_fim: date,
    allow_inferred: bool = False,
    min_ids: int = 1,
) -> dict[str, list[ParlamentarPeriodo]]:
    """Carrega periodos de mandato normalizados, se `parlamentares/v1` existir."""
    output_root = data_root / "processed" / "parlamentares" / "v1"
    rows = list(_iter_periodo_rows(output_root))
    if not rows:
        return {}

    periodos_by_id: dict[str, list[ParlamentarPeriodo]] = {}
    for row in rows:
        if _string(row.get("source")) != source:
            continue
        if not allow_inferred and _is_truthy(row.get("intervalo_inferido")):
            continue
        if not allow_inferred and _string(row.get("intervalo_fonte")) != "mandato":
            continue

        parlamentar_id = _string(row.get("parlamentar_id"))
        if not parlamentar_id:
            continue
        inicio = _parse_date(row.get("vigencia_inicio")) or data_inicio
        fim = _parse_period_end(row) or data_fim
        if inicio > data_fim or fim < data_inicio:
            continue

        periodos_by_id.setdefault(parlamentar_id, []).append(
            ParlamentarPeriodo(
                parlamentar_id=parlamentar_id,
                nome=_string(row.get("nome_parlamentar") or row.get("nome_civil")),
                vigencia_inicio=max(inicio, data_inicio),
                vigencia_fim=min(fim, data_fim),
                source=source,
                intervalo_fonte=_string(row.get("intervalo_fonte")),
            )
        )

    for parlamentar_id, periodos in list(periodos_by_id.items()):
        periodos.sort(key=lambda item: (item.vigencia_inicio, item.vigencia_fim, item.nome or ""))
        periodos_by_id[parlamentar_id] = periodos
    if len(periodos_by_id) < min_ids:
        return {}
    return dict(sorted(periodos_by_id.items(), key=lambda item: _id_sort_key(item[0])))


def active_parlamentares_for_window(
    periodos_by_id: dict[str, list[ParlamentarPeriodo]],
    *,
    start: date,
    end: date,
    sample: bool = False,
    sample_limit: int | None = None,
    default_sample_limit: int = 3,
) -> list[dict[str, Any]]:
    """Retorna parlamentares ativos na janela, com a janela efetiva clipada."""
    planned: list[dict[str, Any]] = []
    for parlamentar_id, periodos in sorted(periodos_by_id.items(), key=lambda item: _id_sort_key(item[0])):
        active = [periodo for periodo in periodos if periodo.vigencia_inicio <= end and periodo.vigencia_fim >= start]
        if not active:
            continue
        active_start = max(start, min(periodo.vigencia_inicio for periodo in active))
        active_end = min(end, max(periodo.vigencia_fim for periodo in active))
        nome = next((periodo.nome for periodo in active if periodo.nome), None)
        planned.append(
            {
                "id": int(parlamentar_id) if parlamentar_id.isdigit() else parlamentar_id,
                "nome": nome,
                "_active_start": active_start,
                "_active_end": active_end,
                "_periodos_mandato": len(active),
            }
        )

    if sample:
        limit = sample_limit if sample_limit is not None else default_sample_limit
        return planned[:limit]
    return planned


def parlamentar_active_period(deputado: dict[str, Any], fallback_start: date, fallback_end: date) -> tuple[date, date]:
    start = deputado.get("_active_start")
    end = deputado.get("_active_end")
    if isinstance(start, date) and isinstance(end, date):
        return start, end
    return fallback_start, fallback_end


def _iter_periodo_rows(output_root: Path) -> Iterator[dict[str, Any]]:
    parquet_path = output_root / "parquet" / "parlamentares_periodos.parquet"
    if parquet_path.exists():
        parquet_rows = list(_iter_parquet_rows(parquet_path))
        if parquet_rows:
            yield from parquet_rows
            return

    jsonl_path = output_root / "parlamentares_periodos.jsonl"
    if jsonl_path.exists():
        yield from _iter_jsonl_rows(jsonl_path)


def _iter_parquet_rows(path: Path) -> Iterator[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return

    try:
        table = pq.read_table(path)
    except Exception:
        return
    for row in table.to_pylist():
        if isinstance(row, dict):
            yield row


def _iter_jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def _parse_period_end(row: dict[str, Any]) -> date | None:
    fim = _parse_date(row.get("vigencia_fim"))
    if fim and fim != date(9999, 12, 31):
        return fim
    fim_exclusivo = _parse_date(row.get("vigencia_fim_exclusivo"))
    if fim_exclusivo and fim_exclusivo != date(9999, 12, 31):
        return fim_exclusivo - timedelta(days=1)
    return None if fim == date(9999, 12, 31) else fim


def _parse_date(value: Any) -> date | None:
    text = _string(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "sim", "yes"}
    return bool(value)


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _id_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**12, value)
