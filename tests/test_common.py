from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from coleta.common.cli import build_parser, parse_runtime_args, resolve_output_dir
from coleta.common.config import PROD_DATA_ROOT_ENV, quarter_windows, year_windows
from coleta.common.documents import download_and_extract_document, extract_meta_refresh_url, extract_text_from_html_bytes
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun
from coleta.common.parlamentares import active_parlamentares_for_window, load_parlamentares_periodos


def test_year_windows_preserve_requested_bounds() -> None:
    assert list(year_windows(date(2024, 11, 15), date(2026, 2, 3))) == [
        ("2024", date(2024, 11, 15), date(2024, 12, 31)),
        ("2025", date(2025, 1, 1), date(2025, 12, 31)),
        ("2026", date(2026, 1, 1), date(2026, 2, 3)),
    ]


def test_year_windows_reject_inverted_period() -> None:
    with pytest.raises(ValueError, match="data_inicio"):
        list(year_windows(date(2026, 1, 2), date(2026, 1, 1)))


def test_quarter_windows_preserve_requested_bounds() -> None:
    assert list(quarter_windows(date(2024, 2, 15), date(2025, 4, 3))) == [
        ("2024-Q1", date(2024, 2, 15), date(2024, 3, 31)),
        ("2024-Q2", date(2024, 4, 1), date(2024, 6, 30)),
        ("2024-Q3", date(2024, 7, 1), date(2024, 9, 30)),
        ("2024-Q4", date(2024, 10, 1), date(2024, 12, 31)),
        ("2025-Q1", date(2025, 1, 1), date(2025, 3, 31)),
        ("2025-Q2", date(2025, 4, 1), date(2025, 4, 3)),
    ]


def test_quarter_windows_reject_inverted_period() -> None:
    with pytest.raises(ValueError, match="data_inicio"):
        list(quarter_windows(date(2026, 1, 2), date(2026, 1, 1)))


def test_load_parlamentares_periodos_filters_and_clips_mandates(tmp_path) -> None:
    output_root = tmp_path / "processed" / "parlamentares" / "v1"
    output_root.mkdir(parents=True)
    rows = [
        {
            "source": "camara",
            "parlamentar_id": "10",
            "nome_parlamentar": "Deputada A",
            "vigencia_inicio": "2026-02-01",
            "vigencia_fim": "2026-06-30",
            "intervalo_fonte": "mandato",
            "intervalo_inferido": False,
        },
        {
            "source": "camara",
            "parlamentar_id": "11",
            "nome_parlamentar": "Deputado B",
            "vigencia_inicio": "2025-01-01",
            "vigencia_fim": "2025-12-31",
            "intervalo_fonte": "mandato",
            "intervalo_inferido": False,
        },
        {
            "source": "camara",
            "parlamentar_id": "12",
            "nome_parlamentar": "Inferido",
            "vigencia_inicio": "0001-01-01",
            "vigencia_fim": "9999-12-31",
            "intervalo_fonte": "identidade",
            "intervalo_inferido": True,
        },
    ]
    path = output_root / "parlamentares_periodos.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    periodos = load_parlamentares_periodos(
        tmp_path,
        source="camara",
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 12, 31),
    )
    planejados = active_parlamentares_for_window(
        periodos,
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )

    assert list(periodos) == ["10"]
    assert planejados == [
        {
            "id": 10,
            "nome": "Deputada A",
            "_active_start": date(2026, 2, 1),
            "_active_end": date(2026, 6, 30),
            "_periodos_mandato": 1,
        }
    ]
    assert (
        load_parlamentares_periodos(
            tmp_path,
            source="camara",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            min_ids=2,
        )
        == {}
    )


def test_open_data_client_retries_transient_status() -> None:
    calls = {"count": 0}
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        urls.append(str(request.url))
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "temporario"})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=transport, follow_redirects=True)

    result = client.get_json("/dados", params={"siglaCasa": "SF"})

    assert calls["count"] == 2
    assert urls == [
        "https://example.test/dados?siglaCasa=SF",
        "https://example.test/dados?siglaCasa=SF",
    ]
    assert result.status_code == 200
    assert result.data == {"ok": True}


