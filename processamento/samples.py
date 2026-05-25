from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from coleta.common.config import PROD_DATA_ROOT_ENV, utc_now_iso
from processamento.normalizacao import DATASET_NAME, DATASET_VERSION, PROCESSED_FIELDS

DEFAULT_SAMPLE_RATE = 0.01
DEFAULT_MIN_PER_GROUP = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera ZIPs de amostras dos JSONLs processed/textos_parlamentares/v1."
    )
    parser.add_argument(
        "--profile",
        choices=["colab", "samples-local"],
        default=None,
        help="Preenche caminhos padrao para Google Drive no Colab ou samples locais.",
    )
    parser.add_argument("--data-root", default=None, help="Raiz de dados usada no perfil colab.")
    parser.add_argument("--input-root", default=None, help="Raiz dos JSONLs processed v1.")
    parser.add_argument("--output-root", default=None, help="Diretorio dos ZIPs e manifest gerados.")
    parser.add_argument("--run-id", default=None, help="Identificador da geracao das amostras.")
    parser.add_argument("--sample-rate", type=float, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--min-per-group", type=int, default=DEFAULT_MIN_PER_GROUP)
    parser.add_argument("--include-parquet", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    input_root, output_root, run_id = resolve_sample_paths(args, env=os.environ)
    manifest = write_sample_zips(
        input_root=input_root,
        output_root=output_root,
        run_id=run_id,
        sample_rate=args.sample_rate,
        min_per_group=args.min_per_group,
        include_parquet=args.include_parquet,
        overwrite=args.overwrite,
    )
    print(manifest["manifest_path"])


def resolve_sample_paths(
    args: argparse.Namespace,
    *,
    env: os._Environ[str] | dict[str, str],
) -> tuple[Path, Path, str]:
    run_id = args.run_id or f"samples-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"

    if args.profile == "colab":
        data_root_value = args.data_root or env.get(PROD_DATA_ROOT_ENV)
        if not data_root_value:
            raise ValueError(f"--profile colab exige --data-root ou {PROD_DATA_ROOT_ENV}")
        data_root = Path(data_root_value).expanduser()
        input_root = (
            Path(args.input_root).expanduser()
            if args.input_root
            else data_root / "processed" / DATASET_NAME / DATASET_VERSION
        )
        output_root = (
            Path(args.output_root).expanduser()
            if args.output_root
            else data_root / "processed" / "downloads" / run_id
        )
        return input_root, output_root, run_id

    if args.profile == "samples-local":
        input_root = Path(args.input_root or f"data/samples/{DATASET_NAME}/{DATASET_VERSION}").expanduser()
        output_root = (
            Path(args.output_root).expanduser() if args.output_root else input_root / "downloads" / run_id
        )
        return input_root, output_root, run_id

    if not args.input_root or not args.output_root:
        raise ValueError("--input-root e --output-root sao obrigatorios sem --profile")
    return Path(args.input_root).expanduser(), Path(args.output_root).expanduser(), run_id


def write_sample_zips(
    *,
    input_root: Path,
    output_root: Path,
    run_id: str | None = None,
    sample_rate: float = DEFAULT_SAMPLE_RATE,
    min_per_group: int = DEFAULT_MIN_PER_GROUP,
    include_parquet: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    input_root = input_root.expanduser()
    output_root = output_root.expanduser()
    run_id = run_id or f"samples-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
    if not input_root.exists():
        raise FileNotFoundError(f"Raiz de entrada nao encontrada: {input_root}")
    if not 0 < sample_rate <= 1:
        raise ValueError("sample_rate deve estar entre 0 e 1")
    if min_per_group <= 0:
        raise ValueError("min_per_group deve ser positivo")

    manifest_path = output_root / "manifest.json"
    if output_root.exists() and not overwrite and _generated_outputs(output_root):
        raise FileExistsError(f"Saidas de amostra ja existem em {output_root}; use --overwrite para substituir.")
    if overwrite and output_root.exists():
        for path in _generated_outputs(output_root):
            path.unlink()

    records_by_stratum: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_text_ids: set[str] = set()
    input_files: set[str] = set()
    input_records = 0
    skipped_counts: Counter[str] = Counter()
    input_record_counts: Counter[str] = Counter()

    for jsonl_path in iter_processed_jsonl_paths(input_root, output_root=output_root):
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
            documento_tipo = _string(row.get("documento_tipo"))
            ano = _string(row.get("ano"))
            mes = _string(row.get("mes"))
            texto_id = _string(row.get("texto_id"))
            if not source or not dataset or not documento_tipo or not ano or not mes:
                skipped_counts["missing_group_fields"] += 1
                continue
            if not texto_id:
                skipped_counts["missing_texto_id"] += 1
                continue
            input_record_counts[_zip_group_key(source, dataset, documento_tipo)] += 1
            if texto_id in seen_text_ids:
                skipped_counts["duplicate_texto_id"] += 1
                continue

            seen_text_ids.add(texto_id)
            records_by_stratum[(source, dataset, documento_tipo, ano)].append(_processed_v1_record(row))

    sampled_records: list[dict[str, Any]] = []
    stratum_counts: dict[str, dict[str, int]] = {}
    for stratum, records in sorted(records_by_stratum.items()):
        selected = _sample_stratum(records, sample_rate=sample_rate, min_per_group=min_per_group)
        sampled_records.extend(selected)
        stratum_key = "/".join(stratum)
        stratum_counts[stratum_key] = {"input_records": len(records), "sample_records": len(selected)}

    records_by_zip: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in sampled_records:
        source = _required_string(record, "source")
        dataset = _required_string(record, "dataset")
        documento_tipo = _required_string(record, "documento_tipo")
        records_by_zip[(source, dataset, documento_tipo)].append(record)

    output_root.mkdir(parents=True, exist_ok=True)
    output_files: list[str] = []
    output_record_counts: Counter[str] = Counter()
    for zip_group, records in sorted(records_by_zip.items()):
        zip_path = output_root / f"{_zip_group_key(*zip_group)}.zip"
        write_group_zip(
            zip_path=zip_path,
            input_root=input_root,
            zip_group=zip_group,
            records=records,
            include_parquet=include_parquet,
        )
        output_files.append(zip_path.as_posix())
        output_record_counts[_zip_group_key(*zip_group)] = len(records)

    manifest = {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "created_at": utc_now_iso(),
        "input_root": str(input_root),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "sample_rate": sample_rate,
        "min_per_group": min_per_group,
        "include_parquet": include_parquet,
        "input_records": input_records,
        "deduplicated_records": len(seen_text_ids),
        "sample_records": len(sampled_records),
        "input_files": sorted(input_files),
        "input_file_count": len(input_files),
        "output_files": output_files,
        "output_file_count": len(output_files),
        "input_record_counts": dict(sorted(input_record_counts.items())),
        "output_record_counts": dict(sorted(output_record_counts.items())),
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "schema_fields": PROCESSED_FIELDS,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_group_zip(
    *,
    zip_path: Path,
    input_root: Path,
    zip_group: tuple[str, str, str],
    records: Iterable[dict[str, Any]],
    include_parquet: bool,
) -> None:
    source, dataset, documento_tipo = zip_group
    group_name = _zip_group_key(source, dataset, documento_tipo)
    records_by_month: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_month[(_required_string(record, "ano"), _required_string(record, "mes"))].append(record)

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for (ano, mes), month_records in sorted(records_by_month.items()):
            month_records = sorted(month_records, key=lambda row: _required_string(row, "texto_id"))
            name = f"{group_name}/{group_name}__ano={_safe_part(ano)}__mes={_safe_part(mes)}.jsonl"
            data = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in month_records)
            archive.writestr(name, data)

        if include_parquet:
            parquet_path = input_root / "parquet" / f"{_safe_part(source)}__{_safe_part(dataset)}.parquet"
            if parquet_path.exists():
                archive.write(parquet_path, f"parquet/{parquet_path.name}")


def iter_processed_jsonl_paths(input_root: Path, *, output_root: Path | None = None) -> Iterator[Path]:
    output_root_resolved = output_root.resolve(strict=False) if output_root else None
    paths = sorted(input_root.rglob("*.jsonl"), key=lambda path: (_mtime(path), path.as_posix()), reverse=True)
    for path in paths:
        if _relative_path_has_part(path, input_root, "parquet"):
            continue
        if _relative_path_has_part(path, input_root, "downloads"):
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


def _sample_stratum(
    records: list[dict[str, Any]],
    *,
    sample_rate: float,
    min_per_group: int,
) -> list[dict[str, Any]]:
    if not records:
        return []
    sample_size = min(len(records), max(min_per_group, math.ceil(len(records) * sample_rate)))
    ranked = sorted(records, key=lambda row: (_sample_key(row), _required_string(row, "texto_id")))
    return ranked[:sample_size]


def _sample_key(record: dict[str, Any]) -> str:
    texto_id = _required_string(record, "texto_id")
    raw_checksum = _string(record.get("raw_checksum")) or ""
    return hashlib.sha1(f"{texto_id}|{raw_checksum}".encode("utf-8")).hexdigest()


def _processed_v1_record(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in PROCESSED_FIELDS}


def _generated_outputs(output_root: Path) -> list[Path]:
    outputs = list(output_root.glob("*.zip"))
    manifest_path = output_root / "manifest.json"
    if manifest_path.exists():
        outputs.append(manifest_path)
    return outputs


def _zip_group_key(source: str, dataset: str, documento_tipo: str) -> str:
    return "__".join(_safe_part(part) for part in (source, dataset, documento_tipo))


def _safe_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.=-]+", "_", value.strip())
    return normalized.strip("_") or "sem_valor"


def _required_string(record: dict[str, Any], field: str) -> str:
    value = _string(record.get(field))
    if value is None:
        raise ValueError(f"Campo obrigatorio ausente no registro de amostra: {field}")
    return value


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


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
