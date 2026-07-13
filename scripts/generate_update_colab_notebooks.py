from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from textwrap import dedent

import nbformat


ROOT = Path(__file__).resolve().parents[1]
COLETA_DIR = ROOT / "notebooks" / "coleta"
PROCESSAMENTO_DIR = ROOT / "notebooks" / "processamento"


def md(source: str):
    return nbformat.v4.new_markdown_cell(dedent(source).strip())


def code(source: str):
    return nbformat.v4.new_code_cell(dedent(source).strip())


DRIVE_CELL = code(
    """
    from google.colab import drive

    drive.mount("/content/drive")
    """
)


SETUP_CELL = code(
    """
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
    ACTIVE_CONFIG_PATH = DATA_ROOT / "operations" / "atualizacao" / "active.json"
    REPO_URL = "https://github.com/pedblan/falando_nela.git"
    REPO_DIR = Path("/content/falando_nela")
    REPO_REF = ""  # Opcional: branch, tag ou commit. Vazio usa o default remoto.

    os.environ["FALANDO_NELA_DATA_ROOT"] = str(DATA_ROOT)
    for name in ["raw", "checkpoints", "logs", "manifests", "processed", "operations/atualizacao"]:
        (DATA_ROOT / name).mkdir(parents=True, exist_ok=True)

    if not REPO_DIR.exists():
        subprocess.run(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
    else:
        subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "--all", "--tags", "--prune"], check=True)
        if not REPO_REF:
            subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], check=True)
    if REPO_REF:
        subprocess.run(["git", "-C", str(REPO_DIR), "checkout", REPO_REF], check=True)

    os.chdir(REPO_DIR)
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    print("DATA_ROOT:", DATA_ROOT)
    print("Repositorio:", subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip())
    """
)


CONTROL_CELL = code(
    """
    EXPECTED_CYCLE_ID = "20260713"
    if not ACTIVE_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Controle ativo ausente: {ACTIVE_CONFIG_PATH}. Execute o caderno 00 primeiro.")
    CONFIG = json.loads(ACTIVE_CONFIG_PATH.read_text(encoding="utf-8"))
    assert CONFIG["schema_version"] == 1
    assert CONFIG["cycle_id"] == EXPECTED_CYCLE_ID, CONFIG["cycle_id"]
    assert CONFIG["window"] == {"data_inicio": "2026-05-01", "data_fim": "2026-07-13"}
    assert CONFIG["data_inicio"] == CONFIG["window"]["data_inicio"]
    assert CONFIG["data_fim"] == CONFIG["window"]["data_fim"]
    assert Path(CONFIG["data_root"]) == DATA_ROOT
    RUNS = {item["key"]: item for item in CONFIG["collection_runs"]}
    print("Ciclo ativo:", CONFIG["cycle_id"], CONFIG["window"])
    """
)


HELPERS_CELL = code(
    """
    from contextlib import contextmanager
    from datetime import datetime, timezone

    TERMINAL_STATUSES = {"completed"}

    def read_json(path):
        path = Path(path)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def manifest_for(run):
        return DATA_ROOT / "manifests" / f"{run['run_id']}.json"

    def checkpoint_for(run):
        return DATA_ROOT / "checkpoints" / run["source"] / f"{run['dataset']}.json"

    def unresolved_partitions(run):
        checkpoint = read_json(checkpoint_for(run)) or {}
        current = (checkpoint.get("runs") or {}).get(run["run_id"], {}) or {}
        failed = set((current.get("failed_partitions") or {}).keys())
        completed = set((current.get("completed_partitions") or {}).keys())
        return sorted(failed - completed)

    def assert_collection_complete(run):
        manifest = read_json(manifest_for(run))
        assert manifest is not None, f"Manifest final ausente: {manifest_for(run)}"
        assert manifest.get("run_id") == run["run_id"]
        assert manifest.get("status") in TERMINAL_STATUSES, (run["key"], manifest.get("status"))
        assert manifest.get("mode") == "prod", (run["key"], manifest.get("mode"))
        assert manifest.get("sample") is False, (run["key"], manifest.get("sample"))
        assert manifest.get("data_inicio") == run["data_inicio"], (run["key"], manifest.get("data_inicio"))
        assert manifest.get("data_fim") == run["data_fim"], (run["key"], manifest.get("data_fim"))
        unresolved = unresolved_partitions(run)
        assert not unresolved, f"Particoes falhas nao resolvidas em {run['key']}: {unresolved[:20]}"
        return manifest

    def show_run_state(run, tail_lines=5):
        final = read_json(manifest_for(run))
        autosave_path = DATA_ROOT / "manifests" / f"{run['run_id']}.autosave.json"
        autosave = read_json(autosave_path)
        log_path = DATA_ROOT / "logs" / f"{run['run_id']}.jsonl"
        tail = log_path.read_text(encoding="utf-8").splitlines()[-tail_lines:] if log_path.exists() else []
        print(run["key"], {
            "manifest": str(manifest_for(run)),
            "status": final.get("status") if final else None,
            "autosave_status": autosave.get("status") if autosave else None,
            "unresolved": unresolved_partitions(run),
            "log_tail": tail,
        })

    def collector_command(run, *extra):
        return [
            sys.executable, "-u", "-m", run["module"],
            "--mode", "prod",
            "--output-dir", str(DATA_ROOT),
            "--data-inicio", run["data_inicio"],
            "--data-fim", run["data_fim"],
            "--run-id", run["run_id"],
            "--no-sample", "--resume", *extra,
        ]

    def run_streamed(command, label):
        print(f"\\n=== {label} ===", flush=True)
        print(" ".join(map(str, command)), flush=True)
        completed = subprocess.run(list(map(str, command)), check=False)
        returncode = completed.returncode
        print(f"=== retorno {returncode}: {label} ===", flush=True)
        return returncode

    @contextmanager
    def dataset_lock(run):
        lock_root = DATA_ROOT / "operations" / "atualizacao" / "locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        lock_path = lock_root / f"{run['source']}__{run['dataset']}.json"
        payload = {
            "cycle_id": CONFIG["cycle_id"],
            "run_id": run["run_id"],
            "source": run["source"],
            "dataset": run["dataset"],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\\n")
        except FileExistsError as exc:
            raise RuntimeError(f"Dataset ja bloqueado por outra sessao: {lock_path}\\n{lock_path.read_text()}") from exc
        try:
            yield
        finally:
            if lock_path.exists() and read_json(lock_path) == payload:
                lock_path.unlink()

    def run_collector(run, *extra):
        with dataset_lock(run):
            return run_streamed(collector_command(run, *extra), run["key"])

    def require_explicit_confirmation(enabled, confirmation):
        if enabled:
            assert confirmation == EXPECTED_CYCLE_ID, "Digite o cycle_id na variavel CONFIRMAR_CICLO."

    def assert_parlamentares_ready():
        run_id = CONFIG["processing_run_ids"]["parlamentares"]
        manifest_path = DATA_ROOT / "processed" / "manifests" / f"{run_id}-parlamentares.json"
        periodos_path = DATA_ROOT / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
        manifest = read_json(manifest_path)
        assert manifest and manifest.get("run_id") == run_id and manifest.get("dataset_version") == "v1", manifest_path
        assert periodos_path.exists(), periodos_path
        return manifest
    """
)


