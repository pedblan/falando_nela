from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

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
    "segmentacao_metodo",
    "segmentacao_modelo",
    "texto_fonte_sha256",
    "candidatos_aparte",
    "ordem_aparte",
    "aparte_bloco_inicio",
    "aparte_bloco_fim",
    "aparte_char_start",
    "aparte_char_end",
    "texto_aparte",
    "ordem_resposta",
    "resposta_bloco_inicio",
    "resposta_bloco_fim",
    "resposta_char_start",
    "resposta_char_end",
    "texto_resposta",
]
SEGMENTATION_SOURCE_COLUMNS = [
    "texto_id",
    "arena",
    "data",
    "texto_fonte",
    "texto_fonte_sha256",
    "caracteres",
    "blocos",
    "blocos_json",
    "candidatos",
    "candidatos_json",
]
SEGMENTATION_ERROR_COLUMNS = ["line", "custom_id", "texto_id", "aparte_id", "error"]
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
BATCH_MAX_REQUESTS = 50_000
BATCH_SAFE_MAX_BYTES = 190 * 1024 * 1024
SEGMENTATION_REVIEW_MANUAL_COLUMNS = [
    "segmentacao_aparte_correta",
    "segmentacao_resposta_correta",
    "revisor",
    "observacao_revisao",
]
QUALITATIVE_REVIEW_MANUAL_COLUMNS = [
    "presente_humano",
    "evidencia_humana",
    "codificador",
    "adjudicado",
    "observacao",
]


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
            "segmentacao_metodo": "regra_marcadores_v1",
            "segmentacao_modelo": None,
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
                "aparte_char_start": int(apart_turn["char_start"]),
                "aparte_char_end": int(apart_turn["char_end"]),
                "texto_aparte": apart_turn["turn_text"],
                "ordem_resposta": int(response_candidates.iloc[0]["turn_order"]) if len(response_candidates) else None,
                "resposta_char_start": int(response_candidates.iloc[0]["char_start"]) if len(response_candidates) else None,
                "resposta_char_end": int(response_candidates.iloc[0]["char_end"]) if len(response_candidates) else None,
                "texto_resposta": response_text,
            }
        )
    return pd.DataFrame(rows).reindex(columns=INTERACTION_COLUMNS)


def segment_text_blocks(text: str, *, max_chars: int = 240) -> list[dict[str, Any]]:
    """Create deterministic addressable blocks that preserve every source character."""

    if max_chars < 80:
        raise ValueError("max_chars deve ser pelo menos 80")
    source = str(text or "")
    blocks: list[dict[str, Any]] = []
    line_start = 0
    for line in source.splitlines(keepends=True):
        line_end = line_start + len(line)
        start = line_start
        while start < line_end:
            hard_end = min(start + max_chars, line_end)
            end = hard_end
            if hard_end < line_end:
                window = source[start:hard_end]
                candidates = [
                    match.end()
                    for match in re.finditer(r"(?<=[.!?;:])\s+|\s+", window)
                    if match.end() >= max_chars // 2
                ]
                if candidates:
                    end = start + candidates[-1]
            block_id = f"B{len(blocks) + 1:06d}"
            blocks.append(
                {
                    "block_id": block_id,
                    "char_start": start,
                    "char_end": end,
                    "text": source[start:end],
                }
            )
            start = end
        line_start = line_end
    if line_start < len(source):
        block_id = f"B{len(blocks) + 1:06d}"
        blocks.append(
            {
                "block_id": block_id,
                "char_start": line_start,
                "char_end": len(source),
                "text": source[line_start:],
            }
        )
    return blocks


