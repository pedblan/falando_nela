from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
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
                        if stats.get("page_errors", 0):
                            errors += int(stats["page_errors"])
                            status = "completed_with_errors"
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
