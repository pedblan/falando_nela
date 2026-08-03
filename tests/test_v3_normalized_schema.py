from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

from pipeline_dados_v3.inventario_metadados_raw import (
    InventoryConfig,
    run_inventory,
)
from pipeline_dados_v3.schema_normalizado import (
    APPROVED_INVENTORY_MANIFEST_SHA256,
    APPROVED_LOGICAL_FIELDS,
    AliasMetrics,
    BATCH_MAPPING_OPERATION_ID,
    LinkRule,
    RawRecord,
    SchemaConfig,
    audit_linked_records,
    batch_frozen_vocabulary,
    batch_mapping_output_json_schema,
    build_compact_global_catalog,
    count_batch_mapping_input_tokens,
    draft_logical_schema,
    estimate_gpt56_batch_cost,
    estimate_gpt56_global_cost,
    evaluate_context_ab,
    generate_alias_candidates,
    GLOBAL_PROPOSAL_SCHEMA_VERSION,
    global_proposal_json_schema,
    global_schema_prompt,
    initialize_field_review,
    merge_batch_mapping_attempts,
    prepare_batch_mapping,
    prepare_batch_repair,
    prepare_schema_evidence,
    read_jsonl,
    reconcile_rejected_lines,
    retrieve_batch_mapping,
    retrieve_global_proposal,
    run_gpt_pilot,
    submit_batch_mapping,
    submit_global_proposal,
    validate_global_proposal,
    validate_proposal,
    write_jsonl,
)


COMMIT = "b" * 40


def test_approved_g01_manifest_hash_is_pinned() -> None:
    assert (
        APPROVED_INVENTORY_MANIFEST_SHA256
        == "b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9"
    )


def test_logical_schema_encodes_approved_provenance_entities_and_aliases() -> None:
    schema = draft_logical_schema()
    Draft202012Validator.check_schema(schema)

    record_coordinate = schema["$defs"]["source_record_coordinate"]
    assert set(record_coordinate["required"]) == {
        "source",
        "dataset",
        "record_type",
        "source_file_path",
        "source_record_number",
        "record_locator_scheme",
    }
    value_coordinate = schema["$defs"]["source_value_coordinate"]
    assert value_coordinate["properties"]["array_index_base"]["const"] == (
        "zero_based"
    )
    assert {
        "catalog_field_path",
        "source_value_pointer",
        "source_container_shape",
        "source_occurrence_id",
    }.issubset(value_coordinate["required"])

    entities = schema["properties"]["normalized"]["properties"]["entities"][
        "properties"
    ]
    expected_entities = {
        "committee_meetings": "committee_meeting",
        "events": "event",
        "plenary_sessions": "plenary_session",
        "legislative_sessions": "legislative_session",
        "pronouncements": "pronouncement",
        "propositions": "proposition",
        "legislative_matters": "legislative_matter",
        "legislative_processes": "legislative_process",
        "documents": "document",
        "agenda_items": "agenda_item",
        "opinions": "opinion",
        "taquigraphic_quarters": "taquigraphic_quarter",
        "taquigraphic_markers": "taquigraphic_marker",
    }
    for collection, entity_type in expected_entities.items():
        assert entities[collection]["items"]["properties"]["entity_type"] == {
            "const": entity_type
        }

    cardinalities = {
        (
            item["source_entity"],
            item["relationship"],
            item["target_entity"],
        ): item["cardinality"]
        for item in schema["x-cardinalities"]
    }
    assert cardinalities[
        (
            "legible_raw_record",
            "has_source_value_occurrence",
            "source_value_occurrence",
        )
    ] == "1:N"
    assert cardinalities[
        ("committee_meeting", "has_part", "meeting_part")
    ] == "0:N"
    assert cardinalities[
        (
            "committee_meeting_observation",
            "has_presidency",
            "participation",
        )
    ] == "0..1"

    canonical_fields = set(
        schema["$defs"]["lineaged_value"]["properties"]["canonical_field"][
            "enum"
        ]
    )
    assert {
        "speech_indexing_source_raw",
        "proposition_subject_source",
        "committee_meeting_id",
        "plenary_session_id",
        "legislative_session_id",
        "pronouncement_official_id",
    }.issubset(canonical_fields)
    assert "index" not in canonical_fields
    assert schema["x-index-policy"]["generic_index_field_allowed"] is False

    alias_decisions = schema["x-approved-technical-duplications"]
    assert sum(
        item["decision"] == "technical_duplication"
        for item in alias_decisions
    ) == 7
    assert sum(item["decision"] == "not_alias" for item in alias_decisions) == 1
    assert all(item["raw_mutation_allowed"] is False for item in alias_decisions)
    assert all(
        item["preserve_all_source_lineages"] is True
        for item in alias_decisions
    )
    agenda_detail = next(
        item
        for item in alias_decisions
        if item["rule_id"] == "alias-ccj-agenda-detail-subtrees"
    )
    assert agenda_detail["field_ids"] == ["F13711", "F16294"]
    assert agenda_detail["source_paths"] == [
        "$.payload.metadata.agenda",
        "$.payload.metadata.detalhe",
    ]
    assert agenda_detail["canonical_target"] is None
    meeting_id_duplication = next(
        item
        for item in alias_decisions
        if item["rule_id"] == "alias-senado-meeting-id"
    )
    assert meeting_id_duplication["source_paths"] == [
        "$.payload.CodigoReuniao",
        "$.payload.codigo_reuniao",
    ]
    assert meeting_id_duplication["supporting_field_ids"] == [
        "F16569",
        "F16570",
    ]

    assert schema["x-physical-layout"] == "deferred_to_g03_g05"
    assert schema["x-parquet-layout-assumed"] is False
    assert schema["x-normalized-record-materialization"] is False