def notebook(title: str, description: str, cells: list) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata.update(
        {
            "colab": {"name": title, "provenance": []},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        }
    )
    nb.cells = [md(f"# {title}\n\n{description}"), DRIVE_CELL, SETUP_CELL, *cells]
    return nb


def write_notebook(path: Path, nb: nbformat.NotebookNode) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    relative = path.relative_to(ROOT).as_posix()
    for index, cell in enumerate(nb.cells):
        stable_key = f"{relative}:{index}:{cell.cell_type}:{cell.source}".encode("utf-8")
        cell["id"] = sha256(stable_key).hexdigest()[:16]
    nbformat.validate(nb)
    nbformat.write(nb, path)
    print(path.relative_to(ROOT))


def build_00() -> nbformat.NotebookNode:
    return notebook(
        "00 - Auditoria e configuracao da atualizacao",
        "Monta o Drive antes do repositorio, inventaria o estado real e prepara o ciclo `20260713`. "
        "A gravacao fica bloqueada ate confirmacao explicita.",
        [
            code(
                """
                EXPECTED_CYCLE_ID = "20260713"
                CYCLE_DIR = DATA_ROOT / "operations" / "atualizacao" / "ciclos" / EXPECTED_CYCLE_ID
                WINDOW = {"data_inicio": "2026-05-01", "data_fim": "2026-07-13"}

                COLLECTION_RUNS = [
                    {"key": "parlamentares", "lane": "prerequisite", "module": "coleta.parlamentares.collect", "source": "all", "dataset": "parlamentares", "run_id": "prod-atualizacao-20260713-parlamentares", "data_inicio": "2026-05-01", "data_fim": "2026-07-13", "checkpoint_sources": ["camara", "senado"]},
                    {"key": "senado_ccj_historico", "lane": "senado", "module": "coleta.senado.ccj_notas.collect", "source": "senado", "dataset": "ccj_notas", "run_id": "prod-historico-senado-ccj", "data_inicio": "1900-01-01", "data_fim": "2026-05-28", "recovery": True},
                    {"key": "senado_plenario", "lane": "senado", "module": "coleta.senado.plenario_discursos.collect", "source": "senado", "dataset": "plenario_discursos", "run_id": "prod-atualizacao-20260713-senado-plenario", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "senado_ccj", "lane": "senado", "module": "coleta.senado.ccj_notas.collect", "source": "senado", "dataset": "ccj_notas", "run_id": "prod-atualizacao-20260713-senado-ccj", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "senado_pareceres_pec", "lane": "senado", "module": "coleta.senado.pareceres_pec.collect", "source": "senado", "dataset": "pareceres_pec", "run_id": "prod-atualizacao-20260713-senado-pareceres-pec", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "senado_apartes", "lane": "senado", "module": "coleta.senado.plenario_apartes.collect", "source": "senado", "dataset": "plenario_apartes", "run_id": "prod-atualizacao-20260713-senado-plenario-apartes", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "congresso_textos", "lane": "congresso", "module": "coleta.senado.congresso_discursos.collect", "source": "senado", "dataset": "congresso_discursos", "run_id": "prod-historico-senado-congresso-textos-v1", "data_inicio": "1996-05-01", "data_fim": "2026-07-13"},
                    {"key": "camara_ccjc_historico", "lane": "camara_demais", "module": "coleta.camara.ccjc_eventos.collect", "source": "camara", "dataset": "ccjc_eventos", "run_id": "prod-historico-camara-ccjc", "data_inicio": "1900-01-01", "data_fim": "2026-05-28", "recovery": True},
                    {"key": "camara_ccjc", "lane": "camara_demais", "module": "coleta.camara.ccjc_eventos.collect", "source": "camara", "dataset": "ccjc_eventos", "run_id": "prod-atualizacao-20260713-camara-ccjc", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "camara_pareceres_pec", "lane": "camara_demais", "module": "coleta.camara.pareceres_pec.collect", "source": "camara", "dataset": "pareceres_pec", "run_id": "prod-atualizacao-20260713-camara-pareceres-pec", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "camara_apartes", "lane": "camara_demais", "module": "coleta.camara.plenario_apartes.collect", "source": "camara", "dataset": "plenario_apartes", "run_id": "prod-atualizacao-20260713-camara-plenario-apartes", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                    {"key": "camara_plenario_historico", "lane": "camara_plenario", "module": "coleta.camara.plenario_discursos.collect", "source": "camara", "dataset": "plenario_discursos", "run_id": "prod-historico-camara-plenario", "data_inicio": "1946-01-01", "data_fim": "2026-05-28", "recovery": True},
                    {"key": "camara_plenario", "lane": "camara_plenario", "module": "coleta.camara.plenario_discursos.collect", "source": "camara", "dataset": "plenario_discursos", "run_id": "prod-atualizacao-20260713-camara-plenario", "data_inicio": "2026-05-01", "data_fim": "2026-07-13"},
                ]

                from datetime import datetime, timezone

                PROCESSING_RUN_IDS = {
                    "parlamentares": "processed-parlamentares-v1-current",
                    "textos": "processed-textos-v1-current",
                    "parquet": "parquet-textos-v1-current",
                    "apartes": "processed-apartes-parlamentares-v1-current",
                    "join_audit": "parlamentares-join-20260713",
                    "samples": "samples-textos-v1-20260713",
                }
                EXPECTED_TEXT_PARQUETS = [
                    "senado__plenario_discursos.parquet",
                    "senado__congresso_discursos.parquet",
                    "senado__ccj_notas.parquet",
                    "senado__pareceres_pec.parquet",
                    "camara__plenario_discursos.parquet",
                    "camara__ccjc_eventos.parquet",
                    "camara__pareceres_pec.parquet",
                ]
                EXPECTED_TEXT_DATASETS = [name.removesuffix(".parquet").replace("__", "/") for name in EXPECTED_TEXT_PARQUETS]

                CONFIG_CANDIDATE = {
                    "schema_version": 1,
                    "cycle_id": EXPECTED_CYCLE_ID,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "data_root": str(DATA_ROOT),
                    "data_inicio": WINDOW["data_inicio"],
                    "data_fim": WINDOW["data_fim"],
                    "window": WINDOW,
                    "historical_floor": "1900-01-01",
                    "raw_policy": "immutable_cumulative",
                    "processed_policy": "canonical_current",
                    "collection_runs": COLLECTION_RUNS,
                    "historical_recoveries": [item for item in COLLECTION_RUNS if item.get("recovery")],
                    "run_ids": {
                        "collection": {item["key"]: item["run_id"] for item in COLLECTION_RUNS},
                        "processing": PROCESSING_RUN_IDS,
                    },
                    "processing_run_ids": PROCESSING_RUN_IDS,
                    "expected_text_datasets": EXPECTED_TEXT_DATASETS,
                    "expected_text_parquets": EXPECTED_TEXT_PARQUETS,
                    "expected_apartes_sources": ["senado", "camara"],
                    "expected_processed_bases": ["textos_parlamentares/v1", "parlamentares/v1", "apartes_parlamentares/v1"],
                    "expected_processed_outputs": [
                        "processed/textos_parlamentares/v1",
                        "processed/parlamentares/v1",
                        "processed/apartes_parlamentares/v1",
                    ],
                }
                print(json.dumps(CONFIG_CANDIDATE, ensure_ascii=False, indent=2))
                """
            ),
            md("## Inventario read-only\n\nConfere pastas, manifests, autosaves, checkpoints, Parquets e locks antes de gravar o ciclo."),
            code(
                """
                def compact_manifest(path):
                    item = read_json(path) or {}
                    return {
                        "arquivo": path.name,
                        "status": item.get("status"),
                        "source": item.get("source"),
                        "dataset": item.get("dataset"),
                        "data_inicio": item.get("data_inicio"),
                        "data_fim": item.get("data_fim"),
                        "errors": item.get("errors"),
                    }

                def read_json(path):
                    path = Path(path)
                    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

                import pyarrow.parquet as pq

                print("Pasta ativa existe:", DATA_ROOT.exists(), DATA_ROOT)
                manifest_paths = [path for path in (DATA_ROOT / "manifests").glob("*.json") if not path.name.endswith(".autosave.json")]
                manifests = [read_json(path) for path in manifest_paths]
                dataset_cutoffs = {}
                for item in manifests:
                    if not item or not item.get("dataset") or not item.get("data_fim"):
                        continue
                    dataset_cutoffs[item["dataset"]] = max(item["data_fim"], dataset_cutoffs.get(item["dataset"], ""))
                print("Manifestos finais:", len(manifest_paths))
                print("Autosaves:", len(list((DATA_ROOT / "manifests").glob("*.autosave.json"))))
                print("Checkpoints:", len(list((DATA_ROOT / "checkpoints").rglob("*.json"))))
                parquet_root = DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"
                parquet_paths = sorted(parquet_root.glob("*.parquet"))
                parquet_rows = {path.name: pq.ParquetFile(path).metadata.num_rows for path in parquet_paths}
                print("Parquets textuais:", parquet_rows, "total=", sum(parquet_rows.values()))
                print("Cortes por dataset:", dataset_cutoffs)
                print("Locks ativos:", sorted(path.name for path in (DATA_ROOT / "operations" / "atualizacao" / "locks").glob("*.json")))

                known_state = {
                    "prod-historico-camara-plenario": read_json(DATA_ROOT / "manifests" / "prod-historico-camara-plenario.autosave.json"),
                    "prod-historico-senado-ccj": read_json(DATA_ROOT / "manifests" / "prod-historico-senado-ccj.json"),
                    "prod-historico-camara-ccjc": read_json(DATA_ROOT / "manifests" / "prod-historico-camara-ccjc.json"),
                }
                baseline_warnings = []
                if (known_state["prod-historico-camara-plenario"] or {}).get("status") != "running":
                    baseline_warnings.append("Autosave do Plenario da Camara nao esta mais em running; revisar antes de gravar.")
                if (known_state["prod-historico-senado-ccj"] or {}).get("errors") != 2:
                    baseline_warnings.append("A CCJ do Senado nao apresenta mais os 2 erros inventariados; revisar o novo estado.")
                if (known_state["prod-historico-camara-ccjc"] or {}).get("errors") != 33:
                    baseline_warnings.append("A CCJC da Camara nao apresenta mais os 33 erros inventariados; revisar o novo estado.")
                if len(parquet_rows) != 6 or sum(parquet_rows.values()) != 407084:
                    baseline_warnings.append("A fotografia anterior diverge de seis Parquets/407.084 textos; registrar a mudanca.")
                if dataset_cutoffs.get("plenario_apartes") not in {None, "2026-05-18"}:
                    baseline_warnings.append(f"O corte de apartes diverge de 2026-05-18: {dataset_cutoffs.get('plenario_apartes')}")
                print("AVISOS DO BASELINE:", baseline_warnings or "nenhum")

                for run in COLLECTION_RUNS:
                    final_path = DATA_ROOT / "manifests" / f"{run['run_id']}.json"
                    autosave_path = DATA_ROOT / "manifests" / f"{run['run_id']}.autosave.json"
                    unresolved = {}
                    for source in run.get("checkpoint_sources") or [run["source"]]:
                        checkpoint = read_json(DATA_ROOT / "checkpoints" / source / f"{run['dataset']}.json") or {}
                        current = (checkpoint.get("runs") or {}).get(run["run_id"], {}) or {}
                        failed = set((current.get("failed_partitions") or {}).keys())
                        completed = set((current.get("completed_partitions") or {}).keys())
                        unresolved[source] = sorted(failed - completed)
                    print(run["key"], "final=", compact_manifest(final_path) if final_path.exists() else None,
                          "autosave=", compact_manifest(autosave_path) if autosave_path.exists() else None,
                          "falhas_nao_resolvidas=", unresolved)

                INVENTORY_REPORT = {
                    "cycle_id": EXPECTED_CYCLE_ID,
                    "data_root": str(DATA_ROOT),
                    "manifest_count": len(manifest_paths),
                    "dataset_cutoffs": dataset_cutoffs,
                    "previous_text_parquets": parquet_rows,
                    "previous_text_rows": sum(parquet_rows.values()),
                    "known_state": known_state,
                    "warnings": baseline_warnings,
                }
                """
            ),
            md("## Gravar controle\n\nRevise o inventario. A celula recusa sobrescrever outro ciclo e exige que o `cycle_id` seja digitado."),
            code(
                """
                GRAVAR_CONFIGURACAO = False
                CONFIRMAR_CICLO = ""  # Digite 20260713.
                SOBRESCREVER_MESMO_CICLO = False

                if GRAVAR_CONFIGURACAO:
                    assert CONFIRMAR_CICLO == EXPECTED_CYCLE_ID
                    existing = read_json(ACTIVE_CONFIG_PATH)
                    if existing:
                        assert existing.get("cycle_id") == EXPECTED_CYCLE_ID, f"Outro ciclo esta ativo: {existing.get('cycle_id')}"
                        assert SOBRESCREVER_MESMO_CICLO, "Ative SOBRESCREVER_MESMO_CICLO apos revisar o active.json existente."
                    CYCLE_DIR.mkdir(parents=True, exist_ok=True)
                    serialized = json.dumps(CONFIG_CANDIDATE, ensure_ascii=False, indent=2, sort_keys=True) + "\\n"
                    ACTIVE_CONFIG_PATH.write_text(serialized, encoding="utf-8")
                    (CYCLE_DIR / "config.json").write_text(serialized, encoding="utf-8")
                    audit_dir = CYCLE_DIR / "audits"
                    audit_dir.mkdir(parents=True, exist_ok=True)
                    (audit_dir / "initial_inventory.json").write_text(
                        json.dumps(INVENTORY_REPORT, ensure_ascii=False, indent=2, sort_keys=True) + "\\n",
                        encoding="utf-8",
                    )
                    print("Controle gravado:", ACTIVE_CONFIG_PATH)
                    print("Copia do ciclo:", CYCLE_DIR / "config.json")
                else:
                    print("Somente auditoria: GRAVAR_CONFIGURACAO=False")
                """
            ),
        ],
    )


