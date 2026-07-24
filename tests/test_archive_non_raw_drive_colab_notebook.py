from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    ROOT
    / "notebooks"
    / "manutencao"
    / "00_arquivar_pos_coleta_v1_colab.ipynb"
)


def test_notebook_is_valid_and_code_cells_compile() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    combined = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    for cell in notebook["cells"]:
        if cell.get("cell_type") == "code":
            ast.parse("".join(cell.get("source", [])))

    assert 'drive.mount("/content/drive")' in combined
    assert 'CONFIRM_OPERATION_ID = ""' in combined
    assert "execute_plan" in combined
    assert 'assert remaining == ["raw"]' in combined
