from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from pipeline_dados_v3.inventario_metadados_raw import (
    DEFAULT_MAX_JSON_BYTES,
    canonical_json_value,
    declared_record_type,
    escape_path_key,
    flatten_fields,
    is_relative_to,
    mounted_drive_root,
    structural_fingerprint,
    technical_type,
    value_state,
)


APPROVED_INVENTORY_OPERATION_ID = "raw-metadata-full-20260724t184418z"
DEFAULT_RAW_ROOT = Path("/content/drive/MyDrive/falando_nela/data/raw")
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_v3_schema")
SCHEMA_VERSION = "normalized-schema-evidence-v3.1"
SPEC_REF = "specs/pipeline_dados_v3/02_schema_normalizado/requirements.md"
PROMPT_VERSION = "schema-proposal-gpt56-v1"
PROPOSAL_SCHEMA_VERSION = "schema-proposal-response-v1"
REQUESTED_MODEL = "gpt-5.6"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_METADATA_VALUE_LIMIT = 200
DEFAULT_PREVIEW_LIMIT = 500

APPROVED_COUNTS = {
    "records_observed": 1_148_754,
    "records_read": 1_148_740,
    "records_rejected": 14,
    "record_groups": 50,
    "field_paths": 23_786,
}
APPROVED_TYPE_CONFLICTS = {
    ("senado", "ccj_notas"): 540,
    ("senado", "parlamentares"): 1,
    ("senado", "plenario_discursos"): 2,
}
APPROVED_CCJ_PATHS = 20_523

INVENTORY_ARTIFACTS = {
    "inventario_arquivos.csv",
    "inventario_campos.csv",
    "valores_observados.csv",
    "amostras_campos.jsonl",
    "inconsistencias.csv",
    "relatorio.md",
}

FIELD_BOOK_FIELDS = [
    "source",
    "dataset",
    "record_type",
    "field_path",
    "technical_types",
    "records_universe",
    "field_absent",
    "present_null",
    "present_empty",
    "present_filled",
    "fill_rate",
    "cardinality",
    "cardinality_method",
    "string_length_min",
    "string_length_median",
    "string_length_max",
    "first_partition",
    "last_partition",
    "type_conflict",
    "semantic_role",
    "decision",
    "proposed_category",
    "proposed_logical_type",
    "rule_id",
    "decision_rationale",
    "decision_by",
    "decision_at",
]

ALIAS_FIELDS = [
    "candidate_id",
    "source",
    "dataset",
    "record_type",
    "field_a",
    "field_b",
    "comparison_scope",
    "candidate_signal",
    "comparator",
    "rule_id",
    "records_universe",
    "u",
    "ab",
    "equal",
    "different",
    "only_a",
    "only_b",
    "coincidence_rate",
    "overlap_rate",
    "only_a_rate",
    "only_b_rate",
    "a_absent",
    "a_null",
    "a_empty",
    "b_absent",
    "b_null",
    "b_empty",
    "agree_coordinates",
    "differ_coordinates",
    "link_matched",
    "link_unmatched_a",
    "link_unmatched_b",
    "link_ambiguous",
    "evidence_status",
    "human_decision",
    "human_rationale",
]

MAPPING_FIELDS = [
    "pair_id",
    "packet_id",
    "proposal_id",
    "condition",
    "canonical_field",
    "logical_type",
    "operation",
    "source",
    "dataset",
    "record_type",
    "source_paths_json",
    "evidence_ids_json",
    "context_refs_json",
    "api_category_refs_json",
    "possible_aliases_json",
    "caveats_json",
    "needs_human_review",
    "human_decision",
    "human_rationale",
]

EXECUTION_FIELDS = [
    "pair_id",
    "packet_id",
    "condition",
    "requested_model",
    "resolved_model",
    "reasoning_effort",
    "prompt_version",
    "prompt_sha256",
    "schema_version",
    "schema_sha256",
    "input_sha256",
    "response_sha256",
    "status",
    "refusal",
    "error",
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "latency_seconds",
    "cost_usd",
    "pricing_ref",
]

AB_FIELDS = [
    "pair_id",
    "packet_id",
    "condition",
    "reviewed_proposals",
    "accepted_proposals",
    "unsupported_categories",
    "incorrect_aliases",
    "insufficient_evidence",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "latency_seconds",
    "cost_usd",
    "human_preview_decision",
]


@dataclass(frozen=True)
class SchemaConfig:
    raw_root: Path
    inventory_root: Path
    output_base: Path
    operation_id: str
    code_commit: str
    expected_inventory_operation_id: str = APPROVED_INVENTORY_OPERATION_ID
    expected_inventory_manifest_sha256: str | None = None
    enforce_approved_counts: bool = True
    metadata_value_limit: int = DEFAULT_METADATA_VALUE_LIMIT
    preview_limit: int = DEFAULT_PREVIEW_LIMIT
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES
    max_alias_candidates_per_group: int | None = None
    field_review_path: Path | None = None
    manual_alias_path: Path | None = None
    api_categories_path: Path | None = None
    progress_every_files: int = 100

    @property
    def operation_root(self) -> Path:
        return self.output_base / self.operation_id


@dataclass(frozen=True)
class RawRecord:
    source: str
    dataset: str
    record_type: str
    relative_path: str
    record_number: int
    technical_kind: str
    value: Any

    @property
    def coordinate(self) -> str:
        return f"{self.relative_path}#{self.record_number}"


@dataclass(frozen=True)
class AliasCandidate:
    source: str
    dataset: str
    record_type: str
    field_a: str
    field_b: str
    comparison_scope: str = "same_record"
    candidate_signal: str = "same_terminal_key"

    @property
    def candidate_id(self) -> str:
        payload = "\0".join(
            [
                self.source,
                self.dataset,
                self.record_type,
                self.field_a,
                self.field_b,
                self.comparison_scope,
            ]
        )
        return "alias_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class LinkRule:
    rule_id: str
    link_path_a: str
    link_path_b: str
    value_path_a: str
    value_path_b: str
    link_field_role_a: str
    link_field_role_b: str
    approved_by: str

    def validate(self) -> None:
        if not self.rule_id.strip() or not self.approved_by.strip():
            raise ValueError("Vínculo entre registros exige regra e aprovação.")
        if (
            self.link_field_role_a != "metadata"
            or self.link_field_role_b != "metadata"
        ):
            raise ValueError(
                "Vínculo entre registros só pode usar metadados aprovados."
            )
        for name in (
            "link_path_a",
            "link_path_b",
            "value_path_a",
            "value_path_b",
        ):
            if not getattr(self, name).startswith("$"):
                raise ValueError(f"Caminho inválido na regra de vínculo: {name}")


@dataclass
class AliasMetrics:
    records_universe: int = 0
    u: int = 0
    ab: int = 0
    equal: int = 0
    different: int = 0
    only_a: int = 0
    only_b: int = 0
    a_absent: int = 0
    a_null: int = 0
    a_empty: int = 0
    b_absent: int = 0
    b_null: int = 0
    b_empty: int = 0
    agree_coordinates: list[str] = field(default_factory=list)
    differ_coordinates: list[str] = field(default_factory=list)
    link_matched: int | str = ""
    link_unmatched_a: int | str = ""
    link_unmatched_b: int | str = ""
    link_ambiguous: int | str = ""
    evidence_status: str = "measured"

    def observe(
        self,
        values_a: Sequence[Any] | None,
        values_b: Sequence[Any] | None,
        coordinate: str,
    ) -> None:
        self.records_universe += 1
        state_a = occurrence_state(values_a)
        state_b = occurrence_state(values_b)
        if state_a == "absent":
            self.a_absent += 1
        elif state_a == "null":
            self.a_null += 1
        elif state_a == "empty":
            self.a_empty += 1
        if state_b == "absent":
            self.b_absent += 1
        elif state_b == "null":
            self.b_null += 1
        elif state_b == "empty":
            self.b_empty += 1

        filled_a = state_a == "filled"
        filled_b = state_b == "filled"
        if not (filled_a or filled_b):
            return
        self.u += 1
        if filled_a and filled_b:
            self.ab += 1
            if typed_occurrence_token(values_a or []) == typed_occurrence_token(
                values_b or []
            ):
                self.equal += 1
                append_coordinate(self.agree_coordinates, coordinate)
            else:
                self.different += 1
                append_coordinate(self.differ_coordinates, coordinate)
        elif filled_a:
            self.only_a += 1
        else:
            self.only_b += 1

    def validate(self) -> None:
        if self.u != self.ab + self.only_a + self.only_b:
            raise AssertionError("U não reconcilia com AB + SA + SB.")
        if self.ab != self.equal + self.different:
            raise AssertionError("AB não reconcilia com E + D.")

    def finalize_universe(self, records_universe: int) -> None:
        if records_universe < self.records_universe:
            raise AssertionError("Universo final menor que registros auditados.")
        unseen = records_universe - self.records_universe
        self.a_absent += unseen
        self.b_absent += unseen
        self.records_universe = records_universe

    def rates(self) -> dict[str, str]:
        self.validate()
        return {
            "coincidence_rate": rate(self.equal, self.ab),
            "overlap_rate": rate(self.ab, self.u),
            "only_a_rate": rate(self.only_a, self.u),
            "only_b_rate": rate(self.only_b, self.u),
        }


@dataclass
class SampleCandidate:
    score: tuple[Any, ...]
    coordinate: str
    record: RawRecord
    sanitized: Any
    structure_hash: str
    filled_paths: int
    max_depth: int
    conflict_paths: int