def build_01() -> nbformat.NotebookNode:
    return notebook(
        "01 - Atualizacao de parlamentares",
        "Atualiza deputados e senadores com endpoints de detalhe e regenera `parlamentares/v1` antes das faixas da Camara.",
        [
            CONTROL_CELL,
            HELPERS_CELL,
            code(
                """
                RODAR_COLETA = False
                RODAR_PROCESSAMENTO = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_COLETA or RODAR_PROCESSAMENTO, CONFIRMAR_CICLO)

                run = RUNS["parlamentares"]
                if RODAR_COLETA:
                    rc = run_collector(run, "--source", "all")
                    assert rc == 0
                    assert_collection_complete(run)

                if RODAR_PROCESSAMENTO:
                    command = [
                        sys.executable, "-u", "-m", "processamento.parlamentares",
                        "--mode", "prod", "--data-root", str(DATA_ROOT),
                        "--run-id", CONFIG["processing_run_ids"]["parlamentares"],
                        "--data-inicio", CONFIG["historical_floor"],
                        "--data-fim", CONFIG["window"]["data_fim"], "--overwrite",
                    ]
                    assert run_streamed(command, "processar parlamentares/v1 current") == 0
                """
            ),
            md("## Gate de parlamentares e mandatos"),
            code(
                """
                import pyarrow.parquet as pq

                show_run_state(RUNS["parlamentares"])
                assert_collection_complete(RUNS["parlamentares"])
                proc_run = CONFIG["processing_run_ids"]["parlamentares"]
                proc_manifest_path = DATA_ROOT / "processed" / "manifests" / f"{proc_run}-parlamentares.json"
                proc_manifest = read_json(proc_manifest_path)
                assert proc_manifest and proc_manifest.get("dataset_version") == "v1"
                periodos_path = DATA_ROOT / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
                assert periodos_path.exists()
                table = pq.read_table(periodos_path, columns=["parlamentar_id", "source", "vigencia_inicio", "vigencia_fim"])
                assert table.num_rows > 0
                rows = table.to_pylist()
                assert all(row["parlamentar_id"] and row["source"] and row["vigencia_inicio"] for row in rows)
                invalid = [row for row in rows if row.get("vigencia_fim") and row["vigencia_inicio"] > row["vigencia_fim"]]
                assert not invalid, invalid[:10]
                print("Gate aprovado:", table.num_rows, "periodos de mandato")
                """
            ),
        ],
    )


