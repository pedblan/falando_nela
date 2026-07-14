from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    ROOT
    / "notebooks"
    / "coleta"
    / "07_auditoria_cobertura_discursos_senadores_2010_colab.ipynb"
)
GENERATOR_PATH = ROOT / "scripts" / "generate_senator_speech_audit_colab_notebook.py"


def test_senator_speech_audit_notebook_is_valid_guarded_and_id_based() -> None:
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
    assert 'HOUSES = ("SF", "CN")' in combined
    assert "RODAR_AUDITORIA = False" in combined
    assert 'CONFIRM_AUDIT_ID = ""' in combined
    assert "coleta.senado.auditoria_discursos_historicos" in combined
    assert '"--data-root"' in combined
    assert '"--resume"' in combined
    assert '"--strict"' in combined
    assert "senator_endpoint_missing_ids.jsonl" in combined
    assert "raw_ids_not_in_senator_endpoint" in combined
    assert "--require-complete" not in combined


def test_senator_speech_audit_notebook_is_synchronized_with_generator() -> None:
    subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        check=True,
    )
