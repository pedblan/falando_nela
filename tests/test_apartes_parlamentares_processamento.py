from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from processamento.apartes_parlamentares import APARTES_FIELDS, process_apartes_data_root


def test_process_apartes_senado_generates_jsonl_parquet_and_audits(tmp_path: Path) -> None:
    _write_parlamentares_periodos(
        tmp_path,
        [
            _periodo("senado", "22", "Esperidiao Amin", "masculino", "PP", "SC"),
            _periodo("senado", "5502", "Plinio Valerio", "masculino", "PSDB", "AM"),
        ],
    )
    _write_raw(
        tmp_path,
        "senado",
        "run-senado-apartes",
        [
            _raw_record(
                "senado",
                "senador_apartes_year_probe",
                "SF:senador:22:apartes:20250101:20251231",
                _senado_payload(aparteante_id="22", pronunciamento_id="519407"),
            ),
            _raw_record(
                "senado",
                "senador_apartes_metadata",
                "SF:senador:22:apartes:20251201:20251231",
                _senado_payload(aparteante_id="22", pronunciamento_id="519407"),
            ),
            _raw_record(
                "senado",
                "senador_apartes_metadata",
                "SF:senador:22:apartes:20251201:20251231:duplicado",
                _senado_payload(aparteante_id="22", pronunciamento_id="519407"),
            ),
        ],
    )

    manifest = process_apartes_data_root(tmp_path, run_id="processed-apartes-test", overwrite=True)

    output_path = tmp_path / "processed" / "apartes_parlamentares" / "v1" / "apartes_parlamentares.jsonl"
    rows = _read_jsonl(output_path)
    assert len(rows) == 1
    assert list(rows[0]) == APARTES_FIELDS
    assert rows[0]["source"] == "senado"
    assert rows[0]["ano"] == 2025
    assert rows[0]["mes"] == 12
    assert rows[0]["pronunciamento_id"] == "519407"
    assert rows[0]["aparteante_id"] == "22"
    assert rows[0]["aparteante_genero"] == "masculino"
    assert rows[0]["aparteante_partido"] == "PP"
    assert rows[0]["orador_id"] == "5502"
    assert rows[0]["orador_genero"] == "masculino"
    assert rows[0]["match_status"] == "matched"
    assert manifest["skipped_counts"]["probe_record"] == 1
    assert manifest["skipped_counts"]["duplicate_aparte_id"] == 1
    assert manifest["output_records"] == 1

    table = pq.read_table(tmp_path / "processed" / "apartes_parlamentares" / "v1" / "parquet" / "apartes_parlamentares.parquet")
    assert table.num_rows == 1
    assert table.column_names == APARTES_FIELDS
    assert (tmp_path / "processed" / "audits" / "apartes_parlamentares" / "processed-apartes-test" / "contagens_anuais.csv").exists()