def lane_notebook(title: str, description: str, run_keys: list[str]) -> nbformat.NotebookNode:
    keys_repr = repr(run_keys)
    return notebook(
        title,
        description,
        [
            CONTROL_CELL,
            HELPERS_CELL,
            code(
                f"""
                RUN_KEYS = {keys_repr}
                RODAR_FAIXA = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_FAIXA, CONFIRMAR_CICLO)

                if RODAR_FAIXA:
                    assert_parlamentares_ready()
                    for key in RUN_KEYS:
                        run = RUNS[key]
                        rc = run_collector(run)
                        assert rc == 0, (key, rc)
                        assert_collection_complete(run)
                else:
                    print("Faixa protegida: RODAR_FAIXA=False")
                """
            ),
            md("## Validacao da faixa"),
            code(
                """
                for key in RUN_KEYS:
                    run = RUNS[key]
                    show_run_state(run)
                    path = manifest_for(run)
                    if path.exists():
                        manifest = assert_collection_complete(run)
                        print(key, manifest.get("status"), manifest.get("record_counts", {}))
                    else:
                        print(key, "PENDENTE", path)
                """
            ),
            md(
                """
                Se uma sessao caiu e deixou lock, confirme no log que nao existe outra sessao ativa.
                Remova manualmente apenas o arquivo correspondente em
                `operations/atualizacao/locks/` e execute de novo com o mesmo `run_id` e `--resume`.
                """
            ),
        ],
    )


