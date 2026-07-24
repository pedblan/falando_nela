from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline_dados_v3 import inventario_metadados_raw
from pipeline_dados_v3.inventario_metadados_raw import (
    InventoryConfig,
    run_inventory,
)


COMMIT = "a" * 40


def test_full_inventory_is_read_only_and_reconciles_field_states(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "data" / "raw"
    jsonl_path = (
        raw_root / "camara" / "plenario_discursos" / "ano=2020" / "mes=01" / "run.jsonl"
    )
    jsonl_path.parent.mkdir(parents=True)
    long_text = "conteudo-longo-" * 30
    records = [
        {
            "record_type": "discurso",
            "source": "camara",
            "dataset": "plenario_discursos",
            "nullable": None,
            "empty_string": "",
            "mixed": 1,
            "payload": {
                "tags": [{"x": 1}, {"x": 2}],
                "texto": long_text,
            },
        },
        {
            "record_type": "discurso",
            "source": "camara",
            "dataset": "plenario_discursos",
            "empty_string": "preenchido",
            "mixed": "1",
            "payload": {
                "tags": [{"x": 3}],
                "texto": long_text,
            },
        },
    ]
    jsonl_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        + "\n{invalido\n",
        encoding="utf-8",
    )
    before = tree_signature(raw_root)

    result = run_inventory(
        make_config(
            raw_root,
            tmp_path / "output",
            "inventory-full-test",
            max_copy_length=40,
        )
    )

    assert tree_signature(raw_root) == before
    manifest = result["manifest"]
    assert manifest["execution_status"] == "succeeded"
    assert manifest["scientific_gate"] == "needs_review"
    assert manifest["counts"]["records_observed"] == 3
    assert manifest["counts"]["records_read"] == 2
    assert manifest["counts"]["records_rejected"] == 1
    assert len(manifest["outputs"]) == 6

    by_path = {
        row["field_path"]: row
        for row in result["field_rows"]
        if row["record_type"] == "discurso"
    }
    assert by_path["$.nullable"]["records_universe"] == 2
    assert by_path["$.nullable"]["field_absent"] == 1
    assert by_path["$.nullable"]["present_null"] == 1
    assert by_path["$.empty_string"]["present_empty"] == 1
    assert by_path["$.empty_string"]["present_filled"] == 1
    assert by_path["$.payload.tags[].x"]["present_filled"] == 2
    assert by_path["$.payload.tags[].x"]["field_absent"] == 0
    assert by_path["$.mixed"]["type_conflict"] is True
    assert by_path["$.payload"]["cardinality_method"] == "not_applicable_complex"
    assert by_path["$.payload.texto"]["string_length_max"] == len(long_text)

    operation_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result["paths"]["manifest"].parent.iterdir()
        if path.is_file()
    )
    assert long_text not in operation_text
    assert any(issue["issue_type"] == "invalid_json_line" for issue in result["issues"])


