from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "dados_v3" / "01_inventario_metadados_raw_colab.ipynb"


def test_notebook_is_valid_and_code_cells_compile() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    for source in code_cells:
        ast.parse(source)
    combined = "\n".join(code_cells)

    assert "MONTAR_DRIVE = False" in combined
    assert "EXECUTAR_SMOKE = False" in combined
    assert 'CONFIRMAR_SMOKE_OPERATION_ID = ""' in combined
    assert "max_files_per_group=SMOKE_FILES_PER_GROUP" in combined
    assert "EXECUTAR_INVENTARIO_COMPLETO = False" in combined
    assert 'SMOKE_REVISADO_OPERATION_ID = ""' in combined
    assert 'CONFIRMAR_FULL_OPERATION_ID = ""' in combined
    assert "max_files_per_group=None" in combined
    assert 'children == ["raw"]' in combined
    assert "run_inventory" in combined
    assert "OPENAI_API_KEY" not in combined
