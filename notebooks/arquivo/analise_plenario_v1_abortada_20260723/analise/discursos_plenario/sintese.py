from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


def artifact_inventory(run_root: str | Path) -> pd.DataFrame:
    root = Path(run_root)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "09_sintese" in path.parts:
            continue
        rows.append(
            {
                "etapa": path.relative_to(root).parts[0],
                "arquivo": str(path.relative_to(root)),
                "formato": path.suffix.lower().lstrip("."),
                "tamanho_bytes": path.stat().st_size,
            }
        )
    return pd.DataFrame(rows)


def methodological_status(run_root: str | Path) -> pd.DataFrame:
    root = Path(run_root)
    rows = []
    stage_labels = {
        "00_snapshot": "reproducao",
        "01_genero": "suspensa",
        "02_descritivas": "reproducao",
        "03_apartes": "reproducao",
        "04_nlp": "reproducao",
        "05_inferencia": "robustez",
        "06_clusterizacao": "exploracao",
        "07_topicos": "exploracao",
        "08_figuras": "exploracao",
    }
    for directory, kind in stage_labels.items():
        path = root / directory
        manifests = sorted(path.glob("manifest*.json")) if path.exists() else []
        rows.append(
            {
                "etapa": directory,
                "tipo": kind,
                "executada": bool(manifests),
                "manifest": str(manifests[-1]) if manifests else None,
            }
        )
    return pd.DataFrame(rows)


def synthesis_coverage(run_root: str | Path) -> pd.DataFrame:
    root = Path(run_root)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)
    snapshot = pd.read_parquet(snapshot_path)
    coverage = (
        snapshot.groupby(["arena", "ano"], dropna=False)
        .agg(
            discursos=("texto_id", "size"),
            genero_oficial_identificado=("genero_oficial", lambda values: (~values.fillna("nao_informado").eq("nao_informado")).sum()),
            genero_pesquisado=("genero_presumido", "sum"),
            nlp_elegiveis=("elegivel_nlp", "sum"),
            llm_elegiveis=("elegivel_llm", "sum"),
        )
        .reset_index()
    )
    coverage["cobertura_genero_oficial"] = coverage["genero_oficial_identificado"] / coverage["discursos"]
    coverage["ytd"] = coverage["ano"].eq(2026)
    bridge_path = root / "03_apartes" / "ponte_camara.csv"
    if bridge_path.exists():
        bridge = pd.read_csv(bridge_path)
        bridge_summary = bridge["ponte_status"].value_counts(normalize=True).to_dict()
        coverage["ponte_camara_exato"] = bridge_summary.get("exato", 0.0)
        coverage["ponte_camara_provavel_unico"] = bridge_summary.get("provavel_unico", 0.0)
    else:
        coverage["ponte_camara_exato"] = pd.NA
        coverage["ponte_camara_provavel_unico"] = pd.NA
    return coverage


def export_coverage_figure(coverage: pd.DataFrame, output_root: str | Path) -> list[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib e necessario para exportar PNG e SVG") from exc
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    for arena, group in coverage.groupby("arena"):
        axis.plot(group["ano"], group["discursos"], marker="o", linewidth=1.5, label=str(arena))
    axis.axvspan(2025.5, 2026.5, color="#cccccc", alpha=0.3, label="2026 YTD")
    axis.set(title="Discursos por arena e ano", xlabel="Ano", ylabel="Discursos")
    axis.legend()
    figure.tight_layout()
    paths = [root / "discursos_por_arena.png", root / "discursos_por_arena.svg"]
    for path in paths:
        figure.savefig(path, dpi=180 if path.suffix == ".png" else None)
    plt.close(figure)
    return paths


def run_synthesis(*, data_root: str | Path, run_id: str, config_path: str | Path | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    output_root = root / "09_sintese"
    inventory = artifact_inventory(root)
    status = methodological_status(root)
    coverage = synthesis_coverage(root)
    outputs = []
    for name, frame in [("inventario_artefatos", inventory), ("status_metodologico", status), ("cobertura", coverage)]:
        csv_path = write_dataframe_atomic(frame, output_root / f"{name}.csv")
        parquet_path = write_dataframe_atomic(frame, output_root / f"{name}.parquet")
        outputs.extend([artifact_record(csv_path, rows=len(frame)), artifact_record(parquet_path, rows=len(frame))])
    html_path = output_root / "sintese.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        "<html><head><meta charset='utf-8'><title>Sinopse comparativa</title></head><body>"
        "<h1>Sinopse comparativa dos discursos em plenário</h1>"
        "<p>2026 é apresentado como YTD; os resultados são separados por arena.</p>"
        + status.to_html(index=False)
        + coverage.to_html(index=False)
        + "</body></html>",
        encoding="utf-8",
    )
    outputs.append(artifact_record(html_path))
    for figure_path in export_coverage_figure(coverage, output_root):
        outputs.append(artifact_record(figure_path))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="09_sintese",
        inputs=inventory.to_dict("records"),
        outputs=outputs,
        counts={"stages_completed": int(status["executada"].sum()), "ytd_year": int(config.raw["ytd_year"])},
    )
    manifest_path = write_json_atomic(output_root / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}
