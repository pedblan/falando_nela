from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from processamento import inventario_drive
from processamento.inventario_drive import (
    scan_metadata,
    write_drive_inventory,
)


COMMIT = "a" * 40


def test_inventory_is_read_only_and_writes_d06_bundle(tmp_path: Path) -> None:
    data_root = tmp_path / "mounted-drive" / "falando_nela" / "data"
    output_base = tmp_path / "content" / "falando_nela_inventory"
    _build_fixture(data_root)
    before = _tree_signature(data_root)

    result = write_drive_inventory(
        data_root=data_root,
        output_base=output_base,
        operation_id="drive-inventory-test-1",
        code_commit=COMMIT,
        max_structured_bytes=1024 * 1024,
    )

    after = _tree_signature(data_root)
    operation_root = output_base / "drive-inventory-test-1"
    manifest = result["manifest"]

    assert before == after
    assert manifest["execution_status"] == "succeeded"
    assert manifest["scientific_gate"] == "needs_review"
    assert manifest["counts"]["references_missing"] == 1
    assert (
        manifest["counts"]["universe_items_reconciled"]
        == manifest["counts"]["items_cataloged"]
    )
    assert len(manifest["outputs"]) == 8
    assert (operation_root / "relatorio.md").exists()
    assert (operation_root / "manifest.json").exists()
    assert (operation_root / "logs" / "execution.jsonl").exists()
    assert (operation_root / "artifacts" / "mapa_dados.md").exists()
    assert len(
        _read_csv(operation_root / "artifacts" / "catalogo_dados.csv")
    ) == manifest["counts"]["items_cataloged"]
    assert "O programa terminou normalmente." in (
        operation_root / "relatorio.md"
    ).read_text(encoding="utf-8")
    assert "cada item descendente da raiz pertence exatamente a um grupo" in (
        operation_root / "artifacts" / "mapa_dados.md"
    ).read_text(encoding="utf-8")
    assert sum(row["items"] for row in result["universes"]) == len(
        result["catalog"]
    )


