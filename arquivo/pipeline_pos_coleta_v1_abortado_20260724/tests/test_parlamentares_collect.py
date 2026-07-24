from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from processamento.normalizacao import DATASET_VERSION, PROCESSED_FIELDS
from processamento.parlamentares import write_parquet_table
from coleta.parlamentares.collect import (
    discover_text_parlamentar_ids,
    discover_existing_parlamentar_ids,
    extract_senado_parlamentar_ids,
    legislaturas_for_period,
)


def test_legislaturas_for_period_baseline() -> None:
    assert legislaturas_for_period(date(2011, 5, 18), date(2026, 5, 18)) == [54, 55, 56, 57]


def test_extract_senado_parlamentar_ids_from_nested_payload() -> None:
    payload = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {"IdentificacaoParlamentar": {"CodigoParlamentar": "5672"}},
                    {"IdentificacaoParlamentar": {"CodigoParlamentar": "5672"}},
                    {"IdentificacaoParlamentar": {"CodigoParlamentar": "5000"}},
                ]
            }
        }
    }

    assert extract_senado_parlamentar_ids(payload) == ["5000", "5672"]


def test_discover_existing_parlamentar_ids_uses_official_ids_only(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "camara" / "pareceres_pec" / "ano=2026" / "mes=05" / "run.jsonl"
    _write_jsonl(
        raw_path,
        [
            {
                "source": "camara",
                "dataset": "pareceres_pec",
                "record_type": "parecer_pec_texto",
                "source_id": "proposicao:999:documento:123",
                "payload": {"id": 999, "idDeputado": 204379},
            }
        ],
    )
    processed_path = tmp_path / "processed" / "textos_parlamentares" / "v1" / "ano=2026" / "mes=05" / "run.jsonl"
    _write_jsonl(
        processed_path,
        [
            {
                "source": "camara",
                "parlamentar_id": "204380",
            }
        ],
    )

    assert discover_existing_parlamentar_ids(tmp_path, "camara") == ["204379", "204380"]


def test_discover_text_parlamentar_ids_reads_jsonl_and_parquet_samples(tmp_path: Path) -> None:
    textos_root = tmp_path / "samples" / "textos_parlamentares" / "v1"
    _write_jsonl(
        textos_root / "ano=2026" / "mes=05" / "sample.jsonl",
        [
            {"source": "camara", "parlamentar_id": "204379"},
            {"source": "senado", "parlamentar_id": "5672"},
            {"source": "camara", "parlamentar_id": None},
        ],
    )
    write_parquet_table(
        textos_root / "parquet" / "camara__plenario_discursos.parquet",
        [
            _processed_row("camara", "204380"),
            _processed_row("senado", "5000"),
        ],
        PROCESSED_FIELDS,
    )

    assert discover_text_parlamentar_ids(textos_root, "camara") == ["204379", "204380"]
    assert discover_text_parlamentar_ids(textos_root, "senado") == ["5000", "5672"]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _processed_row(source: str, parlamentar_id: str) -> dict[str, object]:
    row = {field: None for field in PROCESSED_FIELDS}
    row.update(
        {
            "texto_id": f"{source}:{parlamentar_id}:texto",
            "dataset_version": DATASET_VERSION,
            "source": source,
            "dataset": "plenario_discursos",
            "documento_tipo": "discurso",
            "data": "2026-05-01",
            "ano": "2026",
            "parlamentar_id": parlamentar_id,
            "texto": "Texto",
        }
    )
    return row