def test_logical_schema_accepts_a_minimal_fully_lineaged_record() -> None:
    schema = draft_logical_schema()
    occurrence_id = "sha256:" + ("1" * 64)
    mapping_rule = {
        "method": "python_regra_aprovada",
        "rule_id": "copy-envelope-field-v1",
        "rule_version": "1",
        "validation_state": "valid",
        "human_decision": "approved",
    }

    def lineaged_value(canonical_field: str, value: str) -> dict[str, Any]:
        return {
            "canonical_field": canonical_field,
            "logical_type": "string",
            "normalized_value": value,
            "source_occurrence_ids": [occurrence_id],
            "mapping_rule": mapping_rule,
        }

    instance = {
        "schema_version": "normalized-schema-evidence-v3.1",
        "source_record_coordinate": {
            "source": "senado",
            "dataset": "ccj_notas",
            "record_type": "reuniao_detalhe",
            "source_file_path": "senado/ccj_notas/metadata/run.jsonl",
            "source_record_number": 1842,
            "record_locator_scheme": "jsonl_physical_line_1_based",
        },
        "source_field_states": [
            {
                "catalog_field_path": "$.source",
                "presence_state": "filled",
                "technical_types": ["string"],
                "source_occurrence_ids": [occurrence_id],
            }
        ],
        "source_value_occurrences": [
            {
                "coordinate": {
                    "catalog_field_path": "$.source",
                    "source_value_pointer": "/source",
                    "source_container_shape": [],
                    "source_occurrence_id": occurrence_id,
                    "array_index_base": "zero_based",
                },
                "technical_type": "string",
                "presence_state": "filled",
                "original_value": "senado",
            }
        ],
        "normalized": {
            "record_scope": {
                "source": lineaged_value("source", "senado"),
                "dataset": lineaged_value("dataset", "ccj_notas"),
                "record_type": lineaged_value(
                    "record_type",
                    "reuniao_detalhe",
                ),
            },
            "record_metadata": [],
            "entities": {},
            "relationships": [],
        },
    }
    Draft202012Validator(schema).validate(instance)


def test_alias_metrics_distinguish_presence_type_and_zero_denominators() -> None:
    metrics = AliasMetrics()
    observations = [
        ([1], [1]),
        ([1], ["1"]),
        ([None], [None]),
        ([""], [""]),
        (None, [2]),
        ([3], None),
    ]
    for index, (left, right) in enumerate(observations, start=1):
        metrics.observe(left, right, f"fixture.jsonl#{index}")

    assert metrics.u == 4
    assert metrics.ab == 2
    assert metrics.equal == 1
    assert metrics.different == 1
    assert metrics.only_a == 1
    assert metrics.only_b == 1
    assert metrics.rates() == {
        "coincidence_rate": "0.50000000",
        "overlap_rate": "0.50000000",
        "only_a_rate": "0.25000000",
        "only_b_rate": "0.25000000",
    }
    assert metrics.a_null == 1
    assert metrics.a_empty == 1
    assert metrics.b_null == 1
    assert metrics.b_empty == 1

    ordered = AliasMetrics()
    ordered.observe([[1, 2]], [[2, 1]], "fixture.jsonl#1")
    ordered.observe([1, 1], [1], "fixture.jsonl#2")
    assert ordered.different == 2

    empty = AliasMetrics()
    empty.observe(None, [None], "fixture.jsonl#1")
    assert set(empty.rates().values()) == {"nao_aplicavel"}


def test_linked_audit_excludes_ambiguous_keys() -> None:
    records_a = [
        raw_record(1, {"id": 1, "value": "x"}, side="a"),
        raw_record(2, {"id": 2, "value": "y"}, side="a"),
        raw_record(3, {"id": 2, "value": "duplicate"}, side="a"),
    ]
    records_b = [
        raw_record(1, {"id": 1, "other": "x"}, side="b"),
        raw_record(2, {"id": 2, "other": "y"}, side="b"),
        raw_record(3, {"other": "unkeyed"}, side="b"),
    ]

    metrics = audit_linked_records(
        records_a,
        records_b,
        rule=LinkRule(
            rule_id="link_fixture_v1",
            link_path_a="$.id",
            link_path_b="$.id",
            value_path_a="$.value",
            value_path_b="$.other",
            link_field_role_a="metadata",
            link_field_role_b="metadata",
            approved_by="pesquisador",
        ),
    )

    assert metrics.link_matched == 1
    assert metrics.link_ambiguous == 1
    assert metrics.equal == 1
    assert metrics.evidence_status == "measured_with_ambiguous_keys_excluded"

    text_rule = LinkRule(
        rule_id="invalid_text_link",
        link_path_a="$.id",
        link_path_b="$.id",
        value_path_a="$.value",
        value_path_b="$.other",
        link_field_role_a="text",
        link_field_role_b="metadata",
        approved_by="pesquisador",
    )
    try:
        audit_linked_records(records_a, records_b, rule=text_rule)
    except ValueError as exc:
        assert "metadados aprovados" in str(exc)
    else:
        raise AssertionError("Vínculo textual deveria ser rejeitado.")


