from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "specs"
    / "reinicio_analise_plenario"
    / "02_relatorios_colab"
    / "schema"
    / "manifest.schema.json"
)
EXECUTION_STATUSES = frozenset(
    {"not_started", "running", "succeeded", "failed", "cancelled"}
)
SCIENTIFIC_GATES = frozenset(
    {"not_applicable", "not_evaluated", "needs_review", "approved", "rejected"}
)
SECRET_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "token",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{8,}"),
)


@dataclass(frozen=True)
class ArtifactRef:
    """Referência compacta usada em ``inputs`` e ``outputs`` do manifest."""

    name: str
    role: str
    uri: str
    format: str
    size_bytes: int | None = None
    sha256: str | None = None
    rows: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CountRow:
    """Contagem humana acompanhada de seu universo ou regra."""

    label: str
    value: int
    universe_or_rule: str


@dataclass(frozen=True)
class ReportArtifact:
    """Entrada ou saída exibida no relatório humano."""

    kind: str
    name: str
    purpose: str
    uri: str
    action: str


def build_manifest(
    *,
    module: str,
    operation_id: str,
    spec_ref: str,
    spec_version: str,
    code_commit: str,
    execution_status: str,
    scientific_gate: str,
    started_at: str | None,
    finished_at: str | None,
    inputs: Sequence[ArtifactRef] = (),
    outputs: Sequence[ArtifactRef] = (),
    counts: Mapping[str, int] | None = None,
    analysis_run_id: str | None = None,
    snapshot_id: str | None = None,
    config_ref: str | None = None,
    config_hash: str | None = None,
    report_ref: str = "relatorio.md",
    log_ref: str = "logs/execution.jsonl",
    warnings_ref: str | None = None,
    errors_ref: str | None = None,
) -> dict[str, Any]:
    """Monta e valida um manifest com as 21 chaves do contrato D06."""

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": module,
        "operation_id": operation_id,
        "analysis_run_id": analysis_run_id,
        "snapshot_id": snapshot_id,
        "spec_ref": spec_ref,
        "spec_version": spec_version,
        "code_commit": code_commit,
        "execution_status": execution_status,
        "scientific_gate": scientific_gate,
        "started_at": started_at,
        "finished_at": finished_at,
        "inputs": [artifact.to_dict() for artifact in inputs],
        "outputs": [artifact.to_dict() for artifact in outputs],
        "config_ref": config_ref,
        "config_hash": config_hash,
        "counts": dict(counts or {}),
        "report_ref": report_ref,
        "log_ref": log_ref,
        "warnings_ref": warnings_ref,
        "errors_ref": errors_ref,
    }
    validate_manifest(manifest)
    return manifest


def validate_manifest(
    manifest: Mapping[str, Any],
    *,
    schema_path: Path = SCHEMA_PATH,
) -> None:
    """Valida schema, formatos e ausência de segredos; levanta ``ValueError``."""

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(manifest)), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{_json_path(error.path)}: {error.message}" for error in errors
        )
        raise ValueError(f"Manifest inválido: {details}")
    _assert_no_secrets(manifest)


