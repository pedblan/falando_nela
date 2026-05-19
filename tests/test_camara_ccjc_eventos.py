from __future__ import annotations

import json
from pathlib import Path

import httpx

from coleta.camara.ccjc_eventos.collect import (
    _collect_event_escriba,
    _collect_event_pages,
    parse_escriba_html,
)
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun


ESCRIBA_HTML = """
<html>
  <body>
    <div class="contentTitle">
      <strong>Comissao de Constituicao e Justica e de Cidadania</strong><br />
      <strong>(Reuniao Deliberativa Extraordinaria)</strong><br />
      <span>Em 12 de Maio de 2026</span>
    </div>
    <table id="tabelaQuartos">
      <tbody>
        <tr id="quarto1">
          <td class="hora">
            <div>15:06</div>
            <div>
              <span title="Texto revisado">RF</span>
              <a href="javascript:abreAudio('https://imagem.camara.leg.br/audio/1');" title="Audio">audio</a>
              <a class="lnkVideo" urlVideo="plenario1_2026-05-12-15-06-50" href="#">video</a>
            </div>
          </td>
          <td class="justificado">
            <div>
              <div class="principalStyle">
                <a name="5074242"></a>
                <span><b><a href="http://www.camara.leg.br/Internet/Deputado/dep_Detalhe.asp?id=92102">O SR. PRESIDENTE</a></b>
                (Leur Lomanto Junior. Bloco/UNIAO - BA) - Declaro aberta a reuniao.</span>
              </div>
            </div>
            <div>
              <div class="intercorrenciaCentralizadoStyle">
                <span><i>(Pausa.)</i></span>
              </div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


def test_parse_escriba_html_extracts_header_segments_and_sources() -> None:
    event = {
        "id": 81996,
        "dataHoraInicio": "2026-05-12T15:07",
        "urlRegistro": "https://www.youtube.com/watch?v=t-vy6sYk9t4",
    }

    payload = parse_escriba_html(
        ESCRIBA_HTML,
        event=event,
        url="https://escriba.camara.leg.br/escriba-servicosweb/html/81996",
    )

    assert payload["CodigoEvento"] == 81996
    assert payload["texto_status"] == "disponivel"
    assert payload["metodo_obtencao"] == "scraping_escriba_html"
    assert "Declaro aberta a reuniao." in payload["TextoIntegral"]
    assert payload["metadata"]["cabecalho"]["linhas"][0] == "Comissao de Constituicao e Justica e de Cidadania"
    assert payload["quartos"][0]["horario"] == "15:06"
    assert payload["quartos"][0]["status_revisao"] == {"sigla": "RF", "descricao": "Texto revisado"}
    assert payload["segmentos"][0]["id_segmento"] == "5074242"
    assert payload["segmentos"][0]["orador"]["id_deputado"] == 92102
    assert payload["segmentos"][1]["tipo"] == "intercorrencia"
    assert payload["fontes"]["audios"] == ["https://imagem.camara.leg.br/audio/1"]
    assert payload["fontes"]["videos"] == ["plenario1_2026-05-12-15-06-50"]
    assert payload["fontes"]["urlRegistro"] == "https://www.youtube.com/watch?v=t-vy6sYk9t4"


def test_collect_event_pages_uses_api_as_index_and_respects_sample_limit(tmp_path: Path) -> None:
    response = {
        "dados": [
            {"id": 81990, "dataHoraInicio": "2026-05-12T15:38"},
            {"id": 81996, "dataHoraInicio": "2026-05-12T15:07"},
            {"id": 82014, "dataHoraInicio": "2026-05-13T10:52"},
        ],
        "links": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-pages", resume=False)

    events = _collect_event_pages(
        client,
        run,
        "2026-05",
        {"data_inicio": "2026-05-12", "data_fim": "2026-05-12"},
        sample=True,
        sample_limit=2,
    )

    metadata_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "metadata" / "run-pages.jsonl"
    records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert [event["id"] for event in events] == [81990, 81996]
    assert records[0]["record_type"] == "eventos_page"
    assert records[0]["request"]["path"] == "api/v2/orgaos/2003/eventos"


def test_collect_event_escriba_writes_html_status_and_monthly_notes(tmp_path: Path) -> None:
    event = {
        "id": 81996,
        "dataHoraInicio": "2026-05-12T15:07",
        "urlRegistro": "https://www.youtube.com/watch?v=t-vy6sYk9t4",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "escriba.camara.leg.br"
        return httpx.Response(200, text=ESCRIBA_HTML, headers={"Content-Type": "text/html;charset=UTF-8"})

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-escriba", resume=False)

    stats = _collect_event_escriba(
        client,
        run,
        "2026-05",
        {"data_inicio": "2026-05-12", "data_fim": "2026-05-12"},
        event,
    )

    metadata_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "metadata" / "run-escriba.jsonl"
    corpus_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "ano=2026" / "mes=05" / "run-escriba.jsonl"
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    corpus_record = json.loads(corpus_path.read_text(encoding="utf-8"))

    assert stats["status_records"] == 1
    assert stats["notas_disponiveis"] == 1
    assert [record["record_type"] for record in metadata_records] == ["escriba_html", "escriba_status"]
    assert metadata_records[0]["payload"]["html"] == ESCRIBA_HTML
    assert metadata_records[1]["payload"]["texto_status"] == "disponivel"
    assert corpus_record["record_type"] == "notas_taquigraficas"
    assert corpus_record["payload"]["TextoIntegral"]
    assert corpus_record["payload"]["fontes"]["escriba_pdf"].endswith("/pdf/81996?isTaquigrafia=false")


def test_collect_event_escriba_404_writes_status_without_corpus(tmp_path: Path) -> None:
    event = {"id": 82163, "dataHoraInicio": "2026-05-19T15:00", "situacao": "Convocada"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status": 404}, headers={"Content-Type": "application/json"})

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-404", resume=False)

    stats = _collect_event_escriba(
        client,
        run,
        "2026-05",
        {"data_inicio": "2026-05-19", "data_fim": "2026-05-19"},
        event,
    )

    metadata_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "metadata" / "run-404.jsonl"
    corpus_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "ano=2026" / "mes=05" / "run-404.jsonl"
    record = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert stats == {"status_records": 1, "notas_disponiveis": 0}
    assert record["record_type"] == "escriba_status"
    assert record["payload"]["texto_status"] == "ausente"
    assert record["payload"]["motivo"] == "escriba_404"
    assert not corpus_path.exists()


def test_collect_event_escriba_pre_2019_documents_gap_without_request(tmp_path: Path) -> None:
    event = {"id": 38849, "dataHoraInicio": "2015-05-05T14:55", "situacao": "Encerrada (Final)"}
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-pre-2019", resume=False)

    stats = _collect_event_escriba(
        client,
        run,
        "2015-05",
        {"data_inicio": "2015-05-01", "data_fim": "2015-05-31"},
        event,
    )

    metadata_path = tmp_path / "raw" / "camara" / "ccjc_eventos" / "metadata" / "run-pre-2019.jsonl"
    record = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert requested_urls == []
    assert stats == {"status_records": 1, "notas_disponiveis": 0}
    assert record["payload"]["texto_status"] == "fora_escopo"
    assert record["payload"]["motivo"] == "antes_de_2019"


def test_collect_event_escriba_resume_skips_existing_status(tmp_path: Path) -> None:
    seed = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-resume", resume=False)
    seed.write_record(
        partition="metadata",
        source_id="ccjc:evento:82163:escriba_status",
        request={"method": "GET", "path": "https://escriba.camara.leg.br/escriba-servicosweb/html/82163", "params": {}},
        response={"status_code": 404, "url": "https://escriba.camara.leg.br/escriba-servicosweb/html/82163", "headers": {}},
        periodo={"data_inicio": "2026-05-19", "data_fim": "2026-05-19"},
        payload={"evento_id": 82163, "texto_status": "ausente"},
        record_type="escriba_status",
    )
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(500)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    resumed = CollectionRun(tmp_path, source="camara", dataset="ccjc_eventos", run_id="run-resume", resume=True)

    stats = _collect_event_escriba(
        client,
        resumed,
        "2026-05",
        {"data_inicio": "2026-05-19", "data_fim": "2026-05-19"},
        {"id": 82163, "dataHoraInicio": "2026-05-19T15:00"},
    )

    assert requested_urls == []
    assert stats == {"status_records": 0, "notas_disponiveis": 0}
