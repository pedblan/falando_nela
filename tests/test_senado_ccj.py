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
    extract_texto_notas_html,
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
    assert payload["metodo_obtencao"] == "api_taquigrafia_notas_reuniao"
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
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "14657",
            "IndicadorNotasTaquigraficas": "S",
            "UrlNotasTaquigraficas": "https://www25.senado.leg.br/web/atividade/notas-taquigraficas/-/notas/r/14657",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dadosabertos/comissao/reuniao/14657.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/14657.json":
            return httpx.Response(200, json=notas_metadata)
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
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert [record["record_type"] for record in metadata_records] == [
        "reuniao_detalhe",
        "notas_taquigraficas_metadata",
    ]
    assert all(record["partition"] == "metadata" for record in metadata_records)
    assert corpus_record["record_type"] == "notas_taquigraficas"
    assert corpus_record["partition"] == "2026-05"
    assert corpus_record["payload"]["TextoIntegral"] == "Texto oficial das notas."
    assert corpus_record["payload"]["texto_status"] == "disponivel"


def test_extract_texto_notas_html_discards_not_found_page() -> None:
    html = """
    <html><body>
      <h1>Notas Taquigraficas</h1>
      <p>Reuni\u00e3o n\u00e3o encontrada ou texto n\u00e3o produzido pelo Senado Federal.</p>
    </body></html>
    """.encode()

    assert extract_texto_notas_html(html) == ""


def test_collect_reuniao_falls_back_to_public_html_notes(tmp_path: Path) -> None:
    reuniao = {
        "codigo": "3925",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "3925",
                "titulo": "31a Reuniao Ordinaria",
            }
        }
    }
    html = """
    <html><body>
      <h1>Notas Taquigraficas</h1>
      <p>22/09/2015 - 31a - Comissao de Constituicao e Justica</p>
      <p>Horario</p>
      <p>Texto com revisao</p>
      <p>10:35</p>
      <p>R</p>
      <p>O SR. PRESIDENTE - Declaro aberta a reuniao.</p>
    </body></html>
    """.encode()
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "3925",
            "IndicadorNotasTaquigraficas": "S",
            "UrlNotasTaquigraficas": "https://example.test/web/atividade/notas-taquigraficas/-/notas/r/3925",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dadosabertos/comissao/reuniao/3925.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/3925.json":
            return httpx.Response(200, json=notas_metadata)
        if request.url.path == "/dadosabertos/taquigrafia/notas/reuniao/3925.json":
            return httpx.Response(404, json={"status": 404})
        if request.url.path == "/web/atividade/notas-taquigraficas/-/notas/r/3925":
            return httpx.Response(200, content=html, headers={"Content-Type": "text/html"})
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-html",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2015-09",
        {"data_inicio": "2015-09-01", "data_fim": "2015-09-30"},
        "3925",
        reuniao,
    )

    corpus_path = tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2015" / "mes=09" / "run-ccj-html.jsonl"
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert corpus_record["record_type"] == "notas_taquigraficas"
    assert corpus_record["request"]["path"].endswith("/web/atividade/notas-taquigraficas/-/notas/r/3925")
    assert corpus_record["payload"]["metodo_obtencao"] == "pagina_notas_reuniao_html"
    assert corpus_record["payload"]["TextoIntegral"] == "10:35\nR\nO SR. PRESIDENTE - Declaro aberta a reuniao."
    assert [item["metodo_obtencao"] for item in corpus_record["payload"]["tentativas_texto"]] == [
        "api_comissao_reuniao_notas",
        "api_taquigrafia_notas_reuniao",
        "pagina_notas_reuniao_html",
    ]


def test_collect_reuniao_stores_metadata_without_corpus_when_indicator_is_no_and_sources_fail(
    tmp_path: Path,
) -> None:
    reuniao = {
        "codigo": "243",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
    }
    detalhe = {"DetalheReuniao": {"reuniao": {"codigo": "243"}}}
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "243",
            "IndicadorNotasTaquigraficas": "N",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dadosabertos/comissao/reuniao/243.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/243.json":
            return httpx.Response(200, json=notas_metadata)
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-no-notes",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2012-03",
        {"data_inicio": "2012-03-01", "data_fim": "2012-03-31"},
        "243",
        reuniao,
    )

    metadata_path = tmp_path / "raw" / "senado" / "ccj_notas" / "metadata" / "run-ccj-no-notes.jsonl"
    corpus_path = (
        tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2012" / "mes=03" / "run-ccj-no-notes.jsonl"
    )
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert [record["record_type"] for record in metadata_records] == [
        "reuniao_detalhe",
        "notas_taquigraficas_metadata",
        "notas_taquigraficas_status",
    ]
    assert metadata_records[1]["payload"]["NotasTaquigraficasReuniao"]["IndicadorNotasTaquigraficas"] == "N"
    assert metadata_records[2]["payload"]["motivo"] == "api_textual_erro_html_sem_texto"
    assert [item["metodo_obtencao"] for item in metadata_records[2]["payload"]["tentativas_texto"]] == [
        "api_comissao_reuniao_notas",
        "api_taquigrafia_notas_reuniao_forcado",
        "pagina_notas_reuniao_html",
    ]
    assert not corpus_path.exists()


