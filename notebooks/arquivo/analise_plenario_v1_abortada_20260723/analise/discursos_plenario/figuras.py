from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .config import AnalysisConfig, load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


FIGURE_RESULT_COLUMNS = [
    "custom_id",
    "response_id",
    "model",
    "texto_id",
    "categoria",
    "presente",
    "contagem",
    "evidencias",
    "confianca",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
]
FIGURE_ERROR_COLUMNS = ["line", "custom_id", "texto_id", "error"]


def figures_codebook_template(config: AnalysisConfig) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "categoria": category,
                "definicao_operacional": "",
                "criterio_positivo": "",
                "criterio_negativo": "",
                "caso_limitrofe": "",
                "exemplo_positivo_id": "",
                "exemplo_negativo_id": "",
                "versao": "v1",
            }
            for category in config.raw["rhetorical_figures"]
        ]
    )


def balanced_figure_pilot(
    eligible: pd.DataFrame,
    *,
    size: int = 200,
    seed: int = 20260713,
) -> pd.DataFrame:
    if eligible.empty:
        return eligible.copy()
    sample_frame = eligible.copy()
    years = pd.to_numeric(sample_frame["ano"], errors="coerce")
    sample_frame["periodo_piloto"] = pd.cut(
        years,
        bins=[2009, 2015, 2019, 2026],
        labels=["2010-2015", "2016-2019", "2020-2026"],
    )
    length = pd.to_numeric(sample_frame["n_palavras"], errors="coerce")
    sample_frame["faixa_extensao"] = pd.qcut(length.rank(method="first"), q=min(3, len(sample_frame)), labels=False, duplicates="drop")
    groups = list(sample_frame.groupby(["arena", "periodo_piloto", "faixa_extensao"], dropna=False, observed=True))
    quota = max(1, int(np.ceil(min(size, len(sample_frame)) / max(1, len(groups)))))
    pieces = [group.sample(n=min(quota, len(group)), random_state=seed) for _, group in groups]
    pilot = pd.concat(pieces, ignore_index=True)
    if len(pilot) > size:
        pilot = pilot.sample(n=size, random_state=seed)
    return pilot.sort_values(["arena", "periodo_piloto", "texto_id"], kind="stable").reset_index(drop=True)


def figure_manual_coding_template(pilot: pd.DataFrame, categories: Sequence[str]) -> pd.DataFrame:
    rows = []
    for record in pilot.to_dict("records"):
        for category in categories:
            rows.append(
                {
                    "texto_id": record["texto_id"],
                    "arena": record.get("arena"),
                    "ano": record.get("ano"),
                    "parlamentar_id": record.get("parlamentar_id"),
                    "categoria": category,
                    "presente_humano": "",
                    "contagem_humano": "",
                    "evidencia_humana": "",
                    "codificador": "",
                    "adjudicado": "",
                    "observacao": "",
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "texto_id",
            "arena",
            "ano",
            "parlamentar_id",
            "categoria",
            "presente_humano",
            "contagem_humano",
            "evidencia_humana",
            "codificador",
            "adjudicado",
            "observacao",
        ],
    )


def pricing_table_template(models: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "model": model,
                "input_per_million": np.nan,
                "cached_input_per_million": np.nan,
                "output_per_million": np.nan,
                "batch_discount": np.nan,
                "currency": "USD",
                "source_url": "",
                "as_of": "",
            }
            for model in models
        ]
    )


