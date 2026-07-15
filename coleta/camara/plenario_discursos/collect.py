from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, runtime_config_from_namespace
from coleta.common.config import apply_sample_window, month_windows, quarter_windows, year_windows
from coleta.common.http import HttpResult, OpenDataClient, iter_camara_pages
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
PAGE_ERROR_RECORD_TYPE = "discursos_page_error"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
FAST_FALLBACK_STATUS_CODES = {500}


def collect(argv: Sequence[str] | None = None) -> None:
    parser = build_parser("Coleta discursos de deputados pela API de Dados Abertos da Camara.")
    parser.add_argument(
        "--skip-existing-record-scan",
        action="store_true",
        help=(
            "Pula a varredura inicial dos JSONLs do run. Exige --resume e uma fronteira "
            "limpa comprovada por checkpoint e log; particoes concluidas continuam sendo puladas."
        ),
    )
    parser.add_argument(
        "--parlamentares-periodos-path",
        default=None,
        help=(
            "Caminho explicito para parlamentares_periodos.parquet ou .jsonl. "
            "Use uma copia local no runtime Colab para evitar leitura aleatoria pelo Drive FUSE."
        ),
    )
    args = parser.parse_args(argv)
    runtime = runtime_config_from_namespace(parser, args)
    if args.skip_existing_record_scan and not runtime.resume:
        parser.error("--skip-existing-record-scan exige --resume")
    periodos_path = (
        Path(args.parlamentares_periodos_path).expanduser()
        if args.parlamentares_periodos_path
        else None
    )
    if periodos_path is not None:
        if periodos_path.suffix not in {".parquet", ".jsonl"}:
            parser.error("--parlamentares-periodos-path deve terminar em .parquet ou .jsonl")
        if not periodos_path.is_file():
            parser.error(f"Arquivo de periodos ausente: {periodos_path}")

    requested_partitions = {
        partition for partition, _, _ in year_windows(runtime.data_inicio, runtime.data_fim)
    }
    resume_state = None
    resume_state_error = None
    if runtime.resume:
        try:
            resume_state = inspect_checkpoint_resume_state(
                runtime.output_dir,
                run_id=runtime.run_id,
                requested_partitions=requested_partitions,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            resume_state_error = error_summary(exc)

    boundary = None
    if args.skip_existing_record_scan:
        boundary = validate_clean_checkpoint_boundary(
            runtime.output_dir,
            run_id=runtime.run_id,
            requested_partitions=requested_partitions,
        )
    partial_scan_years = _partial_resume_scan_years(resume_state)
    if partial_scan_years:
        print(
            "Retomada parcial comprovada; o indice de duplicatas sera reconstruido "
            f"somente para os anos {sorted(partial_scan_years)}.",
            flush=True,
        )
    elif runtime.resume and not args.skip_existing_record_scan:
        print(
            "Escopo parcial nao comprovado; o indice de duplicatas sera reconstruido "
            "a partir de todo o raw do run.",
            flush=True,
        )
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
        load_existing_records=not args.skip_existing_record_scan,
        existing_record_years=partial_scan_years,
    )
    if boundary is not None:
        run.log("resume_record_scan_skipped", **boundary)
    elif partial_scan_years:
        run.log(
            "resume_record_scan_filtered",
            years=sorted(partial_scan_years),
            open_partitions=resume_state["open_partitions"] if resume_state else [],
            unresolved_failed_partitions=(
                resume_state["unresolved_failed_partitions"] if resume_state else []
            ),
        )
    elif resume_state_error is not None:
        run.log("resume_state_inspection_failed", error=resume_state_error)
    windows = apply_sample_window(list(year_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_deputados = 0
    processed_discourse_pages = 0
    processed_discourses = 0
    processed_transcricoes = 0
    preflight_stats: Counter[str] = Counter()
    status = "completed"
    errors = 0
    run.log(
        "parlamentares_periodos_loading",
        path=str(periodos_path) if periodos_path else "processed/parlamentares/v1",
    )
    periodos_by_deputado = load_parlamentares_periodos(
        runtime.output_dir,
        source=SOURCE,
        data_inicio=runtime.data_inicio,
        data_fim=runtime.data_fim,
        min_ids=1 if runtime.sample else 100,
        periodos_path=periodos_path,
    )
    run.log(
        "parlamentares_periodos_loaded",
        path=str(periodos_path) if periodos_path else "processed/parlamentares/v1",
        deputados=len(periodos_by_deputado),
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
                    partition_errors = 0
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

                    for deputado_index, deputado in enumerate(deputados, start=1):
                        try:
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
                                partition_errors += 1
                                status = "completed_with_errors"
                                run.log(
                                    "deputy_discourses_failed",
                                    deputado_id=deputado_id,
                                    error=error_summary(exc),
                                )
                                continue
                            if stats.get("page_errors", 0):
                                page_errors = int(stats["page_errors"])
                                errors += page_errors
                                partition_errors += page_errors
                                status = "completed_with_errors"
                            preflight_stats.update(stats["preflight"])
                            processed_deputados += 1
                            processed_discourse_pages += stats["pages"]
                            processed_discourses += stats["discursos"]
                            processed_transcricoes += stats["transcricoes"]
                        finally:
                            if (
                                deputado_index == 1
                                or deputado_index % 25 == 0
                                or deputado_index == len(deputados)
                            ):
                                progress = {
                                    "partition": partition,
                                    "deputados_visitados": deputado_index,
                                    "deputados_total": len(deputados),
                                    "deputados_processados": processed_deputados,
                                    "paginas_discursos": processed_discourse_pages,
                                    "discursos": processed_discourses,
                                    "discursos_com_transcricao": processed_transcricoes,
                                    "errors": errors,
                                }
                                run.log("deputy_progress", **progress)
                                run.write_autosave(status="running", active_partition=partition, **progress)

                    partition_metadata = {
                        "periodo": periodo,
                        "deputados": len(deputados),
                        "deputados_processados": processed_deputados,
                        "paginas_discursos": processed_discourse_pages,
                        "discursos": processed_discourses,
                        "discursos_com_transcricao": processed_transcricoes,
                        "preflight": dict(preflight_stats),
                    }
                    if partition_errors:
                        run.mark_partition_failed(
                            partition,
                            errors=partition_errors,
                            **partition_metadata,
                        )
                        run.log(
                            "partition_completed_with_errors",
                            partition=partition,
                            errors=partition_errors,
                            **partition_metadata,
                        )
                    else:
                        run.mark_partition_complete(partition, **partition_metadata)
                        run.log("partition_completed", partition=partition, **partition_metadata)
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
            skip_existing_record_scan=bool(args.skip_existing_record_scan),
            parlamentares_periodos_path=str(periodos_path) if periodos_path else None,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def validate_clean_checkpoint_boundary(
    output_dir: Path,
    *,
    run_id: str,
    requested_partitions: set[str] | None = None,
) -> dict[str, Any]:
    state = inspect_checkpoint_resume_state(
        output_dir,
        run_id=run_id,
        requested_partitions=requested_partitions,
    )
    if not state["completed_partitions"]:
        raise RuntimeError(
            f"Retomada rapida recusada: o run {run_id} nao possui particoes concluidas."
        )
    if state["unresolved_failed_partitions"]:
        raise RuntimeError(
            "Retomada rapida recusada: particoes falhas nao resolvidas: "
            f"{state['unresolved_failed_partitions'][:20]}"
        )
    if state["open_partitions"]:
        raise RuntimeError(
            "Retomada rapida recusada: ha particao iniciada sem conclusao no log: "
            f"{state['open_partitions'][:20]}. Use --resume sem pular a varredura."
        )
    if state["checkpoint_completions_missing_in_log"]:
        raise RuntimeError(
            "Retomada rapida recusada: checkpoint e log divergem nas particoes: "
            f"{state['checkpoint_completions_missing_in_log'][:20]}"
        )
    if not state["relevant_events"]:
        raise RuntimeError("Retomada rapida recusada: o log nao contem eventos de particao.")

    return {
        "checkpoint_boundary": "clean",
        "completed_partitions": len(state["completed_partitions"]),
        "unresolved_failed_partitions": [],
    }


def inspect_checkpoint_resume_state(
    output_dir: Path,
    *,
    run_id: str,
    requested_partitions: set[str] | None = None,
) -> dict[str, Any]:
    checkpoint_path = output_dir / "checkpoints" / SOURCE / f"{DATASET}.json"
    log_path = output_dir / "logs" / f"{run_id}.jsonl"
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint ausente para retomada: {checkpoint_path}")
    if not log_path.is_file():
        raise FileNotFoundError(f"Log ausente para retomada: {log_path}")

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    current = (checkpoint.get("runs") or {}).get(run_id, {}) or {}
    completed = set((current.get("completed_partitions") or {}).keys())
    failed = set((current.get("failed_partitions") or {}).keys())
    if requested_partitions is not None:
        completed &= requested_partitions
        failed &= requested_partitions
    unresolved = failed - completed

    open_partitions: set[str] = set()
    completed_in_log: set[str] = set()
    relevant_events = 0
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("run_id") != run_id:
                continue
            partition = event.get("partition")
            event_name = event.get("event")
            if not isinstance(partition, str):
                continue
            if requested_partitions is not None and partition not in requested_partitions:
                continue
            if event_name == "partition_started":
                relevant_events += 1
                open_partitions.add(partition)
            elif event_name == "partition_completed":
                relevant_events += 1
                completed_in_log.add(partition)
                open_partitions.discard(partition)
            elif event_name == "partition_failed":
                relevant_events += 1
                open_partitions.discard(partition)

    missing_log_completion = completed - completed_in_log
    return {
        "completed_partitions": sorted(completed),
        "unresolved_failed_partitions": sorted(unresolved),
        "open_partitions": sorted(open_partitions),
        "checkpoint_completions_missing_in_log": sorted(missing_log_completion),
        "relevant_events": relevant_events,
    }


def _partial_resume_scan_years(state: dict[str, Any] | None) -> set[str] | None:
    if not state or not state["completed_partitions"] or not state["relevant_events"]:
        return None
    if state["checkpoint_completions_missing_in_log"]:
        return None
    partial = set(state["open_partitions"]) | set(state["unresolved_failed_partitions"])
    if not partial or any(len(partition) != 4 or not partition.isdigit() for partition in partial):
        return None
    return partial


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
    stats: dict[str, Any] = {
        "pages": 0,
        "discursos": 0,
        "transcricoes": 0,
        "page_errors": 0,
        "preflight": Counter(),
    }
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
        stats["page_errors"] += month_stats["page_errors"]
        stats["preflight"]["months_expanded"] += month_stats["months"]
        stats["preflight"]["monthly_page_errors"] += month_stats["page_errors"]
    return stats


def _collect_discursos_deputado_months(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado_id: int,
    start: date,
    end: date,
) -> dict[str, int]:
    stats = {"pages": 0, "discursos": 0, "transcricoes": 0, "months": 0, "page_errors": 0}
    for month_partition, month_start, month_end in month_windows(start, end):
        periodo = {"data_inicio": month_start.isoformat(), "data_fim": month_end.isoformat()}
        try:
            month_stats = _collect_discursos_deputado(client, run, month_partition, periodo, deputado_id)
        except Exception as exc:
            stats["page_errors"] += 1
            run.log(
                "discursos_month_failed",
                partition=month_partition,
                deputado_id=deputado_id,
                periodo=periodo,
                error=error_summary(exc),
            )
            _write_discursos_error_record(
                run,
                partition=month_partition,
                periodo=periodo,
                deputado_id=deputado_id,
                page_index=None,
                request={"method": "GET", "path": f"api/v2/deputados/{deputado_id}/discursos", "params": {}},
                error=exc,
                strategy="month_failed",
            )
            stats["months"] += 1
            continue
        stats["pages"] += month_stats["pages"]
        stats["discursos"] += month_stats["discursos"]
        stats["transcricoes"] += month_stats["transcricoes"]
        stats["page_errors"] += month_stats["page_errors"]
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
    params = _discursos_params(start.isoformat(), end.isoformat(), itens=1, ordered=True)
    source_id = f"deputado:{deputado_id}:discursos:{probe_label}:{partition}"
    already_recorded = run.has_record(source_id=source_id, record_type=record_type)
    request_params = params
    strategy = "default"
    try:
        result = _get_json_fast_fallback(client, path, params=params)
    except httpx.HTTPStatusError as exc:
        if not _is_retryable_http_error(exc):
            raise
        request_params = _discursos_params(start.isoformat(), end.isoformat(), itens=1, ordered=False)
        strategy = "sem_ordenacao"
        run.log(
            "discursos_probe_fallback_started",
            partition=partition,
            deputado_id=deputado_id,
            periodo=periodo,
            record_type=record_type,
            fallback_strategy=strategy,
            error=error_summary(exc),
        )
        result = _get_json_once(client, path, params=request_params)
    discursos = _dados(result.data)
    status = "positive" if discursos else "zero"
    if already_recorded:
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        return status, False
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request=_request_payload(path, request_params, strategy=strategy),
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
    default_params = _discursos_params(periodo["data_inicio"], periodo["data_fim"], itens=100, ordered=True)
    try:
        pages = _fetch_discursos_pages_follow_next(
            client,
            path,
            params=default_params,
            strategy="default",
            retries=True,
            fast_fallback=True,
        )
        return _write_discursos_pages(
            run,
            partition=partition,
            periodo=periodo,
            deputado_id=deputado_id,
            pages=pages,
        )
    except httpx.HTTPStatusError as exc:
        if not _is_retryable_http_error(exc):
            raise
        run.log(
            "discursos_month_fallback_started",
            partition=partition,
            deputado_id=deputado_id,
            periodo=periodo,
            fallback_strategy="sem_ordenacao",
            error=error_summary(exc),
        )

    unordered_params = _discursos_params(periodo["data_inicio"], periodo["data_fim"], itens=100, ordered=False)
    try:
        pages = _fetch_discursos_pages_follow_next(
            client,
            path,
            params=unordered_params,
            strategy="sem_ordenacao",
            retries=False,
            fast_fallback=False,
        )
        return _write_discursos_pages(
            run,
            partition=partition,
            periodo=periodo,
            deputado_id=deputado_id,
            pages=pages,
        )
    except httpx.HTTPStatusError as exc:
        if not _is_retryable_http_error(exc):
            raise
        run.log(
            "discursos_month_fallback_started",
            partition=partition,
            deputado_id=deputado_id,
            periodo=periodo,
            fallback_strategy="itens_1",
            error=error_summary(exc),
        )

    return _collect_discursos_deputado_explicit_pages(
        client,
        run,
        partition=partition,
        periodo=periodo,
        deputado_id=deputado_id,
        itens=1,
    )


def _fetch_discursos_pages_follow_next(
    client: OpenDataClient,
    path: str,
    *,
    params: dict[str, Any],
    strategy: str,
    retries: bool,
    fast_fallback: bool,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    next_url: str | None = path
    next_params: dict[str, Any] | None = params
    page_index = 1
    while next_url:
        if fast_fallback:
            result = _get_json_fast_fallback(client, next_url, params=next_params or {})
        elif retries:
            result = client.get_json(next_url, params=next_params)
        else:
            result = _get_json_once(client, next_url, params=next_params or {})
        request_path = next_url
        request_params = next_params or {}
        pages.append(
            {
                "page_index": page_index,
                "result": result,
                "request": _request_payload(request_path, request_params, strategy=strategy),
            }
        )
        next_url = _next_link(result.data)
        next_params = None
        page_index += 1
    return pages


def _collect_discursos_deputado_explicit_pages(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    partition: str,
    periodo: dict[str, str],
    deputado_id: int,
    itens: int,
) -> dict[str, int]:
    path = f"api/v2/deputados/{deputado_id}/discursos"
    first_params = _discursos_params(periodo["data_inicio"], periodo["data_fim"], itens=itens, ordered=False)
    first_request = _request_payload(path, first_params, strategy=f"itens_{itens}")
    first_result = _get_json_once(client, path, params=first_params)
    last_page = _last_page_from_links(first_result.data) or 1
    stats = _write_discursos_pages(
        run,
        partition=partition,
        periodo=periodo,
        deputado_id=deputado_id,
        pages=[{"page_index": 1, "result": first_result, "request": first_request}],
    )

    for page_index in range(2, last_page + 1):
        params = {**first_params, "pagina": page_index}
        request = _request_payload(path, params, strategy=f"itens_{itens}")
        try:
            result = _get_json_once(client, path, params=params)
        except Exception as exc:
            stats["page_errors"] += 1
            run.log(
                "discursos_page_failed",
                partition=partition,
                deputado_id=deputado_id,
                page_index=page_index,
                last_page=last_page,
                periodo=periodo,
                fallback_strategy=f"itens_{itens}",
                error=error_summary(exc),
            )
            _write_discursos_error_record(
                run,
                partition=partition,
                periodo=periodo,
                deputado_id=deputado_id,
                page_index=page_index,
                request=request,
                error=exc,
                strategy=f"itens_{itens}",
            )
            continue

        page_stats = _write_discursos_pages(
            run,
            partition=partition,
            periodo=periodo,
            deputado_id=deputado_id,
            pages=[{"page_index": page_index, "result": result, "request": request}],
        )
        stats["pages"] += page_stats["pages"]
        stats["discursos"] += page_stats["discursos"]
        stats["transcricoes"] += page_stats["transcricoes"]
        stats["page_errors"] += page_stats["page_errors"]
    return stats


def _write_discursos_pages(
    run: CollectionRun,
    *,
    partition: str,
    periodo: dict[str, str],
    deputado_id: int,
    pages: list[dict[str, Any]],
) -> dict[str, int]:
    stats = {"pages": 0, "discursos": 0, "transcricoes": 0, "page_errors": 0}
    for page in pages:
        page_index = int(page["page_index"])
        result = page["result"]
        request = page["request"]
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
            request=request,
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type=RECORD_TYPE,
        )
    return stats


def _write_discursos_error_record(
    run: CollectionRun,
    *,
    partition: str,
    periodo: dict[str, str],
    deputado_id: int,
    page_index: int | None,
    request: dict[str, Any],
    error: BaseException,
    strategy: str,
) -> None:
    page_label = f"pagina:{page_index}" if page_index is not None else "mes"
    source_id = f"deputado:{deputado_id}:discursos:{partition}:{page_label}:erro:{strategy}"
    if run.has_record(source_id=source_id, record_type=PAGE_ERROR_RECORD_TYPE):
        run.log("record_resume_skipped", source_id=source_id, record_type=PAGE_ERROR_RECORD_TYPE)
        return
    run.write_record(
        partition="metadata",
        source_id=source_id,
        request=request,
        response=_response_from_error(error),
        periodo=periodo,
        payload={"error": error_summary(error), "fallback_strategy": strategy, "page_index": page_index},
        record_type=PAGE_ERROR_RECORD_TYPE,
    )


def _discursos_params(data_inicio: str, data_fim: str, *, itens: int, ordered: bool) -> dict[str, Any]:
    params: dict[str, Any] = {
        "dataInicio": data_inicio,
        "dataFim": data_fim,
        "itens": itens,
    }
    if ordered:
        params["ordem"] = "ASC"
        params["ordenarPor"] = "dataHoraInicio"
    return params


def _request_payload(path: str, params: dict[str, Any], *, strategy: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"method": "GET", "path": path, "params": params}
    if strategy != "default":
        payload["fallback_strategy"] = strategy
    return payload


def _get_json_once(client: OpenDataClient, path_or_url: str, *, params: dict[str, Any]) -> HttpResult:
    response = client.client.get(
        client._resolve_url(path_or_url),
        params=params,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    return client._result(response, response_type="json")


def _get_json_fast_fallback(client: OpenDataClient, path_or_url: str, *, params: dict[str, Any]) -> HttpResult:
    response = client.client.get(
        client._resolve_url(path_or_url),
        params=params,
        headers={"Accept": "application/json"},
    )
    if response.status_code in FAST_FALLBACK_STATUS_CODES:
        response.raise_for_status()
    if response.status_code in RETRYABLE_STATUS_CODES:
        return client.get_json(path_or_url, params=params)
    response.raise_for_status()
    return client._result(response, response_type="json")


def _is_retryable_http_error(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code in RETRYABLE_STATUS_CODES


def _response_from_error(error: BaseException) -> dict[str, Any]:
    if isinstance(error, httpx.HTTPStatusError):
        return {
            "url": str(error.request.url),
            "status_code": error.response.status_code,
            "headers": {
                key: value
                for key, value in error.response.headers.items()
                if key.lower()
                in {
                    "content-disposition",
                    "content-length",
                    "content-type",
                    "date",
                    "link",
                    "location",
                    "retry-after",
                    "x-total-count",
                }
            },
        }
    return {"url": None, "status_code": None, "headers": {}}


def _next_link(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for link in payload.get("links", []):
        if isinstance(link, dict) and link.get("rel") == "next":
            href = link.get("href")
            return href if isinstance(href, str) else None
    return None


def _last_page_from_links(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for link in payload.get("links", []):
        if not isinstance(link, dict) or link.get("rel") != "last":
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        page_values = parse_qs(urlparse(href).query).get("pagina", [])
        if not page_values:
            continue
        try:
            return int(page_values[0])
        except ValueError:
            return None
    return None


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


if __name__ == "__main__":
    collect()
