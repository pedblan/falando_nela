from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import AnalysisConfig, load_config, resolve_input_paths
from .io import artifact_record, base_manifest, prepare_run_directory, read_optional_parquet, write_dataframe_atomic, write_json_atomic


UNKNOWN_GENDER_VALUES = {"", "nao_informado", "não informado", "nao_identificado", "unknown", "none", "nan"}
REVIEW_COLUMNS = [
    "parlamentar_key",
    "genero_oficial",
    "genero_enriquecido",
    "genero_analitico",
    "genero_origem",
    "genero_presumido",
    "evidencia_url",
    "evidencia_titulo",
    "evidencia_trecho",
    "fontes_consultadas",
    "consultado_em",
    "modelo",
    "prompt_version",
    "revisao_status",
    "revisor",
    "revisado_em",
    "observacao_revisao",
]


def select_unknown_parliamentarians(periods: pd.DataFrame) -> pd.DataFrame:
    required = {"parlamentar_key", "genero"}
    missing = required.difference(periods.columns)
    if missing:
        raise ValueError(f"Tabela temporal sem colunas: {sorted(missing)}")
    values = periods["genero"].fillna("").astype(str).str.casefold().str.strip()
    unknowns = periods.loc[values.isin(UNKNOWN_GENDER_VALUES)].copy()
    identity_columns = [
        column
        for column in [
            "parlamentar_key",
            "source",
            "casa",
            "parlamentar_id",
            "nome_parlamentar",
            "nome_civil",
            "genero",
            "sexo_original",
        ]
        if column in unknowns
    ]
    result = unknowns[identity_columns].drop_duplicates("parlamentar_key", keep="last").reset_index(drop=True)
    return result.rename(columns={"genero": "genero_oficial"})


def requery_official_sources(
    unknowns: pd.DataFrame,
    resolver: Callable[[Mapping[str, Any]], Mapping[str, Any] | None],
) -> pd.DataFrame:
    """Run a caller-supplied official resolver before any public web research."""

    rows: list[dict[str, Any]] = []
    for record in unknowns.to_dict("records"):
        resolved = dict(resolver(record) or {})
        rows.append({**record, **resolved, "consulta_oficial_executada": True})
    return pd.DataFrame(rows)


def build_gender_research_prompt(record: Mapping[str, Any]) -> str:
    identity = {
        "parlamentar_key": record.get("parlamentar_key"),
        "source": record.get("source"),
        "casa": record.get("casa"),
        "parlamentar_id": record.get("parlamentar_id"),
        "nome_parlamentar": record.get("nome_parlamentar"),
        "nome_civil": record.get("nome_civil"),
    }
    return f"""Pesquise informacao publica e textual sobre o genero/sexo registral da pessoa parlamentar abaixo.

Identidade para desambiguacao:
{json.dumps(identity, ensure_ascii=False, sort_keys=True)}

Regras obrigatorias:
1. Priorize paginas e documentos oficiais; use outras fontes publicas confiaveis somente se necessario.
2. Nao conclua com base apenas no nome, fotografia, aparencia ou forma de tratamento.
3. Exija uma afirmacao textual publica e citavel que identifique o genero/sexo da propria pessoa.
4. Se a evidencia for insuficiente, responda genero_enriquecido=nao_identificado.
5. Transcreva apenas um trecho curto, suficiente para auditoria, e informe URL e titulo.
6. Sua resposta sera somente uma candidatura para revisao humana; nao altere o dado oficial.
"""


def gender_research_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "genero_enriquecido": {
                "type": "string",
                "enum": ["feminino", "masculino", "nao_identificado"],
            },
            "evidencia_url": {"type": ["string", "null"]},
            "evidencia_titulo": {"type": ["string", "null"]},
            "evidencia_trecho": {"type": ["string", "null"]},
            "fontes_consultadas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "titulo": {"type": "string"},
                    },
                    "required": ["url", "titulo"],
                    "additionalProperties": False,
                },
            },
            "justificativa": {"type": "string"},
        },
        "required": [
            "genero_enriquecido",
            "evidencia_url",
            "evidencia_titulo",
            "evidencia_trecho",
            "fontes_consultadas",
            "justificativa",
        ],
        "additionalProperties": False,
    }


