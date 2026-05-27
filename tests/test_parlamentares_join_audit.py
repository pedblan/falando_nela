from __future__ import annotations

import csv
import json
from pathlib import Path

from processamento.normalizacao import DATASET_VERSION, PROCESSED_FIELDS
from processamento.parlamentares import PERIODOS_FIELDS, write_parquet_table
from processamento.parlamentares_join_audit import audit_join, resolve_audit_paths


def test_audit_join_reports_matches_unmatched_and_gender_distribution(tmp_path: Path) -> None:
    textos_root = tmp_path / "textos"
    parlamentares_root = tmp_path / "parlamentares"
    output_root = tmp_path / "audits" / "parlamentares" / "run"
    write_parquet_table(
        textos_root / "camara__plenario_discursos.parquet",
        [
            _text_row("texto-1", "camara", "204379", "2024-05-01"),
            _text_row("texto-2", "camara", "999999", "2024-05-01"),
            _text_row("texto-3", "camara", None, "2024-05-01"),
        ],
        PROCESSED_FIELDS,
    )
    write_parquet_table(
        parlamentares_root / "parlamentares_periodos.parquet",
        [
            _periodo_row(
                parlamentar_key="camara:204379",
                source="camara",
                parlamentar_id="204379",
                genero="feminino",
                vigencia_inicio="2023-02-01",
                vigencia_fim="2027-01-31",
                vigencia_fim_exclusivo="2027-02-01",
            )
        ],
        PERIODOS_FIELDS,
    )

    manifest = audit_join(
        textos_parquet_root=textos_root,
        parlamentares_parquet_root=parlamentares_root,
        output_root=output_root,
        run_id="join-test",
        overwrite=True,
    )

    coverage = list(csv.DictReader((output_root / "join_coverage.csv").open(encoding="utf-8")))
    gender = list(csv.DictReader((output_root / "gender_distribution.csv").open(encoding="utf-8")))
    unmatched = _read_jsonl(output_root / "unmatched_textos.jsonl")

    assert manifest["textos_lidos"] == 3
    assert {row["status"] for row in coverage} == {"matched", "unmatched", "sem_autoria_individual"}
    assert gender == [{"source": "camara", "dataset": "plenario_discursos", "ano": "2024", "genero": "feminino", "textos": "1"}]
    assert unmatched[0]["texto_id"] == "texto-2"


def test_resolve_audit_paths_uses_colab_and_samples_defaults() -> None:
    sample = resolve_audit_paths(_args(profile="samples-local", run_id="sample-run"), env={})
    assert sample["textos_parquet_root"] == Path("data/samples/textos_parlamentares/v1/parquet")
    assert sample["parlamentares_parquet_root"] == Path("data/samples/parlamentares/v1/parquet")
    assert sample["output_root"] == Path("data/samples/textos_parlamentares/v1/audits/parlamentares/sample-run")

    colab = resolve_audit_paths(
        _args(profile="colab", run_id="colab-run"),
        env={"FALANDO_NELA_DATA_ROOT": "/content/drive/MyDrive/falando_nela/data"},
    )
    assert colab["textos_parquet_root"] == Path("/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet")
    assert colab["parlamentares_parquet_root"] == Path("/content/drive/MyDrive/falando_nela/data/processed/parlamentares/v1/parquet")
    assert colab["output_root"] == Path("/content/drive/MyDrive/falando_nela/data/processed/audits/parlamentares/colab-run")


def _text_row(texto_id: str, source: str, parlamentar_id: str | None, data: str) -> dict[str, object]:
    row = {field: None for field in PROCESSED_FIELDS}
    row.update(
        {
            "texto_id": texto_id,
            "dataset_version": DATASET_VERSION,
            "source": source,
            "dataset": "plenario_discursos",
            "documento_tipo": "discurso",
            "data": data,
            "ano": data[:4],
            "parlamentar_id": parlamentar_id,
            "parlamentar_nome": "Nome",
            "texto": "Texto",
        }
    )
    return row


def _periodo_row(**overrides: object) -> dict[str, object]:
    row = {field: None for field in PERIODOS_FIELDS}
    row.update(
        {
            "dataset_version": "v1",
            "source": "camara",
            "casa": "Camara dos Deputados",
            "nome_parlamentar": "Ana Silva",
            "match_priority": 1,
            "intervalo_inferido": False,
        }
    )
    row.update(overrides)
    return row


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _args(**overrides: object):
    import argparse

    values = {
        "profile": None,
        "data_root": None,
        "textos_parquet_root": None,
        "parlamentares_parquet_root": None,
        "output_root": None,
        "run_id": None,
        "overwrite": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)