class StructuralSampleSelector:
    def __init__(
        self,
        field_stats: Mapping[tuple[str, str, str, str], Mapping[str, str]],
        field_roles: Mapping[tuple[str, str, str, str], str],
        *,
        metadata_value_limit: int,
    ) -> None:
        self.field_stats = field_stats
        self.field_roles = field_roles
        self.metadata_value_limit = metadata_value_limit
        self._candidates: dict[
            tuple[str, str, str], dict[str, list[SampleCandidate]]
        ] = defaultdict(lambda: defaultdict(list))

    def observe(self, raw_record: RawRecord) -> None:
        group = (raw_record.source, raw_record.dataset, raw_record.record_type)
        occurrences = occurrences_by_path(raw_record.value)
        filled = {
            path
            for path, values in occurrences.items()
            if occurrence_state(values) == "filled"
        }
        fill_rates = [
            Decimal(
                self.field_stats.get((*group, path), {}).get("fill_rate", "0") or "0"
            )
            for path in filled
        ]
        rarity = sum((Decimal("1") - value for value in fill_rates), Decimal("0"))
        conflict_paths = sum(
            truthy(self.field_stats.get((*group, path), {}).get("type_conflict", ""))
            for path in filled
        )
        depth = max((path_depth(path) for path in occurrences), default=0)
        sanitized = sanitize_record(
            raw_record.value,
            group=group,
            field_roles=self.field_roles,
            metadata_value_limit=self.metadata_value_limit,
        )
        structure_hash = sha256_json(structure_signature(raw_record.value))
        common = {
            "coordinate": raw_record.coordinate,
            "record": raw_record,
            "sanitized": sanitized,
            "structure_hash": structure_hash,
            "filled_paths": len(filled),
            "max_depth": depth,
            "conflict_paths": conflict_paths,
        }
        role_scores = {
            "typical": (
                sum(fill_rates, Decimal("0")),
                len(filled),
                -depth,
            ),
            "sparse": (-len(filled), -depth),
            "rare_or_conflict": (conflict_paths, rarity, depth, len(filled)),
        }
        for role, score in role_scores.items():
            candidate = SampleCandidate(score=score, **common)
            bucket = self._candidates[group][role]
            bucket.append(candidate)
            bucket.sort(key=lambda item: (item.score, item.coordinate), reverse=True)
            del bucket[8:]

    def rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for group in sorted(self._candidates):
            used: set[str] = set()
            for role in ("typical", "sparse", "rare_or_conflict"):
                selected = next(
                    (
                        candidate
                        for candidate in self._candidates[group][role]
                        if candidate.coordinate not in used
                    ),
                    None,
                )
                if selected is None:
                    continue
                used.add(selected.coordinate)
                raw_record = selected.record
                evidence_id = stable_id(
                    "evidence",
                    *group,
                    role,
                    raw_record.coordinate,
                    selected.structure_hash,
                )
                rows.append(
                    {
                        "evidence_id": evidence_id,
                        "channel": "evidence",
                        "source": raw_record.source,
                        "dataset": raw_record.dataset,
                        "record_type": raw_record.record_type,
                        "relative_path": raw_record.relative_path,
                        "record_number": raw_record.record_number,
                        "selection_role": role,
                        "selection_reason": {
                            "filled_paths": selected.filled_paths,
                            "max_depth": selected.max_depth,
                            "conflict_paths": selected.conflict_paths,
                            "criterion": "deterministic_structural_score",
                        },
                        "structure_hash": selected.structure_hash,
                        "record": selected.sanitized,
                    }
                )
        return rows


