from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "coleta" / "07_auditoria_cobertura_discursos_senadores_2010_colab.ipynb"


def clean(value: str) -> str:
    return textwrap.dedent(value).strip()


def code(value: str, role: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_code_cell(clean(value))
    cell.metadata["falando_nela"] = {"role": role}
    return cell


def md(value: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_markdown_cell(clean(value))
    cell.metadata["language"] = "pt-BR"
    return cell


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        md(
            """
            # Auditoria histórica de discursos de senadores — 2010 em diante

            Este caderno consulta a lista oficial de senadores por legislatura,
            usa `CodigoParlamentar` no endpoint individual de discursos e compara
            os `CodigoPronunciamento` encontrados com o raw cumulativo do Drive.

            A execução é somente de auditoria: não altera raw, processed, Parquet
            nem snapshot. Respostas são persistidas de forma retomável em
            `operations/auditorias/discursos_senadores/`.
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
            REPO_REF = "2015_2016"
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
                assert not dirty, f"Clone efêmero com alterações locais; revise antes de atualizar:\\n{dirty}"
                subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "origin", REPO_REF], check=True)
                branches = subprocess.check_output(
                    ["git", "-C", str(REPO_DIR), "branch", "--format=%(refname:short)"], text=True
                ).splitlines()
                if REPO_REF in branches:
                    subprocess.run(["git", "-C", str(REPO_DIR), "switch", REPO_REF], check=True)
                else:
                    subprocess.run(
                        ["git", "-C", str(REPO_DIR), "switch", "--track", f"origin/{REPO_REF}"],
                        check=True,
                    )
                subprocess.run(
                    ["git", "-C", str(REPO_DIR), "pull", "--ff-only", "origin", REPO_REF],
                    check=True,
                )

            current_ref = subprocess.check_output(
                ["git", "-C", str(REPO_DIR), "branch", "--show-current"], text=True
            ).strip()
            assert current_ref == REPO_REF, (current_ref, REPO_REF)
            required_module = REPO_DIR / "coleta" / "senado" / "auditoria_discursos_historicos.py"
            assert required_module.exists(), f"Branch sem o auditor esperado: {required_module}"

            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")],
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
            DATA_INICIO = "2010-01-01"
            DATA_FIM = "2026-07-14"
            HOUSES = ("SF", "CN")
            AUDIT_ID = "audit-discursos-senadores-2010-20260714"
            AUDIT_DIR = (
                DATA_ROOT
                / "operations"
                / "auditorias"
                / "discursos_senadores"
                / AUDIT_ID
            )

            RODAR_AUDITORIA = False
            CONFIRM_AUDIT_ID = ""

            assert DATA_ROOT.exists(), f"Raiz do Drive ausente: {DATA_ROOT}"
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            print("Auditoria:", AUDIT_ID)
            print("Janela:", DATA_INICIO, "a", DATA_FIM)
            print("Casas:", HOUSES)
            print("Saída:", AUDIT_DIR)
            """,
            "configure_audit",
        ),
        code(
            r'''
            import subprocess
            import sys

            def run_command(command):
                print("Executando:", " ".join(map(str, command)), flush=True)
                process = subprocess.Popen(
                    list(map(str, command)),
                    cwd=REPO_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="", flush=True)
                returncode = process.wait()
                print("returncode:", returncode)
                return returncode
            ''',
            "command_helper",
        ),
        md(
            """
            ## Executar a auditoria

            Esta é a etapa longa. Ela pode ser interrompida e retomada com o mesmo
            `AUDIT_ID`: cada resposta concluída é anexada imediatamente ao JSONL.

            Antes de executar, defina `RODAR_AUDITORIA = True` e copie exatamente
            o valor de `AUDIT_ID` para `CONFIRM_AUDIT_ID`.
            """
        ),
        code(
            """
            if RODAR_AUDITORIA:
                assert CONFIRM_AUDIT_ID == AUDIT_ID, (
                    "Confirme explicitamente a auditoria preenchendo CONFIRM_AUDIT_ID."
                )
                command = [
                    sys.executable,
                    "-u",
                    "-m",
                    "coleta.senado.auditoria_discursos_historicos",
                    "--cycle-dir",
                    str(AUDIT_DIR),
                    "--data-root",
                    str(DATA_ROOT),
                    "--data-inicio",
                    DATA_INICIO,
                    "--data-fim",
                    DATA_FIM,
                    "--houses",
                    *HOUSES,
                    "--resume",
                    "--strict",
                ]
                returncode = run_command(command)
                assert returncode == 0, (
                    "A auditoria persistiu o progresso, mas encontrou erro ou conflito. "
                    "Reexecute a mesma célula para tentar novamente e depois inspecione os artefatos."
                )
            else:
                print("Auditoria protegida. Ative RODAR_AUDITORIA e confirme AUDIT_ID.")
            """,
            "run_audit",
        ),
        md(
            """
            ## Examinar a cobertura

            `missing_ids` mede discursos de senadores encontrados na fonte mas
            ausentes no raw. `raw_ids_not_in_senator_endpoint` é apenas informativo:
            em `CN`, pode incluir deputados e outras autoridades.
            """
        ),
        code(
            """
            import json
            import pandas as pd
            from IPython.display import display

            summary_path = AUDIT_DIR / "senator_endpoint_summary.json"
            coverage_path = AUDIT_DIR / "senator_endpoint_coverage.csv"
            missing_path = AUDIT_DIR / "senator_endpoint_missing_ids.jsonl"
            errors_path = AUDIT_DIR / "senator_endpoint_errors.jsonl"
            conflicts_path = AUDIT_DIR / "senator_endpoint_conflicts.jsonl"

            assert summary_path.exists(), f"Execute a auditoria primeiro: {summary_path}"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            coverage = pd.read_csv(coverage_path)
            display(coverage)
            display(
                coverage.groupby(["house", "status"], dropna=False)
                .size()
                .rename("anos")
                .reset_index()
            )
            display(
                coverage.groupby("house")[[
                    "source_ids",
                    "source_ids_present_in_raw",
                    "missing_ids",
                    "mispartitioned_ids",
                    "raw_ids_not_in_senator_endpoint",
                ]]
                .sum()
                .reset_index()
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))

            missing = [
                json.loads(line)
                for line in missing_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if missing:
                display(pd.DataFrame(missing).drop(columns=["pronunciamento"], errors="ignore").head(100))
                print("IDs ausentes:", len(missing), "— não regenere derivados ainda.")
            else:
                print("Nenhum discurso de senador ausente no raw para a janela auditada.")

            assert summary["errors"] == 0, errors_path
            assert summary["invalid_probe_lines"] == 0, summary
            assert summary["invalid_raw_lines"] == 0, summary
            assert summary["source_conflicts"] == 0, conflicts_path
            """,
            "inspect_results",
        ),
        md(
            """
            ## Próxima etapa

            Se houver IDs ausentes, preserve este diretório de auditoria e use
            `senator_endpoint_missing_ids.jsonl` como população fechada do backfill.
            Não execute normalização, Parquet ou snapshot antes de implementar e
            validar a incorporação desses IDs ao raw imutável.
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
        stable = f"{OUTPUT.relative_to(ROOT)}:{index}:{cell.cell_type}:{cell.source}".encode("utf-8")
        cell["id"] = sha256(stable).hexdigest()[:16]
    nbformat.validate(notebook)
    return notebook


def render() -> str:
    return nbformat.writes(build_notebook()) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != generated:
            raise SystemExit(f"Notebook fora de sincronia: {OUTPUT}")
        return
    OUTPUT.write_text(generated, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
