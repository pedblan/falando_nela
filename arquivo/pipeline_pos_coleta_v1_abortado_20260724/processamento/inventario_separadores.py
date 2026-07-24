from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import pyarrow.parquet as pq

from coleta.common.config import PROD_DATA_ROOT_ENV, utc_now_iso

DEFAULT_COLAB_DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
DEFAULT_COLAB_PARQUET_ROOT = DEFAULT_COLAB_DATA_ROOT / "processed" / "textos_parlamentares" / "v1" / "parquet"
DEFAULT_SAMPLES_PARQUET_ROOT = Path("data/samples/textos_parlamentares/v1/parquet")
DEFAULT_CONTEXT_CHARS = 280
DEFAULT_MAX_EXAMPLES_PER_SEPARATOR = 25
DEFAULT_BATCH_SIZE = 2_000
DEFAULT_AI_SAMPLE_RATE = 0.001
DEFAULT_AI_SAMPLE_MIN_PER_STRATUM = 1
DEFAULT_AI_SAMPLE_MAX_CHARS = 24_000
AI_PROMPT_VERSION = "separadores-v1"

READ_COLUMNS = [
    "texto_id",
    "source",
    "dataset",
    "ano",
    "mes",
    "data",
    "documento_tipo",
    "unidade_analitica",
    "texto",
]

SEPARATOR_SUMMARY_FIELDS = [
    "source",
    "dataset",
    "ano",
    "action",
    "kind",
    "separator_normalized",
    "separator_example",
    "occurrences",
    "textos",
]

PARENTHETICAL_SUMMARY_FIELDS = [
    "source",
    "dataset",
    "ano",
    "action",
    "parenthetical_normalized",
    "parenthetical_example",
    "occurrences",
    "textos",
]

