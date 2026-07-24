from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .apartes import (
    analyze_interjections_by_arena_year,
    bridge_quality,
    build_camara_speech_bridge,
    denominators_authorized,
    filter_interjections_by_date,
)
from .apartes_qualitativos import (
    BATCH_MAX_REQUESTS,
    BATCH_SAFE_MAX_BYTES,
    _coerce_paths,
    _iter_path_lines,
    _optional_boolean_series,
    _preserve_manual_columns,
    _response_output_text,
    _write_batch_jsonl_parts,
    build_segmentation_candidates,
    build_senate_speech_bridge,
    speaker_name_from_header,
)
from .config import AnalysisConfig, load_config, resolve_input_paths, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


EPISODE_PIPELINE_VERSION = "episodios_interacao_v2"
EPISODE_METHOD = "ia_turnos_subturnos_v2"
EPISODE_REVIEW_MANUAL_COLUMNS = [
    "atribuicao_participantes_correta",
    "episodio_completo",
    "atribuicao_respostas_correta",
    "contexto_suficiente",
    "revisor",
    "observacao_revisao",
]
EPISODE_REVIEW_BOOLEAN_COLUMNS = EPISODE_REVIEW_MANUAL_COLUMNS[:4]
EPISODE_ERROR_COLUMNS = [
    "line",
    "custom_id",
    "texto_id",
    "aparte_id",
    "error",
]
PARTICIPANT_COLUMNS = [
    "texto_id",
    "participante_id",
    "pessoa_chave",
    "pessoa_id_relacional",
    "nome",
    "nome_normalizado",
    "origem",
    "papeis_json",
    "aparte_ids_json",
]
RAW_TURN_COLUMNS = [
    "texto_id",
    "turno_id",
    "ordem_turno",
    "speaker_header",
    "speaker_name",
    "speaker_name_normalized",
    "participante_id_python",
    "atribuicao_python_status",
    "char_start",
    "conteudo_char_start",
    "char_end",
    "texto_turno",
    "texto_conteudo",
    "texto_fonte_sha256",
]
TURN_UNIT_COLUMNS = [
    "texto_id",
    "unidade_id",
    "turno_id",
    "subturno_id",
    "nivel",
    "ordem_turno",
    "ordem_subturno",
    "speaker_name",
    "participante_id_python",
    "atribuicao_python_status",
    "char_start",
    "char_end",
    "texto_unidade",
    "texto_fonte_sha256",
]
EPISODE_COLUMNS = [
    "episodio_id",
    "aparte_id",
    "texto_id",
    "arena",
    "data",
    "ano",
    "participante_id",
    "participante_nome",
    "orador_participante_id",
    "orador_nome",
    "aparteante_genero",
    "orador_genero",
    "status_episodio",
    "modelo",
    "metodo",
    "texto_fonte_sha256",
    "episodio_fingerprint_v2",
    "caso_diagnostico",
    "ancora_v1_disponivel",
    "revisao_v1_disponivel",
    "char_start",
    "char_end",
    "ordem_inicio",
    "ordem_fim",
    "n_falas_participante",
    "n_backchannels",
    "n_respostas_orador",
    "n_turnos_contexto",
    "texto_participante",
    "texto_backchannels",
    "texto_respostas",
    "texto_contexto",
    "texto_episodio_cronologico",
]
EPISODE_TURN_LINK_COLUMNS = [
    "episodio_id",
    "aparte_id",
    "texto_id",
    "unidade_id",
    "turno_id",
    "subturno_id",
    "selecao_modelo_id",
    "papel_no_episodio",
    "participante_alvo_id",
    "ordem_no_papel",
    "ordem_cronologica",
    "char_start",
    "char_end",
    "speaker_name",
    "texto_unidade",
]
CANDIDATE_RESULT_COLUMNS = [
    "aparte_id",
    "texto_id",
    "participante_id",
    "status_resultado",
    "episodios",
    "modelo",
    "metodo",
    "erro_associado",
]
SPEAKER_ASSIGNMENT_COLUMNS = [
    "texto_id",
    "turno_id",
    "participante_id",
    "status_atribuicao",
    "origem",
    "modelo",
]
EPISODE_SOURCE_COLUMNS = [
    "texto_id",
    "arena",
    "data",
    "texto_fonte",
    "texto_fonte_sha256",
    "caracteres",
    "participantes",
    "participantes_json",
    "turnos",
    "turnos_json",
    "unidades",
    "unidades_json",
    "candidatos",
    "candidatos_json",
    "turnos_ambiguos_json",
]
DIAGNOSTIC_CASES = {
    "geovania_rogerio_episodios_sobrepostos": ("geovania", "rogerio"),
    "julio_campos_aparte_multiturno_perfeito": ("julio campos",),
    "izalci_pedido_concessao_fora_aparte": ("izalci",),
}
DIAGNOSTIC_CASE_IDS = {
    "camara:2dbfcb9db21b05d4e50792d0": (
        "geovania_rogerio_episodios_sobrepostos"
    ),
    "camara:56b37524858b1b11e3eba216": (
        "geovania_rogerio_episodios_sobrepostos"
    ),
    "camara:4832ef40cc933090157a075b": (
        "julio_campos_aparte_multiturno_perfeito"
    ),
    "camara:3876d2f8cca7b70cf8a3b987": (
        "izalci_pedido_concessao_fora_aparte"
    ),
}

TURN_PATTERN_V2 = re.compile(
    r"(?mi)^[\t \u00a0]*(?P<header>(?:O|A)\s+SR(?:A|ª)?\.\s+[^\n]+?)\s+[–—]\s+"
)
TURN_PATTERN_ASCII_V2 = re.compile(
    r"(?mi)^[\t \u00a0]*(?P<header>(?:O|A)\s+SR(?:A|ª)?\.\s+[^\n]+)\s+-\s+"
)


def segment_raw_turns_v2(text: str, *, texto_id: str) -> pd.DataFrame:
    """Create deterministic speaker turns with exact source offsets."""

    source = str(text or "")
    matches = _turn_matches_v2(source)
    spans: list[tuple[int, int, str, int]] = []
    if matches and matches[0].start() > 0:
        spans.append((0, matches[0].start(), "", 0))
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(source)
        spans.append((match.start(), end, match.group("header").strip(), match.end()))
    if not matches and source.strip():
        spans.append((0, len(source), "", 0))

    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    rows: list[dict[str, Any]] = []
    for position, (start, end, header, content_start) in enumerate(spans, start=1):
        content_left, content_right = _trimmed_span(source, content_start, end)
        rows.append(
            {
                "texto_id": str(texto_id),
                "turno_id": f"T{position:06d}",
                "ordem_turno": position,
                "speaker_header": header,
                "speaker_name": speaker_name_from_header(header) if header else "",
                "speaker_name_normalized": _normalize(header and speaker_name_from_header(header)),
                "participante_id_python": None,
                "atribuicao_python_status": "nao_identificado",
                "char_start": start,
                "conteudo_char_start": content_left,
                "char_end": end,
                "texto_turno": source[start:end],
                "texto_conteudo": source[content_left:content_right],
                "texto_fonte_sha256": source_hash,
            }
        )
    return pd.DataFrame(rows, columns=RAW_TURN_COLUMNS)


def build_turn_units_v2(
    raw_turns: pd.DataFrame,
    *,
    max_chars: int = 360,
) -> pd.DataFrame:
    """Create selectable whole-turn and deterministic subturn units."""

    if max_chars < 80:
        raise ValueError("subturn_max_chars deve ser pelo menos 80")
    rows: list[dict[str, Any]] = []
    for turn in raw_turns.to_dict("records"):
        content = str(turn.get("texto_conteudo") or "")
        if not content.strip():
            continue
        base = {
            "texto_id": turn["texto_id"],
            "turno_id": turn["turno_id"],
            "ordem_turno": int(turn["ordem_turno"]),
            "speaker_name": turn.get("speaker_name"),
            "participante_id_python": turn.get("participante_id_python"),
            "atribuicao_python_status": turn.get("atribuicao_python_status"),
            "texto_fonte_sha256": turn["texto_fonte_sha256"],
        }
        start = int(turn["conteudo_char_start"])
        end = start + len(content)
        rows.append(
            {
                **base,
                "unidade_id": turn["turno_id"],
                "subturno_id": None,
                "nivel": "turno",
                "ordem_subturno": 0,
                "char_start": start,
                "char_end": end,
                "texto_unidade": content,
            }
        )
        for suborder, (local_start, local_end) in enumerate(
            _subturn_spans(content, max_chars=max_chars),
            start=1,
        ):
            subturn_id = f"{turn['turno_id']}.S{suborder:03d}"
            rows.append(
                {
                    **base,
                    "unidade_id": subturn_id,
                    "subturno_id": subturn_id,
                    "nivel": "subturno",
                    "ordem_subturno": suborder,
                    "char_start": start + local_start,
                    "char_end": start + local_end,
                    "texto_unidade": content[local_start:local_end],
                }
            )
    return pd.DataFrame(rows, columns=TURN_UNIT_COLUMNS)


