from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from coleta.common.config import format_senado_date
from coleta.common.http import OpenDataClient
from coleta.parlamentares.collect import extract_senado_parlamentar_ids, legislaturas_for_period


BASE_URL = "https://legis.senado.leg.br/"
SENATOR_SPEECH_ENDPOINT = "dadosabertos/senador/{codigo}/discursos"
HOUSE_DATASETS = {"SF": "plenario_discursos", "CN": "congresso_discursos"}
COVERAGE_FIELDS = [
    "house",
    "dataset",
    "year",
    "senators_queried",
    "source_ids",
    "raw_ids_in_year",
    "source_ids_present_in_raw",
    "missing_ids",
    "mispartitioned_ids",
    "raw_ids_not_in_senator_endpoint",
    "request_errors",
    "status",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audita a cobertura histórica de discursos por CodigoParlamentar e compara "
            "CodigoPronunciamento com o raw existente."
        )
    )
    parser.add_argument("--cycle-dir", required=True)
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--data-inicio", default="2015-01-01")
    parser.add_argument("--data-fim", default="2016-12-31")
    parser.add_argument("--houses", nargs="+", choices=sorted(HOUSE_DATASETS), default=["SF", "CN"])
    parser.add_argument("--limit-senators", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falha depois de persistir os artefatos se houver erro de fonte, JSONL inválido ou conflito.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Além de --strict, exige zero CodigoPronunciamento ausente no raw em todos os anos/casas.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = audit_senator_endpoint(
        cycle_dir=Path(args.cycle_dir),
        data_root=Path(args.data_root) if args.data_root else None,
        start=date.fromisoformat(args.data_inicio),
        end=date.fromisoformat(args.data_fim),
        houses=args.houses,
        limit_senators=args.limit_senators,
        resume=args.resume,
        strict=args.strict,
        require_complete=args.require_complete,
    )
    print(result["summary_path"])


def audit_senator_endpoint(
    *,
    cycle_dir: Path,
    start: date,
    end: date,
    data_root: Path | None = None,
    houses: Sequence[str] = ("SF", "CN"),
    limit_senators: int | None = None,
    resume: bool = False,
    strict: bool = False,
    require_complete: bool = False,
) -> dict[str, Any]:
    if start > end:
        raise ValueError("data_inicio posterior a data_fim")
    if limit_senators is not None and limit_senators <= 0:
        raise ValueError("limit_senators deve ser positivo")
    selected_houses = tuple(dict.fromkeys(str(house).upper() for house in houses))
    invalid_houses = sorted(set(selected_houses) - set(HOUSE_DATASETS))
    if invalid_houses:
        raise ValueError(f"Casas inválidas: {invalid_houses}")
    if require_complete and data_root is None:
        raise ValueError("--require-complete exige --data-root")

    cycle_dir.mkdir(parents=True, exist_ok=True)
    output_path = cycle_dir / "senator_endpoint_probes.jsonl"
    if resume and output_path.exists():
        by_key, invalid_probe_lines = load_probe_records(output_path)
    else:
        by_key, invalid_probe_lines = {}, 0
        _write_text("", output_path)

    relevant_keys: set[str] = set()
    legislatures = legislaturas_for_period(start, end)
    if not legislatures:
        raise ValueError("Nenhuma legislatura encontrada para o período")

    senator_ids_by_legislature: dict[int, list[str]] = {}
    with OpenDataClient(BASE_URL, min_interval_seconds=0.11) as client:
        for legislature in legislatures:
            probe_key = f"senators:L{legislature}"
            relevant_keys.add(probe_key)
            endpoint = f"dadosabertos/senador/lista/legislatura/{legislature}/{legislature}.json"
            record = by_key.get(probe_key)
            if not probe_succeeded(record):
                try:
                    result = client.get_json(endpoint)
                    record = probe_record(
                        probe_key=probe_key,
                        probe_scope="senators",
                        request={"method": "GET", "path": endpoint, "params": {}},
                        response=result.response_metadata,
                        payload=result.data,
                        legislature=legislature,
                    )
                except Exception as exc:
                    record = probe_record(
                        probe_key=probe_key,
                        probe_scope="senators",
                        request={"method": "GET", "path": endpoint, "params": {}},
                        response={"status": "error"},
                        payload=None,
                        error={"type": type(exc).__name__, "message": str(exc)},
                        legislature=legislature,
                    )
                append_probe_record(record, output_path)
                by_key[probe_key] = record
            senator_ids_by_legislature[legislature] = extract_senado_parlamentar_ids(
                (record or {}).get("payload")
            )

        senator_ids_by_year: dict[int, list[str]] = {}
        for year in range(start.year, end.year + 1):
            year_start = max(start, date(year, 1, 1))
            year_end = min(end, date(year, 12, 31))
            active_legislatures = [
                legislature
                for legislature in legislatures
                if legislature_intersects(legislature, year_start, year_end)
            ]
            senator_ids = sorted(
                {
                    senator_id
                    for legislature in active_legislatures
                    for senator_id in senator_ids_by_legislature.get(legislature, [])
                },
                key=_code_sort_key,
            )
            if limit_senators is not None:
                senator_ids = senator_ids[:limit_senators]
            senator_ids_by_year[year] = senator_ids

            for house in selected_houses:
                for senator_id in senator_ids:
                    probe_key = (
                        f"{house}:{year}:{format_senado_date(year_start)}:"
                        f"{format_senado_date(year_end)}:{senator_id}"
                    )
                    relevant_keys.add(probe_key)
                    if probe_succeeded(by_key.get(probe_key)):
                        continue
                    endpoint = SENATOR_SPEECH_ENDPOINT.format(codigo=senator_id)
                    params = {
                        "casa": house,
                        "dataInicio": format_senado_date(year_start),
                        "dataFim": format_senado_date(year_end),
                        "v": 5,
                    }
                    try:
                        result = client.get_json(endpoint, params=params)
                        record = probe_record(
                            probe_key=probe_key,
                            probe_scope="speeches",
                            request={"method": "GET", "path": endpoint, "params": params},
                            response=result.response_metadata,
                            payload=result.data,
                            house=house,
                            year=year,
                            parlamentar_id=senator_id,
                        )
                    except Exception as exc:
                        record = probe_record(
                            probe_key=probe_key,
                            probe_scope="speeches",
                            request={"method": "GET", "path": endpoint, "params": params},
                            response={"status": "error"},
                            payload=None,
                            error={"type": type(exc).__name__, "message": str(exc)},
                            house=house,
                            year=year,
                            parlamentar_id=senator_id,
                        )
                    append_probe_record(record, output_path)
                    by_key[probe_key] = record

    relevant_records = {
        key: record for key, record in by_key.items() if key in relevant_keys
    }
    source_inventory, source_conflicts = build_source_inventory(
        relevant_records.values(), houses=selected_houses
    )
    raw_inventory = (
        scan_raw_pronunciamentos(data_root, houses=selected_houses, start=start, end=end)
        if data_root is not None
        else empty_raw_inventory(selected_houses)
    )
    request_errors = [
        probe_error_payload(record)
        for record in relevant_records.values()
        if not probe_succeeded(record)
    ]
    coverage, missing_records = build_coverage(
        start=start,
        end=end,
        houses=selected_houses,
        senator_ids_by_year=senator_ids_by_year,
        source_inventory=source_inventory,
        raw_inventory=raw_inventory,
        probe_records=relevant_records.values(),
        source_conflicts=source_conflicts,
        invalid_probe_lines=invalid_probe_lines,
        compare_raw=data_root is not None,
    )

    coverage_path = cycle_dir / "senator_endpoint_coverage.csv"
    missing_path = cycle_dir / "senator_endpoint_missing_ids.jsonl"
    conflicts_path = cycle_dir / "senator_endpoint_conflicts.jsonl"
    errors_path = cycle_dir / "senator_endpoint_errors.jsonl"
    _write_csv(coverage, coverage_path)
    _write_jsonl(missing_records, missing_path)
    _write_jsonl(source_conflicts, conflicts_path)
    _write_jsonl(request_errors, errors_path)

    ids_by_house_year = {
        f"{house}/{year}": len(source_inventory["by_house_year"].get((house, year), {}))
        for year in range(start.year, end.year + 1)
        for house in selected_houses
    }
    summary = {
        "schema_version": 2,
        "source": "senado",
        "strategy": "senator-discourses-by-codigo-parlamentar",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "houses": list(selected_houses),
        "legislatures": legislatures,
        "senators": len(
            {senator_id for values in senator_ids_by_year.values() for senator_id in values}
        ),
        "senators_by_year": {
            str(year): len(senator_ids) for year, senator_ids in senator_ids_by_year.items()
        },
        "limited": limit_senators is not None,
        "requests": sum(
            1 for record in relevant_records.values() if record.get("probe_scope") == "speeches"
        ),
        "errors": len(request_errors),
        "invalid_probe_lines": invalid_probe_lines,
        "invalid_raw_lines": raw_inventory["invalid_lines"],
        "source_conflicts": len(source_conflicts),
        "missing_ids": len(missing_records),
        "coverage_status_counts": _count_values(row["status"] for row in coverage),
        "ids_by_house_year": ids_by_house_year,
        "data_root": str(data_root) if data_root is not None else None,
        "output_path": str(output_path),
        "coverage_path": str(coverage_path),
        "missing_path": str(missing_path),
        "conflicts_path": str(conflicts_path),
        "errors_path": str(errors_path),
        "summary_path": str(cycle_dir / "senator_endpoint_summary.json"),
    }
    _write_json(summary, Path(summary["summary_path"]))

    if strict and (
        request_errors
        or invalid_probe_lines
        or raw_inventory["invalid_lines"]
        or source_conflicts
    ):
        raise ValueError(
            "Auditoria inconclusiva: "
            f"errors={len(request_errors)}, invalid_probe_lines={invalid_probe_lines}, "
            f"invalid_raw_lines={raw_inventory['invalid_lines']}, conflicts={len(source_conflicts)}"
        )
    if require_complete:
        incomplete = [row for row in coverage if row["status"] != "complete"]
        if incomplete:
            labels = ", ".join(f"{row['house']}/{row['year']}={row['status']}" for row in incomplete[:12])
            raise ValueError(f"Cobertura por senador incompleta: {labels}")
    return summary


def legislature_intersects(legislature: int, start: date, end: date) -> bool:
    legislature_start = date(2011 + (legislature - 54) * 4, 2, 1)
    legislature_end = date(legislature_start.year + 4, 1, 31)
    return legislature_start <= end and legislature_end >= start


def extract_pronunciamentos_senador(
    payload: Any,
    *,
    parlamentar_id: str | None = None,
    requested_house: str | None = None,
) -> list[dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            code = value.get("CodigoPronunciamento") or value.get("codigo_pronunciamento")
            if code is not None:
                code_text = str(code)
                item = {
                    "codigo_pronunciamento": code_text,
                    "parlamentar_id": parlamentar_id,
                    "data": _string(value.get("DataPronunciamento") or value.get("dataPronunciamento")),
                    "house": _string(
                        value.get("SiglaCasaPronunciamento")
                        or value.get("siglaCasaPronunciamento")
                        or requested_house
                    ),
                    "pronunciamento": value,
                }
                existing = items.get(code_text)
                if existing is None or len(json.dumps(value, ensure_ascii=False, default=str)) > len(
                    json.dumps(existing["pronunciamento"], ensure_ascii=False, default=str)
                ):
                    items[code_text] = item
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(items.values(), key=lambda item: _code_sort_key(item["codigo_pronunciamento"]))


def extract_pronunciamento_codes(payload: Any) -> list[str]:
    return [item["codigo_pronunciamento"] for item in extract_pronunciamentos_senador(payload)]


def build_source_inventory(
    records: Iterable[dict[str, Any]],
    *,
    houses: Sequence[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected_houses = set(houses)
    by_house_year: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    all_by_house: dict[str, set[str]] = {house: set() for house in houses}
    conflicts: list[dict[str, Any]] = []

    for record in records:
        if record.get("probe_scope") != "speeches" or not probe_succeeded(record):
            continue
        requested_house = _string(record.get("house"))
        query_year = _integer(record.get("year"))
        parlamentar_id = _string(record.get("parlamentar_id"))
        items = extract_pronunciamentos_senador(
            record.get("payload"),
            parlamentar_id=parlamentar_id,
            requested_house=requested_house,
        )
        for item in items:
            house = _string(item.get("house")) or requested_house
            item_year = _year(item.get("data")) or query_year
            code = item["codigo_pronunciamento"]
            if house not in selected_houses or item_year is None:
                conflicts.append(
                    {
                        "type": "invalid_house_or_date",
                        "probe_key": record.get("probe_key"),
                        "codigo_pronunciamento": code,
                        "requested_house": requested_house,
                        "observed_house": house,
                        "query_year": query_year,
                        "observed_date": item.get("data"),
                    }
                )
                continue
            if requested_house and house != requested_house:
                conflicts.append(
                    {
                        "type": "house_mismatch",
                        "probe_key": record.get("probe_key"),
                        "codigo_pronunciamento": code,
                        "requested_house": requested_house,
                        "observed_house": house,
                    }
                )
            if query_year and item_year != query_year:
                conflicts.append(
                    {
                        "type": "year_mismatch",
                        "probe_key": record.get("probe_key"),
                        "codigo_pronunciamento": code,
                        "query_year": query_year,
                        "observed_year": item_year,
                        "observed_date": item.get("data"),
                    }
                )
            previous = by_house_year[(house, item_year)].get(code)
            if previous and (
                previous.get("data") != item.get("data") or previous.get("house") != item.get("house")
            ):
                conflicts.append(
                    {
                        "type": "duplicate_id_conflict",
                        "codigo_pronunciamento": code,
                        "first": previous,
                        "second": item,
                    }
                )
            if previous:
                ids = set(previous.get("discovering_parlamentar_ids") or [])
                if parlamentar_id:
                    ids.add(parlamentar_id)
                previous["discovering_parlamentar_ids"] = sorted(ids, key=_code_sort_key)
            else:
                item["probe_key"] = record.get("probe_key")
                item["discovering_parlamentar_ids"] = [parlamentar_id] if parlamentar_id else []
                by_house_year[(house, item_year)][code] = item
            all_by_house[house].add(code)

    return {"by_house_year": dict(by_house_year), "all_by_house": all_by_house}, conflicts


def scan_raw_pronunciamentos(
    data_root: Path,
    *,
    houses: Sequence[str],
    start: date,
    end: date,
) -> dict[str, Any]:
    all_by_house: dict[str, set[str]] = {house: set() for house in houses}
    by_house_year: dict[tuple[str, int], set[str]] = defaultdict(set)
    years_by_house_code: dict[str, dict[str, set[int]]] = {
        house: defaultdict(set) for house in houses
    }
    files_scanned = 0
    records_scanned = 0
    invalid_lines = 0

    for house in houses:
        dataset = HOUSE_DATASETS[house]
        root = data_root / "raw" / "senado" / dataset
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl")):
            relative_parts = path.relative_to(root).parts
            if "metadata" in relative_parts or "transcription_queue" in relative_parts:
                continue
            files_scanned += 1
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        invalid_lines += 1
                        continue
                    if not isinstance(record, dict) or record.get("record_type") != "pronunciamento_texto":
                        continue
                    records_scanned += 1
                    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                    code = _string(
                        payload.get("codigo_pronunciamento")
                        or payload.get("CodigoPronunciamento")
                    )
                    if not code:
                        continue
                    all_by_house[house].add(code)
                    record_year = raw_record_year(record, path)
                    if record_year is not None:
                        years_by_house_code[house][code].add(record_year)
                        if start.year <= record_year <= end.year:
                            by_house_year[(house, record_year)].add(code)

    return {
        "all_by_house": all_by_house,
        "by_house_year": dict(by_house_year),
        "years_by_house_code": years_by_house_code,
        "files_scanned": files_scanned,
        "records_scanned": records_scanned,
        "invalid_lines": invalid_lines,
    }


def empty_raw_inventory(houses: Sequence[str]) -> dict[str, Any]:
    return {
        "all_by_house": {house: set() for house in houses},
        "by_house_year": {},
        "years_by_house_code": {house: {} for house in houses},
        "files_scanned": 0,
        "records_scanned": 0,
        "invalid_lines": 0,
    }


def raw_record_year(record: dict[str, Any], path: Path) -> int | None:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    pronunciamento = metadata.get("pronunciamento") if isinstance(metadata.get("pronunciamento"), dict) else {}
    sessao = metadata.get("sessao") if isinstance(metadata.get("sessao"), dict) else {}
    candidates = [
        pronunciamento.get("DataPronunciamento"),
        pronunciamento.get("Data"),
        pronunciamento.get("data"),
        sessao.get("DataSessao"),
        (record.get("periodo") or {}).get("data_inicio")
        if isinstance(record.get("periodo"), dict)
        else None,
    ]
    for candidate in candidates:
        year = _year(candidate)
        if year is not None:
            return year
    for part in path.parts:
        if part.startswith("ano=") and part[4:].isdigit():
            return int(part[4:])
    return None


def build_coverage(
    *,
    start: date,
    end: date,
    houses: Sequence[str],
    senator_ids_by_year: dict[int, list[str]],
    source_inventory: dict[str, Any],
    raw_inventory: dict[str, Any],
    probe_records: Iterable[dict[str, Any]],
    source_conflicts: list[dict[str, Any]],
    invalid_probe_lines: int,
    compare_raw: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    error_counts: dict[tuple[str, int], int] = defaultdict(int)
    legislature_error_years: set[int] = set()
    for record in probe_records:
        if probe_succeeded(record):
            continue
        if record.get("probe_scope") == "speeches":
            house = _string(record.get("house"))
            year = _integer(record.get("year"))
            if house and year:
                error_counts[(house, year)] += 1
        elif record.get("probe_scope") == "senators":
            legislature = _integer(record.get("legislature"))
            if legislature:
                for year in range(start.year, end.year + 1):
                    if legislature_intersects(
                        legislature,
                        max(start, date(year, 1, 1)),
                        min(end, date(year, 12, 31)),
                    ):
                        legislature_error_years.add(year)

    conflict_counts: dict[tuple[str, int], int] = defaultdict(int)
    for conflict in source_conflicts:
        house = _string(conflict.get("observed_house") or conflict.get("requested_house"))
        year = _integer(conflict.get("observed_year") or conflict.get("query_year"))
        if house and year:
            conflict_counts[(house, year)] += 1

    coverage: list[dict[str, Any]] = []
    missing_records: list[dict[str, Any]] = []
    for year in range(start.year, end.year + 1):
        for house in houses:
            source_items = source_inventory["by_house_year"].get((house, year), {})
            source_ids = set(source_items)
            raw_all = raw_inventory["all_by_house"].get(house, set())
            raw_year = raw_inventory["by_house_year"].get((house, year), set())
            present = source_ids & raw_all if compare_raw else set()
            missing = source_ids - raw_all if compare_raw else set()
            years_by_code = raw_inventory["years_by_house_code"].get(house, {})
            mispartitioned = {
                code
                for code in present
                if year not in set(years_by_code.get(code, set()))
            }
            raw_not_in_source = raw_year - source_ids if compare_raw else set()
            request_errors = error_counts[(house, year)] + int(year in legislature_error_years)

            if not compare_raw:
                status = "source_only"
            elif invalid_probe_lines or raw_inventory["invalid_lines"]:
                status = "inconclusive_invalid_jsonl"
            elif request_errors or conflict_counts[(house, year)]:
                status = "inconclusive"
            elif not source_ids:
                status = "empty_source"
            elif missing or mispartitioned:
                status = "incomplete"
            else:
                status = "complete"

            coverage.append(
                {
                    "house": house,
                    "dataset": HOUSE_DATASETS[house],
                    "year": year,
                    "senators_queried": len(senator_ids_by_year.get(year, [])),
                    "source_ids": len(source_ids),
                    "raw_ids_in_year": len(raw_year) if compare_raw else "",
                    "source_ids_present_in_raw": len(present) if compare_raw else "",
                    "missing_ids": len(missing) if compare_raw else "",
                    "mispartitioned_ids": len(mispartitioned) if compare_raw else "",
                    "raw_ids_not_in_senator_endpoint": len(raw_not_in_source) if compare_raw else "",
                    "request_errors": request_errors,
                    "status": status,
                }
            )
            for code in sorted(missing, key=_code_sort_key):
                item = source_items[code]
                missing_records.append(
                    {
                        "house": house,
                        "dataset": HOUSE_DATASETS[house],
                        "year": year,
                        "codigo_pronunciamento": code,
                        "data": item.get("data"),
                        "parlamentar_ids": item.get("discovering_parlamentar_ids", []),
                        "pronunciamento": item.get("pronunciamento"),
                        "probe_key": item.get("probe_key"),
                    }
                )
    return coverage, missing_records


def probe_record(
    *,
    probe_key: str,
    probe_scope: str,
    request: dict[str, Any],
    response: dict[str, Any],
    payload: Any,
    error: dict[str, Any] | None = None,
    legislature: int | None = None,
    house: str | None = None,
    year: int | None = None,
    parlamentar_id: str | None = None,
) -> dict[str, Any]:
    record = {
        "probe_key": probe_key,
        "probe_scope": probe_scope,
        "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "senado",
        "record_type": "senator_discourses_probe",
        "request": request,
        "response": response,
        "checksum": sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "payload": payload,
        "pronunciamento_ids": extract_pronunciamento_codes(payload),
    }
    for key, value in {
        "legislature": legislature,
        "house": house,
        "year": year,
        "parlamentar_id": parlamentar_id,
    }.items():
        if value is not None:
            record[key] = value
    if error:
        record["error"] = error
    return record


def probe_succeeded(record: dict[str, Any] | None) -> bool:
    if not record or record.get("error"):
        return False
    response = record.get("response")
    return not isinstance(response, dict) or response.get("status") != "error"


def probe_error_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "probe_key": record.get("probe_key"),
        "probe_scope": record.get("probe_scope"),
        "house": record.get("house"),
        "year": record.get("year"),
        "parlamentar_id": record.get("parlamentar_id"),
        "legislature": record.get("legislature"),
        "request": record.get("request"),
        "response": record.get("response"),
        "error": record.get("error") or {"type": "UnknownProbeError"},
    }


def load_probe_records(path: Path) -> tuple[dict[str, dict[str, Any]], int]:
    by_key: dict[str, dict[str, Any]] = {}
    invalid_lines = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(value, dict) and value.get("probe_key"):
                by_key[str(value["probe_key"])] = value
    return by_key, invalid_lines


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    records, _ = load_probe_records(path)
    yield from records.values()


def append_probe_record(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=COVERAGE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    ordered = sorted(
        records,
        key=lambda record: (
            str(record.get("house") or ""),
            _integer(record.get("year")) or 0,
            _code_sort_key(str(record.get("codigo_pronunciamento") or record.get("probe_key") or "")),
        ),
    )
    text = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        for record in ordered
    )
    _write_text(text, path)


def _write_json(payload: dict[str, Any], path: Path) -> None:
    _write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", path)


def _write_text(value: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value.encode("utf-8"))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _count_values(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(sorted(counts.items()))


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer(value: Any) -> int | None:
    text = _string(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _year(value: Any) -> int | None:
    text = _string(value)
    if not text or len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def _code_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**18, value)


if __name__ == "__main__":
    main()
