from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import duckdb
import pyarrow.parquet as pq

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
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_snapshot_census")
SPEC_REF = (
    "specs/reinicio_analise_plenario/"
    "04_snapshot_discursos_v2/requirements.md"
)
SPEC_VERSION = "approved-20260723-census-gate"


@dataclass(frozen=True)
class CandidateBase:
    filename: str
    expected_source: str
    expected_dataset: str


CANDIDATE_BASES = (
    CandidateBase(
        "camara__plenario_discursos.parquet",
        "camara",
        "plenario_discursos",
    ),
    CandidateBase(
        "senado__plenario_discursos.parquet",
        "senado",
        "plenario_discursos",
    ),
    CandidateBase(
        "senado__congresso_discursos.parquet",
        "senado",
        "congresso_discursos",
    ),
)
CANDIDATE_FILENAMES = tuple(base.filename for base in CANDIDATE_BASES)

REQUIRED_COLUMNS = (
    "texto_id",
    "dataset_version",
    "source",
    "dataset",
    "ambito",
    "documento_tipo",
    "unidade_analitica",
    "data",
    "ano",
    "texto_tamanho",
    "texto_status",
    "parlamentar_nome",
    "raw_path",
    "raw_source_id",
)
CATEGORY_COLUMNS = (
    "source",
    "dataset",
    "ambito",
    "documento_tipo",
    "unidade_analitica",
    "texto_status",
)

BASE_FIELDS = (
    "candidate_file",
    "expected_source",
    "expected_dataset",
    "size_bytes",
    "row_groups",
    "columns",
    "records",
    "date_min",
    "date_max",
    "ids_missing",
    "ids_distinct",
    "duplicate_id_rows",
    "text_nonempty",
    "author_nonempty",
    "provenance_nonempty",
    "unexpected_source_rows",
    "unexpected_dataset_rows",
    "invalid_date_rows",
)
YEAR_FIELDS = (
    "candidate_file",
    "source",
    "dataset",
    "ambito",
    "year",
    "records",
    "text_nonempty",
    "author_nonempty",
)
CATEGORY_FIELDS = (
    "candidate_file",
    "dimension",
    "value",
    "records",
)
OVERLAP_FIELDS = (
    "left_candidate",
    "right_candidate",
    "shared_ids",
)
SCHEMA_FIELDS = (
    "candidate_file",
    "column",
    "arrow_type",
    "required",
)
ISSUE_FIELDS = (
    "issue_type",
    "severity",
    "candidate_file",
    "count",
    "detail",
)