def research_gender_candidate(
    record: Mapping[str, Any],
    *,
    client: Any,
    model: str,
    prompt_version: str,
) -> dict[str, Any]:
    """Research one candidate with web search; callers control whether the API is invoked."""

    response = client.responses.create(
        model=model,
        tools=[{"type": "web_search"}],
        input=build_gender_research_prompt(record),
        text={
            "format": {
                "type": "json_schema",
                "name": "gender_research_candidate",
                "strict": True,
                "schema": gender_research_schema(),
            }
        },
    )
    payload = json.loads(response.output_text)
    candidate = candidate_from_research_payload(
        record,
        payload,
        model=model,
        prompt_version=prompt_version,
    )
    candidate["response_id"] = getattr(response, "id", None)
    return candidate


def research_gender_candidates(
    unknowns: pd.DataFrame,
    *,
    client: Any,
    model: str,
    prompt_version: str,
    limit: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Research candidates sequentially and keep failures in a resumable audit."""

    records = unknowns.head(limit).to_dict("records") if limit is not None else unknowns.to_dict("records")
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for record in records:
        try:
            candidates.append(
                research_gender_candidate(
                    record,
                    client=client,
                    model=model,
                    prompt_version=prompt_version,
                )
            )
        except Exception as exc:  # failures are persisted for deliberate retry
            errors.append(
                {
                    "parlamentar_key": record.get("parlamentar_key"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return pd.DataFrame(candidates), pd.DataFrame(errors)


def candidate_from_research_payload(
    record: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    model: str,
    prompt_version: str,
    consulted_at: str | None = None,
) -> dict[str, Any]:
    value = str(payload.get("genero_enriquecido") or "nao_identificado")
    if value not in {"feminino", "masculino", "nao_identificado"}:
        raise ValueError(f"Valor de genero invalido: {value}")
    has_evidence = all(str(payload.get(field) or "").strip() for field in ("evidencia_url", "evidencia_titulo", "evidencia_trecho"))
    if value != "nao_identificado" and not has_evidence:
        raise ValueError("Candidatura identificada exige evidencia com URL, titulo e trecho textual")
    official = str(record.get("genero_oficial") or "nao_informado")
    return {
        "parlamentar_key": record.get("parlamentar_key"),
        "genero_oficial": official,
        "genero_enriquecido": value,
        "genero_analitico": official,
        "genero_origem": "oficial",
        "genero_presumido": False,
        "evidencia_url": payload.get("evidencia_url"),
        "evidencia_titulo": payload.get("evidencia_titulo"),
        "evidencia_trecho": payload.get("evidencia_trecho"),
        "fontes_consultadas": json.dumps(payload.get("fontes_consultadas") or [], ensure_ascii=False),
        "consultado_em": consulted_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "modelo": model,
        "prompt_version": prompt_version,
        "revisao_status": "pendente",
        "revisor": None,
        "revisado_em": None,
        "observacao_revisao": None,
    }


def publish_approved_gender_enrichment(candidates: pd.DataFrame) -> pd.DataFrame:
    missing = set(REVIEW_COLUMNS).difference(candidates.columns)
    if missing:
        raise ValueError(f"Tabela de revisao sem colunas: {sorted(missing)}")
    approved = candidates.loc[candidates["revisao_status"].eq("aprovado")].copy()
    invalid = approved["genero_enriquecido"].isin(["feminino", "masculino"]) & (
        approved["revisor"].fillna("").str.strip().eq("")
        | approved["revisado_em"].fillna("").str.strip().eq("")
        | approved["evidencia_url"].fillna("").str.strip().eq("")
        | approved["evidencia_trecho"].fillna("").str.strip().eq("")
    )
    if invalid.any():
        raise ValueError("Candidaturas aprovadas exigem revisor, data e evidencia textual")
    identified = approved["genero_enriquecido"].isin(["feminino", "masculino"])
    approved.loc[identified, "genero_analitico"] = approved.loc[identified, "genero_enriquecido"]
    approved.loc[identified, "genero_origem"] = "pesquisa_publica_revisada"
    approved.loc[identified, "genero_presumido"] = True
    return approved[REVIEW_COLUMNS].reset_index(drop=True)


def apply_approved_gender_enrichment(snapshot: pd.DataFrame, approved: pd.DataFrame) -> pd.DataFrame:
    result = snapshot.copy()
    if approved.empty:
        return result
    enrichment = approved[["parlamentar_key", "genero_analitico", "genero_origem", "genero_presumido"]].rename(
        columns={
            "genero_analitico": "genero_analitico_enriquecido",
            "genero_origem": "genero_origem_enriquecido",
            "genero_presumido": "genero_presumido_enriquecido",
        }
    )
    result = result.merge(enrichment, on="parlamentar_key", how="left", validate="many_to_one")
    has_value = result["genero_analitico_enriquecido"].notna()
    result.loc[has_value, "genero_analitico"] = result.loc[has_value, "genero_analitico_enriquecido"]
    result["genero_origem"] = result["genero_origem_enriquecido"].fillna("oficial")
    result["genero_presumido"] = result["genero_presumido_enriquecido"].fillna(False).astype(bool)
    return result.drop(columns=[column for column in result if column.endswith("_enriquecido")])


def run_gender_enrichment_setup(
    *,
    data_root: str | Path,
    run_id: str,
    config_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    output_root = prepare_run_directory(config, data_root, run_id, stage="01_genero", overwrite=overwrite)
    periods_path = resolve_input_paths(config, data_root)["parliamentarian_periods"]
    periods = read_optional_parquet(periods_path)
    if periods.empty:
        raise FileNotFoundError(f"Tabela temporal ausente ou vazia: {periods_path}")
    unknowns = select_unknown_parliamentarians(periods)
    output_path = write_dataframe_atomic(unknowns, output_root / "01_genero" / "parlamentares_genero_desconhecido.csv")
    template = pd.DataFrame(columns=REVIEW_COLUMNS)
    template_path = write_dataframe_atomic(template, output_root / "01_genero" / "revisao_genero.csv")
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="01_genero_setup",
        inputs=[{"path": str(periods_path)}],
        outputs=[artifact_record(output_path, rows=len(unknowns)), artifact_record(template_path, rows=0)],
        counts={"unknown_parliamentarians": len(unknowns)},
    )
    manifest_path = write_json_atomic(output_root / "01_genero" / "manifest_setup.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def publish_gender_review(
    *,
    data_root: str | Path,
    run_id: str,
    review_path: str | Path,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    output_root = Path(data_root) / config.output_relative_path / run_id
    review = pd.read_csv(review_path, dtype=str, keep_default_na=False)
    if "genero_presumido" in review:
        review["genero_presumido"] = review["genero_presumido"].str.casefold().isin({"true", "1", "sim"})
    approved = publish_approved_gender_enrichment(review)
    output = write_dataframe_atomic(approved, output_root / "01_genero" / "genero_enriquecido_aprovado.parquet")
    manifest = base_manifest(
        config=config,
        run_id=run_id,
        stage="01_genero_publicacao",
        inputs=[{"path": str(review_path)}],
        outputs=[artifact_record(output, rows=len(approved))],
        counts={"reviewed_rows": len(review), "published_rows": len(approved)},
    )
    manifest_path = write_json_atomic(output_root / "01_genero" / "manifest_publicacao.json", manifest)
    return {**manifest, "manifest_path": str(manifest_path)}