def test_open_data_client_get_text() -> None:
    seen_accept_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_accept_headers.append(request.headers.get("accept"))
        return httpx.Response(200, text="texto integral", headers={"Content-Type": "text/plain"})

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = client.get_text("/texto/1")

    assert seen_accept_headers == ["text/plain"]
    assert result.status_code == 200
    assert result.headers["content-type"] == "text/plain"
    assert result.data == "texto integral"


def test_open_data_client_get_bytes() -> None:
    seen_accept_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_accept_headers.append(request.headers.get("accept"))
        return httpx.Response(
            200,
            content=b"%PDF-1.4",
            headers={
                "Content-Type": "application/pdf",
                "Content-Length": "8",
                "Content-Disposition": "inline; filename=parecer.pdf",
            },
        )

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = client.get_bytes("/documento/1")

    assert seen_accept_headers == ["*/*"]
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/pdf"
    assert result.headers["content-length"] == "8"
    assert result.headers["content-disposition"] == "inline; filename=parecer.pdf"
    assert result.data == b"%PDF-1.4"


def test_extract_meta_refresh_url_and_html_text() -> None:
    html = b"""
    <html><head><meta http-equiv="refresh" content="0; URL=/arquivo.pdf"></head>
    <body><script>ignore()</script><p>Texto do parecer</p></body></html>
    """

    assert extract_meta_refresh_url(html, base_url="https://example.test/origem") == "https://example.test/arquivo.pdf"
    assert extract_text_from_html_bytes(html) == "Texto do parecer"


def test_download_and_extract_document_follows_meta_refresh_to_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.test/origem":
            return httpx.Response(
                200,
                content=b'<meta http-equiv="refresh" content="0; URL=/parecer.txt">',
                headers={"Content-Type": "text/html"},
            )
        if str(request.url) == "https://example.test/parecer.txt":
            return httpx.Response(200, text="texto do parecer", headers={"Content-Type": "text/plain"})
        return httpx.Response(404)

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = download_and_extract_document(client, "https://example.test/origem")

    assert result.text == "texto do parecer"
    assert result.method == "text_document_download"
    assert result.text_status == "disponivel"
    assert result.fontes["documento_resolvido"] == "https://example.test/parecer.txt"
    assert result.document["content_type"] == "text/plain"


def test_iter_camara_pages_follows_next_links() -> None:
    responses = {
        "https://example.test/api/v2/items": {
            "dados": [{"id": 1}],
            "links": [{"rel": "next", "href": "https://example.test/api/v2/items?pagina=2"}],
        },
        "https://example.test/api/v2/items?pagina=2": {
            "dados": [{"id": 2}],
            "links": [],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[str(request.url)])

    client = OpenDataClient("https://example.test", sleep=lambda _: None)
    client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    pages = list(iter_camara_pages(client, "api/v2/items"))

    assert [page.data["dados"][0]["id"] for page in pages] == [1, 2]


def test_collection_run_writes_record_checkpoint_and_manifest(tmp_path) -> None:
    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-test",
        resume=True,
    )

    run.write_record(
        partition="2026-05",
        source_id="fonte:1",
        request={"method": "GET", "path": "/x", "params": {}},
        response={"status_code": 200, "url": "https://example.test/x", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"dados": [1]},
        record_type="response",
    )
    run.mark_partition_complete("2026-05")
    run.write_manifest(sample=True)

    raw_path = tmp_path / "raw" / "fonte" / "dataset" / "ano=2026" / "mes=05" / "run-test.jsonl"
    checkpoint_path = tmp_path / "checkpoints" / "fonte" / "dataset.json"
    manifest_path = tmp_path / "manifests" / "run-test.json"
    autosave_path = tmp_path / "manifests" / "run-test.autosave.json"

    assert raw_path.exists()
    assert checkpoint_path.exists()
    assert manifest_path.exists()
    assert autosave_path.exists()

    record = json.loads(raw_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    autosave = json.loads(autosave_path.read_text(encoding="utf-8"))

    assert record["checksum"]
    assert checkpoint["completed_partitions"]["2026-05"]["run_id"] == "run-test"
    assert checkpoint["completed_partitions"]["2026-05"]["records"] == 1
    assert checkpoint["runs"]["run-test"]["completed_partitions"]["2026-05"]["run_id"] == "run-test"
    assert checkpoint["runs"]["run-test"]["completed_partitions"]["2026-05"]["records"] == 1
    assert manifest["record_counts"]["response"] == 1
    assert autosave["run_id"] == "run-test"
    assert run.should_skip_partition("2026-05")


def test_collection_run_does_not_skip_partition_completed_by_other_run_id(tmp_path) -> None:
    first_run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-a",
        resume=True,
    )
    first_run.mark_partition_complete("2026-05")

    second_run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-b",
        resume=True,
    )

    assert not second_run.should_skip_partition("2026-05")


