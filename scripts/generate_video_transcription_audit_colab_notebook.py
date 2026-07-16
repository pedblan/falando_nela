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
    / "11_auditoria_transcricoes_e_amostras_plenario_colab.ipynb"
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
            # Auditoria segura das transcrições e amostras integrais de plenário

            Este caderno revisa a recuperação operacional de transcrições do
            Senado sem promover textos ao corpus. Também testa a hipótese de que
            o portal da Câmara já fornece transcrições para suas unidades com
            mídia e mostra amostras integrais reproduzíveis de 2010, 2015 e 2016
            em Câmara, Senado e Congresso.

            O fluxo:

            1. audita uma amostra dos vínculos fortes recuperados;
            2. separa conflitos por causa;
            3. prepara amostras dos vínculos manuais;
            4. mede por ano os candidatos não encontrados no legado;
            5. mede a cobertura texto/mídia da Câmara;
            6. exibe textos integrais dos anos problemáticos, com amostra extra
               dos registros obtidos no Diário.

            Todas as leituras usam o Drive. A escrita fica desligada por padrão
            e, quando confirmada, ocorre somente em `operations/auditorias/`.
            `raw/`, `processed/`, Parquets canônicos e snapshots não são
            alterados.
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
            RECOVERY_DIR = (
                DATA_ROOT
                / "operations"
                / "recuperacoes"
                / "transcricoes_legadas"
                / RECOVERY_ID
            )

            AUDIT_ID = "auditoria-transcricoes-plenario-2010-2015-2016-20260716-v1"
            AUDIT_DIR = (
                DATA_ROOT
                / "operations"
                / "auditorias"
                / "transcricoes_legadas"
                / AUDIT_ID
            )

            TARGET_YEARS = (2010, 2015, 2016)
            RANDOM_SEED = 20260716
            ACCEPTED_SAMPLES_PER_STRATUM = 3
            MANUAL_SAMPLES_PER_STRATUM = 3
            GENERAL_SAMPLES_PER_ARENA_YEAR = 2
            DIARY_SAMPLES_PER_ARENA_YEAR = 3

            GRAVAR_AUDITORIA = False
            CONFIRM_AUDIT_ID = ""

            assert DATA_ROOT.is_dir(), f"Raiz de dados ausente: {DATA_ROOT}"
            assert RECOVERY_DIR.is_dir(), f"Recuperação operacional ausente: {RECOVERY_DIR}"
            assert "operations" in AUDIT_DIR.parts
            assert "raw" not in AUDIT_DIR.parts and "processed" not in AUDIT_DIR.parts
            print("Recuperação lida:", RECOVERY_DIR)
            print("Auditoria:", AUDIT_DIR)
            print("Anos:", TARGET_YEARS, "| semente:", RANDOM_SEED)
            """,
            "configure_audit",
        ),
        markdown(
            """
            ## Funções de auditoria e exibição

            As amostras são pseudoaleatórias e reproduzíveis: uma ordenação por
            SHA-256 combina a semente e o identificador estável. Os textos
            integrais aparecem em cartões recolhíveis para permitir inspeção de
            cabeçalhos, separadores e marcas editoriais sem truncamento.
            """
        ),
        code(
            r'''
            import hashlib
            import html
            import importlib
            import json

            import duckdb
            import pandas as pd
            from IPython.display import HTML, display
            from coleta import transcricoes_audiovisuais

            transcricoes_audiovisuais = importlib.reload(transcricoes_audiovisuais)
            assert getattr(transcricoes_audiovisuais, "INVENTORY_CODE_VERSION", 0) >= 3, (
                "Módulo antigo ainda carregado. Reexecute a preparação do repositório."
            )
            assert "/content/falando_nela/" in str(transcricoes_audiovisuais.__file__)
            print("Módulo:", transcricoes_audiovisuais.__file__)
            print("Versão do inventário:", transcricoes_audiovisuais.INVENTORY_CODE_VERSION)


            def sha256_text(value):
                return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()


            def sha256_file(path):
                digest = hashlib.sha256()
                with Path(path).open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                return digest.hexdigest()


            def stable_sample(frame, group_columns, size, seed, identity_column="candidate_id"):
                if frame.empty:
                    return frame.copy()
                sampled = frame.copy()
                sampled["_sample_rank"] = sampled[identity_column].fillna("").astype(str).map(
                    lambda value: hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()
                )
                sampled = sampled.sort_values([*group_columns, "_sample_rank"], kind="stable")
                sampled = sampled.groupby(group_columns, dropna=False, sort=True).head(size)
                return sampled.drop(columns="_sample_rank").reset_index(drop=True)


            def present(value):
                if value is None:
                    return False
                if isinstance(value, str):
                    return bool(value)
                try:
                    return not bool(pd.isna(value))
                except (TypeError, ValueError):
                    return True


            def text_cards(frame, *, text_column, title):
                parts = [f"<h3>{html.escape(title)}</h3>"]
                if frame.empty:
                    return "".join(parts + ["<p>Nenhum texto nesta seleção.</p>"])
                metadata_fields = [
                    "amostra_tipo", "arena", "audit_year", "year", "date", "data",
                    "candidate_id", "texto_id", "speaker_name", "parlamentar_nome",
                    "match_method", "match_score", "metodo_obtencao", "raw_run_id",
                    "raw_source_id", "raw_path", "url_texto",
                ]
                for row in frame.to_dict("records"):
                    summary = " | ".join(
                        f"{field}={row.get(field)}"
                        for field in metadata_fields
                        if present(row.get(field))
                    )
                    text_value = row.get(text_column)
                    text = str(text_value) if present(text_value) else ""
                    parts.append(
                        "<details style='margin:0.7em 0'>"
                        f"<summary><strong>{html.escape(summary or 'texto')}</strong></summary>"
                        "<pre style='white-space:pre-wrap;overflow-wrap:anywhere;"
                        "border:1px solid #ddd;padding:1em;background:#fafafa'>"
                        f"{html.escape(text)}</pre></details>"
                    )
                return "".join(parts)


            def json_records(frame):
                return json.loads(frame.to_json(orient="records", date_format="iso"))


            def quote_literal(value):
                return "'" + str(value).replace("'", "''") + "'"
            ''',
            "define_audit_helpers",
        ),
        markdown(
            """
            ## Carregar e reconciliar as saídas operacionais

            Esta etapa exige todos os artefatos do caderno 10 e confirma que as
            contagens persistidas ainda coincidem com `summary.json`.
            """
        ),
        code(
            """
            INPUT_PATHS = {
                "accepted": RECOVERY_DIR / "recovered_legacy_texts.parquet",
                "manual_review": RECOVERY_DIR / "legacy_matches_manual_review.parquet",
                "conflicts": RECOVERY_DIR / "legacy_match_conflicts.parquet",
                "candidate_status": RECOVERY_DIR / "candidate_status.csv",
                "camara_queue": RECOVERY_DIR / "camara_media_download_queue.parquet",
                "summary": RECOVERY_DIR / "summary.json",
            }
            missing_inputs = [str(path) for path in INPUT_PATHS.values() if not path.is_file()]
            assert not missing_inputs, f"Artefatos operacionais ausentes: {missing_inputs}"

            recovery_summary = json.loads(INPUT_PATHS["summary"].read_text(encoding="utf-8"))
            accepted = pd.read_parquet(INPUT_PATHS["accepted"])
            manual_review = pd.read_parquet(INPUT_PATHS["manual_review"])
            conflicts = pd.read_parquet(INPUT_PATHS["conflicts"])
            candidate_status = pd.read_csv(INPUT_PATHS["candidate_status"], dtype={"candidate_id": str})
            camara_queue = pd.read_parquet(INPUT_PATHS["camara_queue"])

            assert len(accepted) == recovery_summary["accepted_strong_key"]
            assert len(manual_review) == recovery_summary["manual_review"]
            assert len(conflicts) == recovery_summary["conflicts"]
            assert len(candidate_status) == recovery_summary["current_candidates"]
            assert accepted["candidate_id"].is_unique
            assert candidate_status["candidate_id"].is_unique
            assert accepted.empty or accepted["house"].eq("senado").all()

            display(pd.DataFrame([
                {"artefato": "aceitos", "linhas": len(accepted)},
                {"artefato": "revisão manual", "linhas": len(manual_review)},
                {"artefato": "conflitos (correspondências)", "linhas": len(conflicts)},
                {"artefato": "candidatos", "linhas": len(candidate_status)},
                {"artefato": "fila Câmara", "linhas": len(camara_queue)},
            ]))
            """,
            "load_operational_outputs",
        ),
        markdown(
            """
            ## 1. Amostra dos vínculos fortes

            O vínculo forte valida identidade, não qualidade textual. Aqui o
            hash e o comprimento são recalculados, e uma amostra por
            método/ano é exibida integralmente para inspeção humana.
            """
        ),
        code(
            """
            accepted = accepted.copy()
            accepted["audit_year"] = pd.to_datetime(accepted["date"], errors="coerce").dt.year.astype("Int64")
            accepted["recomputed_text_sha256"] = accepted["legacy_text"].map(sha256_text)
            accepted["sha256_valid"] = accepted["recomputed_text_sha256"].eq(
                accepted["legacy_text_sha256"].astype(str)
            )
            accepted["recomputed_text_length"] = accepted["legacy_text"].fillna("").astype(str).str.strip().str.len()
            accepted["length_valid"] = accepted["recomputed_text_length"].eq(
                pd.to_numeric(accepted["legacy_text_length"], errors="coerce")
            )
            accepted_sample = stable_sample(
                accepted,
                ["match_method", "audit_year"],
                ACCEPTED_SAMPLES_PER_STRATUM,
                RANDOM_SEED,
            )

            accepted_audit = pd.DataFrame([{
                "accepted_rows": len(accepted),
                "unique_candidates": accepted["candidate_id"].nunique(),
                "valid_sha256": int(accepted["sha256_valid"].sum()),
                "valid_lengths": int(accepted["length_valid"].sum()),
                "sample_rows": len(accepted_sample),
            }])
            display(accepted_audit)
            display(
                accepted.groupby(["match_method", "audit_year"], dropna=False)
                .size().rename("rows").reset_index()
            )
            display(HTML(text_cards(
                accepted_sample,
                text_column="legacy_text",
                title="Amostra integral dos recuperados por chave forte",
            )))
            """,
            "audit_accepted_recoveries",
        ),
        markdown(
            """
            ## 2. Separar conflitos por causa

            `legacy_match_conflicts.parquet` conta correspondências, não apenas
            candidatos. A tabela abaixo reduz os conflitos ao nível do
            candidato e distingue múltiplas versões de texto de uma mesma linha
            legada compartilhada por candidatos diferentes.
            """
        ),
        code(
            """
            conflicts = conflicts.copy()
            conflicts["audit_year"] = pd.to_datetime(conflicts["date"], errors="coerce").dt.year.astype("Int64")
            fingerprint_candidate_counts = conflicts.groupby("legacy_row_fingerprint")[
                "candidate_id"
            ].nunique()
            shared_fingerprints = set(
                fingerprint_candidate_counts[fingerprint_candidate_counts.gt(1)].index
            )

            cause_rows = []
            for candidate_id, group in conflicts.groupby("candidate_id", sort=True):
                text_variants = group["legacy_text_sha256"].nunique()
                ambiguous_rows = group.loc[
                    group["legacy_row_fingerprint"].isin(shared_fingerprints),
                    "legacy_row_fingerprint",
                ].nunique()
                multiple_texts = text_variants > 1
                shared_legacy = ambiguous_rows > 0
                if multiple_texts and shared_legacy:
                    cause = "multiple_text_variants_and_shared_legacy_row"
                elif multiple_texts:
                    cause = "multiple_text_variants"
                elif shared_legacy:
                    cause = "shared_legacy_row"
                else:
                    cause = "unclassified"
                cause_rows.append({
                    "candidate_id": candidate_id,
                    "audit_year": group["audit_year"].iloc[0],
                    "match_rows": len(group),
                    "text_variants": int(text_variants),
                    "legacy_rows": int(group["legacy_row_fingerprint"].nunique()),
                    "ambiguous_legacy_rows": int(ambiguous_rows),
                    "match_methods": "|".join(sorted(set(group["match_method"].astype(str)))),
                    "conflict_cause": cause,
                })
            conflict_causes = pd.DataFrame(cause_rows)

            conflict_id_sample = stable_sample(
                conflict_causes,
                ["conflict_cause"],
                2,
                RANDOM_SEED,
            )
            conflict_variant_sample = conflicts.loc[
                conflicts["candidate_id"].isin(conflict_id_sample["candidate_id"])
            ].sort_values(["candidate_id", "legacy_text_sha256"])

            display(conflict_causes.groupby("conflict_cause").size().rename("candidates").reset_index())
            display(
                conflict_causes.groupby(["audit_year", "conflict_cause"], dropna=False)
                .size().rename("candidates").reset_index()
            )
            display(conflict_causes.sort_values(["text_variants", "match_rows"], ascending=False).head(30))
            display(HTML(text_cards(
                conflict_variant_sample,
                text_column="legacy_text",
                title="Variantes integrais de uma pequena amostra de conflitos",
            )))
            """,
            "classify_conflict_causes",
        ),
        markdown(
            """
            ## 3. Amostra dos vínculos para revisão manual

            Esses casos usam parlamentar, data e sessão e nunca são aceitos
            automaticamente. A amostra por método/ano serve para comparar autor,
            contexto e texto integral.
            """
        ),
        code(
            """
            manual_review = manual_review.copy()
            manual_review["audit_year"] = pd.to_datetime(
                manual_review["date"], errors="coerce"
            ).dt.year.astype("Int64")
            manual_sample = stable_sample(
                manual_review,
                ["match_method", "audit_year"],
                MANUAL_SAMPLES_PER_STRATUM,
                RANDOM_SEED,
            )
            assert manual_review.empty or manual_review["match_score"].lt(90).all()

            display(
                manual_review.groupby(["match_method", "audit_year"], dropna=False)
                .size().rename("rows").reset_index()
            )
            display(HTML(text_cards(
                manual_sample,
                text_column="legacy_text",
                title="Amostra integral dos vínculos de revisão manual",
            )))
            """,
            "audit_manual_review",
        ),
        markdown(
            """
            ## 4. Distribuição anual dos não encontrados

            A distribuição ajuda a distinguir uma lacuna concentrada em um
            período de simples falhas de chave espalhadas no tempo.
            """
        ),
        code(
            """
            not_found = candidate_status.loc[
                candidate_status["workflow_status"].eq("not_found_in_legacy")
            ].copy()
            not_found["year"] = pd.to_numeric(not_found["year"], errors="coerce").astype("Int64")
            not_found_by_year = (
                not_found.groupby(["house", "year"], dropna=False)
                .size().rename("candidates").reset_index()
                .sort_values(["house", "year"], na_position="last")
            )
            not_found_by_year["share_within_status"] = (
                not_found_by_year["candidates"] / max(len(not_found), 1)
            )

            display(not_found_by_year)
            print("Total não encontrado:", len(not_found))
            """,
            "summarize_not_found_by_year",
        ),
        markdown(
            """
            ## 5. A Câmara já transcreveu as unidades com mídia?

            A auditoria lê apenas o corpus mensal. Ela mede ocorrências e
            unidades únicas, pois o mesmo discurso pode reaparecer em runs
            distintos. Uma unidade com mídia só fica pendente se nenhuma
            ocorrência tiver `transcricao`.
            """
        ),
        code(
            """
            camara_coverage = pd.DataFrame(
                transcricoes_audiovisuais.audit_camara_transcription_coverage(
                    DATA_ROOT, progress=print
                )
            )
            assert not camara_coverage.empty, "Corpus mensal da Câmara não encontrado"
            current_camara_pending = int(
                camara_coverage["unique_pending_media_transcription"].sum()
            )
            prior_camara_pending = len(camara_queue)
            camara_diagnostics = {
                "current_unique_pending_media_transcription": current_camara_pending,
                "prior_probe_queue_rows": prior_camara_pending,
                "same_as_prior_probe": current_camara_pending == prior_camara_pending,
                "all_observed_media_units_have_text": current_camara_pending == 0,
            }

            display(camara_coverage)
            display(camara_coverage.loc[
                camara_coverage["year"].isin(TARGET_YEARS),
                [
                    "year", "unique_units", "unique_units_with_text",
                    "unique_units_with_media", "unique_units_with_media_and_text",
                    "unique_pending_media_transcription", "text_coverage_rate",
                    "media_text_coverage_rate",
                ],
            ])
            display(camara_diagnostics)
            """,
            "audit_camara_media_text_coverage",
        ),
        markdown(
            """
            ## Amostras integrais de 2010, 2015 e 2016

            A amostra geral contém até dois textos por arena/ano. Além dela, o
            caderno procura até três textos por arena/ano cuja proveniência
            mencione `diario`, dando prioridade aos pronunciamentos recuperados
            do Diário do Congresso. A ordenação por hash funciona como sorteio
            reproduzível com semente fixa.
            """
        ),
        code(
            r'''
            PARQUET_ROOT = DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"
            ARENA_PARQUETS = {
                "camara": PARQUET_ROOT / "camara__plenario_discursos.parquet",
                "senado": PARQUET_ROOT / "senado__plenario_discursos.parquet",
                "congresso": PARQUET_ROOT / "senado__congresso_discursos.parquet",
            }
            missing_parquets = [str(path) for path in ARENA_PARQUETS.values() if not path.is_file()]
            assert not missing_parquets, f"Parquets canônicos ausentes: {missing_parquets}"

            target_years_sql = ", ".join(str(year) for year in TARGET_YEARS)
            diary_expression = """
                LOWER(CONCAT_WS(' ',
                    COALESCE(CAST(metodo_obtencao AS VARCHAR), ''),
                    COALESCE(CAST(raw_run_id AS VARCHAR), ''),
                    COALESCE(CAST(raw_source_id AS VARCHAR), ''),
                    COALESCE(CAST(raw_path AS VARCHAR), ''),
                    COALESCE(CAST(url_texto AS VARCHAR), ''),
                    COALESCE(CAST(fontes AS VARCHAR), '')
                )) LIKE '%diario%'
            """
            connection = duckdb.connect()
            inventory_parts = []
            for arena, path in ARENA_PARQUETS.items():
                inventory_parts.append(connection.execute(f"""
                    SELECT
                        {quote_literal(arena)} AS arena,
                        TRY_CAST(ano AS INTEGER) AS year,
                        COUNT(*) AS rows,
                        SUM(CASE WHEN LENGTH(TRIM(COALESCE(texto, ''))) > 0 THEN 1 ELSE 0 END)
                            AS nonempty_text_rows,
                        SUM(CASE WHEN {diary_expression} THEN 1 ELSE 0 END) AS diary_rows
                    FROM read_parquet({quote_literal(path)})
                    WHERE TRY_CAST(ano AS INTEGER) IN ({target_years_sql})
                    GROUP BY 1, 2
                """).fetchdf())
            historical_inventory = pd.concat(inventory_parts, ignore_index=True).sort_values(
                ["arena", "year"]
            )


            def sample_parquet(arena, path, year, size, *, diary_only):
                diary_filter = f"AND ({diary_expression})" if diary_only else ""
                sample_type = "prioridade_diario" if diary_only else "aleatoria_geral"
                seed_material = f"{RANDOM_SEED}:{arena}:{year}:{sample_type}"
                return connection.execute(f"""
                    SELECT
                        {quote_literal(sample_type)} AS amostra_tipo,
                        {quote_literal(arena)} AS arena,
                        TRY_CAST(ano AS INTEGER) AS year,
                        CAST(texto_id AS VARCHAR) AS texto_id,
                        CAST(casa AS VARCHAR) AS casa,
                        CAST(data AS VARCHAR) AS data,
                        CAST(parlamentar_nome AS VARCHAR) AS parlamentar_nome,
                        CAST(tipo_discurso AS VARCHAR) AS tipo_discurso,
                        CAST(titulo AS VARCHAR) AS titulo,
                        CAST(metodo_obtencao AS VARCHAR) AS metodo_obtencao,
                        CAST(raw_run_id AS VARCHAR) AS raw_run_id,
                        CAST(raw_source_id AS VARCHAR) AS raw_source_id,
                        CAST(raw_path AS VARCHAR) AS raw_path,
                        CAST(url_texto AS VARCHAR) AS url_texto,
                        CAST(texto AS VARCHAR) AS texto,
                        TRY_CAST(texto_tamanho AS BIGINT) AS texto_tamanho
                    FROM read_parquet({quote_literal(path)})
                    WHERE TRY_CAST(ano AS INTEGER) = {int(year)}
                      AND LENGTH(TRIM(COALESCE(texto, ''))) > 0
                      {diary_filter}
                    ORDER BY hash(
                        COALESCE(CAST(texto_id AS VARCHAR), '') || {quote_literal(seed_material)}
                    )
                    LIMIT {int(size)}
                """).fetchdf()


            general_parts = []
            diary_parts = []
            for arena, path in ARENA_PARQUETS.items():
                for year in TARGET_YEARS:
                    general_parts.append(sample_parquet(
                        arena,
                        path,
                        year,
                        GENERAL_SAMPLES_PER_ARENA_YEAR,
                        diary_only=False,
                    ))
                    diary_parts.append(sample_parquet(
                        arena,
                        path,
                        year,
                        DIARY_SAMPLES_PER_ARENA_YEAR,
                        diary_only=True,
                    ))

            general_samples = pd.concat(general_parts, ignore_index=True)
            diary_samples = pd.concat(diary_parts, ignore_index=True)
            historical_samples = (
                pd.concat([diary_samples, general_samples], ignore_index=True)
                .drop_duplicates(["arena", "year", "texto_id"], keep="first")
                .sort_values(["arena", "year", "amostra_tipo", "texto_id"])
                .reset_index(drop=True)
            )
            historical_sample_coverage = (
                historical_samples.groupby(["arena", "year", "amostra_tipo"])
                .size().rename("sample_rows").reset_index()
            )

            display(historical_inventory)
            display(historical_sample_coverage)
            display(historical_samples.drop(columns="texto"))
            historical_cards_html = text_cards(
                historical_samples,
                text_column="texto",
                title="Textos integrais sorteados por arena e ano",
            )
            display(HTML(historical_cards_html))
            ''',
            "sample_historical_full_texts",
        ),
        markdown(
            """
            ## Gates, proveniência e exportação opcional

            Gates estruturais protegem a auditoria. Diagnósticos substantivos,
            como a existência de pendências na Câmara ou a ausência de textos
            do Diário no Parquet atual, são registrados como achados e não são
            convertidos automaticamente em decisões.
            """
        ),
        code(
            r'''
            status_counts = candidate_status["workflow_status"].value_counts()
            expected_combinations = {
                (arena, year) for arena in ARENA_PARQUETS for year in TARGET_YEARS
            }
            inventory_combinations = set(
                historical_inventory.loc[historical_inventory["rows"].gt(0), ["arena", "year"]]
                .itertuples(index=False, name=None)
            )
            sample_combinations = set(
                historical_samples[["arena", "year"]].itertuples(index=False, name=None)
            )

            structural_gates = {
                "accepted_hashes_valid": bool(accepted["sha256_valid"].all()),
                "accepted_lengths_valid": bool(accepted["length_valid"].all()),
                "accepted_candidates_unique": bool(accepted["candidate_id"].is_unique),
                "manual_candidates_reconciled": int(status_counts.get("manual_review", 0))
                    == manual_review["candidate_id"].nunique(),
                "conflict_candidates_reconciled": int(status_counts.get("conflict", 0))
                    == conflicts["candidate_id"].nunique()
                    == len(conflict_causes),
                "not_found_candidates_reconciled": int(status_counts.get("not_found_in_legacy", 0))
                    == len(not_found),
                "recovery_is_senate_only": bool(accepted.empty or accepted["house"].eq("senado").all()),
                "camara_coverage_audited": bool(not camara_coverage.empty),
                "historical_combinations_present": expected_combinations.issubset(inventory_combinations),
                "historical_samples_cover_combinations": expected_combinations.issubset(sample_combinations),
                "historical_sample_texts_nonempty": bool(
                    historical_samples["texto"].fillna("").astype(str).str.strip().ne("").all()
                ),
                "canonical_outputs_untouched": True,
            }
            findings = {
                **camara_diagnostics,
                "historical_diary_rows": int(historical_inventory["diary_rows"].sum()),
                "historical_diary_sample_rows": len(diary_samples),
                "missing_historical_combinations": sorted(expected_combinations - inventory_combinations),
                "missing_sample_combinations": sorted(expected_combinations - sample_combinations),
            }
            display({"structural_gates": structural_gates, "findings": findings})
            assert all(structural_gates.values()), structural_gates


            def confirmed():
                assert CONFIRM_AUDIT_ID == AUDIT_ID, (
                    "Para gravar, copie AUDIT_ID exatamente para CONFIRM_AUDIT_ID."
                )


            if GRAVAR_AUDITORIA:
                confirmed()
                assert not AUDIT_DIR.exists(), (
                    f"Auditoria imutável já existe: {AUDIT_DIR}. Defina outro AUDIT_ID."
                )
                AUDIT_DIR.mkdir(parents=True, exist_ok=False)

                accepted_sample.to_parquet(AUDIT_DIR / "accepted_review_sample.parquet", index=False)
                manual_sample.to_parquet(AUDIT_DIR / "manual_review_sample.parquet", index=False)
                conflict_causes.to_parquet(AUDIT_DIR / "conflict_causes.parquet", index=False)
                conflict_causes.to_csv(AUDIT_DIR / "conflict_causes.csv", index=False)
                conflict_variant_sample.to_parquet(
                    AUDIT_DIR / "conflict_variant_sample.parquet", index=False
                )
                not_found_by_year.to_csv(AUDIT_DIR / "not_found_by_year.csv", index=False)
                camara_coverage.to_csv(AUDIT_DIR / "camara_transcription_coverage.csv", index=False)
                historical_inventory.to_csv(AUDIT_DIR / "historical_inventory.csv", index=False)
                historical_samples.to_parquet(
                    AUDIT_DIR / "historical_full_text_samples.parquet", index=False
                )
                report_path = AUDIT_DIR / "historical_full_text_samples.html"
                report_path.write_text(
                    "<!doctype html><meta charset='utf-8'><title>Amostras integrais</title>"
                    + historical_cards_html,
                    encoding="utf-8",
                )

                output_paths = sorted(
                    path for path in AUDIT_DIR.iterdir() if path.name != "provenance.json"
                )
                provenance = {
                    "schema_version": 1,
                    "analysis_run_id": AUDIT_ID,
                    "compared_to": None,
                    "recovery_id": RECOVERY_ID,
                    "repository_commit": REPO_COMMIT,
                    "notebooks": [
                        "notebooks/coleta/11_auditoria_transcricoes_e_amostras_plenario_colab.ipynb"
                    ],
                    "parameters": {
                        "target_years": list(TARGET_YEARS),
                        "accepted_samples_per_stratum": ACCEPTED_SAMPLES_PER_STRATUM,
                        "manual_samples_per_stratum": MANUAL_SAMPLES_PER_STRATUM,
                        "general_samples_per_arena_year": GENERAL_SAMPLES_PER_ARENA_YEAR,
                        "diary_samples_per_arena_year": DIARY_SAMPLES_PER_ARENA_YEAR,
                    },
                    "random_seeds": {"stable_sha256_order": RANDOM_SEED},
                    "inputs": {
                        name: {
                            "path": str(path),
                            "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                        }
                        for name, path in {**INPUT_PATHS, **{
                            f"parquet_{arena}": path for arena, path in ARENA_PARQUETS.items()
                        }}.items()
                    },
                    "structural_gates": structural_gates,
                    "findings": findings,
                    "counts": {
                        "accepted": len(accepted),
                        "manual_review": len(manual_review),
                        "conflict_match_rows": len(conflicts),
                        "conflict_candidates": len(conflict_causes),
                        "not_found": len(not_found),
                        "historical_sample_rows": len(historical_samples),
                    },
                    "camara_coverage": json_records(camara_coverage),
                    "historical_inventory": json_records(historical_inventory),
                    "outputs": [
                        {
                            "path": str(path),
                            "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                        }
                        for path in output_paths
                    ],
                    "canonical_outputs_untouched": True,
                }
                (AUDIT_DIR / "provenance.json").write_text(
                    json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print("Auditoria gravada em:", AUDIT_DIR)
            else:
                print("Escrita protegida. Revise as tabelas e os textos antes de gravar.")
            ''',
            "validate_and_export_audit",
        ),
        markdown(
            """
            ## Como interpretar o encerramento

            - Se `all_observed_media_units_have_text=True`, a fotografia raw
              sustenta a hipótese de que a Câmara já oferece transcrição para
              todas as unidades com mídia observadas. Isso ainda não mede itens
              ausentes do corpus.
            - Conflitos e vínculos manuais continuam sem decisão automática.
            - `historical_diary_rows` confirma quantos registros dos anos-alvo
              preservam marca explícita de proveniência do Diário no Parquet
              atual.
            - A promoção dos 471 textos recuperados exige um caderno posterior,
              com decisões humanas registradas e um contrato raw versionado.
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
