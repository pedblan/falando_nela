from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import load_config, resolve_output_root
from .io import artifact_record, base_manifest, write_dataframe_atomic, write_json_atomic


ACCOMPANY_PATTERN = re.compile(r"\bque\s+nos\s+acompanham\b", re.IGNORECASE)
CLOSING_PATTERN = re.compile(r"\bera\s+o\s+que\s+eu\s+tinha\s+a\s+dizer\b", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\b[^\W\d_]+(?:[-'][^\W\d_]+)*\b", re.UNICODE)


def load_portuguese_pipeline(model: str = "pt_core_news_lg") -> Any:
    try:
        import spacy
        import textdescriptives  # noqa: F401 - registers spaCy factories
    except ImportError as exc:
        raise RuntimeError("Instale requirements-analise.txt antes de executar NLP") from exc
    nlp = spacy.load(model)
    if "textdescriptives/all" not in nlp.pipe_names:
        nlp.add_pipe("textdescriptives/all")
    return nlp


def lexical_diversity(text: str) -> dict[str, float]:
    tokens = [token.casefold() for token in TOKEN_PATTERN.findall(text)]
    if not tokens:
        return {"tokens": 0, "types": 0, "type_token_ratio": np.nan, "repetition_ratio": np.nan}
    types = len(set(tokens))
    return {
        "tokens": len(tokens),
        "types": types,
        "type_token_ratio": types / len(tokens),
        "repetition_ratio": 1 - types / len(tokens),
    }


def custom_linguistic_features(doc: Any) -> dict[str, Any]:
    alpha_tokens = [token for token in doc if getattr(token, "is_alpha", False)]
    n = len(alpha_tokens)
    personal_pronouns = [token for token in alpha_tokens if token.pos_ == "PRON" and "Person" in token.morph]
    subject_pronouns = [token for token in personal_pronouns if token.dep_ in {"nsubj", "csubj"}]
    interrogative_sentences = [sent for sent in doc.sents if sent.text.rstrip().endswith("?") or any(token.dep_ == "advmod" and token.tag_ in {"ADV", "PRON"} for token in sent)]
    ir_periphrases = 0
    ser_auxiliary = 0
    ser_passive = 0
    ser_evaluative = 0
    dependency_distances: list[int] = []
    for token in alpha_tokens:
        if token.head is not token:
            dependency_distances.append(abs(token.i - token.head.i))
        if token.lemma_.casefold() == "ir" and any(child.pos_ == "VERB" and child.morph.get("VerbForm") == ["Inf"] for child in token.children):
            ir_periphrases += 1
        if token.lemma_.casefold() == "ser" and token.dep_ in {"aux", "cop", "aux:pass"}:
            ser_auxiliary += 1
            if token.dep_ == "aux:pass" or any(child.dep_ == "nsubj:pass" for child in token.head.children):
                ser_passive += 1
            if token.dep_ == "cop" and token.head.pos_ in {"ADJ", "NOUN"}:
                ser_evaluative += 1
    pos_counts = {label: 0 for label in ["PRON", "ADP", "AUX", "NOUN", "VERB", "ADJ", "ADV"]}
    for token in alpha_tokens:
        if token.pos_ in pos_counts:
            pos_counts[token.pos_] += 1
    text = doc.text
    result: dict[str, Any] = {
        "n_tokens_alpha": n,
        "n_sentencas": sum(1 for _ in doc.sents),
        "n_pronomes_pessoais": len(personal_pronouns),
        "n_pronomes_sujeito": len(subject_pronouns),
        "n_interrogativas": len(interrogative_sentences),
        "n_perifrases_ir": ir_periphrases,
        "n_ser_auxiliar": ser_auxiliary,
        "n_ser_passivo": ser_passive,
        "n_ser_avaliativo": ser_evaluative,
        "distancia_dependencia_media_custom": float(np.mean(dependency_distances)) if dependency_distances else np.nan,
        "padrao_que_nos_acompanham": len(ACCOMPANY_PATTERN.findall(text)),
        "padrao_era_o_que_eu_tinha_a_dizer": len(CLOSING_PATTERN.findall(text)),
    }
    for label, value in pos_counts.items():
        result[f"n_{label.casefold()}"] = value
        result[f"prop_{label.casefold()}"] = value / n if n else np.nan
    result.update(lexical_diversity(text))
    return result


def extract_textdescriptives(documents: Iterable[Any]) -> pd.DataFrame:
    try:
        import textdescriptives as td
    except ImportError as exc:
        raise RuntimeError("TextDescriptives nao instalado") from exc
    docs = list(documents)
    try:
        return td.extract_df(docs, include_text=False)
    except TypeError:
        return td.extract_df(docs)


def analyze_nlp_frame(
    frame: pd.DataFrame,
    *,
    nlp: Any,
    text_column: str = "texto_analitico",
    id_column: str = "texto_id",
    batch_size: int = 32,
    n_process: int = 1,
) -> pd.DataFrame:
    required = {id_column, text_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dados sem colunas: {sorted(missing)}")
    texts = frame[text_column].fillna("").astype(str).tolist()
    docs = list(nlp.pipe(texts, batch_size=batch_size, n_process=n_process))
    td_features = extract_textdescriptives(docs).reset_index(drop=True)
    custom = pd.DataFrame([custom_linguistic_features(doc) for doc in docs])
    identity_columns = [column for column in [id_column, "arena", "ano", "parlamentar_id", "genero_analitico", "n_palavras"] if column in frame]
    identity = frame[identity_columns].reset_index(drop=True)
    duplicate_columns = set(identity).intersection(td_features) | set(identity).intersection(custom) | set(td_features).intersection(custom)
    if duplicate_columns:
        custom = custom.rename(columns={column: f"{column}_custom" for column in duplicate_columns})
    return pd.concat([identity, td_features, custom], axis=1)


def run_nlp_analysis(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
    model: str = "pt_core_news_lg",
    limit: int | None = None,
    batch_size: int = 32,
    n_process: int = 1,
) -> dict[str, Any]:
    config = load_config(config_path)
    root = resolve_output_root(config, data_root, run_id)
    snapshot_path = root / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)
    snapshot = pd.read_parquet(snapshot_path)
    eligible = snapshot.loc[snapshot["elegivel_nlp"]].copy()
    if limit is not None:
        eligible = eligible.head(limit)
    nlp = load_portuguese_pipeline(model)
    features = analyze_nlp_frame(eligible, nlp=nlp, batch_size=batch_size, n_process=n_process)
    output = write_dataframe_atomic(features, root / "04_nlp" / "nlp_features.parquet")
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="04_nlp",
        inputs=[artifact_record(snapshot_path, rows=len(snapshot))],
        outputs=[artifact_record(output, rows=len(features))],
        counts={"eligible": len(eligible), "processed": len(features), "model": model},
    )
    manifest_path = write_json_atomic(root / "04_nlp" / "manifest.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}
