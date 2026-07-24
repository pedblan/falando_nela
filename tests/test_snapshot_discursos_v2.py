from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from processamento.snapshot_discursos_v2 import (
    SNAPSHOT_FIELDS,
    SNAPSHOT_INPUTS,
    write_snapshot_v2_smoke,
)


COMMIT = "b" * 40


def test_smoke_is_read_only_reconciled_and_schema_valid(tmp_path: Path) -> None:
    parquet_root = tmp_path / "drive" / "processed" / "parquet"
    output_base = tmp_path / "content" / "snapshot-smoke"
    _build_fixture(parquet_root)
    before = _signature(parquet_root)

    result = write_snapshot_v2_smoke(
        parquet_root=parquet_root,
        output_base=output_base,
        operation_id="snapshot-v2-smoke-test-1",
        snapshot_id="discursos-plenario-v2-smoke-test-1",
        code_commit=COMMIT,
        rows_per_base=1,
    )

    assert _signature(parquet_root) == before
    manifest = result["manifest"]
    assert manifest["execution_status"] == "succeeded"
    assert manifest["scientific_gate"] == "needs_review"
    assert manifest["snapshot_id"] == "discursos-plenario-v2-smoke-test-1"
    assert manifest["counts"] == {
        "candidate_files": 3,
        "source_records": 8,
        "within_period_records": 4,
        "excluded_source_records": 4,
        "snapshot_records": 3,
        "excluded_sample_records": 3,
        "duplicate_ids": 0,
    }
    assert len(manifest["outputs"]) == 7

    operation_root = output_base / "snapshot-v2-smoke-test-1"
    snapshot_path = (
        operation_root / "artifacts" / "snapshot_discursos_v2.parquet"
    )
    exclusions_path = (
        operation_root / "artifacts" / "registros_excluidos.parquet"
    )
    snapshot = pq.read_table(snapshot_path)
    exclusions = pq.read_table(exclusions_path)

    assert snapshot.column_names == list(SNAPSHOT_FIELDS)
    assert str(snapshot.schema.field("data").type) == "date32[day]"
    assert snapshot.num_rows == 3
    assert exclusions.num_rows == 3
    assert (
        operation_root / "artifacts" / "contagens_por_etapa.csv"
    ).exists()
    assert (operation_root / "artifacts" / "schema.json").exists()
    assert (operation_root / "manifest.json").exists()
    assert (operation_root / "logs" / "execution.jsonl").exists()
    report = (operation_root / "relatorio.md").read_text(encoding="utf-8")
    assert "o snapshot integral não foi criado" in report
    assert "não pode ser promovido" in report


def test_smoke_preserves_missing_author_and_builds_ordered_flags(
    tmp_path: Path,
) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)

    result = write_snapshot_v2_smoke(
        parquet_root=parquet_root,
        output_base=tmp_path / "output",
        operation_id="snapshot-v2-smoke-author",
        snapshot_id="discursos-plenario-v2-smoke-author",
        code_commit=COMMIT,
        rows_per_base=2,
    )

    snapshot_path = (
        result["paths"]["artifacts"] / "snapshot_discursos_v2.parquet"
    )
    rows = pq.read_table(snapshot_path).to_pylist()
    camara = next(row for row in rows if row["texto_id"] == "camara-1")

    assert camara["parlamentar_nome"] is None
    assert camara["autor_disponivel"] is False
    assert camara["qualidade_flags"] == [
        "autor_ausente",
        "partido_ausente",
        "uf_ausente",
        "data_hora_ausente",
        "sessao_id_ausente",
        "evento_id_ausente",
        "pronunciamento_id_ausente",
    ]
    assert camara["texto_tamanho"] == len(camara["texto"])


def test_smoke_selection_is_deterministic(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)

    selected = []
    for index in (1, 2):
        result = write_snapshot_v2_smoke(
            parquet_root=parquet_root,
            output_base=tmp_path / f"output-{index}",
            operation_id=f"snapshot-v2-smoke-deterministic-{index}",
            snapshot_id=f"discursos-plenario-v2-smoke-deterministic-{index}",
            code_commit=COMMIT,
            rows_per_base=1,
        )
        table = pq.read_table(
            result["paths"]["artifacts"]
            / "snapshot_discursos_v2.parquet",
            columns=["texto_id", "input_parquet"],
        )
        selected.append(table.to_pylist())

    assert selected[0] == selected[1]


def test_smoke_stops_on_duplicate_id_across_sources(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)
    senate_path = parquet_root / SNAPSHOT_INPUTS[1].filename
    rows = pq.read_table(senate_path).to_pylist()
    rows[0]["texto_id"] = "camara-1"
    pq.write_table(pa.Table.from_pylist(rows), senate_path)

    with pytest.raises(ValueError, match="duplicate_ids=1"):
        write_snapshot_v2_smoke(
            parquet_root=parquet_root,
            output_base=tmp_path / "output",
            operation_id="snapshot-v2-smoke-duplicate",
            snapshot_id="discursos-plenario-v2-smoke-duplicate",
            code_commit=COMMIT,
            rows_per_base=1,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("texto_id", "", "missing_texto_id=1"),
        ("texto", "", "missing_text=1"),
        ("raw_path", None, "missing_provenance=1"),
    ],
)
def test_smoke_stops_instead_of_silently_dropping_required_records(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)
    path = parquet_root / SNAPSHOT_INPUTS[0].filename
    rows = pq.read_table(path).to_pylist()
    rows[0][field] = value
    if field == "raw_path":
        rows[0]["raw_source_id"] = None
    pq.write_table(pa.Table.from_pylist(rows), path)

    with pytest.raises(ValueError, match=message):
        write_snapshot_v2_smoke(
            parquet_root=parquet_root,
            output_base=tmp_path / "output",
            operation_id="snapshot-v2-smoke-invalid",
            snapshot_id="discursos-plenario-v2-smoke-invalid",
            code_commit=COMMIT,
            rows_per_base=1,
        )


