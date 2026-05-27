from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from processamento.parlamentares import (
    DATASET_VERSION,
    PARLAMENTARES_FIELDS,
    PERIODOS_FIELDS,
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