class PreviewSelector:
    def __init__(
        self,
        field_rows: Mapping[tuple[str, str, str, str], Mapping[str, str]],
        field_roles: Mapping[tuple[str, str, str, str], str],
        *,
        preview_limit: int,
    ) -> None:
        self.field_rows = field_rows
        self.field_roles = field_roles
        self.preview_limit = preview_limit
        self._best: dict[tuple[str, str, str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def observe(self, raw_record: RawRecord) -> None:
        group = (raw_record.source, raw_record.dataset, raw_record.record_type)
        for path, values in occurrences_by_path(raw_record.value).items():
            key = (*group, path)
            if self.field_roles.get(key) != "text":
                continue
            median = decimal_or_zero(self.field_rows.get(key, {}).get("string_length_median"))
            for occurrence_index, value in enumerate(values):
                if not isinstance(value, str) or value_state(value) != "filled":
                    continue
                digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                score = (abs(Decimal(len(value)) - median), digest)
                context_id = stable_id(
                    "context",
                    *group,
                    path,
                    raw_record.coordinate,
                    str(occurrence_index),
                    digest,
                )
                preview = value[: self.preview_limit]
                row = {
                    "context_id": context_id,
                    "channel": "context_only",
                    "context_only": True,
                    "approved_for_gpt": False,
                    "approval_by": "",
                    "approval_at": "",
                    "approval_rationale": "",
                    "source": raw_record.source,
                    "dataset": raw_record.dataset,
                    "record_type": raw_record.record_type,
                    "field_path": path,
                    "relative_path": raw_record.relative_path,
                    "record_number": raw_record.record_number,
                    "occurrence_index": occurrence_index,
                    "start": 0,
                    "end": len(preview),
                    "full_length": len(value),
                    "full_sha256": digest,
                    "selection_criterion": "closest_to_inventory_median_then_sha256",
                    "preview": preview,
                }
                current = self._best.get(key)
                if current is None or score < current[0]:
                    self._best[key] = (score, row)

    def rows(self) -> list[dict[str, Any]]:
        return [self._best[key][1] for key in sorted(self._best)]


def validate_inventory(
    config: SchemaConfig,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    manifest_path = config.inventory_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Manifest G01 ausente: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_hash = sha256_file(manifest_path)
    if config.enforce_approved_counts:
        expected_manifest_hash = config.expected_inventory_manifest_sha256
        if (
            expected_manifest_hash is None
            or len(expected_manifest_hash) != 64
            or any(char not in "0123456789abcdef" for char in expected_manifest_hash)
        ):
            raise ValueError(
                "A execução integral exige o SHA-256 aprovado do manifest G01."
            )
        if manifest_hash != expected_manifest_hash:
            raise ValueError("Hash aprovado do manifest G01 não confere.")
    if manifest.get("operation_id") != config.expected_inventory_operation_id:
        raise ValueError(
            "operation_id G01 divergente: "
            f"{manifest.get('operation_id')!r} != "
            f"{config.expected_inventory_operation_id!r}"
        )
    if manifest.get("execution_status") != "succeeded":
        raise ValueError("O inventário G01 não terminou com succeeded.")
    if manifest.get("scope_mode") != "full":
        raise ValueError("G02 exige inventário integral, não smoke.")

    output_refs = manifest.get("outputs")
    if not isinstance(output_refs, list):
        raise ValueError("Manifest G01 sem lista outputs.")
    refs_by_name = {str(item.get("name")): item for item in output_refs}
    if set(refs_by_name) != INVENTORY_ARTIFACTS:
        raise ValueError(
            "Artefatos G01 divergentes: "
            f"esperados={sorted(INVENTORY_ARTIFACTS)}; "
            f"observados={sorted(refs_by_name)}"
        )
    for name in sorted(INVENTORY_ARTIFACTS):
        path = config.inventory_root / name
        if not path.is_file():
            raise ValueError(f"Artefato G01 ausente: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != refs_by_name[name].get("sha256"):
            raise ValueError(f"Hash G01 divergente para {name}.")

    fields = read_csv(config.inventory_root / "inventario_campos.csv")
    issues = read_csv(config.inventory_root / "inconsistencias.csv")
    if config.enforce_approved_counts:
        counts = manifest.get("counts", {})
        for name, expected in APPROVED_COUNTS.items():
            if int(counts.get(name, -1)) != expected:
                raise ValueError(
                    f"Contagem G01 divergente para {name}: "
                    f"{counts.get(name)!r} != {expected}"
                )
        conflicts = Counter(
            (row["source"], row["dataset"])
            for row in fields
            if truthy(row["type_conflict"])
        )
        if sum(conflicts.values()) != 543:
            raise ValueError("O inventário não possui exatamente 543 conflitos.")
        for group, expected in APPROVED_TYPE_CONFLICTS.items():
            if conflicts[group] != expected:
                raise ValueError(
                    f"Conflitos divergentes em {'/'.join(group)}: "
                    f"{conflicts[group]} != {expected}"
                )
        ccj_paths = sum(
            row["source"] == "senado" and row["dataset"] == "ccj_notas"
            for row in fields
        )
        if ccj_paths != APPROVED_CCJ_PATHS:
            raise ValueError(
                f"senado/ccj_notas possui {ccj_paths}, não {APPROVED_CCJ_PATHS} caminhos."
            )
        rejected = int(counts["records_rejected"])
        if int(counts["records_observed"]) != int(counts["records_read"]) + rejected:
            raise ValueError("Registros observados não reconciliam lidos + rejeitados.")
    return manifest, fields, issues


def validated_config(config: SchemaConfig) -> SchemaConfig:
    raw_root = config.raw_root.expanduser().resolve()
    inventory_root = config.inventory_root.expanduser().resolve()
    output_base = config.output_base.expanduser().resolve()
    normalized = SchemaConfig(
        raw_root=raw_root,
        inventory_root=inventory_root,
        output_base=output_base,
        operation_id=config.operation_id,
        code_commit=config.code_commit,
        expected_inventory_operation_id=config.expected_inventory_operation_id,
        expected_inventory_manifest_sha256=(
            config.expected_inventory_manifest_sha256
        ),
        enforce_approved_counts=config.enforce_approved_counts,
        metadata_value_limit=config.metadata_value_limit,
        preview_limit=config.preview_limit,
        max_json_bytes=config.max_json_bytes,
        max_alias_candidates_per_group=config.max_alias_candidates_per_group,
        field_review_path=resolve_optional(config.field_review_path),
        manual_alias_path=resolve_optional(config.manual_alias_path),
        api_categories_path=resolve_optional(config.api_categories_path),
        progress_every_files=config.progress_every_files,
    )
    if not raw_root.is_dir() or raw_root.name != "raw":
        raise ValueError(f"Raiz raw inválida: {raw_root}")
    if not inventory_root.is_dir():
        raise ValueError(f"Diretório G01 inválido: {inventory_root}")
    if not config.operation_id or "/" in config.operation_id:
        raise ValueError("operation_id de G02 é obrigatório e não pode conter '/'.")
    if not config.code_commit.strip():
        raise ValueError("code_commit é obrigatório.")
    if normalized.metadata_value_limit < 1:
        raise ValueError("metadata_value_limit deve ser positivo.")
    if not 1 <= normalized.preview_limit <= DEFAULT_PREVIEW_LIMIT:
        raise ValueError("preview_limit deve estar entre 1 e 500.")
    if normalized.max_alias_candidates_per_group is not None:
        if normalized.max_alias_candidates_per_group < 1:
            raise ValueError("max_alias_candidates_per_group deve ser positivo.")
        if normalized.enforce_approved_counts:
            raise ValueError(
                "Limite de candidatos não é permitido na execução integral aprovada."
            )
    operation_root = normalized.operation_root
    if is_relative_to(operation_root, raw_root):
        raise ValueError("A saída não pode ficar dentro do raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(operation_root, drive_root):
        raise ValueError("A saída temporária não pode ficar dentro do Drive.")
    if operation_root.exists():
        raise FileExistsError(
            f"A saída já existe e não será sobrescrita: {operation_root}"
        )
    return normalized


def prepare_schema_evidence(config: SchemaConfig) -> dict[str, Any]:
    config = validated_config(config)
    started_at = utc_now()
    manifest_g01, field_rows, issues = validate_inventory(config)
    value_rows = read_csv(config.inventory_root / "valores_observados.csv")
    inventory_sample_rows = read_jsonl(
        config.inventory_root / "amostras_campos.jsonl"
    )
    fingerprint_before = structural_fingerprint(config.raw_root)
    approved_fingerprint = (
        manifest_g01.get("input", {}).get("structural_fingerprint")
    )
    if approved_fingerprint and fingerprint_before != approved_fingerprint:
        raise RuntimeError("O fingerprint atual do raw diverge do inventário G01.")

    field_by_key = {
        field_key(row): row
        for row in field_rows
    }
    roles, review_rows = build_field_book(
        field_rows,
        review_path=config.field_review_path,
    )
    candidates = generate_alias_candidates(
        field_rows,
        field_roles=roles,
        manual_alias_path=config.manual_alias_path,
        max_per_group=config.max_alias_candidates_per_group,
    )
    candidates_by_group: defaultdict[
        tuple[str, str, str], list[AliasCandidate]
    ] = defaultdict(list)
    candidate_ids_by_path: defaultdict[
        tuple[str, str, str, str], set[str]
    ] = defaultdict(set)
    candidate_by_id = {
        candidate.candidate_id: candidate for candidate in candidates
    }
    metrics = {candidate.candidate_id: AliasMetrics() for candidate in candidates}
    for candidate in candidates:
        candidate_group = (
            candidate.source,
            candidate.dataset,
            candidate.record_type,
        )
        candidates_by_group[candidate_group].append(candidate)
        candidate_ids_by_path[(*candidate_group, candidate.field_a)].add(
            candidate.candidate_id
        )
        candidate_ids_by_path[(*candidate_group, candidate.field_b)].add(
            candidate.candidate_id
        )

    sample_selector = StructuralSampleSelector(
        field_by_key,
        roles,
        metadata_value_limit=config.metadata_value_limit,
    )
    preview_selector = PreviewSelector(
        field_by_key,
        roles,
        preview_limit=config.preview_limit,
    )
    files = selected_inventory_files(config.inventory_root)
    records_seen = 0
    for file_index, file_row in enumerate(files, start=1):
        for raw_record in iter_raw_file(
            config.raw_root,
            file_row,
            max_json_bytes=config.max_json_bytes,
        ):
            records_seen += 1
            sample_selector.observe(raw_record)
            preview_selector.observe(raw_record)
            group = (
                raw_record.source,
                raw_record.dataset,
                raw_record.record_type,
            )
            group_candidates = candidates_by_group.get(group)
            if group_candidates:
                occurrences = occurrences_by_path(raw_record.value)
                relevant_ids: set[str] = set()
                for path in occurrences:
                    relevant_ids.update(candidate_ids_by_path.get((*group, path), ()))
                for candidate_id in sorted(relevant_ids):
                    candidate = candidate_by_id[candidate_id]
                    metrics[candidate.candidate_id].observe(
                        occurrences.get(candidate.field_a),
                        occurrences.get(candidate.field_b),
                        raw_record.coordinate,
                    )
        if config.progress_every_files > 0 and (
            file_index == 1
            or file_index == len(files)
            or file_index % config.progress_every_files == 0
        ):
            print(
                f"[schema-v3] arquivos lidos: {file_index}/{len(files)}",
                flush=True,
            )
    expected_records = int(manifest_g01["counts"]["records_read"])
    if records_seen != expected_records:
        raise RuntimeError(
            f"Leitura G02 observou {records_seen} registros; G01 registra "
            f"{expected_records}."
        )
    fingerprint_after = structural_fingerprint(config.raw_root)
    if fingerprint_after != fingerprint_before:
        raise RuntimeError("A árvore raw mudou durante a auditoria G02.")

    group_universe = {
        (row["source"], row["dataset"], row["record_type"]): int(
            row["records_universe"]
        )
        for row in field_rows
    }
    for candidate in candidates:
        metrics[candidate.candidate_id].finalize_universe(
            group_universe[
                (candidate.source, candidate.dataset, candidate.record_type)
            ]
        )

    sample_rows = sample_selector.rows()
    preview_rows = preview_selector.rows()
    alias_rows = build_alias_rows(candidates, metrics)
    conflict_rows = build_conflict_rows(field_rows, inventory_sample_rows)
    rejected_rows = build_rejected_rows(issues, config.raw_root)
    ccj_report = render_ccj_report(field_rows, conflict_rows)
    api_categories = load_api_categories(config.api_categories_path)
    packets = build_gpt_packets(
        field_rows=field_rows,
        value_rows=value_rows,
        field_roles=roles,
        sample_rows=sample_rows,
        alias_rows=alias_rows,
        api_categories=api_categories,
    )
    operation_root = config.operation_root
    operation_root.mkdir(parents=True)
    paths = write_preparation_outputs(
        operation_root=operation_root,
        field_book_rows=review_rows,
        alias_rows=alias_rows,
        sample_rows=sample_rows,
        preview_rows=preview_rows,
        conflict_rows=conflict_rows,
        rejected_rows=rejected_rows,
        ccj_report=ccj_report,
        packets=packets,
    )
    manifest = build_manifest(
        config=config,
        manifest_g01=manifest_g01,
        fingerprint=fingerprint_before,
        started_at=started_at,
        records_seen=records_seen,
        paths=paths,
        counts={
            "field_book_rows": len(review_rows),
            "alias_candidates": len(alias_rows),
            "structural_samples": len(sample_rows),
            "context_previews": len(preview_rows),
            "type_conflicts": len(conflict_rows),
            "rejected_lines": len(rejected_rows),
            "gpt_packets": len(packets),
        },
    )
    write_json(operation_root / "manifest.json", manifest)
    return {
        "manifest": manifest,
        "paths": {**paths, "manifest": operation_root / "manifest.json"},
        "field_book_rows": review_rows,
        "alias_rows": alias_rows,
        "sample_rows": sample_rows,
        "preview_rows": preview_rows,
        "packets": packets,
    }


def initialize_field_review(
    config: SchemaConfig,
    output_path: Path,
) -> Path:
    normalized_output = output_path.expanduser().resolve()
    if normalized_output.exists():
        raise FileExistsError(
            f"A revisão já existe e não será sobrescrita: {normalized_output}"
        )
    raw_root = config.raw_root.expanduser().resolve()
    if is_relative_to(normalized_output, raw_root):
        raise ValueError("A revisão de campos não pode ser escrita dentro do raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(normalized_output, drive_root):
        raise ValueError("A revisão temporária não pode ser escrita no Drive.")
    _manifest, field_rows, _issues = validate_inventory(config)
    _roles, review_rows = build_field_book(field_rows, review_path=None)
    normalized_output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(normalized_output, review_rows, FIELD_BOOK_FIELDS)
    return normalized_output


def build_field_book(
    field_rows: Sequence[Mapping[str, str]],
    *,
    review_path: Path | None,
) -> tuple[
    dict[tuple[str, str, str, str], str],
    list[dict[str, Any]],
]:
    existing: dict[tuple[str, str, str, str], Mapping[str, str]] = {}
    if review_path is not None:
        for row in read_csv(review_path):
            key = field_key(row)
            if key in existing:
                raise ValueError(f"Chave duplicada na revisão de campos: {key}")
            existing[key] = row
    inventory_keys = {field_key(row) for row in field_rows}
    invented = set(existing).difference(inventory_keys)
    if invented:
        raise ValueError(
            f"A revisão de campos inventou {len(invented)} caminhos; exemplo: "
            f"{sorted(invented)[0]}"
        )

    allowed_roles = {"unknown", "metadata", "text", "technical_control"}
    allowed_decisions = {
        "nao_avaliado",
        "candidato",
        "mapeado",
        "preservado_sem_normalizacao",
        "adiado_para_estrutura_textual",
        "conflito_aberto",
        "fora_do_schema_proposto",
    }
    roles: dict[tuple[str, str, str, str], str] = {}
    result: list[dict[str, Any]] = []
    for row in sorted(field_rows, key=field_sort_key):
        key = field_key(row)
        decision_row = existing.get(key, {})
        role = str(decision_row.get("semantic_role") or "unknown")
        decision = str(decision_row.get("decision") or "nao_avaliado")
        if role not in allowed_roles:
            raise ValueError(f"semantic_role inválido para {key}: {role}")
        if decision not in allowed_decisions:
            raise ValueError(f"decision inválida para {key}: {decision}")
        rationale = str(decision_row.get("decision_rationale") or "")
        if decision == "fora_do_schema_proposto" and not rationale.strip():
            raise ValueError(
                f"fora_do_schema_proposto exige justificativa humana: {key}"
            )
        roles[key] = role
        result.append(
            {
                **{name: row.get(name, "") for name in FIELD_BOOK_FIELDS},
                "semantic_role": role,
                "decision": decision,
                "proposed_category": decision_row.get("proposed_category", ""),
                "proposed_logical_type": decision_row.get(
                    "proposed_logical_type", ""
                ),
                "rule_id": decision_row.get("rule_id", ""),
                "decision_rationale": rationale,
                "decision_by": decision_row.get("decision_by", ""),
                "decision_at": decision_row.get("decision_at", ""),
            }
        )
    if len(result) != len(inventory_keys):
        raise AssertionError("O livro de campos não cobre exatamente o inventário.")
    return roles, result


def generate_alias_candidates(
    field_rows: Sequence[Mapping[str, str]],
    *,
    field_roles: Mapping[tuple[str, str, str, str], str],
    manual_alias_path: Path | None,
    max_per_group: int | None,
) -> list[AliasCandidate]:
    known_keys = {field_key(row) for row in field_rows}
    groups: defaultdict[
        tuple[str, str, str, str, str], list[str]
    ] = defaultdict(list)
    for row in field_rows:
        if field_roles.get(field_key(row)) != "metadata":
            continue
        path = row["field_path"]
        if path == "$":
            continue
        terminal = terminal_key(path)
        non_null_types = "|".join(
            value
            for value in str(row["technical_types"]).split("|")
            if value and value != "null"
        )
        groups[
            (
                row["source"],
                row["dataset"],
                row["record_type"],
                terminal,
                non_null_types,
            )
        ].append(path)

    candidates: dict[str, AliasCandidate] = {}
    per_record_group: Counter[tuple[str, str, str]] = Counter()
    for key in sorted(groups):
        source, dataset, record_type, _terminal, _types = key
        paths = sorted(set(groups[key]))
        for field_a, field_b in itertools.combinations(paths, 2):
            group = (source, dataset, record_type)
            if max_per_group is not None and per_record_group[group] >= max_per_group:
                break
            candidate = AliasCandidate(
                source=source,
                dataset=dataset,
                record_type=record_type,
                field_a=field_a,
                field_b=field_b,
            )
            candidates[candidate.candidate_id] = candidate
            per_record_group[group] += 1

    if manual_alias_path is not None:
        for row in read_csv(manual_alias_path):
            scope = row.get("comparison_scope") or "same_record"
            if scope not in {"same_record", "linked_records"}:
                raise ValueError(f"comparison_scope inválido: {scope}")
            field_a, field_b = sorted([row["field_a"], row["field_b"]])
            for path in (field_a, field_b):
                key = (
                    row["source"],
                    row["dataset"],
                    row["record_type"],
                    path,
                )
                if key not in known_keys:
                    raise ValueError(f"Par manual cita caminho inexistente: {key}")
                if field_roles.get(key) != "metadata":
                    raise ValueError(
                        f"Par manual exige campo classificado como metadata: {key}"
                    )
            candidate = AliasCandidate(
                source=row["source"],
                dataset=row["dataset"],
                record_type=row["record_type"],
                field_a=field_a,
                field_b=field_b,
                comparison_scope=scope,
                candidate_signal=row.get("candidate_signal") or "human_declared",
            )
            candidates[candidate.candidate_id] = candidate
    return [candidates[key] for key in sorted(candidates)]


def build_alias_rows(
    candidates: Sequence[AliasCandidate],
    metrics: Mapping[str, AliasMetrics],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        metric = metrics[candidate.candidate_id]
        if candidate.comparison_scope != "same_record":
            metric.evidence_status = "insufficient_without_approved_link"
        metric.validate()
        rates = metric.rates()
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "source": candidate.source,
                "dataset": candidate.dataset,
                "record_type": candidate.record_type,
                "field_a": candidate.field_a,
                "field_b": candidate.field_b,
                "comparison_scope": candidate.comparison_scope,
                "candidate_signal": candidate.candidate_signal,
                "comparator": "typed_exact_json_occurrence_sequence_v1",
                "rule_id": "",
                "records_universe": metric.records_universe,
                "u": metric.u,
                "ab": metric.ab,
                "equal": metric.equal,
                "different": metric.different,
                "only_a": metric.only_a,
                "only_b": metric.only_b,
                **rates,
                "a_absent": metric.a_absent,
                "a_null": metric.a_null,
                "a_empty": metric.a_empty,
                "b_absent": metric.b_absent,
                "b_null": metric.b_null,
                "b_empty": metric.b_empty,
                "agree_coordinates": json_compact(metric.agree_coordinates),
                "differ_coordinates": json_compact(metric.differ_coordinates),
                "link_matched": metric.link_matched,
                "link_unmatched_a": metric.link_unmatched_a,
                "link_unmatched_b": metric.link_unmatched_b,
                "link_ambiguous": metric.link_ambiguous,
                "evidence_status": metric.evidence_status,
                "human_decision": "nao_avaliado",
                "human_rationale": "",
            }
        )
    return rows


def audit_linked_records(
    records_a: Sequence[RawRecord],
    records_b: Sequence[RawRecord],
    *,
    rule: LinkRule,
) -> AliasMetrics:
    rule.validate()
    index_a, ambiguous_a, _unkeyed_a = build_unique_link_index(
        records_a, rule.link_path_a
    )
    index_b, ambiguous_b, _unkeyed_b = build_unique_link_index(
        records_b, rule.link_path_b
    )
    ambiguous_keys = ambiguous_a | ambiguous_b
    common = sorted(set(index_a) & set(index_b) - ambiguous_keys)
    metrics = AliasMetrics()
    for token in common:
        record_a = index_a[token]
        record_b = index_b[token]
        metrics.observe(
            occurrences_by_path(record_a.value).get(rule.value_path_a),
            occurrences_by_path(record_b.value).get(rule.value_path_b),
            f"{record_a.coordinate}<->{record_b.coordinate}",
        )
    metrics.link_matched = len(common)
    metrics.link_ambiguous = len(ambiguous_keys)
    metrics.link_unmatched_a = len(records_a) - len(common)
    metrics.link_unmatched_b = len(records_b) - len(common)
    metrics.evidence_status = (
        "measured_with_approved_one_to_one_link"
        if not ambiguous_keys
        else "measured_with_ambiguous_keys_excluded"
    )
    metrics.validate()
    return metrics


def build_unique_link_index(
    records: Sequence[RawRecord],
    link_path: str,
) -> tuple[dict[str, RawRecord], set[str], int]:
    buckets: defaultdict[str, list[RawRecord]] = defaultdict(list)
    unkeyed = 0
    for record in records:
        values = occurrences_by_path(record.value).get(link_path)
        if occurrence_state(values) != "filled":
            unkeyed += 1
            continue
        buckets[typed_occurrence_token(values or [])].append(record)
    ambiguous = {key for key, values in buckets.items() if len(values) != 1}
    unique = {
        key: values[0]
        for key, values in buckets.items()
        if key not in ambiguous
    }
    return unique, ambiguous, unkeyed


def selected_inventory_files(inventory_root: Path) -> list[dict[str, str]]:
    rows = read_csv(inventory_root / "inventario_arquivos.csv")
    selected = [
        row
        for row in rows
        if row.get("item_type") == "file"
        and truthy(row.get("selected_for_read", ""))
        and row.get("read_status") in {"read", "read_with_rejections"}
    ]
    return sorted(selected, key=lambda row: row["relative_path"])


def iter_raw_file(
    raw_root: Path,
    file_row: Mapping[str, str],
    *,
    max_json_bytes: int,
) -> Iterator[RawRecord]:
    relative_path = file_row["relative_path"]
    path = raw_root / relative_path
    suffix = path.suffix.lower()
    source = file_row["source"]
    dataset = file_row["dataset"]
    if suffix in {".jsonl", ".ndjson"}:
        technical_kind = "jsonl_record"
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    line_number,
                    technical_kind,
                    value,
                )
        return
    if suffix == ".json":
        if path.stat().st_size > max_json_bytes:
            raise RuntimeError(f"JSON excede max_json_bytes em G02: {relative_path}")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            for index, item in enumerate(value, start=1):
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    index,
                    "json_array_item",
                    item,
                )
        else:
            yield make_raw_record(
                source,
                dataset,
                relative_path,
                1,
                "json_document",
                value,
            )
        return
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return
            for index, value in enumerate(reader, start=1):
                if None in value:
                    continue
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    index,
                    "csv_row",
                    dict(value),
                )
        return
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pyarrow é necessário para ler Parquet.") from exc
        parquet = pq.ParquetFile(path)
        record_number = 0
        for batch in parquet.iter_batches(batch_size=4_096):
            for value in batch.to_pylist():
                record_number += 1
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    record_number,
                    "parquet_row",
                    value,
                )
        return
    raise ValueError(f"Formato não suportado listado em G01: {relative_path}")


def make_raw_record(
    source: str,
    dataset: str,
    relative_path: str,
    record_number: int,
    technical_kind: str,
    value: Any,
) -> RawRecord:
    return RawRecord(
        source=source,
        dataset=dataset,
        record_type=declared_record_type(value, technical_kind),
        relative_path=relative_path,
        record_number=record_number,
        technical_kind=technical_kind,
        value=value,
    )


def occurrences_by_path(value: Any) -> dict[str, list[Any]]:
    result: defaultdict[str, list[Any]] = defaultdict(list)
    for path, occurrence in flatten_fields(value):
        result[path].append(occurrence)
    return dict(result)


def occurrence_state(values: Sequence[Any] | None) -> str:
    if values is None:
        return "absent"
    states = {value_state(value) for value in values}
    if "filled" in states:
        return "filled"
    if "empty" in states:
        return "empty"
    return "null"


def typed_occurrence_token(values: Sequence[Any]) -> str:
    typed = [
        {
            "technical_type": technical_type(value),
            "value": canonical_json_value(value),
        }
        for value in values
    ]
    return json_compact(typed)


def sanitize_record(
    value: Any,
    *,
    group: tuple[str, str, str],
    field_roles: Mapping[tuple[str, str, str, str], str],
    metadata_value_limit: int,
    path: str = "$",
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_record(
                child,
                group=group,
                field_roles=field_roles,
                metadata_value_limit=metadata_value_limit,
                path=f"{path}.{escape_path_key(str(key))}",
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            sanitize_record(
                child,
                group=group,
                field_roles=field_roles,
                metadata_value_limit=metadata_value_limit,
                path=f"{path}[]",
            )
            for child in value
        ]
    if isinstance(value, str):
        role = field_roles.get((*group, path), "unknown")
        if role == "metadata" and len(value) <= metadata_value_limit:
            return value
        return {
            "__redacted_string__": True,
            "length": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "semantic_role": role,
        }
    if isinstance(value, bytes):
        return {
            "__redacted_bytes__": True,
            "length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    return canonical_json_value(value)


def structure_signature(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): structure_signature(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [structure_signature(child) for child in value]
    return {"technical_type": technical_type(value), "state": value_state(value)}


def build_conflict_rows(
    field_rows: Sequence[Mapping[str, str]],
    sample_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    samples_by_field: defaultdict[
        tuple[str, str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for sample in sample_rows:
        samples_by_field[field_key(sample)].append(sample)
    rows = []
    for row in sorted(field_rows, key=field_sort_key):
        if not truthy(row["type_conflict"]):
            continue
        rows.append(
            {
                **dict(row),
                "safe_examples_json": json_compact(
                    sorted(
                        samples_by_field.get(field_key(row), []),
                        key=lambda item: str(item.get("sample_hash", "")),
                    )
                ),
                "decision": "conflito_aberto",
                "proposed_treatment": "",
                "human_rationale": "",
            }
        )
    return rows


def build_rejected_rows(
    issues: Sequence[Mapping[str, str]],
    raw_root: Path,
) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if issue.get("issue_type") not in {"invalid_json_line", "invalid_csv_row"}:
            continue
        relative_path = issue["relative_path"]
        record_number = int(issue["record_number"])
        raw_hash = rejected_physical_line_hash(
            raw_root / relative_path,
            (
                record_number + 1
                if Path(relative_path).suffix.lower() == ".csv"
                else record_number
            ),
        )
        rows.append(
            {
                "severity": issue["severity"],
                "issue_type": issue["issue_type"],
                "relative_path": relative_path,
                "record_number": record_number,
                "field_path": issue.get("field_path", ""),
                "detail": issue["detail"],
                "raw_line_sha256": raw_hash,
                "treatment": "preserved_rejected_no_repair",
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["relative_path"], row["record_number"]),
    )


def rejected_physical_line_hash(path: Path, line_number: int) -> str:
    if path.suffix.lower() not in {".jsonl", ".ndjson", ".csv"}:
        return ""
    with path.open("rb") as handle:
        for index, line in enumerate(handle, start=1):
            if index == line_number:
                return hashlib.sha256(line).hexdigest()
    raise ValueError(f"Linha rejeitada não localizável: {path}#{line_number}")


def render_ccj_report(
    field_rows: Sequence[Mapping[str, str]],
    conflict_rows: Sequence[Mapping[str, Any]],
) -> str:
    ccj = [
        row
        for row in field_rows
        if row["source"] == "senado" and row["dataset"] == "ccj_notas"
    ]
    groups = Counter(row["record_type"] for row in ccj)
    type_variants = Counter(row["technical_types"] for row in ccj)
    arrays = sum("[]" in row["field_path"] for row in ccj)
    conflicts = [
        row
        for row in conflict_rows
        if row["source"] == "senado" and row["dataset"] == "ccj_notas"
    ]
    lines = [
        "# Trilha estrutural — senado/ccj_notas",
        "",
        "Estado: evidência técnica; revisão humana pendente.",
        "",
        f"- caminhos preservados: {len(ccj)}",
        f"- conflitos de tipo preservados: {len(conflicts)}",
        f"- caminhos sob coleções (`[]`): {arrays}",
        "- identidade implícita de `[]`: nenhuma",
        "- coerções ou achatamentos aplicados: nenhum",
        "",
        "## Caminhos por record_type",
        "",
        "| record_type | caminhos |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {groups[key]} |" for key in sorted(groups))
    lines.extend(
        [
            "",
            "## Combinações de tipos observadas",
            "",
            "| tipos técnicos | caminhos |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| `{key}` | {type_variants[key]} |" for key in sorted(type_variants)
    )
    lines.extend(
        [
            "",
            "Objetos, arrays, escalares, nulos, vazios, ordem e multiplicidade "
            "permanecem representados pelo caminho e pelos tipos originais. "
            "Nenhum elemento de coleção é vinculado sem chave declarativa "
            "preenchida e aprovada.",
            "",
        ]
    )
    return "\n".join(lines)


def load_api_categories(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Categorias de API devem formar uma lista JSON.")
    result = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("Cada categoria de API deve ser um objeto.")
        required = {"api_category_id", "source", "name", "definition", "url", "as_of"}
        missing = required.difference(item)
        if missing:
            raise ValueError(f"Categoria de API sem campos: {sorted(missing)}")
        if not str(item["url"]).startswith("https://"):
            raise ValueError("Referência de API exige URL HTTPS oficial.")
        result.append({name: item[name] for name in sorted(item)})
    return sorted(result, key=lambda item: str(item["api_category_id"]))


def build_gpt_packets(
    *,
    field_rows: Sequence[Mapping[str, str]],
    value_rows: Sequence[Mapping[str, str]],
    field_roles: Mapping[tuple[str, str, str, str], str],
    sample_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    api_categories: Sequence[Mapping[str, Any]],
    max_fields_per_packet: int = 100,
) -> list[dict[str, Any]]:
    fields_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, str]]
    ] = defaultdict(list)
    samples_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    aliases_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    api_by_source: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    values_by_field: defaultdict[
        tuple[str, str, str, str], list[Mapping[str, str]]
    ] = defaultdict(list)
    for row in field_rows:
        if field_roles.get(field_key(row)) != "metadata":
            continue
        fields_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in sample_rows:
        samples_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in alias_rows:
        aliases_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in api_categories:
        api_by_source[str(row["source"])].append(row)
    for row in value_rows:
        values_by_field[field_key(row)].append(row)

    packets: list[dict[str, Any]] = []
    for group in sorted(fields_by_group):
        ordered_fields = sorted(fields_by_group[group], key=field_sort_key)
        for chunk_index, start in enumerate(
            range(0, len(ordered_fields), max_fields_per_packet),
            start=1,
        ):
            chunk = ordered_fields[start : start + max_fields_per_packet]
            structural_fields = []
            for row in chunk:
                key = field_key(row)
                evidence_id = stable_id(
                    "field",
                    row["source"],
                    row["dataset"],
                    row["record_type"],
                    row["field_path"],
                )
                structural_fields.append(
                    {
                        "evidence_id": evidence_id,
                        "source": row["source"],
                        "dataset": row["dataset"],
                        "record_type": row["record_type"],
                        "field_path": row["field_path"],
                        "semantic_role": "metadata",
                        "technical_types": row["technical_types"].split("|"),
                        "records_universe": int(row["records_universe"]),
                        "field_absent": int(row["field_absent"]),
                        "present_null": int(row["present_null"]),
                        "present_empty": int(row["present_empty"]),
                        "present_filled": int(row["present_filled"]),
                        "fill_rate": row["fill_rate"],
                        "cardinality": integer_or_text(row["cardinality"]),
                        "cardinality_method": row["cardinality_method"],
                        "string_length": {
                            "min": integer_or_text(row["string_length_min"]),
                            "median": number_or_text(row["string_length_median"]),
                            "max": integer_or_text(row["string_length_max"]),
                        },
                        "type_conflict": truthy(row["type_conflict"]),
                        "observed_low_cardinality_values": (
                            [
                                {
                                    "value_type": value_row["value_type"],
                                    "value": json.loads(value_row["value_json"]),
                                    "frequency": int(value_row["frequency"]),
                                    "rank": int(value_row["rank"]),
                                }
                                for value_row in sorted(
                                    values_by_field.get(key, []),
                                    key=lambda item: int(item["rank"]),
                                )
                            ]
                            if field_roles.get(key) == "metadata"
                            else []
                        ),
                    }
                )
            chunk_paths = {row["field_path"] for row in chunk}
            relevant_aliases = [
                {
                    "candidate_id": row["candidate_id"],
                    "field_a": row["field_a"],
                    "field_b": row["field_b"],
                    "u": int(row["u"]),
                    "ab": int(row["ab"]),
                    "equal": int(row["equal"]),
                    "different": int(row["different"]),
                    "coincidence_rate": row["coincidence_rate"],
                    "overlap_rate": row["overlap_rate"],
                    "evidence_status": row["evidence_status"],
                }
                for row in aliases_by_group[group]
                if row["field_a"] in chunk_paths or row["field_b"] in chunk_paths
            ]
            packet_id = stable_id(
                "packet",
                *group,
                str(chunk_index),
                sha256_json(structural_fields),
            )
            packets.append(
                {
                    "packet_id": packet_id,
                    "packet_version": "g02-structural-evidence-v1",
                    "source": group[0],
                    "dataset": group[1],
                    "record_type": group[2],
                    "chunk_index": chunk_index,
                    "structural_evidence": structural_fields,
                    "record_samples": list(samples_by_group[group]),
                    "alias_metrics": relevant_aliases,
                    "official_api_categories": list(api_by_source[group[0]]),
                    "context_previews": [],
                }
            )
    return packets


def proposal_json_schema() -> dict[str, Any]:
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "proposal_id",
            "canonical_field",
            "logical_type",
            "source_paths",
            "evidence_ids",
            "context_refs",
            "api_category_refs",
            "operation",
            "possible_aliases",
            "caveats",
            "needs_human_review",
        ],
        "properties": {
            "proposal_id": {"type": "string", "minLength": 1},
            "canonical_field": {"type": "string", "minLength": 1},
            "logical_type": {
                "type": "string",
                "enum": [
                    "string",
                    "integer",
                    "number",
                    "boolean",
                    "date",
                    "datetime",
                    "object",
                    "array",
                    "typed_union",
                    "unknown",
                ],
            },
            "source_paths": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
            },
            "evidence_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "context_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "api_category_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "operation": {
                "type": "string",
                "enum": [
                    "direct_copy",
                    "rename",
                    "lossless_cast",
                    "closed_map",
                    "preserve_unmapped",
                    "needs_human_rule",
                ],
            },
            "possible_aliases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "candidate_id",
                        "field_a",
                        "field_b",
                        "evidence_ids",
                        "status",
                    ],
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "field_a": {"type": "string"},
                        "field_b": {"type": "string"},
                        "evidence_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                        "status": {
                            "type": "string",
                            "enum": ["possible", "insufficient_evidence"],
                        },
                    },
                },
            },
            "caveats": {"type": "array", "items": {"type": "string"}},
            "needs_human_review": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["packet_id", "status", "proposals", "insufficiency_reasons"],
        "properties": {
            "packet_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["proposal", "insufficient_evidence"],
            },
            "proposals": {"type": "array", "items": proposal},
            "insufficiency_reasons": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


