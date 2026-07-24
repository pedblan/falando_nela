from __future__ import annotations

import ast
import json
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    ROOT
    / "notebooks"
    / "dados"
    / "02_snapshot_discursos_v2_smoke_colab.ipynb"
)
GENERATOR = (
    ROOT / "scripts" / "generate_snapshot_v2_smoke_colab_notebook.py"
)


def test_notebook_is_generated_valid_and_all_code_cells_compile() -> None:
    namespace: dict[str, object] = {
        "__file__": str(GENERATOR),
        "__name__": "not_main",
    }
    exec(
        compile(GENERATOR.read_text(encoding="utf-8"), str(GENERATOR), "exec"),
        namespace,
    )
    assert NOTEBOOK.read_text(encoding="utf-8") == namespace["render"]()

    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    for index, cell in enumerate(notebook.cells, start=1):
        if cell.cell_type == "code":
            ast.parse(cell.source, filename=f"{NOTEBOOK.name}::cell-{index}")


def test_notebook_has_exact_scope_and_two_explicit_identifiers() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    ]
    source = "\n".join(code_cells)

    assert "drive.mount" in code_cells[0]
    assert "MONTAR_DRIVE = False" in code_cells[0]
    assert "EXECUTAR_SMOKE = False" in source
    assert 'CONFIRM_OPERATION_ID = ""' in source
    assert 'CONFIRM_SNAPSHOT_ID = ""' in source
    assert "CONFIRM_OPERATION_ID == OPERATION_ID" in source
    assert "CONFIRM_SNAPSHOT_ID == SNAPSHOT_ID" in source
    assert "ROWS_PER_BASE = 20" in source
    assert 'PERIOD_START.isoformat() == "2010-01-01"' in source
    assert 'PERIOD_END.isoformat() == "2026-07-13"' in source
    assert '"camara__plenario_discursos.parquet"' in source
    assert '"senado__plenario_discursos.parquet"' in source
    assert '"senado__congresso_discursos.parquet"' in source
    assert 'Path("/content/falando_nela_snapshot_v2_smoke")' in source
    assert "write_snapshot_v2_smoke(" in source
    assert "OpenAI" in NOTEBOOK.read_text(encoding="utf-8")


def test_notebook_cell_roles_follow_the_controlled_flow() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    roles = [
        cell.metadata.get("falando_nela", {}).get("role")
        for cell in notebook.cells
        if cell.cell_type == "code"
    ]

    assert roles == [
        "mount_drive_gate",
        "prepare_repository",
        "configure_smoke_scope",
        "authorize_smoke",
        "preflight_gate",
        "run_smoke",
        "review_report",
        "inspect_sample",
        "final_summary",
    ]


def test_notebook_runs_locally_with_smoke_disabled(capsys) -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    namespace: dict[str, object] = {"__name__": "__notebook_test__"}

    for cell in notebook.cells:
        if cell.cell_type == "code":
            exec(compile(cell.source, NOTEBOOK.name, "exec"), namespace)

    output = capsys.readouterr().out
    assert "Gate fechado: nenhum registro Parquet será transformado." in output
    assert "Execução protegida. Nenhuma amostra foi criada." in output
    assert "execution_status: not_started" in output
    assert namespace["result"] is None
