from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import duckdb
import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    ROOT
    / "notebooks"
    / "coleta"
    / "11_auditoria_transcricoes_e_amostras_plenario_colab.ipynb"
)
GENERATOR_PATH = ROOT / "scripts" / "generate_video_transcription_audit_colab_notebook.py"


def test_video_transcription_audit_notebook_is_valid_and_guarded() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    assert "drive.mount" in code_cells[0]
    for index, source in enumerate(code_cells):
        ast.parse(source, filename=f"{NOTEBOOK_PATH.name}:{index}")

    combined = "\n".join(code_cells)
    assert 'REPO_REF = "main"' in combined
    assert 'TARGET_YEARS = (2010, 2015, 2016)' in combined
    assert "RANDOM_SEED = 20260716" in combined
    assert "importlib.reload(transcricoes_audiovisuais)" in combined
    assert '"INVENTORY_CODE_VERSION", 0' in combined
    assert "audit_camara_transcription_coverage" in combined
    assert "unique_pending_media_transcription" in combined
    assert "recovered_legacy_texts.parquet" in combined
    assert "legacy_matches_manual_review.parquet" in combined
    assert "legacy_match_conflicts.parquet" in combined
    assert "not_found_by_year" in combined
    assert "multiple_text_variants" in combined
    assert "shared_legacy_row" in combined
    assert "historical_full_text_samples.parquet" in combined
    assert "historical_full_text_samples.html" in combined
    assert "prioridade_diario" in combined
    assert "metodo_obtencao" in combined
    assert "white-space:pre-wrap" in combined
    assert "sha256_file" in combined
    assert "provenance.json" in combined
    assert "GRAVAR_AUDITORIA = False" in combined
    assert 'CONFIRM_AUDIT_ID = ""' in combined
    assert "assert not AUDIT_DIR.exists()" in combined
    assert '"canonical_outputs_untouched": True' in combined
    assert "faster-whisper" not in combined
    assert "yt-dlp" not in combined
    assert "ffmpeg" not in combined


def test_video_transcription_audit_notebook_is_synchronized() -> None:
    subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_video_transcription_audit_has_expected_cell_roles() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    roles = {
        cell.metadata.get("falando_nela", {}).get("role")
        for cell in notebook.cells
        if cell.cell_type == "code"
    }
    assert {
        "mount_drive",
        "prepare_repository",
        "configure_audit",
        "load_operational_outputs",
        "audit_accepted_recoveries",
        "classify_conflict_causes",
        "audit_manual_review",
        "summarize_not_found_by_year",
        "audit_camara_media_text_coverage",
        "sample_historical_full_texts",
        "validate_and_export_audit",
    }.issubset(roles)


def _role_source(role: str) -> str:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    return next(
        cell.source
        for cell in notebook.cells
        if cell.metadata.get("falando_nela", {}).get("role") == role
    )


