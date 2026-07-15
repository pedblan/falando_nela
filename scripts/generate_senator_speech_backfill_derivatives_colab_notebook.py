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
    / "processamento"
    / "07_derivados_backfill_discursos_senadores_por_codigo_colab.ipynb"
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
            # Derivados do backfill de discursos de senadores por código

            Este caderno só deve ser executado depois de o caderno 08 concluir
            a reauditoria com cobertura completa. Ele não coleta dados e não
            altera raw: reconstrói os derivados canônicos a partir de todo o
            raw cumulativo, cria um snapshot imutável e valida 2015 e 2016.

            Não use o caderno 06 para estas etapas. Seus gates dependem dos
            manifests da recuperação histórica anterior, não do backfill
            auditado por CodigoParlamentar.
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
            for required in [
                REPO_DIR / "processamento" / "normalizacao.py",
                REPO_DIR / "processamento" / "parquet.py",
                REPO_DIR / "analise" / "discursos_plenario" / "snapshot.py",
            ]:
                assert required.exists(), required
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
            BACKFILL_ID = "backfill-discursos-senadores-por-codigo-2010-20260714"
            DERIVATION_ID = f"{BACKFILL_ID}-derivados"
            DERIVATION_DIR = (
                DATA_ROOT / "operations" / "backfills" / "discursos_senadores_por_codigo" / DERIVATION_ID
            )
            PROCESSED_RUN_ID = "processed-textos-v1-current"
            PARQUET_RUN_ID = "parquet-textos-v1-current"
            ANALYSIS_RUN_ID = f"analise-plenario-{BACKFILL_ID}"
            SNAPSHOT_DIR = (
                DATA_ROOT / "analises" / "discursos_plenario" / "v1" / ANALYSIS_RUN_ID / "00_snapshot"
            )
            SNAPSHOT_PATH = SNAPSHOT_DIR / "discursos_plenario_snapshot.parquet"
            SNAPSHOT_MANIFEST = SNAPSHOT_DIR / "manifest.json"
            SNAPSHOT_CONFIG = REPO_DIR / "analise" / "discursos_plenario" / "config.v1.json"

            RODAR_DERIVADOS = False
            RODAR_SNAPSHOT = False
            VALIDAR_RESULTADOS = False
            CONFIRM_DERIVATION_ID = ""

            assert DATA_ROOT.exists(), DATA_ROOT
            assert SNAPSHOT_CONFIG.exists(), SNAPSHOT_CONFIG
            print("Auditoria:", AUDIT_DIR)
            print("Derivação:", DERIVATION_DIR)
            print("Snapshot:", SNAPSHOT_PATH)
            """,
            "configure_derivatives",
        ),
        code(
            """
            import hashlib
            import json
            import shutil
            import subprocess
            from datetime import datetime, timezone

            import pandas as pd
            from IPython.display import display
            from processamento.normalizacao import validate_jsonl_file

            TARGETS = {
                "plenario_discursos": {"arena": "senado", "parquet": "senado__plenario_discursos.parquet"},
                "congresso_discursos": {"arena": "congresso", "parquet": "senado__congresso_discursos.parquet"},
            }

            def confirmed():
                assert CONFIRM_DERIVATION_ID == DERIVATION_ID, (
                    "Preencha CONFIRM_DERIVATION_ID com o valor exato de DERIVATION_ID."
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

            def load_json(path):
                return json.loads(Path(path).read_text(encoding="utf-8"))

            def assert_post_audit_complete():
                summary_path = AUDIT_DIR / "senator_endpoint_summary.json"
                assert summary_path.exists(), summary_path
                summary = load_json(summary_path)
                assert summary["start"] == DATA_INICIO and summary["end"] == DATA_FIM, summary
                assert set(summary["houses"]) == {"SF", "CN"}, summary
                for field in ["errors", "invalid_probe_lines", "invalid_raw_lines", "source_conflicts", "missing_ids"]:
                    assert summary[field] == 0, summary
                assert set(summary["coverage_status_counts"]) == {"complete"}, summary
                return summary

            def processed_manifest_path():
                return DATA_ROOT / "processed" / "manifests" / f"{PROCESSED_RUN_ID}.json"

            def parquet_manifest_path():
                return DATA_ROOT / "processed" / "manifests" / f"{PARQUET_RUN_ID}-parquet.json"

            def assert_derivatives_complete():
                processed = load_json(processed_manifest_path())
                parquet = load_json(parquet_manifest_path())
                assert processed["run_id"] == PROCESSED_RUN_ID, processed
                assert processed["raw_run_id_filter"] == [], processed
                assert processed["output_records"] > 0, processed
                processed_root = DATA_ROOT / "processed" / "textos_parlamentares" / "v1"
                processed_paths = sorted(processed_root.rglob(f"{PROCESSED_RUN_ID}.jsonl"))
                assert processed_paths, processed_root
                valid_processed_records = sum(validate_jsonl_file(path) for path in processed_paths)
                assert valid_processed_records == processed["output_records"], {
                    "valid_processed_records": valid_processed_records,
                    "manifest_output_records": processed["output_records"],
                }
                assert parquet["run_id"] == f"{PARQUET_RUN_ID}-parquet", parquet
                assert parquet["output_records"] > 0, parquet
                for dataset, target in TARGETS.items():
                    parquet_path = (
                        DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet" / target["parquet"]
                    )
                    assert parquet_path.exists(), parquet_path
                return processed, parquet

            def sha256_file(path):
                digest = hashlib.sha256()
                with Path(path).open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                return digest.hexdigest()

            def archive(path):
                path = Path(path)
                target = DERIVATION_DIR / "artifacts" / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                return target

            def write_summary(payload):
                DERIVATION_DIR.mkdir(parents=True, exist_ok=True)
                path = DERIVATION_DIR / "summary.json"
                payload["derivation_id"] = DERIVATION_ID
                payload["created_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
                return path
            """,
            "helpers",
        ),
        code(
            """
            audit = assert_post_audit_complete()
            display({
                "audit_id": AUDIT_ID,
                "missing_ids": audit["missing_ids"],
                "coverage_status_counts": audit["coverage_status_counts"],
            })
            """,
            "verify_post_audit",
        ),
        markdown(
            """
            ## Reconstruir a fotografia current

            Esta etapa lê todo o raw cumulativo e substitui somente os
            derivados current. Ela não limita a leitura ao run de backfill:
            isso preserva todas as bases existentes no mesmo produto canônico.
            """
        ),
        code(
            """
            if RODAR_DERIVADOS:
                confirmed()
                assert_post_audit_complete()
                normalized = run_command([
                    sys.executable, "-u", "-m", "processamento.normalizacao",
                    "--mode", "prod", "--data-root", str(DATA_ROOT),
                    "--run-id", PROCESSED_RUN_ID, "--overwrite",
                ])
                assert normalized == 0
                parquet = run_command([
                    sys.executable, "-u", "-m", "processamento.parquet",
                    "--profile", "colab", "--data-root", str(DATA_ROOT),
                    "--run-id", PARQUET_RUN_ID, "--overwrite",
                ])
                assert parquet == 0
                processed, parquet_manifest = assert_derivatives_complete()
                display({
                    "processed_records": processed["output_records"],
                    "parquet_records": parquet_manifest["output_records"],
                    "processed_manifest": str(archive(processed_manifest_path())),
                    "parquet_manifest": str(archive(parquet_manifest_path())),
                })
            else:
                print("Derivados protegidos.")
            """,
            "rebuild_derivatives",
        ),
        markdown(
            """
            ## Criar o snapshot pós-backfill

            O snapshot recebe um run_id novo e imutável. Reexecutá-lo com a
            mesma confirmação substitui somente esse snapshot, nunca raw ou a
            fotografia current.
            """
        ),
        code(
            """
            if RODAR_SNAPSHOT:
                confirmed()
                assert_post_audit_complete()
                assert_derivatives_complete()
                from analise.discursos_plenario.snapshot import run_snapshot

                result = run_snapshot(
                    data_root=DATA_ROOT,
                    run_id=ANALYSIS_RUN_ID,
                    config_path=SNAPSHOT_CONFIG,
                    overwrite=True,
                )
                assert result["coverage_gate"]["passed"], result["coverage_gate"]
                assert SNAPSHOT_PATH.exists() and SNAPSHOT_MANIFEST.exists()
                display({
                    "snapshot": str(archive(SNAPSHOT_PATH)),
                    "manifest": str(archive(SNAPSHOT_MANIFEST)),
                    "rows_by_arena": result["counts"]["rows_by_arena"],
                })
            else:
                print("Snapshot protegido.")
            """,
            "build_snapshot",
        ),
        markdown(
            """
            ## Validação final

            Esta etapa confirma a auditoria pós-backfill, a fotografia
            processed, os Parquets-alvo e a cobertura do novo snapshot em 2015
            e 2016. Ela também deixa um summary auditável no Drive.
            """
        ),
        code(
            """
            if VALIDAR_RESULTADOS:
                confirmed()
                audit = assert_post_audit_complete()
                processed, parquet_manifest = assert_derivatives_complete()
                assert SNAPSHOT_PATH.exists() and SNAPSHOT_MANIFEST.exists()
                snapshot_manifest = load_json(SNAPSHOT_MANIFEST)
                assert snapshot_manifest["coverage_gate"]["passed"], snapshot_manifest["coverage_gate"]

                target_coverage = []
                for dataset, target in TARGETS.items():
                    parquet_path = (
                        DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet" / target["parquet"]
                    )
                    frame = pd.read_parquet(parquet_path)
                    assert frame["texto_id"].is_unique, parquet_path
                    for year in [2015, 2016]:
                        rows = frame.loc[pd.to_numeric(frame["ano"], errors="coerce").eq(year)]
                        assert not rows.empty, (dataset, year)
                        target_coverage.append({"layer": "parquet", "dataset": dataset, "year": year, "rows": int(len(rows))})

                snapshot = pd.read_parquet(SNAPSHOT_PATH)
                for dataset, target in TARGETS.items():
                    for year in [2015, 2016]:
                        rows = snapshot.loc[
                            snapshot["arena"].eq(target["arena"])
                            & pd.to_numeric(snapshot["ano"], errors="coerce").eq(year)
                        ]
                        assert not rows.empty, (target["arena"], year)
                        target_coverage.append({"layer": "snapshot", "dataset": dataset, "year": year, "rows": int(len(rows))})

                summary_path = write_summary({
                    "audit_summary": str(AUDIT_DIR / "senator_endpoint_summary.json"),
                    "processed_manifest": str(processed_manifest_path()),
                    "parquet_manifest": str(parquet_manifest_path()),
                    "snapshot_manifest": str(SNAPSHOT_MANIFEST),
                    "snapshot_sha256": sha256_file(SNAPSHOT_PATH),
                    "target_coverage": target_coverage,
                })
                display(pd.DataFrame(target_coverage))
                print("Aceito:", summary_path)
            else:
                print("Validação final protegida.")
            """,
            "validate_results",
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