def build_segmentation_candidates(
    interjections: pd.DataFrame,
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    """Keep one auditable candidate row per processed interjection."""

    if interjections["aparte_id"].astype(str).duplicated().any():
        raise ValueError("aparte_id duplicado no universo de segmentacao")
    bridge_columns = ["aparte_id", "texto_id", "ponte_status", "ponte_score"]
    available = [column for column in bridge_columns if column in bridge]
    if bridge.empty:
        linked = pd.DataFrame(columns=bridge_columns)
    else:
        if bridge["aparte_id"].astype(str).duplicated().any():
            raise ValueError("aparte_id duplicado na ponte")
        linked = bridge[available].copy()
    base = interjections.drop(
        columns=[column for column in ["texto_id", "ponte_status", "ponte_score"] if column in interjections],
        errors="ignore",
    )
    candidates = base.merge(linked, on="aparte_id", how="left", validate="one_to_one")
    candidates["ponte_status"] = candidates.get("ponte_status", pd.Series(index=candidates.index, dtype=object)).fillna("ausente")
    candidates["texto_id"] = candidates.get("texto_id", pd.Series(index=candidates.index, dtype=object))
    candidates["arena"] = candidates.get("source", pd.Series(index=candidates.index, dtype=object))
    return candidates


def build_segmentation_sources(
    candidates: pd.DataFrame,
    speeches: pd.DataFrame,
    *,
    block_max_chars: int = 240,
) -> pd.DataFrame:
    """Bundle all linked interjection candidates into one request per transcript."""

    eligible = candidates.loc[
        candidates["ponte_status"].isin(["exato", "provavel_unico"])
        & candidates["texto_id"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if eligible.empty:
        return pd.DataFrame(columns=SEGMENTATION_SOURCE_COLUMNS)
    speech_frame = speeches.copy()
    speech_frame = speech_frame.loc[speech_frame["texto_id"].fillna("").astype(str).str.strip().ne("")]
    if speech_frame["texto_id"].astype(str).duplicated().any():
        raise ValueError("texto_id duplicado no snapshot usado para segmentacao")
    speech_index = speech_frame.set_index(speech_frame["texto_id"].astype(str), drop=False).to_dict("index")
    rows: list[dict[str, Any]] = []
    candidate_fields = [
        "aparte_id",
        "aparteante_id",
        "aparteante_nome",
        "orador_id",
        "orador_nome",
        "data",
    ]
    for text_id, group in eligible.groupby(eligible["texto_id"].astype(str), sort=True):
        speech = speech_index.get(str(text_id))
        if speech is None:
            continue
        source = str(speech.get("texto_analitico") or speech.get("texto") or "")
        if not source.strip():
            continue
        blocks = segment_text_blocks(source, max_chars=block_max_chars)
        block_index = [
            {key: block[key] for key in ["block_id", "char_start", "char_end"]}
            for block in blocks
        ]
        candidate_records = []
        for record in group.sort_values("aparte_id", kind="stable").to_dict("records"):
            candidate_record = {field: _json_scalar(record.get(field)) for field in candidate_fields}
            candidate_record["aparte_id"] = str(candidate_record["aparte_id"])
            candidate_records.append(candidate_record)
        rows.append(
            {
                "texto_id": str(text_id),
                "arena": group["arena"].iloc[0],
                "data": _json_scalar(group["data"].iloc[0]) if "data" in group else None,
                "texto_fonte": source,
                "texto_fonte_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "caracteres": len(source),
                "blocos": len(blocks),
                "blocos_json": json.dumps(block_index, ensure_ascii=False),
                "candidatos": len(candidate_records),
                "candidatos_json": json.dumps(candidate_records, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows, columns=SEGMENTATION_SOURCE_COLUMNS)


def segmentation_output_schema() -> dict[str, Any]:
    nullable_block = {"type": ["string", "null"], "pattern": r"^B[0-9]{6}$"}
    return {
        "type": "object",
        "properties": {
            "texto_id": {"type": "string"},
            "segmentos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "aparte_id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": [
                                "segmentado_com_resposta",
                                "segmentado_sem_resposta_explicita",
                                "aparte_nao_localizado",
                                "incerto",
                            ],
                        },
                        "aparte_bloco_inicio": nullable_block,
                        "aparte_bloco_fim": nullable_block,
                        "resposta_bloco_inicio": nullable_block,
                        "resposta_bloco_fim": nullable_block,
                    },
                    "required": [
                        "aparte_id",
                        "status",
                        "aparte_bloco_inicio",
                        "aparte_bloco_fim",
                        "resposta_bloco_inicio",
                        "resposta_bloco_fim",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["texto_id", "segmentos"],
        "additionalProperties": False,
    }


def make_segmentation_batch_request(
    source: Mapping[str, Any],
    *,
    config: AnalysisConfig,
    model: str | None = None,
) -> dict[str, Any]:
    text_id = str(source["texto_id"])
    custom_id = "apartes-seg-" + hashlib.sha256(text_id.encode("utf-8")).hexdigest()[:20]
    blocks = json.loads(str(source["blocos_json"]))
    candidates = json.loads(str(source["candidatos_json"]))
    source_text = str(source["texto_fonte"])
    rendered_blocks = "\n".join(
        f"⟦{block['block_id']}⟧ {source_text[int(block['char_start']):int(block['char_end'])]}"
        for block in blocks
    )
    prompt = f"""Localize apartes parlamentares e a primeira resposta explícita do orador principal.

Você recebe candidatos já extraídos da base relacional e uma transcrição dividida localmente em blocos.
Sua saída deve conter todos os `aparte_id` candidatos exatamente uma vez e somente identificadores de blocos.

Regras:
- não suponha que todo candidato esteja realmente visível na transcrição;
- `aparte_nao_localizado` é um resultado válido e deve ter os quatro blocos nulos;
- `incerto` também deve ter os quatro blocos nulos;
- o trecho do aparte deve conter somente o turno do aparteante, sem absorver falas vizinhas;
- a resposta é a primeira resposta explícita do orador principal ao aparte;
- se o aparte estiver claro, mas não houver resposta explícita, use `segmentado_sem_resposta_explicita` e blocos de resposta nulos;
- início e fim são inclusivos e devem respeitar a ordem dos blocos;
- nunca devolva a transcrição nem copie os trechos: devolva somente IDs e status.

texto_id: {text_id}
candidatos: {json.dumps(candidates, ensure_ascii=False, separators=(',', ':'))}

TRANSCRIÇÃO EM BLOCOS:
{rendered_blocks}
"""
    segmentation_config = config.raw["interjection_segmentation"]
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model or config.raw["openai"]["interjection_segmentation_model"],
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "segmentacao_apartes_blocos",
                    "strict": True,
                    "schema": segmentation_output_schema(),
                }
            },
            "metadata": {
                "texto_id": text_id,
                "prompt_version": segmentation_config["prompt_version"],
                "texto_fonte_sha256": str(source["texto_fonte_sha256"]),
            },
        },
    }


