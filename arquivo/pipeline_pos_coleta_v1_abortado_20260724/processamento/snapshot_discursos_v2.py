from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

import duckdb
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator, FormatChecker

from relatorios_operacionais import (
    ArtifactRef,
    CountRow,
    ReportArtifact,
    append_log_event,
    build_manifest,
    render_report,
    write_minimal_failure_record,
    write_operation_bundle,
)


APPROVED_PARQUET_ROOT = Path(
    "/content/drive/MyDrive/falando_nela/data/"
    "processed/textos_parlamentares/v1/parquet"
)
DEFAULT_SMOKE_OUTPUT_BASE = Path("/content/falando_nela_snapshot_v2_smoke")
PERIOD_START = date(2010, 1, 1)
PERIOD_END = date(2026, 7, 13)
DEFAULT_ROWS_PER_BASE = 20
MAX_SMOKE_ROWS_PER_BASE = 1_000
SPEC_REF = (
    "specs/reinicio_analise_plenario/"
    "04_snapshot_discursos_v2/requirements.md"
)
SPEC_VERSION = "approved-20260723-schema-v2"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "specs"
    / "reinicio_analise_plenario"
    / "04_snapshot_discursos_v2"
    / "schema"
    / "snapshot_discursos_v2.record.schema.json"
)


@dataclass(frozen=True)
class SnapshotInput:
    filename: str
    expected_source: str
    expected_dataset: str
    expected_ambito: str
    expected_unit: str


SNAPSHOT_INPUTS = (
    SnapshotInput(
        "camara__plenario_discursos.parquet",
        "camara",
        "plenario_discursos",
        "plenario",
        "discurso",
    ),
    SnapshotInput(
        "senado__plenario_discursos.parquet",
        "senado",
        "plenario_discursos",
        "plenario",
        "pronunciamento",
    ),
    SnapshotInput(
        "senado__congresso_discursos.parquet",
        "senado",
        "congresso_discursos",
        "congresso",
        "pronunciamento",
    ),
)
SNAPSHOT_INPUT_FILENAMES = tuple(item.filename for item in SNAPSHOT_INPUTS)

DERIVED_FIELDS = frozenset(
    {
        "snapshot_id",
        "input_parquet",
        "unidade_snapshot",
        "autor_disponivel",
        "qualidade_flags",
    }
)
SNAPSHOT_FIELDS = (
    "snapshot_id",
    "texto_id",
    "dataset_version",
    "input_parquet",
    "source",
    "dataset",
    "casa",
    "ambito",
    "orgao_sigla",
    "orgao_nome",
    "documento_tipo",
    "unidade_analitica",
    "unidade_snapshot",
    "data",
    "data_hora",
    "ano",
    "mes",
    "titulo",
    "resumo",
    "indexacao",
    "tipo_discurso",
    "tipo_uso_palavra",
    "fase_evento",
    "parlamentar_id",
    "parlamentar_nome",
    "parlamentar_partido",
    "parlamentar_uf",
    "parlamentar_cargo",
    "autor_disponivel",
    "pronunciamento_id",
    "sessao_id",
    "evento_id",
    "texto",
    "texto_tamanho",
    "texto_status",
    "forma",
    "metodo_obtencao",
    "url_texto",
    "url_audio",
    "url_video",
    "url_origem",
    "raw_run_id",
    "raw_record_type",
    "raw_source_id",
    "raw_partition",
    "raw_collected_at",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
    "qualidade_flags",
)
REQUIRED_INPUT_COLUMNS = tuple(
    field for field in SNAPSHOT_FIELDS if field not in DERIVED_FIELDS
)
STRING_FIELDS = frozenset(
    field
    for field in REQUIRED_INPUT_COLUMNS
    if field not in {"data", "ano", "mes", "texto_tamanho"}
)
EXCLUSION_FIELDS = (
    "snapshot_id",
    "input_parquet",
    "texto_id",
    "data_original",
    "motivo_exclusao",
    "raw_run_id",
    "raw_record_type",
    "raw_source_id",
    "raw_partition",
    "raw_collected_at",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
)
STAGE_FIELDS = (
    "scope",
    "candidate_file",
    "stage",
    "records",
    "rule",
)
BASE_COUNT_FIELDS = (
    "candidate_file",
    "source_records",
    "within_period",
    "invalid_or_missing_date",
    "before_period",
    "after_period",
    "smoke_snapshot_rows",
    "smoke_excluded_rows",
)
YEAR_COUNT_FIELDS = (
    "candidate_file",
    "source",
    "dataset",
    "ambito",
    "year",
    "records",
)
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