def test_historical_sample_cell_covers_all_arenas_and_prioritizes_diary(
    tmp_path: Path,
) -> None:
    parquet_root = tmp_path / "processed" / "textos_parlamentares" / "v1" / "parquet"
    parquet_root.mkdir(parents=True)
    paths = {
        "camara": parquet_root / "camara__plenario_discursos.parquet",
        "senado": parquet_root / "senado__plenario_discursos.parquet",
        "congresso": parquet_root / "senado__congresso_discursos.parquet",
    }
    for arena, path in paths.items():
        rows = []
        for year in (2010, 2015, 2016):
            for index in range(4):
                is_diary = arena == "congresso" and year == 2010 and index == 0
                rows.append(
                    {
                        "ano": year,
                        "texto_id": f"{arena}:{year}:{index}",
                        "casa": arena,
                        "data": f"{year}-03-{index + 1:02d}",
                        "parlamentar_nome": f"Pessoa {index}",
                        "tipo_discurso": "Discurso",
                        "titulo": "Título",
                        "metodo_obtencao": (
                            "diario-congresso-oficial-por-codigo-v1"
                            if is_diary
                            else "api_texto_integral"
                        ),
                        "raw_run_id": "run-diario" if is_diary else "run-api",
                        "raw_source_id": f"source:{arena}:{year}:{index}",
                        "raw_path": f"raw/{arena}/{year}/{index}.jsonl",
                        "url_texto": "https://example.test/texto",
                        "fontes": "{}",
                        "texto": f"CABEÇALHO {arena} {year} {index}\nTexto integral sem truncamento.",
                        "texto_tamanho": 60,
                    }
                )
        pd.DataFrame(rows).to_parquet(path, index=False)

    namespace = {
        "Path": Path,
        "DATA_ROOT": tmp_path,
        "TARGET_YEARS": (2010, 2015, 2016),
        "RANDOM_SEED": 20260716,
        "GENERAL_SAMPLES_PER_ARENA_YEAR": 2,
        "DIARY_SAMPLES_PER_ARENA_YEAR": 3,
        "duckdb": duckdb,
        "pd": pd,
        "display": lambda *_: None,
        "HTML": lambda value: value,
        "quote_literal": lambda value: "'" + str(value).replace("'", "''") + "'",
        "text_cards": lambda frame, **_: "\n".join(frame["texto"].astype(str)),
    }
    exec(
        compile(_role_source("sample_historical_full_texts"), "<historical-samples>", "exec"),
        namespace,
    )

    inventory = namespace["historical_inventory"]
    samples = namespace["historical_samples"]
    assert set(inventory[["arena", "year"]].itertuples(index=False, name=None)) == {
        (arena, year) for arena in paths for year in (2010, 2015, 2016)
    }
    assert set(samples[["arena", "year"]].itertuples(index=False, name=None)) == {
        (arena, year) for arena in paths for year in (2010, 2015, 2016)
    }
    diary = samples.loc[samples["amostra_tipo"].eq("prioridade_diario")]
    assert diary["texto_id"].tolist() == ["congresso:2010:0"]
    assert "CABEÇALHO congresso 2010 0" in namespace["historical_cards_html"]


def test_conflict_cell_distinguishes_text_variants_and_shared_rows() -> None:
    conflicts = pd.DataFrame(
        [
            {
                "candidate_id": "c1",
                "date": "2020-01-01",
                "legacy_text_sha256": "text-a",
                "legacy_row_fingerprint": "row-a",
                "match_method": "exact_speech_id",
                "legacy_text": "Texto A",
            },
            {
                "candidate_id": "c1",
                "date": "2020-01-01",
                "legacy_text_sha256": "text-b",
                "legacy_row_fingerprint": "row-b",
                "match_method": "exact_speech_id",
                "legacy_text": "Texto B",
            },
            {
                "candidate_id": "c2",
                "date": "2020-01-02",
                "legacy_text_sha256": "text-c",
                "legacy_row_fingerprint": "row-shared",
                "match_method": "exact_video_url",
                "legacy_text": "Texto compartilhado",
            },
            {
                "candidate_id": "c3",
                "date": "2020-01-03",
                "legacy_text_sha256": "text-c",
                "legacy_row_fingerprint": "row-shared",
                "match_method": "exact_video_url",
                "legacy_text": "Texto compartilhado",
            },
        ]
    )
    namespace = {
        "pd": pd,
        "conflicts": conflicts,
        "stable_sample": lambda frame, *_args, **_kwargs: frame,
        "RANDOM_SEED": 20260716,
        "display": lambda *_: None,
        "HTML": lambda value: value,
        "text_cards": lambda *_args, **_kwargs: "",
    }
    exec(
        compile(_role_source("classify_conflict_causes"), "<conflict-causes>", "exec"),
        namespace,
    )

    causes = namespace["conflict_causes"].set_index("candidate_id")["conflict_cause"]
    assert causes["c1"] == "multiple_text_variants"
    assert causes["c2"] == "shared_legacy_row"
    assert causes["c3"] == "shared_legacy_row"