def test_process_apartes_camara_marks_ambiguous_name_match(tmp_path: Path) -> None:
    _write_parlamentares_periodos(
        tmp_path,
        [
            _periodo("camara", "100", "Ana Silva", "feminino", "AAA", "SP"),
            _periodo("camara", "101", "Ana Silva", "feminino", "BBB", "RJ"),
            _periodo("camara", "47", "Bruno Costa", "masculino", "CCC", "MG"),
        ],
    )
    _write_raw(
        tmp_path,
        "camara",
        "run-camara-apartes",
        [
            _raw_record(
                "camara",
                "sitaq_apartes_quarter_probe",
                "camara:aparteante:ana-silva:quarter-probe:2025-01-01:2025-03-31:pagina:1",
                {"aparteante_consultado": "Ana Silva", "chaves_extraidas": []},
            ),
            _raw_record(
                "camara",
                "sitaq_apartes_search_page",
                "camara:aparteante:ana-silva:2025-03-01:2025-03-31:pagina:1",
                {
                    "aparteante_consultado": "Ana Silva",
                    "aparteante_id_consultado": None,
                    "page_number": 1,
                    "total_pages_detected": 1,
                    "chaves_extraidas": [
                        {
                            "href": "TextoHTML.asp?Data=05/03/2025&nuSessao=1&nuQuarto=2&nuOrador=47&nuInsercao=0&sgFaseSessao=PE&txApelido=Bruno%20Costa",
                            "discurso_chave": "05/03/2025|1|2|47|0|PE",
                            "nuSessao": "1",
                            "nuQuarto": "2",
                            "nuOrador": "47",
                            "nuInsercao": "0",
                            "Data": "05/03/2025",
                            "sgFaseSessao": "PE",
                            "txApelido": "Bruno Costa",
                            "txTipoSessao": "Deliberativa",
                        }
                    ],
                },
            ),
        ],
    )

    manifest = process_apartes_data_root(tmp_path, run_id="processed-apartes-camara-test", overwrite=True)

    rows = _read_jsonl(tmp_path / "processed" / "apartes_parlamentares" / "v1" / "apartes_parlamentares.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "camara"
    assert rows[0]["data"] == "2025-03-05"
    assert rows[0]["aparteante_id"] is None
    assert rows[0]["aparteante_nome"] == "Ana Silva"
    assert rows[0]["aparteante_genero"] is None
    assert rows[0]["orador_id"] == "47"
    assert rows[0]["orador_genero"] == "masculino"
    assert rows[0]["match_status"] == "ambiguous"
    assert rows[0]["url_texto"].startswith("https://www.camara.leg.br/internet/SitaqWeb/TextoHTML.asp")
    assert manifest["skipped_counts"]["probe_record"] == 1


def _periodo(
    source: str,
    parlamentar_id: str,
    nome: str,
    genero: str,
    partido: str,
    uf: str,
) -> dict[str, object]:
    return {
        "parlamentar_key": f"{source}:{parlamentar_id}",
        "dataset_version": "v1",
        "source": source,
        "casa": "SF" if source == "senado" else "CD",
        "parlamentar_id": parlamentar_id,
        "nome_parlamentar": nome,
        "nome_civil": nome,
        "genero": genero,
        "partido_sigla": partido,
        "uf": uf,
        "vigencia_inicio": "2023-02-01",
        "vigencia_fim": "2027-01-31",
        "vigencia_fim_exclusivo": "2027-02-01",
    }


def _senado_payload(*, aparteante_id: str, pronunciamento_id: str) -> dict[str, object]:
    return {
        "ApartesParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "CodigoParlamentar": aparteante_id,
                    "NomeParlamentar": "Esperidiao Amin",
                    "SexoParlamentar": "Masculino",
                    "SiglaPartidoParlamentar": "PP",
                    "UfParlamentar": "SC",
                },
                "Apartes": {
                    "Aparte": {
                        "CodigoPronunciamento": pronunciamento_id,
                        "DataPronunciamento": "2025-12-10",
                        "SiglaCasaPronunciamento": "SF",
                        "Orador": {
                            "CodigoParlamentar": "5502",
                            "NomeParlamentar": "Plinio Valerio",
                            "SiglaPartidoParlamentarNaData": "PSDB",
                            "UfParlamentarNaData": "AM",
                        },
                        "SessaoPlenaria": {
                            "CodigoSessao": "526727",
                            "DataSessao": "2025-12-10",
                            "SiglaTipoSessao": "DOR",
                        },
                        "TipoUsoPalavra": {"Sigla": "DIS", "Descricao": "Discurso"},
                        "Publicacoes": {"Publicacao": {"UrlDiario": "https://example.test/diario"}},
                        "UrlTexto": f"https://www25.senado.leg.br/web/atividade/pronunciamentos/-/p/texto/{pronunciamento_id}",
                    }
                },
            }
        }
    }


def _raw_record(source: str, record_type: str, source_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": f"raw-{source}",
        "collected_at": "2026-05-30T00:00:00+00:00",
        "source": source,
        "dataset": "plenario_apartes",
        "record_type": record_type,
        "source_id": source_id,
        "partition": "metadata",
        "periodo": {"data_inicio": "2025-01-01", "data_fim": "2025-12-31"},
        "request": {"method": "GET", "path": "/x", "params": {}},
        "response": {"url": f"https://example.test/{source_id}", "status_code": 200, "headers": {}},
        "checksum": source_id,
        "payload": payload,
    }


def _write_raw(tmp_path: Path, source: str, run_id: str, records: list[dict[str, object]]) -> None:
    path = tmp_path / "raw" / source / "plenario_apartes" / "metadata" / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _write_parlamentares_periodos(tmp_path: Path, rows: list[dict[str, object]]) -> None:
    path = tmp_path / "processed" / "parlamentares" / "v1" / "parlamentares_periodos.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