def proposal_prompt() -> str:
    return (
        "Você propõe somente um schema de metadados para revisão humana. "
        "Use exclusivamente structural_evidence e record_samples marcadas como "
        "evidence. Toda proposta e todo possível alias deve citar evidence_ids "
        "estruturais existentes; possível alias também deve citar um candidate_id "
        "presente em alias_metrics. context_previews são apenas context_only: não "
        "podem sustentar coluna, preenchimento, alias, marcador, orador, turno "
        "ou interpretação textual. Categorias oficiais apenas nomeiam campos "
        "observados; não criam campos ausentes. Não confirme aliases, não "
        "escolha prioridade, não descarte, não funda e não aplique regras. "
        "Quando a evidência não bastar, declare insufficient_evidence. "
        "Conflitos de tipo permanecem explícitos e exigem revisão humana."
    )


def validate_proposal(
    proposal: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    allowed_context_ids: set[str],
) -> None:
    if proposal.get("packet_id") != packet["packet_id"]:
        raise ValueError("Resposta cita packet_id diferente da entrada.")
    structural_ids = {
        item["evidence_id"] for item in packet["structural_evidence"]
    } | {
        item["evidence_id"] for item in packet["record_samples"]
    }
    known_paths = {
        item["field_path"] for item in packet["structural_evidence"]
    }
    api_ids = {
        item["api_category_id"] for item in packet["official_api_categories"]
    }
    alias_by_id = {
        item["candidate_id"]: item for item in packet.get("alias_metrics", [])
    }
    if proposal.get("status") not in {"proposal", "insufficient_evidence"}:
        raise ValueError("status da proposta inválido.")
    proposals = proposal.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("proposals deve ser lista.")
    insufficiency_reasons = proposal.get("insufficiency_reasons")
    if not isinstance(insufficiency_reasons, list):
        raise ValueError("insufficiency_reasons deve ser lista.")
    if proposal["status"] == "proposal" and not proposals:
        raise ValueError("status proposal exige ao menos uma proposta.")
    if proposal["status"] == "insufficient_evidence":
        if proposals or not insufficiency_reasons:
            raise ValueError(
                "insufficient_evidence exige propostas vazias e justificativa."
            )
    allowed_operations = {
        "direct_copy",
        "rename",
        "lossless_cast",
        "closed_map",
        "preserve_unmapped",
        "needs_human_rule",
    }
    for item in proposals:
        if not isinstance(item, Mapping):
            raise ValueError("Item de proposta deve ser objeto.")
        evidence_ids = set(item.get("evidence_ids") or [])
        if not evidence_ids or not evidence_ids.issubset(structural_ids):
            raise ValueError(
                "Proposta exige evidence_ids estruturais existentes; "
                "context_refs não os substituem."
            )
        source_paths = set(item.get("source_paths") or [])
        if not source_paths or not source_paths.issubset(known_paths):
            raise ValueError("Proposta cita caminho ausente do inventário.")
        context_refs = set(item.get("context_refs") or [])
        if not context_refs.issubset(allowed_context_ids):
            raise ValueError("Proposta cita context_id inexistente ou não aprovado.")
        if not set(item.get("api_category_refs") or []).issubset(api_ids):
            raise ValueError("Proposta cita categoria oficial inexistente.")
        if item.get("operation") not in allowed_operations:
            raise ValueError("Operação proposta fora do vocabulário fechado.")
        for alias in item.get("possible_aliases") or []:
            candidate = alias_by_id.get(alias.get("candidate_id"))
            if candidate is None:
                raise ValueError(
                    "Possível alias cita candidate_id sem auditoria recorde a recorde."
                )
            alias_evidence = set(alias.get("evidence_ids") or [])
            if not alias_evidence or not alias_evidence.issubset(structural_ids):
                raise ValueError(
                    "Possível alias exige evidence_ids estruturais válidos."
                )
            if alias.get("field_a") not in known_paths:
                raise ValueError("Alias cita field_a ausente.")
            if alias.get("field_b") not in known_paths:
                raise ValueError("Alias cita field_b ausente.")
            if {
                alias.get("field_a"),
                alias.get("field_b"),
            } != {candidate["field_a"], candidate["field_b"]}:
                raise ValueError("Possível alias diverge do par candidato auditado.")


