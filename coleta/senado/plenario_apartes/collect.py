from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, format_senado_date, month_windows, quarter_windows, year_windows
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary, listify
from coleta.parlamentares.collect import extract_senado_parlamentar_ids, legislaturas_for_period

SOURCE = "senado"
DATASET = "plenario_apartes"
BASE_URL = "https://legis.senado.leg.br/"
SIGLA_CASA = "SF"
RECORD_TYPE = "senador_apartes_metadata"
YEAR_PROBE_RECORD_TYPE = "senador_apartes_year_probe"
QUARTER_PROBE_RECORD_TYPE = "senador_apartes_quarter_probe"


def collect() -> None:
    parser = build_parser("Coleta metadados de apartes do Plenario do Senado.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(year_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    periodo_total = {"data_inicio": runtime.data_inicio.isoformat(), "data_fim": runtime.data_fim.isoformat()}
    status = "completed"
    errors = 0
    stats: Counter[str] = Counter()

    try:
        with OpenDataClient(BASE_URL) as client:
            senador_ids = discover_senadores(client, runtime.data_inicio, runtime.data_fim, run, periodo_total)
            stats["senadores_descobertos"] = len(senador_ids)
            if runtime.sample and runtime.sample_limit is not None:
                senador_ids = senador_ids[: runtime.sample_limit]
            stats["senadores_selecionados"] = len(senador_ids)
            run.log("senadores_loaded", total=stats["senadores_descobertos"], selecionados=len(senador_ids))

            for partition, start, end in windows:
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue
                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    run.log("partition_started", partition=partition, periodo=periodo, senadores=len(senador_ids))
                    for senador_id in senador_ids:
                        try:
                            senador_stats = collect_senador_apartes_adaptive(
                                client,
                                run,
                                senador_id=senador_id,
                                start=start,
                                end=end,
                                partition=partition,
                                periodo=periodo,
                            )
                            stats.update(senador_stats)
                            stats["senadores_processados"] += 1
                            if senador_stats.get("errors"):
                                errors += int(senador_stats["errors"])
                                status = "completed_with_errors"
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            stats["errors"] += 1
                            run.log(
                                "senador_apartes_failed",
                                partition=partition,
                                senador_id=senador_id,
                                error=error_summary(exc),
                            )
                            continue
                    run.mark_partition_complete(partition, periodo=periodo, stats=dict(stats))
                    run.log("partition_completed", partition=partition, stats=dict(stats))
                except Exception as exc:
                    errors += 1
                    status = "completed_with_errors"
                    run.mark_partition_failed(partition, periodo=periodo, error=error_summary(exc, include_traceback=True))
                    run.log("partition_failed", partition=partition, error=error_summary(exc))
                    continue
    except Exception as exc:
        errors += 1
        status = "failed"
        run.log("run_failed", error=error_summary(exc, include_traceback=True))
    finally:
        run.write_manifest(
            data_inicio=runtime.data_inicio.isoformat(),
            data_fim=runtime.data_fim.isoformat(),
            mode=runtime.mode,
            sample=runtime.sample,
            sample_limit=runtime.sample_limit,
            status=status,
            errors=errors,
            stats=dict(stats),
        )
        print(run.manifest_path)


def discover_senadores(
    client: OpenDataClient,
    data_inicio: date,
    data_fim: date,
    run: CollectionRun,
    periodo: dict[str, str],
) -> list[str]:
    ids: list[str] = []
    legislaturas = legislaturas_for_period(data_inicio, data_fim)
    if legislaturas:
        inicio, fim = min(legislaturas), max(legislaturas)
        path = f"dadosabertos/senador/lista/legislatura/{inicio}/{fim}.json"
        try:
            result = client.get_json(path)
            ids.extend(extract_senado_parlamentar_ids(result.data))
            run.write_record(
                partition="metadata",
                source_id=f"SF:senadores:legislatura:{inicio}:{fim}",
                request={"method": "GET", "path": path, "params": {}},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="senadores_legislatura_metadata",
            )
        except Exception as exc:
            run.log("senadores_legislatura_failed", error=error_summary(exc))

    current_path = "dadosabertos/senador/lista/atual.json"
    try:
        current = client.get_json(current_path)
        ids.extend(extract_senado_parlamentar_ids(current.data))
        run.write_record(
            partition="metadata",
            source_id="SF:senadores:atual",
            request={"method": "GET", "path": current_path, "params": {}},
            response=current.response_metadata,
            periodo=periodo,
            payload=current.data,
            record_type="senadores_atual_metadata",
        )
    except Exception as exc:
        run.log("senadores_atual_failed", error=error_summary(exc))

    return ordered_ids(ids)


def collect_senador_apartes_adaptive(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    senador_id: str,
    start: date,
    end: date,
    partition: str,
    periodo: dict[str, str],
) -> Counter[str]:
    stats: Counter[str] = Counter()
    try:
        probe_written, annual_count = collect_senador_apartes(
            client,
            run,
            senador_id=senador_id,
            start=start,
            end=end,
            periodo=periodo,
            record_type=YEAR_PROBE_RECORD_TYPE,
            fetch_existing=True,
        )
        stats["year_probes"] += int(probe_written)
        stats["year_probe_apartes_payload"] += annual_count
        if annual_count == 0:
            stats["year_probes_empty"] += 1
            return stats
        stats["year_probes_positive"] += 1
    except Exception as exc:
        stats["errors"] += 1
        stats["year_probe_errors"] += 1
        run.log(
            "senador_apartes_year_probe_failed",
            partition=partition,
            senador_id=senador_id,
            error=error_summary(exc),
        )

    stats.update(
        collect_senador_apartes_quarters(
            client,
            run,
            senador_id=senador_id,
            start=start,
            end=end,
            partition=partition,
        )
    )
    return stats


def collect_senador_apartes_quarters(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    senador_id: str,
    start: date,
    end: date,
    partition: str,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    for quarter_partition, quarter_start, quarter_end in quarter_windows(start, end):
        quarter_periodo = {"data_inicio": quarter_start.isoformat(), "data_fim": quarter_end.isoformat()}
        try:
            probe_written, quarter_count = collect_senador_apartes(
                client,
                run,
                senador_id=senador_id,
                start=quarter_start,
                end=quarter_end,
                periodo=quarter_periodo,
                record_type=QUARTER_PROBE_RECORD_TYPE,
                fetch_existing=True,
            )
            stats["quarter_probes"] += int(probe_written)
            stats["quarter_probe_apartes_payload"] += quarter_count
            if quarter_count == 0:
                stats["quarter_probes_empty"] += 1
                continue
            stats["quarter_probes_positive"] += 1
        except Exception as exc:
            stats["errors"] += 1
            stats["quarter_probe_errors"] += 1
            run.log(
                "senador_apartes_quarter_probe_failed",
                partition=partition,
                quarter_partition=quarter_partition,
                senador_id=senador_id,
                error=error_summary(exc),
            )

        stats.update(
            collect_senador_apartes_months(
                client,
                run,
                senador_id=senador_id,
                start=quarter_start,
                end=quarter_end,
                partition=partition,
                parent_partition=quarter_partition,
            )
        )
    return stats


def collect_senador_apartes_months(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    senador_id: str,
    start: date,
    end: date,
    partition: str,
    parent_partition: str,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    for month_partition, month_start, month_end in month_windows(start, end):
        month_periodo = {"data_inicio": month_start.isoformat(), "data_fim": month_end.isoformat()}
        try:
            written, aparte_count = collect_senador_apartes(
                client,
                run,
                senador_id=senador_id,
                start=month_start,
                end=month_end,
                periodo=month_periodo,
                record_type=RECORD_TYPE,
            )
            stats["months_expanded"] += 1
            stats["requests_apartes"] += int(written)
            stats["apartes_payload"] += aparte_count
        except Exception as exc:
            stats["errors"] += 1
            stats["month_errors"] += 1
            run.log(
                "senador_apartes_month_failed",
                partition=partition,
                parent_partition=parent_partition,
                month_partition=month_partition,
                senador_id=senador_id,
                error=error_summary(exc),
            )
    return stats


def collect_senador_apartes(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    senador_id: str,
    start: date,
    end: date,
    periodo: dict[str, str],
    record_type: str = RECORD_TYPE,
    fetch_existing: bool = False,
) -> tuple[bool, int]:
    endpoint = f"dadosabertos/senador/{senador_id}/apartes"
    params = {
        "casa": SIGLA_CASA,
        "dataInicio": format_senado_date(start),
        "dataFim": format_senado_date(end),
        "v": 5,
    }
    source_id = f"{SIGLA_CASA}:senador:{senador_id}:apartes:{params['dataInicio']}:{params['dataFim']}"
    already_recorded = run.has_record(source_id=source_id, record_type=record_type)
    if already_recorded and not fetch_existing:
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        return False, 0
    result = client.get_json(endpoint, params=params)
    payload = result.data
    if already_recorded:
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        return False, count_apartes(payload)
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": endpoint, "params": params},
        response=result.response_metadata,
        periodo=periodo,
        payload=payload,
        record_type=record_type,
    )
    return written, count_apartes(payload)


def count_apartes(payload: Any) -> int:
    parlamentar = _get(payload, "ApartesParlamentar", "Parlamentar")
    apartes = _get(parlamentar, "Apartes", "Aparte")
    return len([item for item in listify(apartes) if isinstance(item, dict)])


def ordered_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in ids:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return sorted(ordered, key=lambda value: (int(value), value) if value.isdigit() else (10**12, value))


def _get(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


if __name__ == "__main__":
    collect()
