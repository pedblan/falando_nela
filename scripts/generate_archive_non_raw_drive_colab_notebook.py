from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "notebooks"
    / "manutencao"
    / "00_arquivar_pos_coleta_v1_colab.ipynb"
)


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        new_markdown_cell(
            """# Arquivar tudo depois da coleta raw

Este caderno move todos os filhos de
`/content/drive/MyDrive/falando_nela/data` exceto `raw/`.

O destino fica fora de `data/`:

`/content/drive/MyDrive/falando_nela/arquivo/data_pos_coleta_v1_arquivado_20260724`

O caderno não apaga arquivos. Primeiro gera um plano; a movimentação exige que
o `operation_id` seja copiado literalmente na célula de confirmação."""
        ),
        new_code_cell(
            """from google.colab import drive

drive.mount("/content/drive")
"""
        ),
        new_code_cell(
            """import subprocess
import sys
from pathlib import Path

REPO_DIR = Path("/content/falando_nela")
REPO_URL = "https://github.com/pedblan/falando_nela.git"
REPO_REF = "codex/arquivar-pipeline-pos-coleta-v1"

if not (REPO_DIR / ".git").exists():
    subprocess.run(
        ["git", "clone", "--branch", REPO_REF, REPO_URL, str(REPO_DIR)],
        check=True,
    )
else:
    subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "origin"], check=True)
    subprocess.run(
        ["git", "-C", str(REPO_DIR), "checkout", REPO_REF],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(REPO_DIR), "pull", "--ff-only"],
        check=True,
    )

sys.path.insert(0, str(REPO_DIR))
"""
        ),
        new_code_cell(
            """from pathlib import Path

from scripts.archive_non_raw_drive import (
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_DATA_ROOT,
    DEFAULT_OUTPUT_BASE,
    build_plan,
    load_plan,
    write_plan,
)

OPERATION_ID = "archive-non-raw-20260724"
DATA_ROOT = DEFAULT_DATA_ROOT
ARCHIVE_ROOT = DEFAULT_ARCHIVE_ROOT
OPERATION_ROOT = DEFAULT_OUTPUT_BASE / OPERATION_ID

plan_json = OPERATION_ROOT / "plan.json"
plan_csv = OPERATION_ROOT / "plan.csv"
if plan_json.exists():
    plan = load_plan(OPERATION_ROOT)
    print("Plano existente reutilizado.")
else:
    plan = build_plan(
        data_root=DATA_ROOT,
        archive_root=ARCHIVE_ROOT,
        operation_id=OPERATION_ID,
    )
    plan_json, plan_csv = write_plan(plan, OPERATION_ROOT)

print("Plano:", plan_json)
print("Tabela:", plan_csv)
print("Raw protegido:", plan["protected_path"])
print("Fingerprint raw:", plan["protected_raw_fingerprint"])
print("Itens candidatos:", plan["candidate_count"])
"""
        ),
        new_code_cell(
            """import pandas as pd

display(pd.read_csv(plan_csv))
print("Drive alterado: não")
"""
        ),
        new_markdown_cell(
            """## Confirmação da movimentação

Confira a tabela acima. Ela deve listar todos os filhos de `data/` menos
`raw`. Como não há coletores em execução e o critério já foi aprovado, copie
o valor de `OPERATION_ID` para `CONFIRM_OPERATION_ID` e execute a célula uma
vez."""
        ),
        new_code_cell(
            """from scripts.archive_non_raw_drive import execute_plan

CONFIRM_OPERATION_ID = ""

if CONFIRM_OPERATION_ID != OPERATION_ID:
    raise RuntimeError(
        "Movimentação bloqueada. Copie OPERATION_ID literalmente para "
        "CONFIRM_OPERATION_ID."
    )

execution = execute_plan(
    operation_root=OPERATION_ROOT,
    confirmation=CONFIRM_OPERATION_ID,
)
print("Estado:", execution["status"])
print("Itens movidos:", execution["moved_items"])
print("Conteúdo restante em data:", execution["data_root_children"])
print("Arquivo:", execution["archive_root"])
"""
        ),
        new_code_cell(
            """from scripts.archive_non_raw_drive import load_plan, verify_raw

final_plan = load_plan(OPERATION_ROOT)
verify_raw(final_plan)

remaining = sorted(path.name for path in DATA_ROOT.iterdir())
archived = sorted(path.name for path in ARCHIVE_ROOT.iterdir())

print("Filhos atuais de data:", remaining)
print("Itens no arquivo:", archived)
assert remaining == ["raw"]
assert OPERATION_ID + ".manifest.json" in archived
print("Validação final: aprovada")
"""
        ),
    ]
    return new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
            "colab": {"name": OUTPUT.name, "provenance": []},
        },
    )


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook()
    nbformat.validate(notebook)
    nbformat.write(notebook, OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