def run_gpt_pilot(
    operation_root: Path,
    *,
    confirm_operation_id: str,
    execute_gpt: bool,
    pricing_path: Path,
    pilot_packet_ids: set[str],
    client: Any | None = None,
    model: str = REQUESTED_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    operation_root = operation_root.resolve()
    manifest_path = operation_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    operation_id = manifest["operation_id"]
    if not execute_gpt:
        raise PermissionError("Piloto GPT bloqueado: use execute_gpt=True.")
    if confirm_operation_id != operation_id:
        raise PermissionError("Confirmação literal do operation_id não confere.")
    if model != REQUESTED_MODEL:
        raise ValueError(f"O piloto aprovado exige o alias {REQUESTED_MODEL}.")
    pricing = load_pricing(pricing_path, model)
    all_packets = read_jsonl(operation_root / "pacotes_gpt.jsonl")
    if not pilot_packet_ids:
        raise PermissionError("Selecione explicitamente packet_ids para o piloto.")
    known_packet_ids = {row["packet_id"] for row in all_packets}
    unknown_packet_ids = pilot_packet_ids.difference(known_packet_ids)
    if unknown_packet_ids:
        raise ValueError(
            f"packet_ids inexistentes: {sorted(unknown_packet_ids)}"
        )
    packets = [
        row for row in all_packets if row["packet_id"] in pilot_packet_ids
    ]
    previews = read_jsonl(operation_root / "previews_contexto.jsonl")
    approved_previews = {
        row["context_id"]: row
        for row in previews
        if truthy(row.get("approved_for_gpt", False))
    }
    if not approved_previews:
        raise PermissionError(
            "Condição B exige ao menos um preview context_only aprovado humanamente."
        )
    for row in approved_previews.values():
        validate_approved_preview(row)
    preview_groups = {
        (row["source"], row["dataset"], row["record_type"])
        for row in approved_previews.values()
    }
    groups_without_preview = {
        (row["source"], row["dataset"], row["record_type"])
        for row in packets
    }.difference(preview_groups)
    if groups_without_preview:
        raise PermissionError(
            "Todo grupo selecionado para o piloto A/B exige preview aprovado: "
            f"{sorted(groups_without_preview)}"
        )
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY não está disponível no ambiente.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Instale o SDK oficial openai.") from exc
        client = OpenAI()

    prompt = proposal_prompt()
    schema = proposal_json_schema()
    prompt_hash = sha256_text(prompt)
    schema_hash = sha256_json(schema)
    proposal_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for packet in packets:
        group = (packet["source"], packet["dataset"], packet["record_type"])
        contexts = [
            row
            for row in approved_previews.values()
            if (row["source"], row["dataset"], row["record_type"]) == group
        ]
        pair_id = stable_id("ab", packet["packet_id"], model, prompt_hash, schema_hash)
        for condition in ("A", "B"):
            effective = dict(packet)
            effective["context_previews"] = [] if condition == "A" else contexts
            allowed_context_ids = {
                row["context_id"] for row in effective["context_previews"]
            }
            request_input = {
                "instructions": prompt,
                "evidence_packet": effective,
            }
            input_hash = sha256_json(request_input)
            started = time.monotonic()
            status = "error"
            refusal = ""
            error = ""
            response_payload: dict[str, Any] | None = None
            response_text = ""
            usage: Mapping[str, Any] = {}
            resolved_model = ""
            try:
                response = client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": "developer",
                            "content": [
                                {"type": "input_text", "text": prompt},
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": json.dumps(
                                        effective,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                        separators=(",", ":"),
                                    ),
                                }
                            ],
                        },
                    ],
                    reasoning={"effort": reasoning_effort},
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "schema_normalizado_proposal",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                    store=False,
                )
                response_dict = model_dump(response)
                resolved_model = str(response_dict.get("model", ""))
                usage = response_dict.get("usage") or {}
                refusal = extract_refusal(response_dict)
                response_text = extract_output_text(response, response_dict)
                if refusal:
                    status = "refused"
                else:
                    response_payload = json.loads(response_text)
                    validate_proposal(
                        response_payload,
                        effective,
                        allowed_context_ids=allowed_context_ids,
                    )
                    status = "valid"
            except Exception as exc:  # preserve the failure; never fallback
                error = safe_error_message(exc)
            latency = time.monotonic() - started
            usage_flat = flatten_usage(usage)
            cost = calculate_cost(usage_flat, pricing)
            response_hash = sha256_text(response_text) if response_text else ""
            execution_rows.append(
                {
                    "pair_id": pair_id,
                    "packet_id": packet["packet_id"],
                    "condition": condition,
                    "requested_model": model,
                    "resolved_model": resolved_model,
                    "reasoning_effort": reasoning_effort,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": prompt_hash,
                    "schema_version": PROPOSAL_SCHEMA_VERSION,
                    "schema_sha256": schema_hash,
                    "input_sha256": input_hash,
                    "response_sha256": response_hash,
                    "status": status,
                    "refusal": refusal,
                    "error": error,
                    **usage_flat,
                    "latency_seconds": format(latency, ".6f"),
                    "cost_usd": format(cost, ".8f"),
                    "pricing_ref": pricing["pricing_ref"],
                }
            )
            proposal_row = {
                "pair_id": pair_id,
                "packet_id": packet["packet_id"],
                "condition": condition,
                "status": status,
                "raw_response": response_text,
                "validated_response": response_payload,
                "error": error,
                "refusal": refusal,
            }
            proposal_rows.append(proposal_row)
            if response_payload is not None:
                mapping_rows.extend(
                    proposal_to_mapping_rows(
                        response_payload,
                        condition,
                        pair_id=pair_id,
                        packet_id=packet["packet_id"],
                        source=packet["source"],
                        dataset=packet["dataset"],
                        record_type=packet["record_type"],
                    )
                )

    write_jsonl(operation_root / "propostas_gpt.jsonl", proposal_rows)
    write_jsonl(operation_root / "execucao_gpt.jsonl", execution_rows)
    write_csv(
        operation_root / "mapeamentos_propostos.csv",
        mapping_rows,
        MAPPING_FIELDS,
    )
    manifest["gpt_pilot"] = {
        "status": "needs_human_review",
        "requested_model": model,
        "reasoning_effort": reasoning_effort,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "proposal_schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_schema_sha256": schema_hash,
        "calls": len(execution_rows),
        "pilot_packet_ids": sorted(pilot_packet_ids),
        "valid_responses": sum(row["status"] == "valid" for row in execution_rows),
        "refusals": sum(row["status"] == "refused" for row in execution_rows),
        "errors": sum(row["status"] == "error" for row in execution_rows),
    }
    refresh_manifest_outputs(operation_root, manifest)
    write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "execution_rows": execution_rows,
        "proposal_rows": proposal_rows,
        "mapping_rows": mapping_rows,
    }


