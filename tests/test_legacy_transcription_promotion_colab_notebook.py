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
    / "12_promocao_transcricoes_legadas_plenario_colab.ipynb"
)
GENERATOR_PATH = ROOT / "scripts" / "generate_legacy_transcription_promotion_colab_notebook.py"


def test_legacy_transcription_promotion_notebook_is_valid_and_guarded() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    assert "drive.mount" in code_cells[0]
    for index, source in enumerate(code_cells):
        ast.parse(source, filename=f"{NOTEBOOK_PATH.name}:{index}")

    combined = "\n".join(code_cells)
    assert 'REPO_REF = "main"' in combined
    assert 'EXPECTED_ACCEPTED = 471' in combined
    assert 'EXPECTED_DIARY = 83' in combined
    assert 'VISUAL_REVIEW_FRACTION = 0.30' in combined
    assert 'PROMOVER_TRANSCRICOES = False' in combined
    assert 'REGERAR_DERIVADOS = False' in combined
    assert 'CONFIRM_PROMOTION_RUN_ID = ""' in combined
    assert 'CONFIRM_REBUILD_PROMOTION_RUN_ID = ""' in combined
    assert 'CONFIRM_DIARY_CLEANING_VERSION = ""' in combined
    assert "manual_excluded" in combined
    assert "conflicts_excluded" in combined
    assert "all_excluded_statuses_absent" in combined
    assert "find_existing_nonempty_texts" in combined
    assert "write_promotion_records" in combined
    assert "pre_rebuild_state.json" in combined
    assert "normalizacao_texto_diario" in combined
    assert "prior_senate_rows_untouched" in combined
    assert "congress_non_diary_untouched" in combined
    assert "unaffected_parquets_untouched" in combined
    assert "full_row_sha256" in combined
    assert "expected_congress_diary_cleaned" in combined
    assert "diary_text_matches_cleaner_exactly" in combined
    assert "validation.json" in combined
    assert "--overwrite" in combined
    assert "faster-whisper" not in combined
    assert "yt-dlp" not in combined


def test_legacy_transcription_promotion_notebook_is_synchronized() -> None:
    subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_legacy_transcription_promotion_has_expected_cell_roles() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    roles = {
        cell.metadata.get("falando_nela", {}).get("role")
        for cell in notebook.cells
        if cell.cell_type == "code"
    }
    assert {
        "mount_drive",
        "prepare_repository",
        "configure_promotion",
        "load_contracts_and_helpers",
        "reconcile_accepted_population",
        "preview_diary_cleanup",
        "preflight_and_baseline",
        "publish_reviewed_raw",
        "rebuild_current_derivatives",
        "validate_promotion_and_drift",
    }.issubset(roles)
