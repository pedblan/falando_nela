from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from processamento.visualizador_parquets import (
    _build_text_search_clause,
    build_yearly_metrics_chart,
    fetch_text_by_id,
    list_parquet_files,
    query_compact_table,
    query_yearly_metrics,
    resolve_parquet_path,
)


def test_query_compact_table_filters_without_returning_text(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "camara__plenario_discursos.parquet"
    _write_parquet(
        path,
        [
            {
                "texto_id": "texto-1",
                "source": "camara",
                "dataset": "plenario_discursos",
                "data": "2026-05-10",
                "ano": "2026",
                "mes": "05",
                "documento_tipo": "discurso",
                "unidade_analitica": "pronunciamento",
                "orgao_sigla": "PLEN",
                "parlamentar_nome": "Ana Silva",
                "proposicao_identificacao": "PEC 1/2026",
                "titulo": "Sessao plenaria",
                "texto_tamanho": 45,
                "url_texto": "https://example.test/texto-1",
                "raw_path": "raw/camara/plenario/2026.jsonl",
                "texto": "Texto integral sobre saude publica.",
            },
            {
                "texto_id": "texto-2",
                "source": "camara",
                "dataset": "plenario_discursos",
                "data": "2026-06-10",
                "ano": "2026",
                "mes": "06",
                "documento_tipo": "discurso",
                "unidade_analitica": "pronunciamento",
                "orgao_sigla": "PLEN",
                "parlamentar_nome": "Bea Costa",
                "proposicao_identificacao": "PEC 2/2026",
                "titulo": "Sessao plenaria",
                "texto_tamanho": 28,
                "url_texto": "https://example.test/texto-2",
                "raw_path": "raw/camara/plenario/2026.jsonl",
                "texto": "Texto integral sobre educacao.",
            },
        ],
    )

    assert list_parquet_files(root) == ["camara__plenario_discursos.parquet"]
    df, info = query_compact_table(
        root,
        path.name,
        ano="2026",
        mes="5",
        parlamentar_nome="ana",
        busca_textual="saude",
        limit=10,
        sort_column="data",
    )

    assert info.ignored_filters == ()
    assert list(df["texto_id"]) == ["texto-1"]
    assert "texto" not in df.columns


def test_text_search_accepts_quoted_phrases_exclusions_and_or(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "camara__plenario_discursos.parquet"
    _write_parquet(
        path,
        [
            {
                "texto_id": "texto-1",
                "ano": "2026",
                "mes": "05",
                "texto": "A pauta discute saúde pública e financiamento.",
            },
            {
                "texto_id": "texto-2",
                "ano": "2026",
                "mes": "05",
                "texto": "A pauta discute saude privada e publica em blocos separados.",
            },
            {
                "texto_id": "texto-3",
                "ano": "2026",
                "mes": "05",
                "texto": "A audiencia debate educacao basica.",
            },
            {
                "texto_id": "texto-4",
                "ano": "2026",
                "mes": "05",
                "texto": "O relatorio fala de um complexo processo.",
            },
            {
                "texto_id": "texto-5",
                "ano": "2026",
                "mes": "05",
                "texto": "O texto cita plexo de forma isolada.",
            },
        ],
    )

    quoted_df, _ = query_compact_table(root, path.name, busca_textual='"saude publica"', sort_column="texto_id")
    assert list(quoted_df["texto_id"]) == ["texto-1"]

    excluded_df, _ = query_compact_table(root, path.name, busca_textual='saude -privada', sort_column="texto_id")
    assert list(excluded_df["texto_id"]) == ["texto-1"]

    or_df, _ = query_compact_table(
        root,
        path.name,
        busca_textual='"educacao basica" OR financiamento',
        sort_column="texto_id",
        sort_desc=False,
    )
    assert list(or_df["texto_id"]) == ["texto-1", "texto-3"]

    broad_df, _ = query_compact_table(root, path.name, busca_textual="plexo", sort_column="texto_id", sort_desc=False)
    assert list(broad_df["texto_id"]) == ["texto-5"]

    exact_word_df, _ = query_compact_table(
        root,
        path.name,
        busca_textual='"plexo"',
        sort_column="texto_id",
        sort_desc=False,
    )
    assert list(exact_word_df["texto_id"]) == ["texto-5"]


def test_text_search_clause_prefilters_before_regex() -> None:
    clause, params = _build_text_search_clause('plexo -complexo OR "saude publica"', 'texto_busca')

    assert "CASE WHEN" in clause
    assert "ILIKE" in clause
    assert "regexp_matches" in clause
    assert clause.index("ILIKE") < clause.index("regexp_matches")
    assert params == [
        "%plexo%",
        r"(^|[^\p{L}\p{N}_])plexo([^\p{L}\p{N}_]|$)",
        "%saude%",
        "%publica%",
        r"(^|[^\p{L}\p{N}_])saude\s+publica([^\p{L}\p{N}_]|$)",
        "%complexo%",
        r"(^|[^\p{L}\p{N}_])complexo([^\p{L}\p{N}_]|$)",
    ]


def test_yearly_metrics_count_results_per_discourse_and_per_thousand_words(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "camara__plenario_discursos.parquet"
    _write_parquet(
        path,
        [
            {"texto_id": "texto-1", "ano": "2025", "texto": "plexo alfa beta gama"},
            {"texto_id": "texto-2", "ano": "2025", "texto": "complexo alfa beta gama"},
            {"texto_id": "texto-3", "ano": "2026", "texto": "plexo alfa beta gama delta"},
            {"texto_id": "texto-4", "ano": "2026", "texto": "plexo alfa beta gama delta"},
        ],
    )

    metrics = query_yearly_metrics(root, path.name, busca_textual="plexo")

    result_rows = {
        row["ano"]: row
        for row in metrics[metrics["serie"] == "Resultados"].to_dict("records")
    }
    per_discourse_rows = {
        row["ano"]: row
        for row in metrics[metrics["serie"] == "Por discurso"].to_dict("records")
    }
    per_words_rows = {
        row["ano"]: row
        for row in metrics[metrics["serie"] == "Por mil palavras"].to_dict("records")
    }

    assert result_rows["2025"]["valor"] == 1.0
    assert result_rows["2026"]["valor"] == 2.0
    assert per_discourse_rows["2025"]["valor"] == 0.5
    assert per_discourse_rows["2026"]["valor"] == 1.0
    assert per_words_rows["2025"]["valor"] == 125.0
    assert per_words_rows["2026"]["valor"] == 200.0


def test_yearly_metrics_chart_has_required_styles_and_tooltips(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "camara__plenario_discursos.parquet"
    _write_parquet(
        path,
        [
            {"texto_id": "texto-1", "ano": "2025", "texto": "plexo alfa beta gama"},
            {"texto_id": "texto-2", "ano": "2026", "texto": "plexo alfa beta gama delta"},
        ],
    )

    chart = build_yearly_metrics_chart(query_yearly_metrics(root, path.name, busca_textual="plexo"))
    spec = chart.to_dict()

    assert spec["width"] == 900
    assert spec["height"] == 320
    assert spec["resolve"]["scale"]["y"] == "independent"
    assert len(spec["layer"]) == 2
    assert spec["layer"][0]["mark"]["type"] == "line"
    assert spec["layer"][0]["encoding"]["y"]["axis"]["orient"] == "left"
    assert spec["layer"][0]["encoding"]["y"]["title"] == "Resultados"
    assert "strokeDash" not in spec["layer"][0]["mark"]
    relative_layers = spec["layer"][1]["layer"]
    assert len(relative_layers) == 2
    assert relative_layers[0]["mark"]["strokeDash"] == [2, 4]
    assert relative_layers[0]["encoding"]["y"]["axis"]["orient"] == "right"
    assert relative_layers[0]["encoding"]["y"]["title"] == "Metricas relativas"
    assert relative_layers[1]["mark"]["point"]["shape"] == "triangle-up"
    assert relative_layers[1]["encoding"]["y"]["axis"]["orient"] == "right"
    assert spec["layer"][0]["encoding"]["color"]["title"] == "Metrica"
    assert spec["layer"][0]["encoding"]["color"]["legend"]["orient"] == "bottom"
    tooltip_titles = [item["title"] for item in spec["layer"][0]["encoding"]["tooltip"]]
    assert tooltip_titles == ["Ano", "Metrica", "Valor", "Resultados", "Discursos", "Palavras"]


def test_fetch_text_by_id_returns_metadata_and_full_text(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "senado__ccj_notas.parquet"
    full_text = "Linha 1\nLinha 2\nLinha 3"
    _write_parquet(
        path,
        [
            {
                "texto_id": "nota-1",
                "source": "senado",
                "dataset": "ccj_notas",
                "data": "2026-05-11",
                "documento_tipo": "notas_taquigraficas",
                "unidade_analitica": "reuniao",
                "titulo": "CCJ",
                "parlamentar_nome": None,
                "proposicao_identificacao": "PEC 3/2026",
                "url_texto": "https://example.test/nota-1",
                "raw_path": "raw/senado/ccj/2026.jsonl",
                "texto": full_text,
            }
        ],
    )

    result = fetch_text_by_id(root, path.name, "nota-1")

    assert result.status == "Texto carregado: nota-1"
    assert result.text == full_text
    assert result.metadata["source"] == "senado"
    assert result.metadata["proposicao_identificacao"] == "PEC 3/2026"


def test_optional_missing_filters_are_ignored_without_error(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    path = root / "base_minima.parquet"
    _write_parquet(
        path,
        [
            {
                "texto_id": "texto-1",
                "ano": "2026",
                "mes": "05",
                "texto": "Conteudo com palavra-chave.",
            }
        ],
    )

    df, info = query_compact_table(
        root,
        path.name,
        orgao_sigla="CCJ",
        busca_textual="palavra-chave",
        limit=5,
    )

    assert list(df["texto_id"]) == ["texto-1"]
    assert info.ignored_filters == ("orgao_sigla",)


def test_resolve_parquet_path_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "parquet"
    root.mkdir()

    try:
        resolve_parquet_path(root, "../outside.parquet")
    except ValueError as exc:
        assert "invalido" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
