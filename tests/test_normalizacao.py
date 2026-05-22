from __future__ import annotations

import json
import os
from pathlib import Path

from processamento.normalizacao import normalize_data_root, normalize_raw_record


def test_normalize_senado_pronunciamento(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "senado" / "plenario_discursos" / "ano=2026" / "mes=05" / "run.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "run",
        "source": "senado",
        "dataset": "plenario_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "SF:pronunciamento:123",
        "partition": "2026-05",
        "collected_at": "2026-05-18T12:00:00+00:00",
        "checksum": "abc",
        "response": {"url": "https://example.test/texto/123"},
        "payload": {
            "codigo_pronunciamento": "123",
            "texto": " Texto integral ",
            "texto_status": "disponivel",
            "forma": "texto",
            "metodo_obtencao": "api_texto_integral",
            "fontes": {"texto_integral_txt": "https://example.test/texto/123"},
            "metadata": {
                "sessao": {"CodigoSessao": "9", "DataSessao": "2026-05-18", "SiglaCasa": "SF"},
                "pronunciamento": {
                    "CodigoParlamentar": "456",
                    "NomeAutor": "Senadora Teste",
                    "Partido": "ABC",
                    "UF": "SP",
                    "Data": "2026-05-18",
                    "Resumo": "Resumo",
                    "TipoUsoPalavra": {"Descricao": "Discurso"},
                },
            },
        },
    }

    normalized = normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path)

    assert len(normalized) == 1
    record = normalized[0]
    assert record["texto_id"] == "senado:plenario_discursos:pronunciamento:123"
    assert record["data"] == "2026-05-18"
    assert record["ano"] == "2026"
    assert record["mes"] == "05"
    assert record["texto"] == "Texto integral"
    assert record["parlamentar_nome"] == "Senadora Teste"
    assert record["raw_path"] == "raw/senado/plenario_discursos/ano=2026/mes=05/run.jsonl"


def test_normalize_camara_discursos_page_uses_deputado_index(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "ano=2026" / "mes=05" / "run.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "run",
        "source": "camara",
        "dataset": "plenario_discursos",
        "record_type": "discursos_page",
        "source_id": "deputado:999:discursos:2026-05:pagina:1",
        "partition": "2026-05",
        "collected_at": "2026-05-18T12:00:00+00:00",
        "checksum": "abc",
        "response": {"url": "https://example.test/page"},
        "payload": {
            "dados": [
                {
                    "dataHoraInicio": "2026-05-18T10:30",
                    "tipoDiscurso": "PELA ORDEM",
                    "transcricao": "Fala da deputada.",
                    "sumario": "Resumo",
                    "keywords": "tema",
                    "faseEvento": {"titulo": "Breves Comunicacoes"},
                    "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/111",
                    "urlAudio": "https://example.test/audio",
                    "urlVideo": "https://example.test/video",
                }
            ]
        },
    }

    normalized = normalize_raw_record(
        raw_record,
        raw_path=raw_path,
        data_root=tmp_path,
        deputados_index={"999": {"nome": "Deputada Teste", "siglaPartido": "XYZ", "siglaUf": "RJ"}},
    )

    assert len(normalized) == 1
    record = normalized[0]
    assert record["source"] == "camara"
    assert record["parlamentar_id"] == "999"
    assert record["parlamentar_nome"] == "Deputada Teste"
    assert record["evento_id"] == "111"
    assert record["texto_status"] == "disponivel"


def test_normalize_data_root_writes_partitioned_jsonl_and_deduplicates_newer_first(tmp_path: Path) -> None:
    metadata_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "metadata" / "deputados.jsonl"
    metadata_path.parent.mkdir(parents=True)
    _write_jsonl(
        metadata_path,
        [
            {
                "run_id": "meta",
                "source": "camara",
                "dataset": "plenario_discursos",
                "record_type": "deputados_page",
                "source_id": "deputados:pagina:1",
                "partition": "metadata",
                "payload": {"dados": [{"id": 999, "nome": "Deputada Nova", "siglaPartido": "XYZ", "siglaUf": "RJ"}]},
            }
        ],
    )
    older = _camara_discursos_record("old-run", "Texto antigo")
    newer = _camara_discursos_record("new-run", "Texto novo")
    older_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "ano=2026" / "mes=05" / "old.jsonl"
    newer_path = older_path.with_name("new.jsonl")
    older_path.parent.mkdir(parents=True)
    _write_jsonl(older_path, [older])
    _write_jsonl(newer_path, [newer])
    os.utime(older_path, (1, 1))
    os.utime(newer_path, (2, 2))

    manifest = normalize_data_root(tmp_path, run_id="test-run", overwrite=True)

    output_path = tmp_path / "processed" / "textos_parlamentares" / "v1" / "ano=2026" / "mes=05" / "test-run.jsonl"
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert manifest["output_records"] == 1
    assert rows[0]["texto"] == "Texto novo"
    assert rows[0]["parlamentar_nome"] == "Deputada Nova"
    assert manifest["skipped_counts"]["duplicate_texto_id"] == 1


def _camara_discursos_record(run_id: str, texto: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "source": "camara",
        "dataset": "plenario_discursos",
        "record_type": "discursos_page",
        "source_id": "deputado:999:discursos:2026-05:pagina:1",
        "partition": "2026-05",
        "collected_at": "2026-05-18T12:00:00+00:00",
        "checksum": run_id,
        "response": {"url": "https://example.test/page"},
        "payload": {
            "dados": [
                {
                    "dataHoraInicio": "2026-05-18T10:30",
                    "tipoDiscurso": "PELA ORDEM",
                    "transcricao": texto,
                    "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/111",
                }
            ]
        },
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

