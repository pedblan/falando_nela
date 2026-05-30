from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows, quarter_windows, year_windows
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary
from coleta.common.parlamentares import (
    active_parlamentares_for_window,
    load_parlamentares_periodos,
    parlamentar_active_period,
)

SOURCE = "camara"
DATASET = "plenario_discursos"
BASE_URL = "https://dadosabertos.camara.leg.br/"
RECORD_TYPE = "discursos_page"
YEAR_PROBE_RECORD_TYPE = "discursos_year_probe"
QUARTER_PROBE_RECORD_TYPE = "discursos_quarter_probe"


def collect() -> None:
    parser = build_parser("Coleta discursos de deputados pela API de Dados Abertos da Camara.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(year_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_deputados = 0
    processed_discourse_pages = 0
    processed_discourses = 0
    processed_transcricoes = 0
    preflight_stats: Counter[str] = Counter()
    status = "completed"
    errors = 0
    periodos_by_deputado = load_parlamentares_periodos(
        runtime.output_dir,
        source=SOURCE,
        data_inicio=runtime.data_inicio,
        data_fim=runtime.data_fim,
        min_ids=1 if runtime.sample else 100,
    )

    try:
        with OpenDataClient(BASE_URL) as client:
            for partition, start, end in windows:
                if runtime.sample_limit is not None and not runtime.sample and processed_deputados >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    if periodos_by_deputado:
                        deputados = active_parlamentares_for_window(
                            periodos_by_deputado,
                            start=start,
                            end=end,
                            sample=runtime.sample,
                            sample_limit=runtime.sample_limit,
                        )
                        preflight_stats["partitions_with_mandate_plan"] += 1
                    else:
                        deputados = _collect_deputados(
                            client,
                            run,
                            data_inicio=start.isoformat(),
                            data_fim=end.isoformat(),
                            sample=runtime.sample,
                            sample_limit=runtime.sample_limit,
                        )
                    run.log(
                        "partition_started",
                        partition=partition,
                        periodo=periodo,
                        deputados=len(deputados),
                        granularidade="ano",
                        planejamento="parlamentares_periodos" if periodos_by_deputado else "api_deputados_periodo",
                    )

                    for deputado in deputados:
                        if (
                            runtime.sample_limit is not None
                            and not runtime.sample
                            and processed_deputados >= runtime.sample_limit
                        ):
                            run.log(
                                "sample_limit_reached",
                                sample_limit=runtime.sample_limit,
                                processed_deputados=processed_deputados,
                            )
                            break

                        deputado_id = deputado.get("id")
                        if deputado_id is None:
                            continue
                        request_start, request_end = parlamentar_active_period(deputado, start, end)
                        request_periodo = {
                            "data_inicio": request_start.isoformat(),
                            "data_fim": request_end.isoformat(),
                        }
                        try:
                            stats = _collect_discursos_deputado_adaptive(
                                client,
                                run,
                                deputado_id=int(deputado_id),
                                start=request_start,
                                end=request_end,
                                partition=partition,
                                periodo=request_periodo,
                            )
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("deputy_discourses_failed", deputado_id=deputado_id, error=error_summary(exc))
                            continue
                        preflight_stats.update(stats["preflight"])
                        processed_deputados += 1
                        processed_discourse_pages += stats["pages"]
                        processed_discourses += stats["discursos"]
                        processed_transcricoes += stats["transcricoes"]

                    run.mark_partition_complete(
                        partition,
                        periodo=periodo,
                        deputados=len(deputados),
                        deputados_processados=processed_deputados,
                        paginas_discursos=processed_discourse_pages,
                        discursos=processed_discourses,
                        discursos_com_transcricao=processed_transcricoes,
                        preflight=dict(preflight_stats),
                    )
                    run.log(
                        "partition_completed",
                        partition=partition,
                        deputados=len(deputados),
                        deputados_processados=processed_deputados,
                        paginas_discursos=processed_discourse_pages,
                        discursos=processed_discourses,
                        discursos_com_transcricao=processed_transcricoes,
                        preflight=dict(preflight_stats),
                    )
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
            deputados_processados=processed_deputados,
            deputados_periodos_carregados=len(periodos_by_deputado),
            paginas_discursos=processed_discourse_pages,
            discursos=processed_discourses,
            discursos_com_transcricao=processed_transcricoes,
            preflight=dict(preflight_stats),
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_deputados(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    data_inicio: str,
    data_fim: str,
    sample: bool,
    sample_limit: int | None = None,
) -> list[dict[str, Any]]:
    params = {
        "dataInicio": data_inicio,
        "dataFim": data_fim,
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "nome",
    }
    deputados: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    limit = sample_limit if sample and sample_limit is not None else 3 if sample else None
    for page_index, page in enumerate(iter_camara_pages(client, "api/v2/deputados", params=params), start=1):
        source_id = f"deputados:{data_inicio}:{data_fim}:pagina:{page_index}"
        run.write_record(
            partition="metadata",
            source_id=source_id,
            request={"method": "GET", "path": "api/v2/deputados", "params": params},
            response=page.response_metadata,
            periodo={"data_inicio": data_inicio, "data_fim": data_fim},
            payload=page.data,
            record_type="deputados_page",
        )
        dados = page.data.get("dados", []) if isinstance(page.data, dict) else []
        for item in dados:
            if not isinstance(item, dict):
                continue
            deputado_id = item.get("id")
            if not isinstance(deputado_id, int) or deputado_id in seen_ids:
                continue
            deputados.append(item)
            seen_ids.add(deputado_id)
        if limit is not None and len(deputados) >= limit:
            return deputados[:limit]
    return deputados


def _collect_discursos_deputado_adaptive(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado_id: int,
    start: date,
    end: date,
    partition: str,
    periodo: dict[str, str],
) -> dict[str, Any]:
    stats: dict[str, Any] = {"pages": 0, "discursos": 0, "transcricoes": 0, "preflight": Counter()}
    try:
        status, written = _collect_discursos_probe(
            client,
            run,
            deputado_id=deputado_id,
            start=start,
            end=end,
            partition=partition,
            periodo=periodo,
            record_type=YEAR_PROBE_RECORD_TYPE,
            probe_label="ano",
        )
        stats["preflight"]["year_probes"] += int(written)
        stats["preflight"][f"year_probe_{status}"] += 1
        if status == "zero":
            return stats
    except Exception as exc:
        stats["preflight"]["year_probe_errors"] += 1
        run.log(
            "discursos_year_probe_failed",
            partition=partition,
            deputado_id=deputado_id,
            periodo=periodo,
            error=error_summary(exc),
        )

    for quarter_partition, quarter_start, quarter_end in quarter_windows(start, end):
        quarter_periodo = {"data_inicio": quarter_start.isoformat(), "data_fim": quarter_end.isoformat()}
        expand_months = True
        try:
            quarter_status, written = _collect_discursos_probe(
                client,
                run,
                deputado_id=deputado_id,
                start=quarter_start,
                end=quarter_end,
                partition=quarter_partition,
                periodo=quarter_periodo,
                record_type=QUARTER_PROBE_RECORD_TYPE,
                probe_label="trimestre",
            )
            stats["preflight"]["quarter_probes"] += int(written)
            stats["preflight"][f"quarter_probe_{quarter_status}"] += 1
            expand_months = quarter_status != "zero"
        except Exception as exc:
            stats["preflight"]["quarter_probe_errors"] += 1
            run.log(
                "discursos_quarter_probe_failed",
                partition=partition,
                quarter_partition=quarter_partition,
                deputado_id=deputado_id,
                periodo=quarter_periodo,
                error=error_summary(exc),
            )

        if not expand_months:
            continue

        month_stats = _collect_discursos_deputado_months(
            client,
            run,
            deputado_id=deputado_id,
            start=quarter_start,
            end=quarter_end,
        )
        stats["pages"] += month_stats["pages"]
        stats["discursos"] += month_stats["discursos"]
        stats["transcricoes"] += month_stats["transcricoes"]
        stats["preflight"]["months_expanded"] += month_stats["months"]
    return stats


def _collect_discursos_deputado_months(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado_id: int,
    start: date,
    end: date,
) -> dict[str, int]:
    stats = {"pages": 0, "discursos": 0, "transcricoes": 0, "months": 0}
    for month_partition, month_start, month_end in month_windows(start, end):
        periodo = {"data_inicio": month_start.isoformat(), "data_fim": month_end.isoformat()}
        month_stats = _collect_discursos_deputado(client, run, month_partition, periodo, deputado_id)
        stats["pages"] += month_stats["pages"]
        stats["discursos"] += month_stats["discursos"]
        stats["transcricoes"] += month_stats["transcricoes"]
        stats["months"] += 1
    return stats


def _collect_discursos_probe(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado_id: int,
    start: date,
    end: date,
    partition: str,
    periodo: dict[str, str],
    record_type: str,
    probe_label: str,
) -> tuple[str, bool]:
    path = f"api/v2/deputados/{deputado_id}/discursos"
    params = {
        "dataInicio": start.isoformat(),
        "dataFim": end.isoformat(),
        "itens": 1,
        "ordem": "ASC",
        "ordenarPor": "dataHoraInicio",
    }
    source_id = f"deputado:{deputado_id}:discursos:{probe_label}:{partition}"
    already_recorded = run.has_record(source_id=source_id, record_type=record_type)
    result = client.get_json(path, params=params)
    discursos = _dados(result.data)
    status = "positive" if discursos else "zero"
    if already_recorded:
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        return status, False
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": path, "params": params},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type=record_type,
    )
    return status, written


def _collect_discursos_deputado(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    deputado_id: int,
) -> dict[str, int]:
    path = f"api/v2/deputados/{deputado_id}/discursos"
    params = {
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "dataHoraInicio",
    }
    stats = {"pages": 0, "discursos": 0, "transcricoes": 0}

    for page_index, result in enumerate(iter_camara_pages(client, path, params=params), start=1):
        source_id = f"deputado:{deputado_id}:discursos:{partition}:pagina:{page_index}"
        discursos = _dados(result.data)
        if run.has_record(source_id=source_id, record_type=RECORD_TYPE):
            run.log("record_resume_skipped", source_id=source_id, record_type=RECORD_TYPE)
            continue
        stats["pages"] += 1
        stats["discursos"] += len(discursos)
        stats["transcricoes"] += sum(1 for discurso in discursos if _has_text(discurso.get("transcricao")))
        run.write_record(
            partition=partition,
            source_id=source_id,
            request={"method": "GET", "path": path, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type=RECORD_TYPE,
        )
    return stats


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


if __name__ == "__main__":
    collect()
