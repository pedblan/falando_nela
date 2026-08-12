from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from falando_nela.raw import atomic_write_json, canonical_json_bytes, sha256_bytes, sha256_file

StageStatus = Literal["pending", "running", "completed", "failed", "blocked", "cancelled"]
SENSITIVE_CONFIGURATION_MARKERS = ("credential", "password", "secret", "token")


class OperationError(RuntimeError):
    """Estado ou transição inválida de uma operação recuperável."""


def fingerprint(value: Any) -> str:
    return f"sha256:{sha256_bytes(canonical_json_bytes(value))}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def artifact_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OperationError(f"artefato ausente: {path}")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


class RecoverableOperation:
    def __init__(
        self,
        *,
        manifest_path: Path,
        operation_id: str,
        contract_version: int,
        implementation_version: str,
        input_fingerprint: str,
        config_fingerprint: str,
        stages: Sequence[tuple[str, Sequence[str]]],
        configuration: dict[str, Any],
    ) -> None:
        self.manifest_path = manifest_path
        self._active_stages: set[str] = set()
        _assert_public_configuration(configuration)
        stage_definitions = tuple((stage_id, tuple(depends_on)) for stage_id, depends_on in stages)
        _validate_stage_definitions(stage_definitions)
        if manifest_path.exists():
            self.data = self._load()
            self._validate_identity(
                operation_id=operation_id,
                contract_version=contract_version,
                input_fingerprint=input_fingerprint,
                config_fingerprint=config_fingerprint,
            )
        else:
            self.data = {
                "operation_id": operation_id,
                "contract_version": contract_version,
                "implementation_version": implementation_version,
                "input_fingerprint": input_fingerprint,
                "config_fingerprint": config_fingerprint,
                "configuration": copy.deepcopy(configuration),
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "status": "pending",
                "stages": [
                    self._new_stage(stage_id, depends_on, implementation_version)
                    for stage_id, depends_on in stage_definitions
                ],
            }
            self._save()

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def stage(self, stage_id: str) -> dict[str, Any]:
        for stage in self.data["stages"]:
            if stage["id"] == stage_id:
                return stage
        raise OperationError(f"etapa desconhecida: {stage_id}")

    def artifact_is_valid(self, stage_id: str) -> bool:
        stage = self.stage(stage_id)
        artifact = stage.get("artifact")
        if stage.get("status") != "completed" or not isinstance(artifact, dict):
            return False
        path = Path(str(artifact.get("path", "")))
        return (
            path.is_file()
            and path.stat().st_size == artifact.get("bytes")
            and sha256_file(path) == artifact.get("sha256")
        )

    def begin(self, stage_id: str) -> bool:
        stage = self.stage(stage_id)
        self._require_dependencies(stage)
        if self.artifact_is_valid(stage_id):
            return False
        if stage["status"] == "running":
            if stage_id not in self._active_stages:
                raise OperationError(
                    f"etapa interrompida exige reconciliação explícita: {stage_id}"
                )
            raise OperationError(f"etapa já está running: {stage_id}")
        if stage["status"] == "completed":
            self.invalidate(stage_id, reason="artifact_missing_or_changed")
            stage = self.stage(stage_id)
        attempt_number = int(stage["attempts"]) + 1
        attempt = {
            "number": attempt_number,
            "status": "running",
            "started_at": utc_now(),
            "completed_at": None,
            "error": None,
            "remote_result_ambiguous": False,
        }
        stage.update(
            {
                "status": "running",
                "attempts": attempt_number,
                "started_at": attempt["started_at"],
                "completed_at": None,
                "artifact": None,
                "error": None,
                "remote_result_ambiguous": False,
            }
        )
        stage["attempt_history"].append(attempt)
        self._active_stages.add(stage_id)
        self.data["status"] = "running"
        self._save()
        return True

    def complete(
        self,
        stage_id: str,
        *,
        artifact: dict[str, Any],
        remote_id: str | None = None,
        usage: dict[str, int] | None = None,
        estimated_cost_usd: str = "0.000000",
    ) -> None:
        stage = self.stage(stage_id)
        if stage["status"] != "running":
            raise OperationError(f"etapa não está running: {stage_id}")
        path = Path(str(artifact.get("path", "")))
        if (
            not path.is_file()
            or path.stat().st_size != artifact.get("bytes")
            or sha256_file(path) != artifact.get("sha256")
        ):
            raise OperationError(f"artefato não confirmado: {stage_id}")
        completed_at = utc_now()
        stage.update(
            {
                "status": "completed",
                "completed_at": completed_at,
                "artifact": copy.deepcopy(artifact),
                "remote_id": remote_id,
                "usage": usage or {},
                "estimated_cost_usd": estimated_cost_usd,
                "error": None,
                "remote_result_ambiguous": False,
            }
        )
        attempt = stage["attempt_history"][-1]
        attempt.update({"status": "completed", "completed_at": completed_at})
        self._active_stages.discard(stage_id)
        self.data["status"] = (
            "completed"
            if all(item["status"] == "completed" for item in self.data["stages"])
            else "running"
        )
        self._save()

    def fail(
        self,
        stage_id: str,
        *,
        error_type: str,
        message: str,
        blocked: bool = False,
        remote_result_ambiguous: bool = False,
        remote_id: str | None = None,
    ) -> None:
        stage = self.stage(stage_id)
        if stage["status"] != "running":
            raise OperationError(f"etapa não está running: {stage_id}")
        status: StageStatus = "blocked" if blocked else "failed"
        error = {"type": error_type, "message": message}
        completed_at = utc_now()
        stage.update(
            {
                "status": status,
                "completed_at": completed_at,
                "error": error,
                "remote_result_ambiguous": remote_result_ambiguous,
                "remote_id": remote_id,
            }
        )
        stage["attempt_history"][-1].update(
            {
                "status": status,
                "completed_at": completed_at,
                "error": error,
                "remote_result_ambiguous": remote_result_ambiguous,
            }
        )
        self._active_stages.discard(stage_id)
        self.data["status"] = status
        self._save()

    def cancel(self, stage_id: str, *, reason: str) -> None:
        stage = self.stage(stage_id)
        if stage["status"] not in {"pending", "running", "failed", "blocked"}:
            raise OperationError(f"etapa não pode ser cancelada: {stage_id}")
        stage["status"] = "cancelled"
        stage["error"] = {"type": "cancelled", "message": reason}
        stage["completed_at"] = utc_now()
        if stage["attempt_history"] and stage["attempt_history"][-1]["status"] == "running":
            stage["attempt_history"][-1].update(
                {
                    "status": "cancelled",
                    "completed_at": stage["completed_at"],
                    "error": stage["error"],
                }
            )
        self._active_stages.discard(stage_id)
        self.data["status"] = "cancelled"
        self._save()

    def recover_interrupted(
        self, stage_id: str, *, remote_result_ambiguous: bool, message: str
    ) -> None:
        stage = self.stage(stage_id)
        if stage["status"] != "running" or stage_id in self._active_stages:
            raise OperationError(f"etapa não é uma execução interrompida: {stage_id}")
        completed_at = utc_now()
        error = {"type": "interrupted", "message": message}
        stage.update(
            {
                "status": "failed",
                "completed_at": completed_at,
                "error": error,
                "remote_result_ambiguous": remote_result_ambiguous,
            }
        )
        if stage["attempt_history"]:
            stage["attempt_history"][-1].update(
                {
                    "status": "failed",
                    "completed_at": completed_at,
                    "error": error,
                    "remote_result_ambiguous": remote_result_ambiguous,
                }
            )
        self.data["status"] = "failed"
        self._save()

    def invalidate(self, stage_id: str, *, reason: str) -> None:
        target_ids = {stage_id}
        changed = True
        while changed:
            changed = False
            for stage in self.data["stages"]:
                if stage["id"] not in target_ids and target_ids.intersection(stage["depends_on"]):
                    target_ids.add(stage["id"])
                    changed = True
        for stage in self.data["stages"]:
            if stage["id"] in target_ids:
                stage.update(
                    {
                        "status": "pending",
                        "started_at": None,
                        "completed_at": None,
                        "artifact": None,
                        "error": {"type": "invalidated", "message": reason},
                        "remote_result_ambiguous": False,
                    }
                )
        self.data["status"] = "pending"
        self._save()

    def _require_dependencies(self, stage: dict[str, Any]) -> None:
        incomplete = [
            dependency
            for dependency in stage["depends_on"]
            if self.stage(dependency)["status"] != "completed"
        ]
        if incomplete:
            raise OperationError(f"dependências incompletas de {stage['id']}: {incomplete}")

    def _load(self) -> dict[str, Any]:
        import json

        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationError("manifesto existente é ilegível") from exc
        if not isinstance(data, dict) or not isinstance(data.get("stages"), list):
            raise OperationError("manifesto existente tem schema inválido")
        return data

    def _validate_identity(
        self,
        *,
        operation_id: str,
        contract_version: int,
        input_fingerprint: str,
        config_fingerprint: str,
    ) -> None:
        expected = {
            "operation_id": operation_id,
            "contract_version": contract_version,
            "input_fingerprint": input_fingerprint,
            "config_fingerprint": config_fingerprint,
        }
        observed = {key: self.data.get(key) for key in expected}
        if observed != expected:
            raise OperationError("operation_id já existe com entrada ou configuração diferente")

    @staticmethod
    def _new_stage(
        stage_id: str, depends_on: Sequence[str], implementation_version: str
    ) -> dict[str, Any]:
        return {
            "id": stage_id,
            "depends_on": list(depends_on),
            "status": "pending",
            "attempts": 0,
            "implementation_version": implementation_version,
            "started_at": None,
            "completed_at": None,
            "artifact": None,
            "remote_id": None,
            "usage": {},
            "estimated_cost_usd": "0.000000",
            "error": None,
            "remote_result_ambiguous": False,
            "attempt_history": [],
        }

    def _save(self) -> None:
        self.data["updated_at"] = utc_now()
        atomic_write_json(self.manifest_path, self.data)