def test_prepare_evidence_is_read_only_complete_and_deterministic(
    tmp_path: Path,
) -> None:
    setup = prepare_fixture_inputs(tmp_path)
    before = tree_hashes(setup["raw_root"])
    template_path = tmp_path / "new-review.csv"
    initialize_field_review(
        schema_config(setup, tmp_path / "unused-output", "template-fixture"),
        template_path,
    )
    with template_path.open("r", encoding="utf-8", newline="") as handle:
        template_rows = list(csv.DictReader(handle))
    assert len(template_rows) == setup["field_count"]
    assert {row["semantic_role"] for row in template_rows} == {"unknown"}
    assert {row["decision"] for row in template_rows} == {"nao_avaliado"}

    first = prepare_schema_evidence(
        schema_config(setup, tmp_path / "schema-output", "schema-fixture-a")
    )
    second = prepare_schema_evidence(
        schema_config(setup, tmp_path / "schema-output", "schema-fixture-b")
    )

    assert tree_hashes(setup["raw_root"]) == before
    assert first["manifest"]["scientific_gate"] == "needs_review"
    assert first["manifest"]["invariants"]["normalized_records_materialized"] == 0
    assert len(first["field_book_rows"]) == setup["field_count"]
    assert first["manifest"]["counts"]["rejected_lines"] == 2
    assert first["manifest"]["counts"]["type_conflicts"] == 1
    conflict_rows = read_csv_rows(first["paths"]["conflicts"])
    assert len(conflict_rows) == 1
    assert json.loads(conflict_rows[0]["safe_examples_json"])

    alias = next(
        row
        for row in first["alias_rows"]
        if {row["field_a"], row["field_b"]}
        == {"$.author.id", "$.speaker.id"}
    )
    assert alias["u"] == 3
    assert alias["ab"] == 2
    assert alias["equal"] == 1
    assert alias["different"] == 1
    assert alias["only_a"] == 1
    assert alias["human_decision"] == "nao_avaliado"

    sample_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            first["paths"]["samples"],
            first["paths"]["gpt_packets"],
        ]
    )
    assert setup["long_text"] not in sample_text
    assert "__redacted_string__" in sample_text
    assert "metadado-curto" in sample_text
    assert {
        row["selection_role"] for row in first["sample_rows"]
    } == {"typical", "sparse", "rare_or_conflict"}
    assert all("structure_hash" in row for row in first["sample_rows"])

    previews = first["preview_rows"]
    assert previews
    assert all(row["context_only"] is True for row in previews)
    assert all(row["approved_for_gpt"] is False for row in previews)
    assert all(row["end"] - row["start"] <= 500 for row in previews)
    assert any(row["preview"] in setup["long_text"] for row in previews)

    deterministic_names = [
        "livro_campos.csv",
        "auditoria_aliases.csv",
        "amostras_estruturais.jsonl",
        "previews_contexto.jsonl",
        "conflitos_tipos.csv",
        "linhas_rejeitadas.csv",
        "pacotes_gpt.jsonl",
    ]
    for name in deterministic_names:
        assert (
            first["paths"]["manifest"].parent / name
        ).read_bytes() == (
            second["paths"]["manifest"].parent / name
        ).read_bytes()

    source_manifest = first["paths"]["manifest"]
    source_payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_payload["counts"]["rejected_lines"] = 1
    source_manifest.write_text(
        json.dumps(source_payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    inventory_manifest = setup["inventory_root"] / "manifest.json"
    reconciled = reconcile_rejected_lines(
        raw_root=setup["raw_root"],
        inventory_root=setup["inventory_root"],
        source_audit_root=source_manifest.parent,
        output_base=tmp_path / "rejected-reconciliation",
        operation_id="schema-fixture-rejected-lines",
        code_commit=COMMIT,
        expected_inventory_operation_id="fixture-g01",
        expected_inventory_manifest_sha256=sha256_bytes(
            inventory_manifest.read_bytes()
        ),
    )
    assert len(reconciled["rows"]) == 2
    assert reconciled["manifest"]["counts"] == {
        "records_rejected_expected": 2,
        "records_rejected_reconciled": 2,
        "source_issue_rows_deduplicated": 1,
        "deduplication_gap_recovered": 1,
    }
    assert reconciled["manifest"]["invariants"]["raw_writes"] == 0


def test_compact_global_catalog_covers_every_path_and_is_reusable(
    tmp_path: Path,
) -> None:
    setup = prepare_fixture_inputs(tmp_path)
    inventory_root = setup["inventory_root"]
    manifest_path = inventory_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kwargs = {
        "inventory_manifest": manifest,
        "inventory_manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "field_rows": read_csv_rows(inventory_root / "inventario_campos.csv"),
        "issue_rows": read_csv_rows(inventory_root / "inconsistencias.csv"),
        "sample_rows": read_jsonl(inventory_root / "amostras_campos.jsonl"),
        "output_dir": tmp_path / "compact-catalog",
        "expected_operation_id": "fixture-g01",
        "catalog_profile": "schema_core",
        "standard_sample_fields": 50,
        "ccj_sample_fields": 50,
        "samples_per_field": 2,
    }
    first = build_compact_global_catalog(**kwargs)
    second = build_compact_global_catalog(**kwargs)

    assert first["paths"]["catalog"].read_bytes() == second["paths"][
        "catalog"
    ].read_bytes()
    assert len(first["field_rows"]) == setup["field_count"]
    assert len({row["field_id"] for row in first["field_rows"]}) == setup[
        "field_count"
    ]
    assert {
        (
            row["source"],
            row["dataset"],
            row["record_type"],
            row["field_path"],
        )
        for row in first["field_rows"]
    } == {
        (
            row["source"],
            row["dataset"],
            row["record_type"],
            row["field_path"],
        )
        for row in kwargs["field_rows"]
    }
    compact_text = first["paths"]["catalog"].read_text(encoding="utf-8")
    assert reconstruct_compact_paths(compact_text) == {
        row["field_id"]: row["field_path"] for row in first["field_rows"]
    }
    assert setup["long_text"] not in compact_text
    assert "redacted_long_string" in compact_text
    field_lines = [
        line for line in compact_text.splitlines() if line.startswith("F|")
    ]
    assert field_lines
    assert all(len(line.split("|")) == 8 for line in field_lines)
    assert first["manifest"]["catalog_profile"] == "schema_core"
    assert first["manifest"]["counts"]["records_rejected"] == 2
    assert first["manifest"]["counts"]["type_conflicts"] == 1
    assert first["manifest"]["counts"]["ccj_notas_field_paths"] == setup[
        "field_count"
    ]
    assert first["manifest"]["invariants"][
        "all_inventory_paths_in_crosswalk"
    ] is True
    assert "23.786" in global_schema_prompt()

    first["paths"]["catalog"].write_text("divergente\n", encoding="utf-8")
    try:
        build_compact_global_catalog(**kwargs)
    except FileExistsError as exc:
        assert "não será sobrescrito" in str(exc)
    else:
        raise AssertionError("Catálogo divergente não deveria ser sobrescrito.")


def test_global_proposal_is_closed_and_references_only_crosswalk_ids() -> None:
    schema = global_proposal_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["canonical_columns"]["items"][
        "additionalProperties"
    ] is False
    field_rows = [{"field_id": "f1"}, {"field_id": "f2"}]
    proposal = {
        "proposal_version": GLOBAL_PROPOSAL_SCHEMA_VERSION,
        "status": "proposal",
        "summary": "fixture",
        "canonical_columns": [
            {
                "canonical_name": "event_id",
                "label_pt": "Evento",
                "definition": "Identificador do evento segundo a fonte.",
                "research_role": "event",
                "logical_type": "string",
                "cardinality": "scalar",
                "nullable": True,
                "representative_field_ids": ["f1"],
                "mapping_operations": ["direct_copy"],
                "api_alignment": [],
                "caveats": [],
                "needs_human_review": True,
            }
        ],
        "field_families": [
            {
                "family_id": "event",
                "description": "Eventos observados.",
                "canonical_candidates": ["event_id"],
                "representative_field_ids": ["f1"],
                "scope_groups": ["G1"],
                "selection_criteria": ["metadado preenchido"],
                "unmapped_policy": "preserve_unmapped",
            }
        ],
        "alias_hypotheses": [
            {
                "hypothesis_id": "alias-1",
                "field_ids": ["f1", "f2"],
                "rationale": "nomes próximos; não confirmado",
                "required_audit": "record_by_record_exact_typed",
                "status": "candidate_only",
            }
        ],
        "type_conflict_policy": {
            "general_policy": ["preservar conflito"],
            "ccj_notas_policy": ["trilha própria"],
            "representative_field_ids": ["f2"],
        },
        "rejected_records_policy": ["preservar 14 rejeições"],
        "batch_mapping_contract": {
            "schema_version": "fixture-v1",
            "allowed_decisions": ["map", "preserve_unmapped"],
            "required_output_per_field": ["field_id", "decision"],
            "prohibitions": ["não aplicar"],
        },
        "unresolved_questions": [],
        "insufficiency_reasons": [],
    }
    validate_global_proposal(proposal, field_rows)

    proposal["canonical_columns"][0]["representative_field_ids"] = ["missing"]
    try:
        validate_global_proposal(proposal, field_rows)
    except ValueError as exc:
        assert "field_id inexistentes" in str(exc)
    else:
        raise AssertionError("field_id inexistente deveria invalidar a proposta.")


def test_gpt56_global_cost_uses_long_context_rates() -> None:
    assert estimate_gpt56_global_cost(
        input_tokens=691_302,
        output_tokens=32_000,
    ) == Decimal("8.353020")
    assert estimate_gpt56_global_cost(
        input_tokens=691_302,
        output_tokens=32_000,
        cache_write_tokens=691_302,
    ) == Decimal("10.0812750")


def test_global_submission_is_reusable_and_completion_is_not_applied(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "runtime"
    drive_dir = tmp_path / "drive"
    runtime_dir.mkdir()
    catalog = runtime_dir / "catalogo_global_gpt56.txt"
    catalog.write_text("fixture\n", encoding="utf-8")
    catalog_sha256 = sha256_bytes(catalog.read_bytes())
    (runtime_dir / "catalogo_global_crosswalk.csv").write_text(
        "field_id\nf1\nf2\n",
        encoding="utf-8",
    )
    (runtime_dir / "catalogo_global_amostras.csv").write_text(
        "field_id\n",
        encoding="utf-8",
    )
    (runtime_dir / "catalogo_global_manifest.json").write_text(
        json.dumps(
            {
                "catalog_profile": "schema_core",
                "counts": {
                    "field_paths": 23_786,
                    "records_rejected": 14,
                    "type_conflicts": 543,
                    "ccj_notas_field_paths": 20_523,
                },
            }
        ),
        encoding="utf-8",
    )
    (runtime_dir / "upload_token_count.json").write_text(
        json.dumps(
            {
                "model": "gpt-5.6",
                "file_id": "file-fixture",
                "catalog_sha256": catalog_sha256,
                "fits": True,
            }
        ),
        encoding="utf-8",
    )
    proposal = global_proposal_fixture()
    client = FakeGlobalOpenAIClient(proposal)

    first = submit_global_proposal(
        runtime_dir,
        drive_dir,
        confirm_operation_id="schema-global-gpt56-20260724",
        execute_gpt=True,
        client=client,
    )
    second = submit_global_proposal(
        runtime_dir,
        drive_dir,
        confirm_operation_id="schema-global-gpt56-20260724",
        execute_gpt=True,
        client=client,
    )

    assert first["reused"] is False
    assert second["reused"] is True
    assert first["response_id"] == second["response_id"] == "resp-global-fixture"
    assert client.responses.create_calls == 1
    assert {
        path.name for path in drive_dir.iterdir()
    }.issuperset(
        {
            "catalogo_global_gpt56.txt",
            "catalogo_global_crosswalk.csv",
            "catalogo_global_amostras.csv",
            "catalogo_global_manifest.json",
            "upload_token_count.json",
            "submission_receipt.json",
        }
    )

    result = retrieve_global_proposal(
        drive_dir,
        client=client,
        expected_field_paths=2,
    )
    assert result["status"] == "completed"
    assert result["scientific_gate"] == "needs_human_review"
    assert result["proposal_applied"] is False
    assert (drive_dir / "response_raw.json").is_file()
    assert (drive_dir / "proposta_schema_global.json").is_file()
    assert json.loads(
        (drive_dir / "execution.json").read_text(encoding="utf-8")
    )["proposal_applied"] is False


def batch_fixture_inputs(tmp_path: Path) -> tuple[Path, Path]:
    crosswalk = tmp_path / "catalogo_global_crosswalk.csv"
    fieldnames = [
        "field_id",
        "group_id",
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
    ]
    rows = [
        {
            "field_id": "F00001",
            "group_id": "G001",
            "source": "senado",
            "dataset": "ccj_notas",
            "record_type": "notas_taquigraficas",
            "field_path": "$.payload.CodigoReuniao",
            "technical_types": "string",
            "records_universe": "10",
            "field_absent": "0",
            "present_null": "0",
            "present_empty": "0",
            "present_filled": "10",
            "fill_rate": "1",
            "cardinality": "3",
            "cardinality_method": "exact_scalar_values",
            "string_length_min": "1",
            "string_length_median": "2",
            "string_length_max": "3",
            "first_partition": "",
            "last_partition": "",
            "type_conflict": "False",
        },
        {
            "field_id": "F00002",
            "group_id": "G001",
            "source": "senado",
            "dataset": "ccj_notas",
            "record_type": "notas_taquigraficas",
            "field_path": "$.payload.TextoIntegral",
            "technical_types": "string",
            "records_universe": "10",
            "field_absent": "1",
            "present_null": "1",
            "present_empty": "2",
            "present_filled": "6",
            "fill_rate": "0.6",
            "cardinality": "6",
            "cardinality_method": "exact_scalar_values",
            "string_length_min": "0",
            "string_length_median": "20",
            "string_length_max": "100",
            "first_partition": "",
            "last_partition": "",
            "type_conflict": "False",
        },
        {
            "field_id": "F00003",
            "group_id": "G001",
            "source": "senado",
            "dataset": "ccj_notas",
            "record_type": "notas_taquigraficas",
            "field_path": "$.payload.metadata.agenda",
            "technical_types": "array|object",
            "records_universe": "10",
            "field_absent": "5",
            "present_null": "0",
            "present_empty": "1",
            "present_filled": "4",
            "fill_rate": "0.4",
            "cardinality": "",
            "cardinality_method": "not_applicable_complex",
            "string_length_min": "",
            "string_length_median": "",
            "string_length_max": "",
            "first_partition": "",
            "last_partition": "",
            "type_conflict": "True",
        },
    ]
    with crosswalk.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    proposal = global_proposal_fixture()
    proposal_text = json.dumps(proposal)
    proposal_text = proposal_text.replace('"f1"', '"F00001"')
    proposal_text = proposal_text.replace('"f2"', '"F00002"')
    proposal_path = tmp_path / "proposta_schema_global.json"
    proposal_path.write_text(proposal_text, encoding="utf-8")
    return crosswalk, proposal_path


class FakeBatchInputTokens:
    def count(self, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["model"] == "gpt-5.6-sol"
        assert kwargs["text"]["format"]["strict"] is True
        return SimpleNamespace(input_tokens=100)


class FakeBatchResponses:
    def __init__(self) -> None:
        self.input_tokens = FakeBatchInputTokens()


class FakeBatchFiles:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.create_calls = 0

    def create(self, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["purpose"] == "batch"
        assert kwargs["file"].read(1)
        self.create_calls += 1
        return SimpleNamespace(id="file-batch-input")

    def content(self, file_id: str) -> SimpleNamespace:
        assert file_id == "file-batch-output"
        return SimpleNamespace(text=self.output_text)


class FakeBatchObject:
    def __init__(self, status: str) -> None:
        self.id = "batch-fixture"
        self.status = status
        self.input_file_id = "file-batch-input"

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "input_file_id": self.input_file_id,
            "output_file_id": (
                "file-batch-output" if self.status == "completed" else None
            ),
            "error_file_id": None,
            "request_counts": {
                "total": 2,
                "completed": 2 if self.status == "completed" else 0,
                "failed": 0,
            },
            "metadata": {
                "operation_id": BATCH_MAPPING_OPERATION_ID,
            },
        }


class FakeBatches:
    def __init__(self) -> None:
        self.create_calls = 0

    def list(self, limit: int) -> list[Any]:
        assert limit == 100
        return []

    def create(self, **kwargs: Any) -> FakeBatchObject:
        assert kwargs["endpoint"] == "/v1/responses"
        assert kwargs["completion_window"] == "24h"
        self.create_calls += 1
        return FakeBatchObject("validating")

    def retrieve(self, batch_id: str) -> FakeBatchObject:
        assert batch_id == "batch-fixture"
        return FakeBatchObject("completed")


class FakeBatchClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeBatchResponses()
        self.files = FakeBatchFiles(output_text)
        self.batches = FakeBatches()


def fake_batch_output(operation_root: Path) -> str:
    manifest = json.loads(
        (operation_root / "batch_manifest.json").read_text(encoding="utf-8")
    )
    lines = []
    for request in read_jsonl(operation_root / "batch_input.jsonl"):
        payload = json.loads(
            request["body"]["input"][1]["content"][0]["text"]
        )
        ids = [
            field["id"]
            for block in payload["path_blocks"]
            for field in block["f"]
        ]
        response_payload = {
            "schema_version": "gpt56-field-mapping-response-v1",
            "frozen_vocabulary_sha256": manifest["vocabulary_sha256"],
            "mappings": [
                {
                    "field_id": field_id,
                    "decision": "preserve_unmapped",
                    "canonical_candidate_or_null": None,
                    "mapping_operation": "preserve_unmapped",
                    "review_reason": "fixture sem regra substantiva",
                }
                for field_id in ids
            ],
        }
        lines.append(
            json.dumps(
                {
                    "custom_id": request["custom_id"],
                    "response": {
                        "status_code": 200,
                        "body": {
                            "model": "gpt-5.6-sol",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": json.dumps(
                                                response_payload,
                                                ensure_ascii=False,
                                            ),
                                        }
                                    ],
                                }
                            ],
                            "usage": {
                                "input_tokens": 100,
                                "input_tokens_details": {
                                    "cached_tokens": 0,
                                },
                                "output_tokens": 20,
                                "output_tokens_details": {
                                    "reasoning_tokens": 5,
                                },
                            },
                        },
                    },
                    "error": None,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(reversed(lines)) + "\n"


def test_batch_mapping_is_frozen_complete_idempotent_and_not_applied(
    tmp_path: Path,
) -> None:
    crosswalk, proposal_path = batch_fixture_inputs(tmp_path)
    operation_root = tmp_path / "batch"
    prepared = prepare_batch_mapping(
        crosswalk,
        proposal_path,
        operation_root,
        chunk_size=2,
        expected_field_paths=3,
    )
    assert prepared["manifest"]["counts"]["field_ids"] == 3
    assert prepared["manifest"]["counts"]["requests"] == 2
    assert prepared["manifest"]["proposal_applied"] is False
    request_hashes = {
        json.loads(
            request["body"]["input"][1]["content"][0]["text"]
        )["frozen_vocabulary_sha256"]
        for request in prepared["requests"]
    }
    assert request_hashes == {prepared["manifest"]["vocabulary_sha256"]}
    vocabulary = batch_frozen_vocabulary(
        json.loads(proposal_path.read_text(encoding="utf-8"))
    )
    assert set(vocabulary["approved_fields"]) == set(APPROVED_LOGICAL_FIELDS)
    Draft202012Validator.check_schema(batch_mapping_output_json_schema())

    client = FakeBatchClient("")
    estimate = count_batch_mapping_input_tokens(
        operation_root,
        client=client,
    )
    assert estimate["input_tokens"] == 200
    assert estimate["fits_conservative_queue_limit"] is True
    first = submit_batch_mapping(
        operation_root,
        confirm_operation_id=BATCH_MAPPING_OPERATION_ID,
        execute_batch=True,
        client=client,
    )
    second = submit_batch_mapping(
        operation_root,
        confirm_operation_id=BATCH_MAPPING_OPERATION_ID,
        execute_batch=True,
        client=client,
    )
    assert first["reused"] is False
    assert second["reused"] is True
    assert client.batches.create_calls == 1
    assert client.files.create_calls == 1

    client.files.output_text = fake_batch_output(operation_root)
    result = retrieve_batch_mapping(operation_root, client=client)
    assert result["status"] == "completed_validated"
    assert result["field_ids_reconciled"] == 3
    assert result["proposal_applied"] is False
    rows = read_csv_rows(
        operation_root / "mapeamentos_batch_propostos.csv"
    )
    assert [row["field_id"] for row in rows] == [
        "F00001",
        "F00002",
        "F00003",
    ]
    assert all(row["human_decision"] == "nao_avaliado" for row in rows)
    assert all(row["proposal_applied"] == "False" for row in rows)


def test_batch_partial_coverage_prepares_disjoint_repair_and_merges(
    tmp_path: Path,
) -> None:
    crosswalk, proposal_path = batch_fixture_inputs(tmp_path)
    operation_root = tmp_path / "batch"
    prepare_batch_mapping(
        crosswalk,
        proposal_path,
        operation_root,
        chunk_size=2,
        expected_field_paths=3,
    )
    primary_client = FakeBatchClient("")
    count_batch_mapping_input_tokens(operation_root, client=primary_client)
    submit_batch_mapping(
        operation_root,
        confirm_operation_id=BATCH_MAPPING_OPERATION_ID,
        execute_batch=True,
        client=primary_client,
    )
    output_rows = [
        json.loads(line)
        for line in fake_batch_output(operation_root).splitlines()
    ]
    partial_row = next(
        row
        for row in output_rows
        if len(
            json.loads(
                row["response"]["body"]["output"][0]["content"][0]["text"]
            )["mappings"]
        )
        > 1
    )
    response_text = partial_row["response"]["body"]["output"][0][
        "content"
    ][0]["text"]
    response_payload = json.loads(response_text)
    response_payload["mappings"] = response_payload["mappings"][:1]
    partial_row["response"]["body"]["output"][0]["content"][0]["text"] = (
        json.dumps(response_payload, ensure_ascii=False)
    )
    invalid_row = next(row for row in output_rows if row is not partial_row)
    invalid_text = invalid_row["response"]["body"]["output"][0]["content"][0][
        "text"
    ]
    invalid_payload = json.loads(invalid_text)
    invalid_payload["mappings"][0]["decision"] = "type_conflict_open"
    invalid_payload["mappings"][0]["mapping_operation"] = "preserve_unmapped"
    invalid_row["response"]["body"]["output"][0]["content"][0]["text"] = (
        json.dumps(invalid_payload, ensure_ascii=False)
    )
    primary_client.files.output_text = "\n".join(
        json.dumps(row, ensure_ascii=False) for row in output_rows
    )
    primary = retrieve_batch_mapping(operation_root, client=primary_client)
    assert primary["status"] == "completed_incomplete_coverage"
    assert primary["field_ids_reconciled"] == 1
    assert primary["missing_field_ids"] == 2
    assert primary["invalid_mappings"] == 1
    assert primary["scientific_gate"] == "repair_required"

    repair_root = tmp_path / "repair"
    repair_id = f"{BATCH_MAPPING_OPERATION_ID}-repair-001"
    repair = prepare_batch_repair(
        operation_root,
        repair_root,
        operation_id=repair_id,
        chunk_size=1,
    )
    assert repair["manifest"]["counts"]["field_ids"] == 2
    assert repair["manifest"]["counts"]["requests"] == 2
    repair_client = FakeBatchClient("")
    count_batch_mapping_input_tokens(repair_root, client=repair_client)
    submit_batch_mapping(
        repair_root,
        confirm_operation_id=repair_id,
        execute_batch=True,
        client=repair_client,
    )
    repair_client.files.output_text = fake_batch_output(repair_root)
    repaired = retrieve_batch_mapping(repair_root, client=repair_client)
    assert repaired["status"] == "completed_validated"
    assert repaired["field_ids_reconciled"] == 2

    merged = merge_batch_mapping_attempts(operation_root, [repair_root])
    assert merged["status"] == "completed_validated"
    assert merged["field_ids_reconciled"] == 3
    assert merged["missing_field_ids"] == 0
    assert merged["proposal_applied"] is False


def test_batch_cost_uses_half_price_and_never_hides_output_ceiling() -> None:
    assert estimate_gpt56_batch_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    ) == Decimal("17.5")
    assert estimate_gpt56_batch_cost(
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        output_tokens=0,
    ) == Decimal("0.25")


def test_human_approved_structural_alias_audit_accepts_text_without_retyping_it(
    tmp_path: Path,
) -> None:
    field_rows = [
        {
            "source": "senado",
            "dataset": "ccj_notas",
            "record_type": "notas_taquigraficas",
            "field_path": path,
            "technical_types": "string",
        }
        for path in ("$.payload.TextoIntegral", "$.payload.texto")
    ]
    roles = {
        (
            row["source"],
            row["dataset"],
            row["record_type"],
            row["field_path"],
        ): "text"
        for row in field_rows
    }
    manual = tmp_path / "manual.csv"
    with manual.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source",
                "dataset",
                "record_type",
                "field_a",
                "field_b",
                "comparison_scope",
                "candidate_signal",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source": "senado",
                "dataset": "ccj_notas",
                "record_type": "notas_taquigraficas",
                "field_a": "$.payload.TextoIntegral",
                "field_b": "$.payload.texto",
                "comparison_scope": "same_record",
                "candidate_signal": (
                    "human_approved_structural_audit:"
                    "alias-senado-notas-text:technical_duplication"
                ),
            }
        )
    candidates = generate_alias_candidates(
        field_rows,
        field_roles=roles,
        manual_alias_path=manual,
        max_per_group=None,
    )
    assert len(candidates) == 1
    assert candidates[0].candidate_signal.startswith(
        "human_approved_structural_audit:"
    )
    assert set(roles.values()) == {"text"}


