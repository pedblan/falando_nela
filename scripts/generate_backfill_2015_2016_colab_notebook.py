from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "coleta" / "06_backfill_discursos_senado_congresso_2015_2016_colab.ipynb"


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
            # Recuperação dos discursos de Senado e Congresso — 2015–2016

            Ciclo histórico isolado para diagnosticar a anomalia da lista mensal,
            recuperar pronunciamentos pelo índice oficial e reconciliar todas as
            camadas por identificador. Este caderno não faz parte da atualização
            incremental normal.
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
            import shutil
            import subprocess
            import sys

            REPO_URL = "https://github.com/pedblan/falando_nela.git"
            REPO_DIR = Path("/content/falando_nela")
            if not REPO_DIR.exists():
                subprocess.run(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
            else:
                subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], check=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REPO_DIR / "requirements.txt")], check=True)
            sys.path.insert(0, str(REPO_DIR))
            """,
            "setup_repository",
        ),
        md(
            """
            ## Configuração e confirmações

            Confira o identificador do ciclo antes de ativar qualquer flag. Os
            dois `run_id`s de coleta são estáveis e devem ser retomados com
            `--resume`; não crie novos IDs para contornar falhas.
            """
        ),
        code(
            """
            from datetime import datetime, timezone
            from importlib.metadata import PackageNotFoundError, version
            import json
            import os

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            CYCLE_ID = "backfill-discursos-senado-congresso-2015-2016-20260714"
            CYCLE_DIR = DATA_ROOT / "operations" / "atualizacao" / "ciclos" / CYCLE_ID
            ACTIVE_PATH = DATA_ROOT / "operations" / "atualizacao" / "active.json"
            START = "2015-01-01"
            END = "2016-12-31"
            RUNS = {
                "senado": {
                    "source": "senado",
                    "dataset": "plenario_discursos",
                    "module": "coleta.senado.plenario_discursos.collect",
                    "run_id": f"{CYCLE_ID}-senado",
                },
                "congresso": {
                    "source": "senado",
                    "dataset": "congresso_discursos",
                    "module": "coleta.senado.congresso_discursos.collect",
                    "run_id": f"{CYCLE_ID}-congresso",
                },
            }
            PROCESSED_RUN_ID = "processed-textos-v1-current"
            PARQUET_RUN_ID = "parquet-textos-v1-current"
            ANALYSIS_RUN_ID = f"analise-plenario-{CYCLE_ID}"
            SNAPSHOT_PATH = DATA_ROOT / "analises" / "discursos_plenario" / "v1" / ANALYSIS_RUN_ID / "00_snapshot" / "discursos_plenario_snapshot.parquet"

            CONFIRM_CYCLE_ID = ""
            RODAR_CONFIGURACAO = False
            ATIVAR_CICLO = False
            RODAR_AUDITORIA_PRE = False
            RODAR_PROBE_SENADORES = False
            RODAR_CONTROLES = False
            RODAR_SMOKES = False
            RODAR_SENADO = False
            RODAR_CONGRESSO = False
            VALIDAR_COLETAS = False
            RODAR_DERIVADOS = False
            RODAR_SNAPSHOT = False
            RODAR_RECONCILIACAO_POST = False
            ENCERRAR_CICLO = False

            os.environ["FALANDO_NELA_DATA_ROOT"] = str(DATA_ROOT)

            def dependency_version(package):
                try:
                    return version(package)
                except PackageNotFoundError:
                    return None

            print("Ciclo:", CYCLE_ID)
            print("Diretório:", CYCLE_DIR)
            """,
            "configure_cycle",
        ),
        code(
            """
            from contextlib import contextmanager

            def confirmed():
                assert CONFIRM_CYCLE_ID == CYCLE_ID, "Preencha CONFIRM_CYCLE_ID com o cycle_id exato."

            def run_command(command):
                print("Executando:", " ".join(map(str, command)))
                return subprocess.run([str(item) for item in command], cwd=REPO_DIR, check=False)

            def archive_manifest(path):
                path = Path(path)
                assert path.exists(), path
                destination = CYCLE_DIR / "manifests" / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                return destination

            @contextmanager
            def dataset_lock(run):
                lock_path = DATA_ROOT / "locks" / run["source"] / f"{run['dataset']}.lock"
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(descriptor, json.dumps({"cycle_id": CYCLE_ID, "run_id": run["run_id"]}).encode("utf-8"))
                    os.close(descriptor)
                    yield
                finally:
                    lock_path.unlink(missing_ok=True)

            def collector_command(run, *, smoke=False):
                command = [
                    sys.executable, "-m", run["module"],
                    "--mode", "prod" if not smoke else "dev",
                    "--output-dir", str(DATA_ROOT if not smoke else CYCLE_DIR / "smoke_data"),
                    "--data-inicio", START if not smoke else "2015-01-01",
                    "--data-fim", END if not smoke else "2015-01-31",
                    "--run-id", run["run_id"] if not smoke else f"smoke-{run['dataset']}-2015",
                    "--discovery-strategy", "historical-official",
                    "--resume",
                ]
                if not smoke:
                    command.append("--no-sample")
                return command

            CONTROL_MONTHS = {
                "senado": [("2014-05-01", "2014-05-31"), ("2017-03-01", "2017-03-31")],
                "congresso": [("2014-05-01", "2014-05-31"), ("2017-04-01", "2017-04-30")],
            }

            def control_command(name, run, start, end):
                return [
                    sys.executable, "-m", run["module"], "--mode", "prod",
                    "--output-dir", str(CYCLE_DIR / "control_data"),
                    "--data-inicio", start, "--data-fim", end,
                    "--run-id", f"control-{name}-{start[:7]}",
                    "--discovery-strategy", "historical-official",
                    "--no-sample", "--sample-limit", "1", "--resume",
                ]

            def assert_control_complete(name, run, start):
                control_run_id = f"control-{name}-{start[:7]}"
                root = CYCLE_DIR / "control_data"
                manifest = json.loads((root / "manifests" / f"{control_run_id}.json").read_text(encoding="utf-8"))
                assert manifest["status"] == "completed" and manifest["errors"] == 0, manifest
                metadata_path = root / "raw" / "senado" / run["dataset"] / "metadata" / f"{control_run_id}.jsonl"
                records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
                summary = next(record for record in records if record["record_type"] == "discursos_historical_discovery")
                audit = summary["payload"]["audit"]
                assert audit["primary_count"] > 0, audit
                assert audit["primary_missing_in_portal"] == [], audit
                return audit

            def assert_collection_complete(run):
                manifest_path = DATA_ROOT / "manifests" / f"{run['run_id']}.json"
                checkpoint_path = DATA_ROOT / "checkpoints" / run["source"] / f"{run['dataset']}.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                run_checkpoint = checkpoint["runs"][run["run_id"]]
                assert manifest["status"] == "completed" and manifest["errors"] == 0, manifest
                assert manifest["mode"] == "prod" and manifest["sample"] is False
                assert manifest["sample_limit"] is None
                assert manifest["data_inicio"] == START and manifest["data_fim"] == END
                assert manifest["discovery_strategy"] == "historical-official"
                expected = {f"{year}-{month:02d}" for year in (2015, 2016) for month in range(1, 13)}
                completed = set(run_checkpoint.get("completed_partitions", {}))
                failed = set(run_checkpoint.get("failed_partitions", {})) - completed
                assert expected.issubset(completed), sorted(expected - completed)
                assert not failed, sorted(failed)
                archive_manifest(manifest_path)
                return manifest
            """,
            "helpers",
        ),
        code(
            """
            if RODAR_CONFIGURACAO:
                confirmed()
                CYCLE_DIR.mkdir(parents=True, exist_ok=True)
                commit = subprocess.check_output(["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"], text=True).strip()
                config = {
                    "schema_version": 1,
                    "cycle_id": CYCLE_ID,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "collection_start": START,
                    "collection_end": END,
                    "overlap_start": START,
                    "raw_policy": "immutable_cumulative",
                    "processed_policy": "canonical_current",
                    "discovery_strategy": "historical-official",
                    "repository_commit": commit,
                    "dependency_versions": {
                        package: dependency_version(package)
                        for package in ("httpx", "pandas", "pyarrow", "nbformat")
                    },
                    "historical_recoveries": list(RUNS.values()),
                    "control_months": {"SF": ["2014-05", "2017-03"], "CN": ["2014-05", "2017-04"]},
                }
                (CYCLE_DIR / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
                print(CYCLE_DIR / "config.json")

            if ATIVAR_CICLO:
                confirmed()
                config = json.loads((CYCLE_DIR / "config.json").read_text(encoding="utf-8"))
                if ACTIVE_PATH.exists():
                    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
                    assert active.get("cycle_id") == CYCLE_ID, f"Outro ciclo está ativo: {active.get('cycle_id')}"
                ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
                ACTIVE_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
            """,
            "persist_cycle_config",
        ),
        code(
            """
            if RODAR_AUDITORIA_PRE:
                confirmed()
                result = run_command([
                    sys.executable, "-m", "processamento.reconciliacao_discursos",
                    "--data-root", DATA_ROOT, "--cycle-dir", CYCLE_DIR, "--phase", "pre",
                ])
                assert result.returncode == 0
            """,
            "audit_pre",
        ),
        code(
            """
            if RODAR_PROBE_SENADORES:
                confirmed()
                result = run_command([
                    sys.executable, "-m", "coleta.senado.auditoria_discursos_historicos",
                    "--cycle-dir", CYCLE_DIR, "--data-inicio", START, "--data-fim", END,
                    "--resume", "--strict",
                ])
                assert result.returncode == 0
            """,
            "probe_senator_endpoint",
        ),
        code(
            """
            if RODAR_CONTROLES:
                confirmed()
                for name, periods in CONTROL_MONTHS.items():
                    for start, end in periods:
                        result = run_command(control_command(name, RUNS[name], start, end))
                        assert result.returncode == 0
                        display(assert_control_complete(name, RUNS[name], start))
            """,
            "validate_control_months",
        ),
        code(
            """
            if RODAR_SMOKES:
                confirmed()
                for run in RUNS.values():
                    result = run_command(collector_command(run, smoke=True))
                    assert result.returncode == 0
            """,
            "smoke_collectors",
        ),
        code(
            """
            if RODAR_SENADO:
                confirmed()
                with dataset_lock(RUNS["senado"]):
                    run_command(collector_command(RUNS["senado"]))

            if RODAR_CONGRESSO:
                confirmed()
                with dataset_lock(RUNS["congresso"]):
                    run_command(collector_command(RUNS["congresso"]))
            """,
            "collect_production",
        ),
        code(
            """
            if VALIDAR_COLETAS:
                COLLECTION_MANIFESTS = {name: assert_collection_complete(run) for name, run in RUNS.items()}
                display({name: {"records": value["record_counts"], "source_anomalies": value["source_anomaly_partitions"]} for name, value in COLLECTION_MANIFESTS.items()})
            """,
            "validate_collections",
        ),
        code(
            """
            if RODAR_DERIVADOS:
                confirmed()
                for run in RUNS.values():
                    assert_collection_complete(run)
                normalized = run_command([
                    sys.executable, "-m", "processamento.normalizacao", "--mode", "prod",
                    "--data-root", DATA_ROOT, "--run-id", PROCESSED_RUN_ID, "--overwrite",
                ])
                assert normalized.returncode == 0
                parquet = run_command([
                    sys.executable, "-m", "processamento.parquet", "--profile", "colab",
                    "--data-root", DATA_ROOT, "--run-id", PARQUET_RUN_ID, "--overwrite",
                ])
                assert parquet.returncode == 0
                archive_manifest(DATA_ROOT / "processed" / "manifests" / f"{PROCESSED_RUN_ID}.json")
                parquet_manifests = sorted((DATA_ROOT / "processed" / "manifests").glob(f"{PARQUET_RUN_ID}*.json"))
                assert parquet_manifests
                archive_manifest(parquet_manifests[-1])
            """,
            "rebuild_canonical_derivatives",
        ),
        code(
            """
            if RODAR_SNAPSHOT:
                confirmed()
                from analise.discursos_plenario.snapshot import run_snapshot

                result = run_snapshot(
                    data_root=DATA_ROOT,
                    run_id=ANALYSIS_RUN_ID,
                    config_path=REPO_DIR / "analise" / "discursos_plenario" / "config.v1.json",
                    overwrite=False,
                )
                archive_manifest(result["manifest_path"])
                print(result["manifest_path"])
            """,
            "build_new_snapshot",
        ),
        code(
            """
            if RODAR_RECONCILIACAO_POST:
                confirmed()
                assert SNAPSHOT_PATH.exists(), SNAPSHOT_PATH
                result = run_command([
                    sys.executable, "-m", "processamento.reconciliacao_discursos",
                    "--data-root", DATA_ROOT, "--cycle-dir", CYCLE_DIR, "--phase", "post",
                    "--snapshot-path", SNAPSHOT_PATH, "--strict",
                ])
                assert result.returncode == 0
                display(json.loads((CYCLE_DIR / "summary.json").read_text(encoding="utf-8")))
            """,
            "reconcile_post",
        ),
        code(
            """
            if ENCERRAR_CICLO:
                confirmed()
                summary = json.loads((CYCLE_DIR / "summary.json").read_text(encoding="utf-8"))
                assert summary["passed"] is True, summary["gates"]
                if ACTIVE_PATH.exists():
                    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
                    assert active.get("cycle_id") == CYCLE_ID
                    ACTIVE_PATH.unlink()
                print("Ciclo aceito e removido do controle ativo:", CYCLE_ID)
            """,
            "close_cycle",
        ),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.update(
        {
            "colab": {"name": OUTPUT.name, "provenance": []},
            "falando_nela": {"narrative_language": "pt-BR", "generated_by": Path(__file__).name},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
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
            raise SystemExit(f"Notebook fora de sincronia: {OUTPUT.relative_to(ROOT)}")
        print(OUTPUT.relative_to(ROOT), "OK")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT.relative_to(ROOT), "WRITTEN" if current != content else "OK")


if __name__ == "__main__":
    main()
