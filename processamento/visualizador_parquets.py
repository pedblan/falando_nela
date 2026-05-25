from __future__ import annotations

import argparse
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import duckdb
import pandas as pd

from coleta.common.config import PROD_DATA_ROOT_ENV

DEFAULT_COLAB_DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
DEFAULT_COLAB_PARQUET_ROOT = (
    DEFAULT_COLAB_DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"
)
DEFAULT_SAMPLES_PARQUET_ROOT = Path("data/samples/textos_parlamentares/v1/parquet")
DEFAULT_LIMIT = 100
MAX_LIMIT = 1_000
TEXT_COLUMN = "texto"
TEXT_ID_COLUMN = "texto_id"
WORD_PATTERN = r"\p{L}[\p{L}\p{N}_]*"

COMPACT_COLUMNS = [
    "texto_id",
    "source",
    "dataset",
    "data",
    "ano",
    "mes",
    "documento_tipo",
    "unidade_analitica",
    "orgao_sigla",
    "parlamentar_nome",
    "proposicao_identificacao",
    "titulo",
    "texto_tamanho",
    "url_texto",
    "raw_path",
]

METADATA_COLUMNS = [
    "source",
    "dataset",
    "data",
    "documento_tipo",
    "unidade_analitica",
    "titulo",
    "parlamentar_nome",
    "proposicao_identificacao",
    "url_texto",
    "raw_path",
]

FILTER_COLUMNS = [
    "ano",
    "mes",
    "documento_tipo",
    "unidade_analitica",
    "orgao_sigla",
    "parlamentar_nome",
    "proposicao_identificacao",
]


@dataclass(frozen=True)
class QueryInfo:
    status: str
    ignored_filters: tuple[str, ...]
    columns: tuple[str, ...]
    limit: int


@dataclass(frozen=True)
class TextLookup:
    status: str
    metadata: dict[str, str]
    text: str


