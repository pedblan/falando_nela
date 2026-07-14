from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .config import AnalysisConfig, load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


TURN_PATTERN = re.compile(
    r"(?m)^[\t \u00a0]*(?P<header>(?:O|A)\s+SR(?:A|ª)?\.\s+[^\n]+?)\s+[–—]\s+"
)
TURN_PATTERN_ASCII = re.compile(
    r"(?m)^[\t \u00a0]*(?P<header>(?:O|A)\s+SR(?:A|ª)?\.\s+[^\n]+)\s+-\s+"
)
TURN_COLUMNS = ["turn_order", "speaker_header", "speaker_name", "turn_text", "char_start", "char_end"]
INTERACTION_COLUMNS = [
    "interaction_id",
    "aparte_id",
    "texto_id",
    "arena",
    "data",
    "ano",
    "orador_id",
    "orador_nome",
    "orador_genero",
    "aparteante_id",
    "aparteante_nome",
    "aparteante_genero",
    "ponte_status",
    "url_texto",
    "segmentacao_status",
    "candidatos_aparte",
    "ordem_aparte",
    "texto_aparte",
    "ordem_resposta",
    "texto_resposta",
]
QUALITATIVE_RESULT_COLUMNS = [
    "custom_id",
    "interaction_id",
    "modelo",
    "unidade",
    "categoria",
    "presente",
    "evidencia",
]
QUALITATIVE_ERROR_COLUMNS = ["line", "custom_id", "interaction_id", "error"]


def build_senate_speech_bridge(interjections: pd.DataFrame, speeches: pd.DataFrame) -> pd.DataFrame:
    speech_index: dict[str, list[dict[str, Any]]] = {}
    for record in speeches.to_dict("records"):
        key = str(record.get("pronunciamento_id") or "").strip()
        if key:
            speech_index.setdefault(key, []).append(record)
    rows = []
    for aparte in interjections.to_dict("records"):
        key = str(aparte.get("pronunciamento_id") or "").strip()
        candidates = speech_index.get(key, []) if key else []
        if len(candidates) == 1:
            status, text_id = "exato", candidates[0].get("texto_id")
        elif len(candidates) > 1:
            status, text_id = "ambiguo", None
        else:
            status, text_id = "ausente", None
        rows.append(
            {
                "aparte_id": aparte.get("aparte_id"),
                "pronunciamento_id": aparte.get("pronunciamento_id"),
                "texto_id": text_id,
                "ponte_status": status,
                "ponte_score": 6.0 if status == "exato" else 0.0,
                "ponte_evidencias": "pronunciamento_id" if status == "exato" else "",
                "ponte_candidatos": len(candidates),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "aparte_id",
            "pronunciamento_id",
            "texto_id",
            "ponte_status",
            "ponte_score",
            "ponte_evidencias",
            "ponte_candidatos",
        ],
    )


def segment_transcript_turns(text: str) -> pd.DataFrame:
    """Segment stenographic text into explicit speaker turns without guessing boundaries."""

    source = str(text or "")
    matches = list(TURN_PATTERN.finditer(source))
    if not matches:
        matches = list(TURN_PATTERN_ASCII.finditer(source))
    rows: list[dict[str, Any]] = []
    for order, match in enumerate(matches):
        end = matches[order + 1].start() if order + 1 < len(matches) else len(source)
        header = match.group("header").strip()
        body = source[match.end() : end].strip()
        rows.append(
            {
                "turn_order": order,
                "speaker_header": header,
                "speaker_name": speaker_name_from_header(header),
                "turn_text": body,
                "char_start": match.start(),
                "char_end": end,
            }
        )
    return pd.DataFrame(rows, columns=TURN_COLUMNS)


def speaker_name_from_header(header: str) -> str:
    value = re.sub(r"^(?:O|A)\s+SR(?:A|ª)?\.\s+", "", header, flags=re.IGNORECASE).strip()
    before_parenthesis = value.split("(", 1)[0].strip()
    parenthetical = value.split("(", 1)[1].split(")", 1)[0].strip() if "(" in value else ""
    if before_parenthesis.casefold() in {"presidente", "presidenta"} and parenthetical:
        return parenthetical.split(".", 1)[0].strip()
    return before_parenthesis


