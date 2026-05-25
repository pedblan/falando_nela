---
name: falando-nela-colab-notebooks
description: Create, edit, or repair Google Colab and Jupyter notebooks for the Falando Nela project, especially notebooks under notebooks/coleta and notebooks/processamento. Use when Codex needs to generate .ipynb cells safely, preserve Python string literals such as "\\n", mount Google Drive before project setup, or validate notebook JSON and code-cell syntax.
---

# Falando Nela: Colab notebooks

Use this skill when creating or editing project notebooks. The main risk is corrupting Python string literals while serializing `.ipynb` JSON.

## Notebook JSON Rule

A code cell stores `cell.source`, often as a list of strings. Jupyter builds the code with:

```python
codigo_da_celula = "".join(cell["source"])
```

Keep these distinct:

- Notebook line break: the end of a `source` item, usually `\n`.
- Python newline inside a string literal: two characters, `\\n`, inside the JSON text.

Correct JSON representation:

```json
{
  "cell_type": "code",
  "source": [
    "print(\"\\nArquivo:\", path)\n"
  ]
}
```

Incorrect representation:

```json
{
  "cell_type": "code",
  "source": [
    "print(\"\n",
    "Arquivo:\", path)\n"
  ]
}
```

## Generation Rules

- Prefer `nbformat`, `json.dumps`, or another notebook writer. Do not hand-build notebook JSON by string concatenation.
- Build each cell as Python source text first, then serialize with `splitlines(keepends=True)`.
- Use raw strings for cell templates that contain Python literals like `"\n"`:

```python
cell_code = r'''print("\nArquivo:", path)
print("\nUltimas linhas do log:")
'''
source = cell_code.splitlines(keepends=True)
```

- If editing raw `source`, never split an item in the middle of a quoted Python string.
- Multi-line Python strings are fine only when the concatenated code remains valid Python.

## Falando Nela Colab Pattern

- In Colab notebooks, mount Google Drive before cloning, pulling, installing dependencies, or importing project code.
- Set `FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data` for production collection and processing notebooks.
- Use notebooks under `notebooks/coleta/` for collection and `notebooks/processamento/` for normalization, Parquet, descriptions, and sample workflows.
- Avoid `check=True` in long-running collection cells when the existing notebook pattern expects later inspection of stdout, stderr, logs, and manifests.
- Keep complete data in Drive/Colab. Local notebooks should use samples only.

## Common Risk Points

Review code cells that print separators or logs:

```python
print("\nArquivo:", path)
print("\nUltimas linhas do log:")
print("\n".join(log_path.read_text(encoding="utf-8").splitlines()[-10:]))
```

In notebook JSON, those must remain escaped as `\\n` inside the Python string literal.

## Required Validation

After changing notebooks, validate JSON and compile every code cell:

```bash
python3 - <<'PY'
import ast
import json
from pathlib import Path

for root in [Path("notebooks/coleta"), Path("notebooks/processamento")]:
    for path in root.glob("*.ipynb"):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for index, cell in enumerate(notebook.get("cells", []), start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            try:
                ast.parse(source)
            except SyntaxError as exc:
                raise SystemExit(f"{path}: cell {index}: {exc}")
print("ok")
PY
```

Also run `python3 -m json.tool <notebook.ipynb> >/tmp/notebook.json` for each notebook touched when diagnosing JSON corruption.