def write_segmentation_batch_jsonl(
    sources: pd.DataFrame,
    path: str | Path,
    *,
    config: AnalysisConfig,
    model: str | None = None,
    max_requests: int = BATCH_MAX_REQUESTS,
    max_bytes: int = BATCH_SAFE_MAX_BYTES,
) -> list[Path]:
    records = sources.sort_values("texto_id", kind="stable").to_dict("records")
    return _write_batch_jsonl_parts(
        records,
        path,
        request_builder=lambda source: make_segmentation_batch_request(
            source,
            config=config,
            model=model,
        ),
        max_requests=max_requests,
        max_bytes=max_bytes,
    )


def parse_segmentation_batch_output(
    lines: Iterable[str],
    *,
    request_index: Mapping[str, str],
    sources: pd.DataFrame,
    candidates: pd.DataFrame,
    model: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    source_index = sources.set_index(sources["texto_id"].astype(str), drop=False).to_dict("index")
    candidate_index = candidates.set_index(candidates["aparte_id"].astype(str), drop=False).to_dict("index")
    parsed: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    seen_custom_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_number, "custom_id": None, "texto_id": None, "aparte_id": None, "error": str(exc)})
            continue
        custom_id = str(record.get("custom_id") or "")
        text_id = request_index.get(custom_id)
        if custom_id in seen_custom_ids:
            errors.append({"line": line_number, "custom_id": custom_id, "texto_id": text_id, "aparte_id": None, "error": "custom_id duplicado na saida"})
            continue
        seen_custom_ids.add(custom_id)
        if text_id is None or str(text_id) not in source_index:
            errors.append({"line": line_number, "custom_id": custom_id, "texto_id": text_id, "aparte_id": None, "error": "custom_id desconhecido"})
            continue
        response = record.get("response") or {}
        if response.get("status_code") != 200:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": json.dumps(record.get("error") or response, ensure_ascii=False),
                }
            )
            continue
        source = source_index[str(text_id)]
        try:
            payload = json.loads(_response_output_text(response.get("body") or {}))
            rows = _reconstruct_segmentation_payload(
                payload,
                source=source,
                candidates=candidate_index,
                model=model,
            )
            for row in rows:
                apart_id = str(row["aparte_id"])
                if apart_id in parsed:
                    raise ValueError(f"aparte_id repetido entre respostas: {apart_id}")
                parsed[apart_id] = row
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"line": line_number, "custom_id": custom_id, "texto_id": text_id, "aparte_id": None, "error": str(exc)})

    for custom_id, text_id in request_index.items():
        if custom_id not in seen_custom_ids:
            errors.append(
                {
                    "line": None,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": "request sem linha correspondente na saida do Batch",
                }
            )
    rows = []
    source_text_ids = set(sources["texto_id"].astype(str))
    for apart_id, candidate in candidate_index.items():
        if apart_id in parsed:
            rows.append(parsed[apart_id])
            continue
        linked = candidate.get("ponte_status") in {"exato", "provavel_unico"}
        text_id = str(candidate.get("texto_id") or "")
        status = "ia_sem_resultado" if linked and text_id in source_text_ids else "sem_texto_validado"
        rows.append(_interaction_base(candidate) | {"segmentacao_status": status, "segmentacao_metodo": "ia_blocos_offsets_v1", "segmentacao_modelo": model})
    frame = pd.DataFrame(rows).reindex(columns=INTERACTION_COLUMNS)
    return frame, pd.DataFrame(errors, columns=SEGMENTATION_ERROR_COLUMNS)


