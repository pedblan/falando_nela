from __future__ import annotations

import textwrap
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "dados_v3" / "01_inventario_metadados_raw_colab.ipynb"


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
            # Passo 01 — inventário de metadados raw v3

            **Objetivo:** observar todos os arquivos, campos, tipos, estados de
            preenchimento e valores de baixa cardinalidade recebidos nas
            coletas, antes de definir categorias normalizadas.

            **Entrada imutável:**
            `/content/drive/MyDrive/falando_nela/data/raw`

            **Saída temporária:**
            `/content/falando_nela_v3_inventory/{operation_id}`

            Este caderno não chama GPT, não requer chave da OpenAI e não grava
            no Drive. Ele executa primeiro um smoke e deixa a leitura integral
            bloqueada para um segundo gate.

            As flags nascem desligadas. `Run all` não autoriza nenhuma leitura
            estruturada do corpus.
            """
        ),
        code(
            """
            MONTAR_DRIVE = False

            if MONTAR_DRIVE:
                from google.colab import drive

                drive.mount("/content/drive")
                print("Drive montado; o inventário ainda está bloqueado.")
            else:
                print("Drive não montado. Altere MONTAR_DRIVE para True no Colab.")
            """,
            "mount_drive_gate",
        ),
        markdown(
            """
            ## 1. Carregar uma revisão identificável

            Depois que esta implementação estiver incorporada à branch
            principal, a célula clonará ou atualizará `main`. O commit exato
            ficará registrado no manifest do inventário.
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

            required = [
                REPO_DIR
                / "pipeline_dados_v3"
                / "inventario_metadados_raw.py",
                REPO_DIR
                / "specs"
                / "pipeline_dados_v3"
                / "01_inventario_metadados_raw"
                / "requirements.md",
            ]
            for path in required:
                assert path.exists(), f"Revisão incompleta do repositório: {path}"

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
            ## 2. Verificar G00 e a raiz exata

            O inventário só pode começar quando `data/` contiver exatamente
            `raw/`. A saída fica em `/content`, fora do Drive.
            """
        ),
        code(
            """
            from pipeline_dados_v3.inventario_metadados_raw import (
                DEFAULT_OUTPUT_BASE,
                DEFAULT_RAW_ROOT,
            )

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            RAW_ROOT = Path("/content/drive/MyDrive/falando_nela/data/raw")
            OUTPUT_BASE = Path("/content/falando_nela_v3_inventory")

            assert RAW_ROOT == DEFAULT_RAW_ROOT
            assert OUTPUT_BASE == DEFAULT_OUTPUT_BASE
            assert RAW_ROOT.parent == DATA_ROOT
            assert DATA_ROOT not in OUTPUT_BASE.parents

            if MONTAR_DRIVE:
                assert DATA_ROOT.is_dir(), f"Raiz de dados ausente: {DATA_ROOT}"
                children = sorted(path.name for path in DATA_ROOT.iterdir())
                print("Filhos atuais de data/:", children)
                assert children == ["raw"], (
                    "G00 bloqueado: data/ deve conter somente raw/ antes "
                    "do inventário v3."
                )
                assert RAW_ROOT.is_dir(), f"Raiz raw ausente: {RAW_ROOT}"
                print("G00 verificado.")
            else:
                print("G00 não verificado porque o Drive não está montado.")
            """,
            "verify_g00",
        ),
        markdown(
            """
            ## 3. Configurar o smoke

            O smoke cataloga toda a árvore, mas abre no máximo dois arquivos
            por combinação `fonte × dataset × formato`. Strings longas não
            aparecem nas saídas: são representadas somente por tamanho e hash.
            """
        ),
        code(
            """
            from datetime import datetime, timezone

            from pipeline_dados_v3.inventario_metadados_raw import (
                InventoryConfig,
                run_inventory,
            )

            if "SMOKE_OPERATION_ID" not in globals():
                SMOKE_OPERATION_ID = (
                    "raw-metadata-smoke-"
                    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
                )

            SMOKE_FILES_PER_GROUP = 2
            EXECUTAR_SMOKE = False
            CONFIRMAR_SMOKE_OPERATION_ID = ""
            smoke_result = None

            smoke_config = InventoryConfig(
                raw_root=RAW_ROOT,
                output_base=OUTPUT_BASE,
                operation_id=SMOKE_OPERATION_ID,
                code_commit=REPO_COMMIT,
                low_cardinality_limit=100,
                sample_size=5,
                sample_seed="falando-nela-v3",
                max_copy_length=200,
                max_json_bytes=64 * 1024 * 1024,
                cardinality_exact_limit=10_000,
                cardinality_kmv_size=1_024,
                max_files_per_group=SMOKE_FILES_PER_GROUP,
                progress_every_files=25,
            )

            print("Escopo:", smoke_config.scope_mode)
            print("Raiz:", RAW_ROOT)
            print("Saída:", smoke_config.operation_root)
            print("Arquivos por fonte × dataset × formato:", SMOKE_FILES_PER_GROUP)
            print("operation_id:", SMOKE_OPERATION_ID)
            """,
            "configure_smoke",
        ),
        code(
            """
            if EXECUTAR_SMOKE:
                assert MONTAR_DRIVE, "Monte o Drive antes do smoke."
                assert CONFIRMAR_SMOKE_OPERATION_ID == SMOKE_OPERATION_ID, (
                    "Copie SMOKE_OPERATION_ID literalmente para a confirmação."
                )
                smoke_result = run_inventory(smoke_config)
                print("Smoke concluído:", smoke_result["paths"]["report"])
            else:
                print("Smoke bloqueado; nenhum arquivo estruturado foi aberto.")
            """,
            "run_smoke",
        ),
        markdown(
            """
            ## 4. Revisar o smoke

            Revise o relatório, as contagens por arquivo, os campos e as
            inconsistências. O smoke tem gate `not_evaluated`: ele não pode
            aprovar G01.
            """
        ),
        code(
            """
            import pandas as pd
            from IPython.display import Markdown, display

            if smoke_result is None:
                print("Smoke ainda não executado.")
            else:
                paths = smoke_result["paths"]
                display(Markdown(paths["report"].read_text(encoding="utf-8")))
                print("\\nArquivos por estado de leitura:")
                files = pd.read_csv(paths["files"])
                display(
                    files.groupby(["structured_format", "read_status"], dropna=False)
                    .size()
                    .rename("itens")
                    .reset_index()
                )
                print("\\nPrimeiros campos:")
                display(pd.read_csv(paths["fields"]).head(30))
                print("\\nPrimeiras inconsistências:")
                display(pd.read_csv(paths["issues"]).head(30))
            """,
            "review_smoke",
        ),
        markdown(
            """
            ## 5. Gate separado para o inventário completo

            Pare aqui e compartilhe o relatório do smoke para revisão. Somente
            depois, copie o `SMOKE_OPERATION_ID` revisado e o novo
            `FULL_OPERATION_ID` para as duas confirmações abaixo.

            A execução completa continua fora do Drive e nasce em
            `needs_review`.
            """
        ),
        code(
            """
            if "FULL_OPERATION_ID" not in globals():
                FULL_OPERATION_ID = (
                    "raw-metadata-full-"
                    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
                )

            EXECUTAR_INVENTARIO_COMPLETO = False
            SMOKE_REVISADO_OPERATION_ID = ""
            CONFIRMAR_FULL_OPERATION_ID = ""
            full_result = None

            full_config = InventoryConfig(
                raw_root=RAW_ROOT,
                output_base=OUTPUT_BASE,
                operation_id=FULL_OPERATION_ID,
                code_commit=REPO_COMMIT,
                low_cardinality_limit=100,
                sample_size=5,
                sample_seed="falando-nela-v3",
                max_copy_length=200,
                max_json_bytes=64 * 1024 * 1024,
                cardinality_exact_limit=10_000,
                cardinality_kmv_size=1_024,
                max_files_per_group=None,
                progress_every_files=100,
            )

            print("Smoke que deve ser revisado:", SMOKE_OPERATION_ID)
            print("Execução completa proposta:", FULL_OPERATION_ID)
            print("Saída completa:", full_config.operation_root)
            """,
            "configure_full",
        ),
        code(
            """
            if EXECUTAR_INVENTARIO_COMPLETO:
                assert MONTAR_DRIVE, "Monte o Drive antes da execução completa."
                assert SMOKE_REVISADO_OPERATION_ID == SMOKE_OPERATION_ID, (
                    "Confirme literalmente o operation_id do smoke revisado."
                )
                smoke_manifest_path = (
                    OUTPUT_BASE / SMOKE_REVISADO_OPERATION_ID / "manifest.json"
                )
                assert smoke_manifest_path.is_file(), (
                    f"Manifest do smoke não encontrado: {smoke_manifest_path}"
                )
                smoke_manifest = __import__("json").loads(
                    smoke_manifest_path.read_text(encoding="utf-8")
                )
                assert smoke_manifest["execution_status"] == "succeeded"
                assert smoke_manifest["scope_mode"] == "smoke"
                assert CONFIRMAR_FULL_OPERATION_ID == FULL_OPERATION_ID, (
                    "Copie FULL_OPERATION_ID literalmente para a confirmação."
                )
                full_result = run_inventory(full_config)
                print("Inventário completo:", full_result["paths"]["report"])
            else:
                print("Execução completa bloqueada.")
            """,
            "run_full",
        ),
        markdown(
            """
            ## 6. Revisar G01

            Mesmo sem erros operacionais, o inventário completo permanece em
            `needs_review`. Não copie as saídas para o Drive e não inicie o
            schema normalizado antes da aprovação humana de G01.
            """
        ),
        code(
            """
            if full_result is None:
                print("Inventário completo ainda não executado.")
            else:
                paths = full_result["paths"]
                display(Markdown(paths["report"].read_text(encoding="utf-8")))
                manifest = full_result["manifest"]
                print("execution_status:", manifest["execution_status"])
                print("scientific_gate:", manifest["scientific_gate"])
                print("campos:", manifest["counts"]["field_paths"])
                print("inconsistências:", manifest["counts"]["issues"])
                print("próxima ação:", manifest["next_action"])
            """,
            "review_full",
        ),
    ]
    return nbformat.v4.new_notebook(
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
