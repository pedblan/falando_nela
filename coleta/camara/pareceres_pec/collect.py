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
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun

SOURCE = "camara"
DATASET = "pareceres_pec"
BASE_URL = "https://dadosabertos.camara.leg.br/"
PROPOSICOES_ENDPOINT = "api/v2/proposicoes"
ORGAOS_CCJ = {"CCJC", "CCJR"}
ORGAOS_PLENARIO = {"PLEN"}


def collect() -> None:
    parser = build_parser("Coleta pareceres de PEC no Plenario e na CCJC da Camara.")
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

    with OpenDataClient(BASE_URL) as client:
        for partition, start, end in windows:
            if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                break
            if run.should_skip_partition(partition):
                run.log("partition_skipped", partition=partition)
                continue

            periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
            run.log("partition_started", partition=partition, periodo=periodo)
            proposicoes = _collect_pec_pages(client, run, partition, periodo, sample=runtime.sample)
            pareceres_na_particao = 0

            for proposicao in proposicoes:
                if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                    break
                proposicao_id = proposicao.get("id")
                if proposicao_id is None:
                    continue
                detalhe = _collect_proposicao_detail(client, run, partition, periodo, int(proposicao_id))
                tramitacoes = _collect_tramitacoes(client, run, partition, periodo, int(proposicao_id))
                pareceres = [item for item in tramitacoes if is_parecer_tramitacao(item)]

                for tramitacao_index, tramitacao in enumerate(pareceres, start=1):
                    if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                        break
                    url_documento = tramitacao.get("url") or tramitacao.get("urlDocumento")
                    if not isinstance(url_documento, str) or not url_documento:
                        run.log("parecer_without_document_url", proposicao_id=proposicao_id, tramitacao=tramitacao)
                        continue
                    document_text = download_and_extract_document(client, url_documento)
                    payload = build_parecer_payload(proposicao, detalhe, tramitacao, document_text)
                    run.write_record(
                        partition=partition,
                        source_id=build_source_id(proposicao, tramitacao, tramitacao_index),
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
                pecs=len(proposicoes),
                pareceres_processados=pareceres_na_particao,
            )
            run.log(
                "partition_completed",
                partition=partition,
                pecs=len(proposicoes),
                pareceres_processados=pareceres_na_particao,
            )

    run.write_manifest(
        data_inicio=runtime.data_inicio.isoformat(),
        data_fim=runtime.data_fim.isoformat(),
        mode=runtime.mode,
        sample=runtime.sample,
        sample_limit=runtime.sample_limit,
        orgaos_ccj=sorted(ORGAOS_CCJ),
        orgaos_plenario=sorted(ORGAOS_PLENARIO),
    )
    print(run.manifest_path)