def run_segmentation_results(
    *,
    data_root: str | Path,
    run_id: str,
    batch_output_path: str | Path | Sequence[str | Path],
    request_path: str | Path | Sequence[str | Path],
    model: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    stage_root = root / "03_apartes"
    sources_path = stage_root / "fontes_segmentacao_ia.parquet"
    candidates_path = stage_root / "candidatos_segmentacao_ia.parquet"
    sources = pd.read_parquet(sources_path)
    candidates = pd.read_parquet(candidates_path)
    request_paths = _coerce_paths(request_path)
    output_paths = _coerce_paths(batch_output_path)
    request_index: dict[str, str] = {}
    for line in _iter_path_lines(request_paths):
        if not line.strip():
            continue
        request = json.loads(line)
        custom_id = str(request["custom_id"])
        if custom_id in request_index:
            raise ValueError(f"custom_id duplicado no JSONL: {custom_id}")
        request_index[custom_id] = str(request["body"]["metadata"]["texto_id"])
    interactions, errors = parse_segmentation_batch_output(
        _iter_path_lines(output_paths),
        request_index=request_index,
        sources=sources,
        candidates=candidates,
        model=model,
    )
    outputs = []
    interactions_path = write_dataframe_atomic(interactions, stage_root / "interacoes_segmentadas_ia.parquet")
    outputs.append(artifact_record(interactions_path, rows=len(interactions)))
    errors_path = write_dataframe_atomic(errors, stage_root / "segmentacao_ia_erros.csv")
    outputs.append(artifact_record(errors_path, rows=len(errors)))
    segmentation_config = config.raw["interjection_segmentation"]
    review_sample = qualitative_review_sample(
        interactions,
        size=int(segmentation_config["review_sample_size"]),
        seed=config.seed,
    )
    review_sample["segmentacao_fingerprint"] = review_sample.apply(
        _segmentation_fingerprint,
        axis=1,
    )
    review_sample["segmentacao_aparte_correta"] = ""
    review_sample["segmentacao_resposta_correta"] = ""
    review_sample["revisor"] = ""
    review_sample["observacao_revisao"] = ""
    review_path = stage_root / "revisao_segmentacao_ia.csv"
    review_sample = _preserve_manual_columns(
        review_sample,
        review_path,
        key_columns=["interaction_id", "segmentacao_fingerprint"],
        manual_columns=SEGMENTATION_REVIEW_MANUAL_COLUMNS,
    )
    review_path = write_dataframe_atomic(review_sample, review_path)
    outputs.append(artifact_record(review_path, rows=len(review_sample)))
    manual_template = manual_coding_template(review_sample, config)
    manual_path = stage_root / "piloto_atos_fala_ia.csv"
    manual_template = _preserve_manual_columns(
        manual_template,
        manual_path,
        key_columns=["interaction_id", "segmentacao_fingerprint", "unidade", "categoria"],
        manual_columns=QUALITATIVE_REVIEW_MANUAL_COLUMNS,
    )
    manual_path = write_dataframe_atomic(manual_template, manual_path)
    outputs.append(artifact_record(manual_path, rows=len(manual_template)))
    quality = {
        "available": True,
        "method": "ia_blocos_offsets_v1",
        "model": model,
        "offset_unit": "python_unicode_codepoint",
        **segmentation_quality(
            interactions,
            review_sample,
            min_precision=float(segmentation_config["min_precision"]),
            min_reviewed=int(segmentation_config["min_reviewed"]),
        ),
    }
    quality_path = write_json_atomic(stage_root / "segmentacao_qualidade.json", quality)
    outputs.append(artifact_record(quality_path))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="03_apartes_segmentacao_ia",
        inputs=[
            artifact_record(sources_path, rows=len(sources)),
            artifact_record(candidates_path, rows=len(candidates)),
            *(artifact_record(path) for path in request_paths),
            *(artifact_record(path) for path in output_paths),
        ],
        outputs=outputs,
        counts={
            "candidate_interjections": len(candidates),
            "source_transcripts": len(sources),
            "segmented": quality["segmented"],
            "not_located": int(interactions["segmentacao_status"].eq("aparte_nao_localizado").sum()),
            "uncertain": int(interactions["segmentacao_status"].eq("incerto").sum()),
            "without_validated_text": int(interactions["segmentacao_status"].eq("sem_texto_validado").sum()),
            "without_batch_result": int(interactions["segmentacao_status"].eq("ia_sem_resultado").sum()),
            "errors": len(errors),
            "review_sample": len(review_sample),
            "model": model,
            "batch_request_parts": len(request_paths),
            "batch_output_parts": len(output_paths),
        },
    )
    manifest_path = write_json_atomic(stage_root / f"manifest_segmentacao_{model}.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


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


def ensure_qualitative_codebook(path: str | Path, config: AnalysisConfig) -> pd.DataFrame:
    """Create the codebook once and preserve later human edits."""

    destination = Path(path)
    template = qualitative_codebook_template(config)
    if not destination.exists():
        write_dataframe_atomic(template, destination)
        return template
    existing = pd.read_csv(destination, keep_default_na=False)
    expected_columns = list(template.columns)
    if list(existing.columns) != expected_columns:
        raise ValueError(
            "Codebook existente com colunas incompatíveis; preserve o arquivo e faça a migração explicitamente"
        )
    key_columns = ["unidade", "categoria"]
    if existing.duplicated(key_columns).any():
        raise ValueError("Codebook existente contém categorias duplicadas")
    expected_keys = set(map(tuple, template[key_columns].astype(str).to_numpy()))
    actual_keys = set(map(tuple, existing[key_columns].astype(str).to_numpy()))
    if actual_keys != expected_keys:
        raise ValueError(
            "Codebook existente usa taxonomia diferente da configuração; não será sobrescrito"
        )
    return existing


def manual_coding_template(sample: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    rows = []
    categories = [
        *(('aparte', category) for category in config.raw["interjection_speech_acts"]),
        *(('resposta', category) for category in config.raw["response_speech_acts"]),
        ("interacao", "possivel_descortesia"),
    ]
    for interaction in sample.to_dict("records"):
        fingerprint = interaction.get("segmentacao_fingerprint")
        if (
            fingerprint is None
            or pd.isna(fingerprint)
            or not str(fingerprint).strip()
        ):
            fingerprint = _segmentation_fingerprint(interaction)
        for unit, category in categories:
            rows.append(
                {
                    "interaction_id": interaction["interaction_id"],
                    "segmentacao_fingerprint": str(fingerprint),
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
            "segmentacao_fingerprint",
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
    eligible = interactions.loc[_segmentation_eligible_mask(interactions)].copy()
    if eligible.empty:
        return eligible
    years = pd.to_numeric(eligible["ano"], errors="coerce")
    eligible["periodo"] = pd.cut(years, bins=[2009, 2015, 2019, 2026], labels=["2010-2015", "2016-2019", "2020-2026"])
    eligible["direcao_genero"] = eligible["aparteante_genero"].fillna("desconhecido").astype(str) + "→" + eligible["orador_genero"].fillna("desconhecido").astype(str)
    strata = ["arena", "periodo", "direcao_genero"]
    groups = [
        group.sample(frac=1, random_state=seed + position).reset_index(drop=True)
        for position, (_, group) in enumerate(eligible.groupby(strata, dropna=False, observed=True, sort=True))
    ]
    target = min(size, len(eligible))
    selected: list[pd.Series] = []
    offset = 0
    while len(selected) < target:
        added = False
        for group in groups:
            if offset < len(group) and len(selected) < target:
                selected.append(group.iloc[offset])
                added = True
        if not added:
            break
        offset += 1
    sample = pd.DataFrame(selected).reindex(columns=eligible.columns)
    return sample.sort_values(["arena", "periodo", "interaction_id"], kind="stable").reset_index(drop=True)


def segmentation_quality(
    interactions: pd.DataFrame,
    gold: pd.DataFrame | None = None,
    *,
    min_precision: float = 0.95,
    min_reviewed: int = 100,
) -> dict[str, Any]:
    eligible = _segmentation_eligible_mask(interactions)
    result: dict[str, Any] = {
        "n": len(interactions),
        "segmented": int(eligible.sum()),
        "coverage": float(eligible.mean()) if len(interactions) else np.nan,
        "reviewed": 0,
        "review_rows_total": 0,
        "review_rows_complete": 0,
        "review_rows_invalid": 0,
        "precision_aparte": None,
        "precision_resposta": None,
        "classification_authorized": False,
    }
    if gold is None or gold.empty:
        return result
    required = {
        "interaction_id",
        "segmentacao_aparte_correta",
        "segmentacao_resposta_correta",
    }
    if missing := required.difference(gold.columns):
        raise ValueError(f"Gold de segmentacao sem colunas: {sorted(missing)}")
    evaluation = interactions.loc[eligible].copy()
    evaluation["interaction_id"] = evaluation["interaction_id"].astype(str)
    merge_keys = ["interaction_id"]
    selected_columns = list(required)
    if "segmentacao_fingerprint" in gold:
        evaluation["segmentacao_fingerprint"] = evaluation.apply(
            _segmentation_fingerprint,
            axis=1,
        )
        gold = gold.copy()
        gold["segmentacao_fingerprint"] = gold[
            "segmentacao_fingerprint"
        ].astype(str)
        merge_keys.append("segmentacao_fingerprint")
        selected_columns.append("segmentacao_fingerprint")
    if gold.duplicated(merge_keys).any():
        raise ValueError(f"Gold de segmentacao contem chave duplicada: {merge_keys}")
    gold_evaluation = gold[selected_columns].copy()
    gold_evaluation["interaction_id"] = gold_evaluation["interaction_id"].astype(str)
    comparison = evaluation.merge(
        gold_evaluation,
        on=merge_keys,
        how="inner",
        validate="one_to_one",
    )
    apart_correct, apart_invalid = _optional_boolean_series(comparison["segmentacao_aparte_correta"])
    response_correct, response_invalid = _optional_boolean_series(comparison["segmentacao_resposta_correta"])
    complete = apart_correct.notna() & response_correct.notna()
    reviewed = comparison.loc[complete]
    apart_reviewed = apart_correct.loc[complete].astype(bool)
    response_reviewed = response_correct.loc[complete].astype(bool)
    invalid = apart_invalid | response_invalid
    result.update(
        {
            "reviewed": len(reviewed),
            "review_rows_total": len(comparison),
            "review_rows_complete": len(reviewed),
            "review_rows_invalid": int(invalid.sum()),
            "precision_aparte": float(apart_reviewed.mean()) if len(reviewed) else None,
            "precision_resposta": float(response_reviewed.mean()) if len(reviewed) else None,
        }
    )
    result["classification_authorized"] = bool(
        len(reviewed) >= min_reviewed
        and result["precision_aparte"] is not None
        and result["precision_resposta"] is not None
        and float(result["precision_aparte"]) >= min_precision
        and float(result["precision_resposta"]) >= min_precision
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
    max_requests: int = BATCH_MAX_REQUESTS,
    max_bytes: int = BATCH_SAFE_MAX_BYTES,
) -> list[Path]:
    eligible = interactions.loc[_segmentation_eligible_mask(interactions)].copy()
    records = eligible.sort_values("interaction_id", kind="stable").to_dict("records")
    return _write_batch_jsonl_parts(
        records,
        path,
        request_builder=lambda interaction: make_qualitative_batch_request(
            interaction,
            codebook=codebook,
            config=config,
            model=model,
        ),
        max_requests=max_requests,
        max_bytes=max_bytes,
    )


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
    seen_custom_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": None,
                    "interaction_id": None,
                    "error": str(exc),
                }
            )
            continue
        custom_id = str(record.get("custom_id") or "")
        interaction_id = request_index.get(custom_id)
        if custom_id in seen_custom_ids:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "interaction_id": interaction_id,
                    "error": "custom_id duplicado na saída",
                }
            )
            continue
        seen_custom_ids.add(custom_id)
        if interaction_id is None:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "interaction_id": None,
                    "error": "custom_id desconhecido",
                }
            )
            continue
        response = record.get("response") or {}
        if response.get("status_code") != 200:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "interaction_id": interaction_id,
                    "error": json.dumps(
                        record.get("error") or response,
                        ensure_ascii=False,
                    ),
                }
            )
            continue
        try:
            body = response.get("body") or {}
            payload = json.loads(_response_output_text(body))
            if str(payload.get("interaction_id")) != str(interaction_id):
                raise ValueError(
                    f"interaction_id divergente: esperado {interaction_id}"
                )
            _validate_payload_categories(payload, config)
            rows.append(
                flatten_qualitative_payload(
                    payload,
                    model=model,
                    custom_id=custom_id,
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "interaction_id": interaction_id,
                    "error": str(exc),
                }
            )
    for custom_id, interaction_id in request_index.items():
        if custom_id not in seen_custom_ids:
            errors.append(
                {
                    "line": None,
                    "custom_id": custom_id,
                    "interaction_id": interaction_id,
                    "error": "request sem linha correspondente na saída do Batch",
                }
            )
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
    batch_output_path: str | Path | Sequence[str | Path],
    request_path: str | Path | Sequence[str | Path],
    model: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    interactions_path = root / "03_apartes" / "interacoes_segmentadas_ia.parquet"
    human_path = root / "03_apartes" / "piloto_atos_fala_ia.csv"
    interactions = pd.read_parquet(interactions_path)
    request_paths = _coerce_paths(request_path)
    output_paths = _coerce_paths(batch_output_path)
    request_index: dict[str, str] = {}
    for line in _iter_path_lines(request_paths):
        if not line.strip():
            continue
        request = json.loads(line)
        custom_id = str(request["custom_id"])
        if custom_id in request_index:
            raise ValueError(f"custom_id duplicado no JSONL: {custom_id}")
        request_index[custom_id] = str(
            request["body"]["metadata"]["interaction_id"]
        )
    results, errors = parse_qualitative_batch_output(
        _iter_path_lines(output_paths),
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
            *(artifact_record(path) for path in request_paths),
            *(artifact_record(path) for path in output_paths),
        ],
        outputs=outputs,
        counts={
            "classified_rows": len(results),
            "errors": len(errors),
            "model": model,
            "batch_request_parts": len(request_paths),
            "batch_output_parts": len(output_paths),
            **evaluation_counts,
        },
    )
    manifest_path = write_json_atomic(root / "03_apartes" / f"manifest_qualitativo_{model}.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def _reconstruct_segmentation_payload(
    payload: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    model: str,
) -> list[dict[str, Any]]:
    text_id = str(source["texto_id"])
    if str(payload.get("texto_id")) != text_id:
        raise ValueError(f"texto_id divergente: esperado {text_id}")
    expected_records = json.loads(str(source["candidatos_json"]))
    expected_ids = {str(record["aparte_id"]) for record in expected_records}
    segments = payload.get("segmentos")
    if not isinstance(segments, list):
        raise ValueError("segmentos deve ser uma lista")
    actual_ids = [str(segment.get("aparte_id")) for segment in segments]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids:
        raise ValueError("aparte_id ausente, inesperado ou duplicado na resposta")
    blocks = json.loads(str(source["blocos_json"]))
    block_index = {str(block["block_id"]): (position, block) for position, block in enumerate(blocks)}
    source_text = str(source["texto_fonte"])
    rows = []
    for segment in segments:
        apart_id = str(segment["aparte_id"])
        candidate = candidates.get(apart_id)
        if candidate is None or str(candidate.get("texto_id")) != text_id:
            raise ValueError(f"candidato incompatível com texto_id: {apart_id}")
        status = str(segment["status"])
        allowed_statuses = {
            "segmentado_com_resposta",
            "segmentado_sem_resposta_explicita",
            "aparte_nao_localizado",
            "incerto",
        }
        if status not in allowed_statuses:
            raise ValueError(f"status de segmentacao invalido: {status}")
        apart_span = _block_span(
            segment.get("aparte_bloco_inicio"),
            segment.get("aparte_bloco_fim"),
            block_index=block_index,
            source_text=source_text,
        )
        response_span = _block_span(
            segment.get("resposta_bloco_inicio"),
            segment.get("resposta_bloco_fim"),
            block_index=block_index,
            source_text=source_text,
        )
        if status in {"aparte_nao_localizado", "incerto"}:
            if apart_span is not None or response_span is not None:
                raise ValueError(f"{status} exige blocos nulos: {apart_id}")
        else:
            if apart_span is None:
                raise ValueError(f"segmentacao sem trecho de aparte: {apart_id}")
            if not str(apart_span["text"]).strip():
                raise ValueError(f"trecho de aparte vazio: {apart_id}")
            if status == "segmentado_com_resposta" and response_span is None:
                raise ValueError(f"resposta obrigatoria ausente: {apart_id}")
            if (
                status == "segmentado_com_resposta"
                and response_span is not None
                and not str(response_span["text"]).strip()
            ):
                raise ValueError(f"trecho de resposta vazio: {apart_id}")
            if status == "segmentado_sem_resposta_explicita" and response_span is not None:
                raise ValueError(f"resposta deve ser nula: {apart_id}")
            if response_span is not None and int(response_span["char_start"]) < int(apart_span["char_end"]):
                raise ValueError(f"resposta anterior ou sobreposta ao aparte: {apart_id}")
        row = _interaction_base(candidate)
        row.update(
            {
                "segmentacao_status": status,
                "segmentacao_metodo": "ia_blocos_offsets_v1",
                "segmentacao_modelo": model,
                "texto_fonte_sha256": source["texto_fonte_sha256"],
            }
        )
        if apart_span is not None:
            row.update(
                {
                    "ordem_aparte": apart_span["start_order"],
                    "aparte_bloco_inicio": apart_span["start_id"],
                    "aparte_bloco_fim": apart_span["end_id"],
                    "aparte_char_start": apart_span["char_start"],
                    "aparte_char_end": apart_span["char_end"],
                    "texto_aparte": apart_span["text"],
                }
            )
        if response_span is not None:
            row.update(
                {
                    "ordem_resposta": response_span["start_order"],
                    "resposta_bloco_inicio": response_span["start_id"],
                    "resposta_bloco_fim": response_span["end_id"],
                    "resposta_char_start": response_span["char_start"],
                    "resposta_char_end": response_span["char_end"],
                    "texto_resposta": response_span["text"],
                }
            )
        rows.append(row)
    return rows


