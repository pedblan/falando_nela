from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from coleta.senado import discursos
from coleta.senado.congresso_discursos.collect import collect


@dataclass
class _Result:
    data: Any
    status_code: int = 200

    @property
    def response_metadata(self) -> dict[str, Any]:
        return {
            "url": "https://example.test/result",
            "status_code": self.status_code,
            "headers": {"content-type": "application/json"},
        }


class _FakeClient:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> _Result:
        self.state["list_calls"] += 1
        self.state["list_params"].append(params)
        return _Result(
            {
                "DiscursosSessao": {
                    "Sessoes": {
                        "Sessao": {
                            "CodigoSessao": "900",
                            "DataSessao": "2000-03-15",
                            "Pronunciamentos": {
                                "Pronunciamento": {
                                    "CodigoPronunciamento": "12345",
                                    "NomeAutor": "Congressista",
                                    "UrlVideo": "https://example.test/video/12345",
                                }
                            },
                        }
                    }
                }
            }
        )

    def get_text(self, endpoint: str) -> _Result:
        self.state["text_calls"] += 1
        if self.state["fail_text"]:
            raise RuntimeError("falha transitoria inesperada")
        return _Result("Texto integral do Congresso Nacional")


class _FallbackClient(_FakeClient):
    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> _Result:
        if "plenario/lista/discursos" in endpoint:
            return super().get_json(endpoint, params=params)
        self.state["session_calls"] += 1
        if self.state["session_text"] is None:
            return _Result({"Notas": {}})
        return _Result({"Notas": {"Texto": self.state["session_text"]}})

    def get_text(self, endpoint: str) -> _Result:
        self.state["text_calls"] += 1
        request = httpx.Request("GET", "https://example.test/texto")
        response = httpx.Response(404, request=request, json={"status": 404})
        raise httpx.HTTPStatusError("texto ausente", request=request, response=response)


def _args(tmp_path: Path, *, resume: bool = False) -> list[str]:
    args = [
        "--mode",
        "dev",
        "--no-sample",
        "--output-dir",
        str(tmp_path),
        "--data-inicio",
        "2000-03-01",
        "--data-fim",
        "2000-03-31",
        "--run-id",
        "test-congresso-textos",
    ]
    if resume:
        args.append("--resume")
    return args


def _install_fake_client(monkeypatch: Any, state: dict[str, Any]) -> None:
    monkeypatch.setattr(discursos, "OpenDataClient", lambda _base_url: _FakeClient(state))


def _install_fallback_client(monkeypatch: Any, state: dict[str, Any]) -> None:
    monkeypatch.setattr(discursos, "OpenDataClient", lambda _base_url: _FallbackClient(state))


def test_congresso_collects_text_with_cn_and_resume_is_idempotent(tmp_path: Path, monkeypatch: Any) -> None:
    state = {"fail_text": False, "list_calls": 0, "text_calls": 0, "list_params": []}
    _install_fake_client(monkeypatch, state)

    collect(_args(tmp_path))

    metadata_path = tmp_path / "raw" / "senado" / "congresso_discursos" / "metadata" / "test-congresso-textos.jsonl"
    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "ano=2000"
        / "mes=03"
        / "test-congresso-textos.jsonl"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8").strip())
    corpus = json.loads(corpus_path.read_text(encoding="utf-8").strip())

    assert metadata["request"]["params"]["siglaCasa"] == "CN"
    assert corpus["source"] == "senado"
    assert corpus["dataset"] == "congresso_discursos"
    assert corpus["source_id"] == "CN:pronunciamento:12345"
    assert corpus["record_type"] == "pronunciamento_texto"
    assert corpus["payload"]["texto"] == "Texto integral do Congresso Nacional"
    assert not (tmp_path / "raw" / "senado" / "congresso_discursos" / "transcription_queue").exists()

    collect(_args(tmp_path, resume=True))

    assert state["list_calls"] == 1
    assert state["text_calls"] == 1
    assert len(corpus_path.read_text(encoding="utf-8").splitlines()) == 1


def test_unexpected_item_failure_leaves_partition_resumable(tmp_path: Path, monkeypatch: Any) -> None:
    state = {"fail_text": True, "list_calls": 0, "text_calls": 0, "list_params": []}
    _install_fake_client(monkeypatch, state)

    manifest_path = collect(_args(tmp_path, resume=True))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint_path = tmp_path / "checkpoints" / "senado" / "congresso_discursos.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "completed_with_errors"
    assert manifest["errors"] == 1
    assert "2000-03" in checkpoint["runs"]["test-congresso-textos"]["failed_partitions"]
    assert "2000-03" not in checkpoint["runs"]["test-congresso-textos"].get("completed_partitions", {})

    state["fail_text"] = False
    manifest_path = collect(_args(tmp_path, resume=True))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "completed"
    assert manifest["errors"] == 0
    assert "2000-03" in checkpoint["runs"]["test-congresso-textos"]["completed_partitions"]
    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "ano=2000"
        / "mes=03"
        / "test-congresso-textos.jsonl"
    )
    assert len(corpus_path.read_text(encoding="utf-8").splitlines()) == 1


def test_congresso_falls_back_to_session_notes(tmp_path: Path, monkeypatch: Any) -> None:
    state = {
        "fail_text": False,
        "list_calls": 0,
        "text_calls": 0,
        "session_calls": 0,
        "session_text": "Notas integrais da sessao conjunta",
        "list_params": [],
    }
    _install_fallback_client(monkeypatch, state)

    collect(_args(tmp_path))

    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "ano=2000"
        / "mes=03"
        / "test-congresso-textos.jsonl"
    )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8").strip())
    assert corpus["payload"]["texto"] == "Notas integrais da sessao conjunta"
    assert corpus["payload"]["metodo_obtencao"] == "api_notas_sessao"
    assert state["session_calls"] == 1


def test_congresso_queues_transcription_when_all_text_is_absent(tmp_path: Path, monkeypatch: Any) -> None:
    state = {
        "fail_text": False,
        "list_calls": 0,
        "text_calls": 0,
        "session_calls": 0,
        "session_text": None,
        "list_params": [],
    }
    _install_fallback_client(monkeypatch, state)

    collect(_args(tmp_path))

    queue_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "transcription_queue"
        / "test-congresso-textos.jsonl"
    )
    queue = json.loads(queue_path.read_text(encoding="utf-8").strip())
    assert queue["record_type"] == "transcription_queue"
    assert queue["source_id"] == "CN:pronunciamento:12345"
    assert queue["payload"]["texto"] is None
    assert queue["payload"]["metodo_obtencao"] == "pendente_transcricao_video"
