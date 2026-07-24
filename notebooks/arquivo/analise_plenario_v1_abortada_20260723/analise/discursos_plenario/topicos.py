from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .config import AnalysisConfig, load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


PORTUGUESE_STOPWORDS = {
    "a", "ao", "aos", "aquela", "aquele", "aqueles", "as", "até", "com", "como", "da", "das", "de", "dela",
    "dele", "do", "dos", "e", "ela", "ele", "eles", "em", "entre", "era", "essa", "esse", "esta", "este", "eu",
    "foi", "há", "isso", "isto", "já", "lhe", "mais", "mas", "me", "mesmo", "meu", "minha", "muito", "na", "não",
    "nas", "no", "nos", "nós", "o", "os", "ou", "para", "pela", "pelo", "por", "que", "se", "sem", "ser", "seu",
    "sua", "também", "tem", "um", "uma", "vossa"
}


def balanced_summary_sample(
    snapshot: pd.DataFrame,
    *,
    max_per_arena_year: int = 2000,
    seed: int = 20260713,
) -> pd.DataFrame:
    required = {"arena", "ano", "resumo", "texto_id"}
    missing = required.difference(snapshot.columns)
    if missing:
        raise ValueError(f"Snapshot sem colunas: {sorted(missing)}")
    eligible = snapshot.loc[snapshot["resumo"].fillna("").astype(str).str.strip().ne("")].copy()
    pieces = []
    for _, group in eligible.groupby(["arena", "ano"], dropna=False, sort=True):
        pieces.append(group.sample(n=min(len(group), max_per_arena_year), random_state=seed, replace=False))
    if not pieces:
        return eligible.head(0)
    return pd.concat(pieces, ignore_index=True).sort_values(["arena", "ano", "texto_id"], kind="stable").reset_index(drop=True)


def build_topic_model(config: AnalysisConfig, *, seed: int | None = None) -> Any:
    try:
        from bertopic import BERTopic
        from hdbscan import HDBSCAN
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP
    except ImportError as exc:
        raise RuntimeError("Instale os pacotes de topicos de requirements-analise.txt") from exc
    topic_config = config.raw["topics"]
    random_seed = config.seed if seed is None else seed
    umap_params = {**topic_config["umap"], "random_state": random_seed}
    hdbscan_params = dict(topic_config["hdbscan"])
    vectorizer = CountVectorizer(stop_words=sorted(PORTUGUESE_STOPWORDS), ngram_range=(1, 2), min_df=3)
    return BERTopic(
        embedding_model=topic_config["embedding_model"],
        umap_model=UMAP(**umap_params),
        hdbscan_model=HDBSCAN(**hdbscan_params),
        vectorizer_model=vectorizer,
        calculate_probabilities=False,
        verbose=True,
    )


def fit_common_topic_model(sample: pd.DataFrame, config: AnalysisConfig) -> tuple[Any, pd.DataFrame, Any]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("sentence-transformers e necessario para BERTopic") from exc
    documents = sample["resumo"].astype(str).tolist()
    encoder = SentenceTransformer(config.raw["topics"]["embedding_model"])
    embeddings = encoder.encode(documents, show_progress_bar=True, normalize_embeddings=True)
    model = build_topic_model(config)
    topics, probabilities = model.fit_transform(documents, embeddings)
    assignments = sample[[column for column in ["texto_id", "arena", "ano", "resumo"] if column in sample]].copy()
    assignments["topico"] = topics
    if probabilities is not None and np.asarray(probabilities).ndim == 1:
        assignments["probabilidade"] = probabilities
    return model, assignments, embeddings


def topic_prevalence(assignments: pd.DataFrame) -> pd.DataFrame:
    counts = assignments.groupby(["arena", "ano", "topico"], dropna=False).size().rename("n").reset_index()
    totals = counts.groupby(["arena", "ano"], dropna=False)["n"].transform("sum")
    counts["proporcao"] = counts["n"] / totals
    counts["outlier"] = counts["topico"].eq(-1)
    return counts