def extract_interaction_turns(
    interjections: pd.DataFrame,
    speeches: pd.DataFrame,
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    """Extract the interjection turn and the following main-speaker response."""

    speech_index = speeches.set_index("texto_id", drop=False).to_dict("index")
    bridge_index = bridge.set_index("aparte_id", drop=False).to_dict("index") if not bridge.empty else {}
    rows: list[dict[str, Any]] = []
    for aparte in interjections.to_dict("records"):
        aparte_id = aparte.get("aparte_id")
        link = bridge_index.get(aparte_id, {})
        text_id = link.get("texto_id")
        speech = speech_index.get(text_id)
        base = {
            "interaction_id": str(aparte_id),
            "aparte_id": aparte_id,
            "texto_id": text_id,
            "arena": aparte.get("source"),
            "data": aparte.get("data"),
            "ano": aparte.get("ano"),
            "orador_id": aparte.get("orador_id"),
            "orador_nome": aparte.get("orador_nome"),
            "orador_genero": aparte.get("orador_genero"),
            "aparteante_id": aparte.get("aparteante_id"),
            "aparteante_nome": aparte.get("aparteante_nome"),
            "aparteante_genero": aparte.get("aparteante_genero"),
            "ponte_status": link.get("ponte_status", "ausente"),
            "url_texto": aparte.get("url_texto") or (speech or {}).get("url_texto"),
        }
        if speech is None or link.get("ponte_status") not in {"exato", "provavel_unico"}:
            rows.append({**base, "segmentacao_status": "sem_texto_validado", "texto_aparte": None, "texto_resposta": None})
            continue
        turns = segment_transcript_turns(str(speech.get("texto_analitico") or speech.get("texto") or ""))
        if turns.empty:
            rows.append({**base, "segmentacao_status": "sem_marcadores_de_turno", "texto_aparte": None, "texto_resposta": None})
            continue
        apart_name = _normalize(aparte.get("aparteante_nome"))
        candidate_mask = turns["speaker_name"].map(_normalize).map(lambda name: _compatible_name(name, apart_name))
        candidates = turns.loc[candidate_mask]
        if len(candidates) != 1:
            status = "aparte_ausente" if candidates.empty else "aparte_ambiguo"
            rows.append(
                {
                    **base,
                    "segmentacao_status": status,
                    "candidatos_aparte": len(candidates),
                    "texto_aparte": None,
                    "texto_resposta": None,
                }
            )
            continue
        apart_turn = candidates.iloc[0]
        main_name = _normalize(aparte.get("orador_nome"))
        following = turns.loc[
            turns["turn_order"].between(int(apart_turn["turn_order"]) + 1, int(apart_turn["turn_order"]) + 3)
        ]
        response_candidates = following.loc[
            following["speaker_name"].map(_normalize).map(lambda name: _compatible_name(name, main_name))
        ]
        response_text = response_candidates.iloc[0]["turn_text"] if len(response_candidates) else None
        status = "segmentado_com_resposta" if response_text else "segmentado_sem_resposta_explicita"
        rows.append(
            {
                **base,
                "segmentacao_status": status,
                "candidatos_aparte": 1,
                "ordem_aparte": int(apart_turn["turn_order"]),
                "texto_aparte": apart_turn["turn_text"],
                "ordem_resposta": int(response_candidates.iloc[0]["turn_order"]) if len(response_candidates) else None,
                "texto_resposta": response_text,
            }
        )
    return pd.DataFrame(rows).reindex(columns=INTERACTION_COLUMNS)


def qualitative_codebook_template(config: AnalysisConfig) -> pd.DataFrame:
    rows = []
    for unit, categories in [
        ("aparte", config.raw["interjection_speech_acts"]),
        ("resposta", config.raw["response_speech_acts"]),
    ]:
        for category in categories:
            rows.append(
                {
                    "unidade": unit,
                    "categoria": category,
                    "definicao_operacional": "",
                    "criterio_positivo": "",
                    "criterio_negativo": "",
                    "caso_limitrofe": "",
                    "exemplo_positivo_id": "",
                    "exemplo_negativo_id": "",
                    "fonte_taxonomia": "TD355",
                    "versao": "v1",
                }
            )
    rows.append(
        {
            "unidade": "interacao",
            "categoria": "possivel_descortesia",
            "definicao_operacional": "",
            "criterio_positivo": "",
            "criterio_negativo": "",
            "caso_limitrofe": "",
            "exemplo_positivo_id": "",
            "exemplo_negativo_id": "",
            "fonte_taxonomia": "TD355",
            "versao": "v1",
        }
    )
    return pd.DataFrame(
        rows,
        columns=[
            "unidade",
            "categoria",
            "definicao_operacional",
            "criterio_positivo",
            "criterio_negativo",
            "caso_limitrofe",
            "exemplo_positivo_id",
            "exemplo_negativo_id",
            "fonte_taxonomia",
            "versao",
        ],
    )


def manual_coding_template(sample: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    rows = []
    categories = [
        *(('aparte', category) for category in config.raw["interjection_speech_acts"]),
        *(('resposta', category) for category in config.raw["response_speech_acts"]),
        ("interacao", "possivel_descortesia"),
    ]
    for interaction in sample.to_dict("records"):
        for unit, category in categories:
            rows.append(
                {
                    "interaction_id": interaction["interaction_id"],
                    "arena": interaction.get("arena"),
                    "ano": interaction.get("ano"),
                    "unidade": unit,
                    "categoria": category,
                    "presente_humano": "",
                    "evidencia_humana": "",
                    "codificador": "",
                    "adjudicado": "",
                    "observacao": "",
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "interaction_id",
            "arena",
            "ano",
            "unidade",
            "categoria",
            "presente_humano",
            "evidencia_humana",
            "codificador",
            "adjudicado",
            "observacao",
        ],
    )


def qualitative_review_sample(
    interactions: pd.DataFrame,
    *,
    size: int = 200,
    seed: int = 20260713,
) -> pd.DataFrame:
    eligible = interactions.loc[
        interactions["segmentacao_status"].isin(["segmentado_com_resposta", "segmentado_sem_resposta_explicita"])
    ].copy()
    if eligible.empty:
        return eligible
    years = pd.to_numeric(eligible["ano"], errors="coerce")
    eligible["periodo"] = pd.cut(years, bins=[2009, 2015, 2019, 2026], labels=["2010-2015", "2016-2019", "2020-2026"])
    eligible["direcao_genero"] = eligible["aparteante_genero"].fillna("desconhecido").astype(str) + "→" + eligible["orador_genero"].fillna("desconhecido").astype(str)
    strata = ["arena", "periodo", "direcao_genero"]
    groups = list(eligible.groupby(strata, dropna=False, observed=True))
    quota = max(1, int(np.ceil(min(size, len(eligible)) / max(1, len(groups)))))
    pieces = [group.sample(n=min(quota, len(group)), random_state=seed) for _, group in groups]
    sample = pd.concat(pieces, ignore_index=True)
    if len(sample) > size:
        sample = sample.sample(n=size, random_state=seed)
    return sample.sort_values(["arena", "periodo", "interaction_id"], kind="stable").reset_index(drop=True)


def segmentation_quality(
    interactions: pd.DataFrame,
    gold: pd.DataFrame | None = None,
    *,
    min_precision: float = 0.95,
    min_reviewed: int = 100,
) -> dict[str, Any]:
    eligible = interactions["segmentacao_status"].isin(["segmentado_com_resposta", "segmentado_sem_resposta_explicita"])
    result: dict[str, Any] = {
        "n": len(interactions),
        "segmented": int(eligible.sum()),
        "coverage": float(eligible.mean()) if len(interactions) else np.nan,
        "reviewed": 0,
        "precision_aparte": None,
        "precision_resposta": None,
        "classification_authorized": False,
    }
    if gold is None or gold.empty:
        return result
    required = {"interaction_id", "segmentacao_aparte_correta", "segmentacao_resposta_correta"}
    if missing := required.difference(gold.columns):
        raise ValueError(f"Gold de segmentacao sem colunas: {sorted(missing)}")
    comparison = interactions.merge(gold[list(required)], on="interaction_id", how="inner")
    apart_correct = _boolean_series(comparison["segmentacao_aparte_correta"])
    response_correct = _boolean_series(comparison["segmentacao_resposta_correta"])
    result.update(
        {
            "reviewed": len(comparison),
            "precision_aparte": float(apart_correct.mean()) if len(comparison) else np.nan,
            "precision_resposta": float(response_correct.mean()) if len(comparison) else np.nan,
        }
    )
    result["classification_authorized"] = bool(
        len(comparison) >= min_reviewed
        and result["precision_aparte"] >= min_precision
        and result["precision_resposta"] >= min_precision
    )
    return result


def qualitative_output_schema(config: AnalysisConfig) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "interaction_id": {"type": "string"},
            "atos_aparte": _act_array_schema(config.raw["interjection_speech_acts"]),
            "atos_resposta": _act_array_schema(config.raw["response_speech_acts"]),
            "possivel_descortesia": {"type": "boolean"},
            "evidencia_descortesia": {"type": ["string", "null"]},
            "observacao": {"type": ["string", "null"]},
        },
        "required": [
            "interaction_id",
            "atos_aparte",
            "atos_resposta",
            "possivel_descortesia",
            "evidencia_descortesia",
            "observacao",
        ],
        "additionalProperties": False,
    }


