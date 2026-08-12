from __future__ import annotations

import logging
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from falando_nela.gcp_config import GcpContract
from falando_nela.parquet_pipeline import g03_arrow_schema

SOURCE_ENV = "FALANDO_NELA_G04_SOURCE"
FIXTURE_ENV = "FALANDO_NELA_G04_FIXTURE"
DEFAULT_SOURCE = "gcs"
SourceKind = Literal["gcs", "fixture"]

LOGGER = logging.getLogger(__name__)


class MarimoDatasetError(RuntimeError):
    """A fonte do primeiro app Marimo diverge do contrato G04."""


@dataclass(frozen=True)
class LoadedDataset:
    rows: tuple[dict[str, Any], ...]
    source: SourceKind
    locator: str
    operation_id: str
    loaded_at: datetime
    duration_seconds: float


def resolve_source(environ: Mapping[str, str] | None = None) -> SourceKind:
    environment = os.environ if environ is None else environ
    source = environment.get(SOURCE_ENV, DEFAULT_SOURCE).strip().lower()
    if source not in {"gcs", "fixture"}:
        raise MarimoDatasetError(
            f"{SOURCE_ENV} deve ser 'gcs' ou 'fixture'; recebido: {source or '<vazio>'}"
        )
    return cast(SourceKind, source)


def load_g04_dataset(
    contract: GcpContract,
    *,
    environ: Mapping[str, str] | None = None,
    gcs_filesystem: Any | None = None,
) -> LoadedDataset:
    import pyarrow as pa
    import pyarrow.fs as pafs
    import pyarrow.parquet as pq

    environment = os.environ if environ is None else environ
    source = resolve_source(environment)
    started = time.monotonic()

    if source == "fixture":
        fixture_value = environment.get(FIXTURE_ENV, "").strip()
        if not fixture_value:
            raise MarimoDatasetError(f"{FIXTURE_ENV} é obrigatório quando {SOURCE_ENV}=fixture")
        fixture_path = Path(fixture_value).expanduser()
        if not fixture_path.is_file():
            raise MarimoDatasetError(f"fixture G04 não encontrada: {fixture_path}")
        parquet_source: str | Path = fixture_path
        filesystem = None
        locator = str(fixture_path.resolve())
    else:
        parquet_source = f"{contract.data.bucket}/{contract.marimo.parquet_locator}"
        locator = f"gs://{parquet_source}"
        filesystem = gcs_filesystem

    try:
        if source == "gcs" and filesystem is None:
            filesystem = pafs.GcsFileSystem(project_id=contract.project_id)
        parquet = pq.ParquetFile(parquet_source, filesystem=filesystem)
        _validate_parquet_contract(parquet, contract=contract, pa=pa)
        table = parquet.read().sort_by([("source_id", "ascending")])
    except (OSError, pa.ArrowException) as exc:
        source_label = "GCS via ADC" if source == "gcs" else "fixture local"
        raise MarimoDatasetError(
            f"não foi possível ler o Parquet G04 de {source_label}: {locator}"
        ) from exc

    rows = tuple(table.to_pylist())
    duration = time.monotonic() - started
    LOGGER.info(
        "G04 carregado source=%s operation_id=%s records=%d duration_seconds=%.3f",
        source,
        contract.marimo.operation_id,
        len(rows),
        duration,
    )
    return LoadedDataset(
        rows=rows,
        source=source,
        locator=locator,
        operation_id=contract.marimo.operation_id,
        loaded_at=datetime.now(UTC),
        duration_seconds=duration,
    )


def filter_discourses(
    rows: Sequence[Mapping[str, Any]],
    *,
    query: str = "",
    party: str = "",
    federative_unit: str = "",
) -> tuple[dict[str, Any], ...]:
    normalized_query = query.strip().casefold()
    selected: list[dict[str, Any]] = []
    for row in rows:
        if party and row.get("party") != party:
            continue
        if federative_unit and row.get("federative_unit") != federative_unit:
            continue
        searchable = " ".join(
            str(row.get(field) or "")
            for field in ("source_id", "author_name", "speech_type_description", "text")
        ).casefold()
        if normalized_query and normalized_query not in searchable:
            continue
        selected.append(dict(row))
    return tuple(selected)


def filter_options(
    rows: Sequence[Mapping[str, Any]], field: Literal["party", "federative_unit"]
) -> tuple[str, ...]:
    return tuple(sorted({str(row[field]) for row in rows if row.get(field)}))


def presentation_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get("text") or "").split())
        preview = text if len(text) <= 500 else f"{text[:497]}..."
        result.append(
            {
                "source_id": row.get("source_id"),
                "data": row.get("pronouncement_date") or row.get("session_date"),
                "autoria": row.get("author_name"),
                "partido": row.get("party"),
                "UF": row.get("federative_unit"),
                "tipo": row.get("speech_type_description"),
                "texto": preview,
            }
        )
    return result


def _validate_parquet_contract(parquet: Any, *, contract: GcpContract, pa: Any) -> None:
    metadata = parquet.schema_arrow.metadata or {}
    observed_schema = metadata.get(b"falando_nela_schema", b"").decode("utf-8", errors="replace")
    if observed_schema != contract.marimo.parquet_schema:
        raise MarimoDatasetError(
            "schema lógico do Parquet diverge do contrato G04: "
            f"esperado={contract.marimo.parquet_schema}, observado={observed_schema or '<vazio>'}"
        )
    if parquet.schema_arrow.remove_metadata() != g03_arrow_schema(pa):
        raise MarimoDatasetError("schema físico do Parquet diverge do contrato G03")
    if parquet.metadata.num_rows == 0:
        raise MarimoDatasetError("Parquet G04 vazio")
    if parquet.metadata.num_rows != contract.marimo.expected_records:
        raise MarimoDatasetError(
            "contagem do Parquet diverge do contrato G04: "
            f"esperado={contract.marimo.expected_records}, observado={parquet.metadata.num_rows}"
        )