def test_inventory_catalogs_execution_and_missing_reference(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _build_fixture(data_root)

    result = write_drive_inventory(
        data_root=data_root,
        output_base=tmp_path / "output",
        operation_id="drive-inventory-test-2",
        code_commit=COMMIT,
    )

    assert len(result["executions"]) == 1
    execution = result["executions"][0]
    assert execution["operation_id"] == "legacy-run-1"
    assert execution["execution_status"] == "succeeded"
    assert execution["scientific_gate"] == "not_evaluated"
    assert execution["valid_references"] == 1
    assert execution["missing_references"] == 1
    assert any(
        issue["issue_type"] == "declared_reference_missing"
        for issue in result["issues"]
    )
    assert any(
        issue["issue_type"] == "possible_orphan_output"
        and issue["item_relative_path"].endswith("orphan.bin")
        for issue in result["issues"]
    )


def test_inventory_skips_oversized_structured_content(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    manifest_path = data_root / "operations" / "run" / "manifest-large.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text('{"padding": "' + ("x" * 500) + '"}', encoding="utf-8")

    result = write_drive_inventory(
        data_root=data_root,
        output_base=tmp_path / "output",
        operation_id="drive-inventory-test-3",
        code_commit=COMMIT,
        max_structured_bytes=100,
    )

    row = next(
        item
        for item in result["catalog"]
        if item["relative_path"] == "operations/run/manifest-large.json"
    )
    assert row["content_candidate"] is True
    assert row["content_inspected"] is False
    assert row["content_issue"] == "skipped_size_limit"
    assert result["executions"] == []


def test_invalid_manifest_becomes_warning_without_aborting(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    manifest_path = data_root / "manifests" / "broken-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{invalid", encoding="utf-8")

    result = write_drive_inventory(
        data_root=data_root,
        output_base=tmp_path / "output",
        operation_id="drive-inventory-test-4",
        code_commit=COMMIT,
    )

    assert result["manifest"]["execution_status"] == "succeeded"
    assert result["manifest"]["scientific_gate"] == "needs_review"
    assert any(issue["issue_type"] == "invalid_json" for issue in result["issues"])


def test_inventory_refuses_output_inside_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()

    with pytest.raises(ValueError, match="não pode ficar dentro"):
        write_drive_inventory(
            data_root=data_root,
            output_base=data_root / "inventario",
            operation_id="drive-inventory-invalid-output",
            code_commit=COMMIT,
        )

    assert list(data_root.iterdir()) == []


def test_inventory_persists_minimal_failure_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    output_base = tmp_path / "output"

    def fail_scan(_: Path):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(inventario_drive, "scan_metadata", fail_scan)
    with pytest.raises(RuntimeError, match="falha simulada"):
        write_drive_inventory(
            data_root=data_root,
            output_base=output_base,
            operation_id="drive-inventory-failure",
            code_commit=COMMIT,
        )

    operation_root = output_base / "drive-inventory-failure"
    manifest = json.loads(
        (operation_root / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["execution_status"] == "failed"
    assert manifest["scientific_gate"] == "not_evaluated"
    assert "falha simulada" in (
        operation_root / "relatorio.md"
    ).read_text(encoding="utf-8")


def test_inventory_marks_reference_with_two_destinations_as_ambiguous(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    operation_root = data_root / "operations" / "run"
    operation_root.mkdir(parents=True)
    (data_root / "shared.csv").write_text("id\nroot\n", encoding="utf-8")
    (operation_root / "shared.csv").write_text(
        "id\noperation\n",
        encoding="utf-8",
    )
    (operation_root / "manifest.json").write_text(
        json.dumps(
            {
                "operation_id": "run",
                "execution_status": "succeeded",
                "input_path": "shared.csv",
            }
        ),
        encoding="utf-8",
    )

    result = write_drive_inventory(
        data_root=data_root,
        output_base=tmp_path / "output",
        operation_id="drive-inventory-ambiguous",
        code_commit=COMMIT,
    )

    assert result["references"][0]["status"] == "ambiguous"
    assert result["manifest"]["counts"]["references_ambiguous"] == 1
    assert any(
        issue["issue_type"] == "declared_reference_ambiguous"
        for issue in result["issues"]
    )


def test_metadata_taxonomy_is_explicit(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _build_fixture(data_root)

    catalog, issues = scan_metadata(data_root)
    by_path = {row["relative_path"]: row for row in catalog}

    assert issues == []
    assert by_path["raw/camara/discursos.jsonl"]["item_class"] == "dataset"
    assert by_path["raw/camara/discursos.jsonl"]["layer"] == "raw"
    assert by_path["raw/camara/discursos.jsonl"]["source"] == "camara"
    assert (
        by_path["operations/auditorias/legacy-run-1/manifest.json"]["item_class"]
        == "manifest"
    )
    assert (
        by_path["reports/relatorio_cobertura.md"]["item_class"]
        == "report"
    )


def _build_fixture(data_root: Path) -> None:
    raw_path = data_root / "raw" / "camara" / "discursos.jsonl"
    parquet_path = (
        data_root
        / "processed"
        / "textos_parlamentares"
        / "v1"
        / "discursos.parquet"
    )
    operation_root = data_root / "operations" / "auditorias" / "legacy-run-1"
    report_path = data_root / "reports" / "relatorio_cobertura.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    operation_root.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text('{"texto_id": "1"}\n', encoding="utf-8")
    parquet_path.write_bytes(b"PAR1fixture")
    (operation_root / "result.csv").write_text("id\n1\n", encoding="utf-8")
    (operation_root / "orphan.bin").write_bytes(b"orphan")
    (operation_root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "legacy-run-1",
                "module": "legacy_audit",
                "status": "completed",
                "errors": 0,
                "output_path": "result.csv",
                "missing_path": "missing.csv",
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        "# Cobertura\n\nEste relatório descreve um subconjunto legado.\n",
        encoding="utf-8",
    )


def _tree_signature(root: Path) -> list[tuple[str, int, int]]:
    signature = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        signature.append(
            (
                path.relative_to(root).as_posix(),
                stat.st_size,
                stat.st_mtime_ns,
            )
        )
    return signature


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