def test_gpt_pilot_is_paired_a_b_and_never_applies_proposals(
    tmp_path: Path,
) -> None:
    setup = prepare_fixture_inputs(tmp_path)
    prepared = prepare_schema_evidence(
        schema_config(setup, tmp_path / "schema-output", "schema-gpt-fixture")
    )
    operation_root = prepared["paths"]["manifest"].parent
    previews = read_jsonl(operation_root / "previews_contexto.jsonl")
    for row in previews:
        row["approved_for_gpt"] = True
        row["approval_by"] = "pesquisador"
        row["approval_at"] = "2026-07-24"
        row["approval_rationale"] = "piloto sintético"
    write_jsonl(operation_root / "previews_contexto.jsonl", previews)

    pricing = tmp_path / "pricing.json"
    pricing.write_text(
        json.dumps(
            {
                "model": "gpt-5.6",
                "pricing_ref": "fixture-2026-07-24",
                "as_of": "2026-07-24",
                "input_per_million": "1",
                "cached_input_per_million": "0.1",
                "output_per_million": "2",
            }
        ),
        encoding="utf-8",
    )
    client = FakeOpenAIClient()

    result = run_gpt_pilot(
        operation_root,
        confirm_operation_id="schema-gpt-fixture",
        execute_gpt=True,
        pricing_path=pricing,
        pilot_packet_ids={row["packet_id"] for row in prepared["packets"]},
        client=client,
    )

    assert len(result["execution_rows"]) == 2 * len(prepared["packets"])
    assert {row["condition"] for row in result["execution_rows"]} == {"A", "B"}
    assert all(row["status"] == "valid" for row in result["execution_rows"])
    assert all(float(row["cost_usd"]) > 0 for row in result["execution_rows"])
    assert result["mapping_rows"]
    assert all(
        row["human_decision"] == "nao_avaliado"
        for row in result["mapping_rows"]
    )
    assert {
        (row["source"], row["dataset"], row["record_type"])
        for row in result["mapping_rows"]
    } == {("senado", "ccj_notas", "nota")}
    assert result["manifest"]["invariants"]["gpt_proposals_applied"] == 0
    assert client.context_counts.count(0) == len(prepared["packets"])
    assert sum(count > 0 for count in client.context_counts) == len(
        prepared["packets"]
    )
    review_path = tmp_path / "review.csv"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "pair_id",
            "condition",
            "proposal_id",
            "accepted",
            "unsupported_category",
            "incorrect_alias",
            "insufficient_evidence",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in result["mapping_rows"]:
            writer.writerow(
                {
                    "pair_id": row["pair_id"],
                    "condition": row["condition"],
                    "proposal_id": row["proposal_id"],
                    "accepted": True,
                    "unsupported_category": False,
                    "incorrect_alias": False,
                    "insufficient_evidence": False,
                }
            )
    ab_rows = evaluate_context_ab(
        operation_root,
        review_path=review_path,
        human_preview_decision="manter_em_revisao",
    )
    assert {row["condition"] for row in ab_rows} == {"A", "B"}
    assert all(row["accepted_proposals"] == 1 for row in ab_rows)


