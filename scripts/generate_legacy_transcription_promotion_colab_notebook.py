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
    / "12_promocao_transcricoes_legadas_plenario_colab.ipynb"
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
            # Promoção revisada das transcrições legadas e limpeza derivada do Diário

            Este caderno executa duas operações independentes e protegidas:

            1. promove ao raw do Senado somente os **471** textos recuperados
               por chave forte e aprovados após revisão visual de 30%;
            2. regenera os derivados aplicando uma limpeza conservadora de
               cabeçalhos e rodapés somente aos **83** textos cuja obtenção foi
               `diario-congresso-oficial-por-codigo-v1`.

            O PDF e o texto raw do Diário permanecem imutáveis. Vínculos de
            revisão manual, conflitos e itens não encontrados continuam fora da
            promoção. As duas mutações começam desligadas, exigem confirmações
            literais e produzem proveniência e fingerprints antes/depois.
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

            required = REPO_DIR / "coleta" / "senado" / "promocao_transcricoes_legadas.py"
            assert required.exists(), f"A revisão do repositório ainda não contém: {required}"
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")],
                check=True,
            )
            os.chdir(REPO_DIR)
            if str(REPO_DIR) not in sys.path:
                sys.path.insert(0, str(REPO_DIR))
            REPO_COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            print("Commit:", REPO_COMMIT)
            """,
            "prepare_repository",
        ),
        code(
            """
            from pathlib import Path

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            RECOVERY_ID = "recuperacao-transcricoes-legadas-plenario-20260716-v1"
            AUDIT_ID = "auditoria-transcricoes-plenario-2010-2015-2016-20260716-v1"
            PROMOTION_RUN_ID = "promocao-transcricoes-legadas-plenario-20260716-v1"
            NORMALIZATION_RUN_ID = "processed-textos-v1-current"
            PARQUET_RUN_ID = "parquet-textos-v1-current"

            RECOVERY_DIR = DATA_ROOT / "operations" / "recuperacoes" / "transcricoes_legadas" / RECOVERY_ID
            AUDIT_DIR = DATA_ROOT / "operations" / "auditorias" / "transcricoes_legadas" / AUDIT_ID
            PROMOTION_DIR = DATA_ROOT / "operations" / "promocoes" / "transcricoes_legadas" / PROMOTION_RUN_ID
            PROMOTION_MANIFEST_PATH = DATA_ROOT / "manifests" / f"{PROMOTION_RUN_ID}.json"
            PARQUET_ROOT = DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"

            EXPECTED_ACCEPTED = 471
            EXPECTED_DIARY = 83
            VISUAL_REVIEW_FRACTION = 0.30
            VISUAL_REVIEW_DECISION = "approved"
            VISUAL_REVIEW_NOTE = (
                "Amostra aleatória de 30% dos recuperados por chave forte revisada visualmente "
                "em 2026-07-16; conteúdo considerado adequado para promoção."
            )

            PROMOVER_TRANSCRICOES = False
            CONFIRM_PROMOTION_RUN_ID = ""
            REGERAR_DERIVADOS = False
            CONFIRM_REBUILD_PROMOTION_RUN_ID = ""
            CONFIRM_DIARY_CLEANING_VERSION = ""

            assert DATA_ROOT.is_dir(), DATA_ROOT
            assert RECOVERY_DIR.is_dir(), RECOVERY_DIR
            assert AUDIT_DIR.is_dir(), AUDIT_DIR
            assert "operations" in PROMOTION_DIR.parts
            print("Recuperação:", RECOVERY_DIR)
            print("Auditoria:", AUDIT_DIR)
            print("Promoção:", PROMOTION_DIR)
            """,
            "configure_promotion",
        ),
        markdown(
            """
            ## Funções e contratos carregados do commit

            A promoção gera registros raw canônicos particionados por mês. A
            limpeza do Diário só é chamada pela normalização quando o método de
            obtenção coincide exatamente com a recuperação oficial por código.
            """
        ),
        code(
            r'''
            import hashlib
            import html
            import importlib
            import json
            from datetime import datetime, timezone

            import duckdb
            import pandas as pd
            from IPython.display import HTML, display
            from coleta.senado import promocao_transcricoes_legadas
            from processamento import limpeza_diario

            promocao_transcricoes_legadas = importlib.reload(promocao_transcricoes_legadas)
            limpeza_diario = importlib.reload(limpeza_diario)
            PROMOTION_METHOD = promocao_transcricoes_legadas.PROMOTION_METHOD
            DIARY_RECOVERY_METHOD = limpeza_diario.DIARY_RECOVERY_METHOD
            DIARY_CLEANING_VERSION = limpeza_diario.DIARY_CLEANING_VERSION

            assert "/content/falando_nela/" in str(promocao_transcricoes_legadas.__file__)
            assert "/content/falando_nela/" in str(limpeza_diario.__file__)
            print("Método de promoção:", PROMOTION_METHOD)
            print("Versão da limpeza:", DIARY_CLEANING_VERSION)


            def sha256_text(value):
                return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()


            def processed_text(value):
                return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


            def sha256_file(path):
                digest = hashlib.sha256()
                with Path(path).open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                return digest.hexdigest()


            def read_json(path):
                return json.loads(Path(path).read_text(encoding="utf-8"))


            def write_json_atomic(path, value):
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                partial = path.with_name(f"{path.name}.partial")
                partial.write_text(
                    json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                partial.replace(path)


            def quote_literal(value):
                return "'" + str(value).replace("'", "''") + "'"


            def parquet_scope(path, where="TRUE"):
                connection = duckdb.connect()
                query = f"""
                    SELECT *
                    FROM read_parquet({quote_literal(path)})
                    WHERE {where}
                    ORDER BY texto_id
                """
                text_digest = hashlib.sha256()
                id_digest = hashlib.sha256()
                row_digest = hashlib.sha256()
                rows = 0
                reader = connection.execute(query).fetch_record_batch(rows_per_batch=10000)
                for batch in reader:
                    for row in batch.to_pylist():
                        texto_id = row.get("texto_id")
                        text = row.get("texto")
                        encoded_id = json.dumps(texto_id, ensure_ascii=False).encode("utf-8")
                        encoded_pair = json.dumps(
                            [texto_id, text], ensure_ascii=False, separators=(",", ":")
                        ).encode("utf-8")
                        encoded_row = json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        ).encode("utf-8")
                        id_digest.update(encoded_id + b"\n")
                        text_digest.update(encoded_pair + b"\n")
                        row_digest.update(encoded_row + b"\n")
                        rows += 1
                connection.close()
                return {
                    "rows": rows,
                    "id_sha256": id_digest.hexdigest(),
                    "id_text_sha256": text_digest.hexdigest(),
                    "full_row_sha256": row_digest.hexdigest(),
                }


            def frame_text_scope(frame, id_column="texto_id", text_column="texto"):
                id_digest = hashlib.sha256()
                text_digest = hashlib.sha256()
                ordered = frame[[id_column, text_column]].sort_values(id_column)
                for texto_id, text in ordered.itertuples(index=False, name=None):
                    encoded_id = json.dumps(str(texto_id), ensure_ascii=False).encode("utf-8")
                    encoded_pair = json.dumps(
                        [str(texto_id), str(text)],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    id_digest.update(encoded_id + b"\n")
                    text_digest.update(encoded_pair + b"\n")
                return {
                    "rows": len(ordered),
                    "id_sha256": id_digest.hexdigest(),
                    "id_text_sha256": text_digest.hexdigest(),
                }


            def run_streamed(command, label):
                print(f"\n=== {label} ===", flush=True)
                print(" ".join(map(str, command)), flush=True)
                completed = subprocess.run(list(map(str, command)), check=False)
                print(f"=== retorno {completed.returncode}: {label} ===", flush=True)
                return completed.returncode


            def text_cards(rows, title):
                parts = [f"<h3>{html.escape(title)}</h3>"]
                for index, row in enumerate(rows, start=1):
                    parts.append(
                        f"<details><summary>amostra {index}</summary>"
                        f"<h4>Antes</h4><pre style='white-space:pre-wrap'>{html.escape(row['before'])}</pre>"
                        f"<h4>Depois</h4><pre style='white-space:pre-wrap'>{html.escape(row['after'])}</pre>"
                        "</details>"
                    )
                return "".join(parts)
            ''',
            "load_contracts_and_helpers",
        ),
        markdown(
            """
            ## Reconciliar a população permitida

            O gate abaixo relê os artefatos dos cadernos 10 e 11, recalcula
            hashes e comprimentos e prova que nenhum caso manual, conflito ou
            não encontrado entrou nos 471 registros candidatos à promoção.
            """
        ),
        code(
            """
            RECOVERY_PATHS = {
                "accepted": RECOVERY_DIR / "recovered_legacy_texts.parquet",
                "manual": RECOVERY_DIR / "legacy_matches_manual_review.parquet",
                "conflicts": RECOVERY_DIR / "legacy_match_conflicts.parquet",
                "status": RECOVERY_DIR / "candidate_status.csv",
                "summary": RECOVERY_DIR / "summary.json",
                "audit_provenance": AUDIT_DIR / "provenance.json",
            }
            assert all(path.is_file() for path in RECOVERY_PATHS.values()), RECOVERY_PATHS
            accepted = pd.read_parquet(RECOVERY_PATHS["accepted"])
            manual = pd.read_parquet(RECOVERY_PATHS["manual"])
            conflicts = pd.read_parquet(RECOVERY_PATHS["conflicts"])
            candidate_status = pd.read_csv(RECOVERY_PATHS["status"], dtype={"candidate_id": str})
            recovery_summary = read_json(RECOVERY_PATHS["summary"])
            audit_provenance = read_json(RECOVERY_PATHS["audit_provenance"])

            accepted_ids = set(accepted["candidate_id"].astype(str))
            manual_ids = set(manual["candidate_id"].astype(str))
            conflict_ids = set(conflicts["candidate_id"].astype(str))
            excluded_statuses = {"manual_review", "conflict", "not_found_in_legacy"}
            excluded_ids = set(
                candidate_status.loc[
                    candidate_status["workflow_status"].isin(excluded_statuses), "candidate_id"
                ].astype(str)
            )

            accepted["recomputed_sha256"] = accepted["legacy_text"].map(sha256_text)
            accepted["recomputed_length"] = accepted["legacy_text"].astype(str).str.strip().str.len()
            strong_methods = promocao_transcricoes_legadas.STRONG_MATCH_METHODS
            population_gates = {
                "exact_expected_count": len(accepted) == EXPECTED_ACCEPTED,
                "summary_reconciled": len(accepted) == recovery_summary["accepted_strong_key"],
                "unique_candidates": bool(accepted["candidate_id"].is_unique),
                "unique_speech_ids": bool(accepted["speech_id"].astype(str).is_unique),
                "senate_only": bool(accepted["house"].eq("senado").all()),
                "strong_methods_only": set(accepted["match_method"]) <= strong_methods,
                "score_at_least_90": bool(accepted["match_score"].ge(90).all()),
                "hashes_valid": bool(accepted["recomputed_sha256"].eq(accepted["legacy_text_sha256"]).all()),
                "lengths_valid": bool(accepted["recomputed_length"].eq(accepted["legacy_text_length"]).all()),
                "manual_excluded": accepted_ids.isdisjoint(manual_ids),
                "conflicts_excluded": accepted_ids.isdisjoint(conflict_ids),
                "all_excluded_statuses_absent": accepted_ids.isdisjoint(excluded_ids),
                "audit_gates_approved": bool(all(audit_provenance["structural_gates"].values())),
                "visual_review_recorded": VISUAL_REVIEW_FRACTION == 0.30 and VISUAL_REVIEW_DECISION == "approved",
            }
            display(population_gates)
            assert all(population_gates.values()), population_gates

            promotion_records = promocao_transcricoes_legadas.build_promotion_records(
                accepted.to_dict("records"),
                run_id=PROMOTION_RUN_ID,
                recovery_id=RECOVERY_ID,
                audit_id=AUDIT_ID,
                visual_review_fraction=VISUAL_REVIEW_FRACTION,
                visual_review_decision=VISUAL_REVIEW_DECISION,
                visual_review_note=VISUAL_REVIEW_NOTE,
            )
            assert len(promotion_records) == EXPECTED_ACCEPTED
            display(
                pd.DataFrame(promotion_records)
                .groupby("partition").size().rename("textos").reset_index()
            )
            """,
            "reconcile_accepted_population",
        ),
        markdown(
            """
            ## Prévia conservadora da limpeza do Diário

            Somente linhas reconhecidas nas cinco primeiras ou últimas linhas
            não vazias de cada página podem sair. O relatório mostra a
            frequência das linhas removidas e pares antes/depois. Se nenhum
            padrão for reconhecido, o rebuild fica bloqueado para revisão da
            regra — nunca há uma limpeza ampla por tentativa.
            """
        ),
        code(
            r'''
            CONGRESS_PARQUET = PARQUET_ROOT / "senado__congresso_discursos.parquet"
            assert CONGRESS_PARQUET.is_file(), CONGRESS_PARQUET
            diary_rows = duckdb.connect().execute(
                f"""
                SELECT texto_id, texto, metodo_obtencao, raw_path, raw_source_id, fontes
                FROM read_parquet({quote_literal(CONGRESS_PARQUET)})
                WHERE metodo_obtencao = {quote_literal(DIARY_RECOVERY_METHOD)}
                ORDER BY texto_id
                """
            ).fetchdf()
            assert len(diary_rows) == EXPECTED_DIARY, len(diary_rows)

            diary_results = [
                limpeza_diario.clean_diary_editorial_noise(text)
                for text in diary_rows["texto"].astype(str)
            ]
            diary_preview = diary_rows.drop(columns=["texto"]).copy()
            diary_preview["changed"] = [item["changed"] for item in diary_results]
            diary_preview["removed_line_count"] = [item["removed_line_count"] for item in diary_results]
            diary_preview["original_length"] = [item["original_length"] for item in diary_results]
            diary_preview["cleaned_length"] = [item["cleaned_length"] for item in diary_results]
            diary_preview["page_breaks"] = [item["page_breaks"] for item in diary_results]
            removed_lines = pd.DataFrame(
                [
                    {"texto_id": texto_id, **line}
                    for texto_id, result in zip(diary_rows["texto_id"], diary_results)
                    for line in result["removed_lines"]
                ]
            )
            changed_count = int(diary_preview["changed"].sum())
            def recorded_cleaning_version(value):
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        return None
                if not isinstance(value, dict):
                    return None
                audit = value.get("normalizacao_texto_diario")
                return audit.get("version") if isinstance(audit, dict) else None

            diary_already_cleaned = bool(
                changed_count == 0
                and diary_rows["fontes"].map(recorded_cleaning_version).eq(
                    DIARY_CLEANING_VERSION
                ).all()
            )
            assert changed_count > 0 or diary_already_cleaned, (
                "Nenhuma marca editorial reconhecida e não há proveniência de limpeza anterior. "
                "Inspecione as fronteiras antes de alterar a regra."
            )
            assert all(item["text"].strip() for item in diary_results)
            assert all(
                not limpeza_diario.clean_diary_editorial_noise(item["text"])["changed"]
                for item in diary_results
            ), "A limpeza precisa ser idempotente"

            display(diary_preview.describe(include="all"))
            if not removed_lines.empty:
                display(removed_lines.groupby("text").size().rename("ocorrencias").reset_index().sort_values("ocorrencias", ascending=False).head(100))
            preview_pairs = [
                {"before": str(diary_rows.iloc[index]["texto"]), "after": diary_results[index]["text"]}
                for index in diary_preview.loc[diary_preview["changed"]].head(5).index
            ]
            display(HTML(text_cards(preview_pairs, "Amostra antes/depois da limpeza derivada")))
            print(
                "Textos do Diário:", len(diary_rows),
                "| alterados na prévia:", changed_count,
                "| limpeza já materializada:", diary_already_cleaned,
            )
            ''',
            "preview_diary_cleanup",
        ),
        markdown(
            """
            ## Preflight canônico e fotografia anterior

            Na primeira execução, nenhum dos 471 códigos pode ter texto não
            vazio no raw nem aparecer no Parquet atual. Depois de uma promoção
            concluída, o caderno reconhece exclusivamente os próprios registros
            e reutiliza a fotografia anterior persistida para ser retomável.
            """
        ),
        code(
            r'''
            promotion_manifest = (
                read_json(PROMOTION_MANIFEST_PATH) if PROMOTION_MANIFEST_PATH.is_file() else None
            )
            promotion_completed = bool(
                promotion_manifest
                and promotion_manifest.get("status") == "completed"
                and promotion_manifest.get("run_id") == PROMOTION_RUN_ID
                and promotion_manifest.get("records") == EXPECTED_ACCEPTED
            )
            speech_ids = accepted["speech_id"].astype(str).tolist()
            existing_raw = promocao_transcricoes_legadas.find_existing_nonempty_texts(
                DATA_ROOT, speech_ids
            )
            if promotion_completed:
                assert set(existing_raw) == set(speech_ids), (
                    "Promoção manifestada, mas sua população raw está incompleta."
                )
                assert all(
                    item["run_id"] == PROMOTION_RUN_ID
                    and item["metodo_obtencao"] == PROMOTION_METHOD
                    for observations in existing_raw.values()
                    for item in observations
                ), "Texto concorrente encontrado após a promoção"
            else:
                assert not existing_raw, (
                    "Há texto raw anterior para códigos candidatos; não promova silenciosamente."
                )

            SENATE_PARQUET = PARQUET_ROOT / "senado__plenario_discursos.parquet"
            target_text_ids = [
                f"senado:plenario_discursos:pronunciamento:{speech_id}"
                for speech_id in speech_ids
            ]
            target_sql = ",".join(quote_literal(value) for value in target_text_ids)
            current_target_count = duckdb.connect().execute(
                f"SELECT COUNT(*) FROM read_parquet({quote_literal(SENATE_PARQUET)}) "
                f"WHERE texto_id IN ({target_sql})"
            ).fetchone()[0]
            if promotion_completed:
                assert current_target_count in {0, EXPECTED_ACCEPTED}, current_target_count
            else:
                assert current_target_count == 0, current_target_count

            expected_parquet_names = {
                "camara__ccjc_eventos.parquet",
                "camara__pareceres_pec.parquet",
                "camara__plenario_discursos.parquet",
                "senado__ccj_notas.parquet",
                "senado__congresso_discursos.parquet",
                "senado__pareceres_pec.parquet",
                "senado__plenario_discursos.parquet",
            }
            parquet_paths = {path.name: path for path in PARQUET_ROOT.glob("*.parquet")}
            assert set(parquet_paths) == expected_parquet_names, set(parquet_paths)
            pre_state_path = PROMOTION_DIR / "pre_rebuild_state.json"
            if promotion_completed:
                assert pre_state_path.is_file(), pre_state_path
                pre_rebuild_state = read_json(pre_state_path)
            else:
                print("Calculando fingerprints integrais dos sete Parquets...")
                pre_rebuild_state = {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "repository_commit": REPO_COMMIT,
                    "parquets": {},
                }
                for name, path in sorted(parquet_paths.items()):
                    pre_rebuild_state["parquets"][name] = parquet_scope(path)
                    print(name, pre_rebuild_state["parquets"][name])
                pre_rebuild_state["congress_non_diary"] = parquet_scope(
                    CONGRESS_PARQUET,
                    f"COALESCE(metodo_obtencao, '') <> {quote_literal(DIARY_RECOVERY_METHOD)}",
                )
                pre_rebuild_state["congress_diary"] = parquet_scope(
                    CONGRESS_PARQUET,
                    f"metodo_obtencao = {quote_literal(DIARY_RECOVERY_METHOD)}",
                )
                expected_diary = diary_rows[["texto_id"]].copy()
                expected_diary["texto"] = [item["text"] for item in diary_results]
                pre_rebuild_state["expected_congress_diary_cleaned"] = frame_text_scope(
                    expected_diary
                )
            print("Promoção já concluída:", promotion_completed)
            print("Alvos no Parquet atual:", current_target_count)
            ''',
            "preflight_and_baseline",
        ),
        markdown(
            """
            ## Operação 1 — publicar os 471 registros raw

            Para executar, defina `PROMOVER_TRANSCRICOES=True` e copie
            `PROMOTION_RUN_ID` para `CONFIRM_PROMOTION_RUN_ID`. A operação cria
            arquivos mensais novos e um manifest; não sobrescreve raw anterior.
            """
        ),
        code(
            """
            if PROMOVER_TRANSCRICOES:
                assert CONFIRM_PROMOTION_RUN_ID == PROMOTION_RUN_ID, (
                    "Copie PROMOTION_RUN_ID exatamente para CONFIRM_PROMOTION_RUN_ID."
                )
                assert not promotion_completed, "A promoção já foi concluída; não a repita."
                state_path = PROMOTION_DIR / "promotion_state.json"
                if PROMOTION_DIR.exists():
                    prepared = read_json(state_path)
                    assert prepared["status"] == "prepared", prepared
                    assert prepared["run_id"] == PROMOTION_RUN_ID, prepared
                    assert read_json(PROMOTION_DIR / "pre_rebuild_state.json") == pre_rebuild_state
                else:
                    PROMOTION_DIR.mkdir(parents=True, exist_ok=False)
                    write_json_atomic(PROMOTION_DIR / "pre_rebuild_state.json", pre_rebuild_state)
                    write_json_atomic(
                        state_path,
                        {
                            "schema_version": 1,
                            "status": "prepared",
                            "run_id": PROMOTION_RUN_ID,
                            "recovery_id": RECOVERY_ID,
                            "audit_id": AUDIT_ID,
                            "repository_commit": REPO_COMMIT,
                            "records": len(promotion_records),
                        },
                    )

                promotion_manifest = promocao_transcricoes_legadas.write_promotion_records(
                    DATA_ROOT,
                    promotion_records,
                    run_id=PROMOTION_RUN_ID,
                    recovery_id=RECOVERY_ID,
                    audit_id=AUDIT_ID,
                    repository_commit=REPO_COMMIT,
                )
                write_json_atomic(PROMOTION_DIR / "raw_promotion_manifest.json", promotion_manifest)
                write_json_atomic(
                    PROMOTION_DIR / "visual_review.json",
                    {
                        "fraction": VISUAL_REVIEW_FRACTION,
                        "decision": VISUAL_REVIEW_DECISION,
                        "note": VISUAL_REVIEW_NOTE,
                        "audit_id": AUDIT_ID,
                    },
                )
                write_json_atomic(
                    state_path,
                    {
                        "schema_version": 1,
                        "status": "raw_completed",
                        "run_id": PROMOTION_RUN_ID,
                        "recovery_id": RECOVERY_ID,
                        "audit_id": AUDIT_ID,
                        "repository_commit": REPO_COMMIT,
                        "records": len(promotion_records),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                promotion_completed = True
                print("Promoção raw concluída:", PROMOTION_MANIFEST_PATH)
            else:
                print("Promoção protegida: PROMOVER_TRANSCRICOES=False")
            """,
            "publish_reviewed_raw",
        ),
        markdown(
            """
            ## Operação 2 — reconstruir os derivados atuais

            Reexecute o caderno até este ponto depois da promoção. Então defina
            `REGERAR_DERIVADOS=True`, confirme o id da promoção e copie a versão
            da limpeza exibida acima. A normalização e os sete Parquets são
            reconstruídos pelos comandos canônicos do projeto.
            """
        ),
        code(
            """
            if REGERAR_DERIVADOS:
                assert CONFIRM_REBUILD_PROMOTION_RUN_ID == PROMOTION_RUN_ID, (
                    "Copie PROMOTION_RUN_ID para CONFIRM_REBUILD_PROMOTION_RUN_ID."
                )
                assert CONFIRM_DIARY_CLEANING_VERSION == DIARY_CLEANING_VERSION, (
                    "Copie DIARY_CLEANING_VERSION para CONFIRM_DIARY_CLEANING_VERSION."
                )
                manifest_now = read_json(PROMOTION_MANIFEST_PATH)
                assert manifest_now["status"] == "completed"
                assert manifest_now["records"] == EXPECTED_ACCEPTED
                assert (PROMOTION_DIR / "pre_rebuild_state.json").is_file()

                commands = [
                    (
                        [
                            sys.executable, "-u", "-m", "processamento.normalizacao",
                            "--mode", "prod", "--data-root", str(DATA_ROOT),
                            "--run-id", NORMALIZATION_RUN_ID, "--overwrite",
                        ],
                        "normalizar textos current",
                    ),
                    (
                        [
                            sys.executable, "-u", "-m", "processamento.parquet",
                            "--profile", "colab", "--data-root", str(DATA_ROOT),
                            "--run-id", PARQUET_RUN_ID, "--overwrite",
                        ],
                        "gerar sete Parquets",
                    ),
                ]
                for command, label in commands:
                    assert run_streamed(command, label) == 0, label
                print("Derivados reconstruídos.")
            else:
                print("Rebuild protegido: REGERAR_DERIVADOS=False")
            """,
            "rebuild_current_derivatives",
        ),
        markdown(
            """
            ## Validação final e registro de drift

            A validação exige acréscimo exato de 471 linhas no Senado, texto e
            hash esperados para cada promovido, identidade dos demais textos do
            Senado e dos outros cinco Parquets, e mudanças no Congresso
            limitadas aos 83 ids do Diário. Só então o estado operacional recebe
            `validated`.
            """
        ),
        code(
            r'''
            current_target_count = duckdb.connect().execute(
                f"SELECT COUNT(*) FROM read_parquet({quote_literal(SENATE_PARQUET)}) "
                f"WHERE texto_id IN ({target_sql})"
            ).fetchone()[0]
            if current_target_count == EXPECTED_ACCEPTED:
                post_state = {"parquets": {}}
                for name, path in sorted(parquet_paths.items()):
                    post_state["parquets"][name] = parquet_scope(path)
                    print(name, post_state["parquets"][name])

                target_frame = duckdb.connect().execute(
                    f"""
                    SELECT texto_id, texto, metodo_obtencao, raw_run_id
                    FROM read_parquet({quote_literal(SENATE_PARQUET)})
                    WHERE texto_id IN ({target_sql})
                    ORDER BY texto_id
                    """
                ).fetchdf()
                expected_targets = accepted[["speech_id", "legacy_text"]].copy()
                expected_targets["texto_id"] = expected_targets["speech_id"].astype(str).map(
                    lambda value: f"senado:plenario_discursos:pronunciamento:{value}"
                )
                expected_targets["expected_processed_sha256"] = expected_targets["legacy_text"].map(
                    lambda value: hashlib.sha256(processed_text(value).encode("utf-8")).hexdigest()
                )
                target_frame["actual_processed_sha256"] = target_frame["texto"].map(
                    lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest()
                )
                target_check = expected_targets.merge(target_frame, on="texto_id", validate="one_to_one")

                senate_existing = parquet_scope(
                    SENATE_PARQUET, f"texto_id NOT IN ({target_sql})"
                )
                congress_non_diary_post = parquet_scope(
                    CONGRESS_PARQUET,
                    f"COALESCE(metodo_obtencao, '') <> {quote_literal(DIARY_RECOVERY_METHOD)}",
                )
                congress_diary_post = parquet_scope(
                    CONGRESS_PARQUET,
                    f"metodo_obtencao = {quote_literal(DIARY_RECOVERY_METHOD)}",
                )
                unaffected_names = expected_parquet_names - {
                    "senado__plenario_discursos.parquet",
                    "senado__congresso_discursos.parquet",
                }
                validation_gates = {
                    "target_count_exact": len(target_frame) == EXPECTED_ACCEPTED,
                    "target_ids_unique": bool(target_frame["texto_id"].is_unique),
                    "target_text_hashes_exact": bool(
                        target_check["expected_processed_sha256"].eq(
                            target_check["actual_processed_sha256"]
                        ).all()
                    ),
                    "target_method_exact": bool(target_frame["metodo_obtencao"].eq(PROMOTION_METHOD).all()),
                    "target_raw_run_exact": bool(target_frame["raw_run_id"].eq(PROMOTION_RUN_ID).all()),
                    "senate_delta_exact": (
                        post_state["parquets"]["senado__plenario_discursos.parquet"]["rows"]
                        == pre_rebuild_state["parquets"]["senado__plenario_discursos.parquet"]["rows"]
                        + EXPECTED_ACCEPTED
                    ),
                    "prior_senate_rows_untouched": senate_existing == pre_rebuild_state["parquets"]["senado__plenario_discursos.parquet"],
                    "unaffected_parquets_untouched": all(
                        post_state["parquets"][name] == pre_rebuild_state["parquets"][name]
                        for name in unaffected_names
                    ),
                    "congress_row_count_unchanged": (
                        post_state["parquets"]["senado__congresso_discursos.parquet"]["rows"]
                        == pre_rebuild_state["parquets"]["senado__congresso_discursos.parquet"]["rows"]
                    ),
                    "congress_ids_unchanged": (
                        post_state["parquets"]["senado__congresso_discursos.parquet"]["id_sha256"]
                        == pre_rebuild_state["parquets"]["senado__congresso_discursos.parquet"]["id_sha256"]
                    ),
                    "congress_non_diary_untouched": congress_non_diary_post == pre_rebuild_state["congress_non_diary"],
                    "diary_population_same": (
                        congress_diary_post["rows"] == EXPECTED_DIARY
                        and congress_diary_post["id_sha256"] == pre_rebuild_state["congress_diary"]["id_sha256"]
                    ),
                    "diary_text_matches_cleaner_exactly": (
                        congress_diary_post["rows"]
                        == pre_rebuild_state["expected_congress_diary_cleaned"]["rows"]
                        and congress_diary_post["id_sha256"]
                        == pre_rebuild_state["expected_congress_diary_cleaned"]["id_sha256"]
                        and congress_diary_post["id_text_sha256"]
                        == pre_rebuild_state["expected_congress_diary_cleaned"]["id_text_sha256"]
                    ),
                    "diary_text_changed": (
                        congress_diary_post["id_text_sha256"] != pre_rebuild_state["congress_diary"]["id_text_sha256"]
                    ),
                }
                display(validation_gates)
                assert all(validation_gates.values()), validation_gates

                final_report = {
                    "schema_version": 1,
                    "status": "validated",
                    "run_id": PROMOTION_RUN_ID,
                    "recovery_id": RECOVERY_ID,
                    "audit_id": AUDIT_ID,
                    "repository_commit": REPO_COMMIT,
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                    "promotion_method": PROMOTION_METHOD,
                    "diary_cleaning_version": DIARY_CLEANING_VERSION,
                    "promoted_records": EXPECTED_ACCEPTED,
                    "diary_records": EXPECTED_DIARY,
                    "diary_records_changed_in_preview": changed_count,
                    "gates": validation_gates,
                    "pre_rebuild": pre_rebuild_state,
                    "post_rebuild": post_state,
                }
                write_json_atomic(PROMOTION_DIR / "validation.json", final_report)
                state = read_json(PROMOTION_DIR / "promotion_state.json")
                state.update({"status": "validated", "validated_at": final_report["validated_at"]})
                write_json_atomic(PROMOTION_DIR / "promotion_state.json", state)
                print("PROMOÇÃO E REBUILD VALIDADOS:", PROMOTION_DIR)
            else:
                print(
                    "Validação final aguardando o rebuild: alvos presentes =",
                    current_target_count,
                    "de",
                    EXPECTED_ACCEPTED,
                )
            ''',
            "validate_promotion_and_drift",
        ),
        markdown(
            """
            ## Encerramento

            Quando a última célula registrar `validated`, os 471 textos passam
            a integrar o Senado e os 83 textos do Diário ficam limpos apenas nos
            derivados. O raw continua auditável. Os 260 vínculos manuais, 257
            candidatos em conflito e 1.221 não encontrados permanecem para
            fluxos separados; este caderno não muda seus estados.
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
