from __future__ import annotations

from contextlib import nullcontext
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence

import httpx

from coleta.common.cli import build_parser, runtime_config_from_namespace
from coleta.common.config import apply_sample_window, format_senado_date, month_windows
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary, listify
from coleta.senado.discursos_historicos import (
    PORTAL_BASE_URL,
    PortalDiscovery,
    discover_portal_pronunciamentos,
    merge_primary_and_portal,
)

SOURCE = "senado"
BASE_URL = "https://legis.senado.leg.br/"
TEXT_ENDPOINT = "dadosabertos/discurso/texto-integral/{codigo}"
SESSION_NOTES_ENDPOINT = "dadosabertos/taquigrafia/notas/sessao/{codigo_sessao}.json"
VIDEOS_SESSAO_ENDPOINT = "dadosabertos/taquigrafia/videos/sessao/{codigo_sessao}"
DISCOVERY_PERIOD_SESSION = "period-session"
DISCOVERY_HISTORICAL_OFFICIAL = "historical-official"
HISTORICAL_ADAPTER_VERSION = "portal-pronunciamentos-v1"


def collect_discursos(
    *,
    dataset: str,
    sigla_casa: str,
    description: str,
    argv: Sequence[str] | None = None,
) -> Path:
    parser = build_parser(description)
    parser.add_argument(
        "--discovery-strategy",
        choices=[DISCOVERY_PERIOD_SESSION, DISCOVERY_HISTORICAL_OFFICIAL],
        default=DISCOVERY_PERIOD_SESSION,
        help=(
            "period-session usa a lista mensal da API; historical-official reconcilia essa lista "
            "com o indice oficial de pronunciamentos do Senado."
        ),
    )
    args = parser.parse_args(argv)
    runtime = runtime_config_from_namespace(parser, args)
    discovery_strategy = str(args.discovery_strategy)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=dataset,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_pronunciamentos = 0
    status = "completed"
    errors = 0
    discovered_items = 0
    source_anomaly_partitions: list[str] = []
    empty_partitions: list[str] = []

    try:
        portal_context = (
            OpenDataClient(PORTAL_BASE_URL, min_interval_seconds=0.11)
            if discovery_strategy == DISCOVERY_HISTORICAL_OFFICIAL
            else nullcontext(None)
        )
        api_client_options = {"min_interval_seconds": 0.11} if discovery_strategy == DISCOVERY_HISTORICAL_OFFICIAL else {}
        with OpenDataClient(BASE_URL, **api_client_options) as client, portal_context as portal_client:
            for partition, start, end in windows:
                if runtime.sample_limit is not None and processed_pronunciamentos >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    endpoint = (
                        "dadosabertos/plenario/lista/discursos/"
                        f"{format_senado_date(start)}/{format_senado_date(end)}.json"
                    )
                    params = {"siglaCasa": sigla_casa, "v": 4}

                    run.log("partition_started", partition=partition, periodo=periodo)
                    result = client.get_json(endpoint, params=params)
                    run.write_record(
                        partition="metadata",
                        source_id=f"{sigla_casa}:{format_senado_date(start)}:{format_senado_date(end)}",
                        request={"method": "GET", "path": endpoint, "params": params},
                        response=result.response_metadata,
                        periodo=periodo,
                        payload=result.data,
                        record_type="discursos_periodo_metadata",
                    )

                    primary_pronunciamentos = extract_pronunciamentos(result.data)
                    if discovery_strategy == DISCOVERY_HISTORICAL_OFFICIAL:
                        if portal_client is None:
                            raise RuntimeError("Cliente do portal historico nao inicializado")
                        discovery = discover_portal_pronunciamentos(
                            portal_client,
                            start=start,
                            end=end,
                            limit=runtime.sample_limit if runtime.sample else None,
                        )
                        write_portal_raw_pages(
                            run,
                            discovery=discovery,
                            sigla_casa=sigla_casa,
                            partition=partition,
                            periodo=periodo,
                        )
                        pronunciamentos, discovery_audit = merge_primary_and_portal(
                            primary_pronunciamentos,
                            list(discovery.items),
                            sigla_casa=sigla_casa,
                            require_parity=not discovery.truncated,
                        )
                        discovered_items += len(pronunciamentos)
                        if discovery_audit["primary_empty_portal_nonempty"]:
                            source_anomaly_partitions.append(partition)
                        if not pronunciamentos:
                            empty_partitions.append(partition)
                        write_historical_discovery_summary(
                            run,
                            discovery=discovery,
                            discovery_audit=discovery_audit,
                            pronunciamentos=pronunciamentos,
                            sigla_casa=sigla_casa,
                            partition=partition,
                            periodo=periodo,
                        )
                        run.log(
                            "historical_discovery_completed",
                            partition=partition,
                            expected_portal=discovery.expected_count,
                            discovered_portal=discovery.discovered_count,
                            discovered_house=len(pronunciamentos),
                            source_anomaly=discovery_audit["primary_empty_portal_nonempty"],
                            truncated=discovery.truncated,
                        )
                    else:
                        pronunciamentos = primary_pronunciamentos
                        discovered_items += len(pronunciamentos)
                        if not pronunciamentos:
                            empty_partitions.append(partition)
                    partition_errors = 0
                    for item in pronunciamentos:
                        if runtime.sample_limit is not None and processed_pronunciamentos >= runtime.sample_limit:
                            run.log(
                                "sample_limit_reached",
                                sample_limit=runtime.sample_limit,
                                processed_pronunciamentos=processed_pronunciamentos,
                            )
                            break

                        codigo = item["codigo_pronunciamento"]
                        if not codigo:
                            run.log("pronunciamento_without_code", partition=partition, item=item)
                            continue

                        source_id = f"{sigla_casa}:pronunciamento:{codigo}"
                        if run.has_record(source_id=source_id, record_type="pronunciamento_texto"):
                            run.log("record_resume_skipped", source_id=source_id, record_type="pronunciamento_texto")
                            processed_pronunciamentos += 1
                            continue

                        try:
                            payload, text_request, text_response = fetch_pronunciamento_texto(client, item)
                        except Exception as exc:
                            errors += 1
                            partition_errors += 1
                            status = "completed_with_errors"
                            run.log(
                                "pronunciamento_failed",
                                partition=partition,
                                codigo_pronunciamento=codigo,
                                error=error_summary(exc),
                            )
                            continue

                        run.write_record(
                            partition=partition,
                            source_id=source_id,
                            request=text_request,
                            response=text_response,
                            periodo=periodo,
                            payload=payload,
                            record_type="pronunciamento_texto",
                        )
                        if should_enqueue_transcription(payload):
                            run.write_record(
                                partition="transcription_queue",
                                source_id=source_id,
                                request=text_request,
                                response=text_response,
                                periodo=periodo,
                                payload=payload,
                                record_type="transcription_queue",
                            )
                        processed_pronunciamentos += 1

                    if partition_errors:
                        run.mark_partition_failed(
                            partition,
                            periodo=periodo,
                            pronunciamentos_errors=partition_errors,
                        )
                        run.log(
                            "partition_completed_with_errors",
                            partition=partition,
                            pronunciamentos_disponiveis=len(pronunciamentos),
                            pronunciamentos_processados=processed_pronunciamentos,
                            pronunciamentos_errors=partition_errors,
                        )
                    else:
                        run.mark_partition_complete(partition, periodo=periodo)
                        run.log(
                            "partition_completed",
                            partition=partition,
                            pronunciamentos_disponiveis=len(pronunciamentos),
                            pronunciamentos_processados=processed_pronunciamentos,
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
            discovery_strategy=discovery_strategy,
            historical_adapter_version=(
                HISTORICAL_ADAPTER_VERSION
                if discovery_strategy == DISCOVERY_HISTORICAL_OFFICIAL
                else None
            ),
            discovered_items=discovered_items,
            source_anomaly_partitions=sorted(set(source_anomaly_partitions)),
            empty_partitions=sorted(set(empty_partitions)),
            status=status,
            errors=errors,
        )
        print(run.manifest_path)

    return run.manifest_path


