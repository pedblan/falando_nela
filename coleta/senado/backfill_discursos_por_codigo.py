from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Sequence

from coleta.common.cli import build_parser, runtime_config_from_namespace
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary
from coleta.senado.auditoria_discursos_historicos import HOUSE_DATASETS
from coleta.senado.discursos import (
    BASE_URL,
    build_fontes,
    fetch_pronunciamento_texto,
    should_enqueue_transcription,
)


HOUSE_PREFIX = {"SF": "SF", "CN": "CN"}


def build_backfill_parser() -> argparse.ArgumentParser:
    parser = build_parser(
        "Recupera pronunciamentos ausentes a partir da auditoria por CodigoParlamentar."
    )
    parser.add_argument("--missing-path", required=True)
    parser.add_argument("--house", choices=sorted(HOUSE_DATASETS), required=True)
    return parser


def collect(argv: Sequence[str] | None = None) -> Path:
    parser = build_backfill_parser()
    args = parser.parse_args(argv)
    runtime = runtime_config_from_namespace(parser, args)
    missing_path = Path(args.missing_path).expanduser()
    if not missing_path.is_file():
        parser.error(f"--missing-path ausente: {missing_path}")
    house = str(args.house)
    dataset = HOUSE_DATASETS[house]
    population = load_population(
        missing_path,
        house=house,
        dataset=dataset,
        start=runtime.data_inicio,
        end=runtime.data_fim,
    )
    if runtime.sample:
        limit = runtime.sample_limit or 5
        population = population[:limit]

    years = {record["data"][:4] for record in population}
    run = CollectionRun(
        runtime.output_dir,
        source="senado",
        dataset=dataset,
        run_id=runtime.run_id,
        resume=runtime.resume,
        existing_record_years=years,
    )
    existing_codes = existing_pronunciamento_codes(
        runtime.output_dir,
        dataset=dataset,
        expected_codes={record["codigo_pronunciamento"] for record in population},
        run=run,
    )
    by_partition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in population:
        by_partition[record["data"][:7]].append(record)

    status = "completed"
    errors = 0
    stats: Counter[str] = Counter()
    population_source_id = (
        f"{house}:senator-endpoint-backfill-population:{len(population)}:"
        f"{runtime.data_inicio.isoformat()}:{runtime.data_fim.isoformat()}"
    )
    run.write_record(
        partition="metadata",
        source_id=population_source_id,
        request={"method": "READ_JSONL", "path": str(missing_path), "params": {}},
        response={"status_code": 200, "source": "audit_artifact"},
        periodo={
            "data_inicio": runtime.data_inicio.isoformat(),
            "data_fim": runtime.data_fim.isoformat(),
        },
        payload={
            "strategy": "senator-endpoint-missing-ids-v1",
            "house": house,
            "dataset": dataset,
            "missing_path": str(missing_path),
            "population": len(population),
            "existing_before_backfill": len(existing_codes),
            "codes": [record["codigo_pronunciamento"] for record in population],
        },
        record_type="senator_endpoint_backfill_population",
    )

    try:
        with OpenDataClient(BASE_URL, min_interval_seconds=0.11) as client:
            for partition, records in sorted(by_partition.items()):
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    stats["partitions_skipped"] += 1
                    continue
                partition_errors = 0
                run.log(
                    "partition_started",
                    partition=partition,
                    population=len(records),
                    existing=sum(
                        record["codigo_pronunciamento"] in existing_codes for record in records
                    ),
                )
                for index, record in enumerate(records, start=1):
                    code = record["codigo_pronunciamento"]
                    source_id = f"{HOUSE_PREFIX[house]}:pronunciamento:{code}"
                    if code in existing_codes:
                        stats["existing_raw_skipped"] += 1
                        continue
                    if run.has_record(source_id=source_id, record_type="pronunciamento_texto"):
                        stats["resume_skipped"] += 1
                        continue
                    item = missing_record_to_item(record, missing_path=missing_path)
                    try:
                        payload, request, response = fetch_pronunciamento_texto(client, item)
                    except Exception as exc:
                        partition_errors += 1
                        errors += 1
                        run.log(
                            "pronunciamento_failed",
                            partition=partition,
                            codigo_pronunciamento=code,
                            error=error_summary(exc),
                        )
                        continue
                    written = run.write_record(
                        partition=partition,
                        source_id=source_id,
                        request=request,
                        response=response,
                        periodo={"data_inicio": record["data"], "data_fim": record["data"]},
                        payload=payload,
                        record_type="pronunciamento_texto",
                    )
                    stats["pronunciamentos_written"] += int(written)
                    if written and should_enqueue_transcription(payload):
                        queue_written = run.write_record(
                            partition="transcription_queue",
                            source_id=source_id,
                            request=request,
                            response=response,
                            periodo={"data_inicio": record["data"], "data_fim": record["data"]},
                            payload=payload,
                            record_type="transcription_queue",
                        )
                        stats["transcription_queued"] += int(queue_written)
                    if index == 1 or index % 25 == 0 or index == len(records):
                        run.log(
                            "backfill_progress",
                            partition=partition,
                            processed=index,
                            total=len(records),
                            written=stats["pronunciamentos_written"],
                            errors=errors,
                        )
                        run.write_autosave(
                            status="running",
                            active_partition=partition,
                            population=len(population),
                            **dict(stats),
                            errors=errors,
                        )
                if partition_errors:
                    status = "completed_with_errors"
                    run.mark_partition_failed(
                        partition,
                        population=len(records),
                        errors=partition_errors,
                    )
                else:
                    run.mark_partition_complete(partition, population=len(records))
    except Exception as exc:
        status = "failed"
        errors += 1
        run.log("run_failed", error=error_summary(exc, include_traceback=True))
    finally:
        run.write_manifest(
            data_inicio=runtime.data_inicio.isoformat(),
            data_fim=runtime.data_fim.isoformat(),
            mode=runtime.mode,
            sample=runtime.sample,
            sample_limit=runtime.sample_limit,
            house=house,
            dataset=dataset,
            strategy="senator-endpoint-missing-ids-v1",
            missing_path=str(missing_path),
            population=len(population),
            existing_before_backfill=len(existing_codes),
            **dict(stats),
            status=status,
            errors=errors,
        )
        print(run.manifest_path)
    return run.manifest_path