def render_report(
    *,
    module: str,
    objective: str,
    operation_id: str,
    period: str,
    unit: str,
    execution_status: str,
    scientific_gate: str,
    result_summary: str,
    next_action: str,
    counts: Sequence[CountRow] = (),
    artifacts: Sequence[ReportArtifact] = (),
    warnings: Sequence[str] = (),
    errors: Sequence[str] = (),
    analysis_run_id: str | None = None,
    snapshot_id: str | None = None,
) -> str:
    """Renderiza o relatório humano canônico em Markdown simples."""

    if execution_status not in EXECUTION_STATUSES:
        raise ValueError(f"execution_status inválido: {execution_status}")
    if scientific_gate not in SCIENTIFIC_GATES:
        raise ValueError(f"scientific_gate inválido: {scientific_gate}")
    if any(count.value < 0 for count in counts):
        raise ValueError("Contagens do relatório não podem ser negativas.")

    lines = [
        "# Relatório da operação",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Módulo | {_md_cell(module)} |",
        f"| Objetivo | {_md_cell(objective)} |",
        f"| Operação | `{_md_cell(operation_id)}` |",
        f"| Execução científica | {_md_cell(analysis_run_id or 'não aplicável')} |",
        f"| Snapshot | {_md_cell(snapshot_id or 'não aplicável')} |",
        f"| Período observado | {_md_cell(period)} |",
        f"| Unidade observada | {_md_cell(unit)} |",
        f"| Estado da execução | **{execution_status}** |",
        f"| Gate científico | **{scientific_gate}** |",
        "",
        "## Leitura dos estados",
        "",
        _execution_sentence(execution_status),
        _scientific_sentence(scientific_gate),
        "",
        "## Resultado",
        "",
        result_summary.strip(),
        "",
        "## Contagens",
        "",
    ]

    if counts:
        lines.extend(
            [
                "| Contagem | Valor | Universo ou regra |",
                "|---|---:|---|",
                *[
                    f"| {_md_cell(row.label)} | {row.value} | "
                    f"{_md_cell(row.universe_or_rule)} |"
                    for row in counts
                ],
            ]
        )
    else:
        lines.append("Nenhuma contagem se aplica a esta operação.")

    lines.extend(["", "## Entradas e saídas", ""])
    if artifacts:
        lines.extend(
            [
                "| Tipo | Artefato | Finalidade | Local | Ação |",
                "|---|---|---|---|---|",
                *[
                    f"| {_md_cell(item.kind)} | {_md_cell(item.name)} | "
                    f"{_md_cell(item.purpose)} | `{_md_cell(item.uri)}` | "
                    f"{_md_cell(item.action)} |"
                    for item in artifacts
                ],
            ]
        )
    else:
        lines.append("Nenhuma entrada ou saída adicional foi registrada.")

    lines.extend(
        [
            "",
            "## Avisos",
            "",
            *_list_or_none(warnings),
            "",
            "## Erros",
            "",
            *_list_or_none(errors),
            "",
            "## Próxima ação",
            "",
            next_action.strip(),
            "",
        ]
    )
    report = "\n".join(lines)
    _assert_no_secrets(report)
    return report


