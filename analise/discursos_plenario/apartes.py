from __future__ import annotations

import math
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .config import load_config, resolve_input_paths, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


BRIDGE_COLUMNS = [
    "aparte_id",
    "discurso_chave",
    "texto_id",
    "ponte_status",
    "ponte_score",
    "ponte_evidencias",
    "ponte_candidatos",
]
DYAD_COLUMNS = [
    "genero_aparteante",
    "genero_orador",
    "observado",
    "esperado",
    "razao_observado_esperado",
]
TEST_COLUMNS = [
    "arena",
    "ano",
    "n",
    "chi2",
    "chi2_df",
    "chi2_p",
    "cramer_v",
    "min_expected",
    "fisher_applied",
    "fisher_odds_ratio",
    "fisher_p",
    "chi2_p_bh",
    "fisher_p_bh",
]


def observed_expected_dyads(
    interjections: pd.DataFrame,
    *,
    row_gender: str = "aparteante_genero",
    column_gender: str = "orador_genero",
) -> pd.DataFrame:
    required = {row_gender, column_gender}
    missing = required.difference(interjections.columns)
    if missing:
        raise ValueError(f"Apartes sem colunas: {sorted(missing)}")
    observed = pd.crosstab(interjections[row_gender], interjections[column_gender], dropna=False)
    total = float(observed.to_numpy().sum())
    row_totals = observed.sum(axis=1).to_numpy(dtype=float)
    column_totals = observed.sum(axis=0).to_numpy(dtype=float)
    expected = np.outer(row_totals, column_totals) / total if total else np.zeros(observed.shape)
    rows: list[dict[str, Any]] = []
    for row_index, row_value in enumerate(observed.index):
        for column_index, column_value in enumerate(observed.columns):
            obs = float(observed.iloc[row_index, column_index])
            exp = float(expected[row_index, column_index])
            rows.append(
                {
                    "genero_aparteante": row_value,
                    "genero_orador": column_value,
                    "observado": obs,
                    "esperado": exp,
                    "razao_observado_esperado": obs / exp if exp > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows, columns=DYAD_COLUMNS)


def association_tests(table: pd.DataFrame | np.ndarray) -> dict[str, Any]:
    matrix = table.to_numpy(dtype=float) if isinstance(table, pd.DataFrame) else np.asarray(table, dtype=float)
    if matrix.ndim != 2 or min(matrix.shape) < 2:
        raise ValueError("A tabela de contingencia deve ter pelo menos 2x2 celulas")
    if (matrix < 0).any() or matrix.sum() == 0:
        raise ValueError("As contagens devem ser nao negativas e ter total positivo")
    row = matrix.sum(axis=1)
    column = matrix.sum(axis=0)
    expected = np.outer(row, column) / matrix.sum()
    valid = expected > 0
    chi2 = float(np.sum(((matrix - expected) ** 2 / expected)[valid]))
    degrees = int((matrix.shape[0] - 1) * (matrix.shape[1] - 1))
    scipy_stats = _scipy_stats()
    p_chi2 = float(scipy_stats.chi2.sf(chi2, degrees)) if scipy_stats is not None else np.nan
    denominator = matrix.sum() * min(matrix.shape[0] - 1, matrix.shape[1] - 1)
    cramer_v = math.sqrt(chi2 / denominator) if denominator > 0 else np.nan
    fisher_odds, fisher_p = np.nan, np.nan
    fisher_applied = bool(matrix.shape == (2, 2) and (expected < 5).any())
    if fisher_applied and scipy_stats is not None:
        fisher_odds, fisher_p = map(float, scipy_stats.fisher_exact(matrix))
    return {
        "n": int(matrix.sum()),
        "chi2": chi2,
        "chi2_df": degrees,
        "chi2_p": p_chi2,
        "cramer_v": cramer_v,
        "min_expected": float(expected.min()),
        "fisher_applied": fisher_applied,
        "fisher_odds_ratio": fisher_odds,
        "fisher_p": fisher_p,
    }


def analyze_interjections_by_arena_year(interjections: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = interjections.copy()
    if "arena" not in frame:
        frame["arena"] = frame["source"].map({"camara": "camara", "senado": "senado"}).fillna(frame["source"])
    if "ano" not in frame:
        frame["ano"] = pd.to_datetime(frame["data"], errors="coerce").dt.year
    dyads: list[pd.DataFrame] = []
    tests: list[dict[str, Any]] = []
    for (arena, year), group in frame.groupby(["arena", "ano"], dropna=False):
        usable = group.dropna(subset=["aparteante_genero", "orador_genero"])
        if usable.empty:
            continue
        dyad = observed_expected_dyads(usable)
        dyad.insert(0, "ano", year)
        dyad.insert(0, "arena", arena)
        dyads.append(dyad)
        contingency = pd.crosstab(usable["aparteante_genero"], usable["orador_genero"])
        if min(contingency.shape) >= 2:
            tests.append({"arena": arena, "ano": year, **association_tests(contingency)})
    test_frame = pd.DataFrame(tests)
    if not test_frame.empty:
        test_frame["chi2_p_bh"] = benjamini_hochberg(test_frame["chi2_p"])
        test_frame["fisher_p_bh"] = benjamini_hochberg(test_frame["fisher_p"])
    dyad_frame = pd.concat(dyads, ignore_index=True) if dyads else pd.DataFrame(columns=["arena", "ano", *DYAD_COLUMNS])
    if test_frame.empty:
        test_frame = pd.DataFrame(columns=TEST_COLUMNS)
    else:
        test_frame = test_frame.reindex(columns=TEST_COLUMNS)
    return dyad_frame, test_frame


def benjamini_hochberg(values: Sequence[float] | pd.Series) -> pd.Series:
    series = pd.Series(values, dtype=float)
    valid = series.dropna()
    adjusted = pd.Series(np.nan, index=series.index, dtype=float)
    if valid.empty:
        return adjusted
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy()
    n = len(ranked)
    corrected = ranked * n / np.arange(1, n + 1)
    corrected = np.minimum.accumulate(corrected[::-1])[::-1]
    adjusted.loc[order] = np.minimum(corrected, 1.0)
    return adjusted


def build_camara_speech_bridge(
    interjections: pd.DataFrame,
    speeches: pd.DataFrame,
    *,
    ambiguity_margin: float = 0.5,
) -> pd.DataFrame:
    """Create a derived bridge without modifying the canonical interjections table."""

    speech_frame = speeches.copy()
    speech_frame["_date"] = pd.to_datetime(speech_frame["data"], errors="coerce").dt.date
    speech_frame["_speaker_name"] = speech_frame.get("parlamentar_nome", "").map(_normalize)
    rows: list[dict[str, Any]] = []
    for aparte in interjections.to_dict("records"):
        date_value = pd.to_datetime(aparte.get("data"), errors="coerce")
        date_key = date_value.date() if pd.notna(date_value) else None
        candidates = speech_frame.loc[speech_frame["_date"].eq(date_key)].copy()
        scored: list[tuple[float, int, list[str]]] = []
        for index, speech in candidates.iterrows():
            score, evidence = _bridge_score(aparte, speech)
            if score > 0:
                scored.append((score, int(index), evidence))
        scored.sort(key=lambda item: (-item[0], str(speech_frame.loc[item[1]].get("texto_id"))))
        if not scored:
            rows.append(_bridge_row(aparte, None, "ausente", 0.0, []))
            continue
        best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else -np.inf
        speech = speech_frame.loc[best[1]]
        exact_identifier = any(value in best[2] for value in ["pronunciamento_id", "discurso_chave"])
        if exact_identifier and best[0] >= 5:
            status = "exato"
        elif best[0] - second_score > ambiguity_margin and best[0] >= 2:
            status = "provavel_unico"
        else:
            status = "ambiguo"
        rows.append(_bridge_row(aparte, speech, status, best[0], best[2], candidate_count=len(scored)))
    return pd.DataFrame(rows, columns=BRIDGE_COLUMNS)


def bridge_quality(bridge: pd.DataFrame, gold: pd.DataFrame | None = None) -> dict[str, Any]:
    if bridge.empty:
        return {"n": 0, "linked": 0, "coverage": np.nan, "status_counts": {}, "precision": None}
    status_counts = bridge["ponte_status"].value_counts(dropna=False).to_dict()
    linked = bridge["ponte_status"].isin(["exato", "provavel_unico"])
    result: dict[str, Any] = {
        "n": len(bridge),
        "linked": int(linked.sum()),
        "coverage": float(linked.mean()) if len(bridge) else np.nan,
        "status_counts": status_counts,
        "precision": None,
    }
    if gold is not None and not gold.empty:
        comparison = bridge.merge(gold[["aparte_id", "texto_id_gold"]], on="aparte_id", how="inner")
        evaluated = comparison.loc[comparison["ponte_status"].isin(["exato", "provavel_unico"])]
        result["precision"] = float(evaluated["texto_id"].eq(evaluated["texto_id_gold"]).mean()) if len(evaluated) else np.nan
        result["n_gold"] = len(comparison)
    return result


def denominators_authorized(quality: Mapping[str, Any], *, min_precision: float = 0.95, min_coverage: float = 0.80) -> bool:
    precision = quality.get("precision")
    coverage = quality.get("coverage")
    return precision is not None and pd.notna(precision) and pd.notna(coverage) and float(precision) >= min_precision and float(coverage) >= min_coverage


def run_interjection_analysis(*, data_root: str | Path, run_id: str, config_path: str | Path | None = None) -> dict[str, Any]:
    from .apartes_qualitativos import (
        build_senate_speech_bridge,
        extract_interaction_turns,
        manual_coding_template,
        qualitative_codebook_template,
        qualitative_review_sample,
        segmentation_quality,
    )

    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    path = resolve_input_paths(config, data_root)["interjections"]
    if not path.exists():
        raise FileNotFoundError(path)
    interjections = pd.read_parquet(path)
    dyads, tests = analyze_interjections_by_arena_year(interjections)
    outputs = []
    for name, frame in [("diades_genero", dyads), ("testes_associacao", tests)]:
        output = write_dataframe_atomic(frame, root / "03_apartes" / f"{name}.csv")
        outputs.append(artifact_record(output, rows=len(frame)))
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    bridge_summary: dict[str, Any] = {"available": False, "denominators_authorized": False}
    qualitative_summary: dict[str, Any] = {"available": False, "classification_authorized": False}
    if snapshot_path.exists() and "source" in interjections:
        snapshot = pd.read_parquet(snapshot_path)
        camara_interjections = interjections.loc[interjections["source"].eq("camara")]
        camara_speeches = snapshot.loc[snapshot["arena"].eq("camara")]
        bridge = build_camara_speech_bridge(camara_interjections, camara_speeches)
        bridge_path = write_dataframe_atomic(bridge, root / "03_apartes" / "ponte_camara.csv")
        outputs.append(artifact_record(bridge_path, rows=len(bridge)))
        quality = bridge_quality(bridge)
        bridge_summary = {"available": True, **quality, "denominators_authorized": denominators_authorized(quality)}
        quality_path = write_json_atomic(root / "03_apartes" / "ponte_camara_qualidade.json", bridge_summary)
        outputs.append(artifact_record(quality_path))
        senate_interjections = interjections.loc[interjections["source"].eq("senado")]
        senate_speeches = snapshot.loc[snapshot["arena"].eq("senado")]
        senate_bridge = build_senate_speech_bridge(senate_interjections, senate_speeches)
        senate_bridge_path = write_dataframe_atomic(senate_bridge, root / "03_apartes" / "ponte_senado.csv")
        outputs.append(artifact_record(senate_bridge_path, rows=len(senate_bridge)))

        camara_segments = extract_interaction_turns(camara_interjections, camara_speeches, bridge)
        senate_segments = extract_interaction_turns(senate_interjections, senate_speeches, senate_bridge)
        interactions = pd.concat([camara_segments, senate_segments], ignore_index=True, sort=False)
        interactions_path = write_dataframe_atomic(interactions, root / "03_apartes" / "interacoes_segmentadas.parquet")
        outputs.append(artifact_record(interactions_path, rows=len(interactions)))
        review_sample = qualitative_review_sample(interactions, size=200, seed=config.seed)
        review_sample["segmentacao_aparte_correta"] = ""
        review_sample["segmentacao_resposta_correta"] = ""
        review_sample["revisor"] = ""
        review_sample["observacao_revisao"] = ""
        review_path = write_dataframe_atomic(review_sample, root / "03_apartes" / "revisao_segmentacao.csv")
        outputs.append(artifact_record(review_path, rows=len(review_sample)))
        manual_template = manual_coding_template(review_sample, config)
        manual_path = write_dataframe_atomic(manual_template, root / "03_apartes" / "piloto_atos_fala.csv")
        outputs.append(artifact_record(manual_path, rows=len(manual_template)))
        codebook = qualitative_codebook_template(config)
        codebook_path = write_dataframe_atomic(codebook, root / "03_apartes" / "codebook_atos_fala.csv")
        outputs.append(artifact_record(codebook_path, rows=len(codebook)))
        qualitative_summary = {"available": True, **segmentation_quality(interactions)}
        segmentation_path = write_json_atomic(root / "03_apartes" / "segmentacao_qualidade.json", qualitative_summary)
        outputs.append(artifact_record(segmentation_path))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="03_apartes",
        inputs=[artifact_record(path, rows=len(interjections))],
        outputs=outputs,
        counts={"interjections": len(interjections), "camara_bridge": bridge_summary, "qualitative_interactions": qualitative_summary},
    )
    manifest_path = write_json_atomic(root / "03_apartes" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def _bridge_score(aparte: Mapping[str, Any], speech: pd.Series) -> tuple[float, list[str]]:
    score = 0.0
    evidence: list[str] = []
    pairs = [
        ("pronunciamento_id", "pronunciamento_id", 6.0),
        ("discurso_chave", "documento_id", 6.0),
        ("sessao_id", "sessao_id", 2.0),
        ("orador_id", "parlamentar_id", 3.0),
        ("fase_sessao", "fase_evento", 1.0),
        ("evento_id", "evento_id", 1.0),
    ]
    for left, right, weight in pairs:
        if _same_nonempty(aparte.get(left), speech.get(right)):
            score += weight
            evidence.append(left)
    if _normalize(aparte.get("orador_nome")) and _normalize(aparte.get("orador_nome")) == _normalize(speech.get("parlamentar_nome")):
        score += 2.0
        evidence.append("orador_nome")
    if _time_distance_minutes(aparte.get("data_hora"), speech.get("data_hora")) <= 5:
        score += 1.0
        evidence.append("hora_5min")
    return score, evidence


def _bridge_row(
    aparte: Mapping[str, Any],
    speech: pd.Series | None,
    status: str,
    score: float,
    evidence: Sequence[str],
    candidate_count: int = 0,
) -> dict[str, Any]:
    return {
        "aparte_id": aparte.get("aparte_id"),
        "discurso_chave": aparte.get("discurso_chave"),
        "texto_id": speech.get("texto_id") if speech is not None else None,
        "ponte_status": status,
        "ponte_score": score,
        "ponte_evidencias": ",".join(evidence),
        "ponte_candidatos": candidate_count,
    }


def _same_nonempty(left: Any, right: Any) -> bool:
    return bool(str(left or "").strip()) and str(left).strip() == str(right or "").strip()


def _normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold().split())


def _time_distance_minutes(left: Any, right: Any) -> float:
    left_dt = pd.to_datetime(left, errors="coerce")
    right_dt = pd.to_datetime(right, errors="coerce")
    return abs((left_dt - right_dt).total_seconds()) / 60 if pd.notna(left_dt) and pd.notna(right_dt) else np.inf


def _scipy_stats() -> Any | None:
    try:
        from scipy import stats
    except ImportError:
        return None
    return stats
