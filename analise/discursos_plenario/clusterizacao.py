from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .config import load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


def evaluate_kmeans(
    frame: pd.DataFrame,
    features: Sequence[str],
    *,
    k_values: Sequence[int] = tuple(range(2, 9)),
    seed: int = 20260713,
    stability_repetitions: int = 100,
) -> tuple[pd.DataFrame, dict[int, np.ndarray]]:
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn e necessario para clusterizacao") from exc
    data = frame[list(features)].replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < max(k_values) + 1:
        raise ValueError("Amostra insuficiente para avaliar todos os valores de k")
    matrix = StandardScaler().fit_transform(data)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    labels_by_k: dict[int, np.ndarray] = {}
    for k in k_values:
        model = KMeans(n_clusters=k, random_state=seed, n_init=20)
        labels = model.fit_predict(matrix)
        labels_by_k[int(k)] = labels
        stability: list[float] = []
        for repetition in range(stability_repetitions):
            sample = rng.choice(len(matrix), size=max(k + 1, int(0.8 * len(matrix))), replace=False)
            candidate = KMeans(n_clusters=k, random_state=seed + repetition + 1, n_init=10).fit(matrix[sample])
            predicted = candidate.predict(matrix)
            stability.append(float(adjusted_rand_score(labels, predicted)))
        rows.append(
            {
                "k": int(k),
                "n": len(matrix),
                "silhouette": float(silhouette_score(matrix, labels)),
                "davies_bouldin": float(davies_bouldin_score(matrix, labels)),
                "calinski_harabasz": float(calinski_harabasz_score(matrix, labels)),
                "inertia": float(model.inertia_),
                "stability_ari_mean": float(np.mean(stability)),
                "stability_ari_p05": float(np.quantile(stability, 0.05)),
                "stability_ari_p95": float(np.quantile(stability, 0.95)),
            }
        )
    return pd.DataFrame(rows), labels_by_k


def fit_selected_kmeans(
    frame: pd.DataFrame,
    features: Sequence[str],
    *,
    k: int,
    seed: int = 20260713,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("scikit-learn e necessario para clusterizacao") from exc
    valid = frame[list(features)].replace([np.inf, -np.inf], np.nan).dropna().index
    scaler = StandardScaler()
    matrix = scaler.fit_transform(frame.loc[valid, features])
    model = KMeans(n_clusters=k, random_state=seed, n_init=20).fit(matrix)
    assignments = frame.loc[valid, [column for column in ["texto_id", "arena", "ano"] if column in frame]].copy()
    assignments["cluster"] = model.labels_.astype(int)
    centroids = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=features)
    centroids.insert(0, "cluster", range(k))
    return assignments, centroids


def run_clustering(*, data_root: str | Path, run_id: str, config_path: str | Path | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    feature_path = root / "04_nlp" / "nlp_features.parquet"
    features_frame = pd.read_parquet(feature_path)
    features = list(config.raw["clustering"]["features"])
    evaluation, _ = evaluate_kmeans(
        features_frame,
        features,
        k_values=range(int(config.raw["clustering"]["k_min"]), int(config.raw["clustering"]["k_max"]) + 1),
        seed=config.seed,
        stability_repetitions=int(config.raw["clustering"]["stability_repetitions"]),
    )
    output = write_dataframe_atomic(evaluation, root / "06_clusterizacao" / "avaliacao_k.csv")
    decision_template = pd.DataFrame(
        [{"k_selecionado": None, "clusters_estaveis": None, "justificativa": None, "interpretacao_revisada_por": None}]
    )
    template_path = write_dataframe_atomic(decision_template, root / "06_clusterizacao" / "decisao_k.csv")
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="06_clusterizacao_avaliacao",
        inputs=[artifact_record(feature_path, rows=len(features_frame))],
        outputs=[artifact_record(output, rows=len(evaluation)), artifact_record(template_path, rows=1)],
        counts={"features": features, "selected_k": None},
    )
    manifest_path = write_json_atomic(root / "06_clusterizacao" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}
