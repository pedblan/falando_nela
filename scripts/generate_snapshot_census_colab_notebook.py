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
    / "dados"
    / "01_censo_bases_snapshot_v2_colab.ipynb"
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
            # Censo das bases candidatas ao snapshot v2

            **Objetivo:** medir, em modo somente leitura, três Parquets
            processados antes das decisões D03–D05.

            **Unidade:** registro de `textos_parlamentares/v1`.

            Entradas autorizadas:

            - `camara__plenario_discursos.parquet`;
            - `senado__plenario_discursos.parquet`;
            - `senado__congresso_discursos.parquet`.

            O censo verifica schema, registros, período, cobertura textual,
            autores, proveniência, IDs e sobreposições exatas. O texto integral
            não é carregado.

            **Custo:** nenhuma chamada à OpenAI. Nenhum snapshot é criado e
            nenhuma saída é gravada no Drive. `Run all` permanece seguro porque
            a montagem e a execução nascem desligadas.
            """
        ),
        code(
            """
            MONTAR_DRIVE = False

            if MONTAR_DRIVE:
                from google.colab import drive

                drive.mount("/content/drive")
                print("Drive montado. O censo ainda não foi autorizado.")
            else:
                print("Drive não montado. Altere MONTAR_DRIVE para True quando autorizado.")
            """,
            "mount_drive_gate",
        ),
        markdown(
            """
            ## 1. Preparar uma revisão identificável

            No Colab, a célula carrega a `main` publicada e instala somente as
            dependências já declaradas pelo projeto. Fora do Colab, usa o
            repositório e o ambiente locais.
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
                        "duckdb>=1,<2",
                        "pyarrow>=15,<23",
                        "jsonschema>=4.23,<5",
                    ],
                    check=True,
                )

            required = [
                REPO_DIR / "processamento" / "censo_snapshot_v2.py",
                REPO_DIR / "relatorios_operacionais" / "core.py",
                REPO_DIR
                / "specs"
                / "reinicio_analise_plenario"
                / "04_snapshot_discursos_v2"
                / "requirements.md",
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
            ## 2. Conferir o escopo autorizado

            A raiz e os três nomes são fixos. A saída fica em `/content`, fora
            do Drive. Esta célula cria apenas o identificador da tentativa.
            """
        ),
        code(
            """
            from datetime import datetime, timezone

            from processamento.censo_snapshot_v2 import (
                APPROVED_PARQUET_ROOT,
                CANDIDATE_FILENAMES,
                DEFAULT_OUTPUT_BASE,
            )

            PARQUET_ROOT = Path(
                "/content/drive/MyDrive/falando_nela/data/"
                "processed/textos_parlamentares/v1/parquet"
            )
            OUTPUT_BASE = Path("/content/falando_nela_snapshot_census")
            BASES_CANDIDATAS = (
                "camara__plenario_discursos.parquet",
                "senado__plenario_discursos.parquet",
                "senado__congresso_discursos.parquet",
            )
            OPERATION_ID = (
                "snapshot-census-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
            )
            result = None

            assert PARQUET_ROOT == APPROVED_PARQUET_ROOT
            assert OUTPUT_BASE == DEFAULT_OUTPUT_BASE
            assert BASES_CANDIDATAS == CANDIDATE_FILENAMES
            assert PARQUET_ROOT not in OUTPUT_BASE.parents
            print("Raiz aprovada:", PARQUET_ROOT)
            print("Bases candidatas:", len(BASES_CANDIDATAS))
            for filename in BASES_CANDIDATAS:
                print(" -", filename)
            print("Saída temporária:", OUTPUT_BASE / OPERATION_ID)
            print("operation_id:", OPERATION_ID)
            """,
            "configure_approved_scope",
        ),
        markdown(
            """
            ## 3. Autorização explícita

            Execute primeiro com o gate fechado. Para o censo real, altere
            somente esta célula: use `True` e copie literalmente o
            `OPERATION_ID` mostrado acima.
            """
        ),
        code(
            """
            EXECUTAR_CENSO_BASES = False
            CONFIRM_OPERATION_ID = ""

            if EXECUTAR_CENSO_BASES:
                print("Autorização solicitada para:", CONFIRM_OPERATION_ID)
            else:
                print("Autorização fechada.")
            """,
            "authorize_census",
        ),
        markdown(
            """
            ## 4. Gate de preflight

            Esta célula confirma a montagem, o identificador e a presença
            exata das três entradas antes de qualquer leitura de registros.
            """
        ),
        code(
            """
            if EXECUTAR_CENSO_BASES:
                assert MONTAR_DRIVE, "Monte o Drive antes de autorizar o censo."
                assert CONFIRM_OPERATION_ID == OPERATION_ID, (
                    "Copie OPERATION_ID literalmente para CONFIRM_OPERATION_ID."
                )
                assert PARQUET_ROOT.is_dir(), (
                    f"Raiz Parquet ausente: {PARQUET_ROOT}"
                )
                missing = [
                    filename
                    for filename in BASES_CANDIDATAS
                    if not (PARQUET_ROOT / filename).is_file()
                ]
                assert not missing, f"Bases candidatas ausentes: {missing}"
                print("Gate armado para:", OPERATION_ID)
            else:
                print("Gate fechado: nenhum registro Parquet será lido.")
            """,
            "preflight_gate",
        ),
        markdown(
            """
            ## 5. Executar o censo

            A rotina lê metadados e colunas de controle. Ela não carrega
            `texto`, não calcula embeddings, não deduplica e não cria snapshot.
            """
        ),
        code(
            """
            from processamento.censo_snapshot_v2 import (
                write_snapshot_candidate_census,
            )

            if EXECUTAR_CENSO_BASES:
                result = write_snapshot_candidate_census(
                    parquet_root=PARQUET_ROOT,
                    output_base=OUTPUT_BASE,
                    operation_id=OPERATION_ID,
                    code_commit=REPO_COMMIT,
                )
                print("Censo concluído:", result["paths"]["operation_root"])
            else:
                print("Execução protegida. Nenhuma base foi censada.")
            """,
            "run_census",
        ),
        markdown(
            """
            ## 6. Revisar somente o relatório e o mapa

            O relatório resume o estado operacional. O mapa compara as três
            bases. Não é necessário abrir manifest ou log numa execução normal.
            """
        ),
        code(
            """
            from IPython.display import Markdown, display

            if result is not None:
                display(
                    Markdown(
                        result["paths"]["report"].read_text(encoding="utf-8")
                    )
                )
                map_path = result["paths"]["artifacts"] / "mapa_censo.md"
                display(Markdown(map_path.read_text(encoding="utf-8")))
            else:
                print("Relatório indisponível porque a execução está protegida.")
            """,
            "review_report_and_map",
        ),
        markdown(
            """
            ## Ponto de parada

            `succeeded` significa apenas que o censo terminou. O gate continua
            em `needs_review`. Não copie os resultados ao Drive, não aprove D03
            e não crie o snapshot nesta sessão.
            """
        ),
        code(
            """
            if result is None:
                print("execution_status: not_started")
                print("scientific_gate: not_evaluated")
                print("snapshot criado: não")
                print("próxima ação: autorizar explicitamente o censo")
            else:
                counts = result["manifest"]["counts"]
                print("execution_status:", result["manifest"]["execution_status"])
                print("scientific_gate:", result["manifest"]["scientific_gate"])
                print("bases candidatas:", counts["candidate_files"])
                print("registros:", counts["input_records"])
                print("IDs distintos:", counts["global_distinct_ids"])
                print("IDs ausentes:", counts["ids_missing"])
                print("duplicatas internas:", counts["duplicate_id_rows"])
                print("IDs compartilhados:", counts["cross_file_shared_ids"])
                print("snapshot criado: não")
                print("próxima ação: revisar o censo antes de D03")
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