def write_snapshot_candidate_census(
    *,
    parquet_root: Path,
    output_base: Path,
    operation_id: str,
    code_commit: str,
) -> dict[str, Any]:
    """Censa três Parquets candidatos sem alterá-los nem criar um snapshot."""

    parquet_root = parquet_root.expanduser().resolve()
    output_base = output_base.expanduser().resolve()
    operation_root = output_base / operation_id
    candidate_paths = tuple(parquet_root / name for name in CANDIDATE_FILENAMES)
    _validate_preflight(
        parquet_root=parquet_root,
        output_base=output_base,
        operation_root=operation_root,
        candidate_paths=candidate_paths,
        operation_id=operation_id,
        code_commit=code_commit,
    )
    before = _input_signature(candidate_paths)
    started_at = _utc_now()
    append_log_event(
        operation_root,
        level="INFO",
        event="snapshot_census_started",
        message="Censo somente leitura das bases candidatas iniciado.",
        details={"candidate_files": list(CANDIDATE_FILENAMES)},
        at=started_at,
    )

    try:
        census = inspect_candidate_parquets(parquet_root)
        artifact_root = operation_root / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=True)
        artifact_specs = (
            (
                "censo_bases.csv",
                census["bases"],
                BASE_FIELDS,
                "resumo por base candidata",
            ),
            (
                "contagens_anuais.csv",
                census["years"],
                YEAR_FIELDS,
                "cobertura anual por base e arena",
            ),
            (
                "categorias.csv",
                census["categories"],
                CATEGORY_FIELDS,
                "valores observados nas dimensões centrais",
            ),
            (
                "sobreposicoes_ids.csv",
                census["overlaps"],
                OVERLAP_FIELDS,
                "IDs compartilhados entre bases candidatas",
            ),
            (
                "schema_bases.csv",
                census["schemas"],
                SCHEMA_FIELDS,
                "schema observado em cada Parquet",
            ),
            (
                "inconsistencias.csv",
                census["issues"],
                ISSUE_FIELDS,
                "achados que exigem revisão antes de D03",
            ),
        )
        output_refs: list[ArtifactRef] = []
        for name, rows, fields, role in artifact_specs:
            path = artifact_root / name
            _write_csv(path, rows, fields)
            output_refs.append(
                _artifact_ref(
                    path,
                    operation_root=operation_root,
                    role=role,
                    rows=len(rows),
                )
            )

        map_path = artifact_root / "mapa_censo.md"
        map_path.write_text(
            render_census_map(
                bases=census["bases"],
                overlaps=census["overlaps"],
                issues=census["issues"],
            ),
            encoding="utf-8",
        )
        output_refs.append(
            _artifact_ref(
                map_path,
                operation_root=operation_root,
                role="mapa humano das bases candidatas",
                rows=None,
            )
        )

        config = {
            "parquet_root": str(parquet_root),
            "candidate_files": list(CANDIDATE_FILENAMES),
            "read_policy": (
                "parquet_metadata_and_control_columns_without_full_text"
            ),
            "write_policy": "temporary_output_outside_drive",
            "creates_snapshot": False,
            "uses_openai": False,
        }
        config_path = artifact_root / "config.json"
        config_text = (
            json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )
        config_path.write_text(config_text, encoding="utf-8")
        config_hash = sha256(config_text.encode("utf-8")).hexdigest()
        output_refs.append(
            _artifact_ref(
                config_path,
                operation_root=operation_root,
                role="configuração efetiva do censo",
                rows=None,
            )
        )

        after = _input_signature(candidate_paths)
        if before != after:
            raise RuntimeError(
                "Ao menos uma entrada mudou durante o censo; resultado não confiável."
            )

        counts = _manifest_counts(census)
        input_refs = [
            ArtifactRef(
                name=base.filename.removesuffix(".parquet"),
                role="base processada candidata ao snapshot v2",
                uri=str(parquet_root / base.filename),
                format="parquet",
                size_bytes=int(summary["size_bytes"]),
                rows=int(summary["records"]),
            )
            for base, summary in zip(CANDIDATE_BASES, census["bases"], strict=True)
        ]
        finished_at = _utc_now()
        manifest = build_manifest(
            module="snapshot_candidate_census",
            operation_id=operation_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            execution_status="succeeded",
            scientific_gate="needs_review",
            started_at=started_at,
            finished_at=finished_at,
            inputs=input_refs,
            outputs=output_refs,
            counts=counts,
            config_ref="artifacts/config.json",
            config_hash=config_hash,
            warnings_ref=(
                "artifacts/inconsistencias.csv"
                if census["issues"]
                else None
            ),
        )
        report = render_census_report(
            parquet_root=parquet_root,
            operation_id=operation_id,
            bases=census["bases"],
            issues=census["issues"],
            input_refs=input_refs,
            output_refs=output_refs,
            counts=counts,
        )
        paths = write_operation_bundle(
            operation_root,
            manifest=manifest,
            report=report,
        )
        append_log_event(
            operation_root,
            level="INFO",
            event="snapshot_census_succeeded",
            message="Censo concluído; D03 permanece pendente.",
            details=counts,
            at=finished_at,
        )
        return {
            "paths": paths,
            "manifest": manifest,
            **census,
        }
    except Exception as exc:
        write_minimal_failure_record(
            operation_root,
            module="snapshot_candidate_census",
            operation_id=operation_id,
            spec_ref=SPEC_REF,
            spec_version=SPEC_VERSION,
            code_commit=code_commit,
            started_at=started_at,
            objective="censar três bases candidatas sem criar snapshot",
            period="todo o período disponível nas entradas",
            unit="registro de textos_parlamentares/v1",
            error_summary=f"{type(exc).__name__}: {exc}",
            next_action=(
                "Não crie o snapshot. Corrija a causa e use um novo operation_id."
            ),
            overwrite=True,
        )
        raise


