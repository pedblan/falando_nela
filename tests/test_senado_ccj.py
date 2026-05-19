from __future__ import annotations

import json
from pathlib import Path

import httpx

from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun
from coleta.senado.ccj_notas.collect import (
    _ccj_reunioes,
    _collect_reuniao,
    build_notas_payload,
    extract_texto_notas,
)


def test_ccj_reunioes_reads_real_agenda_shape_and_filters_ccj() -> None:
    payload = {
        "AgendaReuniao": {
            "reunioes": {
                "reuniao": [
                    {
                        "codigo": "14657",
                        "colegiadoCriador": {
                            "codigo": "34",
                            "sigla": "CCJ",
                        },
                    },
                    {
                        "codigo": "999",
                        "colegiadoCriador": {
                            "codigo": "50",
                            "sigla": "CAE",
                        },
                    },
                    {
                        "codigo": "14658",
                        "colegiadoCriador": {
                            "codigo": "34",
                            "sigla": "ccj",
                        },
                    },
                ]
            }
        }
    }

    reunioes = _ccj_reunioes(payload)

    assert [item["codigo"] for item in reunioes] == ["14657", "14658"]


def test_extract_texto_notas_joins_quarter_texts() -> None:
    payload = {
        "notasTaquigraficas": {
            "quartos": [
                {"sequencia": "1", "texto": " Primeiro trecho. ", "linkAudio": "https://example.test/audio/1"},
                {"sequencia": "2", "texto": ""},
                {"sequencia": "3", "Texto": "Segundo trecho.", "LinkAudio": "https://example.test/audio/2"},
            ]
        }
    }

    texto = extract_texto_notas(payload)

    assert texto == "Primeiro trecho.\n\nSegundo trecho."


def test_build_notas_payload_text_contract() -> None:
    reuniao = {
        "codigo": "14657",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
    }
    notas = {
        "notasTaquigraficas": {
            "quartos": [
                {"texto": "Texto da reuniao.", "linkAudio": "https://example.test/audio/1"},
            ]
        }
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "14657",
                "titulo": "7a Reuniao Extraordinaria Semipresencial",
                "partes": {"itens": []},
            }
        }
    }

    payload = build_notas_payload("14657", reuniao, notas, detail_payload=detalhe)

    assert payload["CodigoReuniao"] == "14657"
    assert payload["codigo_reuniao"] == "14657"
    assert payload["TextoIntegral"] == "Texto da reuniao."
    assert payload["texto"] == "Texto da reuniao."
    assert payload["forma"] == "texto"
    assert payload["metodo_obtencao"] == "api_notas_reuniao"
    assert payload["texto_status"] == "disponivel"
    assert payload["metadata"]["agenda"] == reuniao
    assert payload["metadata"]["detalhe"]["titulo"] == "7a Reuniao Extraordinaria Semipresencial"
    assert "partes" not in payload["metadata"]["detalhe"]
    assert payload["fontes"]["notas_reuniao_api"].endswith(
        "/dadosabertos/taquigrafia/notas/reuniao/14657.json"
    )
    assert payload["fontes"]["audios"] == ["https://example.test/audio/1"]


def test_collect_reuniao_writes_detail_to_metadata_and_notes_to_monthly_corpus(tmp_path: Path) -> None:
    reuniao = {
        "codigo": "14657",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "14657",
                "titulo": "7a Reuniao Extraordinaria Semipresencial",
            }
        }
    }
    notas = {
        "notasTaquigraficas": {
            "quartos": [
                {"texto": "Texto oficial das notas.", "linkAudio": "https://example.test/audio/1"},
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dadosabertos/comissao/reuniao/14657.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/taquigrafia/notas/reuniao/14657.json":
            return httpx.Response(200, json=notas)
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2026-05",
        {"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        "14657",
        reuniao,
    )

    metadata_path = tmp_path / "raw" / "senado" / "ccj_notas" / "metadata" / "run-ccj.jsonl"
    corpus_path = tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2026" / "mes=05" / "run-ccj.jsonl"
    metadata_record = json.loads(metadata_path.read_text(encoding="utf-8"))
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert metadata_record["record_type"] == "reuniao_detalhe"
    assert metadata_record["partition"] == "metadata"
    assert corpus_record["record_type"] == "notas_taquigraficas"
    assert corpus_record["partition"] == "2026-05"
    assert corpus_record["payload"]["TextoIntegral"] == "Texto oficial das notas."
    assert corpus_record["payload"]["texto_status"] == "disponivel"
