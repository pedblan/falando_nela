from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .config import AnalysisConfig, load_config, resolve_input_paths
from .io import (
    artifact_record,
    base_manifest,
    input_inventory,
    load_inputs,
    prepare_run_directory,
    read_optional_parquet,
    write_dataframe_atomic,
    write_json_atomic,
)


WORD_RE = re.compile(r"\b[^\W\d_]+(?:[-'][^\W\d_]+)*\b", flags=re.UNICODE)
SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^\w]+", flags=re.UNICODE)


def build_snapshot(
    frames: Mapping[str, pd.DataFrame],
    config: AnalysisConfig,
    *,
    parliamentarian_periods: pd.DataFrame | None = None,
    cleaning_rules: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build the immutable analytical snapshot and its audit tables."""

    prepared = [prepare_arena_frame(frame, arena, config) for arena, frame in frames.items()]
    if not prepared:
        raise ValueError("Nenhuma arena foi fornecida")
    snapshot = pd.concat(prepared, ignore_index=True, sort=False)
    snapshot["texto_original"] = snapshot["texto"].fillna("").astype(str)
    cleaned = snapshot["texto_original"].map(lambda value: apply_cleaning_rules(value, cleaning_rules or ()))
    snapshot["texto_analitico"] = cleaned.map(lambda item: item[0])
    snapshot["limpeza_regra"] = cleaned.map(lambda item: item[1])
    snapshot["limpeza_aplicada"] = snapshot["limpeza_regra"].notna()
    snapshot["texto_hash_normalizado"] = snapshot["texto_analitico"].map(normalized_text_hash)
    snapshot["n_palavras"] = snapshot["texto_analitico"].map(count_words)
    snapshot["ano"] = snapshot["data_analise"].dt.year.astype("Int64")
    snapshot["mes"] = snapshot["data_analise"].dt.month.astype("Int64")
    snapshot["ano_ytd"] = snapshot["ano"].eq(int(config.raw["ytd_year"]))
    snapshot["elegivel_descritivas"] = snapshot["texto_analitico"].str.strip().ne("")
    snapshot["elegivel_inferencia_anual"] = snapshot["ano"].between(
        int(config.raw["complete_year_start"]), int(config.raw["complete_year_end"]), inclusive="both"
    )
    snapshot["elegivel_nlp"] = snapshot["n_palavras"].ge(int(config.raw["eligibility"]["nlp_min_words"]))
    snapshot["elegivel_llm"] = snapshot["n_palavras"].ge(int(config.raw["eligibility"]["llm_min_words"]))
    snapshot["elegivel_topicos"] = snapshot.get("resumo", pd.Series("", index=snapshot.index)).fillna("").str.strip().ne("")

    id_conflicts = audit_identifier_conflicts(snapshot)
    duplicate_audit, remove_indices = audit_cross_arena_duplicates(snapshot)
    snapshot["duplicata_removida"] = snapshot.index.isin(remove_indices)
    snapshot["duplicata_auditoria"] = snapshot["texto_id"].isin(set(duplicate_audit.get("texto_id", [])))
    snapshot = snapshot.loc[~snapshot["duplicata_removida"]].copy()

    near_duplicates = find_near_duplicate_candidates(snapshot)
    if parliamentarian_periods is not None and not parliamentarian_periods.empty:
        snapshot = temporal_join(snapshot, parliamentarian_periods)
    else:
        snapshot = add_unmatched_temporal_columns(snapshot)

    snapshot = snapshot.sort_values(["data_analise", "arena", "texto_id"], kind="stable").reset_index(drop=True)
    audits = {
        "duplicate_audit": duplicate_audit,
        "identifier_conflicts": id_conflicts,
        "near_duplicate_candidates": near_duplicates,
        "temporal_join_summary": temporal_join_summary(snapshot),
    }
    return snapshot, audits


def prepare_arena_frame(frame: pd.DataFrame, arena: str, config: AnalysisConfig) -> pd.DataFrame:
    if arena not in config.raw["arenas"]:
        raise ValueError(f"Arena desconhecida: {arena}")
    spec = config.raw["arenas"][arena]
    required = {"texto_id", "source", "dataset", "ambito", "data", "texto"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{arena}: colunas ausentes: {sorted(missing)}")
    data = frame.copy()
    dates = pd.to_datetime(data["data"], errors="coerce")
    mask = (
        data["source"].astype(str).eq(spec["source"])
        & data["dataset"].astype(str).eq(spec["dataset"])
        & data["ambito"].astype(str).eq(spec["scope"])
        & dates.between(pd.Timestamp(config.date_start), pd.Timestamp(config.date_end), inclusive="both")
    )
    if "documento_tipo" in data:
        mask &= data["documento_tipo"].fillna("").astype(str).str.casefold().eq("discurso")
    data = data.loc[mask].copy()
    data["data_analise"] = dates.loc[mask]
    data["arena"] = arena
    data["casa_origem"] = data.get("casa", pd.Series(spec["house"], index=data.index)).fillna(spec["house"])
    return data


def apply_cleaning_rules(
    text: str,
    rules: Sequence[Mapping[str, Any]],
) -> tuple[str, str | None]:
    """Apply only explicitly approved hard-cut rules and preserve the source text."""

    chosen: tuple[int, str] | None = None
    for rule in rules:
        if rule.get("action") != "hard_cut" or not rule.get("approved", False):
            continue
        pattern = str(rule.get("pattern") or "")
        if not pattern:
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match and (chosen is None or match.start() < chosen[0]):
            chosen = (match.start(), str(rule.get("rule_id") or pattern))
    if chosen is None:
        return text, None
    return text[: chosen[0]].rstrip(), chosen[1]


def load_cleaning_rules(config: AnalysisConfig, data_root: str | Path) -> list[dict[str, Any]]:
    relative = config.raw.get("cleaning", {}).get("rules_path")
    if not relative:
        return []
    path = Path(data_root) / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules", payload) if isinstance(payload, dict) else payload
    if not isinstance(rules, list):
        raise ValueError("O arquivo de regras deve conter uma lista")
    invalid = [rule for rule in rules if rule.get("action") != "hard_cut"]
    if invalid:
        raise ValueError("A camada analitica aceita somente regras hard_cut")
    return rules


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return SPACE_RE.sub(" ", text).strip()


def normalized_text_hash(value: Any) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return NON_ALNUM_RE.sub(" ", text).strip()


def count_words(value: Any) -> int:
    return len(WORD_RE.findall(str(value or "")))


def audit_identifier_conflicts(snapshot: pd.DataFrame) -> pd.DataFrame:
    usable = snapshot.loc[snapshot["texto_id"].fillna("").astype(str).ne("")]
    conflicts = usable.groupby("texto_id", dropna=False)["texto_hash_normalizado"].nunique()
    ids = set(conflicts[conflicts > 1].index)
    columns = ["texto_id", "arena", "data", "parlamentar_id", "texto_hash_normalizado"]
    return usable.loc[usable["texto_id"].isin(ids), columns].sort_values(["texto_id", "arena"])


def audit_cross_arena_duplicates(snapshot: pd.DataFrame) -> tuple[pd.DataFrame, set[int]]:
    candidates = snapshot.loc[snapshot["arena"].isin(["senado", "congresso"])].copy()
    candidates["speaker_key"] = _speaker_key(candidates)
    candidates["session_key"] = candidates.get("sessao_id", "").fillna("").astype(str)
    candidates["speech_key"] = candidates.get("pronunciamento_id", "").fillna("").astype(str)
    rows: list[dict[str, Any]] = []
    removed: set[int] = set()

    group_columns = ["data_analise", "speaker_key", "session_key", "texto_hash_normalizado"]
    for _, group in candidates.groupby(group_columns, dropna=False, sort=False):
        arenas = set(group["arena"])
        if arenas != {"senado", "congresso"}:
            continue
        senate = group.loc[group["arena"].eq("senado")]
        congress = group.loc[group["arena"].eq("congresso")]
        for senate_index, senate_row in senate.iterrows():
            for congress_index, congress_row in congress.iterrows():
                same_identifier = _nonempty_equal(senate_row.get("pronunciamento_id"), congress_row.get("pronunciamento_id")) or _nonempty_equal(
                    senate_row.get("texto_id"), congress_row.get("texto_id")
                )
                status = "auto_remove_senado" if same_identifier else "review_exact_content"
                if same_identifier:
                    removed.add(int(senate_index))
                rows.append(
                    {
                        "senado_index": int(senate_index),
                        "congresso_index": int(congress_index),
                        "texto_id": senate_row.get("texto_id"),
                        "senado_texto_id": senate_row.get("texto_id"),
                        "congresso_texto_id": congress_row.get("texto_id"),
                        "pronunciamento_id": senate_row.get("pronunciamento_id"),
                        "data": senate_row.get("data"),
                        "parlamentar_id": senate_row.get("parlamentar_id"),
                        "sessao_id": senate_row.get("sessao_id"),
                        "status": status,
                    }
                )
    return pd.DataFrame(rows), removed


def find_near_duplicate_candidates(
    snapshot: pd.DataFrame,
    *,
    threshold: float = 0.92,
    max_group_size: int = 80,
) -> pd.DataFrame:
    """Find review candidates only within compatible date/speaker groups."""

    candidates = snapshot.loc[snapshot["arena"].isin(["senado", "congresso"])].copy()
    candidates["speaker_key"] = _speaker_key(candidates)
    candidates["token_set"] = candidates["texto_analitico"].map(_token_set)
    rows: list[dict[str, Any]] = []
    for _, group in candidates.groupby(["data_analise", "speaker_key"], dropna=False, sort=False):
        if len(group) > max_group_size or set(group["arena"]) != {"senado", "congresso"}:
            continue
        senate = group.loc[group["arena"].eq("senado")]
        congress = group.loc[group["arena"].eq("congresso")]
        for _, left in senate.iterrows():
            for _, right in congress.iterrows():
                if left["texto_hash_normalizado"] == right["texto_hash_normalizado"]:
                    continue
                left_tokens, right_tokens = left["token_set"], right["token_set"]
                union = left_tokens | right_tokens
                similarity = len(left_tokens & right_tokens) / len(union) if union else 0.0
                if similarity >= threshold:
                    rows.append(
                        {
                            "senado_texto_id": left.get("texto_id"),
                            "congresso_texto_id": right.get("texto_id"),
                            "data": left.get("data"),
                            "parlamentar_id": left.get("parlamentar_id"),
                            "similaridade_jaccard_tokens": similarity,
                            "status": "review_near_duplicate",
                        }
                    )
    return pd.DataFrame(rows)


def temporal_join(snapshot: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    required = {"source", "parlamentar_id", "vigencia_inicio", "vigencia_fim"}
    missing = required.difference(periods.columns)
    if missing:
        raise ValueError(f"parlamentares_periodos sem colunas: {sorted(missing)}")
    result = snapshot.copy()
    period_data = periods.copy()
    period_data["inicio_dt"] = pd.to_datetime(period_data["vigencia_inicio"], errors="coerce")
    period_data["fim_dt"] = pd.to_datetime(period_data["vigencia_fim"], errors="coerce")
    period_data = period_data.dropna(subset=["source", "parlamentar_id", "inicio_dt", "fim_dt"])
    period_data["join_key"] = period_data["source"].astype(str) + "\x1f" + period_data["parlamentar_id"].astype(str)
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    output_fields = [
        "parlamentar_key",
        "genero",
        "sexo_original",
        "partido_sigla",
        "uf",
        "cargo",
        "legislatura",
        "mandato_id",
        "intervalo_fonte",
        "match_priority",
        "intervalo_inferido",
    ]
    for row in period_data.to_dict("records"):
        index[row["join_key"]].append(row)
    for values in index.values():
        values.sort(key=lambda item: (item["inicio_dt"], item.get("match_priority") or 999))

    matched_values: dict[str, list[Any]] = {field: [] for field in output_fields}
    statuses: list[str] = []
    candidate_counts: list[int] = []
    for row in result.to_dict("records"):
        source = str(row.get("source") or "")
        parliamentarian_id = str(row.get("parlamentar_id") or "")
        date_value = row.get("data_analise")
        key = source + "\x1f" + parliamentarian_id
        candidates = [
            item
            for item in index.get(key, [])
            if pd.notna(date_value) and item["inicio_dt"] <= date_value <= item["fim_dt"]
        ]
        candidates.sort(key=lambda item: (item.get("match_priority") or 999, item["inicio_dt"]), reverse=False)
        chosen = candidates[0] if candidates else None
        candidate_counts.append(len(candidates))
        if not parliamentarian_id:
            status = "missing_parliamentarian_id"
        elif pd.isna(date_value):
            status = "missing_date"
        elif not candidates:
            status = "unmatched"
        elif len(candidates) > 1:
            status = "matched_multiple_resolved"
        else:
            status = "matched"
        statuses.append(status)
        for field in output_fields:
            matched_values[field].append(chosen.get(field) if chosen else None)

    rename = {
        "genero": "genero_oficial",
        "sexo_original": "sexo_original_oficial",
        "partido_sigla": "partido_temporal",
        "uf": "uf_temporal",
        "cargo": "cargo_temporal",
    }
    for field, values in matched_values.items():
        result[rename.get(field, field)] = values
    result["juncao_temporal_status"] = statuses
    result["juncao_temporal_candidatos"] = candidate_counts
    result["genero_analitico"] = result["genero_oficial"].fillna("nao_informado")
    result["genero_presumido"] = False
    return result


def add_unmatched_temporal_columns(snapshot: pd.DataFrame) -> pd.DataFrame:
    result = snapshot.copy()
    defaults = {
        "parlamentar_key": None,
        "genero_oficial": "nao_informado",
        "sexo_original_oficial": None,
        "partido_temporal": None,
        "uf_temporal": None,
        "cargo_temporal": None,
        "legislatura": None,
        "mandato_id": None,
        "intervalo_fonte": None,
        "match_priority": None,
        "intervalo_inferido": None,
        "juncao_temporal_status": "periods_not_loaded",
        "juncao_temporal_candidatos": 0,
        "genero_analitico": "nao_informado",
        "genero_presumido": False,
    }
    for column, value in defaults.items():
        result[column] = value
    return result


def temporal_join_summary(snapshot: pd.DataFrame) -> pd.DataFrame:
    return (
        snapshot.groupby(["arena", "ano", "juncao_temporal_status"], dropna=False)
        .size()
        .rename("n_discursos")
        .reset_index()
    )


def run_snapshot(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
    overwrite: bool = False,
    optional_arenas: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    output_root = prepare_run_directory(config, data_root, run_id, stage="00_snapshot", overwrite=overwrite)
    inventory = input_inventory(config, data_root)
    frames = load_inputs(config, data_root, optional=optional_arenas)
    paths = resolve_input_paths(config, data_root)
    periods = read_optional_parquet(paths["parliamentarian_periods"])
    rules = load_cleaning_rules(config, data_root)
    snapshot, audits = build_snapshot(frames, config, parliamentarian_periods=periods, cleaning_rules=rules)

    artifacts: list[dict[str, Any]] = []
    snapshot_path = write_dataframe_atomic(snapshot, output_root / "00_snapshot" / "discursos_plenario_snapshot.parquet")
    artifacts.append(artifact_record(snapshot_path, rows=len(snapshot)))
    inventory_path = write_dataframe_atomic(inventory, output_root / "00_snapshot" / "entradas.csv")
    artifacts.append(artifact_record(inventory_path, rows=len(inventory)))
    for name, frame in audits.items():
        path = write_dataframe_atomic(frame, output_root / "00_snapshot" / f"{name}.csv")
        artifacts.append(artifact_record(path, rows=len(frame)))

    counts = {
        "input_rows": {name: len(frame) for name, frame in frames.items()},
        "snapshot_rows": len(snapshot),
        "rows_by_arena": snapshot["arena"].value_counts(dropna=False).to_dict(),
        "ytd_rows": int(snapshot["ano_ytd"].sum()),
    }
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="00_snapshot",
        inputs=inventory.loc[inventory["existe"]].to_dict("records"),
        outputs=artifacts,
        counts=counts,
    )
    manifest_path = write_json_atomic(output_root / "00_snapshot" / "manifest.json", manifest)
    manifest["manifest_path"] = str(manifest_path)
    manifest["snapshot_path"] = str(snapshot_path)
    return manifest


def _speaker_key(frame: pd.DataFrame) -> pd.Series:
    ids = frame.get("parlamentar_id", pd.Series("", index=frame.index)).fillna("").astype(str)
    names = frame.get("parlamentar_nome", pd.Series("", index=frame.index)).map(normalize_name)
    return ids.where(ids.ne(""), names)


def _token_set(text: Any) -> set[str]:
    return {token.casefold() for token in WORD_RE.findall(str(text or "")) if len(token) > 2}


def _nonempty_equal(left: Any, right: Any) -> bool:
    return bool(str(left or "").strip()) and str(left).strip() == str(right or "").strip()