def write_snapshot_v2_smoke(
    *,
    parquet_root: Path,
    output_base: Path,
    operation_id: str,
    snapshot_id: str,
    code_commit: str,
    rows_per_base: int = DEFAULT_ROWS_PER_BASE,
) -> dict[str, Any]:
    """Produz uma amostra técnica do snapshot v2 fora do Drive."""

    parquet_root = parquet_root.expanduser().resolve()
    output_base = output_base.expanduser().resolve()
    operation_root = output_base / operation_id
    input_paths = tuple(
        parquet_root / item.filename for item in SNAPSHOT_INPUTS
    )
    _validate_preflight(
        parquet_root=parquet_root,
        output_base=output_base,
        operation_root=operation_root,
        input_paths=input_paths,
        operation_id=operation_id,
        snapshot_id=snapshot_id,
        code_commit=code_commit,
        rows_per_base=rows_per_base,
    )
    before = _input_signature(input_paths)
    started_at = _utc_now()
    append_log_event(
        operation_root,
        level="INFO",
        event="snapshot_v2_smoke_started",
        message="Smoke determinístico do snapshot v2 iniciado.",
        details={
            "candidate_files": list(SNAPSHOT_INPUT_FILENAMES),
            "rows_per_base": rows_per_base,
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
        },
        at=started_at,
    )

    try:
        artifact_root = operation_root / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=True)
        snapshot_path = artifact_root / "snapshot_discursos_v2.parquet"
        exclusions_path = artifact_root / "registros_excluidos.parquet"

        connection = duckdb.connect(":memory:")
        try:
            input_counts = _inspect_inputs(connection, parquet_root)
            duplicate_ids = _count_global_duplicate_ids(
                connection,
                parquet_root,
            )
            _assert_inputs_can_be_sampled(
                input_counts=input_counts,
                duplicate_ids=duplicate_ids,
            )
            _write_smoke_snapshot(
                connection,
                parquet_root=parquet_root,
                snapshot_path=snapshot_path,
                snapshot_id=snapshot_id,
                rows_per_base=rows_per_base,
            )
            _write_smoke_exclusions(
                connection,
                parquet_root=parquet_root,
                exclusions_path=exclusions_path,
                snapshot_id=snapshot_id,
                rows_per_base=rows_per_base,
            )
            smoke_counts = _inspect_smoke_outputs(
                connection,
                snapshot_path=snapshot_path,
                exclusions_path=exclusions_path,
            )
            year_counts = _inspect_output_years(connection, snapshot_path)
        finally:
            connection.close()

        _validate_snapshot_records(snapshot_path)
        _validate_exclusion_records(exclusions_path)
        _assert_reconciliation(input_counts, smoke_counts)

        stage_rows = _stage_rows(input_counts, smoke_counts)
        base_rows = _base_count_rows(input_counts, smoke_counts)
        _write_csv(
            artifact_root / "contagens_por_etapa.csv",
            stage_rows,
            STAGE_FIELDS,
        )
        _write_csv(
            artifact_root / "contagens_por_base.csv",
            base_rows,
            BASE_COUNT_FIELDS,
        )
        _write_csv(
            artifact_root / "contagens_por_ano.csv",
            year_counts,
            YEAR_COUNT_FIELDS,
        )

        schema_copy = artifact_root / "schema.json"
        shutil.copyfile(SCHEMA_PATH, schema_copy)

        config = {
            "mode": "smoke",
            "parquet_root": str(parquet_root),
            "candidate_files": list(SNAPSHOT_INPUT_FILENAMES),
            "output_base": str(output_base),
            "period_start": PERIOD_START.isoformat(),
            "period_end": PERIOD_END.isoformat(),
            "rows_per_base_per_outcome": rows_per_base,
            "selection_order": "texto_id_ascending",
            "deduplication": "none",
            "writes_to_drive": False,
            "uses_openai": False,
            "promotable": False,
        }
        config_path = artifact_root / "config.json"
        config_text = (
            json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )
        config_path.write_text(config_text, encoding="utf-8")
        config_hash = sha256(config_text.encode("utf-8")).hexdigest()

        after = _input_signature(input_paths)
        if before != after:
            raise RuntimeError(
                "Ao menos uma entrada mudou durante o smoke; "
                "o resultado não é confiável."
            )

        output_paths = (
            snapshot_path,
            exclusions_path,
            schema_copy,
            artifact_root / "contagens_por_etapa.csv",
            artifact_root / "contagens_por_base.csv",
            artifact_root / "contagens_por_ano.csv",
            config_path,
        )
        output_refs = [
            _artifact_ref(
                path,
                operation_root=operation_root,
                role=_artifact_role(path.name),
            )
            for path in output_paths
        ]
        input_refs = [
            ArtifactRef(
                name=item.filename.removesuffix(".parquet"),
                role="base processada aprovada; somente leitura",
                uri=str(path),
                format="parquet",
                size_bytes=path.stat().st_size,
                rows=int(input_counts[item.filename]["source_records"]),
            )
            for item, path in zip(SNAPSHOT_INPUTS, input_paths, strict=True)
        ]
        manifest_counts = _manifest_counts(
            input_counts=input_counts,
            smoke_counts=smoke_counts,
            duplicate_ids=duplicate_ids,
        )
        finished_at = _utc_now()
        manifest = build_manifest(
            module="snapshot_discursos_v2_smoke",
            operation_id=operation_id,
            snapshot_id=snapshot_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            execution_status="succeeded",
            scientific_gate="needs_review",
            started_at=started_at,
            finished_at=finished_at,
            inputs=input_refs,
            outputs=output_refs,
            counts=manifest_counts,
            config_ref="artifacts/config.json",
            config_hash=config_hash,
        )
        report = render_smoke_report(
            parquet_root=parquet_root,
            operation_id=operation_id,
            snapshot_id=snapshot_id,
            input_refs=input_refs,
            output_refs=output_refs,
            counts=manifest_counts,
            rows_per_base=rows_per_base,
        )
        paths = write_operation_bundle(
            operation_root,
            manifest=manifest,
            report=report,
        )
        append_log_event(
            operation_root,
            level="INFO",
            event="snapshot_v2_smoke_succeeded",
            message=(
                "Smoke concluído; execução integral e promoção permanecem "
                "bloqueadas."
            ),
            details=manifest_counts,
            at=finished_at,
        )
        return {
            "paths": paths,
            "manifest": manifest,
            "input_counts": input_counts,
            "smoke_counts": smoke_counts,
            "year_counts": year_counts,
        }
    except Exception as exc:
        write_minimal_failure_record(
            operation_root,
            module="snapshot_discursos_v2_smoke",
            operation_id=operation_id,
            snapshot_id=snapshot_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            started_at=started_at,
            objective="validar em amostra a transformação do snapshot v2",
            period=f"{PERIOD_START.isoformat()} a {PERIOD_END.isoformat()}",
            unit="intervenção textual oficial de plenário",
            error_summary=f"{type(exc).__name__}: {exc}",
            next_action=(
                "Não execute o universo completo. Corrija a causa e use novos "
                "operation_id e snapshot_id."
            ),
            overwrite=True,
        )
        raise


