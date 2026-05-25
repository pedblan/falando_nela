from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from processamento.normalizacao import DATASET_VERSION, PROCESSED_FIELDS
from processamento.samples import resolve_sample_paths, write_sample_zips


def test_resolve_sample_paths_defaults_to_colab_processed_downloads() -> None:
    args = _args(profile="colab", run_id="samples-run")

    input_root, output_root, run_id = resolve_sample_paths(
        args,
        env={"FALANDO_NELA_DATA_ROOT": "/content/drive/MyDrive/falando_nela/data"},
    )

    assert input_root == Path("/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1")
    assert output_root == Path("/content/drive/MyDrive/falando_nela/data/processed/downloads/samples-run")
    assert run_id == "samples-run"


def test_write_sample_zips_stratifies_by_base_document_type_and_year(tmp_path: Path) -> None:
    input_root = tmp_path / "processed" / "textos_parlamentares" / "v1"
    output_root = tmp_path / "processed" / "downloads" / "samples-run"
    records = [
        _processed_row("camara", "plenario_discursos", "discurso", "2025", "01", f"camara-2025-{index}")
        for index in range(10)
    ]
    records.extend(
        _processed_row("camara", "plenario_discursos", "discurso", "2026", "02", f"camara-2026-{index}")
        for index in range(2)
    )
    records.extend(
        _processed_row("senado", "ccj_notas", "notas_taquigraficas", "2026", "03", f"senado-2026-{index}")
        for index in range(3)
    )
    _write_jsonl(input_root / "ano=2026" / "mes=03" / "rows.jsonl", records)

    manifest = write_sample_zips(
        input_root=input_root,
        output_root=output_root,
        run_id="samples-run",
        sample_rate=0.2,
        min_per_group=1,
        overwrite=True,
    )

    assert manifest["sample_records"] == 4
    assert manifest["output_record_counts"] == {
        "camara__plenario_discursos__discurso": 3,
        "senado__ccj_notas__notas_taquigraficas": 1,
    }
    camara_zip = output_root / "camara__plenario_discursos__discurso.zip"
    senado_zip = output_root / "senado__ccj_notas__notas_taquigraficas.zip"
    assert camara_zip.exists()
    assert senado_zip.exists()

    camara_records = _read_zip_jsonl_records(camara_zip)
    assert _count_by(camara_records, "ano") == {"2025": 2, "2026": 1}
    assert all(list(record) == PROCESSED_FIELDS for record in camara_records)
    assert all(record["dataset_version"] == DATASET_VERSION for record in camara_records)


def test_write_sample_zips_includes_matching_parquet_when_requested(tmp_path: Path) -> None:
    input_root = tmp_path / "processed" / "textos_parlamentares" / "v1"
    output_root = tmp_path / "processed" / "downloads" / "samples-run"
    _write_jsonl(
        input_root / "ano=2026" / "mes=05" / "rows.jsonl",
        [_processed_row("camara", "plenario_discursos", "discurso", "2026", "05", "texto-1")],
    )
    parquet_path = input_root / "parquet" / "camara__plenario_discursos.parquet"
    parquet_path.parent.mkdir(parents=True)
    parquet_path.write_bytes(b"parquet bytes")

    write_sample_zips(
        input_root=input_root,
        output_root=output_root,
        run_id="samples-run",
        include_parquet=True,
        overwrite=True,
    )

    zip_path = output_root / "camara__plenario_discursos__discurso.zip"
    with zipfile.ZipFile(zip_path) as archive:
        assert "parquet/camara__plenario_discursos.parquet" in archive.namelist()
        assert archive.read("parquet/camara__plenario_discursos.parquet") == b"parquet bytes"


def test_write_sample_zips_refuses_to_overwrite_existing_outputs(tmp_path: Path) -> None:
    input_root = tmp_path / "processed" / "textos_parlamentares" / "v1"
    output_root = tmp_path / "processed" / "downloads" / "samples-run"
    _write_jsonl(
        input_root / "ano=2026" / "mes=05" / "rows.jsonl",
        [_processed_row("camara", "plenario_discursos", "discurso", "2026", "05", "texto-1")],
    )
    write_sample_zips(input_root=input_root, output_root=output_root, run_id="samples-run")

    try:
        write_sample_zips(input_root=input_root, output_root=output_root, run_id="samples-run")
    except FileExistsError as exc:
        assert "use --overwrite" in str(exc)
    else:
        raise AssertionError("Expected FileExistsError")


def _processed_row(
    source: str,
    dataset: str,
    documento_tipo: str,
    ano: str,
    mes: str,
    texto_id: str,
) -> dict[str, object]:
    row = {field: None for field in PROCESSED_FIELDS}
    row.update(
        {
            "texto_id": texto_id,
            "dataset_version": DATASET_VERSION,
            "source": source,
            "dataset": dataset,
            "casa": "Casa",
            "ambito": "ambito",
            "documento_tipo": documento_tipo,
            "unidade_analitica": "texto",
            "data": f"{ano}-{mes}-01",
            "ano": ano,
            "mes": mes,
            "texto": f"Texto {texto_id}",
            "texto_tamanho": len(texto_id),
            "raw_run_id": "raw-run",
            "raw_source_id": texto_id,
            "raw_checksum": texto_id,
            "raw_path": "raw/path.jsonl",
        }
    )
    return row


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _read_zip_jsonl_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".jsonl"):
                continue
            for line in archive.read(name).decode("utf-8").splitlines():
                records.append(json.loads(line))
    return records


def _count_by(records: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record[field])
        counts[value] = counts.get(value, 0) + 1
    return counts


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "profile": None,
        "data_root": None,
        "input_root": None,
        "output_root": None,
        "run_id": None,
        "sample_rate": 0.01,
        "min_per_group": 1,
        "include_parquet": False,
        "overwrite": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)
