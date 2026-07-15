from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    ROOT
    / "notebooks"
    / "processamento"
    / "07_derivados_backfill_discursos_senadores_por_codigo_colab.ipynb"
)
GENERATOR_PATH = ROOT / "scripts" / "generate_senator_speech_backfill_derivatives_colab_notebook.py"


def test_derivatives_notebook_is_valid_guarded_and_gated_by_post_audit() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    assert "drive.mount" in code_cells[0]
    for index, source in enumerate(code_cells):
        ast.parse(source, filename=f"{NOTEBOOK_PATH.name}:{index}")

    combined = "\n".join(code_cells)
    assert 'REPO_REF = "2015_2016"' in combined
    assert 'DATA_INICIO = "2010-01-01"' in combined
    assert 'DATA_FIM = "2026-07-14"' in combined
    assert "RODAR_DERIVADOS = False" in combined
    assert "RODAR_SNAPSHOT = False" in combined
    assert "VALIDAR_RESULTADOS = False" in combined
    assert 'CONFIRM_DERIVATION_ID = ""' in combined
    assert "assert_post_audit_complete" in combined
    assert "processamento.normalizacao" in combined
    assert "processamento.parquet" in combined
    assert "run_snapshot" in combined
    assert '"--overwrite"' in combined
    assert "senator_endpoint_summary.json" in combined
    assert "missing_ids" in combined
    assert "2015" in combined and "2016" in combined
    assert "coleta.senado" not in combined


def test_derivatives_notebook_is_synchronized_with_generator() -> None:
    subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        check=True,
    )