def calculate_usage_cost(usage: pd.DataFrame, pricing: pd.DataFrame) -> pd.DataFrame:
    required_usage = {"model", "input_tokens", "output_tokens"}
    required_pricing = {"model", "input_per_million", "output_per_million", "batch_discount", "source_url", "as_of"}
    if missing := required_usage.difference(usage.columns):
        raise ValueError(f"Uso sem colunas: {sorted(missing)}")
    if missing := required_pricing.difference(pricing.columns):
        raise ValueError(f"Precos sem colunas: {sorted(missing)}")
    if pricing[list(required_pricing - {"model", "source_url", "as_of"})].isna().any().any():
        raise ValueError("Preencha integralmente a tabela de precos versionada")
    if pricing["source_url"].fillna("").str.strip().eq("").any() or pricing["as_of"].fillna("").str.strip().eq("").any():
        raise ValueError("Cada preco exige fonte oficial e data de consulta")
    result = usage.merge(pricing, on="model", how="left", validate="many_to_one")
    if result["input_per_million"].isna().any():
        raise ValueError("Ha modelos sem preco registrado")
    cached_source = result["cached_input_tokens"] if "cached_input_tokens" in result else pd.Series(0, index=result.index)
    cached = pd.to_numeric(cached_source, errors="coerce").fillna(0)
    input_tokens = pd.to_numeric(result["input_tokens"], errors="raise")
    output_tokens = pd.to_numeric(result["output_tokens"], errors="raise")
    uncached = (input_tokens - cached).clip(lower=0)
    cached_price = pd.to_numeric(result.get("cached_input_per_million", result["input_per_million"]), errors="coerce").fillna(result["input_per_million"])
    gross = uncached * result["input_per_million"] / 1_000_000 + cached * cached_price / 1_000_000 + output_tokens * result["output_per_million"] / 1_000_000
    result["estimated_cost"] = gross * (1 - result["batch_discount"])
    return result


def figures_output_schema(categories: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "texto_id": {"type": "string"},
            "figuras": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "categoria": {"type": "string", "enum": list(categories)},
                        "presente": {"type": "boolean"},
                        "contagem": {"type": "integer", "minimum": 0},
                        "evidencias": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                        },
                        "confianca": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["categoria", "presente", "contagem", "evidencias", "confianca"],
                    "additionalProperties": False,
                },
                "minItems": len(categories),
                "maxItems": len(categories),
            },
            "observacao": {"type": ["string", "null"]},
        },
        "required": ["texto_id", "figuras", "observacao"],
        "additionalProperties": False,
    }


def build_figures_prompt(text_id: str, text: str, codebook: str, categories: Sequence[str]) -> str:
    return f"""Classifique figuras de linguagem no discurso parlamentar segundo o codebook.

Regras:
- avalie todas as categorias exatamente uma vez: {', '.join(categories)};
- use apenas o trecho fornecido e o codebook;
- evidencia deve ser um fragmento curto do texto, nunca uma explicacao inventada;
- contagem e zero quando presente=false;
- pergunta genuina nao e automaticamente pergunta retorica;
- ironia exige sinal textual contextual suficiente; na duvida, marque ausente;
- a classificacao e descritiva, nao causal.

Codebook:
{codebook}

texto_id: {text_id}
Texto:
{text}
"""


def make_batch_request(
    *,
    text_id: str,
    text: str,
    codebook: str,
    config: AnalysisConfig,
    model: str | None = None,
) -> dict[str, Any]:
    categories = config.raw["rhetorical_figures"]
    custom_id = "figuras-" + hashlib.sha256(str(text_id).encode("utf-8")).hexdigest()[:24]
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model or config.raw["openai"]["figures_default_model"],
            "input": build_figures_prompt(str(text_id), text, codebook, categories),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "figuras_linguagem",
                    "strict": True,
                    "schema": figures_output_schema(categories),
                }
            },
            "metadata": {
                "texto_id": str(text_id),
                "prompt_version": config.raw["openai"]["figures_prompt_version"],
            },
        },
    }


def write_batch_jsonl(
    sample: pd.DataFrame,
    path: str | Path,
    *,
    codebook: str,
    config: AnalysisConfig,
    model: str | None = None,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with destination.open("w", encoding="utf-8") as stream:
        for record in sample.to_dict("records"):
            request = make_batch_request(
                text_id=str(record["texto_id"]),
                text=str(record["texto_analitico"]),
                codebook=codebook,
                config=config,
                model=model,
            )
            if request["custom_id"] in seen:
                raise ValueError(f"custom_id duplicado: {request['custom_id']}")
            seen.add(request["custom_id"])
            stream.write(json.dumps(request, ensure_ascii=False) + "\n")
    return destination


def submit_responses_batch(client: Any, request_path: str | Path, *, description: str) -> Any:
    with Path(request_path).open("rb") as stream:
        uploaded = client.files.create(file=stream, purpose="batch")
    return client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"description": description},
    )


