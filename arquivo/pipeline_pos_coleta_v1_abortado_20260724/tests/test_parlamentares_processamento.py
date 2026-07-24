from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from processamento.parlamentares import (
    DATASET_VERSION,
    MANDATOS_FIELDS,
    PARLAMENTARES_FIELDS,
    PERIODOS_FIELDS,
    build_periodos,
    process_parlamentares_data_root,
)


def test_process_parlamentares_generates_dimension_tables_and_parquets(tmp_path: Path) -> None:
    _write_raw(
        tmp_path,
        "camara",
        "run-camara",
        [
            _raw_record(
                "camara",
                "camara_deputado_detalhe",
                "camara:deputado:204379:detalhe",
                {
                    "dados": {
                        "id": 204379,
                        "uri": "https://dadosabertos.camara.leg.br/api/v2/deputados/204379",
                        "nomeCivil": "ANA SILVA",
                        "sexo": "F",
                        "dataNascimento": "1980-01-02",
                        "ufNascimento": "SP",
                        "municipioNascimento": "Sao Paulo",
                        "ultimoStatus": {
                            "id": 204379,
                            "nome": "Ana Silva",
                            "siglaPartido": "ABC",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "data": "2023-02-01",
                            "situacao": "Exercicio",
                            "condicaoEleitoral": "Titular",
                            "urlFoto": "https://example.test/foto.jpg",
                            "email": "dep.ana@example.test",
                        },
                    }
                },
            ),
            _raw_record(
                "camara",
                "camara_deputado_historico",
                "camara:deputado:204379:historico",
                {
                    "dados": [
                        {
                            "dataHora": "2023-02-01T00:00:00",
                            "siglaPartido": "ABC",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "situacao": "Exercicio",
                            "condicaoEleitoral": "Titular",
                        }
                    ]
                },
            ),
        ],
    )
    _write_raw(
        tmp_path,
        "senado",
        "run-senado",
        [
            _raw_record(
                "senado",
                "senado_senador_detalhe",
                "senado:senador:5672:detalhe",
                {
                    "DetalheParlamentar": {
                        "Parlamentar": {
                            "IdentificacaoParlamentar": {
                                "CodigoParlamentar": "5672",
                                "CodigoPublicoNaLegAtual": "800",
                                "NomeParlamentar": "Alan Rick",
                                "NomeCompletoParlamentar": "Alan Rick Miranda",
                                "SexoParlamentar": "Masculino",
                                "UrlPaginaParlamentar": "https://example.test/senador/5672",
                            },
                            "DadosBasicosParlamentar": {
                                "DataNascimento": "1976-10-23",
                                "Naturalidade": "Rio Branco",
                                "UfNaturalidade": "AC",
                            },
                        }
                    }
                },
            ),
            _raw_record(
                "senado",
                "senado_senador_mandatos",
                "senado:senador:5672:mandatos",
                {
                    "MandatosParlamentar": {
                        "Parlamentar": {
                            "Mandatos": {
                                "Mandato": {
                                    "CodigoMandato": "596",
                                    "UfParlamentar": "AC",
                                    "DescricaoParticipacao": "Titular",
                                    "PrimeiraLegislaturaDoMandato": {
                                        "NumeroLegislatura": "57",
                                        "DataInicio": "2023-02-01",
                                        "DataFim": "2027-01-31",
                                    },
                                }
                            }
                        }
                    }
                },
            ),
            _raw_record(
                "senado",
                "senado_senador_filiacoes",
                "senado:senador:5672:filiacoes",
                {
                    "FiliacoesParlamentar": {
                        "Parlamentar": {
                            "Filiacoes": {
                                "Filiacao": {
                                    "SiglaPartido": "REP",
                                    "NomePartido": "Republicanos",
                                    "DataInicio": "2023-02-01",
                                }
                            }
                        }
                    }
                },
            ),
        ],
    )

    manifest = process_parlamentares_data_root(tmp_path, run_id="processed-parlamentares-test", overwrite=True)

    parlamentares_path = tmp_path / "processed" / "parlamentares" / "v1" / "parlamentares.jsonl"
    periodos_path = tmp_path / "processed" / "parlamentares" / "v1" / "parlamentares_periodos.jsonl"
    parlamentares = _read_jsonl(parlamentares_path)
    periodos = _read_jsonl(periodos_path)

    assert list(parlamentares[0]) == PARLAMENTARES_FIELDS
    assert list(periodos[0]) == PERIODOS_FIELDS
    assert {row["parlamentar_key"] for row in parlamentares} == {"camara:204379", "senado:5672"}
    assert {row["genero"] for row in parlamentares} == {"feminino", "masculino"}
    assert {row["sexo_original"] for row in parlamentares} == {"F", "Masculino"}
    assert any(row["partido_sigla"] == "ABC" and row["vigencia_inicio"] == "2023-02-01" for row in periodos)
    assert any(row["partido_sigla"] == "REP" and row["vigencia_fim"] == "2027-01-31" for row in periodos)
    assert manifest["output_record_counts"]["parlamentares"] == 2

    table = pq.read_table(tmp_path / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares.parquet")
    assert table.num_rows == 2
    assert table.column_names == PARLAMENTARES_FIELDS


def test_process_parlamentares_refuses_to_overwrite_existing_outputs(tmp_path: Path) -> None:
    output_path = tmp_path / "processed" / "parlamentares" / "v1" / "parlamentares.jsonl"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("", encoding="utf-8")

    try:
        process_parlamentares_data_root(tmp_path, run_id="existing", overwrite=False)
    except FileExistsError as exc:
        assert "use --overwrite" in str(exc)
    else:
        raise AssertionError("expected FileExistsError")


def test_camara_historico_consolidates_same_day_changes_without_negative_periods(tmp_path: Path) -> None:
    last_same_day_state = {
        "dataHora": "2023-02-01T18:00:00-03:00",
        "siglaPartido": "BBB",
        "siglaUf": "SP",
        "idLegislatura": 57,
        "situacao": "Exercicio",
        "condicaoEleitoral": "Titular",
    }
    _write_raw(
        tmp_path,
        "camara",
        "run-camara-same-day",
        [
            _raw_record(
                "camara",
                "camara_deputado_detalhe",
                "camara:deputado:100689:detalhe",
                {
                    "dados": {
                        "id": 100689,
                        "nomeCivil": "DEPUTADA TESTE",
                        "sexo": "F",
                        "ultimoStatus": {"id": 100689, "nome": "Deputada Teste"},
                    }
                },
            ),
            _raw_record(
                "camara",
                "camara_deputado_historico",
                "camara:deputado:100689:historico",
                {
                    "dados": [
                        {
                            "dataHora": "2023-02-01T08:00:00-03:00",
                            "siglaPartido": "AAA",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "situacao": "Exercicio",
                            "condicaoEleitoral": "Titular",
                        },
                        {
                            "dataHora": "2023-02-01T18:00:00-03:00",
                            "siglaPartido": "BBA",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "situacao": "Exercicio",
                            "condicaoEleitoral": "Titular",
                        },
                        last_same_day_state,
                        dict(last_same_day_state),
                        {
                            "dataHora": "2023-03-01T09:00:00-03:00",
                            "siglaPartido": "CCC",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "situacao": "Exercicio",
                            "condicaoEleitoral": "Titular",
                        },
                    ]
                },
            ),
        ],
    )

    process_parlamentares_data_root(
        tmp_path,
        run_id="processed-camara-same-day",
        overwrite=True,
        data_fim=None,
    )

    output_root = tmp_path / "processed" / "parlamentares" / "v1"
    mandatos = _read_jsonl(output_root / "mandatos.jsonl")
    periodos = _read_jsonl(output_root / "parlamentares_periodos.jsonl")
    camara_mandatos = [row for row in mandatos if row["parlamentar_key"] == "camara:100689"]
    camara_periodos = [row for row in periodos if row["parlamentar_key"] == "camara:100689"]

    assert len(camara_mandatos) == 2
    assert len(camara_periodos) == 2
    assert [row["data_inicio"] for row in camara_mandatos] == ["2023-02-01", "2023-03-01"]
    assert camara_mandatos[0]["partido_sigla"] == "BBB"
    assert camara_mandatos[0]["data_fim"] == "2023-02-28"
    assert camara_periodos[0]["partido_sigla"] == "BBB"
    assert camara_periodos[0]["vigencia_fim"] == "2023-02-28"
    assert all(
        not row.get("data_fim") or not row.get("data_inicio") or row["data_inicio"] <= row["data_fim"]
        for row in camara_mandatos
    )
    assert all(row["vigencia_inicio"] <= row["vigencia_fim"] for row in camara_periodos)

    for row in camara_mandatos:
        assert row["raw_run_id"] == "raw-camara"
        assert row["raw_source_id"] == "camara:deputado:100689:historico"
        assert row["raw_checksum"] == "camara:deputado:100689:historico"
        assert row["raw_path"].endswith("raw/camara/parlamentares/metadata/run-camara-same-day.jsonl")
        assert row["raw_response_url"].endswith("camara:deputado:100689:historico")

    assert all(list(row) == MANDATOS_FIELDS and row["dataset_version"] == DATASET_VERSION for row in mandatos)
    assert all(list(row) == PERIODOS_FIELDS and row["dataset_version"] == DATASET_VERSION for row in periodos)
    mandatos_parquet = pq.read_table(output_root / "parquet" / "mandatos.parquet")
    periodos_parquet = pq.read_table(output_root / "parquet" / "parlamentares_periodos.parquet")
    assert mandatos_parquet.column_names == MANDATOS_FIELDS
    assert periodos_parquet.column_names == PERIODOS_FIELDS
    assert set(mandatos_parquet.column("dataset_version").to_pylist()) == {DATASET_VERSION}
    assert set(periodos_parquet.column("dataset_version").to_pylist()) == {DATASET_VERSION}


def test_build_periodos_refuses_negative_interval() -> None:
    parlamentar = {
        "parlamentar_key": "camara:1",
        "source": "camara",
        "casa": "Camara dos Deputados",
        "parlamentar_id": "1",
    }
    mandato = {
        "parlamentar_key": "camara:1",
        "source": "camara",
        "parlamentar_id": "1",
        "mandato_id": "camara:1:invalido",
        "data_inicio": "2023-02-01",
        "data_fim": "2023-01-31",
    }

    with pytest.raises(ValueError, match="Intervalo parlamentar invalido"):
        build_periodos(
            parlamentares={"camara:1": parlamentar},
            mandatos=[mandato],
            filiacoes=[],
            data_inicio=None,
            data_fim=None,
        )


def test_process_parlamentares_builds_camara_periodos_from_legislature_lists(tmp_path: Path) -> None:
    _write_raw(
        tmp_path,
        "camara",
        "run-camara-list",
        [
            _raw_record(
                "camara",
                "camara_legislaturas_page",
                "camara:legislaturas:pagina:1",
                {
                    "dados": [
                        {
                            "id": 57,
                            "uri": "https://dadosabertos.camara.leg.br/api/v2/legislaturas/57",
                            "dataInicio": "2023-02-01",
                            "dataFim": "2027-01-31",
                        }
                    ]
                },
            ),
            _raw_record(
                "camara",
                "camara_deputados_page",
                "camara:deputados:legislatura:57:pagina:1",
                {
                    "dados": [
                        {
                            "id": 204379,
                            "nome": "Ana Silva",
                            "siglaPartido": "ABC",
                            "siglaUf": "SP",
                            "idLegislatura": 57,
                            "uri": "https://dadosabertos.camara.leg.br/api/v2/deputados/204379",
                        }
                    ]
                },
            ),
        ],
    )

    process_parlamentares_data_root(tmp_path, run_id="processed-camara-list", overwrite=True)

    periodos = _read_jsonl(tmp_path / "processed" / "parlamentares" / "v1" / "parlamentares_periodos.jsonl")

    assert any(
        row["parlamentar_key"] == "camara:204379"
        and row["vigencia_inicio"] == "2023-02-01"
        and row["vigencia_fim"] == "2027-01-31"
        and row["partido_sigla"] == "ABC"
        for row in periodos
    )


def _raw_record(source: str, record_type: str, source_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": f"raw-{source}",
        "collected_at": "2026-05-27T00:00:00+00:00",
        "source": source,
        "dataset": "parlamentares",
        "record_type": record_type,
        "source_id": source_id,
        "partition": "metadata",
        "periodo": {"data_inicio": "2011-05-18", "data_fim": "2026-05-18"},
        "request": {"method": "GET", "path": "/x", "params": {}},
        "response": {"url": f"https://example.test/{source_id}", "status_code": 200, "headers": {}},
        "checksum": source_id,
        "payload": payload,
    }


def _write_raw(tmp_path: Path, source: str, run_id: str, records: list[dict[str, object]]) -> None:
    path = tmp_path / "raw" / source / "parlamentares" / "metadata" / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
