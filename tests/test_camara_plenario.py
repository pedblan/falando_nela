from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from coleta.camara.plenario_discursos.collect import (
    _collect_deputados,
    _collect_discursos_deputado,
    _collect_discursos_deputado_adaptive,
    _collect_discursos_probe,
    _partial_resume_scan_years,
    inspect_checkpoint_resume_state,
    validate_clean_checkpoint_boundary,
)
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun


def _write_checkpoint_boundary(
    root: Path,
    *,
    log_events: list[dict[str, str]],
    failed: list[str] | None = None,
) -> None:
    run_id = "prod-historico-camara-plenario"
    checkpoint_path = root / "checkpoints" / "camara" / "plenario_discursos.json"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "runs": {
                    run_id: {
                        "completed_partitions": {"1998": {"run_id": run_id}},
                        "failed_partitions": {
                            partition: {"run_id": run_id}
                            for partition in (failed or [])
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    log_path = root / "logs" / f"{run_id}.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "\n".join(json.dumps({"run_id": run_id, **event}) for event in log_events) + "\n",
        encoding="utf-8",
    )


def test_checkpoint_boundary_allows_fast_resume_only_between_partitions(tmp_path: Path) -> None:
    run_id = "prod-historico-camara-plenario"
    _write_checkpoint_boundary(
        tmp_path,
        log_events=[
            {"event": "partition_started", "partition": "1900-11"},
            {"event": "partition_started", "partition": "1998"},
            {"event": "partition_completed", "partition": "1998"},
        ],
    )

    boundary = validate_clean_checkpoint_boundary(
        tmp_path,
        run_id=run_id,
        requested_partitions={"1998", "1999"},
    )

    assert boundary == {
        "checkpoint_boundary": "clean",
        "completed_partitions": 1,
        "unresolved_failed_partitions": [],
    }

    log_path = tmp_path / "logs" / f"{run_id}.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": run_id, "event": "partition_started", "partition": "1999"}) + "\n")

    state = inspect_checkpoint_resume_state(
        tmp_path,
        run_id=run_id,
        requested_partitions={"1998", "1999"},
    )
    assert state["open_partitions"] == ["1999"]
    assert _partial_resume_scan_years(state) == {"1999"}

    with pytest.raises(RuntimeError, match="particao iniciada sem conclusao"):
        validate_clean_checkpoint_boundary(
            tmp_path,
            run_id=run_id,
            requested_partitions={"1998", "1999"},
        )


def test_checkpoint_boundary_rejects_unresolved_failure(tmp_path: Path) -> None:
    run_id = "prod-historico-camara-plenario"
    _write_checkpoint_boundary(
        tmp_path,
        failed=["1999"],
        log_events=[
            {"event": "partition_started", "partition": "1998"},
            {"event": "partition_completed", "partition": "1998"},
            {"event": "partition_started", "partition": "1999"},
            {"event": "partition_failed", "partition": "1999"},
        ],
    )

    with pytest.raises(RuntimeError, match="particoes falhas nao resolvidas"):
        validate_clean_checkpoint_boundary(tmp_path, run_id=run_id)