def test_collect_reuniao_forces_text_api_until_2024_when_indicator_is_no(tmp_path: Path) -> None:
    reuniao = {
        "codigo": "11176",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
        "dataInicio": "2023-03-29T10:00:00",
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "11176",
                "titulo": "3a Reuniao Extraordinaria",
                "dataInicio": "2023-03-29T10:00:00.000",
            }
        }
    }
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "11176",
            "IndicadorNotasTaquigraficas": "N",
        }
    }
    notas = {
        "notasTaquigraficas": {
            "quartos": [
                {"sequencia": "1", "texto": "Texto recuperado apesar do indicador N."},
            ]
        }
    }
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/dadosabertos/comissao/reuniao/11176.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/11176.json":
            return httpx.Response(200, json=notas_metadata)
        if request.url.path == "/dadosabertos/taquigrafia/notas/reuniao/11176.json":
            return httpx.Response(200, json=notas)
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-forced",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2023-03",
        {"data_inicio": "2023-03-29", "data_fim": "2023-03-29"},
        "11176",
        reuniao,
    )

    corpus_path = tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2023" / "mes=03" / "run-ccj-forced.jsonl"
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert corpus_record["record_type"] == "notas_taquigraficas"
    assert corpus_record["source_id"] == "reuniao:11176:notas_taquigraficas"
    assert corpus_record["payload"]["TextoIntegral"] == "Texto recuperado apesar do indicador N."
    assert corpus_record["payload"]["metodo_obtencao"] == "api_taquigrafia_notas_reuniao_forcado"
    assert [item["metodo_obtencao"] for item in corpus_record["payload"]["tentativas_texto"]] == [
        "api_comissao_reuniao_notas",
        "api_taquigrafia_notas_reuniao_forcado",
    ]
    assert "/dadosabertos/taquigrafia/notas/reuniao/11176.json" in requested_paths
    assert "/web/atividade/notas-taquigraficas/-/notas/r/11176" not in requested_paths


def test_collect_reuniao_uses_html_when_forced_text_api_has_no_text(tmp_path: Path) -> None:
    reuniao = {
        "codigo": "11177",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
        "dataInicio": "2023-03-29T14:00:00",
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "11177",
                "titulo": "4a Reuniao Extraordinaria",
                "dataInicio": "2023-03-29T14:00:00.000",
            }
        }
    }
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "11177",
            "IndicadorNotasTaquigraficas": "N",
        }
    }
    notas_vazias = {"notasTaquigraficas": {"quartos": [{"sequencia": "1", "texto": ""}]}}
    html = """
    <html><body>
      <h1>Notas Taquigraficas</h1>
      <p>Horario</p>
      <p>Texto com revisao</p>
      <p>10:35</p>
      <p>R</p>
      <p>O SR. PRESIDENTE - Texto recuperado pela pagina publica.</p>
    </body></html>
    """.encode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dadosabertos/comissao/reuniao/11177.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/11177.json":
            return httpx.Response(200, json=notas_metadata)
        if request.url.path == "/dadosabertos/taquigrafia/notas/reuniao/11177.json":
            return httpx.Response(200, json=notas_vazias)
        if request.url.path == "/web/atividade/notas-taquigraficas/-/notas/r/11177":
            return httpx.Response(200, content=html, headers={"Content-Type": "text/html"})
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-forced-html",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2023-03",
        {"data_inicio": "2023-03-29", "data_fim": "2023-03-29"},
        "11177",
        reuniao,
    )

    corpus_path = (
        tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2023" / "mes=03" / "run-ccj-forced-html.jsonl"
    )
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert corpus_record["payload"]["metodo_obtencao"] == "pagina_notas_reuniao_html"
    assert corpus_record["payload"]["TextoIntegral"] == (
        "10:35\nR\nO SR. PRESIDENTE - Texto recuperado pela pagina publica."
    )
    assert [item["texto_status"] for item in corpus_record["payload"]["tentativas_texto"]] == [
        "ausente",
        "ausente",
        "disponivel",
    ]
    assert [item["metodo_obtencao"] for item in corpus_record["payload"]["tentativas_texto"]] == [
        "api_comissao_reuniao_notas",
        "api_taquigrafia_notas_reuniao_forcado",
        "pagina_notas_reuniao_html",
    ]


