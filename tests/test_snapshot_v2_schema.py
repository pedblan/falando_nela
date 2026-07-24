from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "specs"
    / "reinicio_analise_plenario"
    / "04_snapshot_discursos_v2"
    / "schema"
    / "snapshot_discursos_v2.record.schema.json"
)


def test_snapshot_v2_record_schema_is_valid_and_accepts_example() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )

    assert list(validator.iter_errors(_example_record())) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("data", "2009-12-31"),
        ("data", "2026-07-14"),
        ("texto_id", ""),
        ("texto", ""),
        ("input_parquet", "senado__ccj_notas.parquet"),
    ],
)
def test_snapshot_v2_record_schema_rejects_out_of_contract_values(
    field: str,
    value: object,
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    record = _example_record()
    record[field] = value

    assert list(validator.iter_errors(record))


def test_snapshot_v2_record_requires_at_least_one_provenance_pointer() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    record = _example_record()
    record["raw_path"] = None
    record["raw_source_id"] = None

    assert list(validator.iter_errors(record))


def _example_record() -> dict[str, object]:
    return {
        "snapshot_id": "discursos-plenario-v2-test",
        "texto_id": "camara:plenario_discursos:discurso:1",
        "dataset_version": "v1",
        "input_parquet": "camara__plenario_discursos.parquet",
        "source": "camara",
        "dataset": "plenario_discursos",
        "casa": "Camara dos Deputados",
        "ambito": "plenario",
        "orgao_sigla": "PLEN",
        "orgao_nome": "Plenario da Camara dos Deputados",
        "documento_tipo": "discurso",
        "unidade_analitica": "discurso",
        "unidade_snapshot": "intervencao_textual_oficial",
        "data": "2020-05-10",
        "data_hora": "2020-05-10T14:00:00",
        "ano": 2020,
        "mes": 5,
        "titulo": None,
        "resumo": None,
        "indexacao": None,
        "tipo_discurso": None,
        "tipo_uso_palavra": None,
        "fase_evento": None,
        "parlamentar_id": "1",
        "parlamentar_nome": "Pessoa",
        "parlamentar_partido": "ABC",
        "parlamentar_uf": "DF",
        "parlamentar_cargo": "Deputado(a)",
        "autor_disponivel": True,
        "pronunciamento_id": None,
        "sessao_id": None,
        "evento_id": "10",
        "texto": "Texto integral.",
        "texto_tamanho": 15,
        "texto_status": "disponivel",
        "forma": "texto",
        "metodo_obtencao": "api_transcricao_discursos",
        "url_texto": None,
        "url_audio": None,
        "url_video": None,
        "url_origem": "https://dadosabertos.camara.leg.br/",
        "raw_run_id": "run",
        "raw_record_type": "discursos_page",
        "raw_source_id": "1",
        "raw_partition": "ano=2020/mes=05",
        "raw_collected_at": "2026-07-13T00:00:00Z",
        "raw_checksum": "a" * 64,
        "raw_path": "raw/camara/plenario_discursos/run.jsonl",
        "raw_response_url": "https://dadosabertos.camara.leg.br/",
        "qualidade_flags": [
            "sessao_id_ausente",
            "pronunciamento_id_ausente"
        ],
    }