def topic_coverage(snapshot: pd.DataFrame, sample: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    total = snapshot.groupby(["arena", "ano"], dropna=False).size().rename("discursos").reset_index()
    summaries = snapshot.loc[snapshot["resumo"].fillna("").str.strip().ne("")].groupby(["arena", "ano"], dropna=False).size().rename("com_resumo").reset_index()
    sampled = sample.groupby(["arena", "ano"], dropna=False).size().rename("amostrados").reset_index()
    outliers = assignments.loc[assignments["topico"].eq(-1)].groupby(["arena", "ano"], dropna=False).size().rename("outliers").reset_index()
    result = total.merge(summaries, on=["arena", "ano"], how="left").merge(sampled, on=["arena", "ano"], how="left").merge(outliers, on=["arena", "ano"], how="left")
    result[["com_resumo", "amostrados", "outliers"]] = result[["com_resumo", "amostrados", "outliers"]].fillna(0).astype(int)
    result["cobertura_resumo"] = result["com_resumo"] / result["discursos"]
    result["taxa_outliers"] = result["outliers"] / result["amostrados"].replace(0, np.nan)
    result["ytd"] = result["ano"].eq(2026)
    return result


def assess_topic_stability(
    sample: pd.DataFrame,
    embeddings: Any,
    reference_topics: Sequence[int],
    config: AnalysisConfig,
    *,
    repetitions: int = 2,
) -> pd.DataFrame:
    try:
        from sklearn.metrics import adjusted_mutual_info_score, normalized_mutual_info_score
    except ImportError as exc:
        raise RuntimeError("scikit-learn e necessario para estabilidade de topicos") from exc
    documents = sample["resumo"].astype(str).tolist()
    rows = []
    for repetition in range(repetitions):
        candidate = build_topic_model(config, seed=config.seed + repetition + 1)
        topics, _ = candidate.fit_transform(documents, embeddings)
        rows.append(
            {
                "repetition": repetition + 1,
                "seed": config.seed + repetition + 1,
                "n_topics_including_outlier": len(set(topics)),
                "normalized_mutual_information": float(normalized_mutual_info_score(reference_topics, topics)),
                "adjusted_mutual_information": float(adjusted_mutual_info_score(reference_topics, topics)),
            }
        )
    return pd.DataFrame(rows)


def run_topic_modeling(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
    stability_repetitions: int = 2,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    snapshot = pd.read_parquet(snapshot_path)
    sample = balanced_summary_sample(
        snapshot,
        max_per_arena_year=int(config.raw["topics"]["max_summaries_per_arena_year"]),
        seed=config.seed,
    )
    model, assignments, embeddings = fit_common_topic_model(sample, config)
    prevalence = topic_prevalence(assignments)
    coverage = topic_coverage(snapshot, sample, assignments)
    stability = assess_topic_stability(sample, embeddings, assignments["topico"], config, repetitions=stability_repetitions)
    topic_info = model.get_topic_info()
    outputs = []
    for name, frame, suffix in [
        ("amostra", sample, ".parquet"),
        ("atribuicoes", assignments, ".parquet"),
        ("prevalencia", prevalence, ".csv"),
        ("cobertura", coverage, ".csv"),
        ("estabilidade", stability, ".csv"),
        ("topicos", topic_info, ".csv"),
    ]:
        output = write_dataframe_atomic(frame, root / "07_topicos" / f"{name}{suffix}")
        outputs.append(artifact_record(output, rows=len(frame)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="07_topicos",
        inputs=[artifact_record(snapshot_path, rows=len(snapshot))],
        outputs=outputs,
        counts={"sample": len(sample), "outliers": int(assignments["topico"].eq(-1).sum()), "stability_repetitions": stability_repetitions},
    )
    manifest_path = write_json_atomic(root / "07_topicos" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}