def validate_approved_preview(row: Mapping[str, Any]) -> None:
    if row.get("channel") != "context_only" or row.get("context_only") is not True:
        raise ValueError("Preview aprovado perdeu o rótulo context_only.")
    start = int(row["start"])
    end = int(row["end"])
    full_length = int(row["full_length"])
    preview = str(row["preview"])
    if not (0 <= start < end <= full_length):
        raise ValueError("Posições inválidas em preview aprovado.")
    if end - start > DEFAULT_PREVIEW_LIMIT or len(preview) != end - start:
        raise ValueError("Preview aprovado excede 500 caracteres ou não reconcilia.")
    for name in ("approval_by", "approval_at", "approval_rationale"):
        if not str(row.get(name, "")).strip():
            raise ValueError(f"Preview aprovado sem {name}.")


def evaluate_context_ab(
    operation_root: Path,
    *,
    review_path: Path,
    human_preview_decision: str = "",
) -> list[dict[str, Any]]:
    operation_root = operation_root.resolve()
    executions = read_jsonl(operation_root / "execucao_gpt.jsonl")
    proposals = read_jsonl(operation_root / "propostas_gpt.jsonl")
    mappings = read_csv(operation_root / "mapeamentos_propostos.csv")
    reviews = read_csv(review_path)
    review_by_key: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in reviews:
        key = (row["pair_id"], row["condition"], row["proposal_id"])
        if key in review_by_key:
            raise ValueError(f"Revisão GPT duplicada: {key}")
        review_by_key[key] = row
    expected_review_keys = {
        (row["pair_id"], row["condition"], row["proposal_id"])
        for row in mappings
    }
    unknown_reviews = set(review_by_key).difference(expected_review_keys)
    missing_reviews = expected_review_keys.difference(review_by_key)
    if unknown_reviews:
        raise ValueError(f"Revisões citam propostas inexistentes: {unknown_reviews}")
    if missing_reviews:
        raise ValueError(f"Propostas sem revisão humana: {missing_reviews}")
    response_by_call = {
        (row["pair_id"], row["condition"]): row for row in proposals
    }
    rows: list[dict[str, Any]] = []
    for execution in executions:
        pair_id = str(execution["pair_id"])
        condition = str(execution["condition"])
        call_mappings = [
            row
            for row in mappings
            if row["condition"] == condition
            and row["pair_id"] == pair_id
        ]
        call_reviews = [
            review_by_key[(pair_id, condition, row["proposal_id"])]
            for row in call_mappings
        ]
        rows.append(
            {
                "pair_id": pair_id,
                "packet_id": execution["packet_id"],
                "condition": condition,
                "reviewed_proposals": len(call_reviews),
                "accepted_proposals": sum(
                    truthy(row.get("accepted", "")) for row in call_reviews
                ),
                "unsupported_categories": sum(
                    truthy(row.get("unsupported_category", ""))
                    for row in call_reviews
                ),
                "incorrect_aliases": sum(
                    truthy(row.get("incorrect_alias", "")) for row in call_reviews
                ),
                "insufficient_evidence": sum(
                    truthy(row.get("insufficient_evidence", ""))
                    for row in call_reviews
                )
                + int(
                    (
                        response_by_call.get((pair_id, condition), {}).get(
                            "validated_response"
                        )
                        or {}
                    ).get("status")
                    == "insufficient_evidence"
                ),
                "input_tokens": execution.get("input_tokens", 0),
                "cached_input_tokens": execution.get("cached_input_tokens", 0),
                "output_tokens": execution.get("output_tokens", 0),
                "reasoning_tokens": execution.get("reasoning_tokens", 0),
                "latency_seconds": execution.get("latency_seconds", ""),
                "cost_usd": execution.get("cost_usd", ""),
                "human_preview_decision": human_preview_decision,
            }
        )
    rows.sort(key=lambda row: (row["pair_id"], row["condition"]))
    write_csv(operation_root / "avaliacao_contexto_ab.csv", rows, AB_FIELDS)
    return rows


