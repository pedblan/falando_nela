from __future__ import annotations

import csv
import json
import mimetypes
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from relatorios_operacionais import (
    ArtifactRef,
    CountRow,
    ReportArtifact,
    append_log_event,
    build_manifest,
    render_report,
    write_minimal_failure_record,
    write_operation_bundle,
)


APPROVED_COLAB_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_inventory")
DEFAULT_MAX_STRUCTURED_BYTES = 5 * 1024 * 1024
SPEC_REF = (
    "specs/reinicio_analise_plenario/"
    "03_inventario_dados_drive/requirements.md"
)
SPEC_VERSION = "approved-20260723"

CATALOG_FIELDS = [
    "relative_path",
    "parent_relative_path",
    "name",
    "item_type",
    "suffix",
    "mime_type",
    "size_bytes",
    "modified_at",
    "item_class",
    "layer",
    "source",
    "classification_origin",
    "confidence",
    "classification_reason",
    "content_candidate",
    "content_inspected",
    "content_issue",
]
EXECUTION_FIELDS = [
    "manifest_relative_path",
    "operation_id",
    "analysis_run_id",
    "snapshot_id",
    "module",
    "period",
    "declared_status",
    "execution_status",
    "scientific_gate",
    "input_references",
    "output_references",
    "valid_references",
    "missing_references",
    "ambiguous_references",
    "status_origin",
]
REFERENCE_FIELDS = [
    "manifest_relative_path",
    "json_path",
    "role",
    "reference",
    "status",
    "resolved_relative_path",
]
ISSUE_FIELDS = [
    "issue_type",
    "severity",
    "item_relative_path",
    "reference",
    "detail",
]
MIGRATION_FIELDS = [
    "proposal_id",
    "source_relative_path",
    "proposed_action",
    "reason",
    "requires_approval",
    "executed",
]
UNIVERSE_FIELDS = [
    "source",
    "layer",
    "item_class",
    "item_type",
    "unit",
    "items",
    "files",
    "size_bytes",
    "content_candidates",
    "content_inspected",
    "coverage_rule",
]
STRUCTURED_SUFFIXES = {".json", ".md", ".csv"}
STRUCTURED_KEYWORDS = {
    "catalog",
    "catalogo",
    "config",
    "inconsistencia",
    "manifest",
    "mapa",
    "relatorio",
    "report",
    "review",
    "revisao",
}
REFERENCE_KEY_TOKENS = {
    "dir",
    "file",
    "input",
    "log",
    "manifest",
    "output",
    "path",
    "ref",
    "root",
    "uri",
}
PATHLIKE_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".parquet",
    ".txt",
    ".xlsx",
    ".zip",
}


