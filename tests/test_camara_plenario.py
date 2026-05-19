from __future__ import annotations

import json
from pathlib import Path

import httpx

from coleta.camara.plenario_discursos.collect import _collect_deputados, _collect_discursos_deputado
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun


def test_collect_deputados_paginates_metadata_with_stable_page_ids(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados?dataInicio=2026-05-01&dataFim=2026-05-18&itens=100&ordem=ASC&ordenarPor=nome": {
            "dados": [{"id": 10}, {"id": 11}],
            "links": [{"rel": "next", "href": "https://example.test/api/v2/deputados?pagina=2"}],
        },
        "https://example.test/api/v2/deputados?pagina=2": {
            "dados": [{"id": 12}, {"id": 13}],
            "links": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[str(request.url)])

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    deputados = _collect_deputados(
        client,
        run,
        data_inicio="2026-05-01",
        data_fim="2026-05-18",
        sample=True,
    )

    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "run-test.jsonl"
    records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert [deputado["id"] for deputado in deputados] == [10, 11, 12]
    assert [record["source_id"] for record in records] == ["deputados:pagina:1", "deputados:pagina:2"]
    assert all(record["record_type"] == "deputados_page" for record in records)


def test_collect_discursos_deputado_writes_monthly_pages_and_counts_transcricoes(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados/10/discursos?dataInicio=2026-05-01&dataFim=2026-05-18&itens=100&ordem=ASC&ordenarPor=dataHoraInicio": {
            "dados": [
                {
                    "dataHoraInicio": "2026-05-02T10:00",
                    "transcricao": "texto integral do discurso",
                    "sumario": "resumo auxiliar",
                    "keywords": "palavras auxiliares",
                }
            ],
            "links": [{"rel": "next", "href": "https://example.test/api/v2/deputados/10/discursos?pagina=2"}],
        },
        "https://example.test/api/v2/deputados/10/discursos?pagina=2": {
            "dados": [{"dataHoraInicio": "2026-05-03T10:00", "sumario": "sem transcricao"}],
            "links": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[str(request.url)])

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    stats = _collect_discursos_deputado(
        client,
        run,
        partition="2026-05",
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        deputado_id=10,
    )

    raw_path = (
        tmp_path
        / "raw"
        / "camara"
        / "plenario_discursos"
        / "ano=2026"
        / "mes=05"
        / "run-test.jsonl"
    )
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]

    assert stats == {"pages": 2, "discursos": 2, "transcricoes": 1}
    assert [record["source_id"] for record in records] == [
        "deputado:10:discursos:2026-05:pagina:1",
        "deputado:10:discursos:2026-05:pagina:2",
    ]
    assert records[0]["periodo"] == {"data_inicio": "2026-05-01", "data_fim": "2026-05-18"}
    assert records[0]["record_type"] == "discursos_page"
    assert records[0]["payload"]["dados"][0]["transcricao"] == "texto integral do discurso"
    assert records[0]["payload"]["dados"][0]["sumario"] == "resumo auxiliar"
