from __future__ import annotations

import sys
import unicodedata
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows
from coleta.common.documents import DocumentTextResult, download_and_extract_document
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary

SOURCE = "senado"
DATASET = "pareceres_pec"
BASE_URL = "https://legis.senado.leg.br/"
PROCESSO_ENDPOINT = "dadosabertos/processo"
DOCUMENTOS_ENDPOINT = "dadosabertos/processo/documento"
TIPOS_DOCUMENTO_PARECER = {"PARECER", "RELATORIO", "AVULSO_PARECER"}


def collect() -> None:
    parser = build_parser("Coleta pareceres e relatorios de PEC no Plenario e na CCJ do Senado.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_pareceres = 0
    status = "completed"
    errors = 0

    try:
        with OpenDataClient(BASE_URL) as client:
            for partition, start, end in windows:
                if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    params = {
                        "sigla": "PEC",
                        "dataInicioApresentacao": periodo["data_inicio"],
                        "dataFimApresentacao": periodo["data_fim"],
                        "v": 1,
                    }
                    run.log("partition_started", partition=partition, periodo=periodo)
                    processos_result = client.get_json(PROCESSO_ENDPOINT, params=params)
                    run.write_record(
                        partition="metadata",
                        source_id=f"senado:pec:processos:{partition}",
                        request={"method": "GET", "path": PROCESSO_ENDPOINT, "params": params},
                        response=processos_result.response_metadata,
                        periodo=periodo,
                        payload=processos_result.data,
                        record_type="pec_processos_metadata",
                    )

                    processos = extract_processos(processos_result.data)
                    pareceres_na_particao = 0
                    for processo in processos:
                        if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                            break
                        try:
                            pareceres = _collect_documentos_processo(client, run, partition, periodo, processo)
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("processo_failed", processo_id=processo.get("id"), error=error_summary(exc))
                            continue
                        for documento in pareceres:
                            if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                                break
                            url_documento = documento.get("urlDocumento")
                            if not isinstance(url_documento, str) or not url_documento:
                                run.log("parecer_without_document_url", processo=processo.get("id"), documento=documento)
                                continue
                            source_id = build_source_id(processo, documento)
                            if run.has_record(source_id=source_id, record_type="parecer_pec_texto"):
                                run.log("record_resume_skipped", source_id=source_id, record_type="parecer_pec_texto")
                                processed_pareceres += 1
                                continue
                            try:
                                document_text = download_and_extract_document(client, url_documento)
                                payload = build_parecer_payload(processo, documento, document_text)
                            except Exception as exc:
                                errors += 1
                                status = "completed_with_errors"
                                run.log("parecer_failed", source_id=source_id, error=error_summary(exc))
                                continue
                            run.write_record(
                                partition=partition,
                                source_id=source_id,
                                request=document_text.request,
                                response=document_text.response,
                                periodo=periodo,
                                payload=payload,
                                record_type="parecer_pec_texto",
                            )
                            processed_pareceres += 1
                            pareceres_na_particao += 1

                    run.mark_partition_complete(
                        partition,
                        periodo=periodo,
                        processos=len(processos),
                        pareceres_processados=pareceres_na_particao,
                    )
                    run.log(
                        "partition_completed",
                        partition=partition,
                        processos=len(processos),
                        pareceres_processados=pareceres_na_particao,
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
            tipos_documento_parecer=sorted(TIPOS_DOCUMENTO_PARECER),
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_documentos_processo(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    processo: dict[str, Any],
) -> list[dict[str, Any]]:
    processo_id = processo.get("id")
    if processo_id is None:
        run.log("processo_without_id", partition=partition, processo=processo)
        return []

    path = DOCUMENTOS_ENDPOINT
    params = {"idProcesso": processo_id, "v": 1}
    try:
        result = client.get_json(path, params=params)
    except httpx.HTTPStatusError as exc:
        run.log("processo_documentos_failed", processo_id=processo_id, status_code=exc.response.status_code)
        return []

    run.write_record(
        partition="metadata",
        source_id=f"senado:pec:processo:{processo_id}:documentos",
        request={"method": "GET", "path": path, "params": params},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type="pec_documentos_metadata",
    )
    return [documento for documento in extract_documentos(result.data) if is_parecer_documento(documento)]


def build_parecer_payload(
    processo: dict[str, Any],
    documento: dict[str, Any],
    document_text: DocumentTextResult,
) -> dict[str, Any]:
    texto = document_text.text.strip() or None
    colegiado = classificar_colegiado(documento)
    payload: dict[str, Any] = {
        "IdProcesso": processo.get("id"),
        "CodigoMateria": processo.get("codigoMateria"),
        "IdentificacaoPec": processo.get("identificacao"),
        "IdDocumento": documento.get("id"),
        "TextoIntegral": texto,
        "TextoIntegralUrl": document_text.fontes.get("documento"),
        "texto": texto,
        "forma": "texto" if texto else "documento",
        "metodo_obtencao": document_text.method,
        "texto_status": document_text.text_status,
        "colegiado": colegiado,
        "fontes": {
            "processo": processo.get("urlDocumento"),
            "documento_api": documento.get("urlDocumento"),
            **document_text.fontes,
        },
        "documento": document_text.document,
        "metadata": {
            "processo": processo,
            "documento": documento,
        },
        "tentativas_texto": document_text.attempts,
    }
    if document_text.error:
        payload["erro"] = document_text.error
    return payload


def extract_processos(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("dados", "processos", "Processos", "Materia"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def extract_documentos(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("dados", "documentos", "Documentos", "Documento"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [value]
    return []


def is_parecer_documento(documento: dict[str, Any]) -> bool:
    sigla_tipo = normalize_text(documento.get("siglaTipo"))
    descricao_tipo = normalize_text(documento.get("descricaoTipo"))
    if "LISTAGEM" in sigla_tipo or "LISTAGEM" in descricao_tipo:
        return False
    if sigla_tipo not in TIPOS_DOCUMENTO_PARECER and "PARECER" not in descricao_tipo:
        return False
    return classificar_colegiado(documento)["ambito"] in {"ccj", "plenario"}


def classificar_colegiado(documento: dict[str, Any]) -> dict[str, str | None]:
    sigla = documento.get("siglaColegiadoRecebedor") or documento.get("siglaColegiado") or ""
    nome = documento.get("nomeColegiadoRecebedor") or documento.get("nomeColegiado") or ""
    sigla_normalizada = normalize_text(sigla)
    nome_normalizado = normalize_text(nome)

    if sigla_normalizada == "CCJ" or "CONSTITUICAO" in nome_normalizado:
        ambito = "ccj"
    elif sigla_normalizada in {"PLEN", "PLENARIO"} or "PLENARIO" in nome_normalizado:
        ambito = "plenario"
    else:
        ambito = None

    return {
        "ambito": ambito,
        "sigla": str(sigla) if sigla else None,
        "nome": str(nome) if nome else None,
    }


def build_source_id(processo: dict[str, Any], documento: dict[str, Any]) -> str:
    processo_id = processo.get("id") or processo.get("codigoMateria") or "sem-processo"
    documento_id = documento.get("id") or documento.get("urlDocumento") or "sem-documento"
    return f"senado:pec:{processo_id}:documento:{documento_id}"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


if __name__ == "__main__":
    collect()
