import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell
def _():
    import logging
    from pathlib import Path

    import marimo as mo

    from falando_nela.gcp_config import load_gcp_contract
    from falando_nela.marimo_g04 import (
        filter_discourses,
        filter_options,
        load_g04_dataset,
        presentation_rows,
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return (
        Path,
        filter_discourses,
        filter_options,
        load_g04_dataset,
        load_gcp_contract,
        mo,
        presentation_rows,
    )


@app.cell
def _(Path, load_g04_dataset, load_gcp_contract):
    repo_root = Path(__file__).resolve().parents[1]
    contract = load_gcp_contract(repo_root / "config" / "gcp.toml")
    dataset = load_g04_dataset(contract)
    return contract, dataset


@app.cell
def _(mo):
    mo.md("""
    # Falando Nela — discursos do Senado em 2010

    Primeiro recorte vertical do novo ambiente GCP-first. A consulta é somente leitura e usa o Parquet aprovado da operação G03.
    """)
    return


@app.cell
def _(dataset, filter_options, mo):
    query = mo.ui.text(
        label="Buscar nos discursos",
        placeholder="Texto, autoria, tipo ou source_id",
        full_width=True,
    )
    party = mo.ui.dropdown(
        options={"Todos": "", **{value: value for value in filter_options(dataset.rows, "party")}},
        value="Todos",
        label="Partido",
        searchable=True,
    )
    federative_unit = mo.ui.dropdown(
        options={
            "Todas": "",
            **{value: value for value in filter_options(dataset.rows, "federative_unit")},
        },
        value="Todas",
        label="UF",
        searchable=True,
    )
    return federative_unit, party, query


@app.cell
def _(federative_unit, mo, party, query):
    mo.vstack(
        [
            query,
            mo.hstack([party, federative_unit], justify="start", gap=1.5),
        ]
    )
    return


@app.cell
def _(dataset, federative_unit, filter_discourses, party, query):
    filtered_rows = filter_discourses(
        dataset.rows,
        query=query.value,
        party=party.value,
        federative_unit=federative_unit.value,
    )
    return (filtered_rows,)


@app.cell
def _(contract, dataset, filtered_rows, mo):
    loaded_at = dataset.loaded_at.astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")
    mo.md(
        f"""
        **{len(filtered_rows)} de {len(dataset.rows)} discursos** · Senado · 2010

        Operação `{dataset.operation_id}` · fonte `{dataset.source}` · schema
        `{contract.marimo.parquet_schema}` · carregado em {loaded_at}
        """
    )
    return


@app.cell
def _(filtered_rows, mo, presentation_rows):
    discourse_table = mo.ui.table(
        presentation_rows(filtered_rows),
        selection="single",
        pagination=True,
        page_size=10,
        show_column_summaries=False,
        show_data_types=False,
        show_download=False,
        freeze_columns_left=["source_id"],
        wrapped_columns=["autoria", "tipo", "texto"],
        max_height=560,
        label="Discursos",
    )
    discourse_table
    return (discourse_table,)


@app.cell
def _(dataset, discourse_table, mo):
    selected_id = discourse_table.value[0]["source_id"] if discourse_table.value else None
    selected_row = next(
        (row for row in dataset.rows if row["source_id"] == selected_id),
        None,
    )
    detail = (
        mo.vstack(
            [
                mo.md(
                    f"### {selected_row.get('author_name') or 'Autoria não informada'} "
                    f"— {selected_row.get('party') or 'sem partido'}/"
                    f"{selected_row.get('federative_unit') or 'sem UF'}"
                ),
                mo.md(str(selected_row.get("text") or "*Texto não disponível.*")),
            ]
        )
        if selected_row is not None
        else mo.md("Selecione uma linha para ler o discurso completo.")
    )
    detail
    return


@app.cell
def _(filter_discourses):
    def test_filter_discourses_accepts_empty_rows():
        assert filter_discourses((), query="", party="", federative_unit="") == ()

    return


if __name__ == "__main__":
    app.run()