def test_collection_run_preserves_completed_partitions_for_multiple_run_ids(tmp_path) -> None:
    first_run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-a",
        resume=True,
    )
    first_run.mark_partition_complete("2026-05")

    second_run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-b",
        resume=True,
    )
    second_run.mark_partition_complete("2026-05")

    resumed_first = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-a",
        resume=True,
    )
    resumed_second = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-b",
        resume=True,
    )

    checkpoint_path = tmp_path / "checkpoints" / "fonte" / "dataset.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert resumed_first.should_skip_partition("2026-05")
    assert resumed_second.should_skip_partition("2026-05")
    assert checkpoint["runs"]["run-a"]["completed_partitions"]["2026-05"]["run_id"] == "run-a"
    assert checkpoint["runs"]["run-b"]["completed_partitions"]["2026-05"]["run_id"] == "run-b"
    assert checkpoint["completed_partitions"]["2026-05"]["run_id"] == "run-b"


def test_collection_run_can_skip_legacy_checkpoint_when_current_run_has_partition_output(tmp_path) -> None:
    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="legacy-run",
        resume=False,
    )
    run.write_record(
        partition="2026-05",
        source_id="fonte:1",
        request={"method": "GET", "path": "/x", "params": {}},
        response={"status_code": 200, "url": "https://example.test/x", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"dados": [1]},
        record_type="response",
    )

    checkpoint_path = tmp_path / "checkpoints" / "fonte" / "dataset.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "source": "fonte",
                "dataset": "dataset",
                "completed_partitions": {"2026-05": {"records": 1}},
            }
        ),
        encoding="utf-8",
    )

    resumed = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="legacy-run",
        resume=True,
    )

    assert resumed.should_skip_partition("2026-05")


def test_collection_run_does_not_skip_legacy_checkpoint_without_current_run_output(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoints" / "fonte" / "dataset.json"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "source": "fonte",
                "dataset": "dataset",
                "completed_partitions": {"2026-05": {"records": 1}},
            }
        ),
        encoding="utf-8",
    )

    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="new-run",
        resume=True,
    )

    assert not run.should_skip_partition("2026-05")


def test_collection_run_resume_reads_existing_records_and_skips_duplicates(tmp_path) -> None:
    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-resume",
        resume=False,
    )

    first_write = run.write_record(
        partition="2026-05",
        source_id="fonte:1",
        request={"method": "GET", "path": "/x", "params": {}},
        response={"status_code": 200, "url": "https://example.test/x", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"dados": [1]},
        record_type="response",
    )

    resumed = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-resume",
        resume=True,
    )
    second_write = resumed.write_record(
        partition="2026-05",
        source_id="fonte:1",
        request={"method": "GET", "path": "/x", "params": {}},
        response={"status_code": 200, "url": "https://example.test/x", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"dados": [1]},
        record_type="response",
    )

    raw_path = tmp_path / "raw" / "fonte" / "dataset" / "ano=2026" / "mes=05" / "run-resume.jsonl"

    assert first_write is True
    assert resumed.has_record(source_id="fonte:1", record_type="response")
    assert second_write is False
    assert len(raw_path.read_text(encoding="utf-8").splitlines()) == 1