def render_smoke_report(
    *,
    parquet_root: Path,
    operation_id: str,
    snapshot_id: str,
    input_refs: Sequence[ArtifactRef],
    output_refs: Sequence[ArtifactRef],
    counts: Mapping[str, int],
    rows_per_base: int,
) -> str:
    artifacts = [
        *[
            ReportArtifact(
                "Entrada",
                item.name,
                item.role,
                item.uri,
                "não alterar",
            )
            for item in input_refs
        ],
        *[
            ReportArtifact(
                "Saída temporária",
                item.name,
                item.role,
                item.uri,
                "revisar",
            )
            for item in output_refs
        ],
    ]
    return render_report(
        module="snapshot_discursos_v2_smoke",
        objective="validar em amostra a transformação do snapshot v2",
        operation_id=operation_id,
        snapshot_id=snapshot_id,
        period=f"{PERIOD_START.isoformat()} a {PERIOD_END.isoformat()}",
        unit="intervenção textual oficial de plenário",
        execution_status="succeeded",
        scientific_gate="needs_review",
        result_summary=(
            f"O smoke gravou {counts['snapshot_records']} registros elegíveis "
            f"e {counts['excluded_sample_records']} exclusões de exemplo fora "
            f"do Drive. As {counts['source_records']} linhas das três bases "
            f"foram apenas contadas para reconciliação; o snapshot integral "
            "não foi criado."
        ),
        counts=[
            CountRow(
                "bases aprovadas",
                counts["candidate_files"],
                "três Parquets autorizados por D03",
            ),
            CountRow(
                "registros nas fontes",
                counts["source_records"],
                "universo completo apenas para contagens de controle",
            ),
            CountRow(
                "registros dentro do período",
                counts["within_period_records"],
                "datas entre D04, inclusive",
            ),
            CountRow(
                "registros fora do período ou sem data válida",
                counts["excluded_source_records"],
                "fontes completas; nenhum arquivo de origem foi alterado",
            ),
            CountRow(
                "registros no snapshot de smoke",
                counts["snapshot_records"],
                (
                    f"até {rows_per_base} elegíveis por base em ordem "
                    "determinística"
                ),
            ),
            CountRow(
                "exclusões na amostra de smoke",
                counts["excluded_sample_records"],
                (
                    f"até {rows_per_base} excluídos por base em ordem "
                    "determinística"
                ),
            ),
            CountRow(
                "IDs duplicados globais",
                counts["duplicate_ids"],
                "qualquer valor acima de zero interrompe o smoke",
            ),
        ],
        artifacts=artifacts,
        warnings=[
            "Este é um artefato técnico de amostra e não pode ser promovido.",
            (
                "Os hashes integrais das entradas serão calculados somente na "
                "execução completa autorizada."
            ),
        ],
        next_action=(
            "Revise `relatorio.md`, `artifacts/contagens_por_base.csv` e uma "
            "pequena amostra do Parquet principal. Não copie a saída ao Drive "
            "nem execute o universo completo antes do próximo gate."
        ),
    )