STRUCTURAL_HEADER_PATTERNS = [
    ("ARTIGO A QUE SE REFERE", re.compile(r"\bARTIGO\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("DOCUMENTO(S) A QUE SE REFERE", re.compile(r"\bDOCUMENTOS?\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("MATERIA A QUE SE REFERE", re.compile(r"\bMATERIA\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("NOTA A QUE SE REFERE", re.compile(r"\bNOTA\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("CARTA A QUE SE REFERE", re.compile(r"\bCARTA\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("TEXTO A QUE SE REFERE", re.compile(r"\bTEXTO\s+A\s+QUE\s+SE\s+REFERE\b")),
    ("SEGUE NA INTEGRA", re.compile(r"\bSEGUE[MS]?\s+NA\s+INTEGRA\b")),
    ("PRONUNCIAMENTO ENCAMINHADO", re.compile(r"\bPRONUNCIAMENTOS?\s+ENCAMINHAD[OA]S?\b")),
    ("DISCURSO NA INTEGRA ENCAMINHADO", re.compile(r"\bDISCURSO\s+NA\s+INTEGRA\s+ENCAMINHAD[OA]\b")),
]

STAR_LINE_RE = re.compile(r"^\*{5,}$")
PARENTHETICAL_LINE_RE = re.compile(r"^\(([^()\n]{3,180})\)[.;:]?$")
SPEAKER_PREFIX_RE = re.compile(r"^(O|A)\s+SR[AS]?\b|^SR[AS]?\b|^PRESIDENTE\b|^RELATOR[AA]?\b")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventaria separadores e marcas editoriais nos Parquets processed v1."
    )
    parser.add_argument(
        "--profile",
        choices=["samples-local", "colab"],
        default="samples-local",
        help="Escolhe caminhos padrao para samples locais ou Google Drive no Colab.",
    )
    parser.add_argument("--data-root", default=None, help="Raiz de dados para o perfil colab.")
    parser.add_argument("--parquet-root", default=None, help="Diretorio explicito de Parquets.")
    parser.add_argument("--output-root", default=None, help="Diretorio final dos relatorios.")
    parser.add_argument(
        "--dataset",
        action="append",
        default=None,
        help="Filtra por base no formato source/dataset. Pode ser repetido.",
    )
    parser.add_argument("--run-id", default=None, help="Identificador da auditoria.")
    parser.add_argument("--context-chars", type=int, default=DEFAULT_CONTEXT_CHARS)
    parser.add_argument("--max-examples-per-separator", type=int, default=DEFAULT_MAX_EXAMPLES_PER_SEPARATOR)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--ai-sample-rate", type=float, default=DEFAULT_AI_SAMPLE_RATE)
    parser.add_argument("--ai-sample-min-per-stratum", type=int, default=DEFAULT_AI_SAMPLE_MIN_PER_STRATUM)
    parser.add_argument("--ai-sample-max-chars", type=int, default=DEFAULT_AI_SAMPLE_MAX_CHARS)
    parser.add_argument("--no-ai-sample", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    parquet_root, output_root, run_id = resolve_inventory_paths(
        profile=args.profile,
        data_root=args.data_root,
        parquet_root=args.parquet_root,
        output_root=args.output_root,
        run_id=args.run_id,
        env=os.environ,
    )
    manifest = write_separator_inventory(
        parquet_root=parquet_root,
        output_root=output_root,
        run_id=run_id,
        datasets=args.dataset,
        context_chars=args.context_chars,
        max_examples_per_separator=args.max_examples_per_separator,
        ai_sample=not args.no_ai_sample,
        ai_sample_rate=args.ai_sample_rate,
        ai_sample_min_per_stratum=args.ai_sample_min_per_stratum,
        ai_sample_max_chars=args.ai_sample_max_chars,
        batch_size=args.batch_size,
        overwrite=args.overwrite,
    )
    print(manifest["manifest_path"])


def resolve_inventory_paths(
    *,
    profile: str = "samples-local",
    data_root: str | os.PathLike[str] | None = None,
    parquet_root: str | os.PathLike[str] | None = None,
    output_root: str | os.PathLike[str] | None = None,
    run_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Path, Path, str]:
    run_id = run_id or f"separadores-textos-v1-{_run_timestamp()}"
    if parquet_root:
        resolved_parquet_root = Path(parquet_root).expanduser()
    elif profile == "samples-local":
        resolved_parquet_root = DEFAULT_SAMPLES_PARQUET_ROOT
    elif profile == "colab":
        env = env or os.environ
        root_value = data_root or env.get(PROD_DATA_ROOT_ENV) or DEFAULT_COLAB_DATA_ROOT
        resolved_parquet_root = Path(root_value).expanduser() / "processed" / "textos_parlamentares" / "v1" / "parquet"
    else:
        raise ValueError(f"Perfil de inventario desconhecido: {profile}")

    if output_root:
        resolved_output_root = Path(output_root).expanduser()
    elif profile == "colab":
        env = env or os.environ
        root_value = data_root or env.get(PROD_DATA_ROOT_ENV) or DEFAULT_COLAB_DATA_ROOT
        resolved_output_root = Path(root_value).expanduser() / "processed" / "audits" / "separadores" / run_id
    else:
        resolved_output_root = resolved_parquet_root.parent / "audits" / "separadores" / run_id

    return resolved_parquet_root, resolved_output_root, run_id


def write_separator_inventory(
    *,
    parquet_root: Path,
    output_root: Path,
    run_id: str,
    datasets: Iterable[str] | None = None,
    context_chars: int = DEFAULT_CONTEXT_CHARS,
    max_examples_per_separator: int = DEFAULT_MAX_EXAMPLES_PER_SEPARATOR,
    ai_sample: bool = True,
    ai_sample_rate: float = DEFAULT_AI_SAMPLE_RATE,
    ai_sample_min_per_stratum: int = DEFAULT_AI_SAMPLE_MIN_PER_STRATUM,
    ai_sample_max_chars: int = DEFAULT_AI_SAMPLE_MAX_CHARS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    overwrite: bool = False,
) -> dict[str, Any]:
    parquet_root = parquet_root.expanduser()
    output_root = output_root.expanduser()
    if context_chars < 0:
        raise ValueError("context_chars deve ser maior ou igual a zero")
    if max_examples_per_separator < 0:
        raise ValueError("max_examples_per_separator deve ser maior ou igual a zero")
    if ai_sample_rate < 0:
        raise ValueError("ai_sample_rate deve ser maior ou igual a zero")
    if ai_sample_min_per_stratum < 0:
        raise ValueError("ai_sample_min_per_stratum deve ser maior ou igual a zero")
    if ai_sample_max_chars <= 0:
        raise ValueError("ai_sample_max_chars deve ser positivo")
    if batch_size <= 0:
        raise ValueError("batch_size deve ser positivo")
    if not parquet_root.exists():
        raise FileNotFoundError(f"Diretorio de Parquets nao encontrado: {parquet_root}")

    output_paths = {
        "separadores_resumo": output_root / "separadores_resumo.csv",
        "separadores_exemplos": output_root / "separadores_exemplos.jsonl",
        "parenteticos_resumo": output_root / "parenteticos_resumo.csv",
        "manifest": output_root / "manifest.json",
    }
    if ai_sample:
        output_paths.update(
            {
                "amostra_ia_textos": output_root / "amostra_ia_textos.jsonl",
                "amostra_ia_prompt": output_root / "amostra_ia_prompt.md",
                "amostra_ia_schema": output_root / "amostra_ia_schema.json",
            }
        )
    _prepare_output(output_paths.values(), overwrite=overwrite)

    dataset_filter = set(datasets or [])
    parquet_paths = list(iter_parquet_paths(parquet_root))
    separator_counts: Counter[tuple[str, str, str, str, str, str]] = Counter()
    separator_text_ids: defaultdict[tuple[str, str, str, str, str, str], set[str]] = defaultdict(set)
    separator_examples: dict[tuple[str, str, str, str, str, str], str] = {}
    parenthetical_counts: Counter[tuple[str, str, str, str]] = Counter()
    parenthetical_text_ids: defaultdict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    parenthetical_examples: dict[tuple[str, str, str, str], str] = {}
    examples: list[dict[str, Any]] = []
    example_counts: Counter[tuple[str, str, str, str]] = Counter()
    input_files: list[str] = []
    input_records = 0
    records_with_text = 0
    stratum_counts: Counter[tuple[str, str, str]] = Counter()

    for parquet_path in parquet_paths:
        fallback_source, fallback_dataset = _source_dataset_from_filename(parquet_path)
        if dataset_filter and fallback_source and fallback_dataset and f"{fallback_source}/{fallback_dataset}" not in dataset_filter:
            continue
        input_files.append(_relative_path(parquet_path, parquet_root))
        for row in iter_parquet_records(parquet_path, batch_size=batch_size):
            input_records += 1
            row = _coerce_row(row, fallback_source=fallback_source, fallback_dataset=fallback_dataset)
            source = row["source"]
            dataset = row["dataset"]
            if dataset_filter and f"{source}/{dataset}" not in dataset_filter:
                continue
            text = row["texto"]
            if not text:
                continue
            records_with_text += 1
            stratum_counts[(source, dataset, row["ano"])] += 1

            for parenthetical in detect_parenthetical_lines(row):
                key = (
                    parenthetical["source"],
                    parenthetical["dataset"],
                    parenthetical["ano"],
                    parenthetical["parenthetical_normalized"],
                )
                parenthetical_counts[key] += 1
                parenthetical_text_ids[key].add(parenthetical["texto_id"])
                parenthetical_examples.setdefault(key, parenthetical["parenthetical_text"])

            for candidate in detect_separator_candidates(row, context_chars=context_chars):
                key = (
                    candidate["source"],
                    candidate["dataset"],
                    candidate["ano"],
                    candidate["action"],
                    candidate["kind"],
                    candidate["separator_normalized"],
                )
                separator_counts[key] += 1
                separator_text_ids[key].add(candidate["texto_id"])
                separator_examples.setdefault(key, candidate["separator_text"])
                example_key = (
                    candidate["source"],
                    candidate["dataset"],
                    candidate["action"],
                    candidate["separator_normalized"],
                )
                if example_counts[example_key] < max_examples_per_separator:
                    examples.append(candidate)
                    example_counts[example_key] += 1

    output_root.mkdir(parents=True, exist_ok=True)
    _write_separator_summary(
        output_paths["separadores_resumo"],
        separator_counts,
        separator_text_ids,
        separator_examples,
    )
    _write_examples(output_paths["separadores_exemplos"], examples)
    _write_parenthetical_summary(
        output_paths["parenteticos_resumo"],
        parenthetical_counts,
        parenthetical_text_ids,
        parenthetical_examples,
    )
    ai_sample_count = 0
    if ai_sample:
        ai_sample_count = _write_ai_review_artifacts(
            parquet_paths=parquet_paths,
            sample_path=output_paths["amostra_ia_textos"],
            prompt_path=output_paths["amostra_ia_prompt"],
            schema_path=output_paths["amostra_ia_schema"],
            stratum_counts=stratum_counts,
            dataset_filter=dataset_filter,
            sample_rate=ai_sample_rate,
            min_per_stratum=ai_sample_min_per_stratum,
            max_chars=ai_sample_max_chars,
            batch_size=batch_size,
        )

    manifest = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "parquet_root": str(parquet_root),
        "output_root": str(output_root),
        "manifest_path": str(output_paths["manifest"]),
        "input_files": input_files,
        "input_file_count": len(input_files),
        "input_records": input_records,
        "records_with_text": records_with_text,
        "separator_occurrences": sum(separator_counts.values()),
        "parenthetical_occurrences": sum(parenthetical_counts.values()),
        "example_count": len(examples),
        "ai_sample": ai_sample,
        "ai_prompt_version": AI_PROMPT_VERSION,
        "ai_sample_rate": ai_sample_rate,
        "ai_sample_min_per_stratum": ai_sample_min_per_stratum,
        "ai_sample_max_chars": ai_sample_max_chars,
        "ai_sample_records": ai_sample_count,
        "ai_sample_strata": len(stratum_counts),
        "dataset_filter": sorted(dataset_filter),
        "context_chars": context_chars,
        "max_examples_per_separator": max_examples_per_separator,
        "batch_size": batch_size,
        "output_files": {name: str(path) for name, path in output_paths.items()},
    }
    output_paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def iter_parquet_paths(parquet_root: Path) -> Iterator[Path]:
    yield from sorted(path for path in parquet_root.glob("*.parquet") if path.is_file())


def iter_parquet_records(path: Path, *, batch_size: int) -> Iterator[dict[str, Any]]:
    parquet_file = pq.ParquetFile(path)
    available_columns = set(parquet_file.schema_arrow.names)
    columns = [column for column in READ_COLUMNS if column in available_columns]
    if "texto" not in available_columns:
        return
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns):
        for row in batch.to_pylist():
            yield row


def detect_separator_candidates(row: Mapping[str, Any], *, context_chars: int = DEFAULT_CONTEXT_CHARS) -> list[dict[str, Any]]:
    text = _string(row.get("texto"))
    if not text:
        return []
    candidates: list[dict[str, Any]] = []
    for line_number, start, end, line in _iter_lines(text):
        star_action = _classify_star_line(line, text[end : end + max(context_chars, 600)])
        if star_action:
            candidates.append(
                _candidate(row, text, line, line_number, start, end, kind="asterisk_line", action=star_action, context_chars=context_chars)
            )
            continue

        header_label = _structural_header_label(line)
        if header_label:
            candidates.append(
                _candidate(
                    row,
                    text,
                    line,
                    line_number,
                    start,
                    end,
                    kind="structural_header",
                    action="hard_cut",
                    context_chars=context_chars,
                    separator_normalized=header_label,
                )
            )
            continue

        if _is_review_heading(line):
            candidates.append(
                _candidate(row, text, line, line_number, start, end, kind="uppercase_heading", action="review", context_chars=context_chars)
            )
    return candidates


def detect_parenthetical_lines(row: Mapping[str, Any]) -> list[dict[str, str]]:
    text = _string(row.get("texto"))
    if not text:
        return []
    parentheticals: list[dict[str, str]] = []
    for _, _, _, line in _iter_lines(text):
        match = PARENTHETICAL_LINE_RE.match(line)
        if not match:
            continue
        content = _clean_line(match.group(1))
        parentheticals.append(
            {
                "source": _string(row.get("source")) or "",
                "dataset": _string(row.get("dataset")) or "",
                "ano": _string(row.get("ano")) or "",
                "texto_id": _string(row.get("texto_id")) or "",
                "action": "keep",
                "parenthetical_text": line,
                "parenthetical_normalized": _normalize_for_match(content),
            }
        )
    return parentheticals


def _candidate(
    row: Mapping[str, Any],
    text: str,
    line: str,
    line_number: int,
    start: int,
    end: int,
    *,
    kind: str,
    action: str,
    context_chars: int,
    separator_normalized: str | None = None,
) -> dict[str, Any]:
    return {
        "source": _string(row.get("source")) or "",
        "dataset": _string(row.get("dataset")) or "",
        "ano": _string(row.get("ano")) or "",
        "mes": _string(row.get("mes")) or "",
        "data": _string(row.get("data")) or "",
        "documento_tipo": _string(row.get("documento_tipo")) or "",
        "unidade_analitica": _string(row.get("unidade_analitica")) or "",
        "texto_id": _string(row.get("texto_id")) or "",
        "action": action,
        "kind": kind,
        "separator_text": line,
        "separator_normalized": separator_normalized or _separator_label(line, kind=kind),
        "line_number": line_number,
        "char_start": start,
        "char_end": end,
        "context_before": text[max(0, start - context_chars) : start],
        "context_after": text[end : end + context_chars],
        "trailing_chars": len(text[end:]),
    }


def _classify_star_line(line: str, following_context: str) -> str | None:
    compact = line.replace(" ", "")
    if not STAR_LINE_RE.match(compact):
        return None
    if _structural_header_label(following_context):
        return "hard_cut"
    return "review"


def _structural_header_label(value: str) -> str | None:
    normalized = _normalize_for_match(value)
    for label, pattern in STRUCTURAL_HEADER_PATTERNS:
        if pattern.search(normalized):
            return label
    return None


def _separator_label(line: str, *, kind: str) -> str:
    if kind == "asterisk_line":
        return "ASTERISK_LINE"
    return _normalize_for_match(line)


def _is_review_heading(line: str) -> bool:
    if len(line) < 9 or len(line) > 180:
        return False
    if PARENTHETICAL_LINE_RE.match(line):
        return False
    normalized = _normalize_for_match(line)
    if not normalized or SPEAKER_PREFIX_RE.match(normalized):
        return False
    letters = [char for char in line if char.isalpha()]
    if len(letters) < 4:
        return False
    uppercase_ratio = sum(char.isupper() for char in letters) / len(letters)
    return uppercase_ratio >= 0.85


def _iter_lines(text: str) -> Iterator[tuple[int, int, int, str]]:
    line_number = 0
    for match in re.finditer(r"[^\r\n]+", text):
        line = _clean_line(match.group(0))
        if not line:
            continue
        line_number += 1
        yield line_number, match.start(), match.end(), line


def _coerce_row(row: Mapping[str, Any], *, fallback_source: str | None, fallback_dataset: str | None) -> dict[str, str]:
    return {
        "texto_id": _string(row.get("texto_id")) or "",
        "source": _string(row.get("source")) or fallback_source or "",
        "dataset": _string(row.get("dataset")) or fallback_dataset or "",
        "ano": _string(row.get("ano")) or "",
        "mes": _string(row.get("mes")) or "",
        "data": _string(row.get("data")) or "",
        "documento_tipo": _string(row.get("documento_tipo")) or "",
        "unidade_analitica": _string(row.get("unidade_analitica")) or "",
        "texto": _string(row.get("texto")) or "",
    }


def _write_separator_summary(
    path: Path,
    counts: Counter[tuple[str, str, str, str, str, str]],
    text_ids: Mapping[tuple[str, str, str, str, str, str], set[str]],
    examples: Mapping[tuple[str, str, str, str, str, str], str],
) -> None:
    rows = []
    for key, count in counts.items():
        source, dataset, ano, action, kind, separator_normalized = key
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "ano": ano,
                "action": action,
                "kind": kind,
                "separator_normalized": separator_normalized,
                "separator_example": examples.get(key, ""),
                "occurrences": count,
                "textos": len(text_ids.get(key, set())),
            }
        )
    rows.sort(key=lambda row: (row["source"], row["dataset"], row["ano"], row["action"], row["kind"], -int(row["occurrences"]), row["separator_normalized"]))
    _write_csv(path, SEPARATOR_SUMMARY_FIELDS, rows)


def _write_parenthetical_summary(
    path: Path,
    counts: Counter[tuple[str, str, str, str]],
    text_ids: Mapping[tuple[str, str, str, str], set[str]],
    examples: Mapping[tuple[str, str, str, str], str],
) -> None:
    rows = []
    for key, count in counts.items():
        source, dataset, ano, parenthetical_normalized = key
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "ano": ano,
                "action": "keep",
                "parenthetical_normalized": parenthetical_normalized,
                "parenthetical_example": examples.get(key, ""),
                "occurrences": count,
                "textos": len(text_ids.get(key, set())),
            }
        )
    rows.sort(key=lambda row: (row["source"], row["dataset"], row["ano"], -int(row["occurrences"]), row["parenthetical_normalized"]))
    _write_csv(path, PARENTHETICAL_SUMMARY_FIELDS, rows)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_examples(path: Path, examples: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, sort_keys=True) + "\n")