def test_collect_deputados_paginates_metadata_with_stable_page_ids(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados?dataInicio=2026-05-01&dataFim=2026-05-18&itens=100&ordem=ASC&ordenarPor=nome": {
            "dados": [{"id": 10}, {"id": 11}, {"id": 10}],
            "links": [{"rel": "next", "href": "https://example.test/api/v2/deputados?pagina=2"}],
        },
        "https://example.test/api/v2/deputados?pagina=2": {
            "dados": [{"id": 11}, {"id": 12}, {"id": 13}],
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
    assert [record["source_id"] for record in records] == [
        "deputados:2026-05-01:2026-05-18:pagina:1",
        "deputados:2026-05-01:2026-05-18:pagina:2",
    ]
    assert all(record["record_type"] == "deputados_page" for record in records)
    assert all(record["periodo"] == {"data_inicio": "2026-05-01", "data_fim": "2026-05-18"} for record in records)


def test_collect_discursos_deputado_writes_monthly_pages_and_counts_transcricoes(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados/10/discursos?dataInicio=2026-05-01&dataFim=2026-05-18&itens=100&ordem=ASC&ordenarPor=dataHoraInicio": {
            "dados": [
                {
                    "dataHoraInicio": "2026-05-02T10:00",
                    "transcricao": "A SRA. CONCEIÇÃO SAMPAIO — ação, saúde e Constituição.",
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

    assert stats == {"pages": 2, "discursos": 2, "transcricoes": 1, "page_errors": 0}
    assert [record["source_id"] for record in records] == [
        "deputado:10:discursos:2026-05:pagina:1",
        "deputado:10:discursos:2026-05:pagina:2",
    ]
    assert records[0]["periodo"] == {"data_inicio": "2026-05-01", "data_fim": "2026-05-18"}
    assert records[0]["record_type"] == "discursos_page"
    assert records[0]["payload"]["dados"][0]["transcricao"] == (
        "A SRA. CONCEIÇÃO SAMPAIO — ação, saúde e Constituição."
    )
    assert records[0]["payload"]["dados"][0]["sumario"] == "resumo auxiliar"


def test_collect_discursos_adaptive_stops_after_empty_year_probe(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados/10/discursos?dataInicio=1946-01-01&dataFim=1946-12-31&itens=1&ordem=ASC&ordenarPor=dataHoraInicio": {
            "dados": [],
            "links": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[str(request.url)])

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    stats = _collect_discursos_deputado_adaptive(
        client,
        run,
        deputado_id=10,
        start=date(1946, 1, 1),
        end=date(1946, 12, 31),
        partition="1946",
        periodo={"data_inicio": "1946-01-01", "data_fim": "1946-12-31"},
    )

    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "run-test.jsonl"
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert stats["pages"] == 0
    assert stats["discursos"] == 0
    assert stats["preflight"]["year_probe_zero"] == 1
    assert [record["record_type"] for record in metadata_records] == ["discursos_year_probe"]
    assert not list((tmp_path / "raw" / "camara" / "plenario_discursos").glob("ano=*/mes=*/run-test.jsonl"))


def test_collect_discursos_adaptive_expands_positive_quarter_to_months(tmp_path: Path) -> None:
    responses = {
        "https://example.test/api/v2/deputados/10/discursos?dataInicio=2026-05-01&dataFim=2026-05-31&itens=1&ordem=ASC&ordenarPor=dataHoraInicio": {
            "dados": [{"dataHoraInicio": "2026-05-02T10:00"}],
            "links": [],
        },
        "https://example.test/api/v2/deputados/10/discursos?dataInicio=2026-05-01&dataFim=2026-05-31&itens=100&ordem=ASC&ordenarPor=dataHoraInicio": {
            "dados": [{"dataHoraInicio": "2026-05-02T10:00", "transcricao": "texto"}],
            "links": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[str(request.url)])

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    stats = _collect_discursos_deputado_adaptive(
        client,
        run,
        deputado_id=10,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        partition="2026",
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-31"},
    )

    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "run-test.jsonl"
    raw_path = (
        tmp_path
        / "raw"
        / "camara"
        / "plenario_discursos"
        / "ano=2026"
        / "mes=05"
        / "run-test.jsonl"
    )
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    monthly_records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]

    assert stats["pages"] == 1
    assert stats["discursos"] == 1
    assert stats["transcricoes"] == 1
    assert stats["preflight"]["year_probe_positive"] == 1
    assert stats["preflight"]["quarter_probe_positive"] == 1
    assert stats["preflight"]["months_expanded"] == 1
    assert [record["record_type"] for record in metadata_records] == [
        "discursos_year_probe",
        "discursos_quarter_probe",
    ]
    assert monthly_records[0]["record_type"] == "discursos_page"
    assert monthly_records[0]["periodo"] == {"data_inicio": "2026-05-01", "data_fim": "2026-05-31"}


def test_collect_discursos_probe_falls_back_without_ordering_on_server_error(tmp_path: Path) -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if "ordenarPor" in request.url.params:
            return httpx.Response(500, json={"status": 500, "title": "Erro no servidor"})
        return httpx.Response(200, json={"dados": [{"dataHoraInicio": "1979-04-26T00:00"}], "links": []})

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    status, written = _collect_discursos_probe(
        client,
        run,
        deputado_id=74854,
        start=date(1979, 4, 1),
        end=date(1979, 4, 30),
        partition="1979-04",
        periodo={"data_inicio": "1979-04-01", "data_fim": "1979-04-30"},
        record_type="discursos_quarter_probe",
        probe_label="trimestre",
    )

    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "run-test.jsonl"
    records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert status == "positive"
    assert written is True
    assert records[0]["request"]["fallback_strategy"] == "sem_ordenacao"
    assert "ordenarPor" not in records[0]["request"]["params"]
    assert len(requests) == 2


def test_collect_discursos_deputado_falls_back_to_single_item_pages_on_legacy_500(
    tmp_path: Path,
) -> None:
    ordered_100_requests = 0
    unordered_100_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ordered_100_requests, unordered_100_requests
        params = request.url.params
        itens = params.get("itens")
        pagina = int(params.get("pagina", "1"))
        if itens == "100":
            if "ordenarPor" in params:
                ordered_100_requests += 1
            else:
                unordered_100_requests += 1
            return httpx.Response(500, json={"status": 500, "title": "Erro no servidor"})
        if itens == "1" and pagina == 3:
            return httpx.Response(500, json={"status": 500, "title": "Erro no servidor"})
        if itens == "1":
            links = []
            if pagina == 1:
                links = [
                    {
                        "rel": "last",
                        "href": (
                            "https://example.test/api/v2/deputados/74854/discursos"
                            "?dataInicio=1979-04-01&dataFim=1979-04-30&pagina=4&itens=1"
                        ),
                    }
                ]
            return httpx.Response(
                200,
                json={
                    "dados": [
                        {
                            "dataHoraInicio": f"1979-04-0{pagina}T00:00",
                            "transcricao": "texto" if pagina == 4 else "",
                        }
                    ],
                    "links": links,
                },
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    run = CollectionRun(tmp_path, source="camara", dataset="plenario_discursos", run_id="run-test", resume=False)

    stats = _collect_discursos_deputado(
        client,
        run,
        partition="1979-04",
        periodo={"data_inicio": "1979-04-01", "data_fim": "1979-04-30"},
        deputado_id=74854,
    )

    raw_path = (
        tmp_path
        / "raw"
        / "camara"
        / "plenario_discursos"
        / "ano=1979"
        / "mes=04"
        / "run-test.jsonl"
    )
    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "run-test.jsonl"
    monthly_records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    metadata_records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]

    assert stats == {"pages": 3, "discursos": 3, "transcricoes": 1, "page_errors": 1}
    assert [record["source_id"] for record in monthly_records] == [
        "deputado:74854:discursos:1979-04:pagina:1",
        "deputado:74854:discursos:1979-04:pagina:2",
        "deputado:74854:discursos:1979-04:pagina:4",
    ]
    assert all(record["request"]["fallback_strategy"] == "itens_1" for record in monthly_records)
    assert metadata_records[0]["record_type"] == "discursos_page_error"
    assert metadata_records[0]["source_id"] == "deputado:74854:discursos:1979-04:pagina:3:erro:itens_1"
    assert metadata_records[0]["response"]["status_code"] == 500
    assert ordered_100_requests == 1
    assert unordered_100_requests == 1