def _collect_pec_pages(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    *,
    sample: bool,
) -> list[dict[str, Any]]:
    params = {
        "siglaTipo": "PEC",
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
        "itens": 20 if sample else 100,
        "ordem": "ASC",
        "ordenarPor": "id",
    }
    proposicoes: list[dict[str, Any]] = []
    for page_index, result in enumerate(iter_camara_pages(client, PROPOSICOES_ENDPOINT, params=params), start=1):
        run.write_record(
            partition="metadata",
            source_id=f"camara:pec:proposicoes:{partition}:pagina:{page_index}",
            request={"method": "GET", "path": PROPOSICOES_ENDPOINT, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type="pec_proposicoes_metadata",
        )
        proposicoes.extend(_dados(result.data))
        if sample:
            break
    return proposicoes


def _collect_proposicao_detail(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    proposicao_id: int,
) -> dict[str, Any]:
    path = f"api/v2/proposicoes/{proposicao_id}"
    try:
        result = client.get_json(path)
    except httpx.HTTPStatusError as exc:
        run.log("proposicao_detail_failed", proposicao_id=proposicao_id, status_code=exc.response.status_code)
        return {}

    run.write_record(
        partition="metadata",
        source_id=f"camara:pec:proposicao:{proposicao_id}:detalhe",
        request={"method": "GET", "path": path, "params": {}},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type="pec_proposicao_detail",
    )
    return _dados_item(result.data)


def _collect_tramitacoes(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    proposicao_id: int,
) -> list[dict[str, Any]]:
    path = f"api/v2/proposicoes/{proposicao_id}/tramitacoes"
    params = {
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
    }
    tramitacoes: list[dict[str, Any]] = []
    try:
        pages = iter_camara_pages(client, path, params=params)
        for page_index, result in enumerate(pages, start=1):
            run.write_record(
                partition="metadata",
                source_id=f"camara:pec:proposicao:{proposicao_id}:tramitacoes:{partition}:pagina:{page_index}",
                request={"method": "GET", "path": path, "params": params},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="pec_tramitacoes_metadata",
            )
            tramitacoes.extend(_dados(result.data))
    except httpx.HTTPStatusError as exc:
        run.log("proposicao_tramitacoes_failed", proposicao_id=proposicao_id, status_code=exc.response.status_code)
    return tramitacoes


def build_parecer_payload(
    proposicao: dict[str, Any],
    detalhe: dict[str, Any],
    tramitacao: dict[str, Any],
    document_text: DocumentTextResult,
) -> dict[str, Any]:
    texto = document_text.text.strip() or None
    payload: dict[str, Any] = {
        "IdProposicao": proposicao.get("id") or detalhe.get("id"),
        "SiglaTipo": proposicao.get("siglaTipo") or detalhe.get("siglaTipo"),
        "Numero": proposicao.get("numero") or detalhe.get("numero"),
        "Ano": proposicao.get("ano") or detalhe.get("ano"),
        "TextoIntegral": texto,
        "TextoIntegralUrl": document_text.fontes.get("documento"),
        "texto": texto,
        "forma": "texto" if texto else "documento",
        "metodo_obtencao": document_text.method,
        "texto_status": document_text.text_status,
        "colegiado": classificar_orgao_tramitacao(tramitacao),
        "fontes": {
            "proposicao": proposicao.get("uri"),
            "proposicao_detalhe": detalhe.get("uri"),
            "inteiro_teor_proposicao": detalhe.get("urlInteiroTeor"),
            "documento_api": tramitacao.get("url") or tramitacao.get("urlDocumento"),
            **document_text.fontes,
        },
        "documento": document_text.document,
        "metadata": {
            "proposicao": proposicao,
            "detalhe": detalhe,
            "tramitacao": tramitacao,
        },
        "tentativas_texto": document_text.attempts,
    }
    if document_text.error:
        payload["erro"] = document_text.error
    return payload


def is_parecer_tramitacao(tramitacao: dict[str, Any]) -> bool:
    if classificar_orgao_tramitacao(tramitacao)["ambito"] not in {"ccj", "plenario"}:
        return False
    url_documento = tramitacao.get("url") or tramitacao.get("urlDocumento")
    if not isinstance(url_documento, str) or not url_documento:
        return False
    descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
    despacho = normalize_text(tramitacao.get("despacho"))
    cod_tipo = str(tramitacao.get("codTipoTramitacao") or "")

    if "PARECER" in descricao:
        return True
    if cod_tipo in {"322", "330", "336"}:
        return True
    if "REQUERIMENTO" in descricao:
        return False
    return any(
        phrase in despacho
        for phrase in (
            "PARECER DO RELATOR",
            "PARECER PROFERIDO",
            "PARECER AS EMENDAS",
            "PARECER A PROPOSTA",
        )
    )


def classificar_orgao_tramitacao(tramitacao: dict[str, Any]) -> dict[str, str | None]:
    sigla = tramitacao.get("siglaOrgao") or ""
    nome = tramitacao.get("uriOrgao") or tramitacao.get("nomeOrgao") or ""
    sigla_normalizada = normalize_text(sigla)
    nome_normalizado = normalize_text(nome)

    if sigla_normalizada in ORGAOS_CCJ or "CONSTITUICAO" in nome_normalizado:
        ambito = "ccj"
    elif sigla_normalizada in ORGAOS_PLENARIO or "PLENARIO" in nome_normalizado:
        ambito = "plenario"
    else:
        ambito = None

    return {
        "ambito": ambito,
        "sigla": str(sigla) if sigla else None,
        "nome": str(nome) if nome else None,
    }


def build_source_id(proposicao: dict[str, Any], tramitacao: dict[str, Any], index: int) -> str:
    proposicao_id = proposicao.get("id") or "sem-proposicao"
    data_hora = tramitacao.get("dataHora") or tramitacao.get("data") or f"ordem-{index}"
    return f"camara:pec:{proposicao_id}:tramitacao:{data_hora}:parecer:{index}"


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


def _dados_item(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    item = payload.get("dados", {})
    return item if isinstance(item, dict) else {}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


if __name__ == "__main__":
    collect()
