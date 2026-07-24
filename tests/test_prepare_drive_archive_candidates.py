from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.prepare_drive_archive_candidates import (
    build_candidates,
    classify_catalog_row,
    write_plan,
)


def test_classification_protects_raw_and_reference() -> None:
    assert classify_catalog_row(
        {"relative_path": "raw/senado/texto.json", "layer": "raw"}
    ) == ("preserve", "dado bruto protegido")
    assert classify_catalog_row(
        {"relative_path": "reference/tabela.csv", "layer": "unknown"}
    ) == ("preserve", "referencia preservada ate revisao especifica")


def test_classification_separates_derivatives_and_ambiguous_operations() -> None:
    assert classify_catalog_row(
        {"relative_path": "processed/textos/v1/base.parquet", "layer": "processed"}
    )[0] == "archive_candidate"
    assert classify_catalog_row(
        {"relative_path": "analises/rodada/resultado.csv", "layer": "analysis"}
    )[0] == "archive_candidate"
    assert classify_catalog_row(
        {"relative_path": "operations/ciclo/manifest.json", "layer": "operational"}
    )[0] == "manual_review"


def test_build_candidates_uses_only_files_and_writes_outside_drive(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalogo_dados.csv"
    with catalog.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "relative_path",
                "item_type",
                "layer",
                "item_class",
                "size_bytes",
            ),
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "relative_path": "raw/senado",
                    "item_type": "directory",
                    "layer": "raw",
                },
                {
                    "relative_path": "raw/senado/a.json",
                    "item_type": "file",
                    "layer": "raw",
                    "item_class": "dataset",
                    "size_bytes": "12",
                },
                {
                    "relative_path": "processed/base.parquet",
                    "item_type": "file",
                    "layer": "processed",
                    "item_class": "dataset",
                    "size_bytes": "34",
                },
            ]
        )

    data_root = tmp_path / "drive_data"
    rows = build_candidates(catalog, data_root=data_root)
    assert [row["decision"] for row in rows] == [
        "archive_candidate",
        "preserve",
    ]

    output = tmp_path / "plan" / "candidatos.csv"
    summary = write_plan(rows, output_csv=output, data_root=data_root)
    assert output.exists()
    assert summary.exists()
    assert "Nenhum arquivo do Drive foi movido." in summary.read_text(
        encoding="utf-8"
    )

    with pytest.raises(ValueError, match="fora da raiz"):
        write_plan(
            rows,
            output_csv=data_root / "candidatos.csv",
            data_root=data_root,
        )
