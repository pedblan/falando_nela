from __future__ import annotations

from coleta.common.documents import DocumentTextResult
from coleta.camara.pareceres_pec.collect import (
    build_parecer_payload as build_camara_parecer_payload,
)
from coleta.camara.pareceres_pec.collect import (
    classificar_orgao_tramitacao,
    is_parecer_tramitacao,
)
from coleta.senado.pareceres_pec.collect import (
    build_parecer_payload as build_senado_parecer_payload,
)
from coleta.senado.pareceres_pec.collect import (
    classificar_colegiado,
    is_parecer_documento,
)


def test_senado_filters_pareceres_pec_by_document_type_and_colegiado() -> None:
    parecer_ccj = {
        "id": 1,
        "siglaTipo": "PARECER",
        "descricaoTipo": "Parecer",
        "siglaColegiadoRecebedor": "CCJ",
        "nomeColegiadoRecebedor": "Comissao de Constituicao, Justica e Cidadania",
    }
    relatorio_plenario = {
        "id": 2,
        "siglaTipo": "RELATORIO",
        "descricaoTipo": "Relatorio Legislativo",
        "siglaColegiadoRecebedor": "PLEN",
        "nomeColegiadoRecebedor": "Plenario",
    }
    listagem = {
        "id": 3,
        "siglaTipo": "LISTAGEM_RELATORIO",
        "descricaoTipo": "Listagem de relatorios",
        "siglaColegiadoRecebedor": "CCJ",
    }

    assert classificar_colegiado(parecer_ccj)["ambito"] == "ccj"
    assert classificar_colegiado(relatorio_plenario)["ambito"] == "plenario"
    assert is_parecer_documento(parecer_ccj)
    assert is_parecer_documento(relatorio_plenario)
    assert not is_parecer_documento(listagem)


def test_senado_payload_keeps_text_separate_from_url() -> None:
    document_text = DocumentTextResult(
        request={"method": "GET", "path": "https://example.test/doc.pdf", "params": {}},
        response={"url": "https://example.test/doc.pdf", "status_code": 200, "headers": {}},
        text="texto do parecer",
        method="pdf_text_extraction",
        text_status="disponivel",
        fontes={"documento": "https://example.test/doc.pdf"},
        document={"sha256": "abc", "tamanho_bytes": 10},
        attempts=[],
    )

    payload = build_senado_parecer_payload(
        {"id": 10, "codigoMateria": 20, "identificacao": "PEC 1/2020"},
        {"id": 30, "siglaTipo": "PARECER", "siglaColegiadoRecebedor": "CCJ", "urlDocumento": "url-api"},
        document_text,
    )

    assert payload["TextoIntegral"] == "texto do parecer"
    assert payload["texto"] == "texto do parecer"
    assert payload["TextoIntegralUrl"] == "https://example.test/doc.pdf"
    assert payload["TextoIntegral"] != payload["TextoIntegralUrl"]
    assert payload["forma"] == "texto"
    assert payload["colegiado"]["ambito"] == "ccj"


def test_camara_filters_parecer_tramitacao_by_orgao_text_and_url() -> None:
    ccjc_parecer = {
        "siglaOrgao": "CCJC",
        "descricaoTramitacao": "Parecer do Relator",
        "url": "https://example.test/parecer",
    }
    ccjr_historica = {
        "siglaOrgao": "CCJR",
        "descricaoTramitacao": "Parecer do(a) Relator(a)",
        "despacho": "Aprovado parecer",
        "urlDocumento": "https://example.test/parecer-antigo",
    }
    plen_sem_parecer = {
        "siglaOrgao": "PLEN",
        "descricaoTramitacao": "Recebimento",
        "url": "https://example.test/documento",
    }
    parecer_sem_url = {
        "siglaOrgao": "PLEN",
        "descricaoTramitacao": "Parecer proferido em Plenario",
    }
    requerimento_sobre_comissao = {
        "siglaOrgao": "PLEN",
        "descricaoTramitacao": "Apresentacao de Requerimento",
        "despacho": "Comissao Especial destinada a proferir parecer a Proposta de Emenda a Constituicao",
        "url": "https://example.test/requerimento",
    }

    assert classificar_orgao_tramitacao(ccjc_parecer)["ambito"] == "ccj"
    assert is_parecer_tramitacao(ccjc_parecer)
    assert is_parecer_tramitacao(ccjr_historica)
    assert not is_parecer_tramitacao(plen_sem_parecer)
    assert not is_parecer_tramitacao(parecer_sem_url)
    assert not is_parecer_tramitacao(requerimento_sobre_comissao)


def test_camara_payload_keeps_each_parecer_document_as_text_record() -> None:
    document_text = DocumentTextResult(
        request={"method": "GET", "path": "https://example.test/prop", "params": {}},
        response={"url": "https://example.test/prop", "status_code": 200, "headers": {}},
        text="texto extraido",
        method="html_text_extraction",
        text_status="disponivel",
        fontes={"documento": "https://example.test/prop", "documento_resolvido": "https://example.test/doc.pdf"},
        document={"sha256": "abc", "tamanho_bytes": 10},
        attempts=[],
    )

    payload = build_camara_parecer_payload(
        {"id": 100, "siglaTipo": "PEC", "numero": 1, "ano": 2020, "uri": "uri-prop"},
        {"id": 100, "urlInteiroTeor": "url-pec"},
        {"siglaOrgao": "PLEN", "descricaoTramitacao": "Parecer proferido", "url": "url-parecer"},
        document_text,
    )

    assert payload["IdProposicao"] == 100
    assert payload["TextoIntegral"] == "texto extraido"
    assert payload["texto"] == "texto extraido"
    assert payload["TextoIntegralUrl"] == "https://example.test/prop"
    assert payload["fontes"]["documento_resolvido"] == "https://example.test/doc.pdf"
    assert payload["colegiado"]["ambito"] == "plenario"