def build_03() -> nbformat.NotebookNode:
    return notebook(
        "03 - Backfill textual do Congresso",
        "Valida o texto integral em marco de 2000 e executa a esteira mensal `CN` ate `2026-07-13` com `run_id` proprio.",
        [
            CONTROL_CELL,
            HELPERS_CELL,
            code(
                """
                RODAR_VALIDACAO_CURTA = False
                CONFIRMAR_VALIDACAO = ""
                if RODAR_VALIDACAO_CURTA:
                    assert CONFIRMAR_VALIDACAO == EXPECTED_CYCLE_ID
                    smoke_root = REPO_DIR / "data" / "dev" / "congresso_textos_20260713"
                    command = [
                        sys.executable, "-u", "-m", "coleta.senado.congresso_discursos.collect",
                        "--mode", "dev", "--output-dir", str(smoke_root),
                        "--data-inicio", "2000-03-01", "--data-fim", "2000-03-31",
                        "--run-id", "smoke-congresso-textos-20260713", "--sample-limit", "3", "--resume",
                    ]
                    assert run_streamed(command, "smoke textual do Congresso") == 0
                    raw_paths = list((smoke_root / "raw" / "senado" / "congresso_discursos").glob("ano=*/mes=*/*.jsonl"))
                    records = [json.loads(line) for path in raw_paths for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    assert records and all(item["record_type"] == "pronunciamento_texto" for item in records)
                    assert all(str(item["payload"].get("texto") or "").strip() for item in records)
                    metadata_path = smoke_root / "raw" / "senado" / "congresso_discursos" / "metadata" / "smoke-congresso-textos-20260713.jsonl"
                    metadata = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    assert metadata and all(item["request"]["params"].get("siglaCasa") == "CN" for item in metadata)
                    print("Smoke aprovado:", len(records), "textos")
                """
            ),
            code(
                """
                RODAR_BACKFILL = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_BACKFILL, CONFIRMAR_CICLO)
                run = RUNS["congresso_textos"]
                if RODAR_BACKFILL:
                    assert_parlamentares_ready()
                    rc = run_collector(run)
                    assert rc == 0
                    assert_collection_complete(run)
                else:
                    print("Backfill protegido: RODAR_BACKFILL=False")
                """
            ),
            md("## Auditoria do corpus textual"),
            code(
                """
                if manifest_for(run).exists():
                    manifest = assert_collection_complete(run)
                    show_run_state(run)
                    corpus = DATA_ROOT / "raw" / "senado" / "congresso_discursos"
                    monthly = list(corpus.glob("ano=*/mes=*/*.jsonl"))
                    queue = corpus / "transcription_queue" / f"{run['run_id']}.jsonl"
                    print("Manifest:", manifest_for(run))
                    print("Arquivos mensais:", len(monthly))
                    print("Fila de transcricao:", queue, queue.exists())
                    assert monthly, "Manifest final sem arquivos textuais mensais."
                else:
                    print("Backfill ainda pendente:", manifest_for(run))
                """
            ),
        ],
    )


def build_05() -> nbformat.NotebookNode:
    return notebook(
        "05 - Atualizacao do Plenario da Camara",
        "Retoma primeiro `prod-historico-camara-plenario`. A retomada historica rapida exige uma fronteira limpa de checkpoint e usa uma copia local do plano de mandatos. A faixa incremental so e liberada depois do manifest historico final.",
        [
            CONTROL_CELL,
            HELPERS_CELL,
            md(
                """
                ## Preparacao da retomada historica

                O run historico possui centenas de milhares de registros ja gravados. Se houver
                uma particao parcial, o coletor restringe o indice de duplicatas aos anos abertos
                ou com falha, sem reler os anos ja concluidos. Em uma fronteira limpa, ele so
                aceita `--skip-existing-record-scan` quando checkpoint e log concordam. O Parquet
                pequeno de periodos e copiado para o disco local efemero do runtime; o raw continua
                no Drive, imutavel e cumulativo.
                """
            ),
            code(
                """
                import shutil

                historical = RUNS["camara_plenario_historico"]
                incremental = RUNS["camara_plenario"]
                LOCAL_RUNTIME_ROOT = Path("/content/falando_nela_runtime")

                def cache_parlamentares_periodos():
                    source = DATA_ROOT / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
                    target = LOCAL_RUNTIME_ROOT / "parlamentares_periodos.parquet"
                    assert source.is_file(), source
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    assert target.is_file() and target.stat().st_size == source.stat().st_size, (source, target)
                    print("Plano de mandatos copiado para o runtime local:", target, target.stat().st_size, "bytes")
                    return target

                def inspect_resume_boundary(run):
                    checkpoint = read_json(checkpoint_for(run)) or {}
                    current = (checkpoint.get("runs") or {}).get(run["run_id"], {}) or {}
                    requested_partitions = {
                        str(year)
                        for year in range(int(run["data_inicio"][:4]), int(run["data_fim"][:4]) + 1)
                    }
                    completed = set((current.get("completed_partitions") or {}).keys()) & requested_partitions
                    failed = set((current.get("failed_partitions") or {}).keys()) & requested_partitions
                    unresolved = failed - completed
                    open_partitions = set()
                    completed_in_log = set()
                    log_path = DATA_ROOT / "logs" / f"{run['run_id']}.jsonl"
                    if log_path.exists():
                        with log_path.open("r", encoding="utf-8") as handle:
                            for line in handle:
                                try:
                                    event = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                if event.get("run_id") != run["run_id"] or not isinstance(event.get("partition"), str):
                                    continue
                                partition = event["partition"]
                                if partition not in requested_partitions:
                                    continue
                                if event.get("event") == "partition_started":
                                    open_partitions.add(partition)
                                elif event.get("event") == "partition_completed":
                                    completed_in_log.add(partition)
                                    open_partitions.discard(partition)
                                elif event.get("event") == "partition_failed":
                                    open_partitions.discard(partition)
                    missing_log_completion = completed - completed_in_log
                    clean = bool(completed) and not unresolved and not open_partitions and not missing_log_completion
                    state = {
                        "run_id": run["run_id"],
                        "completed_partitions": len(completed),
                        "unresolved": sorted(unresolved),
                        "open_partitions": sorted(open_partitions),
                        "checkpoint_completions_missing_in_log": sorted(missing_log_completion),
                        "fast_boundary": clean,
                    }
                    print("Estado da retomada:", state)
                    return state

                HISTORICAL_RESUME_STATE = inspect_resume_boundary(historical)
                """
            ),
            code(
                """
                RODAR_RECUPERACAO_HISTORICA = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_RECUPERACAO_HISTORICA, CONFIRMAR_CICLO)
                if RODAR_RECUPERACAO_HISTORICA:
                    assert_parlamentares_ready()
                    local_periodos = cache_parlamentares_periodos()
                    recovery_extra = ["--parlamentares-periodos-path", local_periodos]
                    if HISTORICAL_RESUME_STATE["fast_boundary"]:
                        recovery_extra.append("--skip-existing-record-scan")
                        print("Fronteira limpa: a varredura integral do raw sera pulada.")
                    else:
                        print(
                            "Particao parcial detectada: o coletor reconstruira o indice apenas "
                            "para os anos abertos ou com falha e exibira o progresso."
                        )
                    rc = run_collector(
                        historical,
                        *recovery_extra,
                    )
                    assert rc == 0
                    assert_collection_complete(historical)
                else:
                    print("Recuperacao protegida: RODAR_RECUPERACAO_HISTORICA=False")
                """
            ),
            code(
                """
                RODAR_FAIXA_INCREMENTAL = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_FAIXA_INCREMENTAL, CONFIRMAR_CICLO)
                if RODAR_FAIXA_INCREMENTAL:
                    assert_parlamentares_ready()
                    assert_collection_complete(historical)  # gate obrigatorio
                    local_periodos = cache_parlamentares_periodos()
                    rc = run_collector(
                        incremental,
                        "--parlamentares-periodos-path", local_periodos,
                    )
                    assert rc == 0
                    assert_collection_complete(incremental)
                else:
                    print("Incremental protegido: RODAR_FAIXA_INCREMENTAL=False")
                """
            ),
            md("## Estado dos dois manifests"),
            code(
                """
                for run in [historical, incremental]:
                    show_run_state(run)
                    manifest = read_json(manifest_for(run))
                    print(run["key"], manifest.get("status") if manifest else "PENDENTE", "unresolved=", unresolved_partitions(run))
                """
            ),
        ],
    )