def make_qualitative_batch_request(
    interaction: Mapping[str, Any],
    *,
    codebook: str,
    config: AnalysisConfig,
    model: str | None = None,
) -> dict[str, Any]:
    interaction_id = str(interaction["interaction_id"])
    custom_id = "apartes-" + hashlib.sha256(interaction_id.encode("utf-8")).hexdigest()[:24]
    prompt = f"""Classifique a interação parlamentar segundo o codebook abaixo.

Regras obrigatórias:
- o primeiro trecho é o aparte; o segundo, quando presente, é a resposta do orador principal;
- avalie todas as categorias de cada unidade exatamente uma vez;
- use apenas os trechos segmentados e o codebook;
- uma categoria presente exige evidência textual curta do trecho correspondente;
- não infira tom de voz, gesto ou intenção não sustentada pelo texto;
- `possivel_descortesia` é uma marca cautelosa, não diagnóstico da pessoa;
- ausência de resposta explícita não significa automaticamente `ignorar`.

Codebook:
{codebook}

interaction_id: {interaction_id}

APARTE:
{interaction.get('texto_aparte') or '[ausente]'}

RESPOSTA DO ORADOR PRINCIPAL:
{interaction.get('texto_resposta') or '[sem resposta explícita segmentada]'}
"""
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model or config.raw["openai"]["interjection_default_model"],
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "atos_fala_apartes",
                    "strict": True,
                    "schema": qualitative_output_schema(config),
                }
            },
            "metadata": {
                "interaction_id": interaction_id,
                "prompt_version": "apartes-atos-fala-v1",
            },
        },
    }