def test_collect_reuniao_does_not_force_text_api_after_2024_when_indicator_is_no(tmp_path: Path) -> None:
    reuniao = {
        "codigo": "15000",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
        "dataInicio": "2025-03-01T10:00:00",
    }
    detalhe = {
        "DetalheReuniao": {
            "reuniao": {
                "codigo": "15000",
                "dataInicio": "2025-03-01T10:00:00.000",
            }
        }
    }
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "15000",
            "IndicadorNotasTaquigraficas": "N",
        }
    }
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/dadosabertos/comissao/reuniao/15000.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/15000.json":
            return httpx.Response(200, json=notas_metadata)
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-no-probe-after-2024",
        resume=False,
    )

    _collect_reuniao(
        client,
        run,
        "2025-03",
        {"data_inicio": "2025-03-01", "data_fim": "2025-03-31"},
        "15000",
        reuniao,
    )

    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "ccj_notas"
        / "ano=2025"
        / "mes=03"
        / "run-ccj-no-probe-after-2024.jsonl"
    )
    metadata_path = (
        tmp_path / "raw" / "senado" / "ccj_notas" / "metadata" / "run-ccj-no-probe-after-2024.jsonl"
    )
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert "/dadosabertos/taquigrafia/notas/reuniao/15000.json" not in requested_paths
    assert "/web/atividade/notas-taquigraficas/-/notas/r/15000" not in requested_paths
    assert metadata_records[-1]["record_type"] == "notas_taquigraficas_status"
    assert metadata_records[-1]["payload"]["motivo"] == "indicador_notas_taquigraficas_N"
    assert not corpus_path.exists()


def test_resume_skips_existing_notes_status_without_requests(tmp_path: Path) -> None:
    seed = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-status-resume",
        resume=False,
    )
    seed.write_record(
        partition="metadata",
        source_id="reuniao:15000:notas_taquigraficas_status",
        request={"method": "GET", "path": "/old", "params": {}},
        response={"status_code": 200, "url": "https://example.test/old", "headers": {}},
        periodo={"data_inicio": "2025-03-01", "data_fim": "2025-03-31"},
        payload={"CodigoReuniao": "15000", "texto_status": "ausente"},
        record_type="notas_taquigraficas_status",
    )
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    resumed = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-status-resume",
        resume=True,
    )

    _collect_reuniao(
        client,
        resumed,
        "2025-03",
        {"data_inicio": "2025-03-01", "data_fim": "2025-03-31"},
        "15000",
        {"codigo": "15000", "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"}},
    )

    assert requested_paths == []


def test_resume_still_writes_notes_metadata_when_text_record_already_exists(tmp_path: Path) -> None:
    seed = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-resume",
        resume=False,
    )
    seed.write_record(
        partition="2026-05",
        source_id="reuniao:14657:notas_taquigraficas",
        request={"method": "GET", "path": "/old", "params": {}},
        response={"status_code": 200, "url": "https://example.test/old", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"CodigoReuniao": "14657", "TextoIntegral": "texto ja coletado"},
        record_type="notas_taquigraficas",
    )

    reuniao = {
        "codigo": "14657",
        "colegiadoCriador": {"codigo": "34", "sigla": "CCJ"},
    }
    detalhe = {"DetalheReuniao": {"reuniao": {"codigo": "14657"}}}
    notas_metadata = {
        "NotasTaquigraficasReuniao": {
            "CodigoReuniao": "14657",
            "IndicadorNotasTaquigraficas": "S",
            "UrlNotasTaquigraficas": "https://example.test/notas/14657",
        }
    }
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/dadosabertos/comissao/reuniao/14657.json":
            return httpx.Response(200, json=detalhe)
        if request.url.path == "/dadosabertos/comissao/reuniao/notas/14657.json":
            return httpx.Response(200, json=notas_metadata)
        if request.url.path == "/dadosabertos/taquigrafia/notas/reuniao/14657.json":
            return httpx.Response(500)
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    resumed = CollectionRun(
        tmp_path,
        source="senado",
        dataset="ccj_notas",
        run_id="run-ccj-resume",
        resume=True,
    )

    _collect_reuniao(
        client,
        resumed,
        "2026-05",
        {"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        "14657",
        reuniao,
    )

    metadata_path = tmp_path / "raw" / "senado" / "ccj_notas" / "metadata" / "run-ccj-resume.jsonl"
    corpus_path = tmp_path / "raw" / "senado" / "ccj_notas" / "ano=2026" / "mes=05" / "run-ccj-resume.jsonl"
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert metadata_records[-1]["record_type"] == "notas_taquigraficas_metadata"
    assert metadata_records[-1]["payload"]["NotasTaquigraficasReuniao"]["IndicadorNotasTaquigraficas"] == "S"
    assert "/dadosabertos/taquigrafia/notas/reuniao/14657.json" not in requested_paths
    assert len(corpus_path.read_text(encoding="utf-8").splitlines()) == 1
