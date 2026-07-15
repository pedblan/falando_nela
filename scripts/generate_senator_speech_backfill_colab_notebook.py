from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "coleta" / "08_backfill_discursos_senadores_por_codigo_2010_colab.ipynb"


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
            # Backfill de discursos de senadores por código

            Este caderno recupera exclusivamente os IDs ausentes produzidos pela
            auditoria desde 2010. Ele não busca por nome: cada texto é baixado
            pelo CodigoPronunciamento e preserva o CodigoParlamentar que o
            descobriu como proveniência.

            Execute somente depois da auditoria limpa e mantenha o mesmo
            AUDIT_ID. A etapa posterior repete a auditoria e exige cobertura
            completa antes de qualquer derivado.
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
                assert not dirty, dirty
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

            assert subprocess.check_output(
                ["git", "-C", str(REPO_DIR), "branch", "--show-current"], text=True
            ).strip() == REPO_REF
            required_module = REPO_DIR / "coleta" / "senado" / "backfill_discursos_por_codigo.py"
            assert required_module.exists(), required_module
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
            AUDIT_ID = "audit-discursos-senadores-2010-20260714"
            AUDIT_DIR = (
                DATA_ROOT / "operations" / "auditorias" / "discursos_senadores" / AUDIT_ID
            )
            MISSING_PATH = AUDIT_DIR / "senator_endpoint_missing_ids.jsonl"
            BACKFILL_ID = "backfill-discursos-senadores-por-codigo-2010-20260714"
            RUNS = {
                "SF": {
                    "dataset": "plenario_discursos",
                    "run_id": f"{BACKFILL_ID}-sf",
                },
                "CN": {
                    "dataset": "congresso_discursos",
                    "run_id": f"{BACKFILL_ID}-cn",
                },
            }

            RODAR_BACKFILL_SF = False
            RODAR_BACKFILL_CN = False
            RODAR_AUDITORIA_POS = False
            CONFIRM_BACKFILL_ID = ""

            assert DATA_ROOT.exists(), DATA_ROOT
            assert MISSING_PATH.exists(), MISSING_PATH
            print("Audit:", AUDIT_DIR)
            print("Backfill:", BACKFILL_ID)
            """,
            "configure_backfill",
        ),
        code(
            r'''
            import json
            import os
            import subprocess
            from contextlib import contextmanager

            def confirmed():
                assert CONFIRM_BACKFILL_ID == BACKFILL_ID, (
                    "Preencha CONFIRM_BACKFILL_ID com o valor exato de BACKFILL_ID."
                )

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

            @contextmanager
            def dataset_lock(house):
                run = RUNS[house]
                lock_path = DATA_ROOT / "locks" / "senado" / f"{run['dataset']}.lock"
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(
                        descriptor,
                        json.dumps({"backfill_id": BACKFILL_ID, "house": house, "run_id": run["run_id"]}).encode("utf-8"),
                    )
                    os.close(descriptor)
                    yield
                finally:
                    lock_path.unlink(missing_ok=True)

            def backfill_command(house):
                run = RUNS[house]
                return [
                    sys.executable, "-u", "-m", "coleta.senado.backfill_discursos_por_codigo",
                    "--mode", "prod", "--output-dir", str(DATA_ROOT),
                    "--data-inicio", DATA_INICIO, "--data-fim", DATA_FIM,
                    "--run-id", run["run_id"], "--missing-path", str(MISSING_PATH),
                    "--house", house, "--no-sample", "--resume",
                ]

            def assert_audit_ready():
                summary = json.loads((AUDIT_DIR / "senator_endpoint_summary.json").read_text(encoding="utf-8"))
                assert summary["errors"] == 0, summary
                assert summary["invalid_probe_lines"] == 0, summary
                assert summary["invalid_raw_lines"] == 0, summary
                assert summary["source_conflicts"] == 0, summary
                assert summary["missing_ids"] > 0, summary
                return summary

            def assert_backfill_complete(house):
                run = RUNS[house]
                manifest_path = DATA_ROOT / "manifests" / f"{run['run_id']}.json"
                checkpoint_path = DATA_ROOT / "checkpoints" / "senado" / f"{run['dataset']}.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                current = checkpoint["runs"][run["run_id"]]
                completed = set(current.get("completed_partitions", {}))
                failed = set(current.get("failed_partitions", {})) - completed
                assert manifest["status"] == "completed" and manifest["errors"] == 0, manifest
                assert manifest["mode"] == "prod" and manifest["sample"] is False, manifest
                assert manifest["strategy"] == "senator-endpoint-missing-ids-v1", manifest
                assert manifest["population"] > 0, manifest
                assert not failed, failed
                return manifest
            ''',
            "helpers",
        ),
        code(
            """
            import json
            import pandas as pd
            from IPython.display import display

            summary = assert_audit_ready()
            missing = [
                json.loads(line)
                for line in MISSING_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            population = (
                pd.DataFrame(missing)
                .groupby(["house", "dataset", "year"], dropna=False)
                .size()
                .rename("ids_a_recuperar")
                .reset_index()
            )
            display(population)
            assert set(population["house"]) == {"SF", "CN"}
            """,
            "inspect_population",
        ),
        md(
            """
            ## Executar o backfill

            Rode SF e CN em sequência. Cada etapa é retomável com o mesmo
            BACKFILL_ID. Se o runtime interromper, não apague arquivos nem
            checkpoints: execute a mesma célula novamente.
            """
        ),
        code(
            """
            if RODAR_BACKFILL_SF:
                confirmed()
                with dataset_lock("SF"):
                    returncode = run_command(backfill_command("SF"))
                assert returncode == 0
                display(assert_backfill_complete("SF"))
            else:
                print("SF protegida.")

            if RODAR_BACKFILL_CN:
                confirmed()
                with dataset_lock("CN"):
                    returncode = run_command(backfill_command("CN"))
                assert returncode == 0
                display(assert_backfill_complete("CN"))
            else:
                print("CN protegida.")
            """,
            "run_backfill",
        ),
        md(
            """
            ## Reauditoria obrigatória

            Depois que as duas casas terminarem sem erro, repita a auditoria com
            require-complete. Ela reutiliza os probes já arquivados e apenas
            reavalia o raw. Não processe Parquet ou snapshot antes deste gate.
            """
        ),
        code(
            """
            if RODAR_AUDITORIA_POS:
                confirmed()
                command = [
                    sys.executable, "-u", "-m", "coleta.senado.auditoria_discursos_historicos",
                    "--cycle-dir", str(AUDIT_DIR), "--data-root", str(DATA_ROOT),
                    "--data-inicio", DATA_INICIO, "--data-fim", DATA_FIM,
                    "--houses", "SF", "CN", "--resume", "--strict", "--require-complete",
                ]
                returncode = run_command(command)
                assert returncode == 0
                print("Cobertura por senador completa; derivados podem ser planejados.")
            else:
                print("Reauditoria protegida.")
            """,
            "post_audit",
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