def write_qualitative_batch_jsonl(
    interactions: pd.DataFrame,
    path: str | Path,
    *,
    codebook: str,
    config: AnalysisConfig,
    model: str | None = None,
) -> Path:
    eligible = interactions.loc[
        interactions["segmentacao_status"].isin(["segmentado_com_resposta", "segmentado_sem_resposta_explicita"])
        & interactions["texto_aparte"].fillna("").str.strip().ne("")
    ]
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with destination.open("w", encoding="utf-8") as stream:
        for record in eligible.to_dict("records"):
            request = make_qualitative_batch_request(record, codebook=codebook, config=config, model=model)
            if request["custom_id"] in seen:
                raise ValueError(f"custom_id duplicado: {request['custom_id']}")
            seen.add(request["custom_id"])
            stream.write(json.dumps(request, ensure_ascii=False) + "\n")
    return destination


def flatten_qualitative_payload(payload: Mapping[str, Any], *, model: str, custom_id: str) -> pd.DataFrame:
    rows = []
    expected = {
        "aparte": "atos_aparte",
        "resposta": "atos_resposta",
    }
    for unit, field in expected.items():
        for item in payload[field]:
            rows.append(
                {
                    "custom_id": custom_id,
                    "interaction_id": payload["interaction_id"],
                    "modelo": model,
                    "unidade": unit,
                    "categoria": item["categoria"],
                    "presente": bool(item["presente"]),
                    "evidencia": item.get("evidencia"),
                }
            )
    rows.append(
        {
            "custom_id": custom_id,
            "interaction_id": payload["interaction_id"],
            "modelo": model,
            "unidade": "interacao",
            "categoria": "possivel_descortesia",
            "presente": bool(payload["possivel_descortesia"]),
            "evidencia": payload.get("evidencia_descortesia"),
        }
    )
    return pd.DataFrame(rows)


