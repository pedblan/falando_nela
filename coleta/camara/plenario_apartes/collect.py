from __future__ import annotations

import html
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows, quarter_windows, year_windows
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary

SOURCE = "camara"
DATASET = "plenario_apartes"
CAMARA_API_BASE_URL = "https://dadosabertos.camara.leg.br/"
SITAQ_BASE_URL = "https://www.camara.leg.br/"
SITAQ_PATH = "internet/SitaqWeb/ResultadoPesquisaDiscursos.asp"
RECORD_TYPE = "sitaq_apartes_search_page"
YEAR_PROBE_RECORD_TYPE = "sitaq_apartes_year_probe"
QUARTER_PROBE_RECORD_TYPE = "sitaq_apartes_quarter_probe"
PAGE_SIZE = 50


def collect() -> None:
    parser = build_parser("Coleta metadados de apartes do Plenario da Camara via Banco de Discursos/Sitaq.")
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
        with OpenDataClient(CAMARA_API_BASE_URL) as api_client:
            deputados = discover_deputados(api_client, runtime.data_inicio, runtime.data_fim, run, periodo_total)
        stats["deputados_descobertos"] = len(deputados)
        if runtime.sample and runtime.sample_limit is not None:
            deputados = deputados[: runtime.sample_limit]
        stats["deputados_selecionados"] = len(deputados)
        run.log("deputados_loaded", total=stats["deputados_descobertos"], selecionados=len(deputados))

        with OpenDataClient(SITAQ_BASE_URL) as sitaq_client:
            for partition, start, end in windows:
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue
                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    run.log("partition_started", partition=partition, periodo=periodo, deputados=len(deputados))
                    for deputado in deputados:
                        try:
                            page_stats = collect_apartes_deputado_adaptive(
                                sitaq_client,
                                run,
                                deputado=deputado,
                                start=start,
                                end=end,
                                partition=partition,
                                periodo=periodo,
                            )
                            stats.update(page_stats)
                            stats["deputados_processados"] += 1
                            if page_stats.get("errors"):
                                errors += int(page_stats["errors"])
                                status = "completed_with_errors"
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            stats["errors"] += 1
                            run.log(
                                "deputado_apartes_failed",
                                partition=partition,
                                deputado_id=deputado.get("id"),
                                deputado_nome=deputado.get("nome"),
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


def discover_deputados(
    client: OpenDataClient,
    data_inicio: date,
    data_fim: date,
    run: CollectionRun,
    periodo: dict[str, str],
) -> list[dict[str, Any]]:
    params = {
        "dataInicio": data_inicio.isoformat(),
        "dataFim": data_fim.isoformat(),
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "nome",
    }
    deputados: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for page_index, page in enumerate(iter_camara_pages(client, "api/v2/deputados", params=params), start=1):
        run.write_record(
            partition="metadata",
            source_id=f"camara:deputados:apartes:{data_inicio.isoformat()}:{data_fim.isoformat()}:pagina:{page_index}",
            request={"method": "GET", "path": "api/v2/deputados", "params": params if page_index == 1 else {}},
            response=page.response_metadata,
            periodo=periodo,
            payload=page.data,
            record_type="deputados_apartes_metadata",
        )
        for item in _dados(page.data):
            deputado_id = str(item.get("id") or "").strip()
            nome = str(item.get("nome") or "").strip()
            if not deputado_id or not nome or deputado_id in seen_ids:
                continue
            deputados.append(item)
            seen_ids.add(deputado_id)
    if deputados:
        return deputados
    return discover_deputados_atuais(client, run, periodo)


def discover_deputados_atuais(
    client: OpenDataClient,
    run: CollectionRun,
    periodo: dict[str, str],
) -> list[dict[str, Any]]:
    params = {"itens": 100, "ordem": "ASC", "ordenarPor": "nome"}
    deputados: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for page_index, page in enumerate(iter_camara_pages(client, "api/v2/deputados", params=params), start=1):
        run.write_record(
            partition="metadata",
            source_id=f"camara:deputados:apartes:atual:pagina:{page_index}",
            request={"method": "GET", "path": "api/v2/deputados", "params": params if page_index == 1 else {}},
            response=page.response_metadata,
            periodo=periodo,
            payload=page.data,
            record_type="deputados_apartes_atual_metadata",
        )
        for item in _dados(page.data):
            deputado_id = str(item.get("id") or "").strip()
            nome = str(item.get("nome") or "").strip()
            if not deputado_id or not nome or deputado_id in seen_ids:
                continue
            deputados.append(item)
            seen_ids.add(deputado_id)
    return deputados


def collect_apartes_deputado_adaptive(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    partition: str,
    periodo: dict[str, str],
) -> Counter[str]:
    stats: Counter[str] = Counter()
    try:
        probe_status, probe_written = collect_apartes_deputado_year_probe(
            client,
            run,
            deputado=deputado,
            start=start,
            end=end,
            periodo=periodo,
        )
        stats["year_probes"] += int(probe_written)
        stats[f"year_probe_{probe_status}"] += 1
        if probe_status == "zero":
            return stats
    except Exception as exc:
        stats["errors"] += 1
        stats["year_probe_errors"] += 1
        run.log(
            "deputado_apartes_year_probe_failed",
            partition=partition,
            deputado_id=deputado.get("id"),
            deputado_nome=deputado.get("nome"),
            error=error_summary(exc),
        )

    stats.update(
        collect_apartes_deputado_quarters(
            client,
            run,
            deputado=deputado,
            start=start,
            end=end,
            partition=partition,
        )
    )
    return stats


def collect_apartes_deputado_quarters(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    partition: str,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    for quarter_partition, quarter_start, quarter_end in quarter_windows(start, end):
        quarter_periodo = {"data_inicio": quarter_start.isoformat(), "data_fim": quarter_end.isoformat()}
        try:
            probe_status, probe_written = collect_apartes_deputado_probe(
                client,
                run,
                deputado=deputado,
                start=quarter_start,
                end=quarter_end,
                periodo=quarter_periodo,
                record_type=QUARTER_PROBE_RECORD_TYPE,
                probe_label="quarter-probe",
            )
            stats["quarter_probes"] += int(probe_written)
            stats[f"quarter_probe_{probe_status}"] += 1
            if probe_status == "zero":
                continue
        except Exception as exc:
            stats["errors"] += 1
            stats["quarter_probe_errors"] += 1
            run.log(
                "deputado_apartes_quarter_probe_failed",
                partition=partition,
                quarter_partition=quarter_partition,
                deputado_id=deputado.get("id"),
                deputado_nome=deputado.get("nome"),
                error=error_summary(exc),
            )

        stats.update(
            collect_apartes_deputado_months(
                client,
                run,
                deputado=deputado,
                start=quarter_start,
                end=quarter_end,
                partition=partition,
                parent_partition=quarter_partition,
            )
        )
    return stats


def collect_apartes_deputado_months(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    partition: str,
    parent_partition: str,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    for month_partition, month_start, month_end in month_windows(start, end):
        month_periodo = {"data_inicio": month_start.isoformat(), "data_fim": month_end.isoformat()}
        try:
            page_stats = collect_apartes_deputado(
                client,
                run,
                deputado=deputado,
                start=month_start,
                end=month_end,
                partition=month_partition,
                periodo=month_periodo,
            )
            stats.update(page_stats)
            stats["months_expanded"] += 1
        except Exception as exc:
            stats["errors"] += 1
            stats["month_errors"] += 1
            run.log(
                "deputado_apartes_month_failed",
                partition=partition,
                parent_partition=parent_partition,
                month_partition=month_partition,
                deputado_id=deputado.get("id"),
                deputado_nome=deputado.get("nome"),
                error=error_summary(exc),
            )
    return stats


def collect_apartes_deputado_year_probe(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    periodo: dict[str, str],
) -> tuple[str, bool]:
    return collect_apartes_deputado_probe(
        client,
        run,
        deputado=deputado,
        start=start,
        end=end,
        periodo=periodo,
        record_type=YEAR_PROBE_RECORD_TYPE,
        probe_label="year-probe",
    )


def collect_apartes_deputado_probe(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    periodo: dict[str, str],
    record_type: str,
    probe_label: str,
) -> tuple[str, bool]:
    deputado_id = str(deputado.get("id") or "").strip()
    nome = str(deputado.get("nome") or "").strip()
    if not nome:
        return "zero", False

    params = build_sitaq_params(nome, start, end, page=1)
    source_id = (
        f"camara:aparteante:{deputado_id or normaliza_source_id(nome)}:"
        f"{probe_label}:{start.isoformat()}:{end.isoformat()}:pagina:1"
    )
    already_recorded = run.has_record(source_id=source_id, record_type=record_type)
    result = client.get_text(SITAQ_PATH, params=params)
    total_pages = max(1, extract_total_pages(result.data))
    parsed = parse_sitaq_result_page(result.data)
    probe_status = classify_sitaq_probe(parsed, total_pages)
    if already_recorded:
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        return probe_status, False

    payload = {
        "html": result.data,
        "query": params,
        "aparteante_consultado": nome,
        "aparteante_id_consultado": deputado_id or None,
        "page_number": 1,
        "total_pages_detected": total_pages,
        "probe_label": probe_label,
        "probe_status": probe_status,
        **parsed,
    }
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": SITAQ_PATH, "params": params},
        response=result.response_metadata,
        periodo=periodo,
        payload=payload,
        record_type=record_type,
    )
    return probe_status, written


def collect_apartes_deputado(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    deputado: dict[str, Any],
    start: date,
    end: date,
    partition: str,
    periodo: dict[str, str],
) -> Counter[str]:
    stats: Counter[str] = Counter()
    deputado_id = str(deputado.get("id") or "").strip()
    nome = str(deputado.get("nome") or "").strip()
    if not nome:
        return stats

    first_params = build_sitaq_params(nome, start, end, page=1)
    first_result = client.get_text(SITAQ_PATH, params=first_params)
    total_pages = max(1, extract_total_pages(first_result.data))
    for page_number in range(1, total_pages + 1):
        params = first_params if page_number == 1 else build_sitaq_params(nome, start, end, page=page_number)
        if page_number == 1:
            result = first_result
        else:
            result = client.get_text(SITAQ_PATH, params=params)
        source_id = (
            f"camara:aparteante:{deputado_id or normaliza_source_id(nome)}:"
            f"{start.isoformat()}:{end.isoformat()}:pagina:{page_number}"
        )
        if run.has_record(source_id=source_id, record_type=RECORD_TYPE):
            run.log("record_resume_skipped", source_id=source_id, record_type=RECORD_TYPE)
            stats["paginas_skipped"] += 1
            continue
        parsed = parse_sitaq_result_page(result.data)
        payload = {
            "html": result.data,
            "query": params,
            "aparteante_consultado": nome,
            "aparteante_id_consultado": deputado_id or None,
            "page_number": page_number,
            "total_pages_detected": total_pages,
            **parsed,
        }
        written = run.write_record(
            partition="metadata",
            source_id=source_id,
            request={"method": "GET", "path": SITAQ_PATH, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=payload,
            record_type=RECORD_TYPE,
        )
        stats["paginas_sitaq"] += int(written)
        stats["resultados_extraidos"] += len(parsed["chaves_extraidas"])
    return stats


def classify_sitaq_probe(parsed: dict[str, Any], total_pages: int) -> str:
    result_count_text = parsed.get("result_count_text")
    if result_count_text == "Nenhum discurso encontrado.":
        return "zero"
    if total_pages > 1 or parsed.get("chaves_extraidas") or result_count_text:
        return "positive"
    return "unknown"


def build_sitaq_params(nome: str, start: date, end: date, *, page: int) -> dict[str, Any]:
    return {
        "BasePesq": "plenario",
        "CampoOrdenacao": "dtSessao",
        "PageSize": PAGE_SIZE,
        "TipoOrdenacao": "ASC",
        "dtInicio": format_camara_date(start),
        "dtFim": format_camara_date(end),
        "txAparteante": nome,
        "txOrador": "",
        "txPartido": "",
        "txUF": "",
        "txSessao": "",
        "listaFaseSessao": "",
        "listaTipoFala": "",
        "listaTipoInterv": "",
        "listaTipoSessao": "",
        "listaEtapa": "",
        "inFalaPres": "",
        "txTexto": "",
        "txSumario": "",
        "txIndexacao": "",
        "CurrentPage": page,
    }


def parse_sitaq_result_page(html_text: str) -> dict[str, Any]:
    unescaped = html.unescape(html_text)
    return {
        "result_count_text": extract_result_count_text(unescaped),
        "chaves_extraidas": extract_texto_html_links(unescaped),
    }


def extract_texto_html_links(html_text: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    pattern = re.compile(r'href=["\'](?P<href>TextoHTML\.asp\?[^"\']+)["\']', re.IGNORECASE)
    for match in pattern.finditer(html_text):
        href = html.unescape(match.group("href")).replace("\n", "")
        parsed = urlparse(href)
        query = {key: values[-1].strip() for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
        key = discurso_chave(query)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "href": href,
                "discurso_chave": key,
                "nuSessao": query.get("nuSessao"),
                "nuQuarto": query.get("nuQuarto"),
                "nuOrador": query.get("nuOrador"),
                "nuInsercao": query.get("nuInsercao"),
                "Data": query.get("Data"),
                "sgFaseSessao": query.get("sgFaseSessao"),
                "txApelido": query.get("txApelido"),
                "txFaseSessao": query.get("txFaseSessao"),
                "txTipoSessao": query.get("txTipoSessao"),
                "dtHoraQuarto": query.get("dtHoraQuarto"),
            }
        )
    return links


def extract_total_pages(html_text: str) -> int:
    patterns = [
        r'name=["\']TotalPages["\']\s+value=["\'](?P<value>\d+)["\']',
        r'value=["\'](?P<value>\d+)["\']\s+name=["\']TotalPages["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            return int(match.group("value"))
    return 1


def extract_result_count_text(html_text: str) -> str | None:
    match = re.search(r"\d+\s+a\s+\d+\s+de\s+\d+\s+documentos? encontrados?", html_text, flags=re.IGNORECASE)
    if match:
        return " ".join(match.group(0).split())
    if "Nenhum discurso encontrado" in html_text:
        return "Nenhum discurso encontrado."
    return None


def discurso_chave(query: dict[str, str]) -> str:
    parts = [
        query.get("Data"),
        query.get("nuSessao"),
        query.get("nuQuarto"),
        query.get("nuOrador"),
        query.get("nuInsercao"),
        query.get("sgFaseSessao"),
    ]
    return "|".join((part or "").strip() for part in parts)


def format_camara_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def normaliza_source_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return normalized or "sem-nome"


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


if __name__ == "__main__":
    collect()