def test_gpt_pilot_preserves_refusal_and_error_without_fallback(
    tmp_path: Path,
) -> None:
    setup = prepare_fixture_inputs(tmp_path)
    prepared = prepare_schema_evidence(
        schema_config(setup, tmp_path / "schema-output", "schema-failure-fixture")
    )
    operation_root = prepared["paths"]["manifest"].parent
    previews = read_jsonl(operation_root / "previews_contexto.jsonl")
    for row in previews:
        row["approved_for_gpt"] = True
        row["approval_by"] = "pesquisador"
        row["approval_at"] = "2026-07-24"
        row["approval_rationale"] = "teste de falha"
    write_jsonl(operation_root / "previews_contexto.jsonl", previews)
    pricing = tmp_path / "pricing.json"
    pricing.write_text(
        json.dumps(
            {
                "model": "gpt-5.6",
                "pricing_ref": "fixture-2026-07-24",
                "as_of": "2026-07-24",
                "input_per_million": "1",
                "cached_input_per_million": "0.1",
                "output_per_million": "2",
            }
        ),
        encoding="utf-8",
    )

    result = run_gpt_pilot(
        operation_root,
        confirm_operation_id="schema-failure-fixture",
        execute_gpt=True,
        pricing_path=pricing,
        pilot_packet_ids={row["packet_id"] for row in prepared["packets"]},
        client=FailureOpenAIClient(),
    )

    statuses = [row["status"] for row in result["execution_rows"]]
    assert statuses == ["refused", "error"]
    assert result["execution_rows"][0]["refusal"] == "não posso responder"
    assert "falha sintética" in result["execution_rows"][1]["error"]
    assert result["mapping_rows"] == []
    assert result["manifest"]["invariants"]["gpt_proposals_applied"] == 0


