from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


DEFAULT_RAW_ROOT = Path("/content/drive/MyDrive/falando_nela/data/raw")
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_v3_inventory")
DEFAULT_MAX_JSON_BYTES = 64 * 1024 * 1024
SPEC_REF = "specs/pipeline_dados_v3/01_inventario_metadados_raw/requirements.md"
SCHEMA_VERSION = "raw-metadata-inventory-v3.1"
SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}
OPERATION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")

FILE_FIELDS = [
    "relative_path",
    "item_type",
    "suffix",
    "size_bytes",
    "source",
    "dataset",
    "partition_year",
    "partition_month",
    "structured_format",
    "technically_readable",
    "selected_for_read",
    "read_status",
    "records_observed",
    "records_read",
    "records_rejected",
    "error",
]
FIELD_FIELDS = [
    "source",
    "dataset",
    "record_type",
    "field_path",
    "technical_types",
    "records_universe",
    "field_absent",
    "present_null",
    "present_empty",
    "present_filled",
    "fill_rate",
    "cardinality",
    "cardinality_method",
    "string_length_min",
    "string_length_median",
    "string_length_max",
    "first_partition",
    "last_partition",
    "type_conflict",
]
VALUE_FIELDS = [
    "source",
    "dataset",
    "record_type",
    "field_path",
    "value_type",
    "value_json",
    "frequency",
    "rank",
]
ISSUE_FIELDS = [
    "severity",
    "issue_type",
    "relative_path",
    "record_number",
    "field_path",
    "detail",
]


@dataclass(frozen=True)
class InventoryConfig:
    raw_root: Path
    output_base: Path
    operation_id: str
    code_commit: str
    low_cardinality_limit: int = 100
    sample_size: int = 5
    sample_seed: str = "falando-nela-v3"
    max_copy_length: int = 200
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES
    cardinality_exact_limit: int = 10_000
    cardinality_kmv_size: int = 1_024
    max_files_per_group: int | None = None
    progress_every_files: int = 100

    @property
    def operation_root(self) -> Path:
        return self.output_base / self.operation_id

    @property
    def scope_mode(self) -> str:
        return "smoke" if self.max_files_per_group is not None else "full"


@dataclass
class CardinalityTracker:
    exact_limit: int
    kmv_size: int
    _exact: set[str] | None = field(default_factory=set)
    _kmv: set[int] = field(default_factory=set)

    def add(self, canonical_value: str) -> None:
        if self._exact is not None:
            self._exact.add(canonical_value)
            if len(self._exact) <= self.exact_limit:
                return
            for value in self._exact:
                self._add_hash(_hash_int(value))
            self._exact = None
            return
        self._add_hash(_hash_int(canonical_value))

    def result(self) -> tuple[int, str]:
        if self._exact is not None:
            return len(self._exact), "exact"
        if not self._kmv:
            return 0, "kmv_estimate"
        if len(self._kmv) < self.kmv_size:
            return len(self._kmv), "kmv_estimate"
        maximum = max(self._kmv)
        if maximum == 0:
            return len(self._kmv), "kmv_estimate"
        scale = float(2**256)
        estimate = round((self.kmv_size - 1) * scale / maximum)
        return max(estimate, len(self._kmv)), "kmv_estimate"

    @property
    def exact_values(self) -> set[str] | None:
        return self._exact

    def _add_hash(self, value_hash: int) -> None:
        self._kmv.add(value_hash)
        if len(self._kmv) > self.kmv_size:
            self._kmv.remove(max(self._kmv))


