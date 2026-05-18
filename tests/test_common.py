from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from coleta.common.cli import build_parser, parse_runtime_args, resolve_output_dir
from coleta.common.config import PROD_DATA_ROOT_ENV
from coleta.common.documents import download_and_extract_document, extract_meta_refresh_url, extract_text_from_html_bytes
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun


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
    assert checkpoint["completed_partitions"]["2026-05"]["records"] == 1
    assert manifest["record_counts"]["response"] == 1
    assert autosave["run_id"] == "run-test"
    assert run.should_skip_partition("2026-05")


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