def proposal_to_mapping_rows(
    response: Mapping[str, Any],
    condition: str,
    *,
    pair_id: str,
    packet_id: str,
    source: str,
    dataset: str,
    record_type: str,
) -> list[dict[str, Any]]:
    rows = []
    for proposal in response.get("proposals", []):
        rows.append(
            {
                "pair_id": pair_id,
                "packet_id": packet_id,
                "proposal_id": proposal["proposal_id"],
                "condition": condition,
                "canonical_field": proposal["canonical_field"],
                "logical_type": proposal["logical_type"],
                "operation": proposal["operation"],
                "source": source,
                "dataset": dataset,
                "record_type": record_type,
                "source_paths_json": json_compact(proposal["source_paths"]),
                "evidence_ids_json": json_compact(proposal["evidence_ids"]),
                "context_refs_json": json_compact(proposal["context_refs"]),
                "api_category_refs_json": json_compact(
                    proposal["api_category_refs"]
                ),
                "possible_aliases_json": json_compact(
                    proposal["possible_aliases"]
                ),
                "caveats_json": json_compact(proposal["caveats"]),
                "needs_human_review": proposal["needs_human_review"],
                "human_decision": "nao_avaliado",
                "human_rationale": "",
            }
        )
    return rows


def write_preparation_outputs(
    *,
    operation_root: Path,
    field_book_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    preview_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
    rejected_rows: Sequence[Mapping[str, Any]],
    ccj_report: str,
    packets: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    paths = {
        "field_book": operation_root / "livro_campos.csv",
        "logical_schema": operation_root / "schema_normalizado.schema.json",
        "mappings": operation_root / "mapeamentos_propostos.csv",
        "aliases": operation_root / "auditoria_aliases.csv",
        "samples": operation_root / "amostras_estruturais.jsonl",
        "previews": operation_root / "previews_contexto.jsonl",
        "gpt_packets": operation_root / "pacotes_gpt.jsonl",
        "gpt_proposals": operation_root / "propostas_gpt.jsonl",
        "gpt_execution": operation_root / "execucao_gpt.jsonl",
        "ab_evaluation": operation_root / "avaliacao_contexto_ab.csv",
        "conflicts": operation_root / "conflitos_tipos.csv",
        "ccj_report": operation_root / "senado_ccj_notas.md",
        "rejected": operation_root / "linhas_rejeitadas.csv",
        "report": operation_root / "relatorio.md",
        "proposal_schema": operation_root / "proposta_gpt.schema.json",
        "prompt": operation_root / "prompt_gpt.md",
    }
    write_csv(paths["field_book"], field_book_rows, FIELD_BOOK_FIELDS)
    write_json(paths["logical_schema"], draft_logical_schema())
    write_csv(paths["mappings"], [], MAPPING_FIELDS)
    write_csv(paths["aliases"], alias_rows, ALIAS_FIELDS)
    write_jsonl(paths["samples"], sample_rows)
    write_jsonl(paths["previews"], preview_rows)
    write_jsonl(paths["gpt_packets"], packets)
    write_jsonl(paths["gpt_proposals"], [])
    write_jsonl(paths["gpt_execution"], [])
    write_csv(paths["ab_evaluation"], [], AB_FIELDS)
    conflict_fields = [
        *[
            "source",
            "dataset",
            "record_type",
            "field_path",
            "technical_types",
            "records_universe",
            "field_absent",
            "present_null",
            "present_empty",
            "present_filled",
            "fill_rate",
            "cardinality",
            "cardinality_method",
            "string_length_min",
            "string_length_median",
            "string_length_max",
            "first_partition",
            "last_partition",
        "type_conflict",
        "safe_examples_json",
        ],
        "decision",
        "proposed_treatment",
        "human_rationale",
    ]
    write_csv(paths["conflicts"], conflict_rows, conflict_fields)
    rejected_fields = [
        "severity",
        "issue_type",
        "relative_path",
        "record_number",
        "field_path",
        "detail",
        "raw_line_sha256",
        "treatment",
    ]
    write_csv(paths["rejected"], rejected_rows, rejected_fields)
    paths["ccj_report"].write_text(ccj_report, encoding="utf-8")
    paths["proposal_schema"].write_text(
        json.dumps(
            proposal_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["prompt"].write_text(
        f"# Prompt GPT-5.6 — {PROMPT_VERSION}\n\n{proposal_prompt()}\n",
        encoding="utf-8",
    )
    paths["report"].write_text(
        render_report(
            field_book_rows=field_book_rows,
            alias_rows=alias_rows,
            sample_rows=sample_rows,
            preview_rows=preview_rows,
            conflict_rows=conflict_rows,
            rejected_rows=rejected_rows,
            packets=packets,
        ),
        encoding="utf-8",
    )
    return paths


def draft_logical_schema() -> dict[str, Any]:
    coordinate = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "source",
            "dataset",
            "record_type",
            "relative_path",
            "record_number",
        ],
        "properties": {
            "source": {"type": "string"},
            "dataset": {"type": "string"},
            "record_type": {"type": "string"},
            "relative_path": {"type": "string"},
            "record_number": {"type": "integer", "minimum": 1},
        },
    }
    original_value = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "field_path",
            "technical_type",
            "presence_state",
            "original_value",
        ],
        "properties": {
            "field_path": {"type": "string"},
            "technical_type": {"type": "string"},
            "presence_state": {
                "type": "string",
                "enum": ["absent", "null", "empty", "filled", "rejected"],
            },
            "original_value": {},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://falandonela.local/schema/normalizado-v3-draft",
        "title": "Envelope técnico do schema normalizado v3 — G02 pendente",
        "description": (
            "Rascunho não operacional. Nenhuma categoria de domínio é incluída "
            "antes da revisão humana das evidências observadas."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "coordinate", "original_fields", "normalized"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "coordinate": coordinate,
            "original_fields": {
                "type": "array",
                "items": original_value,
            },
            "normalized": {
                "type": "object",
                "description": "Sem categorias até aprovação humana de G02.",
                "additionalProperties": False,
                "properties": {},
            },
        },
        "x-scientific-gate": "needs_review",
        "x-domain-fields": "none_before_human_g02",
        "x-source-policy": "observed_g01_metadata_only",
        "x-automatic-merge": False,
        "x-normalized-record-materialization": False,
    }


def render_report(
    *,
    field_book_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    preview_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
    rejected_rows: Sequence[Mapping[str, Any]],
    packets: Sequence[Mapping[str, Any]],
) -> str:
    unknown = sum(row["semantic_role"] == "unknown" for row in field_book_rows)
    return f"""# Evidências para o schema normalizado v3

## Estado

Execução técnica concluída; gate científico **needs_review**.

Nenhum registro normalizado foi materializado. Nenhum campo foi descartado,
fundido ou priorizado. Nenhuma proposta GPT foi aplicada.

## Cobertura

| Unidade | Quantidade |
|---|---:|
| caminhos no livro de campos | {len(field_book_rows)} |
| campos com papel semântico ainda não avaliado | {unknown} |
| pares candidatos a alias | {len(alias_rows)} |
| amostras estruturais `evidence` | {len(sample_rows)} |
| previews `context_only` não aprovados por padrão | {len(preview_rows)} |
| conflitos de tipo preservados | {len(conflict_rows)} |
| linhas rejeitadas preservadas | {len(rejected_rows)} |
| pacotes estruturais para piloto | {len(packets)} |

## Limites

- Strings não classificadas humanamente como metadados foram substituídas por
  tipo, comprimento e SHA-256 nas amostras estruturais.
- Os previews literais estão separados e nascem com
  `approved_for_gpt=false`.
- O piloto GPT exige confirmação literal da operação, preço versionado e
  aprovação de previews; a preparação não o executa.
- O schema lógico contém apenas o envelope técnico de proveniência. Categorias
  de domínio permanecem vazias até revisão humana.
- Marcadores, oradores, turnos e estruturas internas de texto continuam
  integralmente adiados.
"""


