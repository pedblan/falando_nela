from __future__ import annotations

from coleta.common.documents import DocumentTextResult
from coleta.camara.pareceres_pec.collect import (
    build_parecer_payload as build_camara_parecer_payload,
)
from coleta.camara.pareceres_pec.collect import (
    anotar_status_deliberativo,
    classificar_orgao_tramitacao,
    classificar_status_deliberativo as classificar_status_camara,
    is_parecer_tramitacao,
)
from coleta.senado.pareceres_pec.collect import (
    build_parecer_payload as build_senado_parecer_payload,
)
from coleta.senado.pareceres_pec.collect import (
    classificar_colegiado,
    classificar_documento_classe as classificar_documento_classe_senado,
    classificar_status_deliberativo as classificar_status_senado,
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
    avulso_sem_colegiado = {
        "id": 4,
        "siglaTipo": "AVULSO_PARECER",
        "descricaoTipo": "Avulso de parecer",
    }
    relatorio_vencido = {
        "id": 5,
        "siglaTipo": "RELATORIO",
        "descricaoTipo": "Relatorio Legislativo",
        "descricao": "Relatorio do Vencido",
        "siglaColegiadoRecebedor": "CCJ",
    }

    assert classificar_colegiado(parecer_ccj)["ambito"] == "ccj"
    assert classificar_colegiado(relatorio_plenario)["ambito"] == "plenario"
    assert classificar_colegiado(avulso_sem_colegiado)["ambito"] == "indeterminado"
    assert is_parecer_documento(parecer_ccj)
    assert is_parecer_documento(relatorio_plenario)
    assert is_parecer_documento(avulso_sem_colegiado)
    assert not is_parecer_documento(listagem)
    assert classificar_documento_classe_senado(relatorio_vencido) == "relatorio"
    assert classificar_status_senado(relatorio_vencido) == "vencido"


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
    assert payload["documento_classe"] == "parecer"
    assert payload["status_deliberativo"] == "proposto"
    assert payload["vencido"] is False


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
    voto_em_separado = {
        "siglaOrgao": "CCJC",
        "descricaoTramitacao": "Declaracao de Voto em Separado",
        "codTipoTramitacao": "431",
        "url": "https://example.test/voto",
    }
    parecer_vencedor_comissao_especial = {
        "siglaOrgao": "PEC17193",
        "descricaoTramitacao": "Designacao de Relator(a) Parcial",
        "codTipoTramitacao": "328",
        "despacho": "Parecer Vencedor, Dep. Marcos Rogerio, pela admissibilidade.",
        "url": "https://example.test/parecer-vencedor",
    }

    assert classificar_orgao_tramitacao(ccjc_parecer)["ambito"] == "ccj"
    assert classificar_orgao_tramitacao(parecer_vencedor_comissao_especial)["ambito"] == "comissao_especial"
    assert is_parecer_tramitacao(ccjc_parecer)
    assert is_parecer_tramitacao(ccjr_historica)
    assert is_parecer_tramitacao(voto_em_separado)
    assert is_parecer_tramitacao(parecer_vencedor_comissao_especial)
    assert classificar_status_camara(parecer_vencedor_comissao_especial) == "vencedor"
    assert not is_parecer_tramitacao(plen_sem_parecer)
    assert not is_parecer_tramitacao(parecer_sem_url)
    assert not is_parecer_tramitacao(requerimento_sobre_comissao)


def test_camara_marks_original_parecer_as_vencido_when_tramitacao_says_it_became_vote() -> None:
    original = {
        "siglaOrgao": "CCJC",
        "descricaoTramitacao": "Parecer do(a) Relator(a)",
        "codTipoTramitacao": "322",
        "despacho": "Parecer do Relator, Dep. Luiz Couto (PT-PB), pela inadmissibilidade.",
        "url": "https://example.test/parecer-original",
    }
    vencedor = {
        "siglaOrgao": "CCJC",
        "descricaoTramitacao": "Designacao de Relator(a) Parcial",
        "codTipoTramitacao": "328",
        "despacho": "Parecer Vencedor, Dep. Marcos Rogerio, pela admissibilidade.",
        "url": "https://example.test/parecer-vencedor",
    }
    aprovacao = {
        "siglaOrgao": "CCJC",
        "descricaoTramitacao": "Aprovacao",
        "codTipoTramitacao": "240",
        "despacho": (
            "Aprovado o Parecer Vencedor do Dep. Marcos Rogerio. "
            "O parecer do Relator, Dep. Luiz Couto, passou a constituir Voto em Separado."
        ),
    }

    anotadas = anotar_status_deliberativo([original, vencedor, aprovacao])

    assert classificar_status_camara(anotadas[0]) == "vencido"
    assert classificar_status_camara(anotadas[1]) == "vencedor"


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
    assert payload["documento_classe"] == "parecer"
    assert payload["status_deliberativo"] == "proposto"
    assert payload["vencido"] is False
