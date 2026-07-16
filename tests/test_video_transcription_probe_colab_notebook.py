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
    / "10_sondagem_transcricoes_audiovisuais_plenario_colab.ipynb"
)
GENERATOR_PATH = ROOT / "scripts" / "generate_video_transcription_probe_colab_notebook.py"


def test_legacy_transcription_recovery_notebook_is_valid_and_guarded() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    nbformat.validate(notebook)
    code_cells = [cell.source for cell in notebook.cells if cell.cell_type == "code"]
    assert "drive.mount" in code_cells[0]
    for index, source in enumerate(code_cells):
        ast.parse(source, filename=f"{NOTEBOOK_PATH.name}:{index}")

    combined = "\n".join(code_cells)
    assert 'REPO_REF = "main"' in combined
    assert "scan_camara_media_candidates" in combined
    assert "scan_senado_transcription_queue" in combined
    assert "importlib.reload(transcricoes_audiovisuais)" in combined
    assert '"INVENTORY_CODE_VERSION", 0' in combined
    assert '"/content/falando_nela/"' in combined
    assert "1R5Xz3tydoPYHSjzmKM8_KDvTzQ51RFk2" in combined
    assert "252_122_904" in combined
    assert "validate_parquet_magic" in combined
    assert "exact_speech_id" in combined
    assert "exact_audio_url" in combined
    assert "exact_video_url" in combined
    assert "senate_speaker_date_event_review" in combined
    assert 'candidate_table = senate_candidates.reindex' in combined
    assert '"legacy_scope": "senado_only"' in combined
    assert "recovered_legacy_texts.parquet" in combined
    assert "legacy_match_conflicts.parquet" in combined
    assert "camara_media_download_queue.parquet" in combined
    assert "requires_media_download" in combined
    assert "operations_only" in combined
    assert "BAIXAR_PARQUET_ANTIGO = False" in combined
    assert "GRAVAR_RESULTADOS = False" in combined
    assert 'CONFIRM_PROBE_ID = ""' in combined
    assert "faster-whisper" not in combined
    assert "yt-dlp" not in combined
    assert "ffmpeg" not in combined


def test_legacy_transcription_recovery_notebook_is_synchronized() -> None:
    subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR_PATH), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_legacy_match_cell_excludes_camara_even_when_legacy_id_matches(tmp_path: Path) -> None:
    old_path = tmp_path / "DiscursosTodos.parquet"
    pd.DataFrame(
        [
            {
                "Casa": "Senado Federal",
                "CodigoPronunciamento": "10",
                "TextoIntegral": "Texto Senado",
                "CodigoParlamentar": "1",
                "DataPronunciamento": "2024-01-01T10:00:00",
                "evento_id": "100",
                "tipoDiscurso": "Fala",
                "urlVideo": "https://old/senado.mp4",
            },
            {
                "Casa": "Câmara dos Deputados",
                "CodigoPronunciamento": "20",
                "TextoIntegral": "Texto Câmara",
                "CodigoParlamentar": "2",
                "DataPronunciamento": "2024-02-02T11:00:00",
                "evento_id": "200",
                "tipoDiscurso": "Ordem do Dia",
                "urlVideo": None,
            },
        ]
    ).to_parquet(old_path, index=False)
    current = pd.DataFrame(
        [
            {
                "candidate_id": "s10",
                "house": "senado",
                "speech_id": "10",
                "speaker_id": "1",
                "event_id": "100",
                "date": "2024-01-01T10:00:00",
                "media_url": "https://new/senado.mp4",
                "tipo_discurso": "Fala",
                "raw_path": "senado.jsonl",
                "raw_source_id": "SF:pronunciamento:10",
                "year": 2024,
            },
            {
                "candidate_id": "c20",
                "house": "camara",
                "speech_id": "20",
                "speaker_id": "2",
                "event_id": "200",
                "date": "2024-02-02T11:00:00",
                "media_url": "https://new/camara.mp4",
                "tipo_discurso": "Ordem do Dia",
                "raw_path": "camara.jsonl",
                "raw_source_id": "deputado:2:discursos:2024-02:pagina:1",
                "year": 2024,
            },
        ]
    )
    old_column_map = {
        "house": "Casa",
        "speech_id": "CodigoPronunciamento",
        "text": "TextoIntegral",
        "speaker_id": "CodigoParlamentar",
        "date": "DataPronunciamento",
        "event_id": "evento_id",
        "speech_type": "tipoDiscurso",
        "video_url": "urlVideo",
    }

    def quote_identifier(value: object) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    def quote_literal(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def old_expression(canonical: str, alias: str = "old") -> str:
        column = old_column_map.get(canonical)
        return "NULL" if not column else f"CAST({alias}.{quote_identifier(column)} AS VARCHAR)"

    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    match_source = next(
        cell.source
        for cell in notebook.cells
        if cell.metadata.get("falando_nela", {}).get("role")
        == "match_legacy_transcriptions"
    )
    namespace = {
        "duckdb": duckdb,
        "pd": pd,
        "current": current,
        "senate_candidates": current[current["house"] == "senado"].copy(),
        "old_column_map": old_column_map,
        "OLD_PARQUET_PATH": old_path,
        "quote_identifier": quote_identifier,
        "quote_literal": quote_literal,
        "old_expression": old_expression,
        "display": lambda *_: None,
    }
    exec(compile(match_source, "<match_legacy_transcriptions>", "exec"), namespace)
    matches = namespace["legacy_matches"]
    assert set(matches["candidate_id"]) == {"s10"}
    assert matches.iloc[0]["match_method"] == "exact_speech_id"
    assert set(matches["house"]) == {"senado"}

    classify_source = next(
        cell.source
        for cell in notebook.cells
        if cell.metadata.get("falando_nela", {}).get("role")
        == "classify_and_export_recoveries"
    )
    camara_queue = current[current["house"] == "camara"].copy()
    camara_queue["download_required"] = True
    camara_queue["download_status"] = "pending"
    camara_queue["transcription_status"] = "pending_after_download"
    camara_queue["download_priority"] = 2
    namespace.update(
        {
            "legacy_matches": matches,
            "camara_download_queue": camara_queue,
            "PROBE_ID": "test-recovery",
            "OLD_PARQUET_FILE_ID": "legacy-file",
            "OLD_PARQUET_EXPECTED_BYTES": old_path.stat().st_size,
            "old_info": {"rows": 2},
            "GRAVAR_RESULTADOS": False,
            "confirmed": lambda: None,
        }
    )
    exec(compile(classify_source, "<classify_and_export_recoveries>", "exec"), namespace)
    statuses = namespace["current_status"].set_index("candidate_id")["workflow_status"]
    assert statuses["s10"] == "recovered_strong_key"
    assert statuses["c20"] == "requires_media_download"
    assert set(namespace["accepted"]["house"]) == {"senado"}
    assert namespace["summary"]["legacy_scope"] == "senado_only"