@dataclass(frozen=True)
class SearchTerm:
    value: str
    excluded: bool = False
    exact: bool = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Abre um app Gradio read-only para navegar pelos Parquets processed v1."
    )
    parser.add_argument(
        "--profile",
        choices=["auto", "samples-local", "colab"],
        default="samples-local",
        help="Escolhe o diretorio padrao de Parquets.",
    )
    parser.add_argument("--data-root", default=None, help="Raiz de dados para o perfil colab.")
    parser.add_argument("--parquet-root", default=None, help="Diretorio explicito de Parquets.")
    parser.add_argument("--share", action="store_true", help="Ativa link publico temporario do Gradio.")
    parser.add_argument("--server-name", default=None)
    parser.add_argument("--server-port", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    parquet_root = resolve_parquet_root(
        profile=args.profile,
        data_root=args.data_root,
        parquet_root=args.parquet_root,
        env=os.environ,
    )
    app = build_gradio_app(parquet_root)
    app.launch(share=args.share, server_name=args.server_name, server_port=args.server_port)


def resolve_parquet_root(
    *,
    profile: str = "samples-local",
    data_root: str | os.PathLike[str] | None = None,
    parquet_root: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    if parquet_root:
        return Path(parquet_root).expanduser()

    env = env or os.environ
    if profile == "auto":
        if DEFAULT_COLAB_PARQUET_ROOT.exists():
            return DEFAULT_COLAB_PARQUET_ROOT
        return DEFAULT_SAMPLES_PARQUET_ROOT

    if profile == "samples-local":
        return DEFAULT_SAMPLES_PARQUET_ROOT

    if profile == "colab":
        root_value = data_root or env.get(PROD_DATA_ROOT_ENV) or DEFAULT_COLAB_DATA_ROOT
        root = Path(root_value).expanduser()
        return root / "processed" / "textos_parlamentares" / "v1" / "parquet"

    raise ValueError(f"Perfil de Parquets desconhecido: {profile}")


def list_parquet_files(parquet_root: Path | str) -> list[str]:
    root = Path(parquet_root).expanduser()
    if not root.exists():
        return []
    return sorted(path.name for path in root.glob("*.parquet") if path.is_file())


def resolve_parquet_path(parquet_root: Path | str, parquet_name: str) -> Path:
    name = str(parquet_name or "").strip()
    if not name:
        raise ValueError("Selecione uma base Parquet.")
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError(f"Nome de Parquet invalido: {name}")
    if not name.endswith(".parquet"):
        raise ValueError(f"O arquivo selecionado nao e Parquet: {name}")

    root = Path(parquet_root).expanduser().resolve(strict=False)
    path = (root / name).resolve(strict=False)
    if path.parent != root:
        raise ValueError(f"Parquet fora do diretorio permitido: {name}")
    if not path.exists():
        raise FileNotFoundError(f"Parquet nao encontrado: {path}")
    return path


def get_columns(parquet_root: Path | str, parquet_name: str) -> list[str]:
    path = resolve_parquet_path(parquet_root, parquet_name)
    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(f"DESCRIBE SELECT * FROM {_parquet_table(path)}").fetchall()
    finally:
        con.close()
    return [str(row[0]) for row in rows]


def count_rows(parquet_root: Path | str, parquet_name: str) -> int:
    path = resolve_parquet_path(parquet_root, parquet_name)
    con = duckdb.connect(database=":memory:")
    try:
        value = con.execute(f"SELECT COUNT(*) FROM {_parquet_table(path)}").fetchone()
    finally:
        con.close()
    return int(value[0]) if value else 0


def compact_columns(columns: Sequence[str]) -> list[str]:
    available = set(columns)
    selected = [column for column in COMPACT_COLUMNS if column in available and column != TEXT_COLUMN]
    if selected:
        return selected
    return [column for column in columns if column != TEXT_COLUMN][:20]


def sort_columns(columns: Sequence[str]) -> list[str]:
    compact = compact_columns(columns)
    return compact or [column for column in columns if column != TEXT_COLUMN]


def default_sort_column(columns: Sequence[str]) -> str | None:
    for candidate in ["data", "ano", "texto_id"]:
        if candidate in columns:
            return candidate
    options = sort_columns(columns)
    return options[0] if options else None


def query_compact_table(
    parquet_root: Path | str,
    parquet_name: str,
    *,
    ano: Any = None,
    mes: Any = None,
    documento_tipo: Any = None,
    unidade_analitica: Any = None,
    orgao_sigla: Any = None,
    parlamentar_nome: Any = None,
    proposicao_identificacao: Any = None,
    busca_textual: Any = None,
    limit: Any = DEFAULT_LIMIT,
    sort_column: str | None = None,
    sort_desc: bool = True,
) -> tuple[pd.DataFrame, QueryInfo]:
    path = resolve_parquet_path(parquet_root, parquet_name)
    columns = get_columns(parquet_root, parquet_name)
    select_columns = compact_columns(columns)
    if not select_columns:
        return pd.DataFrame(), QueryInfo(
            status="A base nao possui colunas compactas para exibir.",
            ignored_filters=(),
            columns=tuple(columns),
            limit=0,
        )

    filters = {
        "ano": ano,
        "mes": mes,
        "documento_tipo": documento_tipo,
        "unidade_analitica": unidade_analitica,
        "orgao_sigla": orgao_sigla,
        "parlamentar_nome": parlamentar_nome,
        "proposicao_identificacao": proposicao_identificacao,
    }
    where_clauses, params, ignored = _build_where(columns, filters, busca_textual)
    effective_limit = _coerce_limit(limit)
    select_sql = ", ".join(_quote_identifier(column) for column in select_columns)
    sql = f"SELECT {select_sql} FROM {_parquet_table(path)}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    if sort_column and sort_column in columns and sort_column != TEXT_COLUMN:
        direction = "DESC" if sort_desc else "ASC"
        sql += f" ORDER BY {_quote_identifier(sort_column)} {direction} NULLS LAST"
    elif sort_column:
        ignored.append(f"ordenacao:{sort_column}")

    sql += " LIMIT ?"
    params.append(effective_limit)

    con = duckdb.connect(database=":memory:")
    try:
        df = con.execute(sql, params).fetchdf()
    finally:
        con.close()

    status = f"{len(df)} linha(s) carregada(s) de {parquet_name}; limite {effective_limit}."
    if ignored:
        status += " Filtros ignorados: " + ", ".join(ignored) + "."
    return df, QueryInfo(
        status=status,
        ignored_filters=tuple(ignored),
        columns=tuple(columns),
        limit=effective_limit,
    )


def query_yearly_metrics(
    parquet_root: Path | str,
    parquet_name: str,
    *,
    ano: Any = None,
    mes: Any = None,
    documento_tipo: Any = None,
    unidade_analitica: Any = None,
    orgao_sigla: Any = None,
    parlamentar_nome: Any = None,
    proposicao_identificacao: Any = None,
    busca_textual: Any = None,
) -> pd.DataFrame:
    path = resolve_parquet_path(parquet_root, parquet_name)
    columns = get_columns(parquet_root, parquet_name)
    if "ano" not in columns:
        return pd.DataFrame(columns=["ano", "serie", "valor", "resultados", "discursos", "palavras"])

    filters = {
        "ano": ano,
        "mes": mes,
        "documento_tipo": documento_tipo,
        "unidade_analitica": unidade_analitica,
        "orgao_sigla": orgao_sigla,
        "parlamentar_nome": parlamentar_nome,
        "proposicao_identificacao": proposicao_identificacao,
    }
    denominator_where, denominator_params, _ = _build_where(columns, filters, None)
    matches_where, matches_params, _ = _build_where(columns, filters, busca_textual)
    denominator_where_sql = "WHERE " + " AND ".join(denominator_where) if denominator_where else ""
    matches_where_sql = "WHERE " + " AND ".join(matches_where) if matches_where else ""
    word_count_expr = _word_count_expression(columns)
    table_sql = _parquet_table(path)

    sql = f"""
        WITH denominator AS (
            SELECT
                CAST({_quote_identifier("ano")} AS VARCHAR) AS ano,
                COUNT(*) AS discursos,
                SUM({word_count_expr}) AS palavras
            FROM {table_sql}
            {denominator_where_sql}
            GROUP BY 1
        ),
        matches AS (
            SELECT
                CAST({_quote_identifier("ano")} AS VARCHAR) AS ano,
                COUNT(*) AS resultados
            FROM {table_sql}
            {matches_where_sql}
            GROUP BY 1
        )
        SELECT
            denominator.ano,
            COALESCE(matches.resultados, 0) AS resultados,
            denominator.discursos,
            denominator.palavras
        FROM denominator
        LEFT JOIN matches USING (ano)
        ORDER BY denominator.ano
    """
    con = duckdb.connect(database=":memory:")
    try:
        yearly = con.execute(sql, [*denominator_params, *matches_params]).fetchdf()
    finally:
        con.close()
    return _yearly_metrics_long(yearly)


def build_yearly_metrics_chart(metrics_df: pd.DataFrame):
    if metrics_df.empty:
        return None

    import altair as alt

    base = alt.Chart(metrics_df).encode(
        x=alt.X("ano:O", title="Ano"),
        y=alt.Y("valor:Q", title="Valor"),
        color=alt.Color("serie:N", title="Metrica"),
        tooltip=[
            alt.Tooltip("ano:O", title="Ano"),
            alt.Tooltip("serie:N", title="Metrica"),
            alt.Tooltip("valor:Q", title="Valor", format=",.4f"),
            alt.Tooltip("resultados:Q", title="Resultados", format=","),
            alt.Tooltip("discursos:Q", title="Discursos", format=","),
            alt.Tooltip("palavras:Q", title="Palavras", format=","),
        ],
    )
    hover = alt.selection_point(fields=["ano"], nearest=True, on="pointerover", empty=False)
    solid = (
        base.transform_filter(alt.datum.serie == "Resultados")
        .mark_line(strokeWidth=3)
    )
    dotted = (
        base.transform_filter(alt.datum.serie == "Por discurso")
        .mark_line(strokeDash=[2, 4], strokeWidth=3)
    )
    triangles = (
        base.transform_filter(alt.datum.serie == "Por mil palavras")
        .mark_line(
            point=alt.OverlayMarkDef(shape="triangle-up", filled=True, size=90),
            strokeWidth=3,
        )
    )
    hover_points = (
        base.mark_point(size=110, filled=True)
        .encode(opacity=alt.condition(hover, alt.value(1), alt.value(0)))
        .add_params(hover)
    )
    return (
        alt.layer(solid, dotted, triangles, hover_points)
        .properties(width=900, height=320, title="Resultados por ano")
        .interactive()
    )


def fetch_text_by_id(
    parquet_root: Path | str,
    parquet_name: str,
    texto_id: Any,
) -> TextLookup:
    text_id = _normalize_value(texto_id)
    if not text_id:
        return TextLookup(status="Informe um texto_id.", metadata={}, text="")

    path = resolve_parquet_path(parquet_root, parquet_name)
    columns = get_columns(parquet_root, parquet_name)
    if TEXT_ID_COLUMN not in columns:
        return TextLookup(status="A base selecionada nao possui texto_id.", metadata={}, text="")
    if TEXT_COLUMN not in columns:
        return TextLookup(status="A base selecionada nao possui coluna texto.", metadata={}, text="")

    select_columns = _dedupe([TEXT_ID_COLUMN, *METADATA_COLUMNS, TEXT_COLUMN], columns)
    select_sql = ", ".join(_quote_identifier(column) for column in select_columns)
    sql = (
        f"SELECT {select_sql} FROM {_parquet_table(path)} "
        f"WHERE CAST({_quote_identifier(TEXT_ID_COLUMN)} AS VARCHAR) = ? LIMIT 1"
    )

    con = duckdb.connect(database=":memory:")
    try:
        df = con.execute(sql, [text_id]).fetchdf()
    finally:
        con.close()

    if df.empty:
        return TextLookup(status=f"texto_id nao encontrado: {text_id}", metadata={}, text="")

    row = df.iloc[0].to_dict()
    metadata = {
        column: _display_value(row.get(column))
        for column in METADATA_COLUMNS
        if column in row and not _is_missing(row.get(column))
    }
    text = _display_value(row.get(TEXT_COLUMN))
    return TextLookup(status=f"Texto carregado: {text_id}", metadata=metadata, text=text)


def format_metadata_markdown(result: TextLookup) -> str:
    lines = [f"**{result.status}**"]
    if result.metadata:
        lines.append("")
        for key, value in result.metadata.items():
            lines.append(f"- `{key}`: {value}")
    return "\n".join(lines)


def build_gradio_app(parquet_root: Path | str):
    import gradio as gr

    root = Path(parquet_root).expanduser()
    initial_bases = list_parquet_files(root)
    initial_base = initial_bases[0] if initial_bases else None
    initial_columns = get_columns(root, initial_base) if initial_base else []
    initial_sort_columns = sort_columns(initial_columns)
    initial_sort = default_sort_column(initial_columns)

    def refresh_bases():
        bases = list_parquet_files(root)
        value = bases[0] if bases else None
        if not value:
            return (
                gr.update(choices=bases, value=value),
                f"Nenhum Parquet encontrado em {root}.",
                gr.update(choices=[], value=None),
            )
        columns = get_columns(root, value)
        return (
            gr.update(choices=bases, value=value),
            _base_status(root, value),
            gr.update(choices=sort_columns(columns), value=default_sort_column(columns)),
        )

    def on_base_change(base_name: str | None):
        if not base_name:
            return "Selecione uma base.", gr.update(choices=[], value=None)
        try:
            columns = get_columns(root, base_name)
            options = sort_columns(columns)
            return _base_status(root, base_name), gr.update(
                choices=options,
                value=default_sort_column(columns),
            )
        except Exception as exc:  # pragma: no cover - UI safety net
            return f"Erro ao ler a base: {exc}", gr.update(choices=[], value=None)

    def run_query(
        base_name,
        ano,
        mes,
        documento_tipo,
        unidade_analitica,
        orgao_sigla,
        parlamentar_nome,
        proposicao_identificacao,
        busca_textual,
        limit,
        sort_column,
        sort_direction,
    ):
        try:
            df, info = query_compact_table(
                root,
                base_name,
                ano=ano,
                mes=mes,
                documento_tipo=documento_tipo,
                unidade_analitica=unidade_analitica,
                orgao_sigla=orgao_sigla,
                parlamentar_nome=parlamentar_nome,
                proposicao_identificacao=proposicao_identificacao,
                busca_textual=busca_textual,
                limit=limit,
                sort_column=sort_column,
                sort_desc=sort_direction != "ascendente",
            )
            chart = build_yearly_metrics_chart(
                query_yearly_metrics(
                    root,
                    base_name,
                    ano=ano,
                    mes=mes,
                    documento_tipo=documento_tipo,
                    unidade_analitica=unidade_analitica,
                    orgao_sigla=orgao_sigla,
                    parlamentar_nome=parlamentar_nome,
                    proposicao_identificacao=proposicao_identificacao,
                    busca_textual=busca_textual,
                )
            )
            choices = _text_id_choices(df)
            first_text_id = choices[0] if choices else None
            return (
                df,
                chart,
                info.status,
                gr.update(choices=choices, value=first_text_id),
                "",
            )
        except Exception as exc:  # pragma: no cover - UI safety net
            return (
                pd.DataFrame(),
                None,
                f"Erro na consulta: {exc}",
                gr.update(choices=[], value=None),
                "",
            )

    def load_text(base_name, text_id):
        try:
            result = fetch_text_by_id(root, base_name, text_id)
            return format_metadata_markdown(result), result.text
        except Exception as exc:  # pragma: no cover - UI safety net
            return f"**Erro ao carregar texto:** {exc}", ""

    def clear_filters():
        return "", "", "", "", "", "", "", "", DEFAULT_LIMIT, "descendente", "Filtros limpos."

    with gr.Blocks(title="Visualizador de Parquets", css=_APP_CSS) as app:
        gr.Markdown("# Visualizador de Parquets")
        status = gr.Markdown(_base_status(root, initial_base) if initial_base else f"Nenhum Parquet encontrado em {root}.")

        with gr.Row():
            base = gr.Dropdown(
                choices=initial_bases,
                value=initial_base,
                label="Base",
                scale=3,
            )
            refresh = gr.Button("Atualizar lista", scale=1)

        with gr.Row():
            ano = gr.Textbox(label="Ano", placeholder="2026")
            mes = gr.Textbox(label="Mes", placeholder="05")
            documento_tipo = gr.Textbox(label="Documento tipo")
            unidade_analitica = gr.Textbox(label="Unidade analitica")

        with gr.Row():
            orgao_sigla = gr.Textbox(label="Orgao sigla")
            parlamentar_nome = gr.Textbox(label="Parlamentar")
            proposicao_identificacao = gr.Textbox(label="Proposicao")
            busca_textual = gr.Textbox(label="Busca textual", placeholder='palavra "frase exata" -excluir')

        with gr.Row():
            limit = gr.Number(label="Limite", value=DEFAULT_LIMIT, precision=0)
            sort_column = gr.Dropdown(
                choices=initial_sort_columns,
                value=initial_sort,
                label="Ordenar por",
            )
            sort_direction = gr.Radio(
                choices=["descendente", "ascendente"],
                value="descendente",
                label="Ordem",
            )

        with gr.Row():
            query_button = gr.Button("Consultar", variant="primary")
            clear_button = gr.Button("Limpar filtros")

        table = gr.Dataframe(label="Tabela compacta", interactive=False)
        yearly_plot = gr.Plot(label="Resultados por ano")
        text_id = gr.Dropdown(choices=[], label="texto_id", allow_custom_value=True)
        load_button = gr.Button("Carregar texto")

        with gr.Row():
            metadata = gr.Markdown()
            full_text = gr.Textbox(label="Texto integral", lines=22, max_lines=40)

        refresh.click(refresh_bases, outputs=[base, status, sort_column])
        base.change(on_base_change, inputs=[base], outputs=[status, sort_column])
        query_button.click(
            run_query,
            inputs=[
                base,
                ano,
                mes,
                documento_tipo,
                unidade_analitica,
                orgao_sigla,
                parlamentar_nome,
                proposicao_identificacao,
                busca_textual,
                limit,
                sort_column,
                sort_direction,
            ],
            outputs=[table, yearly_plot, status, text_id, full_text],
        )
        clear_button.click(
            clear_filters,
            outputs=[
                ano,
                mes,
                documento_tipo,
                unidade_analitica,
                orgao_sigla,
                parlamentar_nome,
                proposicao_identificacao,
                busca_textual,
                limit,
                sort_direction,
                status,
            ],
        )
        load_button.click(load_text, inputs=[base, text_id], outputs=[metadata, full_text])

    return app


def _base_status(parquet_root: Path | str, parquet_name: str | None) -> str:
    if not parquet_name:
        return f"Nenhum Parquet encontrado em {parquet_root}."
    rows = count_rows(parquet_root, parquet_name)
    columns = get_columns(parquet_root, parquet_name)
    return f"Base `{parquet_name}`: {rows} linha(s), {len(columns)} coluna(s)."


def _build_where(
    columns: Sequence[str],
    filters: Mapping[str, Any],
    busca_textual: Any,
) -> tuple[list[str], list[Any], list[str]]:
    available = set(columns)
    clauses: list[str] = []
    params: list[Any] = []
    ignored: list[str] = []

    for column, raw_value in filters.items():
        value = _normalize_value(raw_value)
        if not value:
            continue
        if column not in available:
            ignored.append(column)
            continue
        if column == "mes":
            values = sorted({value, value.zfill(2)} if value.isdigit() else {value})
            placeholders = ", ".join("?" for _ in values)
            clauses.append(f"CAST({_quote_identifier(column)} AS VARCHAR) IN ({placeholders})")
            params.extend(values)
        elif column == "ano":
            clauses.append(f"CAST({_quote_identifier(column)} AS VARCHAR) = ?")
            params.append(value)
        else:
            clauses.append(f"CAST({_quote_identifier(column)} AS VARCHAR) ILIKE ?")
            params.append(f"%{value}%")

    search = _normalize_value(busca_textual)
    if search:
        if TEXT_COLUMN in available:
            search_clause, search_params = _build_text_search_clause(search)
            if search_clause:
                clauses.append(search_clause)
                params.extend(search_params)
        else:
            ignored.append("busca_textual")

    return clauses, params, ignored


def _word_count_expression(columns: Sequence[str]) -> str:
    if TEXT_COLUMN not in columns:
        return "0"
    text_expr = f"strip_accents(COALESCE(CAST({_quote_identifier(TEXT_COLUMN)} AS VARCHAR), ''))"
    return f"len(regexp_extract_all({text_expr}, {_quote_literal(WORD_PATTERN)}, 0, 'i'))"


def _yearly_metrics_long(yearly: pd.DataFrame) -> pd.DataFrame:
    if yearly.empty:
        return pd.DataFrame(columns=["ano", "serie", "valor", "resultados", "discursos", "palavras"])

    records: list[dict[str, object]] = []
    for row in yearly.to_dict("records"):
        ano = str(row.get("ano", ""))
        resultados = int(row.get("resultados") or 0)
        discursos = int(row.get("discursos") or 0)
        palavras = int(row.get("palavras") or 0)
        metric_values = {
            "Resultados": float(resultados),
            "Por discurso": float(resultados / discursos) if discursos else 0.0,
            "Por mil palavras": float(resultados * 1000 / palavras) if palavras else 0.0,
        }
        for serie, valor in metric_values.items():
            records.append(
                {
                    "ano": ano,
                    "serie": serie,
                    "valor": valor,
                    "resultados": resultados,
                    "discursos": discursos,
                    "palavras": palavras,
                }
            )
    return pd.DataFrame.from_records(records)


def _build_text_search_clause(search: str) -> tuple[str, list[str]]:
    groups, exclusions = _parse_search_query(search)
    text_expr = f"strip_accents(CAST({_quote_identifier(TEXT_COLUMN)} AS VARCHAR))"
    params: list[str] = []
    parts: list[str] = []

    positive_parts: list[str] = []
    for group in groups:
        group_parts: list[str] = []
        for term in group:
            clause, param = _text_term_clause(text_expr, term)
            group_parts.append(clause)
            params.append(param)
        if group_parts:
            positive_parts.append("(" + " AND ".join(group_parts) + ")")
    if positive_parts:
        parts.append("(" + " OR ".join(positive_parts) + ")")

    for term in exclusions:
        clause, param = _text_term_clause(text_expr, term)
        parts.append(f"NOT ({clause})")
        params.append(param)

    return " AND ".join(parts), params


def _parse_search_query(search: str) -> tuple[list[list[SearchTerm]], list[SearchTerm]]:
    groups: list[list[SearchTerm]] = [[]]
    exclusions: list[SearchTerm] = []

    for token in _tokenize_search(search):
        if not token.excluded and not token.exact and (token.value.upper() == "OR" or token.value == "|"):
            if groups[-1]:
                groups.append([])
            continue

        if token.excluded:
            exclusions.append(token)
        else:
            groups[-1].append(token)

    return [group for group in groups if group], exclusions


def _tokenize_search(search: str) -> list[SearchTerm]:
    tokens: list[SearchTerm] = []
    index = 0
    length = len(search)

    while index < length:
        while index < length and search[index].isspace():
            index += 1
        if index >= length:
            break

        excluded = False
        if search[index] == "-":
            excluded = True
            index += 1
            while index < length and search[index].isspace():
                index += 1

        exact = False
        chars: list[str] = []
        if index < length and search[index] == '"':
            exact = True
            index += 1
            while index < length:
                char = search[index]
                if char == "\\" and index + 1 < length:
                    chars.append(search[index + 1])
                    index += 2
                    continue
                if char == '"':
                    index += 1
                    break
                chars.append(char)
                index += 1
        else:
            while index < length and not search[index].isspace():
                chars.append(search[index])
                index += 1

        value = "".join(chars).strip()
        if value:
            tokens.append(SearchTerm(value=value, excluded=excluded, exact=exact))

    return tokens


def _text_term_clause(text_expr: str, term: SearchTerm) -> tuple[str, str]:
    return f"regexp_matches({text_expr}, ?, 'i')", _bounded_text_pattern(term.value)


def _bounded_text_pattern(value: str) -> str:
    escaped = re.escape(_strip_accents(value.strip()))
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    return rf"(^|[^\p{{L}}\p{{N}}_]){escaped}([^\p{{L}}\p{{N}}_]|$)"


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))



def _coerce_limit(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_LIMIT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(parsed, MAX_LIMIT))


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _display_value(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except TypeError:
        return False
    if isinstance(missing, bool):
        return missing
    return False


def _dedupe(candidates: Sequence[str], columns: Sequence[str]) -> list[str]:
    available = set(columns)
    selected: list[str] = []
    for candidate in candidates:
        if candidate in available and candidate not in selected:
            selected.append(candidate)
    return selected


def _text_id_choices(df: pd.DataFrame) -> list[str]:
    if TEXT_ID_COLUMN not in df.columns:
        return []
    return [str(value) for value in df[TEXT_ID_COLUMN].dropna().tolist()]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _parquet_table(path: Path) -> str:
    return f"read_parquet({_quote_literal(path.as_posix())})"


_APP_CSS = """
.gradio-container { max-width: 1440px !important; }
textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
"""


if __name__ == "__main__":
    main()