def download_completed_batch(client: Any, batch_id: str, destination: str | Path) -> tuple[Any, Path]:
    batch = client.batches.retrieve(batch_id)
    if getattr(batch, "status", None) != "completed" or not getattr(batch, "output_file_id", None):
        raise RuntimeError(f"Batch ainda nao concluido: {getattr(batch, 'status', None)}")
    response = client.files.content(batch.output_file_id)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(response, "write_to_file"):
        response.write_to_file(path)
    else:
        content = getattr(response, "content", response)
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("Resposta de arquivo em formato inesperado")
        path.write_bytes(bytes(content))
    return batch, path


def parse_batch_output(
    lines: Iterable[str],
    *,
    request_index: Mapping[str, str],
    categories: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        custom_id = record.get("custom_id")
        texto_id = request_index.get(custom_id)
        response = record.get("response") or {}
        if response.get("status_code") != 200:
            errors.append({"line": line_number, "custom_id": custom_id, "texto_id": texto_id, "error": json.dumps(record.get("error") or response, ensure_ascii=False)})
            continue
        body = response.get("body") or {}
        try:
            output_text = _response_output_text(body)
            payload = json.loads(output_text)
            _validate_figure_payload(payload, categories)
            results.extend(_flatten_figure_payload(payload, custom_id=custom_id, body=body))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"line": line_number, "custom_id": custom_id, "texto_id": texto_id, "error": str(exc)})
    return pd.DataFrame(results, columns=FIGURE_RESULT_COLUMNS), pd.DataFrame(errors, columns=FIGURE_ERROR_COLUMNS)


def multilabel_jaccard(truth: Iterable[str], prediction: Iterable[str]) -> dict[str, Any]:
    truth_set, prediction_set = set(truth), set(prediction)
    union = truth_set | prediction_set
    if not union:
        return {"jaccard": np.nan, "both_empty": True, "intersection": 0, "union": 0}
    return {
        "jaccard": len(truth_set & prediction_set) / len(union),
        "both_empty": False,
        "intersection": len(truth_set & prediction_set),
        "union": len(union),
    }


def evaluate_multilabel(
    truth: Sequence[Iterable[str]],
    prediction: Sequence[Iterable[str]],
    categories: Sequence[str],
) -> tuple[dict[str, Any], pd.DataFrame]:
    if len(truth) != len(prediction):
        raise ValueError("truth e prediction devem ter o mesmo tamanho")
    jaccards = [multilabel_jaccard(left, right) for left, right in zip(truth, prediction)]
    per_label: list[dict[str, Any]] = []
    total_tp = total_fp = total_fn = 0
    for category in categories:
        truth_binary = np.array([category in set(values) for values in truth], dtype=bool)
        pred_binary = np.array([category in set(values) for values in prediction], dtype=bool)
        tp = int(np.sum(truth_binary & pred_binary))
        fp = int(np.sum(~truth_binary & pred_binary))
        fn = int(np.sum(truth_binary & ~pred_binary))
        tn = int(np.sum(~truth_binary & ~pred_binary))
        precision = tp / (tp + fp) if tp + fp else np.nan
        recall = tp / (tp + fn) if tp + fn else np.nan
        f1 = 2 * precision * recall / (precision + recall) if pd.notna(precision) and pd.notna(recall) and precision + recall else np.nan
        per_label.append(
            {
                "categoria": category,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "kappa": binary_kappa(truth_binary, pred_binary),
            }
        )
        total_tp += tp
        total_fp += fp
        total_fn += fn
    labels = pd.DataFrame(per_label)
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else np.nan
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else np.nan
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if pd.notna(micro_precision) and pd.notna(micro_recall) and micro_precision + micro_recall else np.nan
    valid_jaccard = [row["jaccard"] for row in jaccards if not row["both_empty"]]
    summary = {
        "n": len(truth),
        "both_empty": sum(row["both_empty"] for row in jaccards),
        "jaccard_mean_nonempty_union": float(np.mean(valid_jaccard)) if valid_jaccard else np.nan,
        "precision_micro": micro_precision,
        "recall_micro": micro_recall,
        "f1_micro": micro_f1,
        "f1_macro": float(labels["f1"].mean(skipna=True)),
        "kappa_macro": float(labels["kappa"].mean(skipna=True)),
    }
    return summary, labels


