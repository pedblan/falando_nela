from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Mapping


DEFAULT_DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
OUTPUT_FIELDS = (
    "relative_path",
    "absolute_path",
    "decision",
    "reason",
    "layer",
    "item_class",
    "size_bytes",
)

ANALYSIS_PARTS = {"analise", "analises", "analysis"}
OPERATIONAL_PARTS = {"operations", "logs", "manifests", "checkpoints", "locks"}


def classify_catalog_row(row: Mapping[str, str]) -> tuple[str, str]:
    relative_path = str(row.get("relative_path") or "").strip().strip("/")
    parts = {part.casefold() for part in Path(relative_path).parts}
    layer = str(row.get("layer") or "").strip().casefold()

    if "raw" in parts or layer == "raw":
        return "preserve", "dado bruto protegido"
    if "reference" in parts:
        return "preserve", "referencia preservada ate revisao especifica"
    if "processed" in parts or layer == "processed":
        return "archive_candidate", "derivado da normalizacao v1"
    if ANALYSIS_PARTS & parts or layer == "analysis":
        return "archive_candidate", "saida de analise encerrada"
    if layer == "snapshot" or "snapshot" in relative_path.casefold():
        return "archive_candidate", "snapshot ou artefato de snapshot encerrado"
    if OPERATIONAL_PARTS & parts or layer == "operational":
        return "manual_review", "pode conter proveniencia de coleta ou derivado"
    return "manual_review", "classificacao insuficiente para movimentacao segura"


def build_candidates(
    catalog_path: Path,
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
) -> list[dict[str, str]]:
    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "relative_path" not in reader.fieldnames:
            raise ValueError("catalogo sem a coluna obrigatoria relative_path")
        rows = []
        for row in reader:
            if str(row.get("item_type") or "").strip().casefold() != "file":
                continue
            relative_path = str(row.get("relative_path") or "").strip().strip("/")
            if not relative_path:
                continue
            decision, reason = classify_catalog_row(row)
            rows.append(
                {
                    "relative_path": relative_path,
                    "absolute_path": str(data_root / relative_path),
                    "decision": decision,
                    "reason": reason,
                    "layer": str(row.get("layer") or ""),
                    "item_class": str(row.get("item_class") or ""),
                    "size_bytes": str(row.get("size_bytes") or ""),
                }
            )
    return sorted(rows, key=lambda item: item["relative_path"])


def write_plan(
    rows: list[dict[str, str]],
    *,
    output_csv: Path,
    data_root: Path,
) -> Path:
    resolved_root = data_root.resolve()
    resolved_output = output_csv.resolve()
    if resolved_output == resolved_root or resolved_root in resolved_output.parents:
        raise ValueError("a saida deve ficar fora da raiz aprovada do Drive")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["decision"] for row in rows)
    summary_path = output_csv.with_suffix(".md")
    summary_path.write_text(
        "\n".join(
            [
                "# Plano de arquivamento do Drive",
                "",
                f"Raiz classificada: `{data_root}`",
                f"Arquivos classificados: **{len(rows)}**",
                "",
                "| Decisão | Arquivos |",
                "|---|---:|",
                f"| preserve | {counts['preserve']} |",
                f"| archive_candidate | {counts['archive_candidate']} |",
                f"| manual_review | {counts['manual_review']} |",
                "",
                "Nenhum arquivo do Drive foi movido.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classifica um catalogo do Drive sem alterar o Drive."
    )
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_candidates(args.catalog, data_root=args.data_root)
    summary_path = write_plan(
        rows,
        output_csv=args.output_csv,
        data_root=args.data_root,
    )
    print(f"Plano CSV: {args.output_csv}")
    print(f"Resumo: {summary_path}")
    print("Drive alterado: nao")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