@dataclass
class FieldStats:
    exact_limit: int
    kmv_size: int
    low_cardinality_limit: int
    sample_size: int
    sample_seed: str
    present: int = 0
    null: int = 0
    empty: int = 0
    filled: int = 0
    technical_types: Counter[str] = field(default_factory=Counter)
    string_lengths: Counter[int] = field(default_factory=Counter)
    partitions: set[str] = field(default_factory=set)
    value_frequencies: Counter[str] | None = field(default_factory=Counter)
    value_representations: dict[str, tuple[str, str]] = field(default_factory=dict)
    samples: dict[str, tuple[str, str, Any]] = field(default_factory=dict)
    cardinality: CardinalityTracker = field(init=False)
    scalar_values_observed: int = 0

    def __post_init__(self) -> None:
        self.cardinality = CardinalityTracker(self.exact_limit, self.kmv_size)

    def observe_record(
        self,
        values: Sequence[Any],
        *,
        partition: str,
        max_copy_length: int,
    ) -> None:
        self.present += 1
        states = {value_state(value) for value in values}
        if "filled" in states:
            self.filled += 1
        elif "empty" in states:
            self.empty += 1
        else:
            self.null += 1
        if partition:
            self.partitions.add(partition)

        for value in values:
            value_type = technical_type(value)
            self.technical_types[value_type] += 1
            if isinstance(value, str):
                self.string_lengths[len(value)] += 1
            safe_value = safe_sample_value(
                value,
                max_copy_length=max_copy_length,
            )
            safe_json = json.dumps(
                safe_value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            sample_token = canonical_token(
                safe_value,
                max_copy_length=max_copy_length,
            )
            sample_hash = hashlib.sha256(
                f"{self.sample_seed}\0{sample_token}".encode("utf-8")
            ).hexdigest()
            self.samples[sample_hash] = (value_type, sample_token, safe_value)
            if len(self.samples) > self.sample_size:
                del self.samples[max(self.samples)]

            if isinstance(value, (Mapping, list, tuple)):
                continue
            self.scalar_values_observed += 1
            canonical = canonical_token(
                value,
                max_copy_length=max_copy_length,
            )
            self.cardinality.add(canonical)
            if self.value_frequencies is not None:
                self.value_frequencies[canonical] += 1
                self.value_representations[canonical] = (value_type, safe_json)
                if len(self.value_frequencies) > self.low_cardinality_limit:
                    self.value_frequencies = None
                    self.value_representations.clear()

    def cardinality_result(self) -> tuple[int | str, str]:
        if self.scalar_values_observed == 0:
            return "", "not_applicable_complex"
        value, method = self.cardinality.result()
        if method == "exact":
            return value, "exact_scalar_values"
        return value, "kmv_scalar_estimate"


@dataclass
class InventoryAccumulator:
    config: InventoryConfig
    group_records: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    fields: dict[tuple[str, str, str, str], FieldStats] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    _issue_keys: set[tuple[str, str, str, int | str, str, str]] = field(
        default_factory=set
    )

    def observe_record(
        self,
        record: Any,
        *,
        source: str,
        dataset: str,
        partition: str,
        relative_path: str,
        record_number: int,
        technical_record_kind: str,
    ) -> None:
        record_type = declared_record_type(record, technical_record_kind)
        group = (source, dataset, record_type)
        self.group_records[group] += 1

        if isinstance(record, Mapping):
            declared_source = record.get("source")
            declared_dataset = record.get("dataset")
            if (
                isinstance(declared_source, str)
                and source
                and declared_source != source
            ):
                self.add_issue(
                    severity="warning",
                    issue_type="declared_source_path_conflict",
                    relative_path=relative_path,
                    record_number=record_number,
                    field_path="$.source",
                    detail=f"declarado={declared_source!r}; caminho={source!r}",
                )
            if (
                isinstance(declared_dataset, str)
                and dataset
                and declared_dataset != dataset
            ):
                self.add_issue(
                    severity="warning",
                    issue_type="declared_dataset_path_conflict",
                    relative_path=relative_path,
                    record_number=record_number,
                    field_path="$.dataset",
                    detail=f"declarado={declared_dataset!r}; caminho={dataset!r}",
                )

        values_by_path: defaultdict[str, list[Any]] = defaultdict(list)
        for field_path, value in flatten_fields(record):
            values_by_path[field_path].append(value)
        for field_path in sorted(values_by_path):
            key = (*group, field_path)
            stats = self.fields.get(key)
            if stats is None:
                stats = FieldStats(
                    exact_limit=self.config.cardinality_exact_limit,
                    kmv_size=self.config.cardinality_kmv_size,
                    low_cardinality_limit=self.config.low_cardinality_limit,
                    sample_size=self.config.sample_size,
                    sample_seed=self.config.sample_seed,
                )
                self.fields[key] = stats
            stats.observe_record(
                values_by_path[field_path],
                partition=partition,
                max_copy_length=self.config.max_copy_length,
            )

    def add_issue(
        self,
        *,
        severity: str,
        issue_type: str,
        relative_path: str,
        detail: str,
        record_number: int | str = "",
        field_path: str = "",
    ) -> None:
        issue_key = (
            severity,
            issue_type,
            relative_path,
            record_number,
            field_path,
            detail,
        )
        if issue_key in self._issue_keys:
            return
        self._issue_keys.add(issue_key)
        self.issues.append(
            {
                "severity": severity,
                "issue_type": issue_type,
                "relative_path": relative_path,
                "record_number": record_number,
                "field_path": field_path,
                "detail": detail,
            }
        )


def run_inventory(config: InventoryConfig) -> dict[str, Any]:
    config = validated_config(config)
    started_at = utc_now()
    operation_root = config.operation_root
    operation_root.mkdir(parents=True)
    file_rows: list[dict[str, Any]] = []
    accumulator = InventoryAccumulator(config)
    fingerprint_before = structural_fingerprint(config.raw_root)

    try:
        file_rows = catalog_tree(config.raw_root, accumulator)
        select_files(file_rows, config)
        selected = [
            row
            for row in file_rows
            if row["item_type"] == "file" and row["selected_for_read"]
        ]
        for index, row in enumerate(selected, start=1):
            inspect_file(
                config.raw_root / row["relative_path"],
                row=row,
                accumulator=accumulator,
            )
            if config.progress_every_files > 0 and (
                index == 1
                or index == len(selected)
                or index % config.progress_every_files == 0
            ):
                print(
                    f"[inventario-v3] arquivos lidos: {index}/{len(selected)}",
                    flush=True,
                )

        fingerprint_after = structural_fingerprint(config.raw_root)
        if fingerprint_after != fingerprint_before:
            raise RuntimeError(
                "A árvore raw mudou durante o inventário; interrompa coletores "
                "e execute novamente."
            )

        field_rows = build_field_rows(accumulator)
        value_rows = build_value_rows(accumulator)
        sample_rows = build_sample_rows(accumulator)
        issues = sorted_issues(accumulator.issues)
        counts = build_counts(
            file_rows=file_rows,
            field_rows=field_rows,
            value_rows=value_rows,
            issues=issues,
        )

        paths = write_success_outputs(
            config=config,
            started_at=started_at,
            fingerprint=fingerprint_before,
            file_rows=file_rows,
            field_rows=field_rows,
            value_rows=value_rows,
            sample_rows=sample_rows,
            issues=issues,
            counts=counts,
        )
        return {
            "manifest": json.loads(paths["manifest"].read_text(encoding="utf-8")),
            "paths": paths,
            "file_rows": file_rows,
            "field_rows": field_rows,
            "value_rows": value_rows,
            "sample_rows": sample_rows,
            "issues": issues,
        }
    except Exception as exc:
        write_failure_outputs(
            config=config,
            started_at=started_at,
            fingerprint=fingerprint_before,
            file_rows=file_rows,
            issues=accumulator.issues,
            error=exc,
        )
        raise


def validated_config(config: InventoryConfig) -> InventoryConfig:
    raw_root = config.raw_root.expanduser().resolve()
    output_base = config.output_base.expanduser().resolve()
    normalized = InventoryConfig(
        raw_root=raw_root,
        output_base=output_base,
        operation_id=config.operation_id,
        code_commit=config.code_commit,
        low_cardinality_limit=config.low_cardinality_limit,
        sample_size=config.sample_size,
        sample_seed=config.sample_seed,
        max_copy_length=config.max_copy_length,
        max_json_bytes=config.max_json_bytes,
        cardinality_exact_limit=config.cardinality_exact_limit,
        cardinality_kmv_size=config.cardinality_kmv_size,
        max_files_per_group=config.max_files_per_group,
        progress_every_files=config.progress_every_files,
    )
    if not raw_root.is_dir():
        raise ValueError(f"Raiz raw inexistente ou inválida: {raw_root}")
    if raw_root.name != "raw":
        raise ValueError("A raiz aprovada deve terminar exatamente em raw.")
    if not OPERATION_ID_PATTERN.fullmatch(config.operation_id):
        raise ValueError(
            "operation_id deve usar apenas minúsculas, números, ponto, "
            "sublinhado e hífen."
        )
    if not config.code_commit.strip():
        raise ValueError("code_commit é obrigatório.")
    for name, value, minimum in [
        ("low_cardinality_limit", config.low_cardinality_limit, 1),
        ("sample_size", config.sample_size, 1),
        ("max_copy_length", config.max_copy_length, 1),
        ("max_json_bytes", config.max_json_bytes, 1),
        ("cardinality_exact_limit", config.cardinality_exact_limit, 2),
        ("cardinality_kmv_size", config.cardinality_kmv_size, 2),
        ("progress_every_files", config.progress_every_files, 0),
    ]:
        if value < minimum:
            raise ValueError(f"{name} deve ser maior ou igual a {minimum}.")
    if config.cardinality_exact_limit <= config.low_cardinality_limit:
        raise ValueError("cardinality_exact_limit deve superar low_cardinality_limit.")
    if config.max_files_per_group is not None and config.max_files_per_group < 1:
        raise ValueError("max_files_per_group deve ser positivo.")

    operation_root = normalized.operation_root
    if is_relative_to(operation_root, raw_root):
        raise ValueError("A saída não pode ficar dentro da raiz raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(operation_root, drive_root):
        raise ValueError("A saída temporária não pode ficar dentro do Drive.")
    if operation_root.exists():
        raise FileExistsError(
            f"operation_id já possui saída e não será sobrescrito: {operation_root}"
        )
    return normalized


def catalog_tree(
    raw_root: Path,
    accumulator: InventoryAccumulator,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(raw_root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(raw_root).as_posix()
        parts = Path(relative).parts
        source = parts[0] if len(parts) >= 1 else ""
        dataset = parts[1] if len(parts) >= 2 else ""
        if path.is_dir():
            stat = path.stat()
            row = {
                "relative_path": relative,
                "item_type": "directory",
                "suffix": "",
                "size_bytes": "",
                "source": source,
                "dataset": dataset,
                "partition_year": partition_value(parts, "ano"),
                "partition_month": partition_value(parts, "mes"),
                "structured_format": "",
                "technically_readable": False,
                "selected_for_read": False,
                "read_status": "not_applicable",
                "records_observed": "",
                "records_read": "",
                "records_rejected": "",
                "error": "",
                "_mtime_ns": stat.st_mtime_ns,
            }
            if not source or not dataset:
                accumulator.add_issue(
                    severity="info",
                    issue_type="catalog_level_above_dataset",
                    relative_path=relative,
                    detail=(
                        "Diretório estrutural acima do nível "
                        "{fonte}/{dataset}; campo vazio é esperado."
                    ),
                )
        elif path.is_file():
            stat = path.stat()
            suffix = path.suffix.lower()
            row = {
                "relative_path": relative,
                "item_type": "file",
                "suffix": suffix,
                "size_bytes": stat.st_size,
                "source": source,
                "dataset": dataset,
                "partition_year": partition_value(parts, "ano"),
                "partition_month": partition_value(parts, "mes"),
                "structured_format": format_name(suffix),
                "technically_readable": suffix in SUPPORTED_SUFFIXES,
                "selected_for_read": False,
                "read_status": (
                    "pending" if suffix in SUPPORTED_SUFFIXES else "unsupported_format"
                ),
                "records_observed": 0,
                "records_read": 0,
                "records_rejected": 0,
                "error": "",
                "_mtime_ns": stat.st_mtime_ns,
            }
            if not source or not dataset:
                accumulator.add_issue(
                    severity="warning",
                    issue_type="source_or_dataset_unresolved",
                    relative_path=relative,
                    detail=(
                        "O caminho não contém os dois níveis esperados "
                        "{fonte}/{dataset}."
                    ),
                )
        else:
            continue
        rows.append(row)
    return rows


def select_files(
    rows: list[dict[str, Any]],
    config: InventoryConfig,
) -> None:
    candidates = [
        row
        for row in rows
        if row["item_type"] == "file" and row["suffix"] in SUPPORTED_SUFFIXES
    ]
    if config.max_files_per_group is None:
        selected_paths = {row["relative_path"] for row in candidates}
    else:
        grouped: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(
            list
        )
        for row in candidates:
            grouped[(row["source"], row["dataset"], row["suffix"])].append(row)
        selected_paths = set()
        for key in sorted(grouped):
            ordered = sorted(grouped[key], key=lambda row: row["relative_path"])
            selected_paths.update(
                row["relative_path"]
                for row in spread_sample(ordered, config.max_files_per_group)
            )
    for row in candidates:
        if row["relative_path"] in selected_paths:
            row["selected_for_read"] = True
        else:
            row["read_status"] = "not_selected_smoke"


def inspect_file(
    path: Path,
    *,
    row: dict[str, Any],
    accumulator: InventoryAccumulator,
) -> None:
    relative_path = row["relative_path"]
    source = row["source"]
    dataset = row["dataset"]
    partition = partition_label(row["partition_year"], row["partition_month"])
    try:
        if path.stat().st_size == 0:
            row["read_status"] = "empty"
            accumulator.add_issue(
                severity="info",
                issue_type="empty_file",
                relative_path=relative_path,
                detail="Arquivo estruturado vazio.",
            )
            return
        suffix = row["suffix"]
        if suffix in {".jsonl", ".ndjson"}:
            records = iter_jsonl(path, row=row, accumulator=accumulator)
        elif suffix == ".json":
            records = iter_json(path, row=row, accumulator=accumulator)
        elif suffix == ".csv":
            records = iter_csv(path, row=row, accumulator=accumulator)
        elif suffix == ".parquet":
            records = iter_parquet(path, row=row, accumulator=accumulator)
        else:
            row["read_status"] = "unsupported_format"
            return

        for record_number, technical_kind, record in records:
            row["records_read"] += 1
            accumulator.observe_record(
                record,
                source=source,
                dataset=dataset,
                partition=partition,
                relative_path=relative_path,
                record_number=record_number,
                technical_record_kind=technical_kind,
            )
        row["read_status"] = (
            "read_with_rejections" if row["records_rejected"] else "read"
        )
    except Exception as exc:
        row["read_status"] = "read_error"
        row["error"] = f"{type(exc).__name__}: {exc}"
        accumulator.add_issue(
            severity="warning",
            issue_type="file_read_error",
            relative_path=relative_path,
            detail=row["error"],
        )


def iter_jsonl(
    path: Path,
    *,
    row: dict[str, Any],
    accumulator: InventoryAccumulator,
) -> Iterator[tuple[int, str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        record_number = 0
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record_number += 1
            row["records_observed"] += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                row["records_rejected"] += 1
                accumulator.add_issue(
                    severity="warning",
                    issue_type="invalid_json_line",
                    relative_path=row["relative_path"],
                    record_number=line_number,
                    detail=f"{exc.msg} (coluna {exc.colno})",
                )
                continue
            yield record_number, "jsonl_record", value


def iter_json(
    path: Path,
    *,
    row: dict[str, Any],
    accumulator: InventoryAccumulator,
) -> Iterator[tuple[int, str, Any]]:
    size_bytes = path.stat().st_size
    if size_bytes > accumulator.config.max_json_bytes:
        raise RuntimeError(
            "JSON não linear excede o limite de memória configurado: "
            f"{size_bytes} > {accumulator.config.max_json_bytes} bytes."
        )
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if isinstance(value, list):
        row["records_observed"] = len(value)
        for index, item in enumerate(value, start=1):
            yield index, "json_array_item", item
    else:
        row["records_observed"] = 1
        yield 1, "json_document", value


def iter_csv(
    path: Path,
    *,
    row: dict[str, Any],
    accumulator: InventoryAccumulator,
) -> Iterator[tuple[int, str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return
        for record_number, record in enumerate(reader, start=1):
            row["records_observed"] += 1
            if None in record:
                row["records_rejected"] += 1
                accumulator.add_issue(
                    severity="warning",
                    issue_type="invalid_csv_row",
                    relative_path=row["relative_path"],
                    record_number=record_number,
                    detail="Linha possui mais valores que o cabeçalho.",
                )
                continue
            yield record_number, "csv_row", dict(record)


def iter_parquet(
    path: Path,
    *,
    row: dict[str, Any],
    accumulator: InventoryAccumulator,
) -> Iterator[tuple[int, str, Any]]:
    del accumulator
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "pyarrow é necessário apenas quando houver Parquet no raw."
        ) from exc
    parquet = pq.ParquetFile(path)
    row["records_observed"] = parquet.metadata.num_rows
    record_number = 0
    for batch in parquet.iter_batches(batch_size=4_096):
        for record in batch.to_pylist():
            record_number += 1
            yield record_number, "parquet_row", record


def flatten_fields(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key in sorted(value, key=lambda item: str(item)):
            child_path = f"{path}.{escape_path_key(str(key))}"
            yield from flatten_fields(value[key], child_path)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from flatten_fields(item, f"{path}[]")


def build_field_rows(accumulator: InventoryAccumulator) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(accumulator.fields):
        source, dataset, record_type, field_path = key
        stats = accumulator.fields[key]
        universe = accumulator.group_records[(source, dataset, record_type)]
        cardinality, cardinality_method = stats.cardinality_result()
        string_length_values = stats.string_lengths
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "record_type": record_type,
                "field_path": field_path,
                "technical_types": "|".join(sorted(stats.technical_types)),
                "records_universe": universe,
                "field_absent": universe - stats.present,
                "present_null": stats.null,
                "present_empty": stats.empty,
                "present_filled": stats.filled,
                "fill_rate": (
                    format(stats.filled / universe, ".8f") if universe else "0"
                ),
                "cardinality": cardinality,
                "cardinality_method": cardinality_method,
                "string_length_min": (
                    min(string_length_values) if string_length_values else ""
                ),
                "string_length_median": (
                    counter_median(string_length_values) if string_length_values else ""
                ),
                "string_length_max": (
                    max(string_length_values) if string_length_values else ""
                ),
                "first_partition": min(stats.partitions) if stats.partitions else "",
                "last_partition": max(stats.partitions) if stats.partitions else "",
                "type_conflict": (
                    len(set(stats.technical_types).difference({"null"})) > 1
                ),
            }
        )
    return rows


def build_value_rows(accumulator: InventoryAccumulator) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(accumulator.fields):
        source, dataset, record_type, field_path = key
        stats = accumulator.fields[key]
        cardinality, method = stats.cardinality_result()
        if (
            method != "exact_scalar_values"
            or not isinstance(cardinality, int)
            or cardinality > accumulator.config.low_cardinality_limit
            or stats.value_frequencies is None
        ):
            continue
        ordered = sorted(
            stats.value_frequencies.items(),
            key=lambda item: (-item[1], item[0]),
        )
        for rank, (canonical, frequency) in enumerate(ordered, start=1):
            value_type, value_json = stats.value_representations[canonical]
            rows.append(
                {
                    "source": source,
                    "dataset": dataset,
                    "record_type": record_type,
                    "field_path": field_path,
                    "value_type": value_type,
                    "value_json": value_json,
                    "frequency": frequency,
                    "rank": rank,
                }
            )
    return rows


def build_sample_rows(accumulator: InventoryAccumulator) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(accumulator.fields):
        source, dataset, record_type, field_path = key
        stats = accumulator.fields[key]
        for sample_hash in sorted(stats.samples):
            value_type, _canonical, safe_value = stats.samples[sample_hash]
            rows.append(
                {
                    "source": source,
                    "dataset": dataset,
                    "record_type": record_type,
                    "field_path": field_path,
                    "sample_hash": sample_hash,
                    "value_type": value_type,
                    "value": safe_value,
                }
            )
    return rows


def write_success_outputs(
    *,
    config: InventoryConfig,
    started_at: str,
    fingerprint: str,
    file_rows: list[dict[str, Any]],
    field_rows: list[dict[str, Any]],
    value_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    counts: dict[str, int],
) -> dict[str, Path]:
    operation_root = config.operation_root
    paths = {
        "report": operation_root / "relatorio.md",
        "files": operation_root / "inventario_arquivos.csv",
        "fields": operation_root / "inventario_campos.csv",
        "values": operation_root / "valores_observados.csv",
        "samples": operation_root / "amostras_campos.jsonl",
        "issues": operation_root / "inconsistencias.csv",
        "manifest": operation_root / "manifest.json",
    }
    write_csv(paths["files"], strip_private_fields(file_rows), FILE_FIELDS)
    write_csv(paths["fields"], field_rows, FIELD_FIELDS)
    write_csv(paths["values"], value_rows, VALUE_FIELDS)
    write_jsonl(paths["samples"], sample_rows)
    write_csv(paths["issues"], issues, ISSUE_FIELDS)
    paths["report"].write_text(
        render_report(config=config, counts=counts, issues=issues),
        encoding="utf-8",
    )
    finished_at = utc_now()
    artifact_refs = [
        artifact_ref(path, operation_root=operation_root, rows=row_count)
        for path, row_count in [
            (paths["report"], None),
            (paths["files"], len(file_rows)),
            (paths["fields"], len(field_rows)),
            (paths["values"], len(value_rows)),
            (paths["samples"], len(sample_rows)),
            (paths["issues"], len(issues)),
        ]
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": "raw_metadata_inventory_v3",
        "operation_id": config.operation_id,
        "scope_mode": config.scope_mode,
        "execution_status": "succeeded",
        "scientific_gate": (
            "needs_review" if config.scope_mode == "full" else "not_evaluated"
        ),
        "started_at": started_at,
        "finished_at": finished_at,
        "spec_ref": SPEC_REF,
        "code_commit": config.code_commit,
        "input": {
            "raw_root": str(config.raw_root),
            "structural_fingerprint": fingerprint,
            "write_policy": "read_only",
        },
        "config": config_payload(config),
        "counts": counts,
        "outputs": artifact_refs,
        "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
        "errors": [],
        "next_action": (
            "Revisar o smoke; não executar o universo completo sem aprovação."
            if config.scope_mode == "smoke"
            else "Revisar relatorio.md e os três catálogos antes de G01."
        ),
    }
    write_json(paths["manifest"], manifest)
    return paths


def write_failure_outputs(
    *,
    config: InventoryConfig,
    started_at: str,
    fingerprint: str,
    file_rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    error: Exception,
) -> None:
    operation_root = config.operation_root
    fatal_issue = {
        "severity": "error",
        "issue_type": "fatal_inventory_error",
        "relative_path": "",
        "record_number": "",
        "field_path": "",
        "detail": f"{type(error).__name__}: {error}",
    }
    all_issues = sorted_issues([*issues, fatal_issue])
    write_csv(operation_root / "inconsistencias.csv", all_issues, ISSUE_FIELDS)
    if file_rows:
        write_csv(
            operation_root / "inventario_arquivos.csv",
            strip_private_fields(file_rows),
            FILE_FIELDS,
        )
    (operation_root / "relatorio.md").write_text(
        "# Inventário de metadados raw v3\n\n"
        "**Estado da execução:** failed\n\n"
        f"A execução foi interrompida: `{type(error).__name__}: {error}`\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": "raw_metadata_inventory_v3",
        "operation_id": config.operation_id,
        "scope_mode": config.scope_mode,
        "execution_status": "failed",
        "scientific_gate": "not_evaluated",
        "started_at": started_at,
        "finished_at": utc_now(),
        "spec_ref": SPEC_REF,
        "code_commit": config.code_commit,
        "input": {
            "raw_root": str(config.raw_root),
            "structural_fingerprint": fingerprint,
            "write_policy": "read_only",
        },
        "config": config_payload(config),
        "counts": {},
        "outputs": [],
        "warnings": sum(1 for issue in all_issues if issue["severity"] == "warning"),
        "errors": [fatal_issue["detail"]],
        "next_action": "Corrigir a falha; não aprovar G01.",
    }
    write_json(operation_root / "manifest.json", manifest)


def render_report(
    *,
    config: InventoryConfig,
    counts: Mapping[str, int],
    issues: Sequence[Mapping[str, Any]],
) -> str:
    warnings = sum(1 for issue in issues if issue["severity"] == "warning")
    infos = sum(1 for issue in issues if issue["severity"] == "info")
    gate = "needs_review" if config.scope_mode == "full" else "not_evaluated"
    scope_note = (
        "Este smoke catalogou toda a árvore, mas abriu somente uma amostra "
        "determinística dos arquivos estruturados."
        if config.scope_mode == "smoke"
        else "Todos os arquivos estruturados suportados foram selecionados para leitura."
    )
    return f"""# Inventário de metadados raw v3

## Estado

| Campo | Valor |
|---|---|
| operação | `{config.operation_id}` |
| escopo | `{config.scope_mode}` |
| execução | **succeeded** |
| gate científico | **{gate}** |
| raiz | `{config.raw_root}` |

{scope_note}

## Resultado

| Contagem | Valor |
|---|---:|
| itens catalogados | {counts["items_cataloged"]} |
| arquivos | {counts["files"]} |
| diretórios | {counts["directories"]} |
| arquivos estruturados suportados | {counts["supported_structured_files"]} |
| arquivos selecionados para leitura | {counts["selected_files"]} |
| registros observados | {counts["records_observed"]} |
| registros lidos | {counts["records_read"]} |
| registros rejeitados | {counts["records_rejected"]} |
| grupos fonte × dataset × record_type | {counts["record_groups"]} |
| caminhos de campo | {counts["field_paths"]} |
| valores de baixa cardinalidade | {counts["low_cardinality_values"]} |
| inconsistências warning | {warnings} |
| inconsistências info | {infos} |

## Artefatos

- `inventario_arquivos.csv`: reconciliação integral da árvore.
- `inventario_campos.csv`: presença, estados, tipos e cardinalidade por campo.
- `valores_observados.csv`: frequências somente para baixa cardinalidade.
- `amostras_campos.jsonl`: amostras determinísticas e limitadas.
- `inconsistencias.csv`: falhas de leitura e conflitos estruturais.
- `manifest.json`: configuração efetiva, proveniência e contagens.

## Próxima ação

{
        "Revise o smoke e sua cobertura. Não execute o inventário completo ainda."
        if config.scope_mode == "smoke"
        else (
            "Revise este relatório, inventario_campos.csv e valores_observados.csv. "
            "A execução permanece em needs_review até a decisão humana de G01."
        )
    }
"""


def build_counts(
    *,
    file_rows: Sequence[Mapping[str, Any]],
    field_rows: Sequence[Mapping[str, Any]],
    value_rows: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    files = [row for row in file_rows if row["item_type"] == "file"]
    return {
        "items_cataloged": len(file_rows),
        "files": len(files),
        "directories": sum(1 for row in file_rows if row["item_type"] == "directory"),
        "supported_structured_files": sum(
            1 for row in files if row["suffix"] in SUPPORTED_SUFFIXES
        ),
        "selected_files": sum(bool(row["selected_for_read"]) for row in files),
        "records_observed": sum(int(row["records_observed"] or 0) for row in files),
        "records_read": sum(int(row["records_read"] or 0) for row in files),
        "records_rejected": sum(int(row["records_rejected"] or 0) for row in files),
        "record_groups": len(
            {(row["source"], row["dataset"], row["record_type"]) for row in field_rows}
        ),
        "field_paths": len(field_rows),
        "low_cardinality_values": len(value_rows),
        "issues": len(issues),
    }


def config_payload(config: InventoryConfig) -> dict[str, Any]:
    return {
        "low_cardinality_limit": config.low_cardinality_limit,
        "sample_size": config.sample_size,
        "sample_seed": config.sample_seed,
        "max_copy_length": config.max_copy_length,
        "max_json_bytes": config.max_json_bytes,
        "cardinality_policy": {
            "exact_limit": config.cardinality_exact_limit,
            "estimator": "kmv_sha256",
            "kmv_size": config.cardinality_kmv_size,
        },
        "max_files_per_group": config.max_files_per_group,
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "path_field_syntax": "jsonpath_like_root_dollar_array_wildcard",
        "python_version": sys.version.split()[0],
    }


def declared_record_type(record: Any, technical_kind: str) -> str:
    if isinstance(record, Mapping):
        value = record.get("record_type")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "__missing__"
    return f"__{technical_kind}__"


def technical_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, time):
        return "time"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return type(value).__name__


def value_state(value: Any) -> str:
    if value is None:
        return "null"
    if value == "":
        return "empty"
    if isinstance(value, (list, tuple, Mapping)) and len(value) == 0:
        return "empty"
    return "filled"


def canonical_value(value: Any) -> str:
    normalized = canonical_json_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def canonical_token(value: Any, *, max_copy_length: int) -> str:
    if isinstance(value, str) and len(value) > max_copy_length:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"long_string:{len(value)}:{digest}"
    if isinstance(value, bytes):
        digest = hashlib.sha256(value).hexdigest()
        return f"bytes:{len(value)}:{digest}"
    serialized = canonical_value(value)
    if len(serialized) > max_copy_length:
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"serialized:{len(serialized)}:{digest}"
    return serialized


def canonical_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): canonical_json_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_json_value(item) for item in value]
    if isinstance(value, bytes):
        return {"__bytes_sha256__": hashlib.sha256(value).hexdigest()}
    if isinstance(value, (datetime, date, time, Decimal)):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return str(value)
    return value


def safe_sample_value(value: Any, *, max_copy_length: int) -> Any:
    if isinstance(value, str):
        if len(value) <= max_copy_length:
            return value
        return {
            "kind": "redacted_long_string",
            "length": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        }
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, Mapping):
        return {
            "kind": "object",
            "size": len(value),
            "keys": sorted(str(key) for key in value)[:25],
        }
    if isinstance(value, (list, tuple)):
        return {"kind": "array", "size": len(value)}
    if isinstance(value, (datetime, date, time, Decimal)):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return str(value)
    return value


def counter_median(lengths: Counter[int]) -> float | int:
    total = sum(lengths.values())
    if total == 0:
        raise ValueError("Não existe mediana de contador vazio.")
    left_position = (total - 1) // 2
    right_position = total // 2
    cumulative = 0
    left_value: int | None = None
    right_value: int | None = None
    for value in sorted(lengths):
        next_cumulative = cumulative + lengths[value]
        if left_value is None and left_position < next_cumulative:
            left_value = value
        if right_position < next_cumulative:
            right_value = value
            break
        cumulative = next_cumulative
    assert left_value is not None and right_value is not None
    median = statistics.mean([left_value, right_value])
    return int(median) if median.is_integer() else median


def structural_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        kind = "d" if path.is_dir() else "f" if path.is_file() else "o"
        size = stat.st_size if path.is_file() else 0
        digest.update(
            f"{kind}\0{relative}\0{size}\0{stat.st_mtime_ns}\n".encode("utf-8")
        )
    return digest.hexdigest()


def artifact_ref(
    path: Path,
    *,
    operation_root: Path,
    rows: int | None,
) -> dict[str, Any]:
    return {
        "name": path.name,
        "relative_path": path.relative_to(operation_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": rows,
    }


def sorted_issues(issues: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(issue)
        for issue in sorted(
            issues,
            key=lambda issue: (
                str(issue.get("severity", "")),
                str(issue.get("issue_type", "")),
                str(issue.get("relative_path", "")),
                str(issue.get("record_number", "")),
                str(issue.get("field_path", "")),
            ),
        )
    ]


def strip_private_fields(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in rows
    ]


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                + "\n"
            )


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def partition_value(parts: Sequence[str], name: str) -> str:
    prefix = f"{name}="
    for part in parts:
        if part.startswith(prefix):
            return part.removeprefix(prefix)
    return ""


def partition_label(year: str, month: str) -> str:
    if year and month:
        return f"{year}-{month}"
    return year


def format_name(suffix: str) -> str:
    return {
        ".csv": "csv",
        ".json": "json",
        ".jsonl": "jsonl",
        ".ndjson": "jsonl",
        ".parquet": "parquet",
    }.get(suffix, "")


def spread_sample(
    rows: Sequence[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit >= len(rows):
        return list(rows)
    if limit == 1:
        return [rows[0]]
    indexes = {
        round(position * (len(rows) - 1) / (limit - 1)) for position in range(limit)
    }
    return [rows[index] for index in sorted(indexes)]


def escape_path_key(value: str) -> str:
    return value.replace("\\", "\\\\").replace(".", "\\.")


def mounted_drive_root(path: Path) -> Path | None:
    parts = path.parts
    if "MyDrive" not in parts:
        return None
    index = parts.index("MyDrive")
    return Path(*parts[: index + 1])


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _hash_int(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest(), "big")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventaria metadados estruturados do raw sem alterá-lo."
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-base", type=Path, default=DEFAULT_OUTPUT_BASE)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--low-cardinality-limit", type=int, default=100)
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--sample-seed", default="falando-nela-v3")
    parser.add_argument("--max-copy-length", type=int, default=200)
    parser.add_argument("--max-json-bytes", type=int, default=DEFAULT_MAX_JSON_BYTES)
    parser.add_argument("--cardinality-exact-limit", type=int, default=10_000)
    parser.add_argument("--cardinality-kmv-size", type=int, default=1_024)
    parser.add_argument("--max-files-per-group", type=int)
    parser.add_argument("--progress-every-files", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = InventoryConfig(
        raw_root=args.raw_root,
        output_base=args.output_base,
        operation_id=args.operation_id,
        code_commit=args.code_commit,
        low_cardinality_limit=args.low_cardinality_limit,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        max_copy_length=args.max_copy_length,
        max_json_bytes=args.max_json_bytes,
        cardinality_exact_limit=args.cardinality_exact_limit,
        cardinality_kmv_size=args.cardinality_kmv_size,
        max_files_per_group=args.max_files_per_group,
        progress_every_files=args.progress_every_files,
    )
    result = run_inventory(config)
    print(result["paths"]["report"])
    print(
        "execution_status:",
        result["manifest"]["execution_status"],
        "| scientific_gate:",
        result["manifest"]["scientific_gate"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
