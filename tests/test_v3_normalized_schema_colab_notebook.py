from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "dados_v3" / "02_schema_normalizado_colab.ipynb"


def test_notebook_is_valid_gated_and_code_cells_compile() -> None:
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
    assert "VALIDAR_G01 = False" in combined
    assert "PREPARAR_EVIDENCIAS = False" in combined
    assert "GERAR_TEMPLATE_REVISAO = False" in combined
    assert "APROVAR_PREVIEWS = False" in combined
    assert "EXECUTAR_PILOTO_GPT = False" in combined
    assert "PILOT_PACKET_IDS = []" in combined
    assert "AVALIAR_AB = False" in combined
    assert 'CONFIRMAR_INVENTORY_OPERATION_ID = ""' in combined
    assert 'CONFIRMAR_SCHEMA_OPERATION_ID = ""' in combined
    assert 'CONFIRMAR_PILOTO_OPERATION_ID = ""' in combined
    assert "APPROVED_INVENTORY_MANIFEST_SHA256" in combined
    assert '"auditoria/pipeline_dados_v3/g01"' in combined
    assert (
        "EXPECTED_INVENTORY_MANIFEST_SHA256 = (\n"
        "    APPROVED_INVENTORY_MANIFEST_SHA256\n"
        ")"
    ) in combined
    assert "prepare_schema_evidence" in combined
    assert 'model="gpt-5.6"' in combined
    assert 'reasoning_effort="medium"' in combined
    assert 'userdata.get("OPENAI_API_KEY")' in combined
    assert "print(api_key)" not in combined
    assert "normalized_records" not in combined

    mount_index = next(
        index
        for index, source in enumerate(code_cells)
        if "drive.mount" in source
    )
    setup_index = next(
        index
        for index, source in enumerate(code_cells)
        if '"git",\n                "clone"' in source
    )
    assert mount_index < setup_index