def test_collection_run_appends_after_partial_jsonl_line_on_resume(tmp_path) -> None:
    raw_path = tmp_path / "raw" / "fonte" / "dataset" / "metadata" / "run-resume.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text('{"partial": true', encoding="utf-8")

    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-resume",
        resume=True,
    )
    run.write_record(
        partition="metadata",
        source_id="fonte:2",
        request={"method": "GET", "path": "/x", "params": {}},
        response={"status_code": 200, "url": "https://example.test/x", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"dados": [2]},
        record_type="response",
    )

    lines = raw_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["source_id"] == "fonte:2"


def test_collection_run_marks_failed_partition(tmp_path) -> None:
    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-failed",
        resume=True,
    )

    run.mark_partition_failed("2026-05", error={"type": "RuntimeError", "message": "falha"})

    checkpoint_path = tmp_path / "checkpoints" / "fonte" / "dataset.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert "2026-05" in checkpoint["failed_partitions"]
    assert checkpoint["failed_partitions"]["2026-05"]["run_id"] == "run-failed"
    assert checkpoint["runs"]["run-failed"]["failed_partitions"]["2026-05"]["run_id"] == "run-failed"
    assert not run.should_skip_partition("2026-05")


def test_collection_run_writes_metadata_partition_outside_monthly_corpus(tmp_path) -> None:
    run = CollectionRun(
        tmp_path,
        source="fonte",
        dataset="dataset",
        run_id="run-test",
        resume=False,
    )

    run.write_record(
        partition="metadata",
        source_id="fonte:metadata:1",
        request={"method": "GET", "path": "/lista", "params": {}},
        response={"status_code": 200, "url": "https://example.test/lista", "headers": {}},
        periodo={"data_inicio": "2026-05-01", "data_fim": "2026-05-18"},
        payload={"itens": [1, 2]},
        record_type="discursos_periodo_metadata",
    )

    metadata_path = tmp_path / "raw" / "fonte" / "dataset" / "metadata" / "run-test.jsonl"
    monthly_path = tmp_path / "raw" / "fonte" / "dataset" / "ano=metadata" / "mes=" / "run-test.jsonl"

    assert metadata_path.exists()
    assert not monthly_path.exists()

    record = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert record["partition"] == "metadata"
    assert record["record_type"] == "discursos_periodo_metadata"


def test_dev_mode_defaults_to_sample_and_data_dev(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(PROD_DATA_ROOT_ENV, raising=False)
    parser = build_parser("teste")

    runtime = parse_runtime_args(parser, [])

    assert runtime.mode == "dev"
    assert runtime.sample is True
    assert runtime.sample_limit == 5
    assert runtime.output_dir == Path("data/dev")


def test_prod_mode_uses_external_env_and_defaults_to_full_collection(monkeypatch, tmp_path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    external_data = tmp_path / "drive" / "falando_nela" / "data"
    monkeypatch.chdir(repo_dir)
    monkeypatch.setenv(PROD_DATA_ROOT_ENV, str(external_data))
    parser = build_parser("teste")

    runtime = parse_runtime_args(parser, ["--mode", "prod"])

    assert runtime.mode == "prod"
    assert runtime.sample is False
    assert runtime.sample_limit is None
    assert runtime.output_dir == external_data


def test_sample_limit_can_be_overridden(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(PROD_DATA_ROOT_ENV, raising=False)
    parser = build_parser("teste")

    runtime = parse_runtime_args(parser, ["--sample-limit", "2"])

    assert runtime.sample_limit == 2


def test_prod_mode_requires_external_data_root(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(PROD_DATA_ROOT_ENV, raising=False)
    parser = build_parser("teste")

    with pytest.raises(SystemExit):
        parse_runtime_args(parser, ["--mode", "prod"])


def test_prod_mode_rejects_output_inside_repo(tmp_path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    with pytest.raises(ValueError):
        resolve_output_dir(
            mode="prod",
            output_dir=str(repo_dir / "data"),
            cwd=repo_dir,
            env={},
            parser=None,
        )