def _block_span(
    start_id: Any,
    end_id: Any,
    *,
    block_index: Mapping[str, tuple[int, Mapping[str, Any]]],
    source_text: str,
) -> dict[str, Any] | None:
    if start_id is None and end_id is None:
        return None
    if start_id is None or end_id is None:
        raise ValueError("inicio e fim do intervalo devem ser ambos nulos ou preenchidos")
    start_key, end_key = str(start_id), str(end_id)
    if start_key not in block_index or end_key not in block_index:
        raise ValueError(f"bloco inexistente: {start_key}..{end_key}")
    start_order, start_block = block_index[start_key]
    end_order, end_block = block_index[end_key]
    if start_order > end_order:
        raise ValueError(f"intervalo de blocos invertido: {start_key}..{end_key}")
    char_start = int(start_block["char_start"])
    char_end = int(end_block["char_end"])
    return {
        "start_id": start_key,
        "end_id": end_key,
        "start_order": start_order,
        "end_order": end_order,
        "char_start": char_start,
        "char_end": char_end,
        "text": source_text[char_start:char_end],
    }


def _interaction_base(candidate: Mapping[str, Any]) -> dict[str, Any]:
    date_value = candidate.get("data")
    year = candidate.get("ano")
    if pd.isna(year):
        parsed_date = pd.to_datetime(date_value, errors="coerce")
        year = int(parsed_date.year) if pd.notna(parsed_date) else None
    return {
        "interaction_id": str(candidate.get("aparte_id")),
        "aparte_id": candidate.get("aparte_id"),
        "texto_id": candidate.get("texto_id"),
        "arena": candidate.get("arena") or candidate.get("source"),
        "data": date_value,
        "ano": year,
        "orador_id": candidate.get("orador_id"),
        "orador_nome": candidate.get("orador_nome"),
        "orador_genero": candidate.get("orador_genero"),
        "aparteante_id": candidate.get("aparteante_id"),
        "aparteante_nome": candidate.get("aparteante_nome"),
        "aparteante_genero": candidate.get("aparteante_genero"),
        "ponte_status": candidate.get("ponte_status"),
        "url_texto": candidate.get("url_texto"),
    }


