from __future__ import annotations

import re
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
from coleta.common.io import CollectionRun, error_summary

SOURCE = "camara"
DATASET = "pareceres_pec"
BASE_URL = "https://dadosabertos.camara.leg.br/"
PROPOSICOES_ENDPOINT = "api/v2/proposicoes"
ORGAOS_CCJ = {"CCJC", "CCJR"}
ORGAOS_PLENARIO = {"PLEN"}
CODIGOS_TRAMITACAO_PARECER = {
    "322",
    "323",
    "324",
    "325",
    "326",
    "327",
    "328",
    "330",
    "335",
    "336",
    "431",
    "1040",
}
CODIGOS_TRAMITACAO_PARECER_COM_TEXTO_OBRIGATORIO = {"327", "328", "1040"}
AMBITOS_PARECER = {"ccj", "comissao_especial", "plenario"}
STATUS_DELIBERATIVOS = {"aprovado", "indeterminado", "proposto", "rejeitado", "vencedor", "vencido"}


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
                    run.log("partition_started", partition=partition, periodo=periodo)
                    proposicoes = _collect_pec_pages(client, run, partition, periodo, sample=runtime.sample)
                    pareceres_na_particao = 0

                    for proposicao in proposicoes:
                        if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                            break
                        proposicao_id = proposicao.get("id")
                        if proposicao_id is None:
                            continue
                        try:
                            detalhe = _collect_proposicao_detail(client, run, partition, periodo, int(proposicao_id))
                            tramitacoes = _collect_tramitacoes(client, run, partition, periodo, int(proposicao_id))
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("proposicao_failed", proposicao_id=proposicao_id, error=error_summary(exc))
                            continue
                        tramitacoes = anotar_status_deliberativo(tramitacoes)
                        pareceres = [item for item in tramitacoes if is_parecer_tramitacao(item)]

                        for tramitacao_index, tramitacao in enumerate(pareceres, start=1):
                            if runtime.sample_limit is not None and processed_pareceres >= runtime.sample_limit:
                                break
                            url_documento = tramitacao.get("url") or tramitacao.get("urlDocumento")
                            if not isinstance(url_documento, str) or not url_documento:
                                run.log("parecer_without_document_url", proposicao_id=proposicao_id, tramitacao=tramitacao)
                                continue
                            source_id = build_source_id(proposicao, tramitacao, tramitacao_index)
                            if run.has_record(source_id=source_id, record_type="parecer_pec_texto"):
                                run.log("record_resume_skipped", source_id=source_id, record_type="parecer_pec_texto")
                                processed_pareceres += 1
                                continue
                            try:
                                document_text = download_and_extract_document(client, url_documento)
                                payload = build_parecer_payload(proposicao, detalhe, tramitacao, document_text)
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
                        pecs=len(proposicoes),
                        pareceres_processados=pareceres_na_particao,
                    )
                    run.log(
                        "partition_completed",
                        partition=partition,
                        pecs=len(proposicoes),
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
            orgaos_ccj=sorted(ORGAOS_CCJ),
            orgaos_plenario=sorted(ORGAOS_PLENARIO),
            orgaos_comissao_especial_regex="PEC\\d+",
            codigos_tramitacao_parecer=sorted(CODIGOS_TRAMITACAO_PARECER),
            codigos_tramitacao_parecer_com_texto_obrigatorio=sorted(
                CODIGOS_TRAMITACAO_PARECER_COM_TEXTO_OBRIGATORIO
            ),
            ambitos_parecer=sorted(AMBITOS_PARECER),
            status_deliberativos=sorted(STATUS_DELIBERATIVOS),
            status=status,
            errors=errors,
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
    documento_classe = classificar_documento_classe(tramitacao, texto)
    status_deliberativo = classificar_status_deliberativo(tramitacao, texto)
    payload: dict[str, Any] = {
        "IdProposicao": proposicao.get("id") or detalhe.get("id"),
        "SiglaTipo": proposicao.get("siglaTipo") or detalhe.get("siglaTipo"),
        "Numero": proposicao.get("numero") or detalhe.get("numero"),
        "Ano": proposicao.get("ano") or detalhe.get("ano"),
        "documento_classe": documento_classe,
        "status_deliberativo": status_deliberativo,
        "vencido": status_deliberativo == "vencido",
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
    if classificar_orgao_tramitacao(tramitacao)["ambito"] not in AMBITOS_PARECER:
        return False
    url_documento = tramitacao.get("url") or tramitacao.get("urlDocumento")
    if not isinstance(url_documento, str) or not url_documento:
        return False
    descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
    despacho = normalize_text(tramitacao.get("despacho"))
    cod_tipo = str(tramitacao.get("codTipoTramitacao") or "")

    if is_tramitacao_excluida(tramitacao):
        return False
    if classificar_documento_classe(tramitacao) is None:
        return False
    if cod_tipo in CODIGOS_TRAMITACAO_PARECER_COM_TEXTO_OBRIGATORIO:
        return any(
            phrase in f"{descricao} {despacho}"
            for phrase in (
                "PARECER",
                "VOTO EM SEPARADO",
                "COMPLEMENTACAO DE VOTO",
                "RELATORIO",
            )
        )
    if cod_tipo in CODIGOS_TRAMITACAO_PARECER:
        return True
    return any(
        phrase in f"{descricao} {despacho}"
        for phrase in (
            "PARECER DO RELATOR",
            "PARECER DO(A) RELATOR(A)",
            "PARECER PROFERIDO",
            "PARECER AS EMENDAS",
            "PARECER A PROPOSTA",
            "PARECER VENCEDOR",
            "PARECER REFORMULADO",
            "COMPLEMENTACAO DE VOTO",
            "VOTO EM SEPARADO",
        )
    )


def is_tramitacao_excluida(tramitacao: dict[str, Any]) -> bool:
    descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
    despacho = normalize_text(tramitacao.get("despacho"))
    cod_tipo = str(tramitacao.get("codTipoTramitacao") or "")
    texto = f"{descricao} {despacho}"

    if "REQUERIMENTO" in descricao or cod_tipo == "194":
        return True
    if "CRIACAO DE COMISSAO" in descricao or "CRIA COMISSAO ESPECIAL" in texto:
        return True
    if "COMISSAO ESPECIAL DESTINADA A PROFERIR PARECER" in texto:
        return True
    return False


def classificar_documento_classe(tramitacao: dict[str, Any], texto: str | None = None) -> str | None:
    descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
    despacho = normalize_text(tramitacao.get("despacho"))
    texto_normalizado = normalize_text(texto)
    cod_tipo = str(tramitacao.get("codTipoTramitacao") or "")
    combined = f"{descricao} {despacho} {texto_normalizado}"

    if "VOTO EM SEPARADO" in combined or cod_tipo == "431":
        return "voto_em_separado"
    if "RELATORIO" in combined:
        return "relatorio"
    if "PARECER" in combined or "COMPLEMENTACAO DE VOTO" in combined:
        return "parecer"
    if cod_tipo in CODIGOS_TRAMITACAO_PARECER - CODIGOS_TRAMITACAO_PARECER_COM_TEXTO_OBRIGATORIO:
        return "parecer"
    return None


def classificar_status_deliberativo(tramitacao: dict[str, Any], texto: str | None = None) -> str:
    override = tramitacao.get("_status_deliberativo")
    if override in STATUS_DELIBERATIVOS:
        return str(override)

    descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
    despacho = normalize_text(tramitacao.get("despacho"))
    texto_normalizado = normalize_text(texto)
    combined = f"{descricao} {despacho} {texto_normalizado}"

    if "VENCID" in combined or "PASSOU A CONSTITUIR VOTO EM SEPARADO" in combined:
        return "vencido"
    if "PARECER VENCEDOR" in combined or "RELATOR DO VENCEDOR" in combined:
        return "vencedor"
    if "APROVADO O PARECER" in combined or "APROVACAO DO PARECER" in combined:
        return "aprovado"
    if "REJEICAO DO PARECER" in combined or "REJEITADO O PARECER" in combined:
        return "rejeitado"
    if classificar_documento_classe(tramitacao, texto) is not None:
        return "proposto"
    return "indeterminado"


def anotar_status_deliberativo(tramitacoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anotadas = [dict(item) for item in tramitacoes]
    for index, tramitacao in enumerate(anotadas):
        descricao = normalize_text(tramitacao.get("descricaoTramitacao"))
        despacho = normalize_text(tramitacao.get("despacho"))
        texto = f"{descricao} {despacho}"

        if "PARECER VENCEDOR" in texto or "RELATOR DO VENCEDOR" in texto:
            tramitacao.setdefault("_status_deliberativo", "vencedor")
        if "APROVADO O PARECER" in texto or "APROVACAO DO PARECER" in texto:
            tramitacao.setdefault("_status_deliberativo", "aprovado")
        if "REJEICAO DO PARECER" in texto or "REJEITADO O PARECER" in texto:
            tramitacao.setdefault("_status_deliberativo", "rejeitado")

        if "PASSOU A CONSTITUIR VOTO EM SEPARADO" not in texto:
            continue

        relator = extrair_nome_relator(texto)
        candidato = encontrar_parecer_vencido(anotadas[:index], relator=relator)
        if candidato is not None:
            candidato["_status_deliberativo"] = "vencido"
            candidato["_vencido_por_tramitacao"] = {
                "dataHora": tramitacao.get("dataHora"),
                "sequencia": tramitacao.get("sequencia"),
                "despacho": tramitacao.get("despacho"),
            }
    return anotadas


def encontrar_parecer_vencido(
    tramitacoes_anteriores: list[dict[str, Any]],
    *,
    relator: str | None,
) -> dict[str, Any] | None:
    candidatos = [
        item
        for item in tramitacoes_anteriores
        if is_parecer_tramitacao(item)
        and classificar_documento_classe(item) == "parecer"
        and classificar_status_deliberativo(item) != "vencedor"
    ]
    if relator:
        for item in reversed(candidatos):
            if relator in normalize_text(item.get("despacho")):
                return item
    return candidatos[-1] if candidatos else None


def extrair_nome_relator(texto_normalizado: str) -> str | None:
    match = re.search(
        r"PARECER DO(?:\(A\))? RELATOR(?:\(A\))?,?\s+"
        r"DEP(?:UTAD[OA])?\.?\s+([A-Z ]+?)(?:\s*\(|,|\.| PASSOU|$)",
        texto_normalizado,
    )
    if match is None:
        match = re.search(r"DEP(?:UTAD[OA])?\.?\s+([A-Z ]+?)(?:\s*\(|,|\.| PASSOU|$)", texto_normalizado)
    if match is None:
        return None
    nome = " ".join(match.group(1).split())
    return nome or None


def classificar_orgao_tramitacao(tramitacao: dict[str, Any]) -> dict[str, str | None]:
    sigla = tramitacao.get("siglaOrgao") or ""
    nome = tramitacao.get("uriOrgao") or tramitacao.get("nomeOrgao") or ""
    sigla_normalizada = normalize_text(sigla)
    nome_normalizado = normalize_text(nome)

    if sigla_normalizada in ORGAOS_CCJ or "CONSTITUICAO" in nome_normalizado:
        ambito = "ccj"
    elif sigla_normalizada in ORGAOS_PLENARIO or "PLENARIO" in nome_normalizado:
        ambito = "plenario"
    elif re.fullmatch(r"PEC\d+", sigla_normalizada):
        ambito = "comissao_especial"
    else:
        ambito = "indeterminado"

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
