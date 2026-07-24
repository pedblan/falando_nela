from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "coleta" / "06_backfill_discursos_senado_congresso_2015_2016_colab.ipynb"
GENERATOR_PATH = ROOT / "scripts" / "generate_backfill_2015_2016_colab_notebook.py"


def test_backfill_notebook_is_valid_guarded_and_complete() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    assert "drive.mount" in code_cells[0]
    for index, source in enumerate(code_cells):
        ast.parse(source, filename=f"{NOTEBOOK_PATH.name}:{index}")

    combined = "\n".join(code_cells)
    assert 'REPO_REF = "2015_2016"' in combined
    assert '"clone", "--branch", REPO_REF, "--single-branch"' in combined
    assert 'required_module = REPO_DIR / "processamento" / "reconciliacao_discursos.py"' in combined
    for flag in (
        "RODAR_CONFIGURACAO",
        "ATIVAR_CICLO",
        "RODAR_AUDITORIA_PRE",
        "RODAR_PROBE_SENADORES",
        "RODAR_CONTROLES",
        "RODAR_SMOKES",
        "RODAR_SENADO",
        "RODAR_CONGRESSO",
        "VALIDAR_COLETAS",
        "RODAR_DERIVADOS",
        "RODAR_SNAPSHOT",
        "RODAR_RECONCILIACAO_POST",
        "ENCERRAR_CICLO",
    ):
        assert f"{flag} = False" in combined
    assert 'CONFIRM_CYCLE_ID = ""' in combined
    assert '"--discovery-strategy", "historical-official"' in combined
    assert '"--no-sample"' in combined
    assert '"--resume"' in combined
    assert "dataset_lock" in combined
    assert '"--phase", "pre"' in combined
    assert "coleta.senado.auditoria_discursos_historicos" in combined
    assert "CONTROL_MONTHS" in combined
    assert '"--sample-limit", "1"' in combined
    assert '"--phase", "post"' in combined
    assert '"--strict"' in combined
    assert "processed-textos-v1-current" in combined
    assert "parquet-textos-v1-current" in combined


def test_backfill_notebook_is_synchronized_with_generator() -> None:
    subprocess.run([str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"], cwd=ROOT, check=True)