def write_portal_raw_pages(
    run: CollectionRun,
    *,
    discovery: PortalDiscovery,
    sigla_casa: str,
    partition: str,
    periodo: dict[str, str],
) -> None:
    for page in discovery.pages:
        page_hash = sha256(page.url.encode("utf-8")).hexdigest()[:20]
        run.write_record(
            partition="metadata",
            source_id=f"{sigla_casa}:portal-page:{partition}:{page_hash}",
            request={"method": "GET", "url": page.url, "params": {}},
            response=page.response,
            periodo=periodo,
            payload={
                "kind": page.kind,
                "author": page.author,
                "page": page.page,
                "url": page.url,
                "html": page.html,
            },
            record_type="discursos_portal_page",
        )


def write_historical_discovery_summary(
    run: CollectionRun,
    *,
    discovery: PortalDiscovery,
    discovery_audit: dict[str, Any],
    pronunciamentos: list[dict[str, Any]],
    sigla_casa: str,
    partition: str,
    periodo: dict[str, str],
) -> None:
    ids = [str(item["codigo_pronunciamento"]) for item in pronunciamentos]
    run.write_record(
        partition="metadata",
        source_id=f"{sigla_casa}:historical-discovery:{partition}",
        request={
            "method": "COMPOSED_GET",
            "strategy": DISCOVERY_HISTORICAL_OFFICIAL,
            "adapter_version": HISTORICAL_ADAPTER_VERSION,
        },
        response={
            "portal_pages": len(discovery.pages),
            "portal_expected_count": discovery.expected_count,
            "portal_discovered_count": discovery.discovered_count,
        },
        periodo=periodo,
        payload={
            "strategy": DISCOVERY_HISTORICAL_OFFICIAL,
            "adapter_version": HISTORICAL_ADAPTER_VERSION,
            "house": sigla_casa,
            "partition": partition,
            "portal_expected_count_all_houses": discovery.expected_count,
            "portal_discovered_count_all_houses": discovery.discovered_count,
            "portal_duplicate_count": discovery.duplicate_count,
            "truncated": discovery.truncated,
            "audit": discovery_audit,
            "ids": ids,
            "items": pronunciamentos,
        },
        record_type="discursos_historical_discovery",
    )