def write_drive_inventory(
    *,
    data_root: Path,
    output_base: Path,
    operation_id: str,
    code_commit: str,
    max_structured_bytes: int = DEFAULT_MAX_STRUCTURED_BYTES,
) -> dict[str, Any]:
    """Inventaria uma raiz montada sem escrever nela.

    Os resultados são sempre gravados em ``output_base/operation_id``. A
    função recusa uma saída contida na raiz examinada e uma reexecução com o
    mesmo ``operation_id``.
    """

    data_root = data_root.expanduser().resolve()
    output_base = output_base.expanduser().resolve()
    operation_root = output_base / operation_id
    _validate_preflight(
        data_root=data_root,
        output_base=output_base,
        operation_root=operation_root,
        operation_id=operation_id,
        code_commit=code_commit,
        max_structured_bytes=max_structured_bytes,
    )

    started_at = _utc_now()
    append_log_event(
        operation_root,
        level="INFO",
        event="inventory_started",
        message="Inventário somente leitura iniciado.",
        details={
            "data_root": str(data_root),
            "max_structured_bytes": max_structured_bytes,
        },
        at=started_at,
    )

    try:
        catalog, issues = scan_metadata(data_root)
        append_log_event(
            operation_root,
            level="INFO",
            event="metadata_scanned",
            message="Passagem de metadados concluída.",
            details={"items": len(catalog), "issues": len(issues)},
        )

        executions, references, content_issues = inspect_structured_items(
            data_root=data_root,
            catalog=catalog,
            max_structured_bytes=max_structured_bytes,
        )
        issues.extend(content_issues)
        issues.extend(find_execution_conflicts(executions))
        issues.extend(
            find_possible_orphans(
                catalog=catalog,
                executions=executions,
                references=references,
            )
        )
        issues.extend(find_potential_duplicates(catalog))
        universes = build_universe_catalog(catalog)
        migration = build_migration_proposals(issues)
        append_log_event(
            operation_root,
            level="INFO",
            event="structured_items_inspected",
            message="Passagem seletiva de conteúdo concluída.",
            details={
                "executions": len(executions),
                "references": len(references),
                "universe_groups": len(universes),
                "issues": len(issues),
            },
        )

        artifact_root = operation_root / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=True)
        artifact_specs = [
            ("catalogo_dados.csv", catalog, CATALOG_FIELDS),
            ("catalogo_execucoes.csv", executions, EXECUTION_FIELDS),
            ("referencias.csv", references, REFERENCE_FIELDS),
            ("inconsistencias.csv", issues, ISSUE_FIELDS),
            ("plano_migracao.csv", migration, MIGRATION_FIELDS),
            ("catalogo_universos.csv", universes, UNIVERSE_FIELDS),
        ]
        output_refs: list[ArtifactRef] = []
        for name, rows, fields in artifact_specs:
            path = artifact_root / name
            _write_csv(path, rows, fields)
            output_refs.append(
                _artifact_ref(
                    path,
                    operation_root=operation_root,
                    role=_artifact_role(name),
                    rows=len(rows),
                )
            )

        map_path = artifact_root / "mapa_dados.md"
        map_path.write_text(
            render_data_map(
                data_root=data_root,
                catalog=catalog,
                executions=executions,
                references=references,
                issues=issues,
                universes=universes,
            ),
            encoding="utf-8",
        )
        output_refs.append(
            _artifact_ref(
                map_path,
                operation_root=operation_root,
                role="mapa humano do universo inventariado",
                rows=None,
            )
        )

        config = {
            "data_root": str(data_root),
            "max_structured_bytes": max_structured_bytes,
            "structured_suffixes": sorted(STRUCTURED_SUFFIXES),
            "structured_keywords": sorted(STRUCTURED_KEYWORDS),
            "read_policy": "metadata_then_selected_structured_files",
            "write_policy": "outside_data_root_only",
        }
        config_path = artifact_root / "config.json"
        config_text = json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        config_path.write_text(config_text, encoding="utf-8")
        config_hash = sha256(config_text.encode("utf-8")).hexdigest()
        output_refs.append(
            _artifact_ref(
                config_path,
                operation_root=operation_root,
                role="configuração efetiva do inventário",
                rows=None,
            )
        )

        finished_at = _utc_now()
        counts = _manifest_counts(
            catalog=catalog,
            executions=executions,
            references=references,
            issues=issues,
            universes=universes,
        )
        input_ref = ArtifactRef(
            name="approved_data_root",
            role="raiz aprovada para inventário somente leitura",
            uri=str(data_root),
            format="directory",
            size_bytes=sum(
                int(row["size_bytes"])
                for row in catalog
                if row["item_type"] == "file" and row["size_bytes"] != ""
            ),
            sha256=None,
            rows=len(catalog),
        )
        manifest = build_manifest(
            module="drive_inventory",
            operation_id=operation_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            execution_status="succeeded",
            scientific_gate="needs_review",
            started_at=started_at,
            finished_at=finished_at,
            inputs=[input_ref],
            outputs=output_refs,
            counts=counts,
            config_ref="artifacts/config.json",
            config_hash=config_hash,
            warnings_ref="artifacts/inconsistencias.csv" if issues else None,
        )
        report = render_inventory_report(
            data_root=data_root,
            operation_id=operation_id,
            catalog=catalog,
            executions=executions,
            references=references,
            issues=issues,
            universes=universes,
            output_refs=output_refs,
        )
        paths = write_operation_bundle(
            operation_root,
            manifest=manifest,
            report=report,
        )
        append_log_event(
            operation_root,
            level="INFO",
            event="inventory_succeeded",
            message="Inventário concluído; revisão humana necessária.",
            details=counts,
            at=finished_at,
        )
        return {
            "paths": paths,
            "manifest": manifest,
            "catalog": catalog,
            "executions": executions,
            "references": references,
            "issues": issues,
            "universes": universes,
        }
    except Exception as exc:
        error_summary = f"{type(exc).__name__}: {exc}"
        write_minimal_failure_record(
            operation_root,
            module="drive_inventory",
            operation_id=operation_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            started_at=started_at,
            objective="inventariar a raiz aprovada sem alterar o Drive",
            period="conteúdo disponível no momento da execução",
            unit="item sob a raiz aprovada",
            error_summary=error_summary,
            next_action=(
                "Leia somente o resumo e o log, corrija a causa e reexecute "
                "com um novo operation_id."
            ),
            overwrite=True,
        )
        raise


