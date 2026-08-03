from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from falando_nela.operations import OperationError
from falando_nela.raw import canonical_json_bytes, sha256_file
from falando_nela.sample_import import (
    PILOT_PREFIX,
    SampleImportError,
    execute_pilot_sample,
)
from falando_nela.sources import SourceObject, SourceRecord

CANONICAL_FOLDER_ID = "canonical-folder-id"


class _FakePilotSource:
    def __init__(self, *, reverse_objects: bool = False, duplicate: bool = False) -> None:
        self.list_calls = 0
        self.stream_calls = 0
        locators = [
            f"{PILOT_PREFIX}/mes=02/a.jsonl",
            f"{PILOT_PREFIX}/mes=03/b.jsonl",
        ]
        self.records: dict[str, list[dict[str, object]]] = {
            locator: [
                {
                    "source": "senado",
                    "dataset": "plenario_discursos",
                    "record_type": "pronunciamento_texto",
                    "source_id": f"speech-{offset + index:04d}",
                    "periodo": {"data_inicio": "2010-03-10"},
                    "payload": {"texto": f"discurso {offset + index}"},
                }
                for index in range(50)
            ]
            for locator, offset in zip(locators, (0, 50), strict=True)
        }
        if duplicate:
            self.records[locators[1]][0]["source_id"] = "speech-0000"
        self.objects = [
            SourceObject(locator, 100 + index, provider_hashes={"MD5": f"hash-{index}"})
            for index, locator in enumerate(locators)
        ]
        if reverse_objects:
            self.objects.reverse()

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "rclone",
            "remote": "raw-canonical-ro",
            "prefix": PILOT_PREFIX,
            "root_folder_id": CANONICAL_FOLDER_ID,
            "scope": "drive.readonly",
            "listing": "raw_only",
        }

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
        assert prefix is None
        self.list_calls += 1
        return list(self.objects)

    def iter_records(self, objects: list[SourceObject]):
        self.stream_calls += 1
        for source_object in objects:
            for line_number, value in enumerate(self.records[source_object.locator], start=1):
                raw = canonical_json_bytes(value)
                yield SourceRecord(
                    locator=source_object.locator,
                    line_number=line_number,
                    raw_record=raw,
                    value=value,
                )


def _write_copy_catalog(root: Path, source: _FakePilotSource) -> Path:
    root.mkdir(parents=True)
    catalog_path = root / "copy-catalog.jsonl"
    catalog_path.write_bytes(
        b"".join(
            canonical_json_bytes(
                {
                    "destination_locator": item.locator,
                    "size_bytes": item.size_bytes,
                    "provider_hashes": item.provider_hashes,
                    "status": "copied_verified",
                }
            )
            + b"\n"
            for item in source.objects
        )
    )
    summary_path = root / "copy-catalog-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "files": len(source.objects),
                "bytes": sum(item.size_bytes for item in source.objects),
                "catalog_path": str(catalog_path),
                "catalog_sha256": sha256_file(catalog_path),
            }
        ),
        encoding="utf-8",
    )
    return summary_path


def _execute(
    tmp_path: Path,
    source: _FakePilotSource,
    operation_id: str,
    progress_events: list[dict[str, object]] | None = None,
):
    data_root = tmp_path / "data_samples"
    catalog_summary = _write_copy_catalog(tmp_path / "catalog", source)
    payload = execute_pilot_sample(
        source=source,
        copy_catalog_summary_path=catalog_summary,
        data_root=data_root,
        operation_id=operation_id,
        confirmed_source_folder_id=CANONICAL_FOLDER_ID,
        quota_bytes=1024**3,
        minimum_free_bytes=1,
        expected_files=2,
        expected_bytes=201,
        expected_population=100,
        expected_selection=1,
        progress_callback=(progress_events.append if progress_events is not None else None),
    )
    return data_root, payload


