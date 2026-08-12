from __future__ import annotations

from pathlib import Path

from falando_nela.raw import (
    atomic_write_json,
    deterministic_gzip,
    iter_jsonl,
    sha256_file,
    uncompressed_sha256,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "raw"
    / "senado"
    / "plenario_discursos"
    / "ano=2010"
    / "fixture.jsonl"
)


def test_gzip_is_deterministic_and_lossless(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl.gz"
    second = tmp_path / "second.jsonl.gz"

    first_result = deterministic_gzip(FIXTURE, first)
    second_result = deterministic_gzip(FIXTURE, second)

    assert sha256_file(first) == sha256_file(second)
    assert first.read_bytes() == second.read_bytes()
    assert first_result["sha256_stored_object"] == second_result["sha256_stored_object"]
    assert first_result["sha256_uncompressed"] == sha256_file(FIXTURE)
    assert uncompressed_sha256(first) == sha256_file(FIXTURE)
    assert list(iter_jsonl(first)) == list(iter_jsonl(FIXTURE))


def test_fixture_contains_only_the_approved_vertical_slice() -> None:
    records = list(iter_jsonl(FIXTURE))

    assert len(records) == 3
    assert {record["source"] for record in records} == {"senado"}
    assert {record["dataset"] for record in records} == {"plenario_discursos"}
    assert {record["record_type"] for record in records} == {"pronunciamento_texto"}
    assert all(record["periodo"]["data_inicio"].startswith("2010-") for record in records)


def test_atomic_json_is_canonical_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "manifest.json"

    atomic_write_json(destination, {"z": 1, "a": "ação"})

    assert destination.read_bytes() == b'{"a":"a\xc3\xa7\xc3\xa3o","z":1}\n'
    assert list(tmp_path.iterdir()) == [destination]