def inspect_candidate_parquets(parquet_root: Path) -> dict[str, Any]:
    """Lê metadados e colunas de controle dos três Parquets autorizados."""

    parquet_root = parquet_root.expanduser().resolve()
    connection = duckdb.connect(":memory:")
    bases: list[dict[str, Any]] = []
    years: list[dict[str, Any]] = []
    categories: list[dict[str, Any]] = []
    schemas: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    try:
        for candidate in CANDIDATE_BASES:
            path = parquet_root / candidate.filename
            parquet_file = pq.ParquetFile(path)
            arrow_schema = parquet_file.schema_arrow
            columns = set(arrow_schema.names)
            for field in arrow_schema:
                schemas.append(
                    {
                        "candidate_file": candidate.filename,
                        "column": field.name,
                        "arrow_type": str(field.type),
                        "required": str(field.name in REQUIRED_COLUMNS).lower(),
                    }
                )
            for missing in sorted(set(REQUIRED_COLUMNS) - columns):
                issues.append(
                    _issue(
                        "missing_required_column",
                        "warning",
                        candidate.filename,
                        1,
                        missing,
                    )
                )

            summary = _inspect_base(
                connection,
                path=path,
                candidate=candidate,
                columns=columns,
                row_groups=parquet_file.metadata.num_row_groups,
                column_count=len(arrow_schema),
            )
            bases.append(summary)
            years.extend(
                _inspect_years(
                    connection,
                    path=path,
                    candidate=candidate,
                    columns=columns,
                )
            )
            categories.extend(
                _inspect_categories(
                    connection,
                    path=path,
                    candidate=candidate,
                    columns=columns,
                )
            )
            issues.extend(_summary_issues(summary))

        overlaps, global_distinct_ids = _inspect_id_metrics(
            connection,
            parquet_root=parquet_root,
            schemas=schemas,
        )
        issues.extend(
            _issue(
                "texto_id_shared_across_bases",
                "warning",
                (
                    f"{row['left_candidate']} | "
                    f"{row['right_candidate']}"
                ),
                int(row["shared_ids"]),
                "texto_id exato observado em mais de uma base candidata",
            )
            for row in overlaps
        )
    finally:
        connection.close()

    return {
        "bases": bases,
        "years": sorted(
            years,
            key=lambda row: (
                str(row["candidate_file"]),
                str(row["year"]),
            ),
        ),
        "categories": sorted(
            categories,
            key=lambda row: (
                str(row["candidate_file"]),
                str(row["dimension"]),
                str(row["value"]),
            ),
        ),
        "overlaps": overlaps,
        "global_distinct_ids": global_distinct_ids,
        "schemas": sorted(
            schemas,
            key=lambda row: (
                str(row["candidate_file"]),
                str(row["column"]),
            ),
        ),
        "issues": sorted(
            issues,
            key=lambda row: (
                str(row["severity"]),
                str(row["issue_type"]),
                str(row["candidate_file"]),
            ),
        ),
    }