def test_context_id_cannot_replace_structural_evidence() -> None:
    packet = {
        "packet_id": "packet-1",
        "structural_evidence": [
            {"evidence_id": "field-1", "field_path": "$.id"}
        ],
        "record_samples": [],
        "official_api_categories": [],
    }
    response = {
        "packet_id": "packet-1",
        "status": "proposal",
        "insufficiency_reasons": [],
        "proposals": [
            {
                "proposal_id": "p1",
                "canonical_field": "id",
                "logical_type": "integer",
                "source_paths": ["$.id"],
                "evidence_ids": ["context-1"],
                "context_refs": ["context-1"],
                "api_category_refs": [],
                "operation": "direct_copy",
                "possible_aliases": [],
                "caveats": [],
                "needs_human_review": True,
            }
        ],
    }

    try:
        validate_proposal(response, packet, allowed_context_ids={"context-1"})
    except ValueError as exc:
        assert "evidence_ids estruturais" in str(exc)
    else:
        raise AssertionError("context_id não pode satisfazer evidência estrutural.")

    response["proposals"][0]["evidence_ids"] = ["field-1"]
    response["proposals"][0]["source_paths"] = ["$.invented"]
    try:
        validate_proposal(response, packet, allowed_context_ids={"context-1"})
    except ValueError as exc:
        assert "caminho ausente" in str(exc)
    else:
        raise AssertionError("Caminho ausente do inventário deve ser rejeitado.")