def load_population(
    path: Path,
    *,
    house: str,
    dataset: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for line_number, record in enumerate(iter_jsonl(path), start=1):
        if record.get("house") != house or record.get("dataset") != dataset:
            continue
        code = _string(record.get("codigo_pronunciamento"))
        value_date = _parse_date(record.get("data"))
        pronunciamento = record.get("pronunciamento")
        if not code or value_date is None or not isinstance(pronunciamento, dict):
            raise ValueError(f"Registro de lacuna inválido na linha {line_number}: {record!r}")
        if not start <= value_date <= end:
            continue
        normalized = {
            "codigo_pronunciamento": code,
            "data": value_date.isoformat(),
            "house": house,
            "dataset": dataset,
            "parlamentar_ids": sorted(
                {_string(value) for value in record.get("parlamentar_ids", []) if _string(value)},
                key=_code_sort_key,
            ),
            "probe_key": _string(record.get("probe_key")),
            "pronunciamento": pronunciamento,
        }
        previous = by_code.get(code)
        if previous and previous != normalized:
            raise ValueError(f"CodigoPronunciamento duplicado com divergência: {code}")
        by_code[code] = normalized
    if not by_code:
        raise ValueError(
            f"Nenhuma lacuna para house={house}, dataset={dataset} na janela "
            f"{start.isoformat()}..{end.isoformat()}"
        )
    return sorted(by_code.values(), key=lambda record: (record["data"], _code_sort_key(record["codigo_pronunciamento"])))


def missing_record_to_item(record: dict[str, Any], *, missing_path: Path) -> dict[str, Any]:
    code = record["codigo_pronunciamento"]
    pronunciamento = record["pronunciamento"]
    fontes = build_fontes({}, pronunciamento, code)
    return {
        "codigo_pronunciamento": code,
        "metadata": {
            "sessao": {},
            "pronunciamento": pronunciamento,
            "senator_endpoint_backfill": {
                "missing_path": str(missing_path),
                "probe_key": record.get("probe_key"),
                "parlamentar_ids": record.get("parlamentar_ids", []),
                "data_official": record["data"],
                "house": record["house"],
            },
        },
        "fontes": fontes,
    }


def existing_pronunciamento_codes(
    data_root: Path,
    *,
    dataset: str,
    expected_codes: set[str],
    run: CollectionRun | None = None,
) -> set[str]:
    root = data_root / "raw" / "senado" / dataset
    if not root.exists() or not expected_codes:
        return set()
    found: set[str] = set()
    paths = [
        path
        for path in sorted(root.rglob("*.jsonl"))
        if "metadata" not in path.parts and "transcription_queue" not in path.parts
    ]
    for path_index, path in enumerate(paths, start=1):
        for record in iter_jsonl(path):
            if record.get("record_type") != "pronunciamento_texto":
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            code = _string(payload.get("codigo_pronunciamento") or payload.get("CodigoPronunciamento"))
            if code in expected_codes:
                found.add(code)
        if run is not None and (path_index == 1 or path_index % 25 == 0 or path_index == len(paths)):
            run.log(
                "existing_codes_scan_progress",
                files=path_index,
                total_files=len(paths),
                matching_codes=len(found),
            )
    return found


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido em {path}") from exc
            if isinstance(record, dict):
                yield record


def _parse_date(value: Any) -> date | None:
    text = _string(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _code_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**18, value)


if __name__ == "__main__":
    collect()
