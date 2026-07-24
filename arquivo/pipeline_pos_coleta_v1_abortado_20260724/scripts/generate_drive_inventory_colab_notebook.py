from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "dados" / "00_inventario_drive_colab.ipynb"


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
            # Inventário controlado dos dados no Drive

            **Público:** pesquisador responsável pelo Falando Nela.

            **Pré-requisitos:** gate inicial da fase 3 aprovado, versão atual
            do repositório publicada e acesso ao Google Drive do projeto.

            **Objetivo:** catalogar, em modo somente leitura, os itens sob
            `/content/drive/MyDrive/falando_nela/data`; reconstruir execuções e
            referências; reconciliar todos os universos por fonte, camada,
            classe e unidade; produzir o relatório D06 fora do Drive.

            Fluxo:

            1. montar o Drive somente mediante autorização;
            2. carregar uma revisão identificável do código;
            3. revisar raiz, taxonomia, limite e `operation_id`;
            4. executar duas passagens de leitura;
            5. revisar relatório, mapa e inconsistências.

            **Custo:** nenhuma chamada à OpenAI. O caderno lê metadados e
            arquivos estruturados selecionados de até 5 MiB. Não grava, move,
            renomeia nem apaga itens no Drive.

            `Run all` não inicia o inventário: as duas autorizações abaixo
            nascem desligadas.
            """
        ),
        code(
            """
            MONTAR_DRIVE = False

            if MONTAR_DRIVE:
                from google.colab import drive

                drive.mount("/content/drive")
                print("Drive montado. Isso ainda não executa o inventário.")
            else:
                print("Drive não montado. Para o piloto real, altere MONTAR_DRIVE para True.")
            """,
            "mount_drive_gate",
        ),
        markdown(
            """
            ## 1. Preparar o repositório

            No Colab, esta célula clona ou atualiza `main` depois do gate de
            montagem. Antes de usar o caderno real, confirme que o commit com o
            inventário já foi publicado. Fora do Colab, ela usa o repositório
            local e não instala nada.
            """
        ),
        code(
            """
            from pathlib import Path
            import os
            import subprocess
            import sys

            REPO_URL = "https://github.com/pedblan/falando_nela.git"
            REPO_REF = "main"
            IN_COLAB = Path("/content").is_dir()
            REPO_DIR = Path("/content/falando_nela") if IN_COLAB else Path.cwd()

            if IN_COLAB:
                if not REPO_DIR.exists():
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
                        "jsonschema>=4.23,<5",
                    ],
                    check=True,
                )

            required = [
                REPO_DIR / "processamento" / "inventario_drive.py",
                REPO_DIR / "relatorios_operacionais" / "core.py",
                REPO_DIR
                / "specs"
                / "reinicio_analise_plenario"
                / "02_relatorios_colab"
                / "schema"
                / "manifest.schema.json",
            ]
            for path in required:
                assert path.exists(), f"Revisão do repositório incompleta: {path}"

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
            ## 2. Configuração aprovada

            A raiz é única e não pode ser ampliada para `falando_nela/` ou
            `MyDrive/`. A saída temporária fica em `/content`, fora do Drive.
            Cada tentativa recebe um novo `operation_id`.
            """
        ),
        code(
            """
            from datetime import datetime, timezone

            from processamento.inventario_drive import (
                APPROVED_COLAB_ROOT,
                DEFAULT_MAX_STRUCTURED_BYTES,
                DEFAULT_OUTPUT_BASE,
            )

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            OUTPUT_BASE = Path("/content/falando_nela_inventory")
            MAX_STRUCTURED_BYTES = 5 * 1024 * 1024
            OPERATION_ID = (
                "drive-inventory-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
            )

            EXECUTAR_INVENTARIO_DRIVE = False
            CONFIRM_OPERATION_ID = ""
            result = None

            assert DATA_ROOT == APPROVED_COLAB_ROOT
            assert OUTPUT_BASE == DEFAULT_OUTPUT_BASE
            assert MAX_STRUCTURED_BYTES == DEFAULT_MAX_STRUCTURED_BYTES
            assert DATA_ROOT not in OUTPUT_BASE.parents
            print("Raiz aprovada:", DATA_ROOT)
            print("Saída temporária:", OUTPUT_BASE / OPERATION_ID)
            print("Limite estruturado:", MAX_STRUCTURED_BYTES, "bytes")
            print("operation_id:", OPERATION_ID)
            """,
            "configure_approved_scope",
        ),
        markdown(
            """
            ## 3. Exercício de controle antes da execução

            Confira quatro fatos:

            - a raiz termina exatamente em `falando_nela/data`;
            - a saída começa em `/content/falando_nela_inventory`;
            - o limite é 5 MiB;
            - a execução continua desligada.

            A célula abaixo funciona como gabarito automático. Para o piloto
            real, altere a flag e copie literalmente o `OPERATION_ID` para a
            confirmação.
            """
        ),
        code(
            """
            assert str(DATA_ROOT) == "/content/drive/MyDrive/falando_nela/data"
            assert str(OUTPUT_BASE) == "/content/falando_nela_inventory"
            assert MAX_STRUCTURED_BYTES == 5 * 1024 * 1024

            if EXECUTAR_INVENTARIO_DRIVE:
                assert MONTAR_DRIVE, "Monte o Drive antes de autorizar a leitura."
                assert CONFIRM_OPERATION_ID == OPERATION_ID, (
                    "Copie OPERATION_ID literalmente para CONFIRM_OPERATION_ID."
                )
                assert DATA_ROOT.is_dir(), f"Raiz aprovada não encontrada: {DATA_ROOT}"
                print("Gate armado para:", OPERATION_ID)
            else:
                print("Gate fechado: nenhuma varredura do Drive será executada.")
            """,
            "preflight_gate",
        ),
        markdown(
            """
            ## 4. Executar as duas passagens

            A passagem 1 lê somente metadados. A passagem 2 abre apenas JSON,
            Markdown e CSV selecionados, com até 5 MiB. Parquet, JSONL
            volumoso, ZIP, mídia e dados brutos permanecem fechados.
            """
        ),
        code(
            """
            from processamento.inventario_drive import write_drive_inventory

            if EXECUTAR_INVENTARIO_DRIVE:
                result = write_drive_inventory(
                    data_root=DATA_ROOT,
                    output_base=OUTPUT_BASE,
                    operation_id=OPERATION_ID,
                    code_commit=REPO_COMMIT,
                    max_structured_bytes=MAX_STRUCTURED_BYTES,
                )
                print("Inventário concluído:", result["paths"]["operation_root"])
            else:
                print("Execução protegida. Nenhum item do Drive foi lido.")
            """,
            "run_inventory",
        ),
        markdown(
            """
            ## 5. Revisar o relatório humano

            O relatório responde se o programa terminou, quantos itens foram
            observados, quais alertas existem e qual é a próxima ação. O
            manifest e o log não devem ser necessários para esta leitura.
            """
        ),
        code(
            """
            from IPython.display import Markdown, display

            if result is not None:
                report_path = result["paths"]["report"]
                display(Markdown(report_path.read_text(encoding="utf-8")))
            else:
                print("Relatório indisponível porque a execução continua protegida.")
            """,
            "review_human_report",
        ),
        markdown(
            """
            ## 6. Revisar o mapa e as tabelas centrais

            O mapa explica classes, camadas, fontes, execuções, referências e
            a reconciliação de todo o universo catalogado. As primeiras linhas
            das inconsistências são mostradas sem despejar tabelas grandes.
            """
        ),
        code(
            """
            import csv

            if result is not None:
                operation_root = result["paths"]["operation_root"]
                map_path = operation_root / "artifacts" / "mapa_dados.md"
                issues_path = operation_root / "artifacts" / "inconsistencias.csv"
                display(Markdown(map_path.read_text(encoding="utf-8")))
                with issues_path.open(encoding="utf-8", newline="") as handle:
                    first_issues = list(csv.DictReader(handle))[:10]
                print("Primeiras inconsistências:")
                display(first_issues)
            else:
                print("Mapa indisponível porque a execução continua protegida.")
            """,
            "review_map_and_issues",
        ),
        markdown(
            """
            ## Armadilhas e extensão opcional

            - Não troque a raiz por `MyDrive`: isso ampliaria silenciosamente o
              universo.
            - Não reutilize um `operation_id`: a tentativa anterior deve
              permanecer auditável.
            - `succeeded` não significa `approved`; o inventário nasce em
              `needs_review`.
            - Não copie a saída ao Drive ainda.

            Extensão opcional, sujeita a outro gate: depois da revisão, poderá
            ser criado um pacote aprovado para preservação no Drive. Este
            caderno não o faz.
            """
        ),
        code(
            """
            if result is None:
                print("execution_status: not_started")
                print("scientific_gate: not_evaluated")
                print("artefatos: nenhum")
                print("próxima ação: autorizar explicitamente o piloto, se desejado")
            else:
                manifest = result["manifest"]
                print("execution_status:", manifest["execution_status"])
                print("scientific_gate:", manifest["scientific_gate"])
                print("itens catalogados:", manifest["counts"]["items_cataloged"])
                print("inconsistências:", manifest["counts"]["inconsistencies"])
                print("relatório:", result["paths"]["report"])
                print("mapa:", result["paths"]["artifacts"] / "mapa_dados.md")
                print(
                    "próxima ação: revisar mapa e inconsistências; "
                    "não iniciar migração ou snapshot"
                )
            """,
            "final_summary",
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
        }
    )
    for index, cell in enumerate(notebook.cells):
        stable = (
            f"{OUTPUT.relative_to(ROOT)}:{index}:{cell.cell_type}:{cell.source}"
        ).encode("utf-8")
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