def extract_pronunciamentos(payload: Any) -> list[dict[str, Any]]:
    sessoes = _get(payload, "DiscursosSessao", "Sessoes", "Sessao")
    items: list[dict[str, Any]] = []

    for sessao in listify(sessoes):
        if not isinstance(sessao, dict):
            continue
        sessao_metadata = {key: value for key, value in sessao.items() if key != "Pronunciamentos"}
        pronunciamentos = _get(sessao, "Pronunciamentos", "Pronunciamento")
        for pronunciamento in listify(pronunciamentos):
            if not isinstance(pronunciamento, dict):
                continue
            codigo = _first(pronunciamento, "CodigoPronunciamento", "id")
            items.append(
                {
                    "codigo_pronunciamento": str(codigo) if codigo is not None else None,
                    "metadata": {
                        "sessao": sessao_metadata,
                        "pronunciamento": pronunciamento,
                    },
                    "fontes": build_fontes(sessao_metadata, pronunciamento, codigo),
                }
            )
    return items


def fetch_pronunciamento_texto(
    client: OpenDataClient,
    item: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    codigo = item["codigo_pronunciamento"]
    endpoint = TEXT_ENDPOINT.format(codigo=codigo)
    request = {"method": "GET", "path": endpoint, "params": {}}
    tentativas: list[dict[str, Any]] = []

    try:
        result = client.get_text(endpoint)
    except httpx.HTTPStatusError as exc:
        text_response = payload_response(exc)
        tentativas.append(
            {
                "metodo_obtencao": "api_texto_integral",
                "texto_status": "erro",
                "response": text_response,
            }
        )
        session_payload = fetch_sessao_texto(client, item, tentativas)
        if session_payload:
            return session_payload
        payload = build_pronunciamento_payload(
            item,
            texto=None,
            forma="video",
            metodo_obtencao="pendente_transcricao_video",
            texto_status="erro",
            tentativas=tentativas,
        )
        return payload, request, text_response

    texto = result.data.strip() if isinstance(result.data, str) else ""
    if texto:
        payload = build_pronunciamento_payload(
            item,
            texto=texto,
            forma="texto",
            metodo_obtencao="api_texto_integral",
            texto_status="disponivel",
        )
    else:
        tentativas.append(
            {
                "metodo_obtencao": "api_texto_integral",
                "texto_status": "ausente",
                "response": result.response_metadata,
            }
        )
        session_payload = fetch_sessao_texto(client, item, tentativas)
        if session_payload:
            return session_payload
        payload = build_pronunciamento_payload(
            item,
            texto=None,
            forma="video",
            metodo_obtencao="pendente_transcricao_video",
            texto_status="ausente",
            tentativas=tentativas,
        )
    return payload, request, result.response_metadata


def fetch_sessao_texto(
    client: OpenDataClient,
    item: dict[str, Any],
    tentativas: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    endpoint = item["fontes"].get("notas_sessao_api")
    if not endpoint:
        return None

    request = {"method": "GET", "path": endpoint, "params": {}}
    try:
        result = client.get_json(endpoint)
    except httpx.HTTPStatusError as exc:
        tentativas.append(
            {
                "metodo_obtencao": "api_notas_sessao",
                "texto_status": "erro",
                "response": payload_response(exc),
            }
        )
        return None

    texto = extract_text_from_nested_payload(result.data)
    if not texto:
        tentativas.append(
            {
                "metodo_obtencao": "api_notas_sessao",
                "texto_status": "ausente",
                "response": result.response_metadata,
            }
        )
        return None

    payload = build_pronunciamento_payload(
        item,
        texto=texto,
        forma="texto",
        metodo_obtencao="api_notas_sessao",
        texto_status="disponivel",
        tentativas=tentativas,
    )
    return payload, request, result.response_metadata


def build_pronunciamento_payload(
    item: dict[str, Any],
    *,
    texto: str | None,
    forma: str,
    metodo_obtencao: str,
    texto_status: str,
    erro: dict[str, Any] | None = None,
    tentativas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "CodigoPronunciamento": item["codigo_pronunciamento"],
        "TextoIntegral": texto,
        "TextoIntegralUrl": item["fontes"].get("texto_integral_txt"),
        "codigo_pronunciamento": item["codigo_pronunciamento"],
        "metadata": item["metadata"],
        "texto": texto,
        "forma": forma,
        "metodo_obtencao": metodo_obtencao,
        "texto_status": texto_status,
        "fontes": item["fontes"],
    }
    if erro:
        payload["erro"] = erro
    if tentativas:
        payload["tentativas_texto"] = tentativas
    return payload


def build_fontes(
    sessao_metadata: dict[str, Any],
    pronunciamento: dict[str, Any],
    codigo: Any,
) -> dict[str, Any]:
    codigo_sessao = _first(sessao_metadata, "CodigoSessao", "codigoSessao")
    fontes = {
        "texto_integral_txt": _first(pronunciamento, "TextoIntegralTxt"),
        "texto_integral_html": _first(pronunciamento, "TextoIntegral"),
        "texto_binario": _first(pronunciamento, "UrlTextoBinario"),
        "video": _first(pronunciamento, "UrlVideo", "urlVideo"),
        "notas_sessao_api": None,
        "videos_sessao_api": None,
    }
    if codigo_sessao:
        fontes["notas_sessao_api"] = BASE_URL + SESSION_NOTES_ENDPOINT.format(codigo_sessao=codigo_sessao)
        fontes["videos_sessao_api"] = BASE_URL + VIDEOS_SESSAO_ENDPOINT.format(codigo_sessao=codigo_sessao)
    if not fontes["texto_integral_txt"] and codigo is not None:
        fontes["texto_integral_txt"] = BASE_URL + TEXT_ENDPOINT.format(codigo=codigo)
    return fontes


def should_enqueue_transcription(payload: dict[str, Any]) -> bool:
    if payload["texto_status"] == "disponivel":
        return False
    fontes = payload.get("fontes", {})
    return any(fontes.get(key) for key in ["video", "videos_sessao_api", "texto_binario"])


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


def extract_text_from_nested_payload(payload: Any) -> str:
    fragments: list[str] = []

    def walk(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                walk(child_value, child_key)
            return
        if isinstance(value, list):
            for child_value in value:
                walk(child_value, key)
            return
        if isinstance(value, str) and key and key.lower() in {"texto", "transcricao", "conteudo"}:
            stripped = value.strip()
            if stripped:
                fragments.append(stripped)

    walk(payload)
    return "\n\n".join(fragments)


def _get(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None