def paired_cluster_bootstrap_jaccard(
    truth: Sequence[Iterable[str]],
    prediction_a: Sequence[Iterable[str]],
    prediction_b: Sequence[Iterable[str]],
    speakers: Sequence[Any],
    *,
    repetitions: int = 2000,
    seed: int = 20260713,
) -> dict[str, Any]:
    if not (len(truth) == len(prediction_a) == len(prediction_b) == len(speakers)):
        raise ValueError("Todas as sequencias devem ter o mesmo tamanho")
    speaker_indices: dict[str, list[int]] = {}
    for index, speaker in enumerate(speakers):
        speaker_indices.setdefault(str(speaker), []).append(index)
    clusters = np.array(list(speaker_indices), dtype=object)
    if len(clusters) < 2:
        raise ValueError("O bootstrap pareado exige ao menos dois oradores")
    rng = np.random.default_rng(seed)
    differences = np.empty(repetitions)
    for repetition in range(repetitions):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        indices = [index for cluster in sampled for index in speaker_indices[str(cluster)]]
        score_a = _mean_jaccard([truth[i] for i in indices], [prediction_a[i] for i in indices])
        score_b = _mean_jaccard([truth[i] for i in indices], [prediction_b[i] for i in indices])
        differences[repetition] = score_a - score_b
    estimate = _mean_jaccard(truth, prediction_a) - _mean_jaccard(truth, prediction_b)
    return {
        "difference_a_minus_b": estimate,
        "lower": float(np.nanquantile(differences, 0.025)),
        "upper": float(np.nanquantile(differences, 0.975)),
        "probability_a_le_b": float(np.nanmean(differences <= 0)),
        "repetitions": repetitions,
        "seed": seed,
        "n_speakers": len(clusters),
    }


def jaccard_permutation_test(
    truth: Sequence[Iterable[str]],
    prediction: Sequence[Iterable[str]],
    *,
    strata: Sequence[Any] | None = None,
    repetitions: int = 2000,
    seed: int = 20260713,
) -> dict[str, Any]:
    if len(truth) != len(prediction):
        raise ValueError("truth e prediction devem ter o mesmo tamanho")
    strata_values = list(strata) if strata is not None else ["all"] * len(truth)
    if len(strata_values) != len(truth):
        raise ValueError("strata deve ter o mesmo tamanho")
    observed = _mean_jaccard(truth, prediction)
    rng = np.random.default_rng(seed)
    groups: dict[str, list[int]] = {}
    for index, value in enumerate(strata_values):
        groups.setdefault(str(value), []).append(index)
    null = np.empty(repetitions)
    for repetition in range(repetitions):
        permuted = list(prediction)
        for indices in groups.values():
            shuffled = rng.permutation(indices)
            for target, source in zip(indices, shuffled):
                permuted[target] = prediction[int(source)]
        null[repetition] = _mean_jaccard(truth, permuted)
    return {
        "observed": observed,
        "null_mean": float(np.nanmean(null)),
        "p_greater": float((1 + np.sum(null >= observed)) / (repetitions + 1)),
        "repetitions": repetitions,
        "seed": seed,
    }


def count_errors(truth: Sequence[int], prediction: Sequence[int]) -> dict[str, float]:
    residual = np.asarray(prediction, dtype=float) - np.asarray(truth, dtype=float)
    return {"mean_absolute_error": float(np.mean(np.abs(residual))), "mean_bias_prediction_minus_truth": float(np.mean(residual))}


