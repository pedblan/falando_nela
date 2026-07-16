from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from processamento.normalizacao import (
    PartitionedJsonlWriter,
    normalize_data_root,
    normalize_raw_record,
)


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


def test_normalize_senado_pronunciamento_uses_data_pronunciamento(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "senado" / "congresso_discursos" / "ano=2010" / "mes=03" / "run.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "backfill-cn",
        "source": "senado",
        "dataset": "congresso_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "CN:pronunciamento:456",
        "partition": "2010-03",
        "payload": {
            "codigo_pronunciamento": "456",
            "texto": "Texto recuperado.",
            "metadata": {
                "sessao": {},
                "pronunciamento": {"DataPronunciamento": "2010-03-10"},
            },
            "fontes": {},
        },
    }

    normalized = normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path)

    assert normalized[0]["data"] == "2010-03-10"
    assert normalized[0]["ano"] == "2010"
    assert normalized[0]["mes"] == "03"


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
                    "transcricao": "A SRA. CONCEIÇÃO SAMPAIO — ação, saúde e Constituição.",
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
        deputados_index={"999": {"nome": "Conceição Sampaio", "siglaPartido": "XYZ", "siglaUf": "RJ"}},
    )

    assert len(normalized) == 1
    record = normalized[0]
    assert record["source"] == "camara"
    assert record["parlamentar_id"] == "999"
    assert record["parlamentar_nome"] == "Conceição Sampaio"
    assert record["texto"] == "A SRA. CONCEIÇÃO SAMPAIO — ação, saúde e Constituição."
    assert record["evento_id"] == "111"
    assert record["texto_status"] == "disponivel"


def test_normalize_camara_discursos_page_ignores_payload_outside_record_period(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "camara" / "plenario_discursos" / "ano=2010" / "mes=03" / "run.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "run",
        "source": "camara",
        "dataset": "plenario_discursos",
        "record_type": "discursos_page",
        "source_id": "deputado:10:discursos:2010-03:pagina:2",
        "partition": "2010-03",
        "periodo": {"data_inicio": "2010-03-01", "data_fim": "2010-03-31"},
        "request": {
            "method": "GET",
            "path": "https://dadosabertos.camara.leg.br/api/v2/deputados/10/discursos",
            "params": {
                "dataInicio": "2010-03-01",
                "dataFim": "2010-03-31",
                "pagina": 2,
                "itens": 100,
            },
        },
        "payload": {"dados": [{"dataHoraInicio": "2009-01-01T10:00", "transcricao": "fora do mês"}]},
    }

    assert normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path) == []


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


def test_normalize_data_root_can_filter_raw_run_ids(tmp_path: Path) -> None:
    path = tmp_path / "raw" / "camara" / "plenario_discursos" / "ano=2026" / "mes=05" / "runs.jsonl"
    path.parent.mkdir(parents=True)
    _write_jsonl(path, [_camara_discursos_record("old-run", "Texto antigo"), _camara_discursos_record("new-run", "Texto novo")])

    manifest = normalize_data_root(tmp_path, run_id="filtered", overwrite=True, raw_run_ids=["new-run"])

    output_path = tmp_path / "processed" / "textos_parlamentares" / "v1" / "ano=2026" / "mes=05" / "filtered.jsonl"
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert manifest["output_records"] == 1
    assert manifest["raw_run_id_filter"] == ["new-run"]
    assert manifest["skipped_counts"]["raw_run_id_filtered"] == 1
    assert rows[0]["texto"] == "Texto novo"


def test_partitioned_writer_only_publishes_completed_jsonl(tmp_path: Path) -> None:
    writer = PartitionedJsonlWriter(output_root=tmp_path, run_id="atomic")
    writer.write({"ano": "2026", "mes": "05", "texto_id": "texto-1"})

    final_path = tmp_path / "ano=2026" / "mes=05" / "atomic.jsonl"
    partial_path = final_path.with_name("atomic.jsonl.partial")
    assert partial_path.exists()
    assert not final_path.exists()

    writer.close(commit=True)

    assert final_path.exists()
    assert not partial_path.exists()
    assert json.loads(final_path.read_text(encoding="utf-8"))["texto_id"] == "texto-1"


def test_partitioned_writer_rejects_invalid_partial_without_publishing(tmp_path: Path) -> None:
    writer = PartitionedJsonlWriter(output_root=tmp_path, run_id="invalid")
    writer.write({"ano": "2026", "mes": "05", "texto_id": "texto-1"})

    final_path = tmp_path / "ano=2026" / "mes=05" / "invalid.jsonl"
    partial_path = final_path.with_name("invalid.jsonl.partial")
    handle = writer._handles[final_path]
    handle.flush()
    with partial_path.open("a", encoding="utf-8") as extra:
        extra.write('{"texto_id": "truncado"')

    with pytest.raises(ValueError, match="JSONL inválido"):
        writer.close(commit=True)

    assert not final_path.exists()


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