def build_06() -> nbformat.NotebookNode:
    return notebook(
        "06 - Processamento e validacao da atualizacao",
        "Aplica gates a todas as coletas, regenera a fotografia `current`, valida os sete Parquets e arquiva os artefatos operacionais do ciclo.",
        [
            CONTROL_CELL,
            HELPERS_CELL,
            md("## Gate bloqueante de coleta"),
            code(
                """
                GATE_RESULTS = {}
                for key, run in RUNS.items():
                    try:
                        manifest = assert_collection_complete(run)
                        GATE_RESULTS[key] = {"ok": True, "status": manifest.get("status"), "manifest": str(manifest_for(run))}
                    except Exception as exc:
                        GATE_RESULTS[key] = {"ok": False, "error": str(exc), "manifest": str(manifest_for(run))}

                for key, result in GATE_RESULTS.items():
                    print(key, result)
                parlamentares_run = CONFIG["processing_run_ids"]["parlamentares"]
                parlamentares_manifest = DATA_ROOT / "processed" / "manifests" / f"{parlamentares_run}-parlamentares.json"
                parlamentares_periodos = DATA_ROOT / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
                PARLAMENTARES_GATE_OK = parlamentares_manifest.exists() and parlamentares_periodos.exists()
                COLLECTION_GATE_OK = all(item["ok"] for item in GATE_RESULTS.values()) and PARLAMENTARES_GATE_OK
                print("PARLAMENTARES_GATE_OK=", PARLAMENTARES_GATE_OK)
                print("COLLECTION_GATE_OK=", COLLECTION_GATE_OK)
                """
            ),
            md("## Auditoria JSONL bloqueante\n\nA leitura pode ser longa no Drive, mas nao faz requisicoes externas nem altera o raw."),
            code(
                """
                RODAR_AUDITORIA_JSONL = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_AUDITORIA_JSONL, CONFIRMAR_CICLO)
                JSONL_GATE_OK = False
                if RODAR_AUDITORIA_JSONL:
                    assert COLLECTION_GATE_OK
                    audit = {"cycle_id": EXPECTED_CYCLE_ID, "runs": {}, "invalid": []}
                    for key, run in RUNS.items():
                        sources = run.get("checkpoint_sources") or [run["source"]]
                        paths = []
                        for source in sources:
                            paths.extend((DATA_ROOT / "raw" / source / run["dataset"]).rglob(f"{run['run_id']}.jsonl"))
                        paths = sorted(set(paths))
                        records = 0
                        for path in paths:
                            with path.open("r", encoding="utf-8") as handle:
                                for line_number, line in enumerate(handle, start=1):
                                    if not line.strip():
                                        continue
                                    try:
                                        value = json.loads(line)
                                        if not isinstance(value, dict):
                                            raise ValueError("linha JSONL nao e objeto")
                                        records += 1
                                    except Exception as exc:
                                        audit["invalid"].append({"path": str(path), "line": line_number, "error": str(exc)})
                                        if len(audit["invalid"]) >= 100:
                                            break
                            if len(audit["invalid"]) >= 100:
                                break
                        audit["runs"][key] = {"files": len(paths), "records": records}
                        print(key, audit["runs"][key])
                        if not paths:
                            audit["invalid"].append({"run": key, "error": "nenhum JSONL encontrado"})
                    JSONL_GATE_OK = not audit["invalid"]
                    audit["ok"] = JSONL_GATE_OK
                    audit_path = DATA_ROOT / "operations" / "atualizacao" / "ciclos" / EXPECTED_CYCLE_ID / "audits" / "raw_jsonl.json"
                    audit_path.parent.mkdir(parents=True, exist_ok=True)
                    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
                    assert JSONL_GATE_OK, audit["invalid"][:20]
                    print("JSONL_GATE_OK=True", audit_path)
                else:
                    print("Auditoria protegida: RODAR_AUDITORIA_JSONL=False")
                """
            ),
            code(
                """
                RODAR_PROCESSAMENTO = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(RODAR_PROCESSAMENTO, CONFIRMAR_CICLO)
                if RODAR_PROCESSAMENTO:
                    assert COLLECTION_GATE_OK, "Processamento bloqueado pelos gates de coleta."
                    assert JSONL_GATE_OK, "Processamento bloqueado ate a auditoria JSONL desta sessao passar."
                    process_runs = CONFIG["processing_run_ids"]
                    commands = [
                        ([sys.executable, "-u", "-m", "processamento.normalizacao", "--mode", "prod", "--data-root", str(DATA_ROOT), "--run-id", process_runs["textos"], "--overwrite"], "normalizar textos current"),
                        ([sys.executable, "-u", "-m", "processamento.apartes_parlamentares", "--mode", "prod", "--data-root", str(DATA_ROOT), "--run-id", process_runs["apartes"], "--overwrite"], "processar apartes current"),
                        ([sys.executable, "-u", "-m", "processamento.parquet", "--profile", "colab", "--data-root", str(DATA_ROOT), "--run-id", process_runs["parquet"], "--overwrite"], "gerar sete Parquets"),
                        ([sys.executable, "-u", "-m", "processamento.parlamentares_join_audit", "--profile", "colab", "--data-root", str(DATA_ROOT), "--run-id", process_runs["join_audit"], "--overwrite"], "auditar joins"),
                        ([sys.executable, "-u", "-m", "processamento.samples", "--profile", "colab", "--data-root", str(DATA_ROOT), "--run-id", process_runs["samples"], "--include-parquet", "--overwrite"], "gerar ZIPs de amostra"),
                    ]
                    for command, label in commands:
                        assert run_streamed(command, label) == 0, label
                else:
                    print("Processamento protegido: RODAR_PROCESSAMENTO=False")
                """
            ),
            md("## Validacao dos sete Parquets e dos derivados"),
            code(
                """
                import pyarrow.compute as pc
                import pyarrow.parquet as pq

                parquet_root = DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"
                actual_names = sorted(path.name for path in parquet_root.glob("*.parquet"))
                expected_names = sorted(CONFIG["expected_text_parquets"])
                assert actual_names == expected_names, {"expected": expected_names, "actual": actual_names}

                total_rows = 0
                seen_ids = set()
                for name in expected_names:
                    path = parquet_root / name
                    expected_source, expected_dataset = name.removesuffix(".parquet").split("__", maxsplit=1)
                    table = pq.read_table(path, columns=["texto_id", "source", "dataset", "dataset_version", "texto"])
                    ids = table.column("texto_id").to_pylist()
                    versions = set(table.column("dataset_version").to_pylist())
                    texts = table.column("texto").to_pylist()
                    assert set(table.column("source").to_pylist()) == {expected_source}
                    assert set(table.column("dataset").to_pylist()) == {expected_dataset}
                    assert len(ids) == len(set(ids)), f"texto_id duplicado dentro de {name}"
                    overlap = seen_ids.intersection(ids)
                    assert not overlap, f"texto_id repetido entre bases: {next(iter(overlap))}"
                    seen_ids.update(ids)
                    assert versions == {"v1"}, (name, versions)
                    assert all(isinstance(value, str) and value.strip() for value in texts), f"texto vazio em {name}"
                    total_rows += table.num_rows
                    print(name, table.num_rows)

                normal_manifest = read_json(DATA_ROOT / "processed" / "manifests" / f"{CONFIG['processing_run_ids']['textos']}.json")
                assert normal_manifest
                assert normal_manifest.get("run_id") == CONFIG["processing_run_ids"]["textos"]
                assert normal_manifest.get("dataset_version") == "v1"
                assert total_rows == normal_manifest.get("output_records"), (total_rows, normal_manifest)
                expected_raw_run_ids = {
                    run["run_id"]
                    for run in RUNS.values()
                    if f"{run['source']}/{run['dataset']}" in CONFIG["expected_text_datasets"]
                }
                observed_raw_run_ids = set(normal_manifest.get("raw_run_ids", []))
                assert expected_raw_run_ids <= observed_raw_run_ids, sorted(expected_raw_run_ids - observed_raw_run_ids)

                initial_inventory_path = DATA_ROOT / "operations" / "atualizacao" / "ciclos" / EXPECTED_CYCLE_ID / "audits" / "initial_inventory.json"
                initial_inventory = read_json(initial_inventory_path) or {}
                previous_total_rows = int(initial_inventory.get("previous_text_rows") or 0)
                JUSTIFICATIVA_REDUCAO = ""  # Preencha somente se uma reducao tiver sido investigada e aceita.
                if total_rows < previous_total_rows:
                    assert JUSTIFICATIVA_REDUCAO.strip(), (previous_total_rows, total_rows)
                ROW_COMPARISON = {
                    "previous_text_rows": previous_total_rows,
                    "current_text_rows": total_rows,
                    "delta": total_rows - previous_total_rows,
                    "reduction_justification": JUSTIFICATIVA_REDUCAO or None,
                }

                proc_runs = CONFIG["processing_run_ids"]
                parlamentares_path = DATA_ROOT / "processed" / "manifests" / f"{proc_runs['parlamentares']}-parlamentares.json"
                apartes_manifest_path = DATA_ROOT / "processed" / "manifests" / f"{proc_runs['apartes']}-apartes-parlamentares.json"
                apartes_path = DATA_ROOT / "processed" / "apartes_parlamentares" / "v1" / "parquet" / "apartes_parlamentares.parquet"
                join_path = DATA_ROOT / "processed" / "audits" / "parlamentares" / proc_runs["join_audit"] / "manifest.json"
                samples_path = DATA_ROOT / "processed" / "downloads" / proc_runs["samples"] / "manifest.json"
                required_paths = [parlamentares_path, apartes_manifest_path, apartes_path, join_path, samples_path]
                for path in required_paths:
                    assert path.exists(), path

                parlamentares_manifest = read_json(parlamentares_path)
                assert parlamentares_manifest.get("run_id") == proc_runs["parlamentares"]
                assert parlamentares_manifest.get("dataset_version") == "v1"
                assert all(Path(path).exists() for path in parlamentares_manifest.get("output_files", {}).values())
                assert all(Path(path).exists() for path in parlamentares_manifest.get("parquet_files", {}).values())
                apartes_manifest = read_json(apartes_manifest_path)
                apartes_table = pq.read_table(apartes_path, columns=["source"])
                assert apartes_manifest.get("run_id") == proc_runs["apartes"]
                assert apartes_manifest.get("dataset_version") == "v1"
                assert all(Path(path).exists() for path in apartes_manifest.get("output_files", {}).values())
                assert all(Path(path).exists() for path in apartes_manifest.get("parquet_files", {}).values())
                assert apartes_table.num_rows == apartes_manifest.get("output_records")
                assert set(apartes_table.column("source").to_pylist()) == set(CONFIG["expected_apartes_sources"])
                join_manifest = read_json(join_path)
                assert join_manifest.get("run_id") == proc_runs["join_audit"]
                assert join_manifest.get("textos_lidos") == total_rows
                samples_manifest = read_json(samples_path)
                assert samples_manifest.get("run_id") == proc_runs["samples"]
                assert samples_manifest.get("dataset_version") == "v1"
                sample_groups = samples_manifest.get("output_record_counts", {})
                for dataset in CONFIG["expected_text_datasets"]:
                    prefix = dataset.replace("/", "__") + "__"
                    assert any(key.startswith(prefix) for key in sample_groups), f"Amostra ausente: {dataset}"
                assert all(Path(path).exists() for path in samples_manifest.get("output_files", []))
                print("Validacao estrutural aprovada:", total_rows, "textos unicos", ROW_COMPARISON)
                """
            ),
            md("## Arquivamento do ciclo\n\nCopia somente configuracao, manifests e auditorias; raw e fotografias `current` nao sao duplicados."),
            code(
                """
                import shutil

                ARQUIVAR_CICLO = False
                CONFIRMAR_CICLO = ""
                require_explicit_confirmation(ARQUIVAR_CICLO, CONFIRMAR_CICLO)
                if ARQUIVAR_CICLO:
                    cycle_dir = DATA_ROOT / "operations" / "atualizacao" / "ciclos" / EXPECTED_CYCLE_ID
                    archive_manifests = cycle_dir / "manifests"
                    archive_audits = cycle_dir / "audits"
                    archive_manifests.mkdir(parents=True, exist_ok=True)
                    archive_audits.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ACTIVE_CONFIG_PATH, cycle_dir / "config.json")
                    manifest_paths = [manifest_for(run) for run in RUNS.values()]
                    manifest_paths.extend([
                        Path(normal_manifest["manifest_path"]),
                        parlamentares_path,
                        apartes_manifest_path,
                        DATA_ROOT / "processed" / "manifests" / f"{CONFIG['processing_run_ids']['parquet']}-parquet.json",
                    ])
                    for path in manifest_paths:
                        if path.exists():
                            shutil.copy2(path, archive_manifests / path.name)
                    for archive_name, path in {
                        "join-audit-manifest.json": join_path,
                        "samples-manifest.json": samples_path,
                    }.items():
                        shutil.copy2(path, archive_manifests / archive_name)
                    cycle_audit_roots = [
                        DATA_ROOT / "processed" / "audits" / "parlamentares" / CONFIG["processing_run_ids"]["join_audit"],
                        DATA_ROOT / "processed" / "audits" / "apartes_parlamentares" / CONFIG["processing_run_ids"]["apartes"],
                    ]
                    for audit_root in cycle_audit_roots:
                        for source in audit_root.rglob("*") if audit_root.exists() else []:
                            if source.is_file():
                                target = archive_audits / audit_root.name / source.relative_to(audit_root)
                                target.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(source, target)
                    GRADIO_CHECKLIST = {
                        "new_window_records_found": False,
                        "compact_table_omits_text": False,
                        "full_text_opened_by_texto_id": False,
                    }
                    summary = {
                        "cycle_id": EXPECTED_CYCLE_ID,
                        "config": CONFIG,
                        "window": CONFIG["window"],
                        "collection_gate": GATE_RESULTS,
                        "collection_gate_ok": COLLECTION_GATE_OK,
                        "jsonl_gate_ok": JSONL_GATE_OK,
                        "expected_text_parquets": CONFIG["expected_text_parquets"],
                        "row_comparison": ROW_COMPARISON,
                        "processed_manifests": {
                            "textos": normal_manifest.get("manifest_path"),
                            "parlamentares": str(parlamentares_path),
                            "apartes": str(apartes_manifest_path),
                            "join_audit": str(join_path),
                            "samples": str(samples_path),
                        },
                        "manual_gradio_inspection": GRADIO_CHECKLIST,
                    }
                    (cycle_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
                    print("Ciclo arquivado em", cycle_dir)
                """
            ),
            md("## Inspecao final no Gradio\n\nAtive somente depois da validacao. Busque datas da nova janela, confira que a tabela compacta nao contem `texto` e abra o texto integral por `texto_id`."),
            code(
                """
                ABRIR_GRADIO = False
                if ABRIR_GRADIO:
                    assert COLLECTION_GATE_OK
                    from processamento.visualizador_parquets import build_gradio_app
                    app = build_gradio_app(parquet_root)
                    app.launch(share=True)
                """
            ),
        ],
    )