def _assert_public_configuration(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if any(marker in normalized for marker in SENSITIVE_CONFIGURATION_MARKERS):
                dotted = ".".join((*path, str(key)))
                raise OperationError(f"campo sensível proibido no manifesto: {dotted}")
            _assert_public_configuration(item, path=(*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_public_configuration(item, path=(*path, str(index)))


def _validate_stage_definitions(stages: Sequence[tuple[str, Sequence[str]]]) -> None:
    if not stages:
        raise OperationError("a operação exige ao menos uma etapa")
    identifiers = [stage_id for stage_id, _ in stages]
    if any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", stage_id) for stage_id in identifiers
    ):
        raise OperationError("id de etapa inválido")
    if len(set(identifiers)) != len(identifiers):
        raise OperationError("ids de etapa duplicados")
    known = set(identifiers)
    graph = {stage_id: tuple(depends_on) for stage_id, depends_on in stages}
    for stage_id, dependencies in graph.items():
        if any(dependency not in known for dependency in dependencies):
            raise OperationError(f"dependência desconhecida em {stage_id}")
        if stage_id in dependencies:
            raise OperationError(f"etapa não pode depender de si mesma: {stage_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visited:
            return
        if stage_id in visiting:
            raise OperationError(f"ciclo de dependências inclui: {stage_id}")
        visiting.add(stage_id)
        for dependency in graph[stage_id]:
            visit(dependency)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in identifiers:
        visit(stage_id)
