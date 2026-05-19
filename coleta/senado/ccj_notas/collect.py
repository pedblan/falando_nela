from __future__ import annotations

import sys
import unicodedata
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, format_senado_date, month_windows
from coleta.common.documents import extract_text_from_html_bytes
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary, listify

SOURCE = "senado"
DATASET = "ccj_notas"
CCJ_SIGLA = "CCJ"
CCJ_CODIGO = "34"
BASE_URL = "https://legis.senado.leg.br/"
DETAIL_ENDPOINT = "dadosabertos/comissao/reuniao/{codigo}.json"
COMMITTEE_NOTES_ENDPOINT = "dadosabertos/comissao/reuniao/notas/{codigo}.json"
NOTES_ENDPOINT = "dadosabertos/taquigrafia/notas/reuniao/{codigo}.json"
NOTES_PUBLIC_URL = "https://www25.senado.leg.br/web/atividade/notas-taquigraficas/-/notas/r/{codigo}"
NOTES_NOT_FOUND_MESSAGE = "reuniao nao encontrada ou texto nao produzido pelo senado federal."


def collect() -> None:
    parser = build_parser("Coleta agenda, detalhes e notas taquigraficas da CCJ do Senado.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_reunioes = 0
    status = "completed"
    errors = 0

    try:
        with OpenDataClient(BASE_URL) as client:
            for partition, start, end in windows:
                if runtime.sample_limit is not None and processed_reunioes >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    endpoint = (
                        "dadosabertos/comissao/agenda/"
                        f"{format_senado_date(start)}/{format_senado_date(end)}.json"
                    )
                    params = {"v": 2}

                    run.log("partition_started", partition=partition, periodo=periodo)
                    agenda = client.get_json(endpoint, params=params)
                    run.write_record(
                        partition="metadata",
                        source_id=f"agenda:{format_senado_date(start)}:{format_senado_date(end)}",
                        request={"method": "GET", "path": endpoint, "params": params},
                        response=agenda.response_metadata,
                        periodo=periodo,
                        payload=agenda.data,
                        record_type="agenda_periodo",
                    )

                    ccj_reunioes = _ccj_reunioes(agenda.data)
                    for reuniao in ccj_reunioes:
                        if runtime.sample_limit is not None and processed_reunioes >= runtime.sample_limit:
                            run.log(
                                "sample_limit_reached",
                                sample_limit=runtime.sample_limit,
                                processed_reunioes=processed_reunioes,
                            )
                            break

                        codigo = _codigo_reuniao(reuniao)
                        if not codigo:
                            run.log("meeting_without_code", partition=partition, reuniao=reuniao)
                            continue
                        try:
                            _collect_reuniao(client, run, partition, periodo, codigo, reuniao)
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log(
                                "meeting_failed",
                                partition=partition,
                                codigo_reuniao=codigo,
                                error=error_summary(exc),
                            )
                            continue
                        processed_reunioes += 1

                    run.mark_partition_complete(partition, periodo=periodo, reunioes_ccj=len(ccj_reunioes))
                    run.log(
                        "partition_completed",
                        partition=partition,
                        reunioes_ccj=len(ccj_reunioes),
                        reunioes_processadas=processed_reunioes,
                    )
                except Exception as exc:
                    errors += 1
                    status = "completed_with_errors"
                    run.mark_partition_failed(
                        partition,
                        periodo=periodo,
                        error=error_summary(exc, include_traceback=True),
                    )
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
            ccj_codigo=CCJ_CODIGO,
            reunioes_processadas=processed_reunioes,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_reuniao(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    codigo: str,
    reuniao: dict[str, Any],
) -> None:
    detail_endpoint = DETAIL_ENDPOINT.format(codigo=codigo)
    notes_endpoint = NOTES_ENDPOINT.format(codigo=codigo)
    detail_payload: dict[str, Any] | None = None

    detail_source_id = f"reuniao:{codigo}:reuniao_detalhe"
    if run.has_record(source_id=detail_source_id, record_type="reuniao_detalhe"):
        run.log("record_resume_skipped", source_id=detail_source_id, record_type="reuniao_detalhe")
    else:
        try:
            detail = client.get_json(detail_endpoint, params={"v": 2})
        except httpx.HTTPStatusError as exc:
            run.log(
                "meeting_request_failed",
                codigo_reuniao=codigo,
                record_type="reuniao_detalhe",
                status_code=exc.response.status_code,
                url=str(exc.request.url),
            )
        else:
            detail_payload = detail.data if isinstance(detail.data, dict) else None
            run.write_record(
                partition="metadata",
                source_id=detail_source_id,
                request={"method": "GET", "path": detail_endpoint, "params": {"v": 2}},
                response=detail.response_metadata,
                periodo=periodo,
                payload=detail.data,
                record_type="reuniao_detalhe",
            )

    committee_notes_endpoint = COMMITTEE_NOTES_ENDPOINT.format(codigo=codigo)
    committee_notes_source_id = f"reuniao:{codigo}:notas_taquigraficas_metadata"
    notes_source_id = f"reuniao:{codigo}:notas_taquigraficas"
    has_text_record = run.has_record(source_id=notes_source_id, record_type="notas_taquigraficas")
    notes_attempts: list[dict[str, Any]] = []
    notes_request: dict[str, Any]
    notes_response: dict[str, Any]
    try:
        committee_notes = client.get_json(committee_notes_endpoint, params={"v": 1})
    except httpx.HTTPStatusError as exc:
        notes_attempts.append(
            {
                "metodo_obtencao": "api_comissao_reuniao_notas",
                "texto_status": "erro",
                "response": payload_response(exc),
            }
        )
        html_result = fetch_notas_html(client, codigo, url=None)
        notes_attempts.append(html_result["attempt"])
        if html_result["texto_status"] != "disponivel":
            run.log(
                "meeting_notes_absent",
                codigo_reuniao=codigo,
                api_status_code=exc.response.status_code,
                html_status_code=html_result["response"].get("status_code"),
                motivo=html_result["texto_status"],
            )
            return
        notes_data = html_result["payload"]
        notes_request = html_result["request"]
        notes_response = html_result["response"]
        metodo_obtencao = "pagina_notas_reuniao_html"
        texto_override = html_result["texto"]
    else:
        if run.has_record(source_id=committee_notes_source_id, record_type="notas_taquigraficas_metadata"):
            run.log(
                "record_resume_skipped",
                source_id=committee_notes_source_id,
                record_type="notas_taquigraficas_metadata",
            )
        else:
            run.write_record(
                partition="metadata",
                source_id=committee_notes_source_id,
                request={"method": "GET", "path": committee_notes_endpoint, "params": {"v": 1}},
                response=committee_notes.response_metadata,
                periodo=periodo,
                payload=committee_notes.data,
                record_type="notas_taquigraficas_metadata",
            )
        if has_text_record:
            run.log("record_resume_skipped", source_id=notes_source_id, record_type="notas_taquigraficas")
            return
        notes_attempts.append(
            {
                "metodo_obtencao": "api_comissao_reuniao_notas",
                "texto_status": "descoberto" if has_notas_taquigraficas(committee_notes.data) else "ausente",
                "response": committee_notes.response_metadata,
            }
        )
        if not has_notas_taquigraficas(committee_notes.data):
            run.log(
                "meeting_notes_absent",
                codigo_reuniao=codigo,
                api_status_code=committee_notes.status_code,
                motivo="indicador_notas_taquigraficas_N",
            )
            return

        notes_endpoint = NOTES_ENDPOINT.format(codigo=codigo)
        try:
            notes = client.get_json(notes_endpoint, params={"v": 1})
        except httpx.HTTPStatusError as exc:
            notes_attempts.append(
                {
                    "metodo_obtencao": "api_taquigrafia_notas_reuniao",
                    "texto_status": "erro",
                    "response": payload_response(exc),
                }
            )
            html_result = fetch_notas_html(client, codigo, url=public_notes_url(committee_notes.data))
            notes_attempts.append(html_result["attempt"])
            if html_result["texto_status"] != "disponivel":
                run.log(
                    "meeting_notes_absent",
                    codigo_reuniao=codigo,
                    api_status_code=exc.response.status_code,
                    html_status_code=html_result["response"].get("status_code"),
                    motivo=html_result["texto_status"],
                )
                return
            notes_data = html_result["payload"]
            notes_request = html_result["request"]
            notes_response = html_result["response"]
            metodo_obtencao = "pagina_notas_reuniao_html"
            texto_override = html_result["texto"]
        else:
            notes_attempts.append(
                {
                    "metodo_obtencao": "api_taquigrafia_notas_reuniao",
                    "texto_status": "disponivel",
                    "response": notes.response_metadata,
                }
            )
            notes_data = notes.data
            notes_request = {"method": "GET", "path": notes_endpoint, "params": {"v": 1}}
            notes_response = notes.response_metadata
            metodo_obtencao = "api_taquigrafia_notas_reuniao"
            texto_override = None

    payload = build_notas_payload(
        codigo,
        reuniao,
        notes_data,
        detail_payload=detail_payload,
        metodo_obtencao=metodo_obtencao,
        texto_override=texto_override,
        tentativas=notes_attempts,
    )
    if payload["texto_status"] != "disponivel":
        run.log("meeting_notes_without_text", codigo_reuniao=codigo, source_id=notes_source_id)
        return

    run.write_record(
        partition=partition,
        source_id=notes_source_id,
        request=notes_request,
        response=notes_response,
        periodo=periodo,
        payload=payload,
        record_type="notas_taquigraficas",
    )


def build_notas_payload(
    codigo: str,
    reuniao: dict[str, Any],
    notas_payload: Any,
    *,
    detail_payload: dict[str, Any] | None = None,
    metodo_obtencao: str = "api_taquigrafia_notas_reuniao",
    texto_override: str | None = None,
    tentativas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    texto = texto_override or extract_texto_notas(notas_payload) or None
    metadata: dict[str, Any] = {"agenda": reuniao}
    detalhe = extract_reuniao_detalhe(detail_payload)
    if detalhe:
        metadata["detalhe"] = detalhe

    payload = {
        "CodigoReuniao": codigo,
        "codigo_reuniao": codigo,
        "TextoIntegral": texto,
        "texto": texto,
        "forma": "texto" if texto else "sem_texto",
        "metodo_obtencao": metodo_obtencao,
        "texto_status": "disponivel" if texto else "ausente",
        "metadata": metadata,
        "fontes": build_fontes_reuniao(codigo, notas_payload),
        "notas_taquigraficas": notas_payload,
    }
    if tentativas:
        payload["tentativas_texto"] = tentativas
    return payload


def fetch_notas_html(client: OpenDataClient, codigo: str, *, url: str | None) -> dict[str, Any]:
    url = url or NOTES_PUBLIC_URL.format(codigo=codigo)
    request = {"method": "GET", "path": url, "params": {}}
    try:
        result = client.get_bytes(url)
    except httpx.HTTPStatusError as exc:
        response = payload_response(exc)
        return {
            "request": request,
            "response": response,
            "payload": {},
            "texto": None,
            "texto_status": "erro",
            "attempt": {
                "metodo_obtencao": "pagina_notas_reuniao_html",
                "texto_status": "erro",
                "response": response,
            },
        }

    content = result.data if isinstance(result.data, bytes) else b""
    texto = extract_texto_notas_html(content)
    texto_status = "disponivel" if texto else "ausente"
    payload = {
        "paginaNotasTaquigraficas": {
            "url": result.url,
            "texto": texto,
        }
    }
    return {
        "request": request,
        "response": result.response_metadata,
        "payload": payload,
        "texto": texto,
        "texto_status": texto_status,
        "attempt": {
            "metodo_obtencao": "pagina_notas_reuniao_html",
            "texto_status": texto_status,
            "response": result.response_metadata,
        },
    }


def extract_texto_notas_html(content: bytes) -> str:
    text = extract_text_from_html_bytes(content)
    if not text or NOTES_NOT_FOUND_MESSAGE in _normalize_for_match(text):
        return ""

    normalized_text = _normalize_for_match(text)
    start_markers = ["horario\ntexto com revisao", "texto com revisao"]
    start = -1
    for marker in start_markers:
        start = normalized_text.find(marker)
        if start != -1:
            start += len(marker)
            break
    if start == -1:
        start = normalized_text.rfind("notas taquigraficas")
        if start != -1:
            start += len("notas taquigraficas")
    if start == -1:
        return ""

    end = text.find("\nENGLISH", start)
    body = text[start:end if end != -1 else None].strip()
    return body if looks_like_transcript(body) else ""


def looks_like_transcript(text: str) -> bool:
    markers = ["O SR.", "A SRA.", "O SENADOR", "A SENADORA", "PRESIDENTE"]
    normalized = text.upper()
    return any(marker in normalized for marker in markers)


def has_notas_taquigraficas(payload: Any) -> bool:
    notas = _first(payload, "NotasTaquigraficasReuniao", "notasTaquigraficasReuniao")
    source = notas if isinstance(notas, dict) else payload
    indicador = _first(source, "IndicadorNotasTaquigraficas", "indicadorNotasTaquigraficas")
    return isinstance(indicador, str) and indicador.strip().upper() == "S"


def public_notes_url(payload: Any) -> str | None:
    notas = _first(payload, "NotasTaquigraficasReuniao", "notasTaquigraficasReuniao")
    source = notas if isinstance(notas, dict) else payload
    url = _first(source, "UrlNotasTaquigraficas", "urlNotasTaquigraficas")
    return url if isinstance(url, str) and url else None


def extract_texto_notas(payload: Any) -> str:
    fragments: list[str] = []
    for quarto in extract_quartos(payload):
        texto = _first(quarto, "texto", "Texto", "transcricao", "Transcricao", "conteudo", "Conteudo")
        if isinstance(texto, str) and texto.strip():
            fragments.append(texto.strip())
    return "\n\n".join(fragments)


def build_fontes_reuniao(codigo: str, notas_payload: Any) -> dict[str, Any]:
    audio_links: list[str] = []
    for quarto in extract_quartos(notas_payload):
        link_audio = _first(quarto, "linkAudio", "LinkAudio", "urlAudio", "UrlAudio")
        if isinstance(link_audio, str) and link_audio and link_audio not in audio_links:
            audio_links.append(link_audio)
    return {
        "reuniao_detalhe_api": BASE_URL + DETAIL_ENDPOINT.format(codigo=codigo),
        "comissao_reuniao_notas_api": BASE_URL + COMMITTEE_NOTES_ENDPOINT.format(codigo=codigo),
        "notas_reuniao_api": BASE_URL + NOTES_ENDPOINT.format(codigo=codigo),
        "notas_reuniao_html": NOTES_PUBLIC_URL.format(codigo=codigo),
        "audios": audio_links,
    }


def extract_quartos(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    notas = _first(payload, "notasTaquigraficas", "NotasTaquigraficas")
    source = notas if isinstance(notas, dict) else payload
    quartos = _first(source, "quartos", "Quartos", "quarto", "Quarto")
    if isinstance(quartos, dict):
        quartos = _first(quartos, "quarto", "Quarto") or quartos
    return [item for item in listify(quartos) if isinstance(item, dict)]


def extract_reuniao_detalhe(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    detalhe = _first(payload, "DetalheReuniao", "detalheReuniao")
    if not isinstance(detalhe, dict):
        return None
    reuniao = _first(detalhe, "reuniao", "Reuniao")
    if not isinstance(reuniao, dict):
        return None
    return {key: value for key, value in reuniao.items() if key != "partes"}


def _ccj_reunioes(payload: Any) -> list[dict[str, Any]]:
    agenda = _first(payload, "AgendaReuniao", "agendaReuniao") or {}
    reunioes = _first(agenda, "reunioes", "Reunioes") or {}
    items = _first(reunioes, "reuniao", "Reuniao") if isinstance(reunioes, dict) else reunioes
    return [item for item in listify(items) if isinstance(item, dict) and _is_ccj(item)]


def _is_ccj(reuniao: dict[str, Any]) -> bool:
    colegiado = _first(reuniao, "colegiadoCriador", "Colegiado", "colegiado") or {}
    sigla = _first(colegiado, "sigla", "Sigla")
    codigo = _first(colegiado, "codigo", "Codigo")
    return _normalize_sigla(sigla) == CCJ_SIGLA or str(codigo).strip() == CCJ_CODIGO


def _codigo_reuniao(reuniao: dict[str, Any]) -> str | None:
    codigo = _first(reuniao, "codigo", "Codigo", "codigoReuniao", "CodigoReuniao")
    return str(codigo) if codigo is not None else None


def _first(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _normalize_sigla(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().upper()


def _normalize_for_match(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def payload_response(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    return {
        "url": str(exc.request.url),
        "status_code": exc.response.status_code,
        "headers": {
            key: value
            for key, value in exc.response.headers.items()
            if key.lower() in {"content-type", "date", "link", "retry-after", "x-total-count"}
        },
    }


if __name__ == "__main__":
    collect()
