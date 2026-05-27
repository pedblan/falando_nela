from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from processamento.inventario_separadores import (
    detect_parenthetical_lines,
    detect_separator_candidates,
    resolve_inventory_paths,
    write_separator_inventory,
)


def test_detects_structural_headers_stars_and_parentheticals() -> None:
    row = {
        "texto_id": "senado-1",
        "source": "senado",
        "dataset": "plenario_discursos",
        "ano": "2012",
        "mes": "05",
        "texto": (
            "Fala principal.\n"
            "(Soa a campainha.)\n"
            "*****\n"
            "DOCUMENTO A QUE SE REFERE O SENADOR TESTE EM SEU PRONUNCIAMENTO.\n"
            "Texto anexado."
        ),
    }

    candidates = detect_separator_candidates(row, context_chars=80)
    parentheticals = detect_parenthetical_lines(row)

    assert ("asterisk_line", "hard_cut", "ASTERISK_LINE") in {
        (item["kind"], item["action"], item["separator_normalized"]) for item in candidates
    }
    assert ("structural_header", "hard_cut", "DOCUMENTO(S) A QUE SE REFERE") in {
        (item["kind"], item["action"], item["separator_normalized"]) for item in candidates
    }
    assert parentheticals == [
        {
            "source": "senado",
            "dataset": "plenario_discursos",
            "ano": "2012",
            "texto_id": "senado-1",
            "action": "keep",
            "parenthetical_text": "(Soa a campainha.)",
            "parenthetical_normalized": "SOA A CAMPAINHA",
        }
    ]


def test_star_without_structural_header_is_review_and_inline_anexo_is_ignored() -> None:
    row = {
        "texto_id": "senado-2",
        "source": "senado",
        "dataset": "plenario_discursos",
        "ano": "2012",
        "texto": "Fala sobre documento em anexo no proprio corpo.\n*****\nContinua a fala sem cabecalho.",
    }

    candidates = detect_separator_candidates(row, context_chars=80)

    assert [item["action"] for item in candidates] == ["review"]
    assert candidates[0]["kind"] == "asterisk_line"


def test_write_separator_inventory_outputs_required_reports(tmp_path: Path) -> None:
    parquet_root = tmp_path / "parquet"
    output_root = tmp_path / "audits" / "separadores" / "run"
    _write_parquet(
        parquet_root / "camara__plenario_discursos.parquet",
        [
            {
                "texto_id": "camara-1",
                "source": "camara",
                "dataset": "plenario_discursos",
                "ano": "2014",
                "mes": "05",
                "data": "2014-05-08",
                "documento_tipo": "discurso",
                "unidade_analitica": "pronunciamento",
                "texto": "Fala principal.\nARTIGO A QUE SE REFERE O ORADOR\nTexto de artigo.",
            },
            {
                "texto_id": "camara-2",
                "source": "camara",
                "dataset": "plenario_discursos",
                "ano": "2014",
                "mes": "05",
                "texto": "Fala comum mencionando anexo sem separador.",
            },
        ],
    )
    _write_parquet(
        parquet_root / "senado__plenario_discursos.parquet",
        [
            {
                "texto_id": "senado-1",
                "source": "senado",
                "dataset": "plenario_discursos",
                "ano": "2012",
                "mes": "05",
                "texto": "Fala.\n(Pausa.)\n*****\nDOCUMENTO A QUE SE REFERE O SENADOR TESTE.",
            }
        ],
    )

    manifest = write_separator_inventory(
        parquet_root=parquet_root,
        output_root=output_root,
        run_id="run",
        overwrite=True,
        context_chars=80,
        max_examples_per_separator=10,
        ai_sample_rate=1.0,
        ai_sample_max_chars=40,
        batch_size=1,
    )

    assert manifest["input_file_count"] == 2
    assert manifest["separator_occurrences"] == 3
    assert manifest["parenthetical_occurrences"] == 1
    assert manifest["ai_sample"] is True
    assert manifest["ai_sample_records"] == 3
    assert (output_root / "separadores_resumo.csv").exists()
    assert (output_root / "separadores_exemplos.jsonl").exists()
    assert (output_root / "parenteticos_resumo.csv").exists()
    assert (output_root / "amostra_ia_textos.jsonl").exists()
    assert (output_root / "amostra_ia_prompt.md").exists()
    assert (output_root / "amostra_ia_schema.json").exists()
    assert (output_root / "manifest.json").exists()

    summary_rows = _read_csv(output_root / "separadores_resumo.csv")
    assert {
        (row["source"], row["dataset"], row["action"], row["kind"], row["separator_normalized"])
        for row in summary_rows
    } >= {
        ("camara", "plenario_discursos", "hard_cut", "structural_header", "ARTIGO A QUE SE REFERE"),
        ("senado", "plenario_discursos", "hard_cut", "asterisk_line", "ASTERISK_LINE"),
        ("senado", "plenario_discursos", "hard_cut", "structural_header", "DOCUMENTO(S) A QUE SE REFERE"),
    }

    parenthetical_rows = _read_csv(output_root / "parenteticos_resumo.csv")
    assert parenthetical_rows[0]["action"] == "keep"
    assert parenthetical_rows[0]["parenthetical_normalized"] == "PAUSA"

    examples = [json.loads(line) for line in (output_root / "separadores_exemplos.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all("context_before" in row and "context_after" in row for row in examples)

    ai_rows = [json.loads(line) for line in (output_root / "amostra_ia_textos.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["texto_id"] for row in ai_rows} == {"camara-1", "camara-2", "senado-1"}
    assert all(row["prompt_version"] == "separadores-v1" for row in ai_rows)
    assert any(row["texto_truncado"] for row in ai_rows)
    schema = json.loads((output_root / "amostra_ia_schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["separadores"]["items"]["properties"]["acao_sugerida"]["enum"] == [
        "hard_cut",
        "review",
        "keep",
    ]


def test_resolve_inventory_paths_uses_profile_defaults() -> None:
    parquet_root, output_root, run_id = resolve_inventory_paths(profile="samples-local", run_id="sample-run")

    assert parquet_root == Path("data/samples/textos_parlamentares/v1/parquet")
    assert output_root == Path("data/samples/textos_parlamentares/v1/audits/separadores/sample-run")
    assert run_id == "sample-run"

    colab_parquet_root, colab_output_root, colab_run_id = resolve_inventory_paths(
        profile="colab",
        run_id="colab-run",
        env={"FALANDO_NELA_DATA_ROOT": "/content/drive/MyDrive/falando_nela/data"},
    )

    assert colab_parquet_root == Path("/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet")
    assert colab_output_root == Path("/content/drive/MyDrive/falando_nela/data/processed/audits/separadores/colab-run")
    assert colab_run_id == "colab-run"


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