def scan_metadata(data_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Executa a passagem 1 sem abrir conteúdo de arquivos."""

    catalog: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for current_root, dirnames, filenames in os.walk(data_root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        current_path = Path(current_root)

        symlink_dirs = [
            name for name in dirnames if (current_path / name).is_symlink()
        ]
        dirnames[:] = [name for name in dirnames if name not in symlink_dirs]
        for name in symlink_dirs:
            path = current_path / name
            row, issue = _metadata_row(path, data_root=data_root, item_type="symlink")
            catalog.append(row)
            if issue:
                issues.append(issue)

        for name in dirnames:
            path = current_path / name
            row, issue = _metadata_row(path, data_root=data_root, item_type="directory")
            catalog.append(row)
            if issue:
                issues.append(issue)

        for name in filenames:
            path = current_path / name
            item_type = "symlink" if path.is_symlink() else "file"
            row, issue = _metadata_row(path, data_root=data_root, item_type=item_type)
            catalog.append(row)
            if issue:
                issues.append(issue)

    catalog.sort(key=lambda row: str(row["relative_path"]))
    return catalog, issues


def inspect_structured_items(
    *,
    data_root: Path,
    catalog: list[dict[str, Any]],
    max_structured_bytes: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    """Abre apenas os candidatos estruturados autorizados pela passagem 2."""

    executions: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    row_by_relative = {str(row["relative_path"]): row for row in catalog}

    for relative_path, row in sorted(row_by_relative.items()):
        if row["item_type"] != "file" or not row["content_candidate"]:
            continue
        size = row["size_bytes"]
        if not isinstance(size, int) or size > max_structured_bytes:
            row["content_issue"] = "skipped_size_limit"
            continue

        path = data_root / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            row["content_issue"] = f"read_error:{type(exc).__name__}"
            issues.append(
                _issue(
                    "structured_read_error",
                    "warning",
                    relative_path,
                    "",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        row["content_inspected"] = True
        suffix = str(row["suffix"])
        if suffix == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                row["content_issue"] = "invalid_json"
                issues.append(
                    _issue(
                        "invalid_json",
                        "warning",
                        relative_path,
                        "",
                        f"linha {exc.lineno}, coluna {exc.colno}",
                    )
                )
                continue
            if row["item_class"] == "manifest" and isinstance(payload, dict):
                manifest_references = list(
                    _extract_references(
                        payload,
                        manifest_relative_path=relative_path,
                        data_root=data_root,
                        manifest_parent=path.parent,
                    )
                )
                references.extend(manifest_references)
                execution = _execution_row(
                    payload,
                    manifest_relative_path=relative_path,
                    references=manifest_references,
                )
                executions.append(execution)
                parent_relative = Path(relative_path).parent.as_posix()
                parent_row = row_by_relative.get(parent_relative)
                if parent_row and parent_row["item_type"] == "directory":
                    parent_row.update(
                        {
                            "item_class": "execution",
                            "classification_origin": "manifest_reference",
                            "confidence": "high",
                            "classification_reason": (
                                "diretório contém manifest estruturado reconhecido"
                            ),
                        }
                    )
                for reference in manifest_references:
                    if reference["status"] in {
                        "missing",
                        "ambiguous",
                        "outside_root",
                    }:
                        issues.append(
                            _issue(
                                {
                                    "missing": "declared_reference_missing",
                                    "ambiguous": "declared_reference_ambiguous",
                                    "outside_root": "declared_reference_outside_root",
                                }[str(reference["status"])],
                                "warning",
                                relative_path,
                                str(reference["reference"]),
                                f"referência declarada em {reference['json_path']}",
                            )
                        )
        elif suffix == ".csv":
            try:
                next(csv.reader(StringIO(text)), [])
            except csv.Error as exc:
                row["content_issue"] = "invalid_csv_header"
                issues.append(
                    _issue(
                        "invalid_csv_header",
                        "warning",
                        relative_path,
                        "",
                        str(exc),
                    )
                )

    executions.sort(key=lambda row: str(row["manifest_relative_path"]))
    references.sort(
        key=lambda row: (
            str(row["manifest_relative_path"]),
            str(row["json_path"]),
            str(row["reference"]),
        )
    )
    return executions, references, issues


def find_execution_conflicts(
    executions: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    by_operation: dict[str, list[str]] = defaultdict(list)
    for execution in executions:
        operation_id = str(execution.get("operation_id") or "").strip()
        if operation_id:
            by_operation[operation_id].append(
                str(execution.get("manifest_relative_path") or "")
            )
    issues = []
    for operation_id, paths in sorted(by_operation.items()):
        if len(paths) <= 1:
            continue
        issues.append(
            _issue(
                "multiple_manifests_same_operation",
                "warning",
                "",
                operation_id,
                " | ".join(sorted(paths)),
            )
        )
    return issues


def find_potential_duplicates(
    catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    for row in catalog:
        if row.get("item_type") != "file":
            continue
        size = row.get("size_bytes")
        name = str(row.get("name") or "")
        if isinstance(size, int) and size > 0 and name:
            groups[(name.casefold(), size)].append(str(row["relative_path"]))
    issues = []
    for (name, size), paths in sorted(groups.items()):
        if len(paths) <= 1:
            continue
        issues.append(
            _issue(
                "potential_duplicate_metadata",
                "info",
                "",
                f"{name}:{size}",
                " | ".join(sorted(paths)),
            )
        )
    return issues


def find_possible_orphans(
    *,
    catalog: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
    references: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Sinaliza arquivos não referenciados sob execuções, sem afirmar orfandade."""

    execution_roots = {
        Path(str(execution["manifest_relative_path"])).parent.as_posix()
        for execution in executions
    }
    referenced = {
        str(reference["resolved_relative_path"])
        for reference in references
        if reference["status"] == "valid"
    }
    issues = []
    for row in catalog:
        if row.get("item_type") != "file":
            continue
        relative_path = str(row["relative_path"])
        if relative_path in referenced or row.get("item_class") in {
            "manifest",
            "report",
            "log",
            "review",
        }:
            continue
        if not any(
            relative_path.startswith(f"{root}/")
            for root in execution_roots
        ):
            continue
        issues.append(
            _issue(
                "possible_orphan_output",
                "info",
                relative_path,
                "",
                "arquivo sob execução reconhecida, sem referência resolvida em manifest",
            )
        )
    return issues


def build_universe_catalog(
    catalog: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reconcilia todos os itens em grupos mutuamente exclusivos de metadados."""

    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in catalog:
        key = (
            str(row.get("source") or "unknown"),
            str(row.get("layer") or "unknown"),
            str(row.get("item_class") or "unknown"),
            str(row.get("item_type") or "unknown"),
        )
        group = groups.setdefault(
            key,
            {
                "source": key[0],
                "layer": key[1],
                "item_class": key[2],
                "item_type": key[3],
                "unit": "filesystem_item",
                "items": 0,
                "files": 0,
                "size_bytes": 0,
                "content_candidates": 0,
                "content_inspected": 0,
                "coverage_rule": (
                    "cada item descendente da raiz pertence exatamente a um grupo"
                ),
            },
        )
        group["items"] += 1
        if row.get("item_type") == "file":
            group["files"] += 1
            size = row.get("size_bytes")
            if isinstance(size, int):
                group["size_bytes"] += size
        group["content_candidates"] += int(bool(row.get("content_candidate")))
        group["content_inspected"] += int(bool(row.get("content_inspected")))

    universes = [groups[key] for key in sorted(groups)]
    if sum(int(row["items"]) for row in universes) != len(catalog):
        raise ValueError("Catálogo de universos não reconcilia com o catálogo de itens.")
    return universes


def build_migration_proposals(
    issues: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Transforma achados em propostas de revisão; nunca em ações executadas."""

    rows = []
    for index, issue in enumerate(issues, start=1):
        rows.append(
            {
                "proposal_id": f"proposal-{index:05d}",
                "source_relative_path": str(
                    issue.get("item_relative_path")
                    or issue.get("reference")
                    or ""
                ),
                "proposed_action": "review_only",
                "reason": str(issue.get("issue_type") or "unknown"),
                "requires_approval": "true",
                "executed": "false",
            }
        )
    return rows


def render_data_map(
    *,
    data_root: Path,
    catalog: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
    references: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    universes: Sequence[Mapping[str, Any]],
) -> str:
    class_counts = Counter(str(row["item_class"]) for row in catalog)
    layer_counts = Counter(str(row["layer"]) for row in catalog)
    source_counts = Counter(str(row["source"]) for row in catalog)
    execution_counts = Counter(str(row["execution_status"]) for row in executions)
    reference_counts = Counter(str(row["status"]) for row in references)
    reconciled_items = sum(int(row["items"]) for row in universes)
    lines = [
        "# Mapa dos dados no Drive",
        "",
        "## Escopo",
        "",
        f"- Raiz examinada: `{data_root}`",
        "- Unidade do catálogo: item descendente da raiz",
        f"- Itens catalogados: **{len(catalog)}**",
        "- Escritas na raiz examinada: **0**",
        "- Gate científico: **needs_review**",
        "",
        "## Itens por classe",
        "",
        *_counter_table(class_counts, "Classe"),
        "",
        "## Itens por camada",
        "",
        *_counter_table(layer_counts, "Camada"),
        "",
        "## Itens por fonte",
        "",
        *_counter_table(source_counts, "Fonte"),
        "",
        "## Execuções aparentes",
        "",
        f"Foram reconstruídas **{len(executions)}** execuções a partir de manifests.",
        "",
        *_counter_table(execution_counts, "Estado operacional"),
        "",
        "## Referências declaradas",
        "",
        *_counter_table(reference_counts, "Situação"),
        "",
        "## Reconciliação do universo",
        "",
        f"- Grupos mutuamente exclusivos: **{len(universes)}**",
        f"- Itens no catálogo principal: **{len(catalog)}**",
        f"- Itens somados no catálogo de universos: **{reconciled_items}**",
        "- Regra: cada item descendente da raiz pertence exatamente a um grupo.",
        "- Unidade nesta fase: item do sistema de arquivos, não discurso ou transcrição.",
        "",
        "## Inconsistências",
        "",
        f"Foram sinalizados **{len(issues)}** itens para revisão. Nenhum foi corrigido.",
        "Consulte `inconsistencias.csv` e `plano_migracao.csv`.",
        "",
        "## Próxima ação",
        "",
        "Revise a cobertura de todas as fontes, camadas, classes e unidades, além "
        "das bases candidatas e inconsistências. Não inicie migração nem snapshot "
        "enquanto o gate permanecer em `needs_review`.",
        "",
    ]
    return "\n".join(lines)


def render_inventory_report(
    *,
    data_root: Path,
    operation_id: str,
    catalog: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
    references: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    universes: Sequence[Mapping[str, Any]],
    output_refs: Sequence[ArtifactRef],
) -> str:
    files = sum(row["item_type"] == "file" for row in catalog)
    directories = sum(row["item_type"] == "directory" for row in catalog)
    missing_references = sum(row["status"] == "missing" for row in references)
    ambiguous_references = sum(
        row["status"] == "ambiguous" for row in references
    )
    reconciled_items = sum(int(row["items"]) for row in universes)
    unknown_layer_items = sum(
        1 for row in catalog if row["layer"] == "unknown"
    )
    unknown_source_items = sum(
        1 for row in catalog if row["source"] == "unknown"
    )
    artifacts = [
        ReportArtifact(
            "Entrada",
            "raiz aprovada",
            "universo do inventário somente leitura",
            str(data_root),
            "não alterar",
        ),
        *[
            ReportArtifact(
                "Saída",
                artifact.name,
                artifact.role,
                artifact.uri,
                "revisar" if artifact.name != "config" else "consultar se necessário",
            )
            for artifact in output_refs
        ],
    ]
    warnings = []
    if issues:
        warnings.append(
            f"Há {len(issues)} inconsistências ou duplicidades potenciais para revisão."
        )
    if missing_references:
        warnings.append(
            f"Há {missing_references} referências declaradas que não foram resolvidas."
        )
    if ambiguous_references:
        warnings.append(
            f"Há {ambiguous_references} referências com mais de um destino possível."
        )
    if unknown_layer_items or unknown_source_items:
        warnings.append(
            f"Há {unknown_layer_items} itens sem camada e "
            f"{unknown_source_items} itens sem fonte classificadas."
        )

    return render_report(
        module="drive_inventory",
        objective="catalogar a raiz aprovada sem alterar o Drive",
        operation_id=operation_id,
        period="conteúdo disponível no momento da execução",
        unit="item descendente da raiz aprovada",
        execution_status="succeeded",
        scientific_gate="needs_review",
        result_summary=(
            f"Foram catalogados {len(catalog)} itens: {files} arquivos e "
            f"{directories} diretórios. O programa terminou, mas o inventário "
            "ainda não está aprovado."
        ),
        counts=[
            CountRow("itens catalogados", len(catalog), "descendentes da raiz aprovada"),
            CountRow("arquivos", files, "itens catalogados com tipo file"),
            CountRow(
                "diretórios",
                directories,
                "itens catalogados com tipo directory",
            ),
            CountRow(
                "execuções aparentes",
                len(executions),
                "manifests estruturados reconhecidos",
            ),
            CountRow(
                "referências verificadas",
                len(references),
                "referências de caminho extraídas dos manifests reconhecidos",
            ),
            CountRow(
                "referências ausentes",
                missing_references,
                "subconjunto das referências verificadas",
            ),
            CountRow(
                "referências ambíguas",
                ambiguous_references,
                "subconjunto das referências verificadas",
            ),
            CountRow(
                "inconsistências",
                len(issues),
                "achados não corrigidos automaticamente",
            ),
            CountRow(
                "grupos de universo",
                len(universes),
                "fonte × camada × classe × tipo de item",
            ),
            CountRow(
                "itens reconciliados",
                reconciled_items,
                "soma de catalogo_universos.csv; deve igualar itens catalogados",
            ),
        ],
        artifacts=artifacts,
        warnings=warnings,
        next_action=(
            "Abra `artifacts/mapa_dados.md`, revise os universos, as "
            "fontes, camadas, unidades e inconsistências. Não copie as saídas ao "
            "Drive nem inicie o snapshot v2 antes do próximo gate."
        ),
    )


def _validate_preflight(
    *,
    data_root: Path,
    output_base: Path,
    operation_root: Path,
    operation_id: str,
    code_commit: str,
    max_structured_bytes: int,
) -> None:
    if not data_root.is_dir():
        raise FileNotFoundError(f"Raiz de dados ausente: {data_root}")
    if data_root == output_base or data_root in output_base.parents:
        raise ValueError("A saída do inventário não pode ficar dentro da raiz lida.")
    if operation_root.exists() and any(operation_root.iterdir()):
        raise FileExistsError(
            f"operation_id já possui artefatos: {operation_root}; use um novo ID."
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", operation_id):
        raise ValueError(f"operation_id inválido: {operation_id}")
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("code_commit deve ser um SHA Git completo de 40 caracteres.")
    if max_structured_bytes <= 0:
        raise ValueError("max_structured_bytes deve ser positivo.")


def _metadata_row(
    path: Path,
    *,
    data_root: Path,
    item_type: str,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    relative_path = path.relative_to(data_root).as_posix()
    parent = path.parent.relative_to(data_root).as_posix()
    parent = "." if parent == "." else parent
    suffix = path.suffix.lower() if item_type == "file" else ""
    item_class, layer, source, origin, confidence, reason = _classify(
        relative_path,
        item_type=item_type,
        suffix=suffix,
    )
    issue = None
    try:
        stat = path.lstat()
        size_bytes: int | str = stat.st_size if item_type == "file" else ""
        modified_at = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat()
    except OSError as exc:
        size_bytes = ""
        modified_at = ""
        issue = _issue(
            "metadata_read_error",
            "warning",
            relative_path,
            "",
            f"{type(exc).__name__}: {exc}",
        )
    content_candidate = (
        item_type == "file"
        and suffix in STRUCTURED_SUFFIXES
        and _is_structured_candidate(relative_path, item_class=item_class)
    )
    return (
        {
            "relative_path": relative_path,
            "parent_relative_path": parent,
            "name": path.name,
            "item_type": item_type,
            "suffix": suffix,
            "mime_type": mimetypes.guess_type(path.name)[0] or "",
            "size_bytes": size_bytes,
            "modified_at": modified_at,
            "item_class": item_class,
            "layer": layer,
            "source": source,
            "classification_origin": origin,
            "confidence": confidence,
            "classification_reason": reason,
            "content_candidate": content_candidate,
            "content_inspected": False,
            "content_issue": "",
        },
        issue,
    )


def _classify(
    relative_path: str,
    *,
    item_type: str,
    suffix: str,
) -> tuple[str, str, str, str, str, str]:
    lower = relative_path.casefold()
    parts = {part for part in Path(lower).parts}
    name = Path(lower).name

    if "raw" in parts:
        layer = "raw"
    elif "processed" in parts:
        layer = "processed"
    elif "snapshot" in lower:
        layer = "snapshot"
    elif {"analise", "analises", "analysis"} & parts:
        layer = "analysis"
    elif {"operations", "logs", "manifests", "checkpoints"} & parts:
        layer = "operational"
    else:
        layer = "unknown"

    found_sources = []
    for source_name, aliases in {
        "camara": {"camara", "câmara"},
        "senado": {"senado"},
        "congresso": {"congresso", "congresso_nacional"},
    }.items():
        if any(
            part == alias or part.startswith(f"{alias}_")
            for part in parts
            for alias in aliases
        ):
            found_sources.append(source_name)
    if len(found_sources) > 1:
        source = "multiple"
    elif found_sources:
        source = found_sources[0]
    elif layer in {"processed", "snapshot", "analysis"}:
        source = "derived"
    else:
        source = "unknown"

    if item_type == "directory":
        if "snapshot" in name:
            item_class = "snapshot"
            reason = "nome do diretório contém snapshot"
        else:
            item_class = "directory"
            reason = "item do sistema de arquivos"
        return item_class, layer, source, "path", "medium", reason

    if item_type == "symlink":
        return "artifact", layer, source, "path", "low", "link simbólico não seguido"
    if "manifest" in name or name.endswith(".autosave.json"):
        return "manifest", layer, source, "path", "high", "nome de manifest"
    if "relatorio" in name or "report" in name or name == "mapa_dados.md":
        return "report", layer, source, "path", "high", "nome de relatório"
    if "review" in name or "revis" in name:
        return "review", layer, source, "path", "high", "nome de revisão"
    if "log" in name or "logs" in parts or suffix == ".log":
        return "log", layer, source, "path", "high", "nome ou diretório de log"
    if "snapshot" in lower:
        return "snapshot", layer, source, "path", "medium", "caminho contém snapshot"
    if suffix in {".csv", ".jsonl", ".parquet", ".xlsx"} and layer in {
        "raw",
        "processed",
        "snapshot",
    }:
        return "dataset", layer, source, "path", "medium", "formato tabular em camada de dados"
    return "artifact", layer, source, "inferred", "low", "arquivo sem convenção específica"


def _is_structured_candidate(relative_path: str, *, item_class: str) -> bool:
    if item_class in {"manifest", "report", "review"}:
        return True
    tokens = {
        token
        for token in re.split(r"[^a-z0-9áàâãéêíóôõúç]+", relative_path.casefold())
        if token
    }
    return bool(tokens & STRUCTURED_KEYWORDS)


def _extract_references(
    payload: Any,
    *,
    manifest_relative_path: str,
    data_root: Path,
    manifest_parent: Path,
    json_path: str = "$",
    parent_key: str = "",
    role_context: str = "",
) -> Iterator[dict[str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{json_path}.{key}"
            normalized_key = str(key).casefold()
            child_role = role_context
            if "output" in normalized_key:
                child_role = "output"
            elif "input" in normalized_key:
                child_role = "input"
            yield from _extract_references(
                value,
                manifest_relative_path=manifest_relative_path,
                data_root=data_root,
                manifest_parent=manifest_parent,
                json_path=child_path,
                parent_key=str(key),
                role_context=child_role,
            )
        return
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from _extract_references(
                value,
                manifest_relative_path=manifest_relative_path,
                data_root=data_root,
                manifest_parent=manifest_parent,
                json_path=f"{json_path}[{index}]",
                parent_key=parent_key,
                role_context=role_context,
            )
        return
    if not isinstance(payload, str) or not _looks_like_reference(parent_key, payload):
        return

    status, resolved = _resolve_reference(
        payload,
        data_root=data_root,
        manifest_parent=manifest_parent,
    )
    role = role_context or (
        "output" if "output" in parent_key.casefold() else "input"
    )
    yield {
        "manifest_relative_path": manifest_relative_path,
        "json_path": json_path,
        "role": role,
        "reference": payload,
        "status": status,
        "resolved_relative_path": resolved,
    }


def _looks_like_reference(key: str, value: str) -> bool:
    if value.startswith(("http://", "https://", "gs://")):
        return False
    normalized_key = re.sub(r"[^a-z0-9]+", "_", key.casefold())
    key_tokens = set(normalized_key.split("_"))
    if not key_tokens & REFERENCE_KEY_TOKENS:
        return False
    candidate = Path(value)
    return "/" in value or "\\" in value or candidate.suffix.casefold() in PATHLIKE_SUFFIXES


def _resolve_reference(
    value: str,
    *,
    data_root: Path,
    manifest_parent: Path,
) -> tuple[str, str]:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        if resolved != data_root and data_root not in resolved.parents:
            return "outside_root", ""
        return (
            ("valid", resolved.relative_to(data_root).as_posix())
            if resolved.exists()
            else ("missing", resolved.relative_to(data_root).as_posix())
        )

    valid_candidates = []
    for base in (manifest_parent, data_root):
        resolved = (base / candidate).resolve()
        if resolved != data_root and data_root not in resolved.parents:
            continue
        if resolved.exists() and resolved not in valid_candidates:
            valid_candidates.append(resolved)
    if len(valid_candidates) > 1:
        return (
            "ambiguous",
            " | ".join(
                path.relative_to(data_root).as_posix()
                for path in valid_candidates
            ),
        )
    if valid_candidates:
        return "valid", valid_candidates[0].relative_to(data_root).as_posix()
    fallback = (manifest_parent / candidate).resolve()
    if fallback == data_root or data_root in fallback.parents:
        return "missing", fallback.relative_to(data_root).as_posix()
    return "outside_root", ""


def _execution_row(
    payload: Mapping[str, Any],
    *,
    manifest_relative_path: str,
    references: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    declared_status = str(
        payload.get("execution_status") or payload.get("status") or ""
    ).strip()
    execution_status, status_origin = _normalize_execution_status(
        declared_status,
        errors=payload.get("errors"),
    )
    scientific_gate = str(payload.get("scientific_gate") or "not_evaluated")
    if scientific_gate not in {
        "not_applicable",
        "not_evaluated",
        "needs_review",
        "approved",
        "rejected",
    }:
        scientific_gate = "not_evaluated"
    operation_id = str(
        payload.get("operation_id")
        or payload.get("run_id")
        or payload.get("recovery_id")
        or payload.get("audit_id")
        or Path(manifest_relative_path).parent.name
    ).strip()
    inputs = sum(reference["role"] == "input" for reference in references)
    outputs = sum(reference["role"] == "output" for reference in references)
    valid = sum(reference["status"] == "valid" for reference in references)
    missing = sum(reference["status"] == "missing" for reference in references)
    ambiguous = sum(
        reference["status"] == "ambiguous" for reference in references
    )
    return {
        "manifest_relative_path": manifest_relative_path,
        "operation_id": operation_id,
        "analysis_run_id": str(payload.get("analysis_run_id") or ""),
        "snapshot_id": str(payload.get("snapshot_id") or ""),
        "module": str(
            payload.get("module")
            or payload.get("strategy")
            or payload.get("dataset")
            or "unknown"
        ),
        "period": _extract_period(payload),
        "declared_status": declared_status,
        "execution_status": execution_status,
        "scientific_gate": scientific_gate,
        "input_references": inputs,
        "output_references": outputs,
        "valid_references": valid,
        "missing_references": missing,
        "ambiguous_references": ambiguous,
        "status_origin": status_origin,
    }


def _normalize_execution_status(
    declared_status: str,
    *,
    errors: Any,
) -> tuple[str, str]:
    normalized = declared_status.casefold().strip()
    if normalized in {"not_started", "running", "succeeded", "failed", "cancelled"}:
        return normalized, "declared_d06"
    if normalized in {"completed", "complete", "success"}:
        if isinstance(errors, int) and errors > 0:
            return "failed", "legacy_mapping_with_errors"
        return "succeeded", "legacy_mapping"
    if normalized in {
        "completed_with_errors",
        "error",
        "interrupted",
        "partial",
    }:
        return "failed", "legacy_mapping"
    if normalized in {"cancelled", "canceled"}:
        return "cancelled", "legacy_mapping"
    return "unknown", "unmapped"


def _extract_period(payload: Mapping[str, Any]) -> str:
    start = (
        payload.get("date_start")
        or payload.get("data_inicio")
        or payload.get("start_date")
        or ""
    )
    end = (
        payload.get("date_end")
        or payload.get("data_fim")
        or payload.get("end_date")
        or ""
    )
    if start or end:
        return f"{start or '?'}..{end or '?'}"
    years = payload.get("years") or payload.get("anos")
    if isinstance(years, list):
        return ",".join(str(year) for year in years)
    return str(payload.get("period") or payload.get("periodo") or "")


def _counter_table(counter: Counter[str], label: str) -> list[str]:
    if not counter:
        return ["Nenhum item."]
    return [
        f"| {label} | Itens |",
        "|---|---:|",
        *[f"| {key} | {value} |" for key, value in sorted(counter.items())],
    ]


def _manifest_counts(
    *,
    catalog: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
    references: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    universes: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "items_cataloged": len(catalog),
        "files": sum(row["item_type"] == "file" for row in catalog),
        "directories": sum(row["item_type"] == "directory" for row in catalog),
        "structured_items_inspected": sum(
            bool(row["content_inspected"]) for row in catalog
        ),
        "apparent_executions": len(executions),
        "references_checked": len(references),
        "references_valid": sum(row["status"] == "valid" for row in references),
        "references_missing": sum(
            row["status"] == "missing" for row in references
        ),
        "references_ambiguous": sum(
            row["status"] == "ambiguous" for row in references
        ),
        "universe_groups": len(universes),
        "universe_items_reconciled": sum(
            int(row["items"]) for row in universes
        ),
        "unknown_layer_items": sum(
            row["layer"] == "unknown" for row in catalog
        ),
        "unknown_source_items": sum(
            row["source"] == "unknown" for row in catalog
        ),
        "inconsistencies": len(issues),
    }


def _artifact_ref(
    path: Path,
    *,
    operation_root: Path,
    role: str,
    rows: int | None,
) -> ArtifactRef:
    return ArtifactRef(
        name=path.stem,
        role=role,
        uri=path.relative_to(operation_root).as_posix(),
        format=path.suffix.lstrip("."),
        size_bytes=path.stat().st_size,
        sha256=_file_sha256(path),
        rows=rows,
    )


def _artifact_role(name: str) -> str:
    return {
        "catalogo_dados.csv": "catálogo completo dos itens observados",
        "catalogo_execucoes.csv": "catálogo das execuções aparentes",
        "referencias.csv": "referências extraídas de manifests",
        "inconsistencias.csv": "achados que exigem revisão",
        "plano_migracao.csv": "propostas não executadas",
        "catalogo_universos.csv": "reconciliação integral dos universos de metadados",
    }[name]


def _write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _issue(
    issue_type: str,
    severity: str,
    item_relative_path: str,
    reference: str,
    detail: str,
) -> dict[str, str]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "item_relative_path": item_relative_path,
        "reference": reference,
        "detail": detail,
    }


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
