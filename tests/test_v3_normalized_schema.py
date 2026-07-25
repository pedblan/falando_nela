from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pipeline_dados_v3.inventario_metadados_raw import (
    InventoryConfig,
    run_inventory,
)
from pipeline_dados_v3.schema_normalizado import (
    APPROVED_INVENTORY_MANIFEST_SHA256,
    AliasMetrics,
    LinkRule,
    RawRecord,
    SchemaConfig,
    audit_linked_records,
    build_compact_global_catalog,
    evaluate_context_ab,
    global_schema_prompt,
    initialize_field_review,
    prepare_schema_evidence,
    read_jsonl,
    run_gpt_pilot,
    validate_proposal,
    write_jsonl,
)


COMMIT = "b" * 40


def test_approved_g01_manifest_hash_is_pinned() -> None:
    assert (
        APPROVED_INVENTORY_MANIFEST_SHA256
        == "b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9"
    )


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
    assert first["manifest"]["counts"]["rejected_lines"] == 1
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
    assert first["manifest"]["counts"]["records_rejected"] == 1
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
        + "\n{invalido\n",
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
