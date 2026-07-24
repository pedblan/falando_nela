from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


def descriptive_panel(
    snapshot: pd.DataFrame,
    *,
    period: str = "year",
    dimensions: Sequence[str] = (),
) -> pd.DataFrame:
    if period not in {"year", "month"}:
        raise ValueError("period deve ser year ou month")
    required = {"arena", "data_analise", "texto_id", "n_palavras"}
    missing = required.difference(snapshot.columns)
    if missing:
        raise ValueError(f"Snapshot sem colunas: {sorted(missing)}")
    frame = snapshot.loc[snapshot.get("elegivel_descritivas", True)].copy()
    frame["periodo"] = pd.to_datetime(frame["data_analise"]).dt.to_period("Y" if period == "year" else "M").astype(str)
    frame["orador_key"] = _speaker_key(frame)
    group_columns = ["arena", "periodo", *dimensions]
    grouped = frame.groupby(group_columns, dropna=False, observed=True)
    result = grouped.agg(
        discursos=("texto_id", "size"),
        oradores=("orador_key", "nunique"),
        palavras=("n_palavras", "sum"),
        palavras_media=("n_palavras", "mean"),
        palavras_mediana=("n_palavras", "median"),
        palavras_desvio_padrao=("n_palavras", "std"),
        palavras_p25=("n_palavras", lambda values: values.quantile(0.25)),
        palavras_p75=("n_palavras", lambda values: values.quantile(0.75)),
        palavras_p90=("n_palavras", lambda values: values.quantile(0.90)),
    ).reset_index()
    result["discursos_por_orador"] = result["discursos"] / result["oradores"].replace(0, np.nan)
    totals = result.groupby(["arena", "periodo"], dropna=False)["discursos"].transform("sum")
    result["discursos_por_mil"] = 1000 * result["discursos"] / totals.replace(0, np.nan)
    result = result.sort_values(group_columns, kind="stable").reset_index(drop=True)
    result["diferenca_periodo_anterior"] = result.groupby(["arena", *dimensions], dropna=False)["discursos"].diff()
    historical_median = result.groupby(["arena", *dimensions], dropna=False)["discursos"].transform("median")
    result["diferenca_mediana_historica"] = result["discursos"] - historical_median
    return result


def speaker_summary(snapshot: pd.DataFrame) -> pd.DataFrame:
    frame = snapshot.copy()
    frame["orador_key"] = _speaker_key(frame)
    dimensions = [column for column in ["arena", "ano", "parlamentar_id", "parlamentar_nome", "genero_analitico", "partido_temporal"] if column in frame]
    return (
        frame.groupby(dimensions, dropna=False, observed=True)
        .agg(discursos=("texto_id", "size"), palavras=("n_palavras", "sum"), palavras_mediana=("n_palavras", "median"))
        .reset_index()
    )


def clustered_speaker_bootstrap(
    frame: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    *,
    estimand: str,
    speaker_column: str = "parlamentar_id",
    repetitions: int = 2000,
    seed: int = 20260713,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Bootstrap speakers, only when the caller states the generalization estimand."""

    if not estimand.strip():
        raise ValueError("O bootstrap exige uma populacao/alvo de generalizacao declarada em estimand")
    if repetitions <= 0:
        raise ValueError("repetitions deve ser positivo")
    grouped = {str(key): group for key, group in frame.groupby(speaker_column, dropna=False)}
    speakers = np.array(list(grouped), dtype=object)
    if len(speakers) < 2:
        raise ValueError("O bootstrap por orador exige ao menos dois oradores")
    rng = np.random.default_rng(seed)
    samples = np.empty(repetitions, dtype=float)
    for index in range(repetitions):
        sampled = rng.choice(speakers, size=len(speakers), replace=True)
        replicate = pd.concat([grouped[str(speaker)].assign(_bootstrap_cluster=position) for position, speaker in enumerate(sampled)])
        samples[index] = float(statistic(replicate))
    alpha = 1.0 - confidence
    return {
        "estimand": estimand,
        "estimate": float(statistic(frame)),
        "confidence": confidence,
        "lower": float(np.quantile(samples, alpha / 2)),
        "upper": float(np.quantile(samples, 1 - alpha / 2)),
        "repetitions": repetitions,
        "seed": seed,
        "n_speakers": len(speakers),
    }


def run_descriptives(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Execute o caderno 00 antes: {snapshot_path}")
    snapshot = pd.read_parquet(snapshot_path)
    outputs: list[dict[str, Any]] = []
    panels = {
        "anual": descriptive_panel(snapshot, period="year"),
        "mensal": descriptive_panel(snapshot, period="month"),
        "anual_genero": descriptive_panel(snapshot, period="year", dimensions=["genero_analitico"]),
        "anual_partido": descriptive_panel(snapshot, period="year", dimensions=["partido_temporal"]),
        "anual_tipo_fala": descriptive_panel(snapshot, period="year", dimensions=["tipo_discurso"]),
        "parlamentares": speaker_summary(snapshot),
    }
    for name, panel in panels.items():
        path = write_dataframe_atomic(panel, root / "02_descritivas" / f"{name}.csv")
        outputs.append(artifact_record(path, rows=len(panel)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="02_descritivas",
        inputs=[artifact_record(snapshot_path, rows=len(snapshot))],
        outputs=outputs,
        counts={"snapshot_rows": len(snapshot)},
    )
    manifest_path = write_json_atomic(root / "02_descritivas" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def _speaker_key(frame: pd.DataFrame) -> pd.Series:
    ids = frame.get("parlamentar_id", pd.Series("", index=frame.index)).fillna("").astype(str)
    names = frame.get("parlamentar_nome", pd.Series("", index=frame.index)).fillna("").astype(str).str.casefold()
    return ids.where(ids.ne(""), names)
