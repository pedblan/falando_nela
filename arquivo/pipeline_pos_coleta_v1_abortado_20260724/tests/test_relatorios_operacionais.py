from __future__ import annotations

import json
from pathlib import Path

import pytest

from relatorios_operacionais import (
    ArtifactRef,
    CountRow,
    ReportArtifact,
    append_log_event,
    build_manifest,
    render_report,
    validate_manifest,
    write_minimal_failure_record,
    write_operation_bundle,
)


COMMIT = "a" * 40
STARTED_AT = "2026-07-23T09:00:00-03:00"
FINISHED_AT = "2026-07-23T09:08:12-03:00"


def test_manifest_has_the_21_approved_fields_and_validates() -> None:
    manifest = _manifest()

    validate_manifest(manifest)

    assert manifest["schema_version"] == "1.0.0"
    assert len(manifest) == 21
    assert manifest["analysis_run_id"] is None
    assert manifest["execution_status"] == "succeeded"
    assert manifest["scientific_gate"] == "needs_review"


def test_report_explains_success_and_pending_scientific_review() -> None:
    report = render_report(
        module="drive_inventory",
        objective="catalogar artefatos sem alterar o Drive",
        operation_id="drive-inventory-test",
        period="até 2026-07-23",
        unit="item do Drive",
        execution_status="succeeded",
        scientific_gate="needs_review",
        result_summary="Foram catalogados 10 itens nas raízes aprovadas.",
        counts=[
            CountRow(
                label="itens catalogados",
                value=10,
                universe_or_rule="todos os itens acessíveis nas raízes aprovadas",
            )
        ],
        artifacts=[
            ReportArtifact(
                kind="Saída",
                name="catálogo",
                purpose="listar itens",
                uri="artifacts/catalogo.parquet",
                action="revisar",
            )
        ],
        next_action="Revise o catálogo antes de aprová-lo.",
    )

    assert "O programa terminou normalmente." in report
    assert "O resultado ainda precisa de revisão humana." in report
    assert "todos os itens acessíveis nas raízes aprovadas" in report
    assert "Revise o catálogo antes de aprová-lo." in report
    assert "## Erros\n\nNenhum." in report


def test_write_bundle_uses_canonical_paths_and_refuses_implicit_overwrite(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    operation_root = tmp_path / manifest["operation_id"]
    report = _report(manifest)

    paths = write_operation_bundle(
        operation_root,
        manifest=manifest,
        report=report,
    )

    assert paths["report"] == operation_root / "relatorio.md"
    assert paths["manifest"] == operation_root / "manifest.json"
    assert paths["log"] == operation_root / "logs" / "execution.jsonl"
    assert paths["artifacts"].is_dir()
    assert json.loads(paths["manifest"].read_text(encoding="utf-8")) == manifest

    with pytest.raises(FileExistsError, match="já existem"):
        write_operation_bundle(
            operation_root,
            manifest=manifest,
            report=report,
        )


def test_log_is_jsonl_and_rejects_secrets(tmp_path: Path) -> None:
    operation_root = tmp_path / "operation-test"
    log_path = append_log_event(
        operation_root,
        level="info",
        event="started",
        message="Operação iniciada.",
        details={"roots": 3},
        at=STARTED_AT,
    )
    event = json.loads(log_path.read_text(encoding="utf-8"))

    assert event == {
        "at": STARTED_AT,
        "level": "INFO",
        "event": "started",
        "message": "Operação iniciada.",
        "details": {"roots": 3},
    }

    with pytest.raises(ValueError, match="sensível"):
        append_log_event(
            operation_root,
            level="info",
            event="unsafe",
            message="Não gravar credenciais.",
            details={"api_key": "valor-secreto"},
        )


def test_reexecution_uses_a_new_operation_id(tmp_path: Path) -> None:
    first = _manifest(operation_id="drive-inventory-attempt-1")
    second = _manifest(operation_id="drive-inventory-attempt-2")

    first_paths = write_operation_bundle(
        tmp_path / str(first["operation_id"]),
        manifest=first,
        report=_report(first),
    )
    second_paths = write_operation_bundle(
        tmp_path / str(second["operation_id"]),
        manifest=second,
        report=_report(second),
    )

    assert first_paths["manifest"].exists()
    assert second_paths["manifest"].exists()
    assert first_paths["operation_root"] != second_paths["operation_root"]


def test_minimal_failure_record_is_recoverable(tmp_path: Path) -> None:
    operation_id = "snapshot-smoke-failed"
    operation_root = tmp_path / operation_id

    paths = write_minimal_failure_record(
        operation_root,
        module="snapshot_v2",
        operation_id=operation_id,
        spec_ref="specs/reinicio_analise_plenario/04_snapshot_discursos_v2/requirements.md",
        spec_version="approved-20260723",
        code_commit=COMMIT,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        objective="testar reconciliação",
        period="2010-01-01 a 2026-07-23",
        unit="discurso",
        error_summary="Um registro não foi reconciliado.",
        next_action="Inspecione o identificador e use um novo operation_id.",
        counts={"input_records": 1240, "output_records": 1227},
        errors_ref="artifacts/errors.csv",
    )

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    report = paths["report"].read_text(encoding="utf-8")
    log_event = json.loads(paths["log"].read_text(encoding="utf-8"))

    assert manifest["execution_status"] == "failed"
    assert manifest["scientific_gate"] == "not_evaluated"
    assert manifest["errors_ref"] == "artifacts/errors.csv"
    assert "nenhuma saída foi promovida" in report
    assert log_event["event"] == "operation_failed"
    assert log_event["message"] == "Um registro não foi reconciliado."


def test_manifest_rejects_invalid_status_and_noncanonical_references() -> None:
    manifest = _manifest()
    manifest["execution_status"] = "completed"
    manifest["report_ref"] = "resumo.txt"

    with pytest.raises(ValueError, match="Manifest inválido"):
        validate_manifest(manifest)


def _manifest(
    *,
    operation_id: str = "drive-inventory-test",
) -> dict[str, object]:
    return build_manifest(
        module="drive_inventory",
        operation_id=operation_id,
        spec_ref="specs/reinicio_analise_plenario/03_inventario_dados_drive/requirements.md",
        spec_version="approved-20260723",
        code_commit=COMMIT,
        execution_status="succeeded",
        scientific_gate="needs_review",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        inputs=[
            ArtifactRef(
                name="approved_roots",
                role="raízes aprovadas",
                uri="config/approved_drive_roots.json",
                format="json",
                size_bytes=100,
                sha256="b" * 64,
                rows=3,
            )
        ],
        outputs=[
            ArtifactRef(
                name="catalog",
                role="catálogo dos itens",
                uri="artifacts/catalogo.parquet",
                format="parquet",
                size_bytes=200,
                sha256="c" * 64,
                rows=10,
            )
        ],
        counts={"items_cataloged": 10},
        config_ref="config/approved_drive_roots.json",
        config_hash="b" * 64,
    )


def _report(manifest: dict[str, object]) -> str:
    return render_report(
        module=str(manifest["module"]),
        objective="catalogar artefatos",
        operation_id=str(manifest["operation_id"]),
        period="até 2026-07-23",
        unit="item",
        execution_status=str(manifest["execution_status"]),
        scientific_gate=str(manifest["scientific_gate"]),
        result_summary="Operação de teste concluída.",
        next_action="Revisar.",
    )
