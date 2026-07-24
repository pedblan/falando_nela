from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from processamento.censo_snapshot_v2 import (
    CANDIDATE_BASES,
    inspect_candidate_parquets,
    write_snapshot_candidate_census,
)


COMMIT = "a" * 40


def test_census_is_read_only_and_writes_review_bundle(tmp_path: Path) -> None:
    parquet_root = tmp_path / "drive" / "processed" / "parquet"
    output_base = tmp_path / "content" / "falando_nela_snapshot_census"
    _build_fixture(parquet_root)
    before = _signature(parquet_root)

    result = write_snapshot_candidate_census(
        parquet_root=parquet_root,
        output_base=output_base,
        operation_id="snapshot-census-test-1",
        code_commit=COMMIT,
    )

    assert _signature(parquet_root) == before
    manifest = result["manifest"]
    assert manifest["execution_status"] == "succeeded"
    assert manifest["scientific_gate"] == "needs_review"
    assert manifest["snapshot_id"] is None
    assert manifest["counts"]["candidate_files"] == 3
    assert manifest["counts"]["input_records"] == 7
    assert manifest["counts"]["duplicate_id_rows"] == 1
    assert manifest["counts"]["cross_file_shared_ids"] == 1
    assert manifest["counts"]["global_distinct_ids"] == 5
    assert len(manifest["outputs"]) == 8

    operation_root = output_base / "snapshot-census-test-1"
    assert (operation_root / "relatorio.md").exists()
    assert (operation_root / "manifest.json").exists()
    assert (operation_root / "logs" / "execution.jsonl").exists()
    assert (operation_root / "artifacts" / "mapa_censo.md").exists()
    assert "Nenhum snapshot foi criado" in (
        operation_root / "relatorio.md"
    ).read_text(encoding="utf-8")
    assert "A execução não aprova D03" in (
        operation_root / "artifacts" / "mapa_censo.md"
    ).read_text(encoding="utf-8")


def test_census_reports_expected_files_years_and_categories(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)

    census = inspect_candidate_parquets(parquet_root)

    assert [row["candidate_file"] for row in census["bases"]] == [
        base.filename for base in CANDIDATE_BASES
    ]
    assert {row["year"] for row in census["years"]} == {2020, 2021, 2022}
    assert any(
        row["dimension"] == "ambito" and row["value"] == "congresso"
        for row in census["categories"]
    )
    assert census["overlaps"] == [
        {
            "left_candidate": "senado__congresso_discursos.parquet",
            "right_candidate": "senado__plenario_discursos.parquet",
            "shared_ids": 1,
        }
    ]
    assert any(
        row["issue_type"] == "duplicate_texto_id_within_base"
        and row["candidate_file"] == "camara__plenario_discursos.parquet"
        for row in census["issues"]
    )


def test_census_requires_all_three_candidates(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)
    (parquet_root / CANDIDATE_BASES[-1].filename).unlink()

    with pytest.raises(FileNotFoundError, match="Bases candidatas ausentes"):
        write_snapshot_candidate_census(
            parquet_root=parquet_root,
            output_base=tmp_path / "output",
            operation_id="snapshot-census-missing",
            code_commit=COMMIT,
        )


def test_census_refuses_output_inside_input_root(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)

    with pytest.raises(ValueError, match="não pode ficar dentro"):
        write_snapshot_candidate_census(
            parquet_root=parquet_root,
            output_base=parquet_root / "output",
            operation_id="snapshot-census-invalid-output",
            code_commit=COMMIT,
        )


def test_census_refuses_reusing_operation_id(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    output_base = tmp_path / "output"
    _build_fixture(parquet_root)
    operation_id = "snapshot-census-reuse"
    kwargs = {
        "parquet_root": parquet_root,
        "output_base": output_base,
        "operation_id": operation_id,
        "code_commit": COMMIT,
    }

    write_snapshot_candidate_census(**kwargs)
    with pytest.raises(FileExistsError, match="já possui artefatos"):
        write_snapshot_candidate_census(**kwargs)


def _build_fixture(parquet_root: Path) -> None:
    parquet_root.mkdir(parents=True, exist_ok=True)
    rows_by_file = {
        "camara__plenario_discursos.parquet": [
            _row("camara-1", "camara", "plenario_discursos", "plenario", 2020),
            _row("camara-2", "camara", "plenario_discursos", "plenario", 2021),
            _row("camara-2", "camara", "plenario_discursos", "plenario", 2021),
        ],
        "senado__plenario_discursos.parquet": [
            _row("senado-1", "senado", "plenario_discursos", "plenario", 2020),
            _row("shared", "senado", "plenario_discursos", "plenario", 2022),
        ],
        "senado__congresso_discursos.parquet": [
            _row("congresso-1", "senado", "congresso_discursos", "congresso", 2021),
            _row("shared", "senado", "congresso_discursos", "congresso", 2022),
        ],
    }
    for filename, rows in rows_by_file.items():
        pq.write_table(pa.Table.from_pylist(rows), parquet_root / filename)


def _row(
    texto_id: str,
    source: str,
    dataset: str,
    ambito: str,
    year: int,
) -> dict[str, object]:
    return {
        "texto_id": texto_id,
        "dataset_version": "v1",
        "source": source,
        "dataset": dataset,
        "ambito": ambito,
        "documento_tipo": "discurso",
        "unidade_analitica": "pronunciamento",
        "data": f"{year}-05-10",
        "ano": year,
        "texto_tamanho": 120,
        "texto_status": "disponivel",
        "parlamentar_nome": "Pessoa",
        "raw_path": f"raw/{source}/{dataset}/{texto_id}.json",
        "raw_source_id": texto_id,
    }


def _signature(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.glob("*.parquet"))
    }