def test_pilot_sample_is_two_pass_deterministic_and_reuses_completed_operation(
    tmp_path: Path,
) -> None:
    source = _FakePilotSource()
    progress_events: list[dict[str, object]] = []
    data_root, first = _execute(tmp_path, source, "pilot-001", progress_events)

    assert first["status"] == "completed"
    assert first["population"] == 100
    assert first["selected_count"] == 1
    assert source.list_calls == 1
    assert source.stream_calls == 2
    assert [event["stage"] for event in progress_events if event["status"] == "completed"] == [
        "preflight",
        "inventory",
        "rank",
        "freeze_selection",
        "materialize",
        "validate",
        "publish",
    ]
    with gzip.open(Path(str(first["output_path"])), "rb") as handle:
        assert len([line for line in handle if line.strip()]) == 1

    ledger = data_root / "operations/sample_pilot/pilot-001/sample-ledger.sqlite"
    connection = sqlite3.connect(ledger)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(candidates)")]
        count = connection.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    finally:
        connection.close()
    assert columns == [
        "identity",
        "selection_key",
        "locator",
        "line_number",
        "raw_sha256",
        "raw_bytes",
    ]
    assert count == 100

    second = execute_pilot_sample(
        source=source,
        copy_catalog_summary_path=tmp_path / "catalog/copy-catalog-summary.json",
        data_root=data_root,
        operation_id="pilot-001",
        confirmed_source_folder_id=CANONICAL_FOLDER_ID,
        quota_bytes=1024**3,
        minimum_free_bytes=1,
        expected_files=2,
        expected_bytes=201,
        expected_population=100,
        expected_selection=1,
    )
    assert second == first
    assert source.list_calls == 1
    assert source.stream_calls == 2


def test_pilot_selection_is_independent_of_source_file_order(tmp_path: Path) -> None:
    first_source = _FakePilotSource()
    _, first = _execute(tmp_path / "first", first_source, "pilot-order")
    second_source = _FakePilotSource(reverse_objects=True)
    _, second = _execute(tmp_path / "second", second_source, "pilot-order")

    assert first["sample_id"] == second["sample_id"]
    assert sha256_file(Path(str(first["output_path"]))) == sha256_file(
        Path(str(second["output_path"]))
    )


def test_pilot_blocks_duplicate_identity_without_publishing(tmp_path: Path) -> None:
    source = _FakePilotSource(duplicate=True)

    with pytest.raises(SampleImportError, match="identidade duplicada"):
        _execute(tmp_path, source, "pilot-duplicate")

    assert not list((tmp_path / "data_samples/raw").rglob("*.gz"))


def test_pilot_blocks_changed_operation_input_and_published_conflict(tmp_path: Path) -> None:
    source = _FakePilotSource()
    data_root, first = _execute(tmp_path, source, "pilot-conflict")
    summary_path = tmp_path / "catalog/copy-catalog-summary.json"
    original_summary = summary_path.read_bytes()
    summary_path.write_bytes(original_summary + b"\n")

    with pytest.raises(OperationError, match="entrada ou configuração diferente"):
        execute_pilot_sample(
            source=source,
            copy_catalog_summary_path=summary_path,
            data_root=data_root,
            operation_id="pilot-conflict",
            confirmed_source_folder_id=CANONICAL_FOLDER_ID,
            quota_bytes=1024**3,
            minimum_free_bytes=1,
            expected_files=2,
            expected_bytes=201,
            expected_population=100,
            expected_selection=1,
        )

    summary_path.write_bytes(original_summary)
    Path(str(first["output_path"])).write_bytes(b"conteudo-divergente")
    with pytest.raises(SampleImportError, match="destino publicado diverge"):
        execute_pilot_sample(
            source=source,
            copy_catalog_summary_path=summary_path,
            data_root=data_root,
            operation_id="pilot-conflict",
            confirmed_source_folder_id=CANONICAL_FOLDER_ID,
            quota_bytes=1024**3,
            minimum_free_bytes=1,
            expected_files=2,
            expected_bytes=201,
            expected_population=100,
            expected_selection=1,
        )


def test_pilot_preflight_blocks_insufficient_reserved_space(tmp_path: Path) -> None:
    source = _FakePilotSource()
    catalog_summary = _write_copy_catalog(tmp_path / "catalog", source)
    free_bytes = shutil.disk_usage(tmp_path).free

    with pytest.raises(SampleImportError, match="espaço livre insuficiente"):
        execute_pilot_sample(
            source=source,
            copy_catalog_summary_path=catalog_summary,
            data_root=tmp_path / "data_samples",
            operation_id="pilot-no-space",
            confirmed_source_folder_id=CANONICAL_FOLDER_ID,
            quota_bytes=free_bytes,
            minimum_free_bytes=1,
            expected_files=2,
            expected_bytes=201,
            expected_population=100,
            expected_selection=1,
        )
