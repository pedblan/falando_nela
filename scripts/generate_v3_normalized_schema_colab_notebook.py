from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "dados_v3" / "02_schema_normalizado_colab.ipynb"


def clean(value: str) -> str:
    return textwrap.dedent(value).strip()


def markdown(value: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_markdown_cell(clean(value))
    cell.metadata["language"] = "pt-BR"
    return cell


def code(value: str, role: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_code_cell(clean(value))
    cell.metadata["falando_nela"] = {"role": role}
    return cell


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        markdown(
            """
            # Passo 02 — evidências para o schema normalizado v3

            Este caderno propõe o contrato de G02 a partir do inventário
            integral aprovado `raw-metadata-full-20260724t184418z`.

            Ele pode:

            - conferir os artefatos de G01 e o fingerprint atual;
            - reler metadados raw em streaming;
            - produzir livro de campos, conflitos, rejeições, aliases,
              amostras estruturais e pacotes GPT;
            - executar, depois de gates humanos, um piloto pareado GPT-5.6.

            Ele **não normaliza registros**, não altera `raw/`, não funde nem
            descarta campos e não interpreta marcadores, oradores ou turnos.
            Todas as flags operacionais nascem desligadas.
            """
        ),
        code(
            """
            MONTAR_DRIVE = False

            if MONTAR_DRIVE:
                from google.colab import drive

                drive.mount("/content/drive")
                print("Drive montado; nenhuma leitura integral foi autorizada.")
            else:
                print("Drive não montado. Altere MONTAR_DRIVE para True no Colab.")
            """,
            "mount_drive_gate",
        ),
        markdown(
            """
            ## 1. Carregar uma revisão identificável

            O Drive é montado antes de qualquer clone, instalação ou import do
            projeto. A implementação exige o SDK oficial da OpenAI, mas só o
            importa na célula de piloto autorizada.
            """
        ),
        code(
            """
            import os
            import subprocess
            import sys
            from pathlib import Path

            REPO_URL = "https://github.com/pedblan/falando_nela.git"
            REPO_REF = "main"
            IN_COLAB = Path("/content").is_dir()
            REPO_DIR = Path("/content/falando_nela") if IN_COLAB else Path.cwd()

            if IN_COLAB:
                if not (REPO_DIR / ".git").exists():
                    subprocess.run(
                        [
                            "git",
                            "clone",
                            "--branch",
                            REPO_REF,
                            "--single-branch",
                            REPO_URL,
                            str(REPO_DIR),
                        ],
                        check=True,
                    )
                else:
                    dirty = subprocess.check_output(
                        ["git", "-C", str(REPO_DIR), "status", "--porcelain"],
                        text=True,
                    ).strip()
                    assert not dirty, f"Clone efêmero com alterações locais: {dirty}"
                    subprocess.run(
                        ["git", "-C", str(REPO_DIR), "fetch", "origin", REPO_REF],
                        check=True,
                    )
                    subprocess.run(
                        ["git", "-C", str(REPO_DIR), "switch", REPO_REF],
                        check=True,
                    )
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(REPO_DIR),
                            "pull",
                            "--ff-only",
                            "origin",
                            REPO_REF,
                        ],
                        check=True,
                    )
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-q",
                        "-r",
                        str(REPO_DIR / "requirements.txt"),
                    ],
                    check=True,
                )

            required = [
                REPO_DIR / "pipeline_dados_v3" / "schema_normalizado.py",
                REPO_DIR
                / "specs"
                / "pipeline_dados_v3"
                / "02_schema_normalizado"
                / "requirements.md",
            ]
            for path in required:
                assert path.exists(), f"Revisão incompleta: {path}"

            os.chdir(REPO_DIR)
            if str(REPO_DIR) not in sys.path:
                sys.path.insert(0, str(REPO_DIR))
            REPO_COMMIT = subprocess.check_output(
                ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            print("Commit carregado:", REPO_COMMIT)
            """,
            "prepare_repository",
        ),
        markdown(
            """
            ## 2. Fixar entradas e saídas

            Informe a localização explícita dos sete artefatos de G01. A saída
            de G02 fica em `/content`, fora do Drive. Arquivos opcionais de
            revisão também devem ser declarativos: nenhum papel semântico é
            inferido pelo código. Preencha também o SHA-256 aprovado do
            `manifest.json`; ele autentica o sétimo artefato, enquanto o
            próprio manifest autentica os outros seis.
            """
        ),
        code(
            """
            from pipeline_dados_v3.schema_normalizado import (
                APPROVED_INVENTORY_OPERATION_ID,
                DEFAULT_OUTPUT_BASE,
                DEFAULT_RAW_ROOT,
                SchemaConfig,
                initialize_field_review,
                prepare_schema_evidence,
                read_jsonl,
                validate_inventory,
            )

            RAW_ROOT = Path("/content/drive/MyDrive/falando_nela/data/raw")
            INVENTORY_ROOT = Path(
                "/content/falando_nela_v3_inventory"
            ) / APPROVED_INVENTORY_OPERATION_ID
            OUTPUT_BASE = Path("/content/falando_nela_v3_schema")
            OPERATION_ID = "schema-evidence-pilot-20260724"
            EXPECTED_INVENTORY_MANIFEST_SHA256 = ""

            FIELD_REVIEW_PATH = Path("/content/revisao_campos_g02.csv")
            MANUAL_ALIASES_PATH = None
            API_CATEGORIES_PATH = None

            assert RAW_ROOT == DEFAULT_RAW_ROOT
            assert OUTPUT_BASE == DEFAULT_OUTPUT_BASE
            assert RAW_ROOT not in OUTPUT_BASE.parents

            schema_config = SchemaConfig(
                raw_root=RAW_ROOT,
                inventory_root=INVENTORY_ROOT,
                output_base=OUTPUT_BASE,
                operation_id=OPERATION_ID,
                code_commit=REPO_COMMIT,
                expected_inventory_manifest_sha256=(
                    EXPECTED_INVENTORY_MANIFEST_SHA256
                ),
                field_review_path=FIELD_REVIEW_PATH,
                manual_alias_path=MANUAL_ALIASES_PATH,
                api_categories_path=API_CATEGORIES_PATH,
                progress_every_files=50,
            )
            print("Inventário aprovado:", INVENTORY_ROOT)
            print("Saída temporária:", schema_config.operation_root)
            """,
            "configure_paths",
        ),
        markdown(
            """
            ## 3. Validar G01 sem preparar G02

            Esta célula recalcula hashes e confere os totais vinculantes. Ela
            também calcula o fingerprint do raw na etapa de preparação; uma
            divergência bloqueia a execução.
            """
        ),
        code(
            """
            VALIDAR_G01 = False
            CONFIRMAR_INVENTORY_OPERATION_ID = ""

            inventory_manifest = None
            if VALIDAR_G01:
                assert MONTAR_DRIVE, "Monte o Drive antes de validar G01."
                assert (
                    CONFIRMAR_INVENTORY_OPERATION_ID
                    == APPROVED_INVENTORY_OPERATION_ID
                ), "Copie literalmente o operation_id aprovado."
                inventory_manifest, inventory_fields, inventory_issues = (
                    validate_inventory(schema_config)
                )
                print("G01 conferido:", inventory_manifest["operation_id"])
                print("Caminhos:", len(inventory_fields))
                print("Inconsistências:", len(inventory_issues))
            else:
                print("Validação de G01 bloqueada.")
            """,
            "validate_g01_gate",
        ),
        markdown(
            """
            ## 4. Inicializar e revisar o livro de campos

            Esta etapa não abre registros raw. Ela cria, a partir do inventário,
            uma linha para cada caminho observado. Classifique explicitamente
            `semantic_role` como `metadata`, `text`, `technical_control` ou
            `unknown`; mantenha decisões humanas e justificativas no mesmo CSV.
            O arquivo nunca é sobrescrito automaticamente.
            """
        ),
        code(
            """
            GERAR_TEMPLATE_REVISAO = False

            if GERAR_TEMPLATE_REVISAO:
                assert VALIDAR_G01, "Valide G01 primeiro."
                template_path = initialize_field_review(
                    schema_config,
                    FIELD_REVIEW_PATH,
                )
                print("Template criado:", template_path)
                print(
                    "Revise semantic_role e decision antes da releitura integral."
                )
            else:
                print("Geração do template bloqueada.")
            """,
            "initialize_field_review_gate",
        ),
        markdown(
            """
            ## 5. Preparar somente evidências de G02

            A releitura é integral e somente leitura. Strings de campos que
            permaneçam `unknown` ficam redigidas nas amostras estruturais;
            previews só são gerados para campos classificados como `text`.
            """
        ),
        code(
            """
            PREPARAR_EVIDENCIAS = False
            CONFIRMAR_SCHEMA_OPERATION_ID = ""
            schema_result = None

            if PREPARAR_EVIDENCIAS:
                assert MONTAR_DRIVE, "Monte o Drive antes da releitura integral."
                assert VALIDAR_G01, "Valide G01 primeiro."
                assert FIELD_REVIEW_PATH.is_file(), (
                    "Crie e revise o livro de campos antes da releitura."
                )
                assert CONFIRMAR_SCHEMA_OPERATION_ID == OPERATION_ID, (
                    "Copie literalmente OPERATION_ID para confirmar."
                )
                schema_result = prepare_schema_evidence(schema_config)
                print("Evidências preparadas:", schema_result["paths"]["report"])
                print(
                    "Gate científico:",
                    schema_result["manifest"]["scientific_gate"],
                )
            else:
                print("Preparação bloqueada; nenhum registro raw foi relido.")
            """,
            "prepare_evidence_gate",
        ),
        markdown(
            """
            ## 6. Revisar os artefatos

            O livro nasce com `semantic_role=unknown` e
            `decision=nao_avaliado`. Exporte uma cópia revisada para uma nova
            operação; não edite o raw. Previews nascem não aprovados.
            """
        ),
        code(
            """
            import pandas as pd
            from IPython.display import Markdown, display

            if schema_result is None:
                print("Evidências ainda não preparadas.")
            else:
                paths = schema_result["paths"]
                display(Markdown(paths["report"].read_text(encoding="utf-8")))
                display(pd.read_csv(paths["field_book"]).head(30))
                display(pd.read_csv(paths["aliases"]).head(30))
                packet_rows = read_jsonl(paths["gpt_packets"])
                display(
                    pd.DataFrame(
                        [
                            {
                                "packet_id": row["packet_id"],
                                "source": row["source"],
                                "dataset": row["dataset"],
                                "record_type": row["record_type"],
                                "chunk_index": row["chunk_index"],
                                "field_count": len(row["structural_evidence"]),
                                "alias_count": len(row["alias_metrics"]),
                            }
                            for row in packet_rows
                        ]
                    )
                )
                previews_df = pd.read_json(paths["previews"], lines=True)
                if previews_df.empty:
                    print(
                        "Sem previews: classifique campos textuais numa revisão "
                        "e execute uma nova operação."
                    )
                else:
                    display(
                        previews_df[
                            [
                                "context_id",
                                "source",
                                "dataset",
                                "record_type",
                                "field_path",
                                "full_length",
                                "preview",
                                "approved_for_gpt",
                            ]
                        ]
                    )
            """,
            "review_artifacts",
        ),
        markdown(
            """
            ## 7. Aprovar previews individualmente

            Liste apenas IDs já lidos pelo pesquisador. A célula limita cada
            trecho a 500 caracteres, mantém `context_only=true` e registra
            responsável, data e justificativa. A aprovação não transforma o
            preview em evidência estrutural.
            """
        ),
        code(
            """
            from datetime import date

            from pipeline_dados_v3.schema_normalizado import (
                read_jsonl,
                write_jsonl,
            )

            APROVAR_PREVIEWS = False
            CONTEXT_IDS_APROVADOS = []
            RESPONSAVEL_PREVIEWS = ""
            JUSTIFICATIVA_PREVIEWS = ""

            if APROVAR_PREVIEWS:
                assert schema_result is not None, "Prepare as evidências primeiro."
                assert CONTEXT_IDS_APROVADOS, "Liste os context_id aprovados."
                assert RESPONSAVEL_PREVIEWS.strip(), "Informe o responsável."
                assert JUSTIFICATIVA_PREVIEWS.strip(), "Informe a justificativa."
                preview_path = schema_result["paths"]["previews"]
                preview_rows = read_jsonl(preview_path)
                known = {row["context_id"] for row in preview_rows}
                requested = set(CONTEXT_IDS_APROVADOS)
                assert requested <= known, f"IDs desconhecidos: {requested - known}"
                for row in preview_rows:
                    if row["context_id"] in requested:
                        assert row["context_only"] is True
                        assert row["end"] - row["start"] <= 500
                        row["approved_for_gpt"] = True
                        row["approval_by"] = RESPONSAVEL_PREVIEWS
                        row["approval_at"] = date.today().isoformat()
                        row["approval_rationale"] = JUSTIFICATIVA_PREVIEWS
                write_jsonl(preview_path, preview_rows)
                print("Previews aprovados:", len(requested))
            else:
                print("Aprovação de previews bloqueada.")
            """,
            "approve_previews_gate",
        ),
        markdown(
            """
            ## 8. Piloto pareado GPT-5.6

            A chave é reutilizada somente de `google.colab.userdata`; ela não é
            exibida nem gravada. Informe um JSON de preços versionado para que
            custo seja calculado. Cada pacote executa A sem previews e B apenas
            com previews aprovados. Não há fallback nem aplicação automática.
            """
        ),
        code(
            """
            EXECUTAR_PILOTO_GPT = False
            CONFIRMAR_PILOTO_OPERATION_ID = ""
            PRICING_JSON = Path("/content/gpt-5.6-pricing.json")
            PILOT_PACKET_IDS = []
            pilot_result = None

            if EXECUTAR_PILOTO_GPT:
                assert APROVAR_PREVIEWS, "Aprove previews antes da condição B."
                assert PILOT_PACKET_IDS, (
                    "Selecione packet_ids estratificados depois da revisão."
                )
                assert (
                    CONFIRMAR_PILOTO_OPERATION_ID == OPERATION_ID
                ), "Copie literalmente OPERATION_ID para confirmar o piloto."
                assert PRICING_JSON.is_file(), "Forneça a tabela de preços."
                if IN_COLAB:
                    from google.colab import userdata

                    api_key = userdata.get("OPENAI_API_KEY")
                    assert api_key, "Cadastre OPENAI_API_KEY nos Secrets do Colab."
                    os.environ["OPENAI_API_KEY"] = api_key

                from pipeline_dados_v3.schema_normalizado import run_gpt_pilot

                pilot_result = run_gpt_pilot(
                    schema_config.operation_root,
                    confirm_operation_id=CONFIRMAR_PILOTO_OPERATION_ID,
                    execute_gpt=True,
                    pricing_path=PRICING_JSON,
                    pilot_packet_ids=set(PILOT_PACKET_IDS),
                    model="gpt-5.6",
                    reasoning_effort="medium",
                )
                print("Chamadas:", len(pilot_result["execution_rows"]))
                print("Gate:", pilot_result["manifest"]["scientific_gate"])
            else:
                print("Piloto GPT bloqueado; nenhuma chamada paga foi feita.")
            """,
            "gpt_pilot_gate",
        ),
        markdown(
            """
            ## 9. Avaliar A/B depois da revisão cega

            A avaliação requer CSV humano com `pair_id`, `condition`,
            `proposal_id`, `accepted`, `unsupported_category`,
            `incorrect_alias` e `insufficient_evidence`. G02 continua pendente
            depois do cálculo.
            """
        ),
        code(
            """
            AVALIAR_AB = False
            REVIEW_CSV = Path("/content/revisao_propostas_gpt.csv")
            DECISAO_HUMANA_PREVIEWS = ""

            if AVALIAR_AB:
                assert pilot_result is not None, "Execute e revise o piloto primeiro."
                assert REVIEW_CSV.is_file(), "Forneça o CSV de revisão humana."
                from pipeline_dados_v3.schema_normalizado import (
                    evaluate_context_ab,
                )

                ab_rows = evaluate_context_ab(
                    schema_config.operation_root,
                    review_path=REVIEW_CSV,
                    human_preview_decision=DECISAO_HUMANA_PREVIEWS,
                )
                display(pd.DataFrame(ab_rows))
                print("Avaliação pronta; G02 ainda exige decisão humana.")
            else:
                print("Avaliação A/B bloqueada.")
            """,
            "evaluate_ab_gate",
        ),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.update(
        {
            "colab": {"name": OUTPUT.name, "provenance": []},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
            "falando_nela": {
                "pipeline": "v3",
                "step": "02_schema_normalizado",
                "scientific_gate": "needs_review",
            },
        }
    )
    return notebook


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(build_notebook(), OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