def _write_ai_review_artifacts(
    *,
    parquet_paths: list[Path],
    sample_path: Path,
    prompt_path: Path,
    schema_path: Path,
    stratum_counts: Counter[tuple[str, str, str]],
    dataset_filter: set[str],
    sample_rate: float,
    min_per_stratum: int,
    max_chars: int,
    batch_size: int,
) -> int:
    targets = {
        stratum: max(min_per_stratum, math.ceil(count * sample_rate))
        for stratum, count in stratum_counts.items()
        if count > 0 and (sample_rate > 0 or min_per_stratum > 0)
    }
    heaps: defaultdict[tuple[str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for parquet_path in parquet_paths:
        fallback_source, fallback_dataset = _source_dataset_from_filename(parquet_path)
        if dataset_filter and fallback_source and fallback_dataset and f"{fallback_source}/{fallback_dataset}" not in dataset_filter:
            continue
        for row in iter_parquet_records(parquet_path, batch_size=batch_size):
            row = _coerce_row(row, fallback_source=fallback_source, fallback_dataset=fallback_dataset)
            if not row["texto"]:
                continue
            source = row["source"]
            dataset = row["dataset"]
            if dataset_filter and f"{source}/{dataset}" not in dataset_filter:
                continue
            stratum = (source, dataset, row["ano"])
            target = targets.get(stratum, 0)
            if target <= 0:
                continue
            score = _sample_score(row)
            heap = heaps[stratum]
            item = (-score, row)
            if len(heap) < target:
                heapq.heappush(heap, item)
            elif score < -heap[0][0]:
                heapq.heapreplace(heap, item)

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with sample_path.open("w", encoding="utf-8") as handle:
        for stratum in sorted(heaps):
            selected = sorted(heaps[stratum], key=lambda item: (-item[0], item[1]["texto_id"]))
            for _, row in selected:
                record = _ai_sample_record(
                    row,
                    stratum_size=stratum_counts[stratum],
                    sample_rate=sample_rate,
                    max_chars=max_chars,
                )
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                count += 1

    prompt_path.write_text(_ai_prompt_text(), encoding="utf-8")
    schema_path.write_text(
        json.dumps(_ai_response_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return count


def _sample_score(row: Mapping[str, Any]) -> int:
    key = "|".join(
        [
            _string(row.get("source")) or "",
            _string(row.get("dataset")) or "",
            _string(row.get("ano")) or "",
            _string(row.get("texto_id")) or "",
        ]
    )
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)


def _ai_sample_record(row: Mapping[str, str], *, stratum_size: int, sample_rate: float, max_chars: int) -> dict[str, Any]:
    text = row["texto"]
    excerpt, truncated = _excerpt_text(text, max_chars=max_chars)
    heuristic_candidates = detect_separator_candidates(row, context_chars=120)
    return {
        "custom_id": f"{row['source']}__{row['dataset']}__{row['ano']}__{hashlib.sha1(row['texto_id'].encode('utf-8')).hexdigest()[:16]}",
        "prompt_version": AI_PROMPT_VERSION,
        "source": row["source"],
        "dataset": row["dataset"],
        "ano": row["ano"],
        "mes": row["mes"],
        "data": row["data"],
        "documento_tipo": row["documento_tipo"],
        "unidade_analitica": row["unidade_analitica"],
        "texto_id": row["texto_id"],
        "stratum_size": stratum_size,
        "sample_rate": sample_rate,
        "texto_tamanho_original": len(text),
        "texto_truncado": truncated,
        "texto_amostra": excerpt,
        "separadores_heuristicos": [
            {
                "action": item["action"],
                "kind": item["kind"],
                "separator_text": item["separator_text"],
                "separator_normalized": item["separator_normalized"],
                "line_number": item["line_number"],
            }
            for item in heuristic_candidates[:20]
        ],
    }


def _excerpt_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    head_chars = max(1, max_chars // 3)
    tail_chars = max_chars - head_chars
    omitted = len(text) - head_chars - tail_chars
    excerpt = (
        text[:head_chars]
        + f"\n\n[... {omitted} caracteres omitidos no meio do texto ...]\n\n"
        + text[-tail_chars:]
    )
    return excerpt, True


def _ai_prompt_text() -> str:
    return """# Tarefa de rotulagem: separadores em textos parlamentares

Analise cada registro de `amostra_ia_textos.jsonl` e responda somente com JSON
valido conforme `amostra_ia_schema.json`.

Objetivo:
- identificar separadores que marcam anexos, documentos agregados, artigos
  citados, materias, cartas, notas ou pronunciamentos encaminhados;
- distinguir esses separadores de marcas taquigraficas ou contexto parlamentar
  que deve permanecer no texto analitico;
- sugerir se cada separador deve ser `hard_cut`, `review` ou `keep`.

Regras:
- Use `hard_cut` apenas quando o trecho depois do separador parece ser anexo,
  documento agregado ou texto que nao e a fala/nota principal.
- Use `review` quando houver indicio de separador, mas o contexto fornecido nao
  for suficiente para corte automatico.
- Use `keep` para marcas taquigraficas entre parenteses, como pausas,
  campainha, microfone, palmas, votacao, intervencoes e indicacao de quem tem a
  palavra.
- Se o texto estiver truncado e isso impedir uma conclusao, marque
  `precisa_texto_completo` como `true`.
"""


def _ai_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "texto_id",
            "source",
            "dataset",
            "ano",
            "tem_bloco_agregado",
            "precisa_texto_completo",
            "separadores",
            "parenteticos",
            "observacoes",
        ],
        "properties": {
            "texto_id": {"type": "string"},
            "source": {"type": "string"},
            "dataset": {"type": "string"},
            "ano": {"type": "string"},
            "tem_bloco_agregado": {"type": "boolean"},
            "precisa_texto_completo": {"type": "boolean"},
            "separadores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["texto_exato", "acao_sugerida", "confianca", "motivo"],
                    "properties": {
                        "texto_exato": {"type": "string"},
                        "acao_sugerida": {"type": "string", "enum": ["hard_cut", "review", "keep"]},
                        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                        "motivo": {"type": "string"},
                    },
                },
            },
            "parenteticos": {
                "type": "object",
                "additionalProperties": False,
                "required": ["acao_geral", "motivo"],
                "properties": {
                    "acao_geral": {"type": "string", "enum": ["keep", "review", "hard_cut"]},
                    "motivo": {"type": "string"},
                },
            },
            "observacoes": {"type": "string"},
        },
    }


def _prepare_output(paths: Iterable[Path], *, overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Relatorios de inventario ja existem; use --overwrite: {existing[0]}")
    if overwrite:
        for path in existing:
            path.unlink()


def _source_dataset_from_filename(path: Path) -> tuple[str | None, str | None]:
    stem = path.stem
    if "__" not in stem:
        return None, None
    source, dataset = stem.split("__", 1)
    return source or None, dataset or None


def _normalize_for_match(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.replace("\xa0", " "))
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    upper = ascii_text.upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", upper)).strip()


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").strip())


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    main()