def prepare_fixture_inputs(tmp_path: Path) -> dict[str, Any]:
    raw_root = tmp_path / "data" / "raw"
    path = raw_root / "senado" / "ccj_notas" / "fixture.jsonl"
    path.parent.mkdir(parents=True)
    long_text = "conteúdo parlamentar sem interpretação " * 30
    records = [
        {
            "record_type": "nota",
            "metadata": {"short": "metadado-curto"},
            "author": {"id": 1},
            "speaker": {"id": 1},
            "mixed": 1,
            "content": long_text,
            "items": [{"value": 1}, {"value": 2}],
            "odd.key|name": "opaque",
        },
        {
            "record_type": "nota",
            "metadata": {"short": "outro"},
            "author": {"id": 2},
            "speaker": {"id": 3},
            "mixed": "1",
            "content": long_text + "x",
            "items": [],
        },
        {
            "record_type": "nota",
            "metadata": {"short": ""},
            "author": {"id": 4},
            "speaker": {"id": None},
            "mixed": None,
            "content": "",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + "\n{invalido\n{tambem-invalido\n",
        encoding="utf-8",
    )
    inventory = run_inventory(
        InventoryConfig(
            raw_root=raw_root,
            output_base=tmp_path / "inventory",
            operation_id="fixture-g01",
            code_commit=COMMIT,
            progress_every_files=0,
        )
    )
    inventory_root = inventory["paths"]["manifest"].parent
    review_path = tmp_path / "field-review.csv"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "source",
            "dataset",
            "record_type",
            "field_path",
            "semantic_role",
            "decision",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "source": "senado",
                "dataset": "ccj_notas",
                "record_type": "nota",
                "field_path": "$.metadata.short",
                "semantic_role": "metadata",
                "decision": "candidato",
            }
        )
        for field_path in ("$.author.id", "$.speaker.id"):
            writer.writerow(
                {
                    "source": "senado",
                    "dataset": "ccj_notas",
                    "record_type": "nota",
                    "field_path": field_path,
                    "semantic_role": "metadata",
                    "decision": "candidato",
                }
            )
        writer.writerow(
            {
                "source": "senado",
                "dataset": "ccj_notas",
                "record_type": "nota",
                "field_path": "$.content",
                "semantic_role": "text",
                "decision": "adiado_para_estrutura_textual",
            }
        )
    return {
        "raw_root": raw_root,
        "inventory_root": inventory_root,
        "field_review": review_path,
        "field_count": len(inventory["field_rows"]),
        "long_text": long_text,
    }


