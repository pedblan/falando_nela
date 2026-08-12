from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import pytest

from falando_nela.gcp_config import load_gcp_contract
from falando_nela.marimo_g04 import (
    FIXTURE_ENV,
    SOURCE_ENV,
    MarimoDatasetError,
    filter_discourses,
    filter_options,
    load_g04_dataset,
    presentation_rows,
    resolve_source,
)
from falando_nela.parquet_pipeline import g03_arrow_schema

REPO_ROOT = Path(__file__).parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "gcp.toml"
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "primeiro_recorte_discursos.py"
OFFLINE_RUNNER_PATH = REPO_ROOT / "tests" / "refundacao_gcp_first" / "offline_runner.py"


def _write_parquet(
    path: Path,
    *,
    records: int = 30,
    logical_schema: str = "g03-senado-plenario-discursos-v1",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in reversed(range(records)):
        text = f"Discurso número {index} sobre educação e ciência"
        rows.append(
            {
                "source": "senado",
                "dataset": "plenario_discursos",
                "record_type": "pronunciamento",
                "source_id": f"SF:pronunciamento:{index:03d}",
                "raw_sha256": f"{index:064x}",
                "pronouncement_date": f"2010-01-{index % 28 + 1:02d}",
                "author_name": "Ana Silva" if index % 2 == 0 else "Bruno Souza",
                "party": "AAA" if index % 2 == 0 else "BBB",
                "federative_unit": "SP" if index % 3 == 0 else "RJ",
                "speech_type_description": "Pronunciamento",
                "text": text,
                "text_sha256": f"{index + 100:064x}",
                "text_bytes": len(text.encode("utf-8")),
            }
        )
    schema = g03_arrow_schema(pa).with_metadata(
        {b"falando_nela_schema": logical_schema.encode("utf-8")}
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")
    return path


def test_fixture_source_loads_validated_sorted_rows_and_filters(tmp_path: Path) -> None:
    fixture = _write_parquet(tmp_path / "g04.parquet")
    contract = load_gcp_contract(CONFIG_PATH)

    dataset = load_g04_dataset(
        contract,
        environ={SOURCE_ENV: "fixture", FIXTURE_ENV: str(fixture)},
    )

    assert dataset.source == "fixture"
    assert len(dataset.rows) == 30
    assert [row["source_id"] for row in dataset.rows] == sorted(
        row["source_id"] for row in dataset.rows
    )
    filtered = filter_discourses(dataset.rows, query="EDUCAÇÃO", party="AAA", federative_unit="SP")
    assert filtered
    assert all(row["party"] == "AAA" for row in filtered)
    assert all(row["federative_unit"] == "SP" for row in filtered)
    assert filter_options(dataset.rows, "party") == ("AAA", "BBB")
    assert set(presentation_rows(filtered)[0]) == {
        "source_id",
        "data",
        "autoria",
        "partido",
        "UF",
        "tipo",
        "texto",
    }


def test_gcs_is_default_and_uses_explicit_contracted_path(tmp_path: Path) -> None:
    contract = load_gcp_contract(CONFIG_PATH)
    remote_path = tmp_path / contract.data.bucket / contract.marimo.parquet_locator
    _write_parquet(remote_path)
    filesystem = pafs.SubTreeFileSystem(str(tmp_path), pafs.LocalFileSystem())

    dataset = load_g04_dataset(contract, environ={}, gcs_filesystem=filesystem)

    assert resolve_source({}) == "gcs"
    assert dataset.source == "gcs"
    assert dataset.locator == f"gs://{contract.data.bucket}/{contract.marimo.parquet_locator}"


def test_fixture_mode_never_falls_back_to_gcs(tmp_path: Path) -> None:
    contract = load_gcp_contract(CONFIG_PATH)
    filesystem = pafs.SubTreeFileSystem(str(tmp_path), pafs.LocalFileSystem())

    with pytest.raises(MarimoDatasetError, match=f"{FIXTURE_ENV} é obrigatório"):
        load_g04_dataset(
            contract,
            environ={SOURCE_ENV: "fixture"},
            gcs_filesystem=filesystem,
        )


@pytest.mark.parametrize("source", ["", "local", "drive"])
def test_unknown_or_empty_source_is_rejected(source: str) -> None:
    with pytest.raises(MarimoDatasetError, match=f"{SOURCE_ENV} deve ser"):
        resolve_source({SOURCE_ENV: source})


@pytest.mark.parametrize(
    ("records", "logical_schema", "message"),
    [
        (0, "g03-senado-plenario-discursos-v1", "vazio"),
        (29, "g03-senado-plenario-discursos-v1", "contagem"),
        (30, "desconhecido", "schema lógico"),
    ],
)
def test_fixture_rejects_incompatible_contract(
    tmp_path: Path,
    records: int,
    logical_schema: str,
    message: str,
) -> None:
    fixture = _write_parquet(
        tmp_path / "invalid.parquet",
        records=records,
        logical_schema=logical_schema,
    )
    contract = load_gcp_contract(CONFIG_PATH)

    with pytest.raises(MarimoDatasetError, match=message):
        load_g04_dataset(
            contract,
            environ={SOURCE_ENV: "fixture", FIXTURE_ENV: str(fixture)},
        )


def test_notebook_executes_as_script_with_explicit_fixture(tmp_path: Path) -> None:
    fixture = _write_parquet(tmp_path / "script.parquet")
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    environment = {
        **os.environ,
        SOURCE_ENV: "fixture",
        FIXTURE_ENV: str(fixture),
        "HOME": str(isolated_home),
        "CLOUDSDK_CONFIG": str(isolated_home / "gcloud"),
    }
    for key in (
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GCLOUD_PROJECT",
        "CLOUDSDK_CORE_PROJECT",
    ):
        environment.pop(key, None)

    result = subprocess.run(
        [sys.executable, str(OFFLINE_RUNNER_PATH), str(NOTEBOOK_PATH)],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Discurso número" not in result.stderr