def main() -> None:
    notebooks = {
        COLETA_DIR / "00_auditoria_configuracao_atualizacao_colab.ipynb": build_00(),
        COLETA_DIR / "01_atualizacao_parlamentares_colab.ipynb": build_01(),
        COLETA_DIR / "02_atualizacao_senado_colab.ipynb": lane_notebook(
            "02 - Atualizacao do Senado",
            "Retoma as duas particoes historicas da CCJ e, depois, atualiza Plenario, CCJ, pareceres de PEC e apartes.",
            ["senado_ccj_historico", "senado_plenario", "senado_ccj", "senado_pareceres_pec", "senado_apartes"],
        ),
        COLETA_DIR / "03_backfill_congresso_textos_colab.ipynb": build_03(),
        COLETA_DIR / "04_atualizacao_camara_demais_bases_colab.ipynb": lane_notebook(
            "04 - Atualizacao das demais bases da Camara",
            "Retoma as 33 particoes historicas da CCJC e atualiza CCJC, pareceres de PEC e apartes.",
            ["camara_ccjc_historico", "camara_ccjc", "camara_pareceres_pec", "camara_apartes"],
        ),
        COLETA_DIR / "05_atualizacao_camara_plenario_colab.ipynb": build_05(),
        PROCESSAMENTO_DIR / "06_processamento_validacao_atualizacao_colab.ipynb": build_06(),
    }
    for path, nb in notebooks.items():
        write_notebook(path, nb)


if __name__ == "__main__":
    main()