def schema_config(
    setup: dict[str, Any],
    output_base: Path,
    operation_id: str,
) -> SchemaConfig:
    return SchemaConfig(
        raw_root=setup["raw_root"],
        inventory_root=setup["inventory_root"],
        output_base=output_base,
        operation_id=operation_id,
        code_commit=COMMIT,
        expected_inventory_operation_id="fixture-g01",
        enforce_approved_counts=False,
        field_review_path=setup["field_review"],
        progress_every_files=0,
    )


def raw_record(number: int, value: dict[str, Any], *, side: str) -> RawRecord:
    return RawRecord(
        source="fixture",
        dataset=side,
        record_type="r",
        relative_path=f"{side}.jsonl",
        record_number=number,
        technical_kind="jsonl_record",
        value=value,
    )


def tree_hashes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def reconstruct_compact_paths(text: str) -> dict[str, str]:
    prefix = ""
    paths: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("G|"):
            prefix = ""
        elif line.startswith("P|"):
            prefix = json.loads(line.split("|", 1)[1])
        elif line.startswith("F|"):
            _, field_id, path_json, *_ = line.split("|")
            paths[field_id] = prefix + json.loads(path_json)
    return paths


def sha256_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def global_proposal_fixture() -> dict[str, Any]:
    return {
        "proposal_version": GLOBAL_PROPOSAL_SCHEMA_VERSION,
        "status": "proposal",
        "summary": "fixture",
        "canonical_columns": [
            {
                "canonical_name": "event_id",
                "label_pt": "Evento",
                "definition": "Identificador do evento segundo a fonte.",
                "research_role": "event",
                "logical_type": "string",
                "cardinality": "scalar",
                "nullable": True,
                "representative_field_ids": ["f1"],
                "mapping_operations": ["direct_copy"],
                "api_alignment": [],
                "caveats": [],
                "needs_human_review": True,
            }
        ],
        "field_families": [
            {
                "family_id": "event",
                "description": "Eventos observados.",
                "canonical_candidates": ["event_id"],
                "representative_field_ids": ["f1"],
                "scope_groups": ["G1"],
                "selection_criteria": ["metadado preenchido"],
                "unmapped_policy": "preserve_unmapped",
            }
        ],
        "alias_hypotheses": [
            {
                "hypothesis_id": "alias-1",
                "field_ids": ["f1", "f2"],
                "rationale": "nomes próximos; não confirmado",
                "required_audit": "record_by_record_exact_typed",
                "status": "candidate_only",
            }
        ],
        "type_conflict_policy": {
            "general_policy": ["preservar conflito"],
            "ccj_notas_policy": ["trilha própria"],
            "representative_field_ids": ["f2"],
        },
        "rejected_records_policy": ["preservar 14 rejeições"],
        "batch_mapping_contract": {
            "schema_version": "fixture-v1",
            "allowed_decisions": ["map", "preserve_unmapped"],
            "required_output_per_field": ["field_id", "decision"],
            "prohibitions": ["não aplicar"],
        },
        "unresolved_questions": [],
        "insufficiency_reasons": [],
    }


class FakeGlobalCompletedResponse:
    def __init__(self, proposal: dict[str, Any]) -> None:
        self.id = "resp-global-fixture"
        self.status = "completed"
        self.output_text = json.dumps(proposal, ensure_ascii=False)

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "model": "gpt-5.6-sol-2026-07-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": self.output_text}
                    ],
                }
            ],
            "usage": {
                "input_tokens": 700_000,
                "input_tokens_details": {
                    "cached_tokens": 0,
                    "cache_write_tokens": 700_000,
                },
                "output_tokens": 1_000,
                "output_tokens_details": {"reasoning_tokens": 250},
            },
        }


class FakeGlobalInputTokens:
    def count(self, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["model"] == "gpt-5.6"
        assert kwargs["text"]["format"]["strict"] is True
        return SimpleNamespace(input_tokens=700_000)


class FakeGlobalResponses:
    def __init__(self, proposal: dict[str, Any]) -> None:
        self.input_tokens = FakeGlobalInputTokens()
        self.proposal = proposal
        self.create_calls = 0

    def create(self, **kwargs: Any) -> SimpleNamespace:
        assert kwargs["background"] is True
        assert kwargs["store"] is True
        assert kwargs["truncation"] == "disabled"
        self.create_calls += 1
        return SimpleNamespace(
            id="resp-global-fixture",
            status="queued",
        )

    def retrieve(self, response_id: str) -> FakeGlobalCompletedResponse:
        assert response_id == "resp-global-fixture"
        return FakeGlobalCompletedResponse(self.proposal)


class FakeGlobalOpenAIClient:
    def __init__(self, proposal: dict[str, Any]) -> None:
        self.responses = FakeGlobalResponses(proposal)


class FakeOpenAIResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.output_text = json.dumps(payload, ensure_ascii=False)
        self._payload = payload

    def model_dump(self) -> dict[str, Any]:
        return {
            "model": "gpt-5.6-sol-2026-07-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": self.output_text}
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {
                    "cached_tokens": 10,
                    "cache_write_tokens": 0,
                },
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 5},
            },
        }


class FakeResponses:
    def __init__(self, owner: "FakeOpenAIClient") -> None:
        self.owner = owner

    def create(self, **kwargs: Any) -> FakeOpenAIResponse:
        packet = json.loads(kwargs["input"][1]["content"][0]["text"])
        self.owner.context_counts.append(len(packet["context_previews"]))
        evidence = packet["structural_evidence"][0]
        payload = {
            "packet_id": packet["packet_id"],
            "status": "proposal",
            "proposals": [
                {
                    "proposal_id": "p_" + packet["packet_id"][-12:],
                    "canonical_field": "campo_proposto",
                    "logical_type": "unknown",
                    "source_paths": [evidence["field_path"]],
                    "evidence_ids": [evidence["evidence_id"]],
                    "context_refs": [],
                    "api_category_refs": [],
                    "operation": "needs_human_rule",
                    "possible_aliases": [],
                    "caveats": ["fixture"],
                    "needs_human_review": True,
                }
            ],
            "insufficiency_reasons": [],
        }
        assert kwargs["model"] == "gpt-5.6"
        assert kwargs["text"]["format"]["strict"] is True
        assert kwargs["store"] is False
        return FakeOpenAIResponse(payload)


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.context_counts: list[int] = []
        self.responses = FakeResponses(self)


class RefusalResponse:
    output_text = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "model": "gpt-5.6-sol-2026-07-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "refusal",
                            "refusal": "não posso responder",
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }


class FailureResponses:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, **kwargs: Any) -> RefusalResponse:
        del kwargs
        self.calls += 1
        if self.calls == 1:
            return RefusalResponse()
        raise RuntimeError("falha sintética")


class FailureOpenAIClient:
    def __init__(self) -> None:
        self.responses = FailureResponses()