def compare_models_against_human(
    human: pd.DataFrame,
    model_results: pd.DataFrame,
    metadata: pd.DataFrame,
    categories: Sequence[str],
    *,
    reference_model: str,
    noninferiority_margin: float,
    repetitions: int = 2000,
    seed: int = 20260713,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare models on the same adjudicated speeches using paired speaker bootstrap."""

    required_human = {"texto_id", "categoria", "presente_humano"}
    required_model = {"texto_id", "categoria", "presente", "modelo"}
    if missing := required_human.difference(human.columns):
        raise ValueError(f"Piloto humano sem colunas: {sorted(missing)}")
    if missing := required_model.difference(model_results.columns):
        raise ValueError(f"Resultados sem colunas: {sorted(missing)}")
    speech_ids = sorted(set(human["texto_id"].astype(str)) & set(model_results["texto_id"].astype(str)))
    truth = [_sets_for_speech(human, speech_id, present_column="presente_humano") for speech_id in speech_ids]
    speakers_index = metadata.assign(texto_id=metadata["texto_id"].astype(str)).set_index("texto_id")["parlamentar_id"].to_dict()
    speakers = [speakers_index.get(speech_id, speech_id) for speech_id in speech_ids]
    model_sets: dict[str, list[set[str]]] = {}
    summaries = []
    for model, group in model_results.groupby("modelo"):
        predictions = [_sets_for_speech(group, speech_id, present_column="presente") for speech_id in speech_ids]
        model_sets[str(model)] = predictions
        summary, _ = evaluate_multilabel(truth, predictions, categories)
        summaries.append({"modelo": model, **summary})
    if reference_model not in model_sets:
        raise ValueError(f"Modelo de referencia ausente: {reference_model}")
    comparisons = []
    for model, predictions in model_sets.items():
        if model == reference_model:
            continue
        bootstrap = paired_cluster_bootstrap_jaccard(
            truth,
            predictions,
            model_sets[reference_model],
            speakers,
            repetitions=repetitions,
            seed=seed,
        )
        comparisons.append(
            {
                "modelo_candidato": model,
                "modelo_referencia": reference_model,
                "margem_nao_inferioridade": noninferiority_margin,
                **bootstrap,
                "nao_inferior": bootstrap["lower"] > -abs(noninferiority_margin),
            }
        )
    return pd.DataFrame(summaries), pd.DataFrame(comparisons)


def prepare_figures_stage(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    snapshot = pd.read_parquet(snapshot_path)
    eligible = snapshot.loc[snapshot["elegivel_llm"]].copy()
    if sample_limit is not None:
        eligible = eligible.groupby(["arena", "ano"], group_keys=False).head(sample_limit)
    codebook = figures_codebook_template(config)
    codebook_path = write_dataframe_atomic(codebook, root / "08_figuras" / "codebook.csv")
    sample_path = write_dataframe_atomic(eligible, root / "08_figuras" / "amostra_elegivel.parquet")
    pilot = balanced_figure_pilot(eligible, size=200, seed=config.seed)
    pilot_path = write_dataframe_atomic(pilot, root / "08_figuras" / "amostra_piloto.parquet")
    validation_template = figure_manual_coding_template(pilot, config.raw["rhetorical_figures"])
    validation_path = write_dataframe_atomic(validation_template, root / "08_figuras" / "piloto_humano.csv")
    pricing = pricing_table_template(config.raw["openai"]["figures_candidate_models"])
    pricing_path = write_dataframe_atomic(pricing, root / "08_figuras" / "precos_openai.csv")
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="08_figuras_setup",
        inputs=[artifact_record(snapshot_path, rows=len(snapshot))],
        outputs=[
            artifact_record(codebook_path, rows=len(codebook)),
            artifact_record(sample_path, rows=len(eligible)),
            artifact_record(pilot_path, rows=len(pilot)),
            artifact_record(validation_path, rows=len(validation_template)),
            artifact_record(pricing_path, rows=len(pricing)),
        ],
        counts={"eligible": len(eligible), "pilot": len(pilot), "default_model": config.raw["openai"]["figures_default_model"]},
    )
    manifest_path = write_json_atomic(root / "08_figuras" / "manifest_setup.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def figure_prevalence(results: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = [column for column in ["texto_id", "arena", "ano", "n_palavras"] if column in snapshot]
    metadata = snapshot[metadata_columns].copy()
    metadata["texto_id"] = metadata["texto_id"].astype(str)
    data = results.copy()
    data["texto_id"] = data["texto_id"].astype(str)
    merged = data.merge(metadata, on="texto_id", how="left", validate="many_to_one")
    grouped = (
        merged.groupby(["model", "arena", "ano", "categoria"], dropna=False)
        .agg(
            discursos=("texto_id", "nunique"),
            discursos_com_figura=("presente", "sum"),
            ocorrencias=("contagem", "sum"),
            palavras=("n_palavras", "sum"),
        )
        .reset_index()
    )
    grouped["discursos_com_figura_proporcao"] = grouped["discursos_com_figura"] / grouped["discursos"]
    grouped["ocorrencias_por_mil_palavras"] = 1000 * grouped["ocorrencias"] / grouped["palavras"].replace(0, np.nan)
    grouped["ytd"] = grouped["ano"].eq(2026)
    return grouped


def run_figures_results(
    *,
    data_root: str | Path,
    run_id: str,
    batch_output_path: str | Path,
    request_path: str | Path,
    model: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    human_path = root / "08_figuras" / "piloto_humano.csv"
    pricing_path = root / "08_figuras" / "precos_openai.csv"
    snapshot = pd.read_parquet(snapshot_path)
    request_index: dict[str, str] = {}
    with Path(request_path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            request = json.loads(line)
            request_index[request["custom_id"]] = str(request["body"]["metadata"]["texto_id"])
    with Path(batch_output_path).open(encoding="utf-8") as stream:
        results, errors = parse_batch_output(
            stream,
            request_index=request_index,
            categories=config.raw["rhetorical_figures"],
        )
    if not results.empty:
        results["model"] = results["model"].fillna(model)
    prevalence = figure_prevalence(results, snapshot) if not results.empty else pd.DataFrame()
    outputs = []
    for name, frame, suffix in [
        (f"resultados_{model}", results, ".parquet"),
        (f"erros_{model}", errors, ".csv"),
        (f"prevalencia_{model}", prevalence, ".csv"),
    ]:
        path = write_dataframe_atomic(frame, root / "08_figuras" / f"{name}{suffix}")
        outputs.append(artifact_record(path, rows=len(frame)))
    counts: dict[str, Any] = {"classified_rows": len(results), "errors": len(errors), "model": model}
    if not results.empty and pricing_path.exists():
        pricing = pd.read_csv(pricing_path)
        model_pricing = pricing.loc[pricing["model"].eq(model)]
        price_fields = ["input_per_million", "output_per_million", "batch_discount", "source_url", "as_of"]
        if len(model_pricing) == 1 and model_pricing[price_fields].notna().all(axis=None) and model_pricing[["source_url", "as_of"]].astype(str).apply(lambda column: column.str.strip().ne("").all()).all():
            usage_columns = [column for column in ["custom_id", "response_id", "model", "input_tokens", "output_tokens", "cached_input_tokens"] if column in results]
            usage = results[usage_columns].drop_duplicates("custom_id")
            costs = calculate_usage_cost(usage, model_pricing)
            cost_path = write_dataframe_atomic(costs, root / "08_figuras" / f"custos_{model}.csv")
            outputs.append(artifact_record(cost_path, rows=len(costs)))
            counts["estimated_cost"] = float(costs["estimated_cost"].sum())
    if human_path.exists() and not results.empty:
        human = pd.read_csv(human_path, keep_default_na=False)
        adjudicated = human.loc[human["adjudicado"].astype(str).str.casefold().isin({"true", "1", "sim"})]
        counts["human_adjudicated_rows"] = len(adjudicated)
        if not adjudicated.empty:
            human_sets = []
            prediction_sets = []
            ids = sorted(set(adjudicated["texto_id"].astype(str)) & set(results["texto_id"].astype(str)))
            for text_id in ids:
                human_sets.append(_sets_for_speech(adjudicated, text_id, present_column="presente_humano"))
                prediction_sets.append(_sets_for_speech(results, text_id, present_column="presente"))
            summary, labels = evaluate_multilabel(human_sets, prediction_sets, config.raw["rhetorical_figures"])
            summary_frame = pd.DataFrame([{"model": model, **summary}])
            labels.insert(0, "model", model)
            for name, frame in [(f"avaliacao_resumo_{model}", summary_frame), (f"avaliacao_categorias_{model}", labels)]:
                path = write_dataframe_atomic(frame, root / "08_figuras" / f"{name}.csv")
                outputs.append(artifact_record(path, rows=len(frame)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="08_figuras_resultados",
        inputs=[artifact_record(snapshot_path, rows=len(snapshot)), artifact_record(request_path), artifact_record(batch_output_path)],
        outputs=outputs,
        counts=counts,
    )
    manifest_path = write_json_atomic(root / "08_figuras" / f"manifest_resultados_{model}.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def binary_kappa(left: Sequence[bool], right: Sequence[bool]) -> float:
    left_array, right_array = np.asarray(left, dtype=bool), np.asarray(right, dtype=bool)
    if len(left_array) == 0:
        return np.nan
    observed = float(np.mean(left_array == right_array))
    left_yes, right_yes = float(left_array.mean()), float(right_array.mean())
    expected = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    return (observed - expected) / (1 - expected) if expected < 1 else np.nan


def _mean_jaccard(truth: Sequence[Iterable[str]], prediction: Sequence[Iterable[str]]) -> float:
    scores = [multilabel_jaccard(left, right) for left, right in zip(truth, prediction)]
    usable = [row["jaccard"] for row in scores if not row["both_empty"]]
    return float(np.mean(usable)) if usable else np.nan


def _sets_for_speech(frame: pd.DataFrame, speech_id: str, *, present_column: str) -> set[str]:
    subset = frame.loc[frame["texto_id"].astype(str).eq(str(speech_id))]
    present = subset[present_column]
    if present.dtype != bool:
        present = present.astype(str).str.casefold().isin({"true", "1", "sim"})
    return set(subset.loc[present.to_numpy(), "categoria"].astype(str))


def _response_output_text(body: Mapping[str, Any]) -> str:
    if isinstance(body.get("output_text"), str):
        return str(body["output_text"])
    pieces: list[str] = []
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                pieces.append(content["text"])
    if not pieces:
        raise ValueError("Resposta sem output_text")
    return "".join(pieces)


def _flatten_figure_payload(payload: Mapping[str, Any], *, custom_id: str, body: Mapping[str, Any]) -> list[dict[str, Any]]:
    texto_id = str(payload["texto_id"])
    usage = body.get("usage") or {}
    return [
        {
            "custom_id": custom_id,
            "response_id": body.get("id"),
            "model": body.get("model"),
            "texto_id": texto_id,
            "categoria": item["categoria"],
            "presente": bool(item["presente"]),
            "contagem": int(item["contagem"]),
            "evidencias": json.dumps(item["evidencias"], ensure_ascii=False),
            "confianca": float(item["confianca"]),
            "input_tokens": usage.get("input_tokens"),
            "cached_input_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        for item in payload["figuras"]
    ]


def _validate_figure_payload(payload: Mapping[str, Any], categories: Sequence[str] | None) -> None:
    figures = payload["figuras"]
    labels = [item["categoria"] for item in figures]
    if len(labels) != len(set(labels)):
        raise ValueError("Categorias de figuras duplicadas")
    if categories is not None and set(labels) != set(categories):
        raise ValueError("Categorias de figuras incompletas ou inesperadas")
    for item in figures:
        if bool(item["presente"]) and not item.get("evidencias"):
            raise ValueError(f"Figura presente sem evidencia: {item['categoria']}")