def build_episode_participants_v2(
    candidates: pd.DataFrame,
    raw_turns_by_text: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build the known participant registry and deterministic speaker suggestions."""

    participant_rows: list[dict[str, Any]] = []
    updated_candidates: list[pd.DataFrame] = []
    updated_turns: dict[str, pd.DataFrame] = {}
    for text_id, group in candidates.groupby(candidates["texto_id"].astype(str), sort=True):
        identities: dict[str, dict[str, Any]] = {}
        for candidate in group.to_dict("records"):
            for role, id_field, name_field in [
                ("orador_principal", "orador_id", "orador_nome"),
                ("aparteante_candidato", "aparteante_id", "aparteante_nome"),
            ]:
                person_id = str(candidate.get(id_field) or "").strip()
                name = str(candidate.get(name_field) or "").strip()
                if not person_id and not name:
                    continue
                key = _person_key(candidate.get("arena") or candidate.get("source"), person_id, name)
                entry = identities.setdefault(
                    key,
                    {
                        "pessoa_chave": key,
                        "pessoa_id_relacional": person_id or None,
                        "nome": name,
                        "nome_normalizado": _normalize(name),
                        "origem": "base_relacional",
                        "papeis": set(),
                        "aparte_ids": set(),
                    },
                )
                entry["papeis"].add(role)
                entry["aparte_ids"].add(str(candidate["aparte_id"]))

        turns = raw_turns_by_text[str(text_id)].copy()
        sorted_identities = sorted(
            identities.values(),
            key=lambda row: (
                row["origem"] != "base_relacional",
                row["nome_normalizado"],
                row["pessoa_chave"],
            ),
        )
        key_to_participant: dict[str, str] = {}
        for position, entry in enumerate(sorted_identities, start=1):
            participant_id = f"P{position:03d}"
            key_to_participant[entry["pessoa_chave"]] = participant_id
            participant_rows.append(
                {
                    "texto_id": str(text_id),
                    "participante_id": participant_id,
                    "pessoa_chave": entry["pessoa_chave"],
                    "pessoa_id_relacional": entry["pessoa_id_relacional"],
                    "nome": entry["nome"],
                    "nome_normalizado": entry["nome_normalizado"],
                    "origem": entry["origem"],
                    "papeis_json": json.dumps(sorted(entry["papeis"]), ensure_ascii=False),
                    "aparte_ids_json": json.dumps(sorted(entry["aparte_ids"]), ensure_ascii=False),
                }
            )

        participants_for_text = [
            row for row in participant_rows if row["texto_id"] == str(text_id)
        ]
        turns = _assign_turn_speakers_python(turns, participants_for_text)
        updated_turns[str(text_id)] = turns
        enriched = group.copy()
        enriched["participante_id_v2"] = enriched.apply(
            lambda row: key_to_participant.get(
                _person_key(
                    row.get("arena") or row.get("source"),
                    str(row.get("aparteante_id") or "").strip(),
                    str(row.get("aparteante_nome") or "").strip(),
                )
            ),
            axis=1,
        )
        enriched["orador_participante_id_v2"] = enriched.apply(
            lambda row: key_to_participant.get(
                _person_key(
                    row.get("arena") or row.get("source"),
                    str(row.get("orador_id") or "").strip(),
                    str(row.get("orador_nome") or "").strip(),
                )
            ),
            axis=1,
        )
        updated_candidates.append(enriched)
    participants = pd.DataFrame(participant_rows, columns=PARTICIPANT_COLUMNS)
    enriched_candidates = (
        pd.concat(updated_candidates, ignore_index=True, sort=False)
        if updated_candidates
        else candidates.copy()
    )
    return participants, enriched_candidates, updated_turns


def build_episode_sources_v2(
    candidates: pd.DataFrame,
    speeches: pd.DataFrame,
    *,
    legacy_interactions: pd.DataFrame | None = None,
    legacy_review: pd.DataFrame | None = None,
    subturn_max_chars: int = 360,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Build all deterministic v2 inputs, including read-only v1 anchors."""

    eligible = candidates.loc[
        candidates["ponte_status"].isin(["exato", "provavel_unico"])
        & candidates["texto_id"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    speech_frame = speeches.loc[
        speeches["texto_id"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if speech_frame["texto_id"].astype(str).duplicated().any():
        raise ValueError("texto_id duplicado no snapshot usado para episodios v2")
    speech_index = speech_frame.set_index(
        speech_frame["texto_id"].astype(str),
        drop=False,
    ).to_dict("index")
    raw_turns_by_text: dict[str, pd.DataFrame] = {}
    source_text_by_id: dict[str, str] = {}
    retained_text_ids: list[str] = []
    for text_id in sorted(eligible["texto_id"].astype(str).unique()):
        speech = speech_index.get(text_id)
        if speech is None:
            continue
        source_text = str(
            speech.get("texto_analitico")
            or speech.get("texto")
            or ""
        )
        if not source_text.strip():
            continue
        source_text_by_id[text_id] = source_text
        raw_turns_by_text[text_id] = segment_raw_turns_v2(
            source_text,
            texto_id=text_id,
        )
        retained_text_ids.append(text_id)
    eligible = eligible.loc[
        eligible["texto_id"].astype(str).isin(retained_text_ids)
    ].copy()
    participants, eligible, raw_turns_by_text = build_episode_participants_v2(
        eligible,
        raw_turns_by_text,
    )
    raw_turn_frames = [
        raw_turns_by_text[text_id] for text_id in sorted(raw_turns_by_text)
    ]
    raw_turns = (
        pd.concat(raw_turn_frames, ignore_index=True, sort=False)
        if raw_turn_frames
        else pd.DataFrame(columns=RAW_TURN_COLUMNS)
    )
    unit_frames = [
        build_turn_units_v2(
            raw_turns_by_text[text_id],
            max_chars=subturn_max_chars,
        )
        for text_id in sorted(raw_turns_by_text)
    ]
    units = (
        pd.concat(unit_frames, ignore_index=True, sort=False)
        if unit_frames
        else pd.DataFrame(columns=TURN_UNIT_COLUMNS)
    )

    legacy_index = _unique_index(
        legacy_interactions,
        "aparte_id",
        label="interacoes_segmentadas_ia.parquet",
    )
    reviewed_ids = _reviewed_v1_ids(legacy_review)
    anchor_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    enriched_candidates: list[pd.DataFrame] = []
    for text_id, group in eligible.groupby(eligible["texto_id"].astype(str), sort=True):
        source_text = source_text_by_id[str(text_id)]
        text_participants = participants.loc[
            participants["texto_id"].astype(str).eq(str(text_id))
        ].copy()
        text_turns = raw_turns.loc[
            raw_turns["texto_id"].astype(str).eq(str(text_id))
        ].copy()
        text_units = units.loc[
            units["texto_id"].astype(str).eq(str(text_id))
        ].copy()
        diagnostic_case = _diagnostic_case_for_group(group)
        candidate_records: list[dict[str, Any]] = []
        group = group.copy()
        group["caso_diagnostico"] = diagnostic_case or ""
        group["revisao_v1_disponivel"] = group["aparte_id"].astype(str).isin(
            reviewed_ids
        )
        group["ancora_v1_disponivel"] = group["aparte_id"].astype(str).isin(
            legacy_index
        )
        for candidate in group.sort_values("aparte_id", kind="stable").to_dict("records"):
            apart_id = str(candidate["aparte_id"])
            legacy = legacy_index.get(apart_id)
            apart_anchor_ids = _legacy_anchor_unit_ids(
                legacy,
                text_units,
                prefix="aparte",
            )
            response_anchor_ids = _legacy_anchor_unit_ids(
                legacy,
                text_units,
                prefix="resposta",
            )
            anchor_rows.append(
                {
                    "aparte_id": apart_id,
                    "texto_id": str(text_id),
                    "segmentacao_status_v1": (
                        legacy.get("segmentacao_status")
                        if legacy is not None
                        else None
                    ),
                    "unidades_aparte_v1_json": json.dumps(
                        apart_anchor_ids,
                        ensure_ascii=False,
                    ),
                    "unidades_resposta_v1_json": json.dumps(
                        response_anchor_ids,
                        ensure_ascii=False,
                    ),
                    "revisao_v1_disponivel": apart_id in reviewed_ids,
                    "uso": "ancora_diagnostica_nao_gold",
                }
            )
            record = {
                "aparte_id": apart_id,
                "participante_id": candidate.get("participante_id_v2"),
                "participante_nome": candidate.get("aparteante_nome"),
                "orador_participante_id": candidate.get(
                    "orador_participante_id_v2"
                ),
                "orador_nome": candidate.get("orador_nome"),
                "arena": candidate.get("arena"),
                "data": _json_scalar(candidate.get("data")),
                "ancora_aparte_unidade_ids": apart_anchor_ids,
                "ancora_resposta_unidade_ids": response_anchor_ids,
                "ancora_v1_status": (
                    legacy.get("segmentacao_status")
                    if legacy is not None
                    else None
                ),
                "revisao_v1_disponivel": apart_id in reviewed_ids,
                "caso_diagnostico": diagnostic_case,
            }
            candidate_records.append(record)
            if diagnostic_case:
                diagnostics.append(
                    {
                        "caso_diagnostico": diagnostic_case,
                        "texto_id": str(text_id),
                        "aparte_id": apart_id,
                        "participante_nome": candidate.get("aparteante_nome"),
                        "orador_nome": candidate.get("orador_nome"),
                        "expectativa": _diagnostic_expectation(diagnostic_case),
                        "ancora_v1_disponivel": legacy is not None,
                        "revisao_v1_disponivel": apart_id in reviewed_ids,
                    }
                )
        enriched_candidates.append(group)
        participant_records = text_participants[
            [
                "participante_id",
                "nome",
                "origem",
                "papeis_json",
                "aparte_ids_json",
            ]
        ].to_dict("records")
        turn_records = text_turns[
            [
                "turno_id",
                "ordem_turno",
                "speaker_name",
                "participante_id_python",
                "atribuicao_python_status",
                "conteudo_char_start",
                "char_end",
            ]
        ].rename(columns={"conteudo_char_start": "char_start"}).to_dict("records")
        unit_records = text_units[
            [
                "unidade_id",
                "turno_id",
                "nivel",
                "ordem_turno",
                "ordem_subturno",
                "char_start",
                "char_end",
            ]
        ].to_dict("records")
        ambiguous_turns = text_turns.loc[
            text_turns["atribuicao_python_status"].isin(
                ["ambiguo", "nao_identificado"]
            ),
            "turno_id",
        ].astype(str).tolist()
        source_rows.append(
            {
                "texto_id": str(text_id),
                "arena": group["arena"].iloc[0],
                "data": _json_scalar(group["data"].iloc[0]),
                "texto_fonte": source_text,
                "texto_fonte_sha256": hashlib.sha256(
                    source_text.encode("utf-8")
                ).hexdigest(),
                "caracteres": len(source_text),
                "participantes": len(participant_records),
                "participantes_json": json.dumps(
                    participant_records,
                    ensure_ascii=False,
                ),
                "turnos": len(turn_records),
                "turnos_json": json.dumps(turn_records, ensure_ascii=False),
                "unidades": len(unit_records),
                "unidades_json": json.dumps(unit_records, ensure_ascii=False),
                "candidatos": len(candidate_records),
                "candidatos_json": json.dumps(
                    candidate_records,
                    ensure_ascii=False,
                ),
                "turnos_ambiguos_json": json.dumps(
                    ambiguous_turns,
                    ensure_ascii=False,
                ),
            }
        )
    enriched = (
        pd.concat(enriched_candidates, ignore_index=True, sort=False)
        if enriched_candidates
        else eligible
    )
    anchors = pd.DataFrame(
        anchor_rows,
        columns=[
            "aparte_id",
            "texto_id",
            "segmentacao_status_v1",
            "unidades_aparte_v1_json",
            "unidades_resposta_v1_json",
            "revisao_v1_disponivel",
            "uso",
        ],
    )
    diagnostic_frame = pd.DataFrame(
        diagnostics,
        columns=[
            "caso_diagnostico",
            "texto_id",
            "aparte_id",
            "participante_nome",
            "orador_nome",
            "expectativa",
            "ancora_v1_disponivel",
            "revisao_v1_disponivel",
        ],
    )
    sources = pd.DataFrame(source_rows, columns=EPISODE_SOURCE_COLUMNS)
    return enriched, participants, raw_turns, units, sources, anchors, diagnostic_frame


def prepare_episode_analysis_v2(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Prepare a parallel v2 pipeline without mutating any v1 artifact."""

    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    stage_root = root / "03_apartes"
    interjections_path = resolve_input_paths(config, data_root)["interjections"]
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    if not interjections_path.exists():
        raise FileNotFoundError(interjections_path)
    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)
    raw_interjections = pd.read_parquet(interjections_path)
    snapshot = pd.read_parquet(snapshot_path)
    interjections, cut_audit = filter_interjections_by_date(
        raw_interjections,
        date_start=config.date_start,
        date_end=config.date_end,
    )
    dyads, tests = analyze_interjections_by_arena_year(interjections)
    camara_interjections = interjections.loc[
        interjections["source"].eq("camara")
    ]
    senate_interjections = interjections.loc[
        interjections["source"].eq("senado")
    ]
    camara_speeches = snapshot.loc[snapshot["arena"].eq("camara")]
    senate_speeches = snapshot.loc[snapshot["arena"].eq("senado")]
    camara_bridge = build_camara_speech_bridge(
        camara_interjections,
        camara_speeches,
    )
    senate_bridge = build_senate_speech_bridge(
        senate_interjections,
        senate_speeches,
    )
    bridges = pd.concat(
        [camara_bridge, senate_bridge],
        ignore_index=True,
        sort=False,
    )
    candidates = build_segmentation_candidates(interjections, bridges)
    legacy_interactions_path = stage_root / "interacoes_segmentadas_ia.parquet"
    legacy_review_path = stage_root / "revisao_segmentacao_ia.csv"
    legacy_interactions = (
        pd.read_parquet(legacy_interactions_path)
        if legacy_interactions_path.exists()
        else pd.DataFrame()
    )
    legacy_review = (
        pd.read_csv(legacy_review_path, keep_default_na=False)
        if legacy_review_path.exists()
        else pd.DataFrame()
    )
    episode_config = config.raw["interjection_episode_linking_v2"]
    (
        candidates_v2,
        participants,
        raw_turns,
        units,
        sources,
        anchors,
        diagnostics,
    ) = build_episode_sources_v2(
        candidates,
        snapshot.loc[snapshot["arena"].isin(["camara", "senado"])],
        legacy_interactions=legacy_interactions,
        legacy_review=legacy_review,
        subturn_max_chars=int(episode_config["subturn_max_chars"]),
    )
    source_text_ids = set(sources["texto_id"].astype(str))
    candidates_v2["elegivel_episodios_v2"] = (
        candidates_v2["ponte_status"].isin(["exato", "provavel_unico"])
        & candidates_v2["texto_id"].fillna("").astype(str).isin(source_text_ids)
    )
    universe = (
        candidates_v2.groupby(
            ["arena", "ponte_status", "elegivel_episodios_v2"],
            dropna=False,
        )
        .size()
        .rename("apartes")
        .reset_index()
    )
    bridge_v2_quality = bridge_quality(camara_bridge)
    bridge_v2_quality = {
        **bridge_v2_quality,
        "denominators_authorized": denominators_authorized(bridge_v2_quality),
    }
    outputs: list[dict[str, Any]] = []
    frames_and_paths = [
        (cut_audit, stage_root / "recorte_apartes_v2.csv"),
        (dyads, stage_root / "diades_genero_v2.csv"),
        (tests, stage_root / "testes_associacao_v2.csv"),
        (camara_bridge, stage_root / "ponte_camara_v2.csv"),
        (senate_bridge, stage_root / "ponte_senado_v2.csv"),
        (candidates_v2, stage_root / "candidatos_episodios_v2.parquet"),
        (universe, stage_root / "universo_episodios_v2.csv"),
        (participants, stage_root / "participantes_interacao_v2.parquet"),
        (raw_turns, stage_root / "turnos_brutos_v2.parquet"),
        (units, stage_root / "unidades_turno_v2.parquet"),
        (sources, stage_root / "fontes_episodios_v2.parquet"),
        (anchors, stage_root / "ancoras_segmentacao_v1_v2.parquet"),
        (diagnostics, stage_root / "diagnosticos_episodios_v2.csv"),
    ]
    for frame, path in frames_and_paths:
        written = write_dataframe_atomic(frame, path)
        outputs.append(artifact_record(written, rows=len(frame)))
    quality_path = write_json_atomic(
        stage_root / "episodios_qualidade_v2.json",
        {
            "pipeline_version": EPISODE_PIPELINE_VERSION,
            "method": EPISODE_METHOD,
            "awaiting_batch": True,
            "qualitative_authorized_v2": False,
            "bridge": bridge_v2_quality,
            "candidate_interjections": len(candidates_v2),
            "eligible_interjections": int(
                candidates_v2["elegivel_episodios_v2"].sum()
            ),
            "source_transcripts": len(sources),
            "participants": len(participants),
            "raw_turns": len(raw_turns),
            "turn_units": len(units),
            "diagnostic_rows": len(diagnostics),
        },
    )
    outputs.append(artifact_record(quality_path))
    inputs = [
        artifact_record(interjections_path, rows=len(raw_interjections)),
        artifact_record(snapshot_path, rows=len(snapshot)),
    ]
    for legacy_path, legacy_frame in [
        (legacy_interactions_path, legacy_interactions),
        (legacy_review_path, legacy_review),
    ]:
        if legacy_path.exists():
            inputs.append(artifact_record(legacy_path, rows=len(legacy_frame)))
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="03_apartes_episodios_v2_preparacao",
        inputs=inputs,
        outputs=outputs,
        counts={
            "pipeline_version": EPISODE_PIPELINE_VERSION,
            "interjections_input": len(raw_interjections),
            "interjections_in_date_cut": len(interjections),
            "candidate_interjections": len(candidates_v2),
            "eligible_interjections": int(
                candidates_v2["elegivel_episodios_v2"].sum()
            ),
            "source_transcripts": len(sources),
            "participants": len(participants),
            "raw_turns": len(raw_turns),
            "turn_units": len(units),
            "legacy_anchors": len(anchors),
            "legacy_reviewed_candidates": int(
                anchors["revisao_v1_disponivel"].sum()
            ),
            "diagnostic_rows": len(diagnostics),
        },
    )
    manifest_path = write_json_atomic(
        stage_root / "manifest_preparacao_episodios_v2.json",
        manifest,
    )
    return {**manifest, "manifest_path": str(manifest_path)}


def episode_output_schema_v2() -> dict[str, Any]:
    unit_id = {
        "type": "string",
        "pattern": r"^T[0-9]{6}(?:\.S[0-9]{3})?$",
    }
    unit_list = {
        "type": "array",
        "items": unit_id,
        "uniqueItems": True,
    }
    episode = {
        "type": "object",
        "properties": {
            "falas_participante_ids": unit_list,
            "backchannels_ids": unit_list,
            "respostas_orador_ids": unit_list,
            "contexto_interveniente_ids": unit_list,
        },
        "required": [
            "falas_participante_ids",
            "backchannels_ids",
            "respostas_orador_ids",
            "contexto_interveniente_ids",
        ],
        "additionalProperties": False,
    }
    candidate = {
        "type": "object",
        "properties": {
            "aparte_id": {"type": "string"},
            "participante_id": {"type": "string", "pattern": r"^P[0-9]{3}$"},
            "status": {
                "type": "string",
                "enum": ["localizado", "nao_localizado", "incerto"],
            },
            "episodios": {"type": "array", "items": episode},
        },
        "required": [
            "aparte_id",
            "participante_id",
            "status",
            "episodios",
        ],
        "additionalProperties": False,
    }
    assignment = {
        "type": "object",
        "properties": {
            "turno_id": {
                "type": "string",
                "pattern": r"^T[0-9]{6}$",
            },
            "participante_id": {
                "type": ["string", "null"],
                "pattern": r"^P[0-9]{3}$",
            },
        },
        "required": ["turno_id", "participante_id"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "texto_id": {"type": "string"},
            "atribuicoes_falante": {
                "type": "array",
                "items": assignment,
            },
            "candidatos": {
                "type": "array",
                "items": candidate,
            },
        },
        "required": [
            "texto_id",
            "atribuicoes_falante",
            "candidatos",
        ],
        "additionalProperties": False,
    }


def make_episode_batch_request_v2(
    source: Mapping[str, Any],
    *,
    config: AnalysisConfig,
    model: str | None = None,
) -> dict[str, Any]:
    text_id = str(source["texto_id"])
    source_text = str(source["texto_fonte"])
    participants = json.loads(str(source["participantes_json"]))
    turns = json.loads(str(source["turnos_json"]))
    units = json.loads(str(source["unidades_json"]))
    candidates = json.loads(str(source["candidatos_json"]))
    ambiguous_turns = json.loads(str(source["turnos_ambiguos_json"]))
    units_by_turn: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        if unit["nivel"] == "subturno":
            units_by_turn.setdefault(str(unit["turno_id"]), []).append(unit)
    rendered: list[str] = []
    for turn in turns:
        turn_id = str(turn["turno_id"])
        rendered.append(
            (
                f"⟦{turn_id}⟧ falante={json.dumps(turn.get('speaker_name') or '', ensure_ascii=False)} "
                f"participante_python={turn.get('participante_id_python') or 'NA'} "
                f"status_python={turn.get('atribuicao_python_status')}"
            )
        )
        for unit in sorted(
            units_by_turn.get(turn_id, []),
            key=lambda row: int(row["ordem_subturno"]),
        ):
            start, end = int(unit["char_start"]), int(unit["char_end"])
            rendered.append(
                f"  ⟦{unit['unidade_id']}⟧ {source_text[start:end]}"
            )
    episode_config = config.raw["interjection_episode_linking_v2"]
    roster_hash = hashlib.sha256(
        json.dumps(
            participants,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    turns_hash = hashlib.sha256(
        json.dumps(
            units,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    custom_payload = "|".join(
        [
            EPISODE_PIPELINE_VERSION,
            text_id,
            str(source["texto_fonte_sha256"]),
            roster_hash,
            turns_hash,
            str(episode_config["prompt_version"]),
        ]
    )
    custom_id = "apartes-ep-v2-" + hashlib.sha256(
        custom_payload.encode("utf-8")
    ).hexdigest()[:20]
    prompt = f"""Associe turnos de uma transcrição parlamentar a episódios de interação multiturno.

Python já criou os turnos, subturnos, participantes conhecidos, candidatos e offsets. Você não deve
segmentar texto livre nem inventar participantes. Resolva somente ambiguidades de falante e associe IDs.

Regras obrigatórias:
- devolva cada `aparte_id` candidato exatamente uma vez;
- `participante_id` deve ser o participante relacional informado para o candidato;
- um candidato pode ter mais de um episódio e episódios de candidatos diferentes podem se sobrepor;
- falas curtas como “Perfeito” podem ser `backchannels_ids` e permanecer no mesmo episódio multiturno;
- pedido e concessão de aparte são contexto/procedimento, não fala substantiva do participante;
- respostas do orador devem ser ligadas ao candidato a quem se dirigem;
- quando um turno bruto responde a pessoas diferentes, selecione os subturnos correspondentes;
- `contexto_interveniente_ids` inclui intervenções necessárias para compreender o episódio;
- selecione o ID do turno inteiro somente quando todo o conteúdo pertencer ao mesmo papel; caso contrário,
  selecione subturnos;
- as âncoras v1 são dicas diagnósticas incompletas, nunca verdade obrigatória;
- use `nao_localizado` ou `incerto` com `episodios=[]`;
- não devolva, resuma ou copie textos. A saída contém apenas IDs e status.

texto_id: {text_id}
participantes: {json.dumps(participants, ensure_ascii=False, separators=(',', ':'))}
candidatos: {json.dumps(candidates, ensure_ascii=False, separators=(',', ':'))}
turnos_com_falante_ambiguo: {json.dumps(ambiguous_turns, ensure_ascii=False, separators=(',', ':'))}

TURNOS E SUBTURNOS:
{chr(10).join(rendered)}
"""
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": (
                model
                or config.raw["openai"]["interjection_segmentation_model"]
            ),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "episodios_interacao_v2",
                    "strict": True,
                    "schema": episode_output_schema_v2(),
                }
            },
            "metadata": {
                "texto_id": text_id,
                "pipeline_version": EPISODE_PIPELINE_VERSION,
                "prompt_version": episode_config["prompt_version"],
                "texto_fonte_sha256": str(source["texto_fonte_sha256"]),
                "roster_sha256": roster_hash,
                "turnos_sha256": turns_hash,
            },
        },
    }


def write_episode_batch_jsonl_v2(
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
        request_builder=lambda source: make_episode_batch_request_v2(
            source,
            config=config,
            model=model,
        ),
        max_requests=max_requests,
        max_bytes=max_bytes,
    )


def parse_episode_batch_output_v2(
    lines: Iterable[str],
    *,
    request_index: Mapping[str, str],
    sources: pd.DataFrame,
    candidates: pd.DataFrame,
    participants: pd.DataFrame,
    raw_turns: pd.DataFrame,
    units: pd.DataFrame,
    model: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_index = sources.set_index(
        sources["texto_id"].astype(str),
        drop=False,
    ).to_dict("index")
    candidate_index = candidates.set_index(
        candidates["aparte_id"].astype(str),
        drop=False,
    ).to_dict("index")
    episode_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    assignment_rows: list[dict[str, Any]] = []
    candidate_result_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_custom_ids: set[str] = set()
    parsed_apart_ids: set[str] = set()
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
                    "texto_id": None,
                    "aparte_id": None,
                    "error": str(exc),
                }
            )
            continue
        custom_id = str(record.get("custom_id") or "")
        text_id = request_index.get(custom_id)
        if custom_id in seen_custom_ids:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": "custom_id duplicado na saida v2",
                }
            )
            continue
        seen_custom_ids.add(custom_id)
        if text_id is None or str(text_id) not in source_index:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": "custom_id desconhecido na saida v2",
                }
            )
            continue
        response = record.get("response") or {}
        if response.get("status_code") != 200:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": json.dumps(
                        record.get("error") or response,
                        ensure_ascii=False,
                    ),
                }
            )
            continue
        try:
            payload = json.loads(
                _response_output_text(response.get("body") or {})
            )
            (
                parsed_episodes,
                parsed_links,
                parsed_assignments,
                parsed_candidates,
            ) = _reconstruct_episode_payload_v2(
                payload,
                source=source_index[str(text_id)],
                candidates=candidate_index,
                participants=participants.loc[
                    participants["texto_id"].astype(str).eq(str(text_id))
                ],
                raw_turns=raw_turns.loc[
                    raw_turns["texto_id"].astype(str).eq(str(text_id))
                ],
                units=units.loc[
                    units["texto_id"].astype(str).eq(str(text_id))
                ],
                model=model,
            )
            parsed_ids = {
                str(row["aparte_id"])
                for row in parsed_candidates
            }
            if parsed_apart_ids & parsed_ids:
                raise ValueError("aparte_id repetido entre respostas v2")
            parsed_apart_ids.update(parsed_ids)
            episode_rows.extend(parsed_episodes)
            link_rows.extend(parsed_links)
            assignment_rows.extend(parsed_assignments)
            candidate_result_rows.extend(parsed_candidates)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "line": line_number,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": str(exc),
                }
            )
    for custom_id, text_id in request_index.items():
        if custom_id not in seen_custom_ids:
            errors.append(
                {
                    "line": None,
                    "custom_id": custom_id,
                    "texto_id": text_id,
                    "aparte_id": None,
                    "error": "request v2 sem linha correspondente na saida do Batch",
                }
            )
    source_text_ids = set(sources["texto_id"].astype(str))
    for apart_id, candidate in candidate_index.items():
        if apart_id in parsed_apart_ids:
            continue
        linked = candidate.get("ponte_status") in {
            "exato",
            "provavel_unico",
        }
        text_id = str(candidate.get("texto_id") or "")
        status = (
            "ia_sem_resultado"
            if linked and text_id in source_text_ids
            else "sem_texto_validado"
        )
        candidate_result_rows.append(
            {
                "aparte_id": apart_id,
                "texto_id": text_id or None,
                "participante_id": candidate.get("participante_id_v2"),
                "status_resultado": status,
                "episodios": 0,
                "modelo": model,
                "metodo": EPISODE_METHOD,
                "erro_associado": True,
            }
        )
    episodes = pd.DataFrame(episode_rows, columns=EPISODE_COLUMNS)
    if not episodes.empty:
        episodes = episodes.sort_values(
            ["texto_id", "ordem_inicio", "episodio_id"],
            kind="stable",
        ).reset_index(drop=True)
    links = pd.DataFrame(link_rows, columns=EPISODE_TURN_LINK_COLUMNS)
    if not links.empty:
        links = links.sort_values(
            ["texto_id", "episodio_id", "ordem_cronologica"],
            kind="stable",
        ).reset_index(drop=True)
    assignments = pd.DataFrame(
        assignment_rows,
        columns=SPEAKER_ASSIGNMENT_COLUMNS,
    )
    candidate_results = pd.DataFrame(
        candidate_result_rows,
        columns=CANDIDATE_RESULT_COLUMNS,
    )
    errors_frame = pd.DataFrame(errors, columns=EPISODE_ERROR_COLUMNS)
    return episodes, links, assignments, candidate_results, errors_frame


def _reconstruct_episode_payload_v2(
    payload: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    participants: pd.DataFrame,
    raw_turns: pd.DataFrame,
    units: pd.DataFrame,
    model: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    text_id = str(source["texto_id"])
    if str(payload.get("texto_id")) != text_id:
        raise ValueError(f"texto_id divergente na v2: esperado {text_id}")
    expected_records = json.loads(str(source["candidatos_json"]))
    expected_by_id = {
        str(record["aparte_id"]): record
        for record in expected_records
    }
    returned_candidates = payload.get("candidatos")
    if not isinstance(returned_candidates, list):
        raise ValueError("candidatos deve ser uma lista")
    returned_ids = [
        str(record.get("aparte_id"))
        for record in returned_candidates
    ]
    if (
        len(returned_ids) != len(set(returned_ids))
        or set(returned_ids) != set(expected_by_id)
    ):
        raise ValueError(
            "aparte_id ausente, inesperado ou duplicado na resposta v2"
        )
    participant_ids = set(participants["participante_id"].astype(str))
    turn_index = raw_turns.set_index("turno_id", drop=False).to_dict("index")
    unit_index = units.set_index("unidade_id", drop=False).to_dict("index")
    ambiguous_turns = set(
        raw_turns.loc[
            raw_turns["atribuicao_python_status"].isin(
                ["ambiguo", "nao_identificado"]
            ),
            "turno_id",
        ].astype(str)
    )
    assignments_payload = payload.get("atribuicoes_falante")
    if not isinstance(assignments_payload, list):
        raise ValueError("atribuicoes_falante deve ser uma lista")
    assignment_rows: list[dict[str, Any]] = []
    seen_assignment_turns: set[str] = set()
    resolved_speakers: dict[str, str] = {}
    for turn_id, turn in turn_index.items():
        python_participant = turn.get("participante_id_python")
        if (
            python_participant is not None
            and not pd.isna(python_participant)
            and str(python_participant).strip()
        ):
            resolved_speakers[str(turn_id)] = str(python_participant)
    for assignment in assignments_payload:
        turn_id = str(assignment.get("turno_id") or "")
        participant_id = assignment.get("participante_id")
        if turn_id in seen_assignment_turns:
            raise ValueError(f"atribuicao de falante duplicada: {turn_id}")
        seen_assignment_turns.add(turn_id)
        if turn_id not in turn_index:
            raise ValueError(f"turno inexistente na atribuicao: {turn_id}")
        if turn_id not in ambiguous_turns:
            raise ValueError(
                f"IA tentou substituir atribuicao Python inequivoca: {turn_id}"
            )
        if participant_id is not None and str(participant_id) not in participant_ids:
            raise ValueError(
                f"participante inexistente na atribuicao: {participant_id}"
            )
        assignment_rows.append(
            {
                "texto_id": text_id,
                "turno_id": turn_id,
                "participante_id": (
                    str(participant_id)
                    if participant_id is not None
                    else None
                ),
                "status_atribuicao": (
                    "resolvido_ia"
                    if participant_id is not None
                    else "nao_resolvido"
                ),
                "origem": "ia_apenas_ambiguidade",
                "modelo": model,
            }
        )
        if participant_id is not None:
            resolved_speakers[turn_id] = str(participant_id)
    episode_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    source_text = str(source["texto_fonte"])
    seen_episode_ids: set[str] = set()
    for returned in returned_candidates:
        apart_id = str(returned["aparte_id"])
        expected = expected_by_id[apart_id]
        candidate = candidates.get(apart_id)
        if candidate is None or str(candidate.get("texto_id")) != text_id:
            raise ValueError(f"candidato v2 incompatível: {apart_id}")
        participant_id = str(returned.get("participante_id") or "")
        if participant_id != str(expected.get("participante_id") or ""):
            raise ValueError(
                f"participante_id divergente para {apart_id}: {participant_id}"
            )
        status = str(returned.get("status") or "")
        if status not in {"localizado", "nao_localizado", "incerto"}:
            raise ValueError(f"status v2 invalido: {status}")
        episode_payloads = returned.get("episodios")
        if not isinstance(episode_payloads, list):
            raise ValueError("episodios deve ser uma lista")
        if status == "localizado" and not episode_payloads:
            raise ValueError(f"candidato localizado sem episodio: {apart_id}")
        if status != "localizado" and episode_payloads:
            raise ValueError(
                f"{status} exige episodios vazios: {apart_id}"
            )
        created_for_candidate = 0
        for episode_number, episode_payload in enumerate(
            episode_payloads,
            start=1,
        ):
            role_inputs = {
                "fala_participante": episode_payload.get(
                    "falas_participante_ids"
                ),
                "backchannel": episode_payload.get(
                    "backchannels_ids"
                ),
                "resposta_orador": episode_payload.get(
                    "respostas_orador_ids"
                ),
                "contexto_interveniente": episode_payload.get(
                    "contexto_interveniente_ids"
                ),
            }
            if any(not isinstance(value, list) for value in role_inputs.values()):
                raise ValueError(
                    f"listas de unidades invalidas no episodio: {apart_id}"
                )
            expanded_by_role = {
                role: _expand_selected_unit_ids(
                    selected,
                    unit_index=unit_index,
                    text_id=text_id,
                )
                for role, selected in role_inputs.items()
            }
            expected_speakers = {
                "fala_participante": participant_id,
                "backchannel": str(
                    expected.get("orador_participante_id") or ""
                ),
                "resposta_orador": str(
                    expected.get("orador_participante_id") or ""
                ),
            }
            for role, expected_speaker in expected_speakers.items():
                if not expected_speaker:
                    raise ValueError(
                        f"participante relacional ausente para o papel {role}: "
                        f"{apart_id}"
                    )
                for unit_id, _ in expanded_by_role[role]:
                    turn_id = str(unit_index[unit_id]["turno_id"])
                    if resolved_speakers.get(turn_id) != expected_speaker:
                        raise ValueError(
                            f"falante incompatível em {role}: {apart_id}/"
                            f"{unit_id}"
                        )
            participant_units = [
                *expanded_by_role["fala_participante"],
            ]
            if not participant_units:
                raise ValueError(
                    f"episodio sem fala do participante: {apart_id}"
                )
            all_expanded = [
                unit_id
                for role_units in expanded_by_role.values()
                for unit_id, _ in role_units
            ]
            if len(all_expanded) != len(set(all_expanded)):
                raise ValueError(
                    f"unidade com papeis conflitantes no episodio: {apart_id}"
                )
            canonical_roles = {
                role: sorted(
                    [unit_id for unit_id, _ in role_units],
                    key=lambda unit_id: (
                        int(unit_index[unit_id]["char_start"]),
                        int(unit_index[unit_id]["char_end"]),
                        unit_id,
                    ),
                )
                for role, role_units in expanded_by_role.items()
            }
            fingerprint_payload = {
                "pipeline_version": EPISODE_PIPELINE_VERSION,
                "texto_id": text_id,
                "texto_fonte_sha256": source["texto_fonte_sha256"],
                "aparte_id": apart_id,
                "participante_id": participant_id,
                "roles": canonical_roles,
            }
            fingerprint = hashlib.sha256(
                json.dumps(
                    fingerprint_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            episode_id = "epv2-" + hashlib.sha256(
                f"{apart_id}|{fingerprint}".encode("utf-8")
            ).hexdigest()[:24]
            if episode_id in seen_episode_ids:
                raise ValueError(
                    f"episodio duplicado para o mesmo candidato: {apart_id}"
                )
            seen_episode_ids.add(episode_id)
            episode_links: list[dict[str, Any]] = []
            for role, role_units in expanded_by_role.items():
                sorted_role_units = sorted(
                    role_units,
                    key=lambda pair: (
                        int(unit_index[pair[0]]["char_start"]),
                        int(unit_index[pair[0]]["char_end"]),
                        pair[0],
                    ),
                )
                for role_order, (unit_id, selected_id) in enumerate(
                    sorted_role_units,
                    start=1,
                ):
                    unit = unit_index[unit_id]
                    episode_links.append(
                        {
                            "episodio_id": episode_id,
                            "aparte_id": apart_id,
                            "texto_id": text_id,
                            "unidade_id": unit_id,
                            "turno_id": unit["turno_id"],
                            "subturno_id": unit.get("subturno_id"),
                            "selecao_modelo_id": selected_id,
                            "papel_no_episodio": role,
                            "participante_alvo_id": (
                                participant_id
                                if role in {"backchannel", "resposta_orador"}
                                else None
                            ),
                            "ordem_no_papel": role_order,
                            "ordem_cronologica": None,
                            "char_start": int(unit["char_start"]),
                            "char_end": int(unit["char_end"]),
                            "speaker_name": unit.get("speaker_name"),
                            "texto_unidade": source_text[
                                int(unit["char_start"]) : int(unit["char_end"])
                            ],
                        }
                    )
            episode_links.sort(
                key=lambda row: (
                    row["char_start"],
                    row["char_end"],
                    row["papel_no_episodio"],
                )
            )
            for chronological_order, link in enumerate(episode_links, start=1):
                link["ordem_cronologica"] = chronological_order
            link_rows.extend(episode_links)
            role_text = {
                role: _join_role_text(
                    episode_links,
                    role,
                )
                for role in [
                    "fala_participante",
                    "backchannel",
                    "resposta_orador",
                    "contexto_interveniente",
                ]
            }
            episode_rows.append(
                {
                    "episodio_id": episode_id,
                    "aparte_id": apart_id,
                    "texto_id": text_id,
                    "arena": candidate.get("arena") or candidate.get("source"),
                    "data": candidate.get("data"),
                    "ano": _candidate_year(candidate),
                    "participante_id": participant_id,
                    "participante_nome": candidate.get("aparteante_nome"),
                    "orador_participante_id": candidate.get(
                        "orador_participante_id_v2"
                    ),
                    "orador_nome": candidate.get("orador_nome"),
                    "aparteante_genero": candidate.get("aparteante_genero"),
                    "orador_genero": candidate.get("orador_genero"),
                    "status_episodio": "localizado",
                    "modelo": model,
                    "metodo": EPISODE_METHOD,
                    "texto_fonte_sha256": source["texto_fonte_sha256"],
                    "episodio_fingerprint_v2": fingerprint,
                    "caso_diagnostico": candidate.get("caso_diagnostico") or "",
                    "ancora_v1_disponivel": bool(
                        candidate.get("ancora_v1_disponivel")
                    ),
                    "revisao_v1_disponivel": bool(
                        candidate.get("revisao_v1_disponivel")
                    ),
                    "char_start": min(
                        link["char_start"] for link in episode_links
                    ),
                    "char_end": max(
                        link["char_end"] for link in episode_links
                    ),
                    "ordem_inicio": min(
                        int(unit_index[link["unidade_id"]]["ordem_turno"])
                        for link in episode_links
                    ),
                    "ordem_fim": max(
                        int(unit_index[link["unidade_id"]]["ordem_turno"])
                        for link in episode_links
                    ),
                    "n_falas_participante": len(
                        expanded_by_role["fala_participante"]
                    ),
                    "n_backchannels": len(
                        expanded_by_role["backchannel"]
                    ),
                    "n_respostas_orador": len(
                        expanded_by_role["resposta_orador"]
                    ),
                    "n_turnos_contexto": len(
                        expanded_by_role["contexto_interveniente"]
                    ),
                    "texto_participante": role_text["fala_participante"],
                    "texto_backchannels": role_text["backchannel"],
                    "texto_respostas": role_text["resposta_orador"],
                    "texto_contexto": role_text["contexto_interveniente"],
                    "texto_episodio_cronologico": "\n".join(
                        (
                            f"[{link['papel_no_episodio']}] "
                            f"{link['texto_unidade']}"
                        )
                        for link in episode_links
                    ),
                }
            )
            created_for_candidate += 1
        candidate_rows.append(
            {
                "aparte_id": apart_id,
                "texto_id": text_id,
                "participante_id": participant_id,
                "status_resultado": status,
                "episodios": created_for_candidate,
                "modelo": model,
                "metodo": EPISODE_METHOD,
                "erro_associado": False,
            }
        )
    return episode_rows, link_rows, assignment_rows, candidate_rows


def episode_review_sample_v2(
    episodes: pd.DataFrame,
    links: pd.DataFrame,
    *,
    size: int = 30,
    seed: int = 20260713,
) -> pd.DataFrame:
    """Select a deterministic pilot, forcing diagnostic and reviewed anchors."""

    if episodes.empty:
        return pd.DataFrame()
    eligible = episodes.loc[
        episodes["status_episodio"].eq("localizado")
    ].copy()
    if eligible.empty:
        return eligible
    eligible["episodio_sobreposto"] = _episode_overlap_flags(eligible)
    eligible["periodo"] = pd.cut(
        pd.to_numeric(eligible["ano"], errors="coerce"),
        bins=[2009, 2015, 2019, 2026],
        labels=["2010-2015", "2016-2019", "2020-2026"],
    )
    link_lists = (
        links.sort_values(
            ["episodio_id", "ordem_cronologica"],
            kind="stable",
        )
        .groupby(["episodio_id", "papel_no_episodio"])["unidade_id"]
        .agg(list)
        .unstack()
    )
    for role in [
        "fala_participante",
        "backchannel",
        "resposta_orador",
        "contexto_interveniente",
    ]:
        mapping = link_lists[role].dropna().to_dict() if role in link_lists else {}
        eligible[f"{role}_ids_json"] = eligible["episodio_id"].map(
            lambda episode_id: json.dumps(
                mapping.get(episode_id, []),
                ensure_ascii=False,
            )
        )
    target = min(int(size), len(eligible))
    forced = eligible.loc[
        eligible["caso_diagnostico"].fillna("").astype(str).str.strip().ne("")
    ].sort_values(
        ["caso_diagnostico", "texto_id", "ordem_inicio", "episodio_id"],
        kind="stable",
    )
    selected_ids = list(dict.fromkeys(forced["episodio_id"].astype(str)))[:target]
    remaining_target = target - len(selected_ids)
    if remaining_target > 0:
        reviewed_anchor = eligible.loc[
            eligible["revisao_v1_disponivel"].fillna(False)
            & ~eligible["episodio_id"].astype(str).isin(selected_ids)
        ].sample(
            frac=1,
            random_state=seed,
        )
        anchor_ids = reviewed_anchor["episodio_id"].astype(str).tolist()[
            :remaining_target
        ]
        selected_ids.extend(anchor_ids)
    remaining_target = target - len(selected_ids)
    if remaining_target > 0:
        remainder = eligible.loc[
            ~eligible["episodio_id"].astype(str).isin(selected_ids)
        ].copy()
        strata = [
            "arena",
            "periodo",
            "episodio_sobreposto",
        ]
        groups = [
            group.sample(
                frac=1,
                random_state=seed + position,
            ).reset_index(drop=True)
            for position, (_, group) in enumerate(
                remainder.groupby(
                    strata,
                    dropna=False,
                    observed=True,
                    sort=True,
                )
            )
        ]
        offset = 0
        while remaining_target > 0:
            added = False
            for group in groups:
                if offset < len(group) and remaining_target > 0:
                    selected_ids.append(str(group.iloc[offset]["episodio_id"]))
                    remaining_target -= 1
                    added = True
            if not added:
                break
            offset += 1
    order = {episode_id: position for position, episode_id in enumerate(selected_ids)}
    sample = eligible.loc[
        eligible["episodio_id"].astype(str).isin(selected_ids)
    ].copy()
    sample["_sample_order"] = sample["episodio_id"].astype(str).map(order)
    sample = sample.sort_values("_sample_order", kind="stable").drop(
        columns="_sample_order"
    )
    for column in EPISODE_REVIEW_MANUAL_COLUMNS:
        sample[column] = ""
    return sample.reset_index(drop=True)


def episode_quality_v2(
    episodes: pd.DataFrame,
    review: pd.DataFrame | None = None,
    *,
    min_reviewed: int = 30,
    min_precision: float = 0.95,
    required_diagnostic_cases: Sequence[str] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pipeline_version": EPISODE_PIPELINE_VERSION,
        "episodes": len(episodes),
        "reviewed": 0,
        "review_rows_total": 0,
        "review_rows_complete": 0,
        "review_rows_invalid": 0,
        "precision_participants": None,
        "precision_completeness": None,
        "precision_responses": None,
        "precision_context": None,
        "diagnostic_cases_required": list(required_diagnostic_cases),
        "diagnostic_cases_approved": [],
        "diagnostic_gate_passed": not required_diagnostic_cases,
        "qualitative_authorized_v2": False,
    }
    if review is None or review.empty:
        return result
    required = {
        "episodio_id",
        "episodio_fingerprint_v2",
        "caso_diagnostico",
        *EPISODE_REVIEW_BOOLEAN_COLUMNS,
    }
    if missing := required.difference(review.columns):
        raise ValueError(
            f"Revisao v2 sem colunas obrigatorias: {sorted(missing)}"
        )
    episode_keys = episodes[
        [
            "episodio_id",
            "episodio_fingerprint_v2",
            "caso_diagnostico",
        ]
    ].copy()
    review_frame = review[list(required)].copy()
    for frame in [episode_keys, review_frame]:
        frame["episodio_id"] = frame["episodio_id"].astype(str)
        frame["episodio_fingerprint_v2"] = frame[
            "episodio_fingerprint_v2"
        ].astype(str)
    if review_frame.duplicated(
        ["episodio_id", "episodio_fingerprint_v2"]
    ).any():
        raise ValueError("Revisao v2 contem episodio/fingerprint duplicado")
    comparison = episode_keys.merge(
        review_frame.drop(columns="caso_diagnostico"),
        on=["episodio_id", "episodio_fingerprint_v2"],
        how="inner",
        validate="one_to_one",
    )
    parsed: dict[str, pd.Series] = {}
    invalid = pd.Series(False, index=comparison.index)
    complete = pd.Series(True, index=comparison.index)
    for column in EPISODE_REVIEW_BOOLEAN_COLUMNS:
        values, invalid_values = _optional_boolean_series(comparison[column])
        parsed[column] = values
        invalid |= invalid_values
        complete &= values.notna()
    reviewed = comparison.loc[complete]
    metrics = {
        "precision_participants": "atribuicao_participantes_correta",
        "precision_completeness": "episodio_completo",
        "precision_responses": "atribuicao_respostas_correta",
        "precision_context": "contexto_suficiente",
    }
    result.update(
        {
            "reviewed": len(reviewed),
            "review_rows_total": len(comparison),
            "review_rows_complete": len(reviewed),
            "review_rows_invalid": int(invalid.sum()),
        }
    )
    for metric, column in metrics.items():
        values = parsed[column].loc[complete].astype(bool)
        result[metric] = float(values.mean()) if len(values) else None
    approved_diagnostics: list[str] = []
    for case in required_diagnostic_cases:
        case_mask = comparison["caso_diagnostico"].astype(str).eq(str(case))
        if not case_mask.any():
            continue
        case_complete = complete & case_mask
        if not case_complete.any():
            continue
        if all(
            parsed[column].loc[case_complete].astype(bool).all()
            for column in EPISODE_REVIEW_BOOLEAN_COLUMNS
        ):
            approved_diagnostics.append(str(case))
    result["diagnostic_cases_approved"] = approved_diagnostics
    result["diagnostic_gate_passed"] = set(approved_diagnostics) == set(
        map(str, required_diagnostic_cases)
    )
    metric_values = [result[metric] for metric in metrics]
    result["qualitative_authorized_v2"] = bool(
        len(reviewed) >= int(min_reviewed)
        and int(invalid.sum()) == 0
        and all(
            value is not None and float(value) >= float(min_precision)
            for value in metric_values
        )
        and result["diagnostic_gate_passed"]
    )
    return result


def run_episode_results_v2(
    *,
    data_root: str | Path,
    run_id: str,
    batch_output_path: str | Path | Sequence[str | Path],
    request_path: str | Path | Sequence[str | Path],
    model: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Materialize normalized v2 results while preserving every v1 path."""

    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    stage_root = root / "03_apartes"
    paths = {
        "sources": stage_root / "fontes_episodios_v2.parquet",
        "candidates": stage_root / "candidatos_episodios_v2.parquet",
        "participants": stage_root / "participantes_interacao_v2.parquet",
        "turns": stage_root / "turnos_brutos_v2.parquet",
        "units": stage_root / "unidades_turno_v2.parquet",
        "diagnostics": stage_root / "diagnosticos_episodios_v2.csv",
    }
    sources = pd.read_parquet(paths["sources"])
    candidates = pd.read_parquet(paths["candidates"])
    participants = pd.read_parquet(paths["participants"])
    raw_turns = pd.read_parquet(paths["turns"])
    units = pd.read_parquet(paths["units"])
    request_paths = _coerce_paths(request_path)
    output_paths = _coerce_paths(batch_output_path)
    request_index: dict[str, str] = {}
    for line in _iter_path_lines(request_paths):
        if not line.strip():
            continue
        request = json.loads(line)
        custom_id = str(request["custom_id"])
        if custom_id in request_index:
            raise ValueError(f"custom_id v2 duplicado no JSONL: {custom_id}")
        metadata = request["body"]["metadata"]
        if metadata.get("pipeline_version") != EPISODE_PIPELINE_VERSION:
            raise ValueError("JSONL nao pertence ao pipeline de episodios v2")
        request_index[custom_id] = str(metadata["texto_id"])
    (
        episodes,
        links,
        assignments,
        candidate_results,
        errors,
    ) = parse_episode_batch_output_v2(
        _iter_path_lines(output_paths),
        request_index=request_index,
        sources=sources,
        candidates=candidates,
        participants=participants,
        raw_turns=raw_turns,
        units=units,
        model=model,
    )
    outputs: list[dict[str, Any]] = []
    frames_and_paths = [
        (episodes, stage_root / "episodios_interacao_v2.parquet"),
        (links, stage_root / "episodio_turnos_v2.parquet"),
        (assignments, stage_root / "atribuicoes_falantes_v2.parquet"),
        (
            candidate_results,
            stage_root / "resultados_candidatos_episodios_v2.parquet",
        ),
        (errors, stage_root / "episodios_erros_v2.csv"),
    ]
    for frame, path in frames_and_paths:
        written = write_dataframe_atomic(frame, path)
        outputs.append(artifact_record(written, rows=len(frame)))
    episode_config = config.raw["interjection_episode_linking_v2"]
    review = episode_review_sample_v2(
        episodes,
        links,
        size=int(episode_config["review_sample_size"]),
        seed=config.seed,
    )
    review_path = stage_root / "revisao_episodios_v2.csv"
    if not review.empty:
        review = _preserve_manual_columns(
            review,
            review_path,
            key_columns=[
                "episodio_id",
                "episodio_fingerprint_v2",
            ],
            manual_columns=EPISODE_REVIEW_MANUAL_COLUMNS,
        )
    review_path = write_dataframe_atomic(review, review_path)
    outputs.append(artifact_record(review_path, rows=len(review)))
    quality = {
        "method": EPISODE_METHOD,
        "model": model,
        "awaiting_batch": False,
        **episode_quality_v2(
            episodes,
            review,
            min_reviewed=int(episode_config["min_reviewed"]),
            min_precision=float(episode_config["min_precision"]),
            required_diagnostic_cases=episode_config[
                "required_diagnostic_cases"
            ],
        ),
    }
    quality_path = write_json_atomic(
        stage_root / "episodios_qualidade_v2.json",
        quality,
    )
    outputs.append(artifact_record(quality_path))
    qualitative_view = episode_qualitative_view_v2(episodes)
    qualitative_view_path = write_dataframe_atomic(
        qualitative_view,
        stage_root / "interacoes_qualitativas_episodios_v2.parquet",
    )
    outputs.append(
        artifact_record(
            qualitative_view_path,
            rows=len(qualitative_view),
        )
    )
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="03_apartes_episodios_v2_resultados",
        inputs=[
            *(artifact_record(path) for path in paths.values() if path.exists()),
            *(artifact_record(path) for path in request_paths),
            *(artifact_record(path) for path in output_paths),
        ],
        outputs=outputs,
        counts={
            "pipeline_version": EPISODE_PIPELINE_VERSION,
            "candidate_results": len(candidate_results),
            "episodes": len(episodes),
            "links": len(links),
            "speaker_assignments": len(assignments),
            "errors": len(errors),
            "review_sample": len(review),
            "reviewed": quality["reviewed"],
            "qualitative_authorized_v2": quality[
                "qualitative_authorized_v2"
            ],
            "batch_request_parts": len(request_paths),
            "batch_output_parts": len(output_paths),
            "model": model,
        },
    )
    manifest_path = write_json_atomic(
        stage_root / f"manifest_episodios_v2_{_safe_name(model)}.json",
        manifest,
    )
    return {**manifest, "manifest_path": str(manifest_path)}


def episode_qualitative_view_v2(episodes: pd.DataFrame) -> pd.DataFrame:
    """Create a chronological compatibility view without flattening v2 storage."""

    if episodes.empty:
        return pd.DataFrame(
            columns=[
                "interaction_id",
                "episodio_id",
                "aparte_id",
                "texto_id",
                "arena",
                "data",
                "ano",
                "aparteante_genero",
                "orador_genero",
                "segmentacao_status",
                "texto_aparte",
                "texto_resposta",
                "texto_contexto",
                "texto_episodio_cronologico",
            ]
        )
    view = episodes.copy()
    view["interaction_id"] = view["episodio_id"]
    view["segmentacao_status"] = np.where(
        view["texto_respostas"].fillna("").astype(str).str.strip().ne(""),
        "segmentado_com_resposta",
        "segmentado_sem_resposta_explicita",
    )
    view["texto_aparte"] = view["texto_participante"]
    view["texto_resposta"] = view.apply(
        lambda row: _join_nonempty(
            [
                row.get("texto_backchannels"),
                row.get("texto_respostas"),
            ]
        ),
        axis=1,
    )
    return view


def _turn_matches_v2(source: str) -> list[re.Match[str]]:
    matches = [
        *TURN_PATTERN_V2.finditer(source),
        *TURN_PATTERN_ASCII_V2.finditer(source),
    ]
    by_start: dict[int, re.Match[str]] = {}
    for match in matches:
        existing = by_start.get(match.start())
        if existing is None or match.end() > existing.end():
            by_start[match.start()] = match
    ordered = sorted(by_start.values(), key=lambda match: match.start())
    result: list[re.Match[str]] = []
    previous_end = -1
    for match in ordered:
        if match.start() < previous_end:
            continue
        result.append(match)
        previous_end = match.end()
    return result


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    left, right = int(start), int(end)
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    return left, right


def _subturn_spans(text: str, *, max_chars: int) -> list[tuple[int, int]]:
    if not text.strip():
        return []
    boundaries = [0]
    for match in re.finditer(
        r"(?:[.!?;:][\"”’')\]]*|\n)\s+",
        text,
    ):
        boundaries.append(match.end())
    boundaries.append(len(text))
    spans: list[tuple[int, int]] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        cursor = start
        while cursor < end:
            hard_end = min(cursor + max_chars, end)
            split_end = hard_end
            if hard_end < end:
                window = text[cursor:hard_end]
                whitespace = [
                    match.end()
                    for match in re.finditer(r"\s+", window)
                    if match.end() >= max_chars // 2
                ]
                if whitespace:
                    split_end = cursor + whitespace[-1]
            left, right = _trimmed_span(text, cursor, split_end)
            if left < right:
                spans.append((left, right))
            cursor = split_end
    if not spans:
        left, right = _trimmed_span(text, 0, len(text))
        if left < right:
            spans.append((left, right))
    return spans


def _person_key(arena: Any, person_id: str, name: str) -> str:
    arena_value = str(arena or "").strip().casefold()
    if person_id:
        return f"relacional:{arena_value}:{person_id}"
    return f"nome:{arena_value}:{_normalize(name)}"


def _normalize(value: Any) -> str:
    text = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _compatible_name(candidate: str, expected: str) -> bool:
    if not candidate or not expected:
        return False
    return (
        candidate == expected
        or (len(candidate) >= 5 and candidate in expected)
        or (len(expected) >= 5 and expected in candidate)
    )


def _assign_turn_speakers_python(
    turns: pd.DataFrame,
    participants: Sequence[Mapping[str, Any]],
) -> pd.DataFrame:
    result = turns.copy()
    for index, turn in result.iterrows():
        name = _normalize(turn.get("speaker_name"))
        if not name:
            continue
        exact = [
            participant
            for participant in participants
            if str(participant.get("nome_normalizado") or "") == name
        ]
        compatible = [
            participant
            for participant in participants
            if _compatible_name(
                name,
                str(participant.get("nome_normalizado") or ""),
            )
        ]
        matches = exact or compatible
        if len(matches) == 1:
            result.at[index, "participante_id_python"] = matches[0][
                "participante_id"
            ]
            result.at[index, "atribuicao_python_status"] = (
                "exato" if exact else "compativel_unico"
            )
        elif len(matches) > 1:
            result.at[index, "atribuicao_python_status"] = "ambiguo"
    return result


def _unique_index(
    frame: pd.DataFrame | None,
    key: str,
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    if frame is None or frame.empty:
        return {}
    if key not in frame:
        raise ValueError(f"{label} sem coluna {key}")
    keys = frame[key].astype(str)
    if keys.duplicated().any():
        raise ValueError(f"{label} contem {key} duplicado")
    return frame.set_index(keys, drop=False).to_dict("index")


def _reviewed_v1_ids(review: pd.DataFrame | None) -> set[str]:
    if review is None or review.empty or "interaction_id" not in review:
        return set()
    required = [
        "segmentacao_aparte_correta",
        "segmentacao_resposta_correta",
    ]
    if any(column not in review for column in required):
        return set()
    apart, _ = _optional_boolean_series(review[required[0]])
    response, _ = _optional_boolean_series(review[required[1]])
    complete = apart.notna() & response.notna()
    return set(review.loc[complete, "interaction_id"].astype(str))


def _legacy_anchor_unit_ids(
    legacy: Mapping[str, Any] | None,
    units: pd.DataFrame,
    *,
    prefix: str,
) -> list[str]:
    if legacy is None:
        return []
    source_hash = str(legacy.get("texto_fonte_sha256") or "")
    unit_hashes = set(
        units["texto_fonte_sha256"].fillna("").astype(str)
    )
    if source_hash and unit_hashes and source_hash not in unit_hashes:
        return []
    try:
        start = int(legacy.get(f"{prefix}_char_start"))
        end = int(legacy.get(f"{prefix}_char_end"))
    except (TypeError, ValueError):
        return []
    if start >= end:
        return []
    leaf_units = units.loc[units["nivel"].eq("subturno")]
    overlaps = leaf_units.loc[
        leaf_units["char_start"].astype(int).lt(end)
        & leaf_units["char_end"].astype(int).gt(start)
    ].sort_values(
        ["char_start", "char_end", "unidade_id"],
        kind="stable",
    )
    return overlaps["unidade_id"].astype(str).tolist()


def _diagnostic_case_for_group(group: pd.DataFrame) -> str | None:
    apart_ids = set(group["aparte_id"].astype(str))
    exact_cases = {
        DIAGNOSTIC_CASE_IDS[apart_id]
        for apart_id in apart_ids
        if apart_id in DIAGNOSTIC_CASE_IDS
    }
    if exact_cases:
        if len(exact_cases) != 1:
            raise ValueError(
                f"Texto associado a casos diagnosticos conflitantes: {exact_cases}"
            )
        return next(iter(exact_cases))
    names = {
        _normalize(value)
        for column in ["aparteante_nome", "orador_nome"]
        if column in group
        for value in group[column].fillna("").astype(str)
    }
    joined = " | ".join(sorted(names))
    for case, required_names in DIAGNOSTIC_CASES.items():
        if all(required_name in joined for required_name in required_names):
            return case
    return None


def _diagnostic_expectation(case: str) -> str:
    expectations = {
        "geovania_rogerio_episodios_sobrepostos": (
            "episodios distintos podem se sobrepor; resposta a Geovania vem "
            "depois da intervencao de Rogerio e antes da resposta a Rogerio"
        ),
        "julio_campos_aparte_multiturno_perfeito": (
            "preservar todas as falas de Julio e os varios backchannels "
            "Perfeito, sem truncar no primeiro microturno"
        ),
        "izalci_pedido_concessao_fora_aparte": (
            "pedido e concessao pertencem ao contexto; fala substantiva "
            "comeca depois da concessao"
        ),
    }
    return expectations.get(case, "")


def _json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _expand_selected_unit_ids(
    selected: Sequence[Any],
    *,
    unit_index: Mapping[str, Mapping[str, Any]],
    text_id: str,
) -> list[tuple[str, str]]:
    selected_ids = [str(value) for value in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("lista de unidades contem IDs duplicados")
    expanded: list[tuple[str, str]] = []
    for selected_id in selected_ids:
        unit = unit_index.get(selected_id)
        if unit is None or str(unit.get("texto_id")) != str(text_id):
            raise ValueError(f"unidade inexistente ou de outro texto: {selected_id}")
        if unit.get("nivel") == "turno":
            children = [
                child
                for child in unit_index.values()
                if child.get("nivel") == "subturno"
                and str(child.get("turno_id")) == str(unit.get("turno_id"))
            ]
            children.sort(
                key=lambda child: (
                    int(child["ordem_subturno"]),
                    str(child["unidade_id"]),
                )
            )
            if not children:
                children = [unit]
            expanded.extend(
                (str(child["unidade_id"]), selected_id)
                for child in children
            )
        else:
            expanded.append((selected_id, selected_id))
    expanded_ids = [unit_id for unit_id, _ in expanded]
    if len(expanded_ids) != len(set(expanded_ids)):
        raise ValueError(
            "selecao mistura turno inteiro e subturno descendente"
        )
    return expanded


def _candidate_year(candidate: Mapping[str, Any]) -> int | None:
    value = candidate.get("ano")
    if value is not None:
        try:
            if pd.notna(value):
                return int(value)
        except (TypeError, ValueError):
            pass
    parsed = pd.to_datetime(candidate.get("data"), errors="coerce")
    return int(parsed.year) if pd.notna(parsed) else None


def _join_role_text(
    links: Sequence[Mapping[str, Any]],
    role: str,
) -> str:
    return "\n".join(
        str(link["texto_unidade"])
        for link in links
        if link["papel_no_episodio"] == role
        and str(link.get("texto_unidade") or "").strip()
    )


def _join_nonempty(values: Sequence[Any]) -> str:
    return "\n".join(
        str(value)
        for value in values
        if str(value or "").strip()
    )


def _episode_overlap_flags(episodes: pd.DataFrame) -> pd.Series:
    flags = pd.Series(False, index=episodes.index)
    for _, group in episodes.groupby("texto_id", sort=False):
        for index, row in group.iterrows():
            overlap = group.loc[group.index != index]
            flags.at[index] = bool(
                (
                    overlap["char_start"].astype(int).lt(int(row["char_end"]))
                    & overlap["char_end"].astype(int).gt(int(row["char_start"]))
                ).any()
            )
    return flags


def _safe_name(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")