def render_census_map(
    *,
    bases: Sequence[Mapping[str, Any]],
    overlaps: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# Censo das bases candidatas ao snapshot v2",
        "",
        "## Escopo",
        "",
        "- Unidade: registro de `textos_parlamentares/v1`.",
        "- Entradas: três Parquets aprovados para censo somente leitura.",
        "- Texto integral: não carregado.",
        "- Snapshot criado: não.",
        "- Gate: `needs_review`.",
        "",
        "## Cobertura por base",
        "",
        "| Base | Registros | Período | IDs ausentes | Duplicatas internas | "
        "Texto disponível | Autor disponível |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in bases:
        records = int(row["records"])
        lines.append(
            f"| `{_md_cell(row['candidate_file'])}` | {records} | "
            f"{_md_cell(_period(row))} | {row['ids_missing']} | "
            f"{row['duplicate_id_rows']} | "
            f"{row['text_nonempty']} ({_percent(row['text_nonempty'], records)}) | "
            f"{row['author_nonempty']} "
            f"({_percent(row['author_nonempty'], records)}) |"
        )

    lines.extend(["", "## Sobreposição exata de IDs entre bases", ""])
    if overlaps:
        lines.extend(
            [
                "| Base A | Base B | IDs compartilhados |",
                "|---|---|---:|",
                *[
                    f"| `{_md_cell(row['left_candidate'])}` | "
                    f"`{_md_cell(row['right_candidate'])}` | "
                    f"{row['shared_ids']} |"
                    for row in overlaps
                ],
            ]
        )
    else:
        lines.append("Nenhum `texto_id` compartilhado entre bases.")

    issue_counts = Counter(str(row["issue_type"]) for row in issues)
    lines.extend(["", "## Achados para revisão", ""])
    if issue_counts:
        lines.extend(
            [
                "| Tipo | Ocorrências sinalizadas |",
                "|---|---:|",
                *[
                    f"| {_md_cell(name)} | {count} |"
                    for name, count in sorted(issue_counts.items())
                ],
            ]
        )
    else:
        lines.append("Nenhum achado estrutural.")

    lines.extend(
        [
            "",
            "## Próxima ação",
            "",
            "Revisar este mapa e as contagens anuais. A execução não aprova D03, "
            "não deduplica registros e não cria o snapshot v2.",
            "",
        ]
    )
    return "\n".join(lines)


def render_census_report(
    *,
    parquet_root: Path,
    operation_id: str,
    bases: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    input_refs: Sequence[ArtifactRef],
    output_refs: Sequence[ArtifactRef],
    counts: Mapping[str, int],
) -> str:
    dates = [
        str(value)
        for row in bases
        for value in (row.get("date_min"), row.get("date_max"))
        if value
    ]
    period = f"{min(dates)} a {max(dates)}" if dates else "datas não disponíveis"
    artifacts = [
        *[
            ReportArtifact(
                "Entrada",
                item.name,
                item.role,
                item.uri,
                "somente leitura",
            )
            for item in input_refs
        ],
        *[
            ReportArtifact(
                "Saída",
                item.name,
                item.role,
                item.uri,
                "revisar",
            )
            for item in output_refs
        ],
    ]
    warnings = []
    if issues:
        warnings.append(
            f"Há {len(issues)} achados agregados para revisão antes de D03."
        )
    if counts["duplicate_id_rows"] or counts["cross_file_shared_ids"]:
        warnings.append(
            "Há IDs repetidos dentro de uma base ou compartilhados entre bases."
        )
    return render_report(
        module="snapshot_candidate_census",
        objective="medir três bases candidatas sem criar snapshot",
        operation_id=operation_id,
        period=period,
        unit="registro de textos_parlamentares/v1",
        execution_status="succeeded",
        scientific_gate="needs_review",
        result_summary=(
            f"Foram lidos {counts['input_records']} registros em "
            f"{counts['candidate_files']} Parquets. Nenhum snapshot foi criado "
            f"e nenhuma entrada sob `{parquet_root}` foi alterada."
        ),
        counts=[
            CountRow(
                "bases candidatas",
                counts["candidate_files"],
                "três Parquets autorizados para o censo",
            ),
            CountRow(
                "registros de entrada",
                counts["input_records"],
                "todas as linhas dos três Parquets",
            ),
            CountRow(
                "IDs distintos globais",
                counts["global_distinct_ids"],
                "texto_id não vazio no conjunto das três bases",
            ),
            CountRow(
                "IDs ausentes",
                counts["ids_missing"],
                "linhas sem texto_id",
            ),
            CountRow(
                "duplicatas internas",
                counts["duplicate_id_rows"],
                "linhas adicionais além do texto_id distinto em cada base",
            ),
            CountRow(
                "IDs compartilhados entre bases",
                counts["cross_file_shared_ids"],
                "soma das interseções exatas por par de bases",
            ),
            CountRow(
                "textos disponíveis",
                counts["text_nonempty"],
                "linhas com texto_tamanho maior que zero",
            ),
            CountRow(
                "autores disponíveis",
                counts["author_nonempty"],
                "linhas com parlamentar_nome não vazio",
            ),
            CountRow(
                "achados agregados",
                counts["issues"],
                "regras estruturais que exigem revisão",
            ),
        ],
        artifacts=artifacts,
        warnings=warnings,
        next_action=(
            "Revise `artifacts/mapa_censo.md` e as contagens anuais. "
            "Não aprove D03 nem crie o snapshot antes do próximo gate."
        ),
    )


def _inspect_base(
    connection: duckdb.DuckDBPyConnection,
    *,
    path: Path,
    candidate: CandidateBase,
    columns: set[str],
    row_groups: int,
    column_count: int,
) -> dict[str, Any]:
    texto_id = _text_expr("texto_id", columns)
    data_value = _text_expr("data", columns)
    texto_tamanho = _int_expr("texto_tamanho", columns)
    parlamentar_nome = _text_expr("parlamentar_nome", columns)
    raw_path = _text_expr("raw_path", columns)
    raw_source_id = _text_expr("raw_source_id", columns)
    source = _text_expr("source", columns)
    dataset = _text_expr("dataset", columns)
    query = f"""
        SELECT
            count(*)::BIGINT AS records,
            min(try_cast({data_value} AS DATE)) AS date_min,
            max(try_cast({data_value} AS DATE)) AS date_max,
            count(*) FILTER (WHERE {texto_id} IS NULL)::BIGINT AS ids_missing,
            count(DISTINCT {texto_id})::BIGINT AS ids_distinct,
            count(*) FILTER (
                WHERE coalesce({texto_tamanho}, 0) > 0
            )::BIGINT AS text_nonempty,
            count(*) FILTER (
                WHERE {parlamentar_nome} IS NOT NULL
            )::BIGINT AS author_nonempty,
            count(*) FILTER (
                WHERE {raw_path} IS NOT NULL OR {raw_source_id} IS NOT NULL
            )::BIGINT AS provenance_nonempty,
            count(*) FILTER (
                WHERE {source} IS DISTINCT FROM '{_sql_literal(candidate.expected_source)}'
            )::BIGINT AS unexpected_source_rows,
            count(*) FILTER (
                WHERE {dataset} IS DISTINCT FROM '{_sql_literal(candidate.expected_dataset)}'
            )::BIGINT AS unexpected_dataset_rows,
            count(*) FILTER (
                WHERE {data_value} IS NOT NULL
                  AND try_cast({data_value} AS DATE) IS NULL
            )::BIGINT AS invalid_date_rows
        FROM read_parquet('{_sql_literal(str(path))}')
    """
    row = _fetch_one(connection, query)
    records = int(row["records"])
    ids_missing = int(row["ids_missing"])
    ids_distinct = int(row["ids_distinct"])
    return {
        "candidate_file": candidate.filename,
        "expected_source": candidate.expected_source,
        "expected_dataset": candidate.expected_dataset,
        "size_bytes": path.stat().st_size,
        "row_groups": row_groups,
        "columns": column_count,
        "records": records,
        "date_min": _scalar(row["date_min"]),
        "date_max": _scalar(row["date_max"]),
        "ids_missing": ids_missing,
        "ids_distinct": ids_distinct,
        "duplicate_id_rows": max(records - ids_missing - ids_distinct, 0),
        "text_nonempty": int(row["text_nonempty"]),
        "author_nonempty": int(row["author_nonempty"]),
        "provenance_nonempty": int(row["provenance_nonempty"]),
        "unexpected_source_rows": int(row["unexpected_source_rows"]),
        "unexpected_dataset_rows": int(row["unexpected_dataset_rows"]),
        "invalid_date_rows": int(row["invalid_date_rows"]),
    }


def _inspect_years(
    connection: duckdb.DuckDBPyConnection,
    *,
    path: Path,
    candidate: CandidateBase,
    columns: set[str],
) -> list[dict[str, Any]]:
    source = _text_expr("source", columns)
    dataset = _text_expr("dataset", columns)
    ambito = _text_expr("ambito", columns)
    ano = _int_expr("ano", columns)
    data_value = _text_expr("data", columns)
    texto_tamanho = _int_expr("texto_tamanho", columns)
    parlamentar_nome = _text_expr("parlamentar_nome", columns)
    query = f"""
        SELECT
            coalesce({source}, '(vazio)') AS source,
            coalesce({dataset}, '(vazio)') AS dataset,
            coalesce({ambito}, '(vazio)') AS ambito,
            coalesce(
                {ano},
                year(try_cast({data_value} AS DATE))
            ) AS year,
            count(*)::BIGINT AS records,
            count(*) FILTER (
                WHERE coalesce({texto_tamanho}, 0) > 0
            )::BIGINT AS text_nonempty,
            count(*) FILTER (
                WHERE {parlamentar_nome} IS NOT NULL
            )::BIGINT AS author_nonempty
        FROM read_parquet('{_sql_literal(str(path))}')
        GROUP BY ALL
    """
    return [
        {
            "candidate_file": candidate.filename,
            **{key: _scalar(value) for key, value in row.items()},
        }
        for row in _fetch_all(connection, query)
    ]


def _inspect_categories(
    connection: duckdb.DuckDBPyConnection,
    *,
    path: Path,
    candidate: CandidateBase,
    columns: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension in CATEGORY_COLUMNS:
        value = _text_expr(dimension, columns)
        query = f"""
            SELECT
                coalesce({value}, '(vazio)') AS value,
                count(*)::BIGINT AS records
            FROM read_parquet('{_sql_literal(str(path))}')
            GROUP BY ALL
        """
        rows.extend(
            {
                "candidate_file": candidate.filename,
                "dimension": dimension,
                "value": _scalar(row["value"]),
                "records": int(row["records"]),
            }
            for row in _fetch_all(connection, query)
        )
    return rows


def _inspect_id_metrics(
    connection: duckdb.DuckDBPyConnection,
    *,
    parquet_root: Path,
    schemas: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    files_with_ids = {
        str(row["candidate_file"])
        for row in schemas
        if row["column"] == "texto_id"
    }
    selects = []
    for candidate in CANDIDATE_BASES:
        if candidate.filename not in files_with_ids:
            continue
        path = parquet_root / candidate.filename
        selects.append(
            "SELECT "
            f"'{_sql_literal(candidate.filename)}' AS candidate_file, "
            f"{_text_expr('texto_id', {'texto_id'})} AS texto_id "
            f"FROM read_parquet('{_sql_literal(str(path))}')"
        )
    if not selects:
        return [], 0
    union = " UNION ALL ".join(selects)
    overlaps: list[dict[str, Any]] = []
    if len(selects) >= 2:
        overlap_query = f"""
            WITH candidate_ids AS (
                {union}
            ),
            unique_ids AS (
                SELECT DISTINCT candidate_file, texto_id
                FROM candidate_ids
                WHERE texto_id IS NOT NULL
            )
            SELECT
                left_ids.candidate_file AS left_candidate,
                right_ids.candidate_file AS right_candidate,
                count(*)::BIGINT AS shared_ids
            FROM unique_ids AS left_ids
            JOIN unique_ids AS right_ids
              ON left_ids.texto_id = right_ids.texto_id
             AND left_ids.candidate_file < right_ids.candidate_file
            GROUP BY ALL
            ORDER BY left_candidate, right_candidate
        """
        overlaps = [
            {
                "left_candidate": row["left_candidate"],
                "right_candidate": row["right_candidate"],
                "shared_ids": int(row["shared_ids"]),
            }
            for row in _fetch_all(connection, overlap_query)
        ]
    distinct_query = f"""
        WITH candidate_ids AS (
            {union}
        )
        SELECT count(DISTINCT texto_id)::BIGINT AS global_distinct_ids
        FROM candidate_ids
        WHERE texto_id IS NOT NULL
    """
    global_distinct_ids = int(
        _fetch_one(connection, distinct_query)["global_distinct_ids"]
    )
    return overlaps, global_distinct_ids


def _summary_issues(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    rules = (
        (
            "missing_texto_id",
            "warning",
            "ids_missing",
            "linhas sem identificador",
        ),
        (
            "duplicate_texto_id_within_base",
            "warning",
            "duplicate_id_rows",
            "linhas adicionais para texto_id já observado",
        ),
        (
            "unexpected_source",
            "warning",
            "unexpected_source_rows",
            "linhas com source diferente do nome canônico",
        ),
        (
            "unexpected_dataset",
            "warning",
            "unexpected_dataset_rows",
            "linhas com dataset diferente do nome canônico",
        ),
        (
            "invalid_date",
            "warning",
            "invalid_date_rows",
            "datas não vazias que não puderam ser interpretadas",
        ),
    )
    issues = []
    for issue_type, severity, field, detail in rules:
        count = int(summary[field])
        if count:
            issues.append(
                _issue(
                    issue_type,
                    severity,
                    str(summary["candidate_file"]),
                    count,
                    detail,
                )
            )
    records = int(summary["records"])
    text_missing = records - int(summary["text_nonempty"])
    if text_missing:
        issues.append(
            _issue(
                "text_not_available",
                "info",
                str(summary["candidate_file"]),
                text_missing,
                "linhas com texto_tamanho ausente ou igual a zero",
            )
        )
    provenance_missing = records - int(summary["provenance_nonempty"])
    if provenance_missing:
        issues.append(
            _issue(
                "provenance_not_available",
                "warning",
                str(summary["candidate_file"]),
                provenance_missing,
                "linhas sem raw_path e raw_source_id",
            )
        )
    return issues


def _manifest_counts(census: Mapping[str, Any]) -> dict[str, int]:
    bases = census["bases"]
    overlaps = census["overlaps"]
    return {
        "candidate_files": len(bases),
        "input_records": sum(int(row["records"]) for row in bases),
        "global_distinct_ids": int(census["global_distinct_ids"]),
        "ids_missing": sum(int(row["ids_missing"]) for row in bases),
        "duplicate_id_rows": sum(
            int(row["duplicate_id_rows"]) for row in bases
        ),
        "cross_file_shared_ids": sum(
            int(row["shared_ids"]) for row in overlaps
        ),
        "text_nonempty": sum(int(row["text_nonempty"]) for row in bases),
        "author_nonempty": sum(
            int(row["author_nonempty"]) for row in bases
        ),
        "issues": len(census["issues"]),
    }
def _validate_preflight(
    *,
    parquet_root: Path,
    output_base: Path,
    operation_root: Path,
    candidate_paths: Sequence[Path],
    operation_id: str,
    code_commit: str,
) -> None:
    if not parquet_root.is_dir():
        raise FileNotFoundError(f"Raiz Parquet ausente: {parquet_root}")
    if parquet_root == output_base or parquet_root in output_base.parents:
        raise ValueError("A saída do censo não pode ficar dentro da raiz lida.")
    missing = [path for path in candidate_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Bases candidatas ausentes: " + ", ".join(str(path) for path in missing)
        )
    if operation_root.exists() and any(operation_root.iterdir()):
        raise FileExistsError(
            f"operation_id já possui artefatos: {operation_root}; use um novo ID."
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", operation_id):
        raise ValueError(f"operation_id inválido: {operation_id}")
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("code_commit deve ser um SHA Git completo de 40 caracteres.")


def _input_signature(paths: Sequence[Path]) -> dict[str, tuple[int, int]]:
    return {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
    }


def _text_expr(column: str, columns: set[str]) -> str:
    if column not in columns:
        return "NULL"
    return f"nullif(trim(cast(\"{column}\" AS VARCHAR)), '')"


def _int_expr(column: str, columns: set[str]) -> str:
    if column not in columns:
        return "NULL"
    return f'try_cast("{column}" AS BIGINT)'


def _fetch_one(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> dict[str, Any]:
    rows = _fetch_all(connection, query)
    if len(rows) != 1:
        raise RuntimeError(f"Consulta esperava uma linha e retornou {len(rows)}.")
    return rows[0]


def _fetch_all(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    fields = [str(item[0]) for item in cursor.description]
    return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def _issue(
    issue_type: str,
    severity: str,
    candidate_file: str,
    count: int,
    detail: str,
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "candidate_file": candidate_file,
        "count": count,
        "detail": detail,
    }


def _write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _artifact_ref(
    path: Path,
    *,
    operation_root: Path,
    role: str,
    rows: int | None,
) -> ArtifactRef:
    return ArtifactRef(
        name=path.stem,
        role=role,
        uri=path.relative_to(operation_root).as_posix(),
        format=path.suffix.lstrip("."),
        size_bytes=path.stat().st_size,
        sha256=_file_sha256(path),
        rows=rows,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _period(row: Mapping[str, Any]) -> str:
    if row.get("date_min") and row.get("date_max"):
        return f"{row['date_min']} a {row['date_max']}"
    return "não disponível"


def _percent(value: Any, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{100 * int(value) / denominator:.1f}%"


def _scalar(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value if value is not None else ""


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
