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
    / "02_snapshot_discursos_v2_smoke_colab.ipynb"
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
            # Smoke do snapshot de discursos v2

            **Objetivo:** validar, em uma amostra pequena e determinística, a
            transformação aprovada para o snapshot v2.

            O caderno:

            - usa somente os três Parquets aprovados;
            - aplica o período inclusivo de `2010-01-01` a `2026-07-13`;
            - preserva registros sem autoria;
            - não deduplica entre fontes;
            - grava apenas em `/content`, fora do Drive;
            - não chama a OpenAI.

            Este smoke não é o snapshot integral e não pode ser promovido.
            `Run all` permanece protegido porque montagem e execução nascem
            desligadas.
            """
        ),
        code(
            """
            MONTAR_DRIVE = False

            if MONTAR_DRIVE:
                from google.colab import drive

                drive.mount("/content/drive")
                print("Drive montado. O smoke ainda não foi autorizado.")
            else:
                print("Drive não montado. Altere MONTAR_DRIVE para True quando autorizado.")
            """,
            "mount_drive_gate",
        ),
        markdown(
            """
            ## 1. Preparar uma revisão identificável

            No Colab, esta célula carrega a `main` publicada e instala apenas
            as dependências declaradas pelo projeto. Fora do Colab, usa o
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
                        "pandas>=2,<3",
                    ],
                    check=True,
                )

            required = [
                REPO_DIR / "processamento" / "snapshot_discursos_v2.py",
                REPO_DIR / "relatorios_operacionais" / "core.py",
                REPO_DIR
                / "specs"
                / "reinicio_analise_plenario"
                / "04_snapshot_discursos_v2"
                / "schema"
                / "snapshot_discursos_v2.record.schema.json",
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
            ## 2. Conferir o escopo do smoke

            A amostra seleciona até 20 registros elegíveis e até 20 registros
            excluídos por base, sempre pela mesma ordenação. A saída é
            temporária e permanece fora do Drive.
            """
        ),
        code(
            """
            from datetime import datetime, timezone

            from processamento.snapshot_discursos_v2 import (
                APPROVED_PARQUET_ROOT,
                DEFAULT_ROWS_PER_BASE,
                DEFAULT_SMOKE_OUTPUT_BASE,
                PERIOD_END,
                PERIOD_START,
                SNAPSHOT_INPUT_FILENAMES,
            )

            PARQUET_ROOT = Path(
                "/content/drive/MyDrive/falando_nela/data/"
                "processed/textos_parlamentares/v1/parquet"
            )
            OUTPUT_BASE = Path("/content/falando_nela_snapshot_v2_smoke")
            BASES_APROVADAS = (
                "camara__plenario_discursos.parquet",
                "senado__plenario_discursos.parquet",
                "senado__congresso_discursos.parquet",
            )
            ROWS_PER_BASE = 20
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()
            OPERATION_ID = f"snapshot-v2-smoke-{timestamp}"
            SNAPSHOT_ID = f"discursos-plenario-v2-smoke-{timestamp}"
            result = None

            assert PARQUET_ROOT == APPROVED_PARQUET_ROOT
            assert OUTPUT_BASE == DEFAULT_SMOKE_OUTPUT_BASE
            assert BASES_APROVADAS == SNAPSHOT_INPUT_FILENAMES
            assert ROWS_PER_BASE == DEFAULT_ROWS_PER_BASE
            assert PERIOD_START.isoformat() == "2010-01-01"
            assert PERIOD_END.isoformat() == "2026-07-13"
            assert PARQUET_ROOT not in OUTPUT_BASE.parents
            print("Raiz aprovada:", PARQUET_ROOT)
            print("Período:", PERIOD_START, "a", PERIOD_END)
            print("Limite por base e resultado:", ROWS_PER_BASE)
            print("Saída temporária:", OUTPUT_BASE / OPERATION_ID)
            print("operation_id:", OPERATION_ID)
            print("snapshot_id:", SNAPSHOT_ID)
            """,
            "configure_smoke_scope",
        ),
        markdown(
            """
            ## 3. Autorização explícita

            Execute primeiro com o gate fechado. Para o smoke real, altere
            somente esta célula: ative o booleano e copie literalmente os dois
            identificadores exibidos acima.
            """
        ),
        code(
            """
            EXECUTAR_SMOKE = False
            CONFIRM_OPERATION_ID = ""
            CONFIRM_SNAPSHOT_ID = ""

            if EXECUTAR_SMOKE:
                print("Autorização solicitada para:", CONFIRM_OPERATION_ID)
                print("Snapshot técnico:", CONFIRM_SNAPSHOT_ID)
            else:
                print("Autorização fechada.")
            """,
            "authorize_smoke",
        ),
        markdown(
            """
            ## 4. Gate de preflight

            O gate confirma montagem, identificadores, entradas e raiz de
            saída. Nenhum registro é lido enquanto ele estiver fechado.
            """
        ),
        code(
            """
            if EXECUTAR_SMOKE:
                assert MONTAR_DRIVE, "Monte o Drive antes de autorizar o smoke."
                assert CONFIRM_OPERATION_ID == OPERATION_ID, (
                    "Copie OPERATION_ID literalmente para CONFIRM_OPERATION_ID."
                )
                assert CONFIRM_SNAPSHOT_ID == SNAPSHOT_ID, (
                    "Copie SNAPSHOT_ID literalmente para CONFIRM_SNAPSHOT_ID."
                )
                assert PARQUET_ROOT.is_dir(), (
                    f"Raiz Parquet ausente: {PARQUET_ROOT}"
                )
                missing = [
                    filename
                    for filename in BASES_APROVADAS
                    if not (PARQUET_ROOT / filename).is_file()
                ]
                assert not missing, f"Bases aprovadas ausentes: {missing}"
                assert not (OUTPUT_BASE / OPERATION_ID).exists(), (
                    "operation_id já utilizado; gere novos identificadores."
                )
                print("Gate armado para:", OPERATION_ID)
            else:
                print("Gate fechado: nenhum registro Parquet será transformado.")
            """,
            "preflight_gate",
        ),
        markdown(
            """
            ## 5. Executar o smoke

            A rotina confere o contrato das entradas, conta todo o universo
            para reconciliar D04 e transforma somente a amostra limitada. Não
            há deduplicação nem escrita no Drive.
            """
        ),
        code(
            """
            from processamento.snapshot_discursos_v2 import (
                write_snapshot_v2_smoke,
            )

            if EXECUTAR_SMOKE:
                result = write_snapshot_v2_smoke(
                    parquet_root=PARQUET_ROOT,
                    output_base=OUTPUT_BASE,
                    operation_id=OPERATION_ID,
                    snapshot_id=SNAPSHOT_ID,
                    code_commit=REPO_COMMIT,
                    rows_per_base=ROWS_PER_BASE,
                )
                print("Smoke concluído:", result["paths"]["operation_root"])
            else:
                print("Execução protegida. Nenhuma amostra foi criada.")
            """,
            "run_smoke",
        ),
        markdown(
            """
            ## 6. Revisar o relatório e as contagens

            Estes são os documentos normais de revisão. Manifest e log ficam
            disponíveis apenas para diagnóstico técnico.
            """
        ),
        code(
            """
            import pandas as pd
            from IPython.display import Markdown, display

            if result is not None:
                display(
                    Markdown(
                        result["paths"]["report"].read_text(encoding="utf-8")
                    )
                )
                display(
                    pd.read_csv(
                        result["paths"]["artifacts"]
                        / "contagens_por_base.csv"
                    )
                )
            else:
                print("Relatório indisponível porque a execução está protegida.")
            """,
            "review_report",
        ),
        markdown(
            """
            ## 7. Inspecionar algumas linhas

            A prévia mostra identidade, fonte, data, autoria, flags e apenas os
            primeiros 240 caracteres do texto. O Parquet integral da amostra
            permanece disponível para uma inspeção mais detalhada.
            """
        ),
        code(
            """
            import duckdb

            if result is not None:
                snapshot_path = (
                    result["paths"]["artifacts"]
                    / "snapshot_discursos_v2.parquet"
                )
                preview = duckdb.connect(":memory:").execute(
                    '''
                    SELECT
                        texto_id,
                        source,
                        dataset,
                        data,
                        parlamentar_nome,
                        qualidade_flags,
                        left(texto, 240) AS texto_inicio
                    FROM read_parquet(?)
                    ORDER BY input_parquet, texto_id
                    LIMIT 12
                    ''',
                    [str(snapshot_path)],
                ).df()
                display(preview)
            else:
                print("Prévia indisponível porque a execução está protegida.")
            """,
            "inspect_sample",
        ),
        markdown(
            """
            ## Ponto de parada

            `succeeded` confirma apenas a transformação da amostra. O gate
            científico continua em `needs_review`. Não copie os resultados ao
            Drive e não execute o universo completo nesta sessão.
            """
        ),
        code(
            """
            if result is None:
                print("execution_status: not_started")
                print("scientific_gate: not_evaluated")
                print("snapshot integral criado: não")
                print("próxima ação: autorizar explicitamente o smoke")
            else:
                counts = result["manifest"]["counts"]
                print("execution_status:", result["manifest"]["execution_status"])
                print("scientific_gate:", result["manifest"]["scientific_gate"])
                print("registros nas fontes:", counts["source_records"])
                print("registros dentro do período:", counts["within_period_records"])
                print("amostra incluída:", counts["snapshot_records"])
                print("amostra excluída:", counts["excluded_sample_records"])
                print("IDs duplicados:", counts["duplicate_ids"])
                print("snapshot integral criado: não")
                print("próxima ação: revisar o smoke antes da execução completa")
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