def test_smoke_refuses_output_inside_input_root(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    _build_fixture(parquet_root)

    with pytest.raises(ValueError, match="não pode ficar dentro"):
        write_snapshot_v2_smoke(
            parquet_root=parquet_root,
            output_base=parquet_root / "output",
            operation_id="snapshot-v2-smoke-output",
            snapshot_id="discursos-plenario-v2-smoke-output",
            code_commit=COMMIT,
            rows_per_base=1,
        )


def test_smoke_refuses_reusing_operation_id(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    output_base = tmp_path / "output"
    _build_fixture(parquet_root)
    kwargs = {
        "parquet_root": parquet_root,
        "output_base": output_base,
        "operation_id": "snapshot-v2-smoke-reuse",
        "snapshot_id": "discursos-plenario-v2-smoke-reuse",
        "code_commit": COMMIT,
        "rows_per_base": 1,
    }

    write_snapshot_v2_smoke(**kwargs)
    with pytest.raises(FileExistsError, match="já possui artefatos"):
        write_snapshot_v2_smoke(**kwargs)


def _build_fixture(parquet_root: Path) -> None:
    parquet_root.mkdir(parents=True, exist_ok=True)
    rows_by_file = {
        "camara__plenario_discursos.parquet": [
            _row(
                "camara-1",
                "camara",
                "plenario_discursos",
                "plenario",
                "discurso",
                "2020-05-10",
                missing_author=True,
            ),
            _row(
                "camara-2",
                "camara",
                "plenario_discursos",
                "plenario",
                "discurso",
                "2021-06-11",
            ),
            _row(
                "camara-old",
                "camara",
                "plenario_discursos",
                "plenario",
                "discurso",
                "2009-12-31",
            ),
        ],
        "senado__plenario_discursos.parquet": [
            _row(
                "senado-1",
                "senado",
                "plenario_discursos",
                "plenario",
                "pronunciamento",
                "2022-05-10",
            ),
            _row(
                "senado-future",
                "senado",
                "plenario_discursos",
                "plenario",
                "pronunciamento",
                "2026-07-14",
            ),
        ],
        "senado__congresso_discursos.parquet": [
            _row(
                "congresso-1",
                "senado",
                "congresso_discursos",
                "congresso",
                "pronunciamento",
                "2023-05-10",
            ),
            _row(
                "congresso-invalid",
                "senado",
                "congresso_discursos",
                "congresso",
                "pronunciamento",
                "sem-data",
            ),
            _row(
                "congresso-old",
                "senado",
                "congresso_discursos",
                "congresso",
                "pronunciamento",
                "2008-01-01",
            ),
        ],
    }
    for filename, rows in rows_by_file.items():
        pq.write_table(pa.Table.from_pylist(rows), parquet_root / filename)


def _row(
    texto_id: str,
    source: str,
    dataset: str,
    ambito: str,
    unidade_analitica: str,
    data: str,
    *,
    missing_author: bool = False,
) -> dict[str, object]:
    author = None if missing_author else "Pessoa"
    return {
        "texto_id": texto_id,
        "dataset_version": "v1",
        "source": source,
        "dataset": dataset,
        "casa": (
            "Camara dos Deputados"
            if source == "camara"
            else "Senado Federal"
        ),
        "ambito": ambito,
        "orgao_sigla": None,
        "orgao_nome": None,
        "documento_tipo": "discurso",
        "unidade_analitica": unidade_analitica,
        "data": data,
        "data_hora": None if missing_author else "2020-05-10T14:00:00",
        "ano": 2020,
        "mes": 5,
        "titulo": None,
        "resumo": None,
        "indexacao": None,
        "tipo_discurso": None,
        "tipo_uso_palavra": None,
        "fase_evento": None,
        "parlamentar_id": None if missing_author else "1",
        "parlamentar_nome": author,
        "parlamentar_partido": None if missing_author else "ABC",
        "parlamentar_uf": None if missing_author else "DF",
        "parlamentar_cargo": None if missing_author else "Parlamentar",
        "pronunciamento_id": None,
        "sessao_id": None,
        "evento_id": None,
        "texto": f"Texto integral de {texto_id}.",
        "texto_tamanho": 999,
        "texto_status": "disponivel",
        "forma": "texto",
        "metodo_obtencao": "api",
        "url_texto": None,
        "url_audio": None,
        "url_video": None,
        "url_origem": "https://example.test/",
        "raw_run_id": "run",
        "raw_record_type": "record",
        "raw_source_id": texto_id,
        "raw_partition": "ano=2020/mes=05",
        "raw_collected_at": "2026-07-13T00:00:00Z",
        "raw_checksum": "a" * 64,
        "raw_path": f"raw/{source}/{dataset}/{texto_id}.json",
        "raw_response_url": "https://example.test/",
    }


def _signature(root: Path) -> dict[str, tuple[int, int]]:
    return {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.glob("*.parquet"))
    }
