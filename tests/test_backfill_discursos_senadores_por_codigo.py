from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from coleta.common.http import HttpResult
from coleta.senado import backfill_discursos_por_codigo as backfill


def _write_population(path: Path, *, code: str = "456", house: str = "SF") -> None:
    dataset = "plenario_discursos" if house == "SF" else "congresso_discursos"
    path.write_text(
        json.dumps(
            {
                "codigo_pronunciamento": code,
                "data": "2010-03-10",
                "dataset": dataset,
                "house": house,
                "parlamentar_ids": ["123"],
                "probe_key": f"{house}:2010:20100101:20101231:123",
                "pronunciamento": {
                    "CodigoPronunciamento": code,
                    "DataPronunciamento": "2010-03-10",
                    "SiglaCasaPronunciamento": house,
                    "UrlTextoBinario": f"https://example.test/bin/{code}",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _args(tmp_path: Path, missing_path: Path, *, resume: bool = False) -> list[str]:
    args = [
        "--mode",
        "dev",
        "--no-sample",
        "--output-dir",
        str(tmp_path),
        "--data-inicio",
        "2010-01-01",
        "--data-fim",
        "2010-12-31",
        "--run-id",
        "backfill-sf-test",
        "--missing-path",
        str(missing_path),
        "--house",
        "SF",
    ]
    if resume:
        args.append("--resume")
    return args


def test_backfill_writes_canonical_raw_record_from_missing_population(
    tmp_path: Path, monkeypatch: Any
) -> None:
    missing_path = tmp_path / "missing.jsonl"
    _write_population(missing_path)
    requested: list[str] = []

    class FakeClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get_text(self, endpoint: str) -> HttpResult:
            requested.append(endpoint)
            return HttpResult("https://example.test/texto/456", 200, {}, "Texto oficial recuperado")

    monkeypatch.setattr(backfill, "OpenDataClient", FakeClient)

    manifest_path = backfill.collect(_args(tmp_path, missing_path))

    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "ano=2010"
        / "mes=03"
        / "backfill-sf-test.jsonl"
    )
    records = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert requested == ["dadosabertos/discurso/texto-integral/456"]
    assert records[0]["source_id"] == "SF:pronunciamento:456"
    assert records[0]["payload"]["texto"] == "Texto oficial recuperado"
    provenance = records[0]["payload"]["metadata"]["senator_endpoint_backfill"]
    assert provenance["parlamentar_ids"] == ["123"]
    assert provenance["house"] == "SF"
    assert manifest["status"] == "completed"
    assert manifest["population"] == 1
    assert manifest["pronunciamentos_written"] == 1


def test_backfill_resume_scans_all_raw_and_does_not_duplicate_existing_code(
    tmp_path: Path, monkeypatch: Any
) -> None:
    missing_path = tmp_path / "missing.jsonl"
    _write_population(missing_path)
    calls = 0

    class FakeClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get_text(self, endpoint: str) -> HttpResult:
            nonlocal calls
            calls += 1
            return HttpResult("https://example.test/texto/456", 200, {}, "Texto oficial recuperado")

    monkeypatch.setattr(backfill, "OpenDataClient", FakeClient)
    backfill.collect(_args(tmp_path, missing_path))
    manifest_path = backfill.collect(_args(tmp_path, missing_path, resume=True))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert calls == 1
    assert manifest["existing_before_backfill"] == 1
    assert manifest["partitions_skipped"] == 1


def test_backfill_rejects_divergent_duplicate_population_codes(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    _write_population(missing_path, code="456")
    with missing_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "codigo_pronunciamento": "456",
                    "data": "2010-04-10",
                    "dataset": "plenario_discursos",
                    "house": "SF",
                    "parlamentar_ids": ["123"],
                    "pronunciamento": {"CodigoPronunciamento": "456"},
                }
            )
            + "\n"
        )

    with pytest.raises(ValueError, match="divergência"):
        backfill.load_population(
            missing_path,
            house="SF",
            dataset="plenario_discursos",
            start=backfill.date(2010, 1, 1),
            end=backfill.date(2010, 12, 31),
        )
