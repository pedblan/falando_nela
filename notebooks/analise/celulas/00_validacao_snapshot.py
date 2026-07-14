from pathlib import Path

import pandas as pd


SNAPSHOT_RUN_ID = globals().get("RUN_ID", "analise-plenario-20260713-v1")
SNAPSHOT_DATA_ROOT = Path(
    globals().get("DATA_ROOT", "/content/drive/MyDrive/falando_nela/data")
)
SNAPSHOT_RUN_OUTPUT_ROOT = Path(
    globals().get(
        "RUN_OUTPUT_ROOT",
        SNAPSHOT_DATA_ROOT
        / "analises"
        / "discursos_plenario"
        / "v1"
        / SNAPSHOT_RUN_ID,
    )
)
SNAPSHOT_PATH = (
    SNAPSHOT_RUN_OUTPUT_ROOT
    / "00_snapshot"
    / "discursos_plenario_snapshot.parquet"
)

assert SNAPSHOT_PATH.exists(), (
    f"Snapshot não encontrado: {SNAPSHOT_PATH}. "
    "Monte o Drive e confira RUN_ID/DATA_ROOT."
)

SNAPSHOT_FRAME = pd.read_parquet(SNAPSHOT_PATH)
SNAPSHOT_REQUIRED_COLUMNS = {
    "arena",
    "ano",
    "data_analise",
    "elegivel_inferencia_anual",
}
SNAPSHOT_MISSING_COLUMNS = SNAPSHOT_REQUIRED_COLUMNS.difference(SNAPSHOT_FRAME.columns)
assert not SNAPSHOT_MISSING_COLUMNS, (
    f"Colunas obrigatórias ausentes: {sorted(SNAPSHOT_MISSING_COLUMNS)}"
)

SNAPSHOT_EXPECTED_ARENAS = ["camara", "senado", "congresso"]
SNAPSHOT_OBSERVED_ARENAS = set(SNAPSHOT_FRAME["arena"].dropna().astype(str).unique())
assert SNAPSHOT_OBSERVED_ARENAS == set(SNAPSHOT_EXPECTED_ARENAS), (
    f"Arenas observadas: {sorted(SNAPSHOT_OBSERVED_ARENAS)}; "
    f"esperadas: {sorted(SNAPSHOT_EXPECTED_ARENAS)}"
)

SNAPSHOT_FRAME["data_analise"] = pd.to_datetime(
    SNAPSHOT_FRAME["data_analise"], errors="coerce"
)
SNAPSHOT_FRAME["ano"] = pd.to_numeric(SNAPSHOT_FRAME["ano"], errors="coerce")
assert SNAPSHOT_FRAME["data_analise"].notna().all(), "Há data_analise inválida."
assert SNAPSHOT_FRAME["ano"].notna().all(), "Há ano inválido."
SNAPSHOT_FRAME["ano"] = SNAPSHOT_FRAME["ano"].astype(int)

SNAPSHOT_DATE_START = pd.Timestamp("2010-02-02")
SNAPSHOT_DATE_END = pd.Timestamp("2026-07-13")
assert SNAPSHOT_FRAME["data_analise"].between(
    SNAPSHOT_DATE_START, SNAPSHOT_DATE_END, inclusive="both"
).all(), "Há discursos fora do recorte temporal."
assert not SNAPSHOT_FRAME.loc[
    SNAPSHOT_FRAME["ano"].eq(2026), "elegivel_inferencia_anual"
].fillna(False).any(), "2026 não pode ser elegível à inferência anual."

SNAPSHOT_SUMMARY = (
    SNAPSHOT_FRAME.groupby("arena", observed=True)
    .agg(
        discursos=("arena", "size"),
        ano_inicial=("ano", "min"),
        ano_final=("ano", "max"),
        anos_com_discursos=("ano", "nunique"),
        data_inicial=("data_analise", "min"),
        data_final=("data_analise", "max"),
    )
    .reindex(SNAPSHOT_EXPECTED_ARENAS)
)

SNAPSHOT_COUNTS = (
    SNAPSHOT_FRAME.groupby(["ano", "arena"], observed=True)
    .size()
    .rename("discursos")
    .unstack("arena")
)
SNAPSHOT_COVERAGE = (
    SNAPSHOT_COUNTS.reindex(
        index=range(2010, 2027),
        columns=SNAPSHOT_EXPECTED_ARENAS,
        fill_value=0,
    )
    .fillna(0)
    .astype("int64")
)
SNAPSHOT_COVERAGE.index.name = "ano"
SNAPSHOT_COVERAGE.columns.name = "arena"

display(SNAPSHOT_SUMMARY)
display(SNAPSHOT_COVERAGE)

SNAPSHOT_MISSING_YEARS = {
    arena: SNAPSHOT_COVERAGE.index[SNAPSHOT_COVERAGE[arena].eq(0)].tolist()
    for arena in SNAPSHOT_EXPECTED_ARENAS
}
print("Anos sem discursos no snapshot:")
for SNAPSHOT_ARENA in SNAPSHOT_EXPECTED_ARENAS:
    print(f"- {SNAPSHOT_ARENA}: {SNAPSHOT_MISSING_YEARS[SNAPSHOT_ARENA] or 'nenhum'}")

print("Snapshot validado:", SNAPSHOT_PATH)
print("Total de discursos:", len(SNAPSHOT_FRAME))
