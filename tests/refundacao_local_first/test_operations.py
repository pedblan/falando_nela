from __future__ import annotations

import json
from pathlib import Path

import pytest

from falando_nela.operations import (
    OperationError,
    RecoverableOperation,
    artifact_metadata,
    fingerprint,
)


def _operation(tmp_path: Path, *, config_fingerprint: str = "cfg") -> RecoverableOperation:
    return RecoverableOperation(
        manifest_path=tmp_path / "operation.json",
        operation_id="op-001",
        contract_version=1,
        implementation_version="r03-test",
        input_fingerprint="input",
        config_fingerprint=config_fingerprint,
        stages=(("discover", ()), ("map", ("discover",))),
        configuration={"source_remote": "raw-source-ro", "dry_run": True},
    )


def test_operation_persists_completed_artifact_and_reuses_it(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    artifact = tmp_path / "inventory.json"
    artifact.write_text('{"files":1}\n', encoding="utf-8")

    assert operation.begin("discover") is True
    with pytest.raises(OperationError, match="já está running"):
        operation.begin("discover")
    operation.complete("discover", artifact=artifact_metadata(artifact))

    assert operation.begin("discover") is False
    assert operation.snapshot()["stages"][0]["implementation_version"] == "r03-test"
    assert json.loads((tmp_path / "operation.json").read_text(encoding="utf-8"))["status"] == (
        "running"
    )


def test_artifact_change_invalidates_stage_and_dependents(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    operation.begin("discover")
    operation.complete("discover", artifact=artifact_metadata(first))
    operation.begin("map")
    operation.complete("map", artifact=artifact_metadata(second))

    first.write_text("changed", encoding="utf-8")

    assert operation.begin("discover") is True
    assert operation.stage("map")["status"] == "pending"
    assert operation.stage("discover")["attempts"] == 2


def test_operation_blocks_dependency_and_identity_mismatch(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    with pytest.raises(OperationError, match="dependências incompletas"):
        operation.begin("map")
    with pytest.raises(OperationError, match="entrada ou configuração diferente"):
        _operation(tmp_path, config_fingerprint="outra")


def test_interrupted_stage_requires_explicit_reconciliation_before_retry(tmp_path: Path) -> None:
    original_process = _operation(tmp_path)
    original_process.begin("discover")

    resumed_process = _operation(tmp_path)
    with pytest.raises(OperationError, match="reconciliação explícita"):
        resumed_process.begin("discover")

    resumed_process.recover_interrupted(
        "discover",
        remote_result_ambiguous=False,
        message="etapa local sem efeito remoto",
    )
    assert resumed_process.begin("discover") is True
    assert resumed_process.stage("discover")["attempts"] == 2


def test_complete_requires_matching_size_and_hash(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    artifact = tmp_path / "inventory.json"
    artifact.write_text("payload", encoding="utf-8")
    metadata = artifact_metadata(artifact)
    metadata["bytes"] += 1
    operation.begin("discover")

    with pytest.raises(OperationError, match="não confirmado"):
        operation.complete("discover", artifact=metadata)


def test_manifest_rejects_sensitive_configuration(tmp_path: Path) -> None:
    with pytest.raises(OperationError, match="campo sensível proibido"):
        RecoverableOperation(
            manifest_path=tmp_path / "operation.json",
            operation_id="op-secret",
            contract_version=1,
            implementation_version="1",
            input_fingerprint=fingerprint({"input": 1}),
            config_fingerprint=fingerprint({"config": 1}),
            stages=(("discover", ()),),
            configuration={"access_token": "TOKEN-SENTINELA-NAO-PODE-VAZAR"},
        )


@pytest.mark.parametrize(
    ("stages", "message"),
    [
        ((), "ao menos uma"),
        ((("a", ()), ("a", ())), "duplicados"),
        ((("a", ("missing",)),), "desconhecida"),
        ((("a", ("b",)), ("b", ("a",))), "ciclo"),
    ],
)
def test_operation_rejects_invalid_stage_graph(
    tmp_path: Path,
    stages: tuple[tuple[str, tuple[str, ...]], ...],
    message: str,
) -> None:
    with pytest.raises(OperationError, match=message):
        RecoverableOperation(
            manifest_path=tmp_path / "operation.json",
            operation_id="op-graph",
            contract_version=1,
            implementation_version="1",
            input_fingerprint="input",
            config_fingerprint="config",
            stages=stages,
            configuration={},
        )
