from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from coleta.common.config import PROD_DATA_ROOT_ENV, utc_now_iso
from processamento.normalizacao import DATASET_NAME, DATASET_VERSION, PROCESSED_FIELDS

JSON_SERIALIZED_FIELDS = {"fontes"}
INT_FIELDS = {"texto_tamanho"}
BOOL_FIELDS = {"vencido"}
DEFAULT_BATCH_SIZE = 5_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unifica JSONLs processed/textos_parlamentares/v1 em Parquets por source/dataset."
    )
    parser.add_argument(
        "--profile",
        choices=["samples-local", "colab"],
        default=None,
        help="Preenche caminhos padrao para samples locais ou Google Drive no Colab.",
    )
    parser.add_argument("--data-root", default=None, help="Raiz de dados usada no perfil colab.")
    parser.add_argument("--input-root", default=None, help="Raiz dos JSONLs processed v1.")
    parser.add_argument("--output-root", default=None, help="Diretorio dos Parquets gerados.")
    parser.add_argument("--manifest-path", default=None, help="Caminho do manifest da conversao.")
    parser.add_argument("--run-id", default=None, help="Identificador da conversao Parquet.")
    parser.add_argument("--schema-path", default=None, help="Schema JSON v1 usado para ordenar colunas.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    input_root, output_root, manifest_path, run_id = resolve_parquet_paths(args, env=os.environ)
    manifest = write_parquet_by_dataset(
        input_root=input_root,
        output_root=output_root,
        manifest_path=manifest_path,
        run_id=run_id,
        overwrite=args.overwrite,
        schema_path=Path(args.schema_path).expanduser() if args.schema_path else None,
        batch_size=args.batch_size,
    )
    print(manifest["manifest_path"])


def resolve_parquet_paths(
    args: argparse.Namespace,
    *,
    env: os._Environ[str] | dict[str, str],
) -> tuple[Path, Path, Path, str | None]:
    profile = args.profile
    run_id = args.run_id

    if profile == "samples-local":
        input_root = Path(args.input_root or f"data/samples/{DATASET_NAME}/{DATASET_VERSION}")
        output_root = Path(args.output_root) if args.output_root else input_root / "parquet"
        manifest_path = Path(args.manifest_path) if args.manifest_path else output_root / "manifest.json"
        return input_root, output_root, manifest_path, run_id

    if profile == "colab":
        data_root_value = args.data_root or env.get(PROD_DATA_ROOT_ENV)
        if not data_root_value:
            raise ValueError(f"--profile colab exige --data-root ou {PROD_DATA_ROOT_ENV}")
        data_root = Path(data_root_value).expanduser()
        input_root = (
            Path(args.input_root).expanduser()
            if args.input_root
            else data_root / "processed" / DATASET_NAME / DATASET_VERSION
        )
        output_root = Path(args.output_root).expanduser() if args.output_root else input_root / "parquet"
        if args.manifest_path:
            manifest_path = Path(args.manifest_path).expanduser()
            manifest_stem = run_id
        else:
            manifest_stem = run_id or f"parquet-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
            if not manifest_stem.endswith("-parquet"):
                manifest_stem = f"{manifest_stem}-parquet"
            manifest_path = data_root / "processed" / "manifests" / f"{manifest_stem}.json"
        conversion_run_id = (
            run_id if run_id and run_id.endswith("-parquet") else f"{run_id}-parquet" if run_id else manifest_stem
        )
        return input_root, output_root, manifest_path, conversion_run_id

    if not args.input_root:
        raise ValueError("--input-root e obrigatorio sem --profile")
    input_root = Path(args.input_root).expanduser()
    output_root = Path(args.output_root).expanduser() if args.output_root else input_root / "parquet"
    manifest_path = Path(args.manifest_path).expanduser() if args.manifest_path else output_root / "manifest.json"
    return input_root, output_root, manifest_path, run_id


def write_parquet_by_dataset(
    *,
    input_root: Path,
    output_root: Path | None = None,
    manifest_path: Path | None = None,
    run_id: str | None = None,
    overwrite: bool = False,
    schema_path: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    input_root = input_root.expanduser()
    if not input_root.exists():
        raise FileNotFoundError(f"Raiz de entrada nao encontrada: {input_root}")
    if batch_size <= 0:
        raise ValueError("batch_size deve ser positivo")

    output_root = (output_root or input_root / "parquet").expanduser()
    manifest_path = (manifest_path or output_root / "manifest.json").expanduser()
    run_id = run_id or f"parquet-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
    schema_path = schema_path or default_schema_path()
    schema_fields = load_schema_fields(schema_path)
    arrow_schema = build_arrow_schema(schema_fields)

    if overwrite and output_root.exists():
        for path in output_root.glob("*.parquet"):
            path.unlink()
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(f"Manifest Parquet ja existe: {manifest_path}; use --overwrite para substituir.")

    jsonl_paths = list(iter_processed_jsonl_paths(input_root, output_root=output_root))
    writers: dict[tuple[str, str], _DatasetParquetWriter] = {}
    seen_text_ids: set[str] = set()
    input_files: set[str] = set()
    input_record_counts: Counter[str] = Counter()
    output_record_counts: Counter[str] = Counter()
    skipped_counts: Counter[str] = Counter()
    input_records = 0
    output_records = 0

    try:
        for jsonl_path in jsonl_paths:
            relative_input_path = _relative_path(jsonl_path, input_root)
            input_files.add(relative_input_path)
            for row in iter_jsonl_records(jsonl_path):
                input_records += 1
                dataset_version = row.get("dataset_version")
                if dataset_version != DATASET_VERSION:
                    skipped_counts["dataset_version_not_v1"] += 1
                    continue

                source = _string(row.get("source"))
                dataset = _string(row.get("dataset"))
                texto_id = _string(row.get("texto_id"))
                if not source or not dataset:
                    skipped_counts["missing_source_or_dataset"] += 1
                    continue
                if not texto_id:
                    skipped_counts["missing_texto_id"] += 1
                    continue

                key = (source, dataset)
                input_record_counts[_base_key(source, dataset)] += 1
                if texto_id in seen_text_ids:
                    skipped_counts["duplicate_texto_id"] += 1
                    continue

                writer = writers.get(key)
                if writer is None:
                    writer = _DatasetParquetWriter(
                        output_root=output_root,
                        source=source,
                        dataset=dataset,
                        schema=arrow_schema,
                        schema_fields=schema_fields,
                        overwrite=overwrite,
                        batch_size=batch_size,
                    )
                    writers[key] = writer

                writer.write(row)
                seen_text_ids.add(texto_id)
                output_record_counts[_base_key(source, dataset)] += 1
                output_records += 1
    finally:
        for writer in writers.values():
            writer.close()

    output_files = sorted(writer.output_path.as_posix() for writer in writers.values() if writer.records_written > 0)
    manifest = {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "created_at": utc_now_iso(),
        "input_root": str(input_root),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "input_records": input_records,
        "output_records": output_records,
        "input_files": sorted(input_files),
        "input_file_count": len(input_files),
        "output_files": output_files,
        "output_file_count": len(output_files),
        "input_record_counts": dict(sorted(input_record_counts.items())),
        "output_record_counts": dict(sorted(output_record_counts.items())),
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "schema": str(schema_path),
        "schema_fields": schema_fields,
        "json_serialized_fields": sorted(JSON_SERIALIZED_FIELDS),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "schemas" / f"processed_{DATASET_NAME}_{DATASET_VERSION}.schema.json"


def load_schema_fields(schema_path: Path) -> list[str]:
    fields: list[str] = []
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            fields.extend(str(field) for field in properties.keys())
    if not fields:
        fields.extend(PROCESSED_FIELDS)
    for field in PROCESSED_FIELDS:
        if field not in fields:
            fields.append(field)
    return fields


def build_arrow_schema(schema_fields: Iterable[str]) -> pa.Schema:
    fields = [pa.field(field, _arrow_type(field)) for field in schema_fields]
    metadata = {
        b"dataset": DATASET_NAME.encode("utf-8"),
        b"dataset_version": DATASET_VERSION.encode("utf-8"),
        b"json_serialized_fields": ",".join(sorted(JSON_SERIALIZED_FIELDS)).encode("utf-8"),
    }
    return pa.schema(fields, metadata=metadata)


def iter_processed_jsonl_paths(input_root: Path, *, output_root: Path | None = None) -> Iterator[Path]:
    output_root_resolved = output_root.resolve(strict=False) if output_root else None
    paths = _sort_newest_first(input_root.rglob("*.jsonl"))
    for path in paths:
        if _relative_path_has_part(path, input_root, "parquet"):
            continue
        if output_root_resolved is not None and _is_relative_to(path.resolve(strict=False), output_root_resolved):
            continue
        yield path


def iter_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
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


class _DatasetParquetWriter:
    def __init__(
        self,
        *,
        output_root: Path,
        source: str,
        dataset: str,
        schema: pa.Schema,
        schema_fields: list[str],
        overwrite: bool,
        batch_size: int,
    ) -> None:
        self.output_path = output_root / f"{source}__{dataset}.parquet"
        self.schema = schema
        self.schema_fields = schema_fields
        self.overwrite = overwrite
        self.batch_size = batch_size
        self.records_written = 0
        self._writer: pq.ParquetWriter | None = None
        self._buffer: list[dict[str, Any]] = []

    def write(self, row: dict[str, Any]) -> None:
        self._buffer.append(_coerce_record(row, self.schema_fields))
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._ensure_writer()
        table = pa.Table.from_pylist(self._buffer, schema=self.schema)
        assert self._writer is not None
        self._writer.write_table(table)
        self.records_written += table.num_rows
        self._buffer.clear()

    def close(self) -> None:
        self.flush()
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def _ensure_writer(self) -> None:
        if self._writer is not None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            if not self.overwrite:
                raise FileExistsError(f"Parquet ja existe: {self.output_path}; use --overwrite para substituir.")
            self.output_path.unlink()
        self._writer = pq.ParquetWriter(self.output_path, self.schema, compression="zstd")


def _coerce_record(row: dict[str, Any], schema_fields: list[str]) -> dict[str, Any]:
    return {field: _coerce_value(field, row.get(field)) for field in schema_fields}


def _coerce_value(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in JSON_SERIALIZED_FIELDS:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if field in INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if field in BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "sim", "yes"}:
                return True
            if normalized in {"false", "0", "nao", "não", "no"}:
                return False
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _arrow_type(field: str) -> pa.DataType:
    if field in INT_FIELDS:
        return pa.int64()
    if field in BOOL_FIELDS:
        return pa.bool_()
    return pa.string()


def _base_key(source: str, dataset: str) -> str:
    return f"{source}/{dataset}"


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _sort_newest_first(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (_mtime(path), path.as_posix()), reverse=True)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _relative_path_has_part(path: Path, root: Path, name: str) -> bool:
    try:
        return name in path.relative_to(root).parts
    except ValueError:
        return name in path.parts


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    main()