def test_json_csv_and_parquet_are_read_as_structured_records(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    dataset_root = raw_root / "senado" / "dataset_teste"
    dataset_root.mkdir(parents=True)
    (dataset_root / "records.json").write_text(
        json.dumps([{"a": 1}, {"a": 2}]),
        encoding="utf-8",
    )
    (dataset_root / "document.json").write_text(
        json.dumps({"a": 3}),
        encoding="utf-8",
    )
    (dataset_root / "records.csv").write_text(
        "a,b\n1,\n2,x\n",
        encoding="utf-8",
    )
    pq.write_table(
        pa.table({"a": [1, 2], "b": [None, "x"]}),
        dataset_root / "records.parquet",
    )

    result = run_inventory(
        make_config(
            raw_root,
            tmp_path / "output",
            "inventory-formats-test",
        )
    )

    assert result["manifest"]["counts"]["records_observed"] == 7
    assert result["manifest"]["counts"]["records_read"] == 7
    statuses = {
        row["suffix"]: row["read_status"]
        for row in result["file_rows"]
        if row["item_type"] == "file"
    }
    assert statuses == {".csv": "read", ".json": "read", ".parquet": "read"}


def test_smoke_catalogs_every_item_but_selects_one_file_per_group(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    dataset_root = raw_root / "camara" / "dataset"
    dataset_root.mkdir(parents=True)
    for name in ["a.jsonl", "b.jsonl"]:
        (dataset_root / name).write_text('{"record_type":"r","x":1}\n')
    (dataset_root / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (dataset_root / "notes.txt").write_text("fora do inventário estruturado")

    result = run_inventory(
        make_config(
            raw_root,
            tmp_path / "output",
            "inventory-smoke-test",
            max_files_per_group=1,
        )
    )

    manifest = result["manifest"]
    assert manifest["scope_mode"] == "smoke"
    assert manifest["scientific_gate"] == "not_evaluated"
    assert manifest["counts"]["files"] == 4
    assert manifest["counts"]["supported_structured_files"] == 3
    assert manifest["counts"]["selected_files"] == 2
    by_name = {
        Path(row["relative_path"]).name: row
        for row in result["file_rows"]
        if row["item_type"] == "file"
    }
    assert by_name["a.jsonl"]["selected_for_read"] is True
    assert by_name["b.jsonl"]["read_status"] == "not_selected_smoke"
    assert by_name["notes.txt"]["read_status"] == "unsupported_format"


def test_samples_are_deterministic_across_operation_ids(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    path = raw_root / "camara" / "dataset" / "values.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            json.dumps({"record_type": "r", "value": value}) for value in range(20)
        )
        + "\n",
        encoding="utf-8",
    )

    first = run_inventory(
        make_config(raw_root, tmp_path / "output", "inventory-sample-a")
    )
    second = run_inventory(
        make_config(raw_root, tmp_path / "output", "inventory-sample-b")
    )

    assert first["sample_rows"] == second["sample_rows"]
    assert first["paths"]["samples"].read_text(encoding="utf-8") == second["paths"][
        "samples"
    ].read_text(encoding="utf-8")


def test_high_cardinality_switches_to_kmv_estimate(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    path = raw_root / "camara" / "dataset" / "values.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            json.dumps({"record_type": "r", "value": value}) for value in range(200)
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_inventory(
        make_config(
            raw_root,
            tmp_path / "output",
            "inventory-cardinality-test",
            cardinality_exact_limit=20,
            cardinality_kmv_size=16,
        )
    )

    value_field = next(
        row for row in result["field_rows"] if row["field_path"] == "$.value"
    )
    assert value_field["cardinality_method"] == "kmv_scalar_estimate"
    assert value_field["cardinality"] > 0
    assert not any(row["field_path"] == "$.value" for row in result["value_rows"])


def test_empty_invalid_and_unsupported_files_remain_auditable(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    dataset_root = raw_root / "senado" / "dataset"
    dataset_root.mkdir(parents=True)
    (dataset_root / "empty.jsonl").write_text("", encoding="utf-8")
    (dataset_root / "broken.json").write_text("{broken", encoding="utf-8")
    (dataset_root / "media.bin").write_bytes(b"\x00\x01")

    result = run_inventory(
        make_config(raw_root, tmp_path / "output", "inventory-errors-test")
    )

    by_name = {
        Path(row["relative_path"]).name: row
        for row in result["file_rows"]
        if row["item_type"] == "file"
    }
    assert by_name["empty.jsonl"]["read_status"] == "empty"
    assert by_name["broken.json"]["read_status"] == "read_error"
    assert by_name["media.bin"]["read_status"] == "unsupported_format"
    issue_types = {issue["issue_type"] for issue in result["issues"]}
    assert {"empty_file", "file_read_error"}.issubset(issue_types)


def test_non_linear_json_respects_memory_limit(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    path = raw_root / "senado" / "dataset" / "large.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"value": "x" * 100}), encoding="utf-8")

    result = run_inventory(
        make_config(
            raw_root,
            tmp_path / "output",
            "inventory-json-limit",
            max_json_bytes=32,
        )
    )

    file_row = next(
        row
        for row in result["file_rows"]
        if row["relative_path"].endswith("large.json")
    )
    assert file_row["read_status"] == "read_error"
    assert "limite de memória" in file_row["error"]


def test_output_inside_raw_or_mounted_drive_is_rejected(tmp_path: Path) -> None:
    raw_root = (
        tmp_path / "content" / "drive" / "MyDrive" / "falando_nela" / "data" / "raw"
    )
    raw_root.mkdir(parents=True)

    with pytest.raises(ValueError, match="dentro da raiz raw"):
        run_inventory(
            make_config(
                raw_root,
                raw_root / "output",
                "inventory-invalid-raw",
            )
        )
    with pytest.raises(ValueError, match="dentro do Drive"):
        run_inventory(
            make_config(
                raw_root,
                tmp_path / "content" / "drive" / "MyDrive" / "output",
                "inventory-invalid-drive",
            )
        )


def test_invalid_operation_id_and_existing_output_are_rejected(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()

    with pytest.raises(ValueError, match="operation_id"):
        run_inventory(
            make_config(
                raw_root,
                tmp_path / "output",
                "../invalido",
            )
        )

    output_base = tmp_path / "output"
    (output_base / "inventory-existing").mkdir(parents=True)
    with pytest.raises(FileExistsError, match="não será sobrescrito"):
        run_inventory(
            make_config(
                raw_root,
                output_base,
                "inventory-existing",
            )
        )


def test_tree_change_produces_failure_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_root = tmp_path / "raw"
    path = raw_root / "camara" / "dataset" / "records.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{"record_type":"r","x":1}\n', encoding="utf-8")
    real_fingerprint = inventario_metadados_raw.structural_fingerprint
    calls = 0

    def changing_fingerprint(root: Path) -> str:
        nonlocal calls
        calls += 1
        value = real_fingerprint(root)
        return value if calls == 1 else "different"

    monkeypatch.setattr(
        inventario_metadados_raw,
        "structural_fingerprint",
        changing_fingerprint,
    )
    config = make_config(
        raw_root,
        tmp_path / "output",
        "inventory-changing-tree",
    )

    with pytest.raises(RuntimeError, match="árvore raw mudou"):
        run_inventory(config)

    manifest = json.loads(
        (config.operation_root / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["execution_status"] == "failed"
    assert manifest["scientific_gate"] == "not_evaluated"
    assert manifest["errors"]


def test_field_csv_reconciles_presence_equation(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    path = raw_root / "camara" / "dataset" / "records.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"record_type":"r","x":null}\n'
        '{"record_type":"r","x":""}\n'
        '{"record_type":"r","x":"ok"}\n'
        '{"record_type":"r"}\n',
        encoding="utf-8",
    )
    result = run_inventory(
        make_config(raw_root, tmp_path / "output", "inventory-equation-test")
    )

    with result["paths"]["fields"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    x = next(row for row in rows if row["field_path"] == "$.x")
    assert int(x["records_universe"]) == (
        int(x["field_absent"])
        + int(x["present_null"])
        + int(x["present_empty"])
        + int(x["present_filled"])
    )


def make_config(
    raw_root: Path,
    output_base: Path,
    operation_id: str,
    **overrides: object,
) -> InventoryConfig:
    values: dict[str, object] = {
        "raw_root": raw_root,
        "output_base": output_base,
        "operation_id": operation_id,
        "code_commit": COMMIT,
        "low_cardinality_limit": 10,
        "sample_size": 3,
        "max_copy_length": 80,
        "cardinality_exact_limit": 50,
        "cardinality_kmv_size": 16,
        "progress_every_files": 0,
    }
    values.update(overrides)
    return InventoryConfig(**values)  # type: ignore[arg-type]


def tree_signature(root: Path) -> list[tuple[str, int, int]]:
    signature: list[tuple[str, int, int]] = []
    for path in sorted(root.rglob("*")):
        stat = path.stat()
        signature.append(
            (
                path.relative_to(root).as_posix(),
                stat.st_size if path.is_file() else 0,
                stat.st_mtime_ns,
            )
        )
    return signature