def _json_scalar(value: Any) -> Any:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _segmentation_eligible_mask(interactions: pd.DataFrame) -> pd.Series:
    status = interactions.get(
        "segmentacao_status",
        pd.Series("", index=interactions.index, dtype=object),
    ).fillna("")
    apart_text = interactions.get(
        "texto_aparte",
        pd.Series("", index=interactions.index, dtype=object),
    ).fillna("").astype(str).str.strip().ne("")
    response_text = interactions.get(
        "texto_resposta",
        pd.Series("", index=interactions.index, dtype=object),
    ).fillna("").astype(str).str.strip().ne("")
    return (
        status.eq("segmentado_sem_resposta_explicita") & apart_text
    ) | (
        status.eq("segmentado_com_resposta") & apart_text & response_text
    )


def _segmentation_fingerprint(interaction: Mapping[str, Any]) -> str:
    fields = [
        "interaction_id",
        "texto_id",
        "segmentacao_status",
        "segmentacao_metodo",
        "segmentacao_modelo",
        "texto_fonte_sha256",
        "aparte_bloco_inicio",
        "aparte_bloco_fim",
        "aparte_char_start",
        "aparte_char_end",
        "texto_aparte",
        "resposta_bloco_inicio",
        "resposta_bloco_fim",
        "resposta_char_start",
        "resposta_char_end",
        "texto_resposta",
    ]
    payload = {
        field: _json_scalar(interaction.get(field))
        for field in fields
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preserve_manual_columns(
    template: pd.DataFrame,
    path: str | Path,
    *,
    key_columns: Sequence[str],
    manual_columns: Sequence[str],
) -> pd.DataFrame:
    destination = Path(path)
    if not destination.exists():
        return template
    existing = pd.read_csv(destination, keep_default_na=False)
    required = set(key_columns) | set(manual_columns)
    if missing := required.difference(existing.columns):
        raise ValueError(
            f"Arquivo manual existente sem colunas obrigatórias: {sorted(missing)}"
        )
    if missing := required.difference(template.columns):
        raise ValueError(
            f"Novo template sem colunas obrigatórias: {sorted(missing)}"
        )
    if existing.duplicated(list(key_columns)).any():
        raise ValueError(
            f"Arquivo manual existente contém chave duplicada: {list(key_columns)}"
        )
    if template.duplicated(list(key_columns)).any():
        raise ValueError(
            f"Novo template contém chave duplicada: {list(key_columns)}"
        )

    def key_for(row: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(str(row[column]) for column in key_columns)

    template_keys = {
        key_for(record)
        for record in template[list(key_columns)].to_dict("records")
    }
    annotated = existing.loc[
        existing[list(manual_columns)]
        .fillna("")
        .astype(str)
        .apply(lambda column: column.str.strip().ne(""))
        .any(axis=1)
    ]
    stale_annotated = [
        key_for(record)
        for record in annotated[list(key_columns)].to_dict("records")
        if key_for(record) not in template_keys
    ]
    if stale_annotated:
        preview = stale_annotated[:3]
        raise FileExistsError(
            "Há revisão humana preenchida para segmentações que mudaram; "
            f"preserve e migre essas linhas antes de reexecutar: {preview}"
        )
    manual_by_key = {
        key_for(record): {
            column: record[column]
            for column in manual_columns
        }
        for record in existing.to_dict("records")
    }
    preserved = template.copy()
    for row_index, record in preserved.to_dict("index").items():
        values = manual_by_key.get(key_for(record))
        if values is None:
            continue
        for column, value in values.items():
            preserved.at[row_index, column] = value
    return preserved


def _write_batch_jsonl_parts(
    records: Sequence[Mapping[str, Any]],
    path: str | Path,
    *,
    request_builder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    max_requests: int,
    max_bytes: int,
) -> list[Path]:
    """Write atomic JSONL parts below both official Batch limits."""

    if max_requests <= 0:
        raise ValueError("max_requests deve ser positivo")
    if max_bytes <= 0:
        raise ValueError("max_bytes deve ser positivo")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_paths: list[Path] = []
    streams: list[Any] = []
    current_stream: Any | None = None
    current_count = 0
    current_bytes = 0
    seen: set[str] = set()

    def start_part() -> Any:
        stream = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        )
        streams.append(stream)
        temporary_paths.append(Path(stream.name))
        return stream

    try:
        for record in records:
            request = request_builder(record)
            custom_id = str(request.get("custom_id") or "")
            if not custom_id:
                raise ValueError("Requisição Batch sem custom_id")
            if custom_id in seen:
                raise ValueError(f"custom_id duplicado: {custom_id}")
            seen.add(custom_id)
            encoded = (
                json.dumps(
                    request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            if len(encoded) > max_bytes:
                raise ValueError(
                    f"Uma única requisição excede max_bytes ({len(encoded)} > {max_bytes})"
                )
            if current_stream is None:
                current_stream = start_part()
            elif (
                current_count >= max_requests
                or current_bytes + len(encoded) > max_bytes
            ):
                current_stream.flush()
                os.fsync(current_stream.fileno())
                current_stream.close()
                current_stream = start_part()
                current_count = 0
                current_bytes = 0
            current_stream.write(encoded)
            current_count += 1
            current_bytes += len(encoded)
        if current_stream is not None and not current_stream.closed:
            current_stream.flush()
            os.fsync(current_stream.fileno())
            current_stream.close()
        if not temporary_paths:
            return []
        if len(temporary_paths) == 1:
            final_paths = [destination]
        else:
            final_paths = [
                destination.with_name(
                    f"{destination.stem}.part-{position:05d}{destination.suffix}"
                )
                for position in range(1, len(temporary_paths) + 1)
            ]
        for temporary_path, final_path in zip(
            temporary_paths,
            final_paths,
            strict=True,
        ):
            os.replace(temporary_path, final_path)
        return final_paths
    except Exception:
        for stream in streams:
            if not stream.closed:
                stream.close()
        for temporary_path in temporary_paths:
            if temporary_path.exists():
                temporary_path.unlink()
        raise


def _coerce_paths(
    value: str | Path | Sequence[str | Path],
) -> list[Path]:
    if isinstance(value, (str, Path)):
        paths = [Path(value)]
    else:
        paths = [Path(path) for path in value]
    if not paths:
        raise ValueError("Nenhum caminho de Batch informado")
    return paths


def _iter_path_lines(paths: Sequence[Path]) -> Iterable[str]:
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            yield from stream


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


def _optional_boolean_series(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    normalized = values.fillna("").astype(str).str.strip().str.casefold()
    truthy = {"true", "1", "sim"}
    falsy = {"false", "0", "nao", "não"}
    result = pd.Series(pd.NA, index=values.index, dtype="boolean")
    result.loc[normalized.isin(truthy)] = True
    result.loc[normalized.isin(falsy)] = False
    invalid = normalized.ne("") & ~normalized.isin(truthy | falsy)
    return result, invalid


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
