from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from .apartes import benjamini_hochberg
from .config import load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


def annual_trajectories(
    frame: pd.DataFrame,
    metrics: Sequence[str],
    *,
    group: str = "arena",
    year: str = "ano",
    complete_year_end: int = 2025,
) -> pd.DataFrame:
    data = frame.loc[pd.to_numeric(frame[year], errors="coerce").le(complete_year_end)].copy()
    numeric_metrics = [metric for metric in metrics if metric in data and pd.api.types.is_numeric_dtype(data[metric])]
    return data.groupby([group, year], dropna=False)[numeric_metrics].mean().reset_index()


def paired_trajectory_correlations(
    annual: pd.DataFrame,
    metrics: Sequence[str],
    *,
    group: str = "arena",
    year: str = "ano",
    first_differences: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = sorted(annual[group].dropna().astype(str).unique())
    for metric in metrics:
        if metric not in annual:
            continue
        wide = annual.pivot(index=year, columns=group, values=metric).sort_index()
        if first_differences:
            wide = wide.diff()
        for left, right in combinations(groups, 2):
            pair = wide[[left, right]].dropna()
            if len(pair) < 3:
                continue
            pearson_r, pearson_p = _pearson(pair[left], pair[right])
            spearman_r, spearman_p = _spearman(pair[left], pair[right])
            rows.append(
                {
                    "metric": metric,
                    "arena_left": left,
                    "arena_right": right,
                    "scale": "first_difference" if first_differences else "level",
                    "n_years": len(pair),
                    "year_min": int(pair.index.min()),
                    "year_max": int(pair.index.max()),
                    "pearson_r": pearson_r,
                    "pearson_p": pearson_p,
                    "spearman_r": spearman_r,
                    "spearman_p": spearman_p,
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        for p_column in ["pearson_p", "spearman_p"]:
            result[f"{p_column}_bh"] = benjamini_hochberg(result[p_column])
    return result


def hac_linear_trends(
    annual: pd.DataFrame,
    metrics: Sequence[str],
    *,
    group: str = "arena",
    year: str = "ano",
    maxlags: int | None = None,
    exclude_years: Iterable[int] = (),
) -> pd.DataFrame:
    try:
        import statsmodels.api as sm
    except ImportError as exc:
        raise RuntimeError("statsmodels e necessario para tendencias HAC/Newey-West") from exc
    excluded = set(exclude_years)
    rows: list[dict[str, Any]] = []
    for group_value, group_frame in annual.groupby(group, dropna=False):
        data = group_frame.loc[~group_frame[year].isin(excluded)].sort_values(year)
        for metric in metrics:
            usable = data[[year, metric]].dropna() if metric in data else pd.DataFrame()
            if len(usable) < 4:
                continue
            x = sm.add_constant(usable[year].astype(float) - float(usable[year].min()))
            lag = maxlags if maxlags is not None else max(1, int(np.floor(4 * (len(usable) / 100) ** (2 / 9))))
            fit = sm.OLS(usable[metric].astype(float), x).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
            rows.append(
                {
                    group: group_value,
                    "metric": metric,
                    "n_years": len(usable),
                    "excluded_years": ",".join(map(str, sorted(excluded))),
                    "slope": float(fit.params.iloc[1]),
                    "std_error_hac": float(fit.bse.iloc[1]),
                    "p_hac": float(fit.pvalues.iloc[1]),
                    "ci_lower": float(fit.conf_int().iloc[1, 0]),
                    "ci_upper": float(fit.conf_int().iloc[1, 1]),
                    "maxlags": lag,
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["p_hac_bh"] = benjamini_hochberg(result["p_hac"])
    return result


def run_temporal_inference(
    *,
    data_root: str | Path,
    run_id: str,
    metrics: Sequence[str] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    feature_path = root / "04_nlp" / "nlp_features.parquet"
    if not feature_path.exists():
        raise FileNotFoundError(f"Execute o caderno 04 antes: {feature_path}")
    features = pd.read_parquet(feature_path)
    selected = list(metrics or [column for column in features.select_dtypes(include="number") if column not in {"ano"}])
    annual = annual_trajectories(features, selected, complete_year_end=int(config.raw["complete_year_end"]))
    correlations = pd.concat(
        [
            paired_trajectory_correlations(annual, selected, first_differences=False),
            paired_trajectory_correlations(annual, selected, first_differences=True),
        ],
        ignore_index=True,
    )
    trends = hac_linear_trends(annual, selected)
    sensitivity = hac_linear_trends(annual, selected, exclude_years=[2020, 2021])
    outputs = []
    for name, frame in [("trajetorias_anuais", annual), ("correlacoes", correlations), ("tendencias_hac", trends), ("tendencias_hac_sem_2020_2021", sensitivity)]:
        path = write_dataframe_atomic(frame, root / "05_inferencia" / f"{name}.csv")
        outputs.append(artifact_record(path, rows=len(frame)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="05_inferencia",
        inputs=[artifact_record(feature_path, rows=len(features))],
        outputs=outputs,
        counts={"metrics": len(selected), "annual_rows": len(annual), "causal_interpretation": False},
    )
    manifest_path = write_json_atomic(root / "05_inferencia" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def _pearson(left: pd.Series, right: pd.Series) -> tuple[float, float]:
    try:
        from scipy.stats import pearsonr
    except ImportError:
        return float(np.corrcoef(left, right)[0, 1]), np.nan
    result = pearsonr(left, right)
    return float(result.statistic), float(result.pvalue)


def _spearman(left: pd.Series, right: pd.Series) -> tuple[float, float]:
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return float(left.rank().corr(right.rank())), np.nan
    result = spearmanr(left, right)
    return float(result.statistic), float(result.pvalue)
