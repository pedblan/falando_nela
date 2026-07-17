from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import nbformat
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks" / "analise"
SNAPSHOT_VALIDATION_CELL_PATH = NOTEBOOK_DIR / "celulas" / "00_validacao_snapshot.py"
EXPECTED_RUN_ID = "analise-plenario-20260717-v1"
EXPECTED = [
    "00_snapshot_discursos_plenario_colab.ipynb",
    "01_enriquecimento_genero_colab.ipynb",
    "02_descritivas_discursos_plenario_colab.ipynb",
    "03_apartes_relacionais_colab.ipynb",
    "04_nlp_leiturabilidade_morfossintaxe_colab.ipynb",
    "05_inferencia_series_temporais_colab.ipynb",
    "06_clusterizacao_discursos_colab.ipynb",
    "07_topicos_bertopic_colab.ipynb",
    "08_figuras_linguagem_gpt56_colab.ipynb",
    "09_sintese_comparativa_colab.ipynb",
]


def test_analysis_notebooks_are_valid_colab_orchestrators() -> None:
    assert sorted(path.name for path in NOTEBOOK_DIR.glob("*.ipynb")) == EXPECTED
    for filename in EXPECTED:
        path = NOTEBOOK_DIR / filename
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        assert notebook.metadata["falando_nela"]["narrative_language"] == "pt-BR"
        ids = [cell.id for cell in notebook.cells]
        assert len(ids) == len(set(ids))
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        assert "drive.mount" in code_cells[0].source
        assert "git" in code_cells[1].source and "requirements-analise.txt" in code_cells[1].source
        assert "--force-reinstall" in code_cells[1].source
        assert '"numpy==2.0.2"' in code_cells[1].source
        assert '"pandas==2.2.3"' in code_cells[1].source
        assert "ABI_CHECK" in code_cells[1].source
        source = "\n".join(cell.source for cell in code_cells)
        assert "RODAR_ETAPA = False" in source
        assert f'RUN_ID = "{EXPECTED_RUN_ID}"' in source
        assert "analise-plenario-20260713-v1" not in source
        assert "2010-02-02" in source
        assert "2026-07-13" in source
        assert "get_ipython" not in source
        for cell in code_cells:
            ast.parse(cell.source, filename=f"{filename}:{cell.id}")
        markdown_cells = [cell for cell in notebook.cells if cell.cell_type == "markdown"]
        assert markdown_cells
        markdown_ids = []
        for cell in markdown_cells:
            metadata = cell.metadata["falando_nela"]
            assert metadata["language"] == "pt-BR"
            markdown_ids.append(metadata["markdown_id"])
        assert len(markdown_ids) == len(set(markdown_ids))


def test_analysis_notebooks_match_generator() -> None:
    completed = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "scripts/generate_analysis_colab_notebooks.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_snapshot_validation_cell_is_standalone_and_synchronized() -> None:
    notebook = nbformat.read(NOTEBOOK_DIR / EXPECTED[0], as_version=4)
    validation_cell = next(
        cell
        for cell in notebook.cells
        if cell.get("metadata", {}).get("falando_nela", {}).get("role") == "validate_stage"
    )
    standalone_source = SNAPSHOT_VALIDATION_CELL_PATH.read_text(encoding="utf-8").strip()
    assert validation_cell.source == standalone_source
    assert 'globals().get("RUN_ID"' in standalone_source
    assert EXPECTED_RUN_ID in standalone_source
    assert "analise-plenario-20260713-v1" not in standalone_source
    assert 'globals().get("DATA_ROOT"' in standalone_source
    assert "SNAPSHOT_OBSERVED_ARENAS == set(SNAPSHOT_EXPECTED_ARENAS)" in standalone_source
    assert "SNAPSHOT_COVERAGE" in standalone_source
    assert "SNAPSHOT_MISSING_YEARS" in standalone_source
    assert "assert not SNAPSHOT_COMPLETE_MISSING" in standalone_source
    assert ".tail(" not in standalone_source
    ast.parse(standalone_source, filename=str(SNAPSHOT_VALIDATION_CELL_PATH))