def _validate_preflight(
    *,
    parquet_root: Path,
    output_base: Path,
    operation_root: Path,
    input_paths: Sequence[Path],
    operation_id: str,
    snapshot_id: str,
    code_commit: str,
    rows_per_base: int,
) -> None:
    if not parquet_root.is_dir():
        raise FileNotFoundError(f"Raiz Parquet ausente: {parquet_root}")
    missing = [path.name for path in input_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Bases aprovadas ausentes: {missing}")
    if _is_relative_to(output_base, parquet_root):
        raise ValueError("A saída temporária não pode ficar dentro da entrada.")
    if _is_relative_to(parquet_root, output_base):
        raise ValueError("A entrada não pode ficar dentro da saída temporária.")
    if operation_root.exists() and any(operation_root.iterdir()):
        raise FileExistsError(
            f"operation_id já possui artefatos: {operation_root}"
        )
    for label, value in (
        ("operation_id", operation_id),
        ("snapshot_id", snapshot_id),
    ):
        if not ID_PATTERN.fullmatch(value):
            raise ValueError(
                f"{label} deve usar 3–128 caracteres minúsculos, números, "
                "ponto, hífen ou sublinhado."
            )
    if not code_commit.strip():
        raise ValueError("code_commit é obrigatório.")
    if not 1 <= rows_per_base <= MAX_SMOKE_ROWS_PER_BASE:
        raise ValueError(
            f"rows_per_base deve estar entre 1 e {MAX_SMOKE_ROWS_PER_BASE}."
        )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    for item, path in zip(SNAPSHOT_INPUTS, input_paths, strict=True):
        columns = set(pq.ParquetFile(path).schema_arrow.names)
        missing_columns = sorted(set(REQUIRED_INPUT_COLUMNS) - columns)
        if missing_columns:
            raise ValueError(
                f"{item.filename} não possui colunas exigidas: "
                f"{missing_columns}"
            )


def _inspect_inputs(
    connection: duckdb.DuckDBPyConnection,
    parquet_root: Path,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for item in SNAPSHOT_INPUTS:
        path = parquet_root / item.filename
        parsed_date = "try_cast(data AS DATE)"
        texto_id = _clean_string("texto_id")
        texto = _clean_string("texto")
        raw_path = _clean_string("raw_path")
        raw_source_id = _clean_string("raw_source_id")
        query = f"""
            SELECT
                count(*)::BIGINT AS source_records,
                count(*) FILTER (
                    WHERE {parsed_date} BETWEEN DATE '{PERIOD_START.isoformat()}'
                        AND DATE '{PERIOD_END.isoformat()}'
                )::BIGINT AS within_period,
                count(*) FILTER (
                    WHERE {parsed_date} IS NULL
                )::BIGINT AS invalid_or_missing_date,
                count(*) FILTER (
                    WHERE {parsed_date} < DATE '{PERIOD_START.isoformat()}'
                )::BIGINT AS before_period,
                count(*) FILTER (
                    WHERE {parsed_date} > DATE '{PERIOD_END.isoformat()}'
                )::BIGINT AS after_period,
                count(*) FILTER (WHERE {texto_id} IS NULL)::BIGINT
                    AS missing_texto_id,
                count(*) FILTER (WHERE {texto} IS NULL)::BIGINT
                    AS missing_text,
                count(*) FILTER (
                    WHERE {raw_path} IS NULL AND {raw_source_id} IS NULL
                )::BIGINT AS missing_provenance,
                count(*) FILTER (
                    WHERE {_clean_string("dataset_version")} IS DISTINCT FROM 'v1'
                       OR {_clean_string("source")} IS DISTINCT FROM
                            '{_sql_literal(item.expected_source)}'
                       OR {_clean_string("dataset")} IS DISTINCT FROM
                            '{_sql_literal(item.expected_dataset)}'
                       OR {_clean_string("ambito")} IS DISTINCT FROM
                            '{_sql_literal(item.expected_ambito)}'
                       OR {_clean_string("documento_tipo")} IS DISTINCT FROM
                            'discurso'
                       OR {_clean_string("unidade_analitica")} IS DISTINCT FROM
                            '{_sql_literal(item.expected_unit)}'
                       OR {_clean_string("casa")} IS NULL
                )::BIGINT AS contract_violations
            FROM read_parquet('{_sql_literal(str(path))}')
        """
        row = _fetch_one(connection, query)
        counts[item.filename] = {
            key: int(value) for key, value in row.items()
        }
    return counts


def _count_global_duplicate_ids(
    connection: duckdb.DuckDBPyConnection,
    parquet_root: Path,
) -> int:
    union = " UNION ALL ".join(
        (
            "SELECT "
            f"{_clean_string('texto_id')} AS texto_id "
            f"FROM read_parquet('{_sql_literal(str(parquet_root / item.filename))}')"
        )
        for item in SNAPSHOT_INPUTS
    )
    query = f"""
        SELECT count(*)::BIGINT
        FROM (
            SELECT texto_id
            FROM ({union})
            WHERE texto_id IS NOT NULL
            GROUP BY texto_id
            HAVING count(*) > 1
        )
    """
    return int(connection.execute(query).fetchone()[0])


def _assert_inputs_can_be_sampled(
    *,
    input_counts: Mapping[str, Mapping[str, int]],
    duplicate_ids: int,
) -> None:
    problems = []
    for filename, row in input_counts.items():
        for field in (
            "missing_texto_id",
            "missing_text",
            "missing_provenance",
            "contract_violations",
        ):
            value = int(row[field])
            if value:
                problems.append(f"{filename}: {field}={value}")
    if duplicate_ids:
        problems.append(f"duplicate_ids={duplicate_ids}")
    if problems:
        raise ValueError(
            "Entradas violam o contrato aprovado: " + "; ".join(problems)
        )


def _write_smoke_snapshot(
    connection: duckdb.DuckDBPyConnection,
    *,
    parquet_root: Path,
    snapshot_path: Path,
    snapshot_id: str,
    rows_per_base: int,
) -> None:
    queries = [
        _snapshot_select(
            path=parquet_root / item.filename,
            input_filename=item.filename,
            snapshot_id=snapshot_id,
            rows_per_base=rows_per_base,
        )
        for item in SNAPSHOT_INPUTS
    ]
    union = " UNION ALL ".join(f"({query})" for query in queries)
    connection.execute(
        f"""
        COPY (
            SELECT *
            FROM ({union})
            ORDER BY texto_id, input_parquet
        )
        TO '{_sql_literal(str(snapshot_path))}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def _snapshot_select(
    *,
    path: Path,
    input_filename: str,
    snapshot_id: str,
    rows_per_base: int,
) -> str:
    expressions = {
        "snapshot_id": f"'{_sql_literal(snapshot_id)}'",
        "input_parquet": f"'{_sql_literal(input_filename)}'",
        "unidade_snapshot": "'intervencao_textual_oficial'",
        "data": "try_cast(data AS DATE)",
        "ano": "year(try_cast(data AS DATE))::INTEGER",
        "mes": "month(try_cast(data AS DATE))::INTEGER",
        "texto_tamanho": "length(cast(texto AS VARCHAR))::BIGINT",
        "autor_disponivel": (
            f"({_clean_string('parlamentar_nome')} IS NOT NULL)"
        ),
        "qualidade_flags": _quality_flags_expr(),
    }
    for field in STRING_FIELDS:
        expressions[field] = _clean_string(field)
    select_list = ",\n                ".join(
        f"{expressions[field]} AS {_quote_identifier(field)}"
        for field in SNAPSHOT_FIELDS
    )
    return f"""
        SELECT
            {select_list}
        FROM read_parquet('{_sql_literal(str(path))}')
        WHERE try_cast(data AS DATE) BETWEEN DATE '{PERIOD_START.isoformat()}'
            AND DATE '{PERIOD_END.isoformat()}'
        ORDER BY {_clean_string("texto_id")}
        LIMIT {rows_per_base}
    """


def _write_smoke_exclusions(
    connection: duckdb.DuckDBPyConnection,
    *,
    parquet_root: Path,
    exclusions_path: Path,
    snapshot_id: str,
    rows_per_base: int,
) -> None:
    queries = [
        _exclusion_select(
            path=parquet_root / item.filename,
            input_filename=item.filename,
            snapshot_id=snapshot_id,
            rows_per_base=rows_per_base,
        )
        for item in SNAPSHOT_INPUTS
    ]
    union = " UNION ALL ".join(f"({query})" for query in queries)
    connection.execute(
        f"""
        COPY (
            SELECT *
            FROM ({union})
            ORDER BY input_parquet, texto_id, data_original
        )
        TO '{_sql_literal(str(exclusions_path))}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )


def _exclusion_select(
    *,
    path: Path,
    input_filename: str,
    snapshot_id: str,
    rows_per_base: int,
) -> str:
    parsed_date = "try_cast(data AS DATE)"
    reason = f"""
        CASE
            WHEN {parsed_date} IS NULL THEN 'data_invalida_ou_ausente'
            WHEN {parsed_date} < DATE '{PERIOD_START.isoformat()}'
                THEN 'data_anterior_ao_periodo'
            WHEN {parsed_date} > DATE '{PERIOD_END.isoformat()}'
                THEN 'data_posterior_ao_periodo'
        END
    """
    return f"""
        SELECT
            '{_sql_literal(snapshot_id)}' AS snapshot_id,
            '{_sql_literal(input_filename)}' AS input_parquet,
            {_clean_string("texto_id")} AS texto_id,
            cast(data AS VARCHAR) AS data_original,
            {reason} AS motivo_exclusao,
            {_clean_string("raw_run_id")} AS raw_run_id,
            {_clean_string("raw_record_type")} AS raw_record_type,
            {_clean_string("raw_source_id")} AS raw_source_id,
            {_clean_string("raw_partition")} AS raw_partition,
            {_clean_string("raw_collected_at")} AS raw_collected_at,
            {_clean_string("raw_checksum")} AS raw_checksum,
            {_clean_string("raw_path")} AS raw_path,
            {_clean_string("raw_response_url")} AS raw_response_url
        FROM read_parquet('{_sql_literal(str(path))}')
        WHERE {parsed_date} IS NULL
           OR {parsed_date} < DATE '{PERIOD_START.isoformat()}'
           OR {parsed_date} > DATE '{PERIOD_END.isoformat()}'
        ORDER BY {_clean_string("texto_id")}, cast(data AS VARCHAR)
        LIMIT {rows_per_base}
    """


def _quality_flags_expr() -> str:
    rules = (
        ("parlamentar_nome", "autor_ausente"),
        ("parlamentar_partido", "partido_ausente"),
        ("parlamentar_uf", "uf_ausente"),
        ("data_hora", "data_hora_ausente"),
        ("sessao_id", "sessao_id_ausente"),
        ("evento_id", "evento_id_ausente"),
        ("pronunciamento_id", "pronunciamento_id_ausente"),
    )
    items = ", ".join(
        (
            f"CASE WHEN {_clean_string(field)} IS NULL "
            f"THEN '{flag}' END"
        )
        for field, flag in rules
    )
    return f"list_filter([{items}], item -> item IS NOT NULL)"


def _inspect_smoke_outputs(
    connection: duckdb.DuckDBPyConnection,
    *,
    snapshot_path: Path,
    exclusions_path: Path,
) -> dict[str, dict[str, int]]:
    counts = {
        item.filename: {
            "snapshot_rows": 0,
            "excluded_rows": 0,
        }
        for item in SNAPSHOT_INPUTS
    }
    for path, field in (
        (snapshot_path, "snapshot_rows"),
        (exclusions_path, "excluded_rows"),
    ):
        rows = connection.execute(
            f"""
            SELECT input_parquet, count(*)::BIGINT AS records
            FROM read_parquet('{_sql_literal(str(path))}')
            GROUP BY input_parquet
            """
        ).fetchall()
        for filename, records in rows:
            counts[str(filename)][field] = int(records)
    return counts


def _inspect_output_years(
    connection: duckdb.DuckDBPyConnection,
    snapshot_path: Path,
) -> list[dict[str, Any]]:
    cursor = connection.execute(
        f"""
        SELECT
            input_parquet AS candidate_file,
            source,
            dataset,
            ambito,
            ano AS year,
            count(*)::BIGINT AS records
        FROM read_parquet('{_sql_literal(str(snapshot_path))}')
        GROUP BY input_parquet, source, dataset, ambito, ano
        ORDER BY input_parquet, ano
        """
    )
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _validate_snapshot_records(snapshot_path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    table = pq.read_table(snapshot_path)
    if str(table.schema.field("data").type) != "date32[day]":
        raise ValueError("O campo data do snapshot deve usar date32.")
    if table.column_names != list(SNAPSHOT_FIELDS):
        raise ValueError("Ordem ou conjunto de campos do snapshot diverge do schema.")

    ids = []
    for index, record in enumerate(table.to_pylist(), start=1):
        record["data"] = record["data"].isoformat()
        errors = sorted(
            validator.iter_errors(record),
            key=lambda item: list(item.path),
        )
        if errors:
            detail = "; ".join(
                f"{'.'.join(map(str, error.path)) or '$'}: {error.message}"
                for error in errors
            )
            raise ValueError(f"Registro de smoke {index} inválido: {detail}")
        ids.append(str(record["texto_id"]))
    if ids != sorted(ids):
        raise ValueError("O snapshot de smoke não está ordenado por texto_id.")
    if len(ids) != len(set(ids)):
        raise ValueError("O snapshot de smoke contém texto_id duplicado.")


def _validate_exclusion_records(exclusions_path: Path) -> None:
    table = pq.read_table(exclusions_path)
    if table.column_names != list(EXCLUSION_FIELDS):
        raise ValueError("Schema dos registros excluídos diverge do contrato.")
    allowed = {
        "data_invalida_ou_ausente",
        "data_anterior_ao_periodo",
        "data_posterior_ao_periodo",
    }
    for row in table.to_pylist():
        if row["motivo_exclusao"] not in allowed:
            raise ValueError("Motivo de exclusão inválido.")
        if not row["raw_path"] and not row["raw_source_id"]:
            raise ValueError("Registro excluído sem proveniência.")


def _assert_reconciliation(
    input_counts: Mapping[str, Mapping[str, int]],
    smoke_counts: Mapping[str, Mapping[str, int]],
) -> None:
    for filename, row in input_counts.items():
        source_records = int(row["source_records"])
        reconciled = sum(
            int(row[field])
            for field in (
                "within_period",
                "invalid_or_missing_date",
                "before_period",
                "after_period",
            )
        )
        if source_records != reconciled:
            raise RuntimeError(
                f"Reconciliação integral falhou para {filename}: "
                f"{source_records} != {reconciled}."
            )
        smoke = smoke_counts[filename]
        if int(smoke["snapshot_rows"]) > int(row["within_period"]):
            raise RuntimeError(f"Smoke excedeu o universo elegível de {filename}.")
        excluded_source = sum(
            int(row[field])
            for field in (
                "invalid_or_missing_date",
                "before_period",
                "after_period",
            )
        )
        if int(smoke["excluded_rows"]) > excluded_source:
            raise RuntimeError(
                f"Smoke excedeu o universo excluído de {filename}."
            )


def _stage_rows(
    input_counts: Mapping[str, Mapping[str, int]],
    smoke_counts: Mapping[str, Mapping[str, int]],
) -> list[dict[str, Any]]:
    rows = []
    rules = (
        ("source_records", "todas as linhas da base"),
        ("within_period", "data dentro de D04"),
        ("invalid_or_missing_date", "data ausente ou não parseável"),
        ("before_period", "data anterior a 2010-01-01"),
        ("after_period", "data posterior a 2026-07-13"),
    )
    for filename in SNAPSHOT_INPUT_FILENAMES:
        for stage, rule in rules:
            rows.append(
                {
                    "scope": "fonte_completa",
                    "candidate_file": filename,
                    "stage": stage,
                    "records": int(input_counts[filename][stage]),
                    "rule": rule,
                }
            )
        rows.extend(
            [
                {
                    "scope": "amostra_smoke",
                    "candidate_file": filename,
                    "stage": "snapshot_rows",
                    "records": int(smoke_counts[filename]["snapshot_rows"]),
                    "rule": "amostra determinística de elegíveis",
                },
                {
                    "scope": "amostra_smoke",
                    "candidate_file": filename,
                    "stage": "excluded_rows",
                    "records": int(smoke_counts[filename]["excluded_rows"]),
                    "rule": "amostra determinística de excluídos por D04",
                },
            ]
        )
    return rows


def _base_count_rows(
    input_counts: Mapping[str, Mapping[str, int]],
    smoke_counts: Mapping[str, Mapping[str, int]],
) -> list[dict[str, int | str]]:
    rows = []
    for filename in SNAPSHOT_INPUT_FILENAMES:
        source = input_counts[filename]
        smoke = smoke_counts[filename]
        rows.append(
            {
                "candidate_file": filename,
                "source_records": int(source["source_records"]),
                "within_period": int(source["within_period"]),
                "invalid_or_missing_date": int(
                    source["invalid_or_missing_date"]
                ),
                "before_period": int(source["before_period"]),
                "after_period": int(source["after_period"]),
                "smoke_snapshot_rows": int(smoke["snapshot_rows"]),
                "smoke_excluded_rows": int(smoke["excluded_rows"]),
            }
        )
    return rows


def _manifest_counts(
    *,
    input_counts: Mapping[str, Mapping[str, int]],
    smoke_counts: Mapping[str, Mapping[str, int]],
    duplicate_ids: int,
) -> dict[str, int]:
    return {
        "candidate_files": len(SNAPSHOT_INPUTS),
        "source_records": sum(
            int(row["source_records"]) for row in input_counts.values()
        ),
        "within_period_records": sum(
            int(row["within_period"]) for row in input_counts.values()
        ),
        "excluded_source_records": sum(
            int(row["invalid_or_missing_date"])
            + int(row["before_period"])
            + int(row["after_period"])
            for row in input_counts.values()
        ),
        "snapshot_records": sum(
            int(row["snapshot_rows"]) for row in smoke_counts.values()
        ),
        "excluded_sample_records": sum(
            int(row["excluded_rows"]) for row in smoke_counts.values()
        ),
        "duplicate_ids": duplicate_ids,
    }


def _artifact_ref(
    path: Path,
    *,
    operation_root: Path,
    role: str,
) -> ArtifactRef:
    rows = None
    if path.suffix == ".parquet":
        rows = pq.ParquetFile(path).metadata.num_rows
    elif path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = max(sum(1 for _ in handle) - 1, 0)
    return ArtifactRef(
        name=path.stem,
        role=role,
        uri=str(path.relative_to(operation_root)),
        format=path.suffix.removeprefix("."),
        size_bytes=path.stat().st_size,
        sha256=_sha256_file(path),
        rows=rows,
    )


def _artifact_role(filename: str) -> str:
    return {
        "snapshot_discursos_v2.parquet": "snapshot técnico de amostra",
        "registros_excluidos.parquet": "amostra auditável de exclusões D04",
        "schema.json": "schema efetivo dos registros",
        "contagens_por_etapa.csv": "reconciliação por regra e escopo",
        "contagens_por_base.csv": "cobertura e amostra por base",
        "contagens_por_ano.csv": "cobertura anual da amostra incluída",
        "config.json": "configuração efetiva do smoke",
    }[filename]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _input_signature(paths: Sequence[Path]) -> dict[str, tuple[int, int]]:
    return {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_one(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> dict[str, Any]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Consulta de contagem não retornou linha.")
    return dict(zip(columns, row, strict=True))


def _clean_string(field: str) -> str:
    return (
        f"nullif(trim(cast({_quote_identifier(field)} AS VARCHAR)), '')"
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