def write_operation_bundle(
    operation_root: Path,
    *,
    manifest: Mapping[str, Any],
    report: str,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Grava relatório e manifest nos nomes canônicos do D06."""

    operation_root = operation_root.expanduser()
    operation_id = str(manifest.get("operation_id") or "")
    if operation_root.name != operation_id:
        raise ValueError(
            "O diretório da operação deve ter o mesmo nome de operation_id: "
            f"{operation_root.name!r} != {operation_id!r}."
        )
    validate_manifest(manifest)
    _assert_no_secrets(report)

    report_path = operation_root / "relatorio.md"
    manifest_path = operation_root / "manifest.json"
    existing = [path for path in (report_path, manifest_path) if path.exists()]
    if existing and not overwrite:
        paths = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Artefatos da operação já existem: {paths}")

    operation_root.mkdir(parents=True, exist_ok=True)
    (operation_root / "logs").mkdir(exist_ok=True)
    (operation_root / "artifacts").mkdir(exist_ok=True)
    _atomic_write(report_path, report if report.endswith("\n") else report + "\n")
    _atomic_write(
        manifest_path,
        json.dumps(dict(manifest), ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "operation_root": operation_root,
        "report": report_path,
        "manifest": manifest_path,
        "log": operation_root / "logs" / "execution.jsonl",
        "artifacts": operation_root / "artifacts",
    }


def append_log_event(
    operation_root: Path,
    *,
    level: str,
    event: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    at: str | None = None,
) -> Path:
    """Acrescenta um evento estruturado ao log técnico da operação."""

    payload = {
        "at": at or _utc_now(),
        "level": level.upper(),
        "event": event,
        "message": message,
        "details": dict(details or {}),
    }
    _assert_no_secrets(payload)
    log_path = operation_root.expanduser() / "logs" / "execution.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return log_path


def write_minimal_failure_record(
    operation_root: Path,
    *,
    module: str,
    operation_id: str,
    spec_ref: str,
    spec_version: str,
    code_commit: str,
    started_at: str,
    objective: str,
    period: str,
    unit: str,
    error_summary: str,
    next_action: str,
    finished_at: str | None = None,
    inputs: Sequence[ArtifactRef] = (),
    counts: Mapping[str, int] | None = None,
    analysis_run_id: str | None = None,
    snapshot_id: str | None = None,
    config_ref: str | None = None,
    config_hash: str | None = None,
    errors_ref: str | None = None,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Persiste o registro mínimo recuperável exigido pelo REL-R19."""

    finished_at = finished_at or _utc_now()
    manifest = build_manifest(
        module=module,
        operation_id=operation_id,
        analysis_run_id=analysis_run_id,
        snapshot_id=snapshot_id,
        spec_ref=spec_ref,
        spec_version=spec_version,
        code_commit=code_commit,
        execution_status="failed",
        scientific_gate="not_evaluated",
        started_at=started_at,
        finished_at=finished_at,
        inputs=inputs,
        counts=counts,
        config_ref=config_ref,
        config_hash=config_hash,
        errors_ref=errors_ref,
    )
    artifacts = [
        ReportArtifact(
            "Saída operacional",
            "manifest",
            "preservar estado e proveniência da falha",
            "manifest.json",
            "consultar somente para auditoria",
        ),
        ReportArtifact(
            "Saída operacional",
            "log",
            "localizar a etapa técnica da interrupção",
            "logs/execution.jsonl",
            "abrir para diagnóstico",
        ),
    ]
    if errors_ref:
        artifacts.append(
            ReportArtifact(
                "Saída",
                "erros",
                "detalhar os itens que causaram a falha",
                errors_ref,
                "revisar antes de reexecutar",
            )
        )
    report = render_report(
        module=module,
        objective=objective,
        operation_id=operation_id,
        analysis_run_id=analysis_run_id,
        snapshot_id=snapshot_id,
        period=period,
        unit=unit,
        execution_status="failed",
        scientific_gate="not_evaluated",
        result_summary="A operação foi interrompida e nenhuma saída foi promovida.",
        counts=[
            CountRow(label=name, value=value, universe_or_rule="estado no ponto da falha")
            for name, value in (counts or {}).items()
        ],
        artifacts=artifacts,
        errors=[error_summary],
        next_action=next_action,
    )
    paths = write_operation_bundle(
        operation_root,
        manifest=manifest,
        report=report,
        overwrite=overwrite,
    )
    append_log_event(
        operation_root,
        level="ERROR",
        event="operation_failed",
        message=error_summary,
        details={"errors_ref": errors_ref},
        at=finished_at,
    )
    return paths


def _execution_sentence(status: str) -> str:
    return {
        "not_started": "O programa ainda não começou.",
        "running": "O programa ainda está em execução.",
        "succeeded": "O programa terminou normalmente.",
        "failed": "O programa terminou com falha.",
        "cancelled": "A execução foi cancelada.",
    }[status]


def _scientific_sentence(gate: str) -> str:
    return {
        "not_applicable": "Esta operação não produz uma decisão científica.",
        "not_evaluated": "O resultado não foi avaliado cientificamente.",
        "needs_review": "O resultado ainda precisa de revisão humana.",
        "approved": "O resultado foi aprovado para o uso definido em sua spec.",
        "rejected": "O resultado foi rejeitado para uso científico.",
    }[gate]


def _list_or_none(items: Sequence[str]) -> list[str]:
    if not items:
        return ["Nenhum."]
    return [f"{index}. {item.strip()}" for index, item in enumerate(items, start=1)]


def _md_cell(value: str) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ").strip()


def _json_path(path: Any) -> str:
    parts = list(path)
    if not parts:
        return "$"
    return "$." + ".".join(str(part) for part in parts)


def _assert_no_secrets(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in SECRET_KEYS and item not in (None, "", "[REDACTED]"):
                raise ValueError(f"Conteúdo sensível detectado no campo {key!r}.")
            _assert_no_secrets(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_secrets(item)
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise ValueError("Conteúdo com aparência de segredo detectado.")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