def parse_qualitative_batch_output(
    lines: Iterable[str],
    *,
    request_index: Mapping[str, str],
    model: str,
    config: AnalysisConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        custom_id = record.get("custom_id")
        response = record.get("response") or {}
        if response.get("status_code") != 200:
            errors.append({"line": line_number, "custom_id": custom_id, "interaction_id": request_index.get(custom_id), "error": json.dumps(record.get("error") or response, ensure_ascii=False)})
            continue
        try:
            body = response.get("body") or {}
            payload = json.loads(_response_output_text(body))
            _validate_payload_categories(payload, config)
            rows.append(flatten_qualitative_payload(payload, model=model, custom_id=str(custom_id)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"line": line_number, "custom_id": custom_id, "interaction_id": request_index.get(custom_id), "error": str(exc)})
    result_frame = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=QUALITATIVE_RESULT_COLUMNS)
    return result_frame.reindex(columns=QUALITATIVE_RESULT_COLUMNS), pd.DataFrame(errors, columns=QUALITATIVE_ERROR_COLUMNS)


def evaluate_qualitative_against_human(
    human: pd.DataFrame,
    results: pd.DataFrame,
    config: AnalysisConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .figuras import evaluate_multilabel

    summaries = []
    labels = []
    for model, model_frame in results.groupby("modelo"):
        for unit, categories in [
            ("aparte", config.raw["interjection_speech_acts"]),
            ("resposta", config.raw["response_speech_acts"]),
            ("interacao", ["possivel_descortesia"]),
        ]:
            human_unit = human.loc[human["unidade"].eq(unit)]
            model_unit = model_frame.loc[model_frame["unidade"].eq(unit)]
            speech_ids = sorted(set(human_unit["interaction_id"].astype(str)) & set(model_unit["interaction_id"].astype(str)))
            truth = [_present_set(human_unit, speech_id, "presente_humano") for speech_id in speech_ids]
            prediction = [_present_set(model_unit, speech_id, "presente") for speech_id in speech_ids]
            summary, per_label = evaluate_multilabel(truth, prediction, categories)
            summaries.append({"modelo": model, "unidade": unit, **summary})
            per_label.insert(0, "unidade", unit)
            per_label.insert(0, "modelo", model)
            labels.append(per_label)
    return pd.DataFrame(summaries), (pd.concat(labels, ignore_index=True) if labels else pd.DataFrame())


def qualitative_prevalence(
    results: pd.DataFrame,
    interactions: pd.DataFrame,
    *,
    dimensions: Sequence[str] = (),
) -> pd.DataFrame:
    metadata_columns = ["interaction_id", "arena", "ano", "aparteante_genero", "orador_genero", *dimensions]
    metadata = interactions[[column for column in dict.fromkeys(metadata_columns) if column in interactions]].copy()
    if "direcao_genero" in dimensions and "direcao_genero" not in metadata:
        metadata["direcao_genero"] = (
            interactions["aparteante_genero"].fillna("desconhecido").astype(str)
            + "→"
            + interactions["orador_genero"].fillna("desconhecido").astype(str)
        )
    merged = results.merge(metadata, on="interaction_id", how="left", validate="many_to_one")
    group_columns = ["modelo", "arena", "ano", *dimensions, "unidade", "categoria"]
    grouped = (
        merged.groupby(group_columns, dropna=False)["presente"]
        .agg([("n", "size"), ("presentes", "sum"), ("proporcao", "mean")])
        .reset_index()
    )
    historical_groups = ["modelo", "arena", *dimensions, "unidade", "categoria"]
    grouped["mediana_historica"] = grouped.groupby(historical_groups, dropna=False)["proporcao"].transform("median")
    grouped["diferenca_mediana_historica"] = grouped["proporcao"] - grouped["mediana_historica"]
    grouped["ytd"] = grouped["ano"].eq(2026)
    return grouped


def run_qualitative_results(
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
    interactions_path = root / "03_apartes" / "interacoes_segmentadas.parquet"
    human_path = root / "03_apartes" / "piloto_atos_fala.csv"
    interactions = pd.read_parquet(interactions_path)
    request_index: dict[str, str] = {}
    with Path(request_path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            request = json.loads(line)
            request_index[request["custom_id"]] = str(request["body"]["metadata"]["interaction_id"])
    with Path(batch_output_path).open(encoding="utf-8") as stream:
        results, errors = parse_qualitative_batch_output(
            stream,
            request_index=request_index,
            model=model,
            config=config,
        )
    prevalence = qualitative_prevalence(results, interactions)
    prevalence_gender = qualitative_prevalence(results, interactions, dimensions=["direcao_genero"])
    outputs = []
    for name, frame, suffix in [
        ("atos_fala_resultados", results, ".parquet"),
        ("atos_fala_erros", errors, ".csv"),
        ("atos_fala_prevalencia_anual", prevalence, ".csv"),
        ("atos_fala_prevalencia_genero", prevalence_gender, ".csv"),
    ]:
        path = write_dataframe_atomic(frame, root / "03_apartes" / f"{name}{suffix}")
        outputs.append(artifact_record(path, rows=len(frame)))
    evaluation_counts: dict[str, Any] = {"human_adjudicated_rows": 0}
    if human_path.exists():
        human = pd.read_csv(human_path, keep_default_na=False)
        adjudicated = human.loc[_boolean_series(human["adjudicado"])] if "adjudicado" in human else human.head(0)
        evaluation_counts["human_adjudicated_rows"] = len(adjudicated)
        if not adjudicated.empty:
            summary, labels = evaluate_qualitative_against_human(adjudicated, results, config)
            for name, frame in [("atos_fala_avaliacao_resumo", summary), ("atos_fala_avaliacao_categorias", labels)]:
                path = write_dataframe_atomic(frame, root / "03_apartes" / f"{name}.csv")
                outputs.append(artifact_record(path, rows=len(frame)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="03_apartes_qualitativo_resultados",
        inputs=[
            artifact_record(interactions_path, rows=len(interactions)),
            artifact_record(request_path),
            artifact_record(batch_output_path),
        ],
        outputs=outputs,
        counts={"classified_rows": len(results), "errors": len(errors), "model": model, **evaluation_counts},
    )
    manifest_path = write_json_atomic(root / "03_apartes" / f"manifest_qualitativo_{model}.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def _act_array_schema(categories: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "enum": list(categories)},
                "presente": {"type": "boolean"},
                "evidencia": {"type": ["string", "null"]},
            },
            "required": ["categoria", "presente", "evidencia"],
            "additionalProperties": False,
        },
        "minItems": len(categories),
        "maxItems": len(categories),
    }


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _compatible_name(candidate: str, expected: str) -> bool:
    if not candidate or not expected:
        return False
    return candidate == expected or (len(candidate) >= 5 and candidate in expected) or (len(expected) >= 5 and expected in candidate)


def _boolean_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.casefold().isin({"true", "1", "sim"})


def _present_set(frame: pd.DataFrame, interaction_id: str, column: str) -> set[str]:
    subset = frame.loc[frame["interaction_id"].astype(str).eq(str(interaction_id))]
    present = _boolean_series(subset[column])
    return set(subset.loc[present.to_numpy(), "categoria"].astype(str))


def _response_output_text(body: Mapping[str, Any]) -> str:
    if isinstance(body.get("output_text"), str):
        return str(body["output_text"])
    pieces = []
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                pieces.append(content["text"])
    if not pieces:
        raise ValueError("Resposta sem output_text")
    return "".join(pieces)


def _validate_payload_categories(payload: Mapping[str, Any], config: AnalysisConfig) -> None:
    actual_apart = [item["categoria"] for item in payload["atos_aparte"]]
    actual_response = [item["categoria"] for item in payload["atos_resposta"]]
    if set(actual_apart) != set(config.raw["interjection_speech_acts"]) or len(actual_apart) != len(set(actual_apart)):
        raise ValueError("Categorias do aparte incompletas ou duplicadas")
    if set(actual_response) != set(config.raw["response_speech_acts"]) or len(actual_response) != len(set(actual_response)):
        raise ValueError("Categorias da resposta incompletas ou duplicadas")
    for item in [*payload["atos_aparte"], *payload["atos_resposta"]]:
        if bool(item["presente"]) and not str(item.get("evidencia") or "").strip():
            raise ValueError(f"Categoria presente sem evidencia: {item['categoria']}")
    if bool(payload["possivel_descortesia"]) and not str(payload.get("evidencia_descortesia") or "").strip():
        raise ValueError("possivel_descortesia presente sem evidencia")