def build_manifest(
    *,
    config: SchemaConfig,
    manifest_g01: Mapping[str, Any],
    fingerprint: str,
    started_at: str,
    records_seen: int,
    paths: Mapping[str, Path],
    counts: Mapping[str, int],
) -> dict[str, Any]:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": "normalized_schema_evidence_v3",
        "operation_id": config.operation_id,
        "execution_status": "succeeded",
        "scientific_gate": "needs_review",
        "started_at": started_at,
        "finished_at": utc_now(),
        "spec_ref": SPEC_REF,
        "code_commit": config.code_commit,
        "runtime": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "openai_sdk": package_version("openai"),
            "pyarrow": package_version("pyarrow"),
        },
        "input": {
            "raw_root": str(config.raw_root),
            "write_policy": "read_only",
            "structural_fingerprint_before": fingerprint,
            "structural_fingerprint_after": fingerprint,
            "inventory_root": str(config.inventory_root),
            "inventory_operation_id": manifest_g01["operation_id"],
            "inventory_manifest_sha256": sha256_file(
                config.inventory_root / "manifest.json"
            ),
            "inventory_outputs": manifest_g01["outputs"],
            "records_read_again": records_seen,
        },
        "config": {
            "metadata_value_limit": config.metadata_value_limit,
            "preview_limit": config.preview_limit,
            "max_json_bytes": config.max_json_bytes,
            "max_alias_candidates_per_group": (
                config.max_alias_candidates_per_group
            ),
            "field_review_path": optional_text(config.field_review_path),
            "manual_alias_path": optional_text(config.manual_alias_path),
            "api_categories_path": optional_text(config.api_categories_path),
            "requested_model": REQUESTED_MODEL,
            "reasoning_effort": DEFAULT_REASONING_EFFORT,
            "prompt_version": PROMPT_VERSION,
            "proposal_schema_version": PROPOSAL_SCHEMA_VERSION,
            "coordinate_conventions": {
                "jsonl_ndjson": "physical_line_number_1_based",
                "json_array": "array_item_ordinal_1_based",
                "json_document": "constant_1",
                "csv": "data_row_ordinal_after_header_1_based",
                "parquet": "row_ordinal_1_based",
            },
        },
        "counts": dict(counts),
        "outputs": [
            artifact_ref(path, operation_root=config.operation_root)
            for path in sorted(paths.values(), key=lambda item: item.name)
        ],
        "invariants": {
            "raw_writes": 0,
            "normalized_records_materialized": 0,
            "automatic_field_merges": 0,
            "automatic_field_drops": 0,
            "gpt_proposals_applied": 0,
            "textual_structure_extractions": 0,
        },
        "next_action": (
            "Revisar papéis de campos, previews, aliases e pacotes; "
            "não abrir G02 ainda."
        ),
    }
    return manifest


def refresh_manifest_outputs(
    operation_root: Path,
    manifest: dict[str, Any],
) -> None:
    output_paths = [
        path
        for path in operation_root.iterdir()
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest["outputs"] = [
        artifact_ref(path, operation_root=operation_root)
        for path in sorted(output_paths, key=lambda item: item.name)
    ]
    manifest["finished_at"] = utc_now()


def load_pricing(path: Path, model: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model") != model:
        raise ValueError("Tabela de preços não corresponde ao modelo solicitado.")
    required = {
        "pricing_ref",
        "as_of",
        "input_per_million",
        "cached_input_per_million",
        "output_per_million",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Tabela de preços incompleta: {sorted(missing)}")
    if not str(payload["pricing_ref"]).strip():
        raise ValueError("pricing_ref é obrigatório.")
    for name in required.difference({"pricing_ref", "as_of"}):
        if Decimal(str(payload[name])) < 0:
            raise ValueError(f"Preço negativo em {name}.")
    return dict(payload)


def flatten_usage(usage: Mapping[str, Any]) -> dict[str, int]:
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(input_details.get("cached_tokens") or 0),
        "cache_write_tokens": int(input_details.get("cache_write_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
    }


def calculate_cost(
    usage: Mapping[str, int],
    pricing: Mapping[str, Any],
) -> Decimal:
    cached = int(usage["cached_input_tokens"])
    input_tokens = int(usage["input_tokens"])
    uncached = max(0, input_tokens - cached)
    output = int(usage["output_tokens"])
    total = (
        Decimal(uncached) * Decimal(str(pricing["input_per_million"]))
        + Decimal(cached) * Decimal(str(pricing["cached_input_per_million"]))
        + Decimal(output) * Decimal(str(pricing["output_per_million"]))
    )
    cache_write_price = pricing.get("cache_write_per_million")
    if cache_write_price is not None:
        total += Decimal(int(usage["cache_write_tokens"])) * Decimal(
            str(cache_write_price)
        )
    return total / Decimal(1_000_000)


def model_dump(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError("Resposta do SDK não oferece model_dump().")


def extract_output_text(response: Any, response_dict: Mapping[str, Any]) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct:
        return direct
    chunks = []
    for item in response_dict.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "".join(chunks)


def extract_refusal(response_dict: Mapping[str, Any]) -> str:
    refusals = []
    for item in response_dict.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "refusal":
                refusals.append(str(content.get("refusal") or ""))
    return "\n".join(value for value in refusals if value)


def safe_error_message(error: Exception) -> str:
    message = f"{type(error).__name__}: {error}"
    secret = os.environ.get("OPENAI_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED_API_KEY]")
    return message


def append_coordinate(values: list[str], coordinate: str, limit: int = 5) -> None:
    if len(values) < limit:
        values.append(coordinate)


def rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "nao_aplicavel"
    return format(Decimal(numerator) / Decimal(denominator), ".8f")


def field_key(
    row: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    return (
        str(row["source"]),
        str(row["dataset"]),
        str(row["record_type"]),
        str(row["field_path"]),
    )


def field_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return field_key(row)


def terminal_key(path: str) -> str:
    escaped = False
    last_dot = -1
    for index, char in enumerate(path):
        if char == "." and not escaped:
            last_dot = index
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return path[last_dot + 1 :].removesuffix("[]")


def path_depth(path: str) -> int:
    return path.count(".") + path.count("[]")


def stable_id(namespace: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{namespace}_{digest}"


def json_compact(value: Any) -> str:
    return json.dumps(
        canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return sha256_text(json_compact(value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim"}


def decimal_or_zero(value: Any) -> Decimal:
    if value in {None, ""}:
        return Decimal("0")
    return Decimal(str(value))


def integer_or_text(value: Any) -> int | str:
    if value in {None, ""}:
        return ""
    return int(value)


def number_or_text(value: Any) -> int | float | str:
    if value in {None, ""}:
        return ""
    parsed = Decimal(str(value))
    if parsed == parsed.to_integral():
        return int(parsed)
    return float(parsed)


def resolve_optional(path: Path | None) -> Path | None:
    return path.expanduser().resolve() if path is not None else None


def optional_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not_installed"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Linha JSONL não é objeto: {path}")
                rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json_compact(row) + "\n")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def artifact_ref(path: Path, *, operation_root: Path) -> dict[str, Any]:
    rows: int | None = None
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = max(0, sum(1 for _ in csv.reader(handle)) - 1)
    elif path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            rows = sum(bool(line.strip()) for line in handle)
    return {
        "name": path.name,
        "relative_path": path.relative_to(operation_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara evidências auditáveis para propor o schema v3; "
            "não materializa dados normalizados."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    prepare.add_argument("--inventory-root", type=Path, required=True)
    prepare.add_argument("--output-base", type=Path, default=DEFAULT_OUTPUT_BASE)
    prepare.add_argument("--operation-id", required=True)
    prepare.add_argument("--code-commit", required=True)
    prepare.add_argument(
        "--expected-inventory-operation-id",
        default=APPROVED_INVENTORY_OPERATION_ID,
    )
    prepare.add_argument("--expected-inventory-manifest-sha256")
    prepare.add_argument("--field-review", type=Path)
    prepare.add_argument("--manual-aliases", type=Path)
    prepare.add_argument("--api-categories", type=Path)
    prepare.add_argument(
        "--metadata-value-limit",
        type=int,
        default=DEFAULT_METADATA_VALUE_LIMIT,
    )
    prepare.add_argument("--preview-limit", type=int, default=DEFAULT_PREVIEW_LIMIT)
    prepare.add_argument("--max-json-bytes", type=int, default=DEFAULT_MAX_JSON_BYTES)
    prepare.add_argument("--progress-every-files", type=int, default=100)

    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--operation-root", type=Path, required=True)
    pilot.add_argument("--confirm-operation-id", required=True)
    pilot.add_argument("--pricing-json", type=Path, required=True)
    pilot.add_argument("--packet-id", action="append", required=True)
    pilot.add_argument("--execute-gpt", action="store_true")
    pilot.add_argument("--model", default=REQUESTED_MODEL)
    pilot.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)

    evaluate = subparsers.add_parser("evaluate-ab")
    evaluate.add_argument("--operation-root", type=Path, required=True)
    evaluate.add_argument("--review-csv", type=Path, required=True)
    evaluate.add_argument("--human-preview-decision", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        result = prepare_schema_evidence(
            SchemaConfig(
                raw_root=args.raw_root,
                inventory_root=args.inventory_root,
                output_base=args.output_base,
                operation_id=args.operation_id,
                code_commit=args.code_commit,
                expected_inventory_operation_id=(
                    args.expected_inventory_operation_id
                ),
                expected_inventory_manifest_sha256=(
                    args.expected_inventory_manifest_sha256
                ),
                field_review_path=args.field_review,
                manual_alias_path=args.manual_aliases,
                api_categories_path=args.api_categories,
                metadata_value_limit=args.metadata_value_limit,
                preview_limit=args.preview_limit,
                max_json_bytes=args.max_json_bytes,
                progress_every_files=args.progress_every_files,
            )
        )
        print(result["paths"]["report"])
        print("scientific_gate:", result["manifest"]["scientific_gate"])
        return 0
    if args.command == "pilot":
        result = run_gpt_pilot(
            args.operation_root,
            confirm_operation_id=args.confirm_operation_id,
            execute_gpt=args.execute_gpt,
            pricing_path=args.pricing_json,
            pilot_packet_ids=set(args.packet_id),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        print(
            args.operation_root / "execucao_gpt.jsonl",
            "| calls:",
            len(result["execution_rows"]),
        )
        return 0
    rows = evaluate_context_ab(
        args.operation_root,
        review_path=args.review_csv,
        human_preview_decision=args.human_preview_decision,
    )
    print(args.operation_root / "avaliacao_contexto_ab.csv", "| rows:", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
