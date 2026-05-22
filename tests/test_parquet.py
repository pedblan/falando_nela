from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pyarrow.parquet as pq

from processamento.normalizacao import DATASET_VERSION, PROCESSED_FIELDS
from processamento.parquet import resolve_parquet_paths, write_parquet_by_dataset


def test_write_parquet_by_dataset_groups_and_deduplicates_newer_first(tmp_path: Path) -> None:
    input_root = tmp_path / "processed" / "textos_parlamentares" / "v1"
    output_root = input_root / "parquet"
    manifest_path = tmp_path / "processed" / "manifests" / "run-parquet.json"
    older_path = input_root / "ano=2026" / "mes=05" / "older.jsonl"
    newer_path = input_root / "ano=2026" / "mes=05" / "newer.jsonl"
    senado_path = input_root / "ano=2026" / "mes=06" / "senado.jsonl"

    _write_jsonl(older_path, [_processed_row("camara", "plenario_discursos", "texto-1", "Texto antigo")])
    _write_jsonl(newer_path, [_processed_row("camara", "plenario_discursos", "texto-1", "Texto novo")])
    _write_jsonl(senado_path, [_processed_row("senado", "ccj_notas", "texto-2", "Nota")])
    os.utime(older_path, (1, 1))
    os.utime(newer_path, (2, 2))
    os.utime(senado_path, (3, 3))

    manifest = write_parquet_by_dataset(
        input_root=input_root,
        output_root=output_root,
        manifest_path=manifest_path,
        run_id="run-parquet",
        overwrite=True,
        batch_size=1,
    )

    camara_table = pq.read_table(output_root / "camara__plenario_discursos.parquet")
    senado_table = pq.read_table(output_root / "senado__ccj_notas.parquet")
    assert camara_table.num_rows == 1
    assert senado_table.num_rows == 1
    assert camara_table.column_names == PROCESSED_FIELDS
    assert camara_table.column("texto").to_pylist() == ["Texto novo"]
    assert camara_table.column("fontes").to_pylist() == ['{"url": "https://example.test"}']
    assert manifest["output_records"] == 2
    assert manifest["output_record_counts"] == {
        "camara/plenario_discursos": 1,
        "senado/ccj_notas": 1,
    }
    assert manifest["skipped_counts"]["duplicate_texto_id"] == 1
    assert manifest["json_serialized_fields"] == ["fontes"]


def test_write_parquet_by_dataset_skips_existing_parquet_tree_and_non_v1_rows(tmp_path: Path) -> None:
    input_root = tmp_path / "samples" / "textos_parlamentares" / "v1"
    output_root = input_root / "parquet"
    _write_jsonl(input_root / "base" / "rows.jsonl", [_processed_row("camara", "ccjc_eventos", "texto-1", "Texto")])
    _write_jsonl(output_root / "ignored.jsonl", [_processed_row("camara", "ccjc_eventos", "texto-ignored", "Ignorado")])
    _write_jsonl(
        input_root / "base" / "wrong-version.jsonl",
        [_processed_row("camara", "ccjc_eventos", "texto-v2", "Ignorado", dataset_version="v2")],
    )

    manifest = write_parquet_by_dataset(input_root=input_root, output_root=output_root, overwrite=True)

    table = pq.read_table(output_root / "camara__ccjc_eventos.parquet")
    assert table.num_rows == 1
    assert table.column("texto_id").to_pylist() == ["texto-1"]
    assert manifest["input_file_count"] == 2
    assert manifest["output_records"] == 1
    assert manifest["skipped_counts"]["dataset_version_not_v1"] == 1


def test_resolve_parquet_paths_uses_distinct_colab_and_local_sample_roots() -> None:
    sample_args = _args(profile="samples-local")
    sample_input, sample_output, sample_manifest, sample_run_id = resolve_parquet_paths(sample_args, env={})

    assert sample_input == Path("data/samples/textos_parlamentares/v1")
    assert sample_output == Path("data/samples/textos_parlamentares/v1/parquet")
    assert sample_manifest == Path("data/samples/textos_parlamentares/v1/parquet/manifest.json")
    assert sample_run_id is None

    colab_args = _args(profile="colab", run_id="processed-textos-v1-20260522")
    colab_input, colab_output, colab_manifest, colab_run_id = resolve_parquet_paths(
        colab_args,
        env={"FALANDO_NELA_DATA_ROOT": "/content/drive/MyDrive/falando_nela/data"},
    )

    assert colab_input == Path("/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1")
    assert colab_output == Path("/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet")
    assert colab_manifest == Path("/content/drive/MyDrive/falando_nela/data/processed/manifests/processed-textos-v1-20260522-parquet.json")
    assert colab_run_id == "processed-textos-v1-20260522-parquet"


def _processed_row(
    source: str,
    dataset: str,
    texto_id: str,
    texto: str,
    *,
    dataset_version: str = DATASET_VERSION,
) -> dict[str, object]:
    row = {field: None for field in PROCESSED_FIELDS}
    row.update(
        {
            "texto_id": texto_id,
            "dataset_version": dataset_version,
            "source": source,
            "dataset": dataset,
            "casa": "Casa",
            "ambito": "ambito",
            "documento_tipo": "discurso",
            "unidade_analitica": "pronunciamento",
            "data": "2026-05-22",
            "ano": "2026",
            "mes": "05",
            "texto": texto,
            "texto_tamanho": len(texto),
            "fontes": {"url": "https://example.test"},
            "raw_run_id": "raw-run",
            "raw_source_id": texto_id,
            "raw_path": "raw/path.jsonl",
        }
    )
    return row


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "profile": None,
        "data_root": None,
        "input_root": None,
        "output_root": None,
        "manifest_path": None,
        "run_id": None,
        "schema_path": None,
        "batch_size": 5000,
        "overwrite": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)
