from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "notebooks"
    / "coleta"
    / "10_sondagem_transcricoes_audiovisuais_plenario_colab.ipynb"
)


def clean(value: str) -> str:
    return textwrap.dedent(value).strip()


def code(value: str, role: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_code_cell(clean(value))
    cell.metadata["falando_nela"] = {"role": role}
    return cell


def markdown(value: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_markdown_cell(clean(value))
    cell.metadata["language"] = "pt-BR"
    return cell


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        markdown(
            """
            # Transcrições audiovisuais — recuperação do Senado e fila da Câmara

            `DiscursosTodos.parquet`, banco da pesquisa anterior, contém apenas
            Senado. Por isso, o caderno trata as duas casas de modo diferente:

            - Senado: cruza a fila atual com as transcrições legadas por
              identificador oficial ou URL de mídia; vínculos secundários ficam
              para revisão.
            - Câmara: inventaria discursos com mídia e sem texto e produz uma
              fila explícita de download/transcrição futura. A Câmara nunca é
              cruzada com o Parquet legado.

            Os recuperados são gravados somente em `operations/`. O caderno não
            baixa mídia nesta sondagem, não executa ASR e não altera `raw/`,
            `processed/`, Parquets canônicos ou snapshots.
            """
        ),
        code(
            """
            from google.colab import drive

            drive.mount("/content/drive")
            """,
            "mount_drive",
        ),
        code(
            """
            from pathlib import Path
            import os
            import subprocess
            import sys

            REPO_URL = "https://github.com/pedblan/falando_nela.git"
            REPO_REF = "main"
            REPO_DIR = Path("/content/falando_nela")

            if not REPO_DIR.exists():
                subprocess.run(
                    ["git", "clone", "--branch", REPO_REF, "--single-branch", REPO_URL, str(REPO_DIR)],
                    check=True,
                )
            else:
                dirty = subprocess.check_output(
                    ["git", "-C", str(REPO_DIR), "status", "--porcelain"], text=True
                ).strip()
                assert not dirty, f"Clone efêmero com alterações locais: {dirty}"
                subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "origin", REPO_REF], check=True)
                subprocess.run(["git", "-C", str(REPO_DIR), "switch", REPO_REF], check=True)
                subprocess.run(
                    ["git", "-C", str(REPO_DIR), "pull", "--ff-only", "origin", REPO_REF],
                    check=True,
                )

            required = REPO_DIR / "coleta" / "transcricoes_audiovisuais.py"
            assert required.exists(), f"A revisão do repositório ainda não contém: {required}"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")],
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "google-api-python-client>=2,<3"],
                check=True,
            )
            os.chdir(REPO_DIR)
            if str(REPO_DIR) not in sys.path:
                sys.path.insert(0, str(REPO_DIR))
            print("Commit:", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
            """,
            "prepare_repository",
        ),
        code(
            """
            from pathlib import Path

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            PROBE_ID = "recuperacao-transcricoes-legadas-plenario-20260716-v1"
            PROBE_DIR = (
                DATA_ROOT
                / "operations"
                / "recuperacoes"
                / "transcricoes_legadas"
                / PROBE_ID
            )

            OLD_PARQUET_FILE_ID = "1R5Xz3tydoPYHSjzmKM8_KDvTzQ51RFk2"
            OLD_PARQUET_EXPECTED_BYTES = 252_122_904
            OLD_PARQUET_PATH = (
                DATA_ROOT / "reference" / "banco_legado" / "DiscursosTodos.parquet"
            )
            OLD_COLUMN_MAP = {}

            BAIXAR_PARQUET_ANTIGO = False
            GRAVAR_RESULTADOS = False
            CONFIRM_PROBE_ID = ""

            assert DATA_ROOT.is_dir(), f"Raiz de dados ausente: {DATA_ROOT}"
            assert "operations" in PROBE_DIR.parts
            assert "raw" not in PROBE_DIR.parts and "processed" not in PROBE_DIR.parts
            print("Recuperação:", PROBE_ID)
            print("Banco legado:", OLD_PARQUET_PATH)
            print("Saída operacional:", PROBE_DIR)
            """,
            "configure_recovery",
        ),
        markdown(
            """
            ## 1. Materializar o banco legado

            O link compartilhado pode devolver uma tela de login em vez do
            arquivo. O download opcional usa a identidade autenticada do Colab e
            só promove o `.part` depois de conferir tamanho, cabeçalho e rodapé
            Parquet.
            """
        ),
        code(
            """
            from coleta.transcricoes_audiovisuais import validate_parquet_magic

            def confirmed():
                assert CONFIRM_PROBE_ID == PROBE_ID, (
                    "Copie o valor exato de PROBE_ID para CONFIRM_PROBE_ID."
                )

            def download_old_parquet_from_drive():
                from google.colab import auth
                import google.auth
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaIoBaseDownload

                confirmed()
                auth.authenticate_user()
                credentials, _ = google.auth.default()
                service = build("drive", "v3", credentials=credentials, cache_discovery=False)
                metadata = service.files().get(
                    fileId=OLD_PARQUET_FILE_ID,
                    fields="id,name,mimeType,size,modifiedTime,md5Checksum",
                    supportsAllDrives=True,
                ).execute()
                assert int(metadata["size"]) == OLD_PARQUET_EXPECTED_BYTES, metadata
                OLD_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
                partial = OLD_PARQUET_PATH.with_suffix(".parquet.part")
                request = service.files().get_media(
                    fileId=OLD_PARQUET_FILE_ID,
                    supportsAllDrives=True,
                )
                with partial.open("wb") as handle:
                    downloader = MediaIoBaseDownload(handle, request, chunksize=16 * 1024 * 1024)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            print(f"Download: {status.progress():.1%}", flush=True)
                validate_parquet_magic(partial, expected_size=OLD_PARQUET_EXPECTED_BYTES)
                partial.replace(OLD_PARQUET_PATH)
                return metadata

            old_drive_metadata = None
            if OLD_PARQUET_PATH.is_file():
                print(validate_parquet_magic(
                    OLD_PARQUET_PATH,
                    expected_size=OLD_PARQUET_EXPECTED_BYTES,
                ))
            elif BAIXAR_PARQUET_ANTIGO:
                old_drive_metadata = download_old_parquet_from_drive()
                print("Banco legado validado:", old_drive_metadata)
            else:
                print(
                    "Ative BAIXAR_PARQUET_ANTIGO e confirme PROBE_ID. "
                    "Sem o arquivo validado, as próximas células param antes do cruzamento."
                )
            """,
            "materialize_old_parquet",
        ),
        code(
            """
            import duckdb
            import pandas as pd
            import pyarrow.parquet as pq
            from IPython.display import display

            from coleta.transcricoes_audiovisuais import infer_old_parquet_columns

            assert OLD_PARQUET_PATH.is_file(), (
                "Materialize DiscursosTodos.parquet na célula anterior antes de continuar."
            )
            validate_parquet_magic(
                OLD_PARQUET_PATH,
                expected_size=OLD_PARQUET_EXPECTED_BYTES,
            )
            parquet_file = pq.ParquetFile(OLD_PARQUET_PATH)
            old_columns = parquet_file.schema_arrow.names
            old_column_map = infer_old_parquet_columns(old_columns)
            old_column_map.update(OLD_COLUMN_MAP)
            old_info = {
                "path": str(OLD_PARQUET_PATH),
                "rows": parquet_file.metadata.num_rows,
                "row_groups": parquet_file.metadata.num_row_groups,
                "columns": len(old_columns),
            }
            display(pd.DataFrame([old_info]))
            display(pd.DataFrame({
                "canonical": old_column_map.keys(),
                "column": old_column_map.values(),
            }))
            print("Colunas legadas:", old_columns)
            assert "text" in old_column_map, (
                "A coluna de texto não foi inferida. Preencha OLD_COLUMN_MAP={'text': 'coluna_real'}."
            )

            def quote_identifier(value):
                return '"' + str(value).replace('"', '""') + '"'

            def quote_literal(value):
                return "'" + str(value).replace("'", "''") + "'"

            def old_expression(canonical, alias="old"):
                column = old_column_map.get(canonical)
                if not column:
                    return "NULL"
                return f"CAST({alias}.{quote_identifier(column)} AS VARCHAR)"
            """,
            "inspect_legacy_schema",
        ),
        markdown(
            """
            ## 2. Inventariar lacunas atuais

            Na Câmara, entram itens com mídia e sem `transcricao`; se outra
            ocorrência da mesma unidade já contém texto, ela é retirada. No
            Senado, o ponto de partida é a fila explícita do coletor.

            No progresso da Câmara, `com_texto` conta ocorrências raw que já
            trazem transcrição — não recuperações feitas por este caderno.
            `sem_texto_com_midia` conta ocorrências candidatas antes da
            deduplicação, e `pendentes_unicos` é a fila provisória após excluir
            unidades observadas com texto em outro run.
            """
        ),
        code(
            """
            import importlib
            from coleta import transcricoes_audiovisuais

            transcricoes_audiovisuais = importlib.reload(transcricoes_audiovisuais)
            assert getattr(transcricoes_audiovisuais, "INVENTORY_CODE_VERSION", 0) >= 2, (
                "Módulo antigo ainda carregado. Reexecute a preparação do repositório "
                "e depois esta célula."
            )
            print("Módulo de inventário:", transcricoes_audiovisuais.__file__)
            print("Versão do inventário:", transcricoes_audiovisuais.INVENTORY_CODE_VERSION)
            assert "/content/falando_nela/" in str(transcricoes_audiovisuais.__file__), (
                "O módulo foi importado de outro checkout: "
                f"{transcricoes_audiovisuais.__file__}"
            )

            current = pd.DataFrame([
                *transcricoes_audiovisuais.scan_camara_media_candidates(
                    DATA_ROOT, progress=print
                ),
                *transcricoes_audiovisuais.scan_senado_transcription_queue(
                    DATA_ROOT, progress=print
                ),
            ])
            assert not current.empty, "Nenhuma lacuna audiovisual encontrada"
            assert current["candidate_id"].is_unique
            senate_candidates = current[current["house"] == "senado"].copy()
            camara_download_queue = current[current["house"] == "camara"].copy()
            assert not senate_candidates.empty, "Fila atual do Senado vazia"
            camara_download_queue["download_required"] = True
            camara_download_queue["download_status"] = "pending"
            camara_download_queue["transcription_status"] = "pending_after_download"
            camara_download_queue["download_priority"] = camara_download_queue[
                "media_source"
            ].map({"audio": 1, "video": 2}).fillna(3).astype(int)
            display(
                current.groupby(
                    ["house", "year", "media_granularity"], dropna=False
                ).size().rename("candidatos").reset_index()
            )
            display(current.drop(columns=["fontes"], errors="ignore").head(30))
            print("Câmara aguardando download/transcrição:", len(camara_download_queue))
            """,
            "inventory_current_gaps",
        ),
        markdown(
            """
            ## 3. Recuperar as transcrições antigas do Senado

            A precedência de aceite é identificador oficial ou URL de mídia
            idêntica. Uma combinação de parlamentar, data e sessão pode localizar
            candidatos para revisão, mas não é aceita automaticamente. O conjunto
            da Câmara fica completamente fora deste cruzamento.
            """
        ),
        code(
            r'''
            import hashlib
            candidate_columns = [
                "candidate_id", "house", "speech_id", "speaker_id", "event_id",
                "date", "media_url", "tipo_discurso", "raw_path", "raw_source_id",
            ]
            candidate_table = senate_candidates.reindex(columns=candidate_columns).copy()
            for column in candidate_table.columns:
                candidate_table[column] = candidate_table[column].fillna("").astype(str)
            assert set(candidate_table["house"]) == {"senado"}

            connection = duckdb.connect()
            connection.register("current_candidates", candidate_table)
            parquet_literal = quote_literal(OLD_PARQUET_PATH)
            connection.execute(
                f"CREATE TEMP VIEW legacy_source AS SELECT * FROM read_parquet({parquet_literal})"
            )

            text_expression = old_expression("text")
            legacy_projection = f"""
                {old_expression('house')} AS old_house,
                {old_expression('speech_id')} AS old_speech_id,
                {old_expression('speaker_id')} AS old_speaker_id,
                {old_expression('event_id')} AS old_event_id,
                {old_expression('date')} AS old_date,
                {old_expression('speech_type')} AS old_speech_type,
                {old_expression('audio_url')} AS old_audio_url,
                {old_expression('video_url')} AS old_video_url,
                {old_expression('text_method')} AS old_text_method,
                {text_expression} AS legacy_text
            """

            branches = []
            if "speech_id" in old_column_map:
                branches.append((
                    "exact_speech_id",
                    100,
                    f"{old_expression('speech_id')} = candidate.speech_id AND candidate.speech_id <> ''",
                ))
            if "audio_url" in old_column_map:
                branches.append((
                    "exact_audio_url",
                    95,
                    f"{old_expression('audio_url')} = candidate.media_url AND candidate.media_url <> ''",
                ))
            if "video_url" in old_column_map:
                branches.append((
                    "exact_video_url",
                    95,
                    f"{old_expression('video_url')} = candidate.media_url AND candidate.media_url <> ''",
                ))

            speaker_date = {"speaker_id", "date"}.issubset(old_column_map)
            if speaker_date and "event_id" in old_column_map:
                branches.append((
                    "senate_speaker_date_event_review",
                    80,
                    f"""
                        candidate.house = 'senado'
                        AND {old_expression('speaker_id')} = candidate.speaker_id
                        AND candidate.speaker_id <> ''
                        AND CAST(TRY_CAST({old_expression('date')} AS DATE) AS VARCHAR)
                            = CAST(TRY_CAST(candidate.date AS DATE) AS VARCHAR)
                        AND {old_expression('event_id')} = candidate.event_id
                        AND candidate.event_id <> ''
                    """,
                ))

            assert branches, (
                "O schema legado não oferece uma chave de cruzamento. "
                "Complete OLD_COLUMN_MAP com os nomes reais."
            )
            queries = []
            for method, score, condition in branches:
                queries.append(f"""
                    SELECT
                        candidate.*,
                        {legacy_projection},
                        '{method}' AS match_method,
                        {score} AS match_score
                    FROM legacy_source AS old
                    INNER JOIN current_candidates AS candidate ON {condition}
                    WHERE LENGTH(TRIM({text_expression})) > 0
                """)
            legacy_matches = connection.execute(" UNION ALL ".join(queries)).fetchdf()

            def hash_text(value):
                return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()

            if not legacy_matches.empty:
                assert set(legacy_matches["house"]) == {"senado"}
                legacy_matches["legacy_text_sha256"] = legacy_matches["legacy_text"].map(hash_text)
                legacy_matches["legacy_text_length"] = legacy_matches["legacy_text"].str.strip().str.len()
                fingerprint_columns = [
                    "old_house", "old_speech_id", "old_speaker_id", "old_event_id",
                    "old_date", "old_speech_type", "old_audio_url", "old_video_url",
                    "legacy_text_sha256",
                ]
                legacy_matches["legacy_row_fingerprint"] = legacy_matches[
                    fingerprint_columns
                ].astype("string").fillna("").agg("\x1f".join, axis=1).map(hash_text)
                legacy_matches = legacy_matches.sort_values(
                    ["candidate_id", "match_score"], ascending=[True, False]
                ).drop_duplicates(["candidate_id", "legacy_text_sha256"])

            print("Correspondências encontradas:", len(legacy_matches))
            if not legacy_matches.empty:
                display(
                    legacy_matches.groupby(["house", "match_method"])
                    .size().rename("matches").reset_index()
                )
            ''',
            "match_legacy_transcriptions",
        ),
        code(
            r'''
            from datetime import datetime, timezone

            def utc_now():
                return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

            if legacy_matches.empty:
                accepted = legacy_matches.copy()
                review = legacy_matches.copy()
                conflicts = legacy_matches.copy()
            else:
                text_variants = legacy_matches.groupby("candidate_id")[
                    "legacy_text_sha256"
                ].nunique()
                conflicting_candidates = set(text_variants[text_variants > 1].index)
                candidate_variants = legacy_matches.groupby("legacy_row_fingerprint")[
                    "candidate_id"
                ].nunique()
                ambiguous_legacy_rows = set(candidate_variants[candidate_variants > 1].index)

                conflict_mask = (
                    legacy_matches["candidate_id"].isin(conflicting_candidates)
                    | legacy_matches["legacy_row_fingerprint"].isin(ambiguous_legacy_rows)
                )
                conflicts = legacy_matches[conflict_mask].copy()
                unambiguous = legacy_matches[~conflict_mask].copy()
                accepted = unambiguous[unambiguous["match_score"] >= 90].copy()
                accepted = accepted.sort_values(
                    ["candidate_id", "match_score"], ascending=[True, False]
                ).drop_duplicates("candidate_id")
                review = unambiguous[unambiguous["match_score"] < 90].copy()

            assert accepted["candidate_id"].is_unique
            assert set(accepted["candidate_id"]).isdisjoint(set(conflicts["candidate_id"]))
            assert accepted.empty or accepted["house"].eq("senado").all()
            accepted["recovery_id"] = PROBE_ID
            accepted["recovery_source"] = "legacy_parquet"
            accepted["legacy_file_id"] = OLD_PARQUET_FILE_ID
            accepted["review_status"] = "accepted_by_strong_key_pending_text_review"
            accepted["publication_status"] = "operations_only"
            accepted["recovered_at"] = utc_now()

            current_status = current[["candidate_id", "house", "year"]].copy()
            current_status["workflow_status"] = "not_found_in_legacy"
            current_status.loc[
                current_status["house"] == "camara", "workflow_status"
            ] = "requires_media_download"
            current_status.loc[
                current_status["candidate_id"].isin(review["candidate_id"]),
                "workflow_status",
            ] = "manual_review"
            current_status.loc[
                current_status["candidate_id"].isin(conflicts["candidate_id"]),
                "workflow_status",
            ] = "conflict"
            current_status.loc[
                current_status["candidate_id"].isin(accepted["candidate_id"]),
                "workflow_status",
            ] = "recovered_strong_key"

            summary = {
                "recovery_id": PROBE_ID,
                "created_at": utc_now(),
                "legacy_file_id": OLD_PARQUET_FILE_ID,
                "legacy_file_size_bytes": OLD_PARQUET_EXPECTED_BYTES,
                "legacy_scope": "senado_only",
                "legacy_rows": old_info["rows"],
                "current_candidates": len(current),
                "senate_candidates": len(senate_candidates),
                "camara_requires_media_download": len(camara_download_queue),
                "raw_matches": len(legacy_matches),
                "accepted_strong_key": len(accepted),
                "manual_review": len(review),
                "conflicts": len(conflicts),
                "senate_not_found_in_legacy": int(
                    (current_status["workflow_status"] == "not_found_in_legacy").sum()
                ),
                "counts_by_house_and_status": current_status.groupby(
                    ["house", "workflow_status"]
                ).size().rename("rows").reset_index().to_dict("records"),
                "gates": {
                    "candidate_id_unique": bool(current["candidate_id"].is_unique),
                    "accepted_candidate_id_unique": bool(accepted["candidate_id"].is_unique),
                    "accepted_has_nonempty_text": bool(
                        accepted.empty or accepted["legacy_text"].str.strip().ne("").all()
                    ),
                    "legacy_recovery_is_senate_only": bool(
                        accepted.empty or accepted["house"].eq("senado").all()
                    ),
                    "camara_is_download_queue_only": bool(
                        current_status.loc[
                            current_status["house"] == "camara", "workflow_status"
                        ].eq("requires_media_download").all()
                    ),
                    "canonical_outputs_untouched": True,
                },
            }
            assert all(summary["gates"].values()), summary["gates"]
            display(current_status.groupby(["house", "workflow_status"]).size())
            display(accepted.drop(columns=["legacy_text"], errors="ignore").head(50))
            display(summary)

            if GRAVAR_RESULTADOS:
                confirmed()
                PROBE_DIR.mkdir(parents=True, exist_ok=True)
                accepted.to_parquet(PROBE_DIR / "recovered_legacy_texts.parquet", index=False)
                review.to_parquet(PROBE_DIR / "legacy_matches_manual_review.parquet", index=False)
                conflicts.to_parquet(PROBE_DIR / "legacy_match_conflicts.parquet", index=False)
                current_status.to_csv(PROBE_DIR / "candidate_status.csv", index=False)
                camara_export = camara_download_queue.drop(
                    columns=["fontes"], errors="ignore"
                ).sort_values(["download_priority", "year", "candidate_id"])
                camara_export.to_parquet(
                    PROBE_DIR / "camara_media_download_queue.parquet", index=False
                )
                camara_export.to_csv(
                    PROBE_DIR / "camara_media_download_queue.csv", index=False
                )
                audit = legacy_matches.drop(columns=["legacy_text"], errors="ignore")
                audit.to_parquet(PROBE_DIR / "legacy_match_audit.parquet", index=False)
                (PROBE_DIR / "summary.json").write_text(
                    __import__("json").dumps(
                        summary, ensure_ascii=False, indent=2, sort_keys=True
                    ) + chr(10),
                    encoding="utf-8",
                )
                print("Recuperação operacional gravada em:", PROBE_DIR)
            else:
                print("Escrita protegida. Ative GRAVAR_RESULTADOS e confirme PROBE_ID.")
            ''',
            "classify_and_export_recoveries",
        ),
        markdown(
            """
            ## Próxima decisão

            Para o Senado, `recovered_legacy_texts.parquet` contém os textos
            recuperados por chave forte, ainda em área operacional. Antes da
            promoção ao corpus:

            1. revisar uma amostra de texto, autor, data e URL por casa;
            2. resolver `legacy_match_conflicts.parquet` e os vínculos de revisão;
            3. criar um contrato raw versionado com proveniência do arquivo
               legado e checksum do texto;
            4. reconstruir processed/Parquet e medir o acréscimo por ano.

            Para a Câmara, `camara_media_download_queue.parquet` mede e identifica
            exatamente o que ainda precisa ser baixado. A próxima etapa poderá
            dimensionar armazenamento, testar uma amostra de URLs e então baixar
            e transcrever de forma retomável — sem misturar essa aquisição com a
            recuperação legada do Senado.
            """
        ),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.update(
        {
            "colab": {"name": OUTPUT.name, "provenance": []},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        }
    )
    for index, cell in enumerate(notebook.cells):
        stable = f"{OUTPUT.relative_to(ROOT)}:{index}:{cell.cell_type}:{cell.source}".encode(
            "utf-8"
        )
        cell["id"] = sha256(stable).hexdigest()[:16]
    nbformat.validate(notebook)
    return notebook


def render() -> str:
    return nbformat.writes(build_notebook()) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
    if args.check:
        if current != content:
            raise SystemExit(f"Notebook fora de sincronia: {OUTPUT}")
        return
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