def test_snapshot_validation_cell_runs_against_existing_artifact(tmp_path: Path) -> None:
    run_id = "snapshot-validacao-teste"
    snapshot_path = (
        tmp_path
        / "analises"
        / "discursos_plenario"
        / "v1"
        / run_id
        / "00_snapshot"
        / "discursos_plenario_snapshot.parquet"
    )
    snapshot_path.parent.mkdir(parents=True)
    rows = [
        {
            "arena": arena,
            "ano": year,
            "data_analise": f"{year}-02-02",
            "elegivel_inferencia_anual": True,
        }
        for year in range(2010, 2026)
        for arena in ("camara", "senado", "congresso")
    ]
    rows.append(
        {
            "arena": "camara",
            "ano": 2026,
            "data_analise": "2026-07-13",
            "elegivel_inferencia_anual": False,
        }
    )
    pd.DataFrame(rows).to_parquet(snapshot_path, index=False)

    displayed: list[pd.DataFrame] = []
    namespace = {
        "DATA_ROOT": tmp_path,
        "RUN_ID": run_id,
        "display": displayed.append,
    }
    source = SNAPSHOT_VALIDATION_CELL_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(SNAPSHOT_VALIDATION_CELL_PATH), "exec"), namespace)

    assert namespace["SNAPSHOT_PATH"] == snapshot_path
    assert namespace["SNAPSHOT_OBSERVED_ARENAS"] == {"camara", "senado", "congresso"}
    assert namespace["SNAPSHOT_COVERAGE"].loc[2010].tolist() == [1, 1, 1]
    assert namespace["SNAPSHOT_COVERAGE"].loc[2026].tolist() == [1, 0, 0]
    assert len(displayed) == 2


def test_snapshot_validation_cell_fails_for_missing_complete_year(tmp_path: Path) -> None:
    run_id = "snapshot-incompleto"
    snapshot_path = (
        tmp_path
        / "analises"
        / "discursos_plenario"
        / "v1"
        / run_id
        / "00_snapshot"
        / "discursos_plenario_snapshot.parquet"
    )
    snapshot_path.parent.mkdir(parents=True)
    rows = [
        {
            "arena": arena,
            "ano": year,
            "data_analise": f"{year}-02-02",
            "elegivel_inferencia_anual": True,
        }
        for year in range(2010, 2026)
        for arena in ("camara", "senado", "congresso")
        if not (arena == "congresso" and year == 2016)
    ]
    pd.DataFrame(rows).to_parquet(snapshot_path, index=False)

    namespace = {"DATA_ROOT": tmp_path, "RUN_ID": run_id, "display": lambda _: None}
    source = SNAPSHOT_VALIDATION_CELL_PATH.read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="2016"):
        exec(compile(source, str(SNAPSHOT_VALIDATION_CELL_PATH), "exec"), namespace)


def test_analysis_requirements_pin_colab_binary_stack() -> None:
    requirements = (ROOT / "requirements-analise.txt").read_text(encoding="utf-8").splitlines()
    assert "numpy==2.0.2" in requirements
    assert "pandas==2.2.3" in requirements


def test_analysis_sources_do_not_contain_removed_dependencies() -> None:
    roots = [
        ROOT / "analise" / "discursos_plenario",
        ROOT / "notebooks" / "analise",
        ROOT / "requirements-analise.txt",
    ]
    forbidden = ("perplex" + "ity", "gpt" + "2", "nilc" + "-metrix")
    for root in roots:
        paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in paths:
            if path.suffix in {".pyc", ".png"}:
                continue
            content = path.read_text(encoding="utf-8").casefold()
            assert not any(term in content for term in forbidden), path
