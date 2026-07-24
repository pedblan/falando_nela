from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pyarrow.parquet as pq

from coleta.common.config import PROD_DATA_ROOT_ENV, utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audita a juncao entre textos parlamentares e parlamentares/v1.")
    parser.add_argument("--profile", choices=["samples-local", "colab"], default=None)
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--textos-parquet-root", default=None)
    parser.add_argument("--parlamentares-parquet-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    paths = resolve_audit_paths(args, env=os.environ)
    manifest = audit_join(
        textos_parquet_root=paths["textos_parquet_root"],
        parlamentares_parquet_root=paths["parlamentares_parquet_root"],
        output_root=paths["output_root"],
        run_id=paths["run_id"],
        overwrite=args.overwrite,
    )
    print(manifest["manifest_path"])


def resolve_audit_paths(
    args: argparse.Namespace,
    *,
    env: os._Environ[str] | dict[str, str],
) -> dict[str, Path | str]:
    run_id = args.run_id or f"parlamentares-join-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if args.profile == "samples-local":
        textos_root = Path(args.textos_parquet_root or "data/samples/textos_parlamentares/v1/parquet")
        parlamentares_root = Path(args.parlamentares_parquet_root or "data/samples/parlamentares/v1/parquet")
        output_root = Path(args.output_root or f"data/samples/textos_parlamentares/v1/audits/parlamentares/{run_id}")
        return {
            "textos_parquet_root": textos_root,
            "parlamentares_parquet_root": parlamentares_root,
            "output_root": output_root,
            "run_id": run_id,
        }

    if args.profile == "colab":
        data_root_value = args.data_root or env.get(PROD_DATA_ROOT_ENV)
        if not data_root_value:
            raise ValueError(f"--profile colab exige --data-root ou {PROD_DATA_ROOT_ENV}")
        data_root = Path(data_root_value).expanduser()
        textos_root = Path(args.textos_parquet_root).expanduser() if args.textos_parquet_root else data_root / "processed" / "textos_parlamentares" / "v1" / "parquet"
        parlamentares_root = Path(args.parlamentares_parquet_root).expanduser() if args.parlamentares_parquet_root else data_root / "processed" / "parlamentares" / "v1" / "parquet"
        output_root = Path(args.output_root).expanduser() if args.output_root else data_root / "processed" / "audits" / "parlamentares" / run_id
        return {
            "textos_parquet_root": textos_root,
            "parlamentares_parquet_root": parlamentares_root,
            "output_root": output_root,
            "run_id": run_id,
        }

    if not args.textos_parquet_root or not args.parlamentares_parquet_root:
        raise ValueError("Sem --profile, informe --textos-parquet-root e --parlamentares-parquet-root.")
    output_root = Path(args.output_root or f"processed/audits/parlamentares/{run_id}")
    return {
        "textos_parquet_root": Path(args.textos_parquet_root).expanduser(),
        "parlamentares_parquet_root": Path(args.parlamentares_parquet_root).expanduser(),
        "output_root": output_root,
        "run_id": run_id,
    }


def audit_join(
    *,
    textos_parquet_root: Path,
    parlamentares_parquet_root: Path,
    output_root: Path,
    run_id: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    textos_parquet_root = textos_parquet_root.expanduser()
    parlamentares_parquet_root = parlamentares_parquet_root.expanduser()
    output_root = output_root.expanduser()
    manifest_path = output_root / "manifest.json"
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Saida de auditoria ja existe: {output_root}; use --overwrite.")
    if overwrite and output_root.exists():
        for path in output_root.iterdir():
            if path.is_file():
                path.unlink()
    output_root.mkdir(parents=True, exist_ok=True)

    periodos_path = parlamentares_parquet_root / "parlamentares_periodos.parquet"
    if not periodos_path.exists():
        raise FileNotFoundError(f"Parquet de periodos nao encontrado: {periodos_path}")
    periodos = load_periodos(periodos_path)

    coverage = Counter()
    gender_distribution = Counter()
    unmatched: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    input_files = []
    total_rows = 0

    for parquet_path in sorted(textos_parquet_root.glob("*.parquet")):
        input_files.append(str(parquet_path))
        for texto in iter_parquet_rows(parquet_path):
            total_rows += 1
            source = _string(texto.get("source"))
            dataset = _string(texto.get("dataset"))
            documento_tipo = _string(texto.get("documento_tipo")) or "sem_documento_tipo"
            ano = _string(texto.get("ano")) or _year_from_date(_string(texto.get("data"))) or "sem_ano"
            bucket = (source or "sem_source", dataset or "sem_dataset", documento_tipo, ano)
            parlamentar_id = _string(texto.get("parlamentar_id"))
            data = _string(texto.get("data"))
            if not parlamentar_id or not source or not data:
                coverage[bucket + ("sem_autoria_individual",)] += 1
                continue
            matches = match_periodos(periodos, source=source, parlamentar_id=parlamentar_id, data=data)
            if not matches:
                coverage[bucket + ("unmatched",)] += 1
                unmatched.append(compact_text_row(texto, motivo="sem_match"))
                continue
            if len(matches) > 1:
                coverage[bucket + ("ambiguous",)] += 1
                ambiguous.append(
                    {
                        **compact_text_row(texto, motivo="match_multiplo"),
                        "matches": [
                            {
                                "parlamentar_key": match.get("parlamentar_key"),
                                "vigencia_inicio": match.get("vigencia_inicio"),
                                "vigencia_fim": match.get("vigencia_fim"),
                                "partido_sigla": match.get("partido_sigla"),
                                "genero": match.get("genero"),
                                "match_priority": match.get("match_priority"),
                            }
                            for match in matches
                        ],
                    }
                )
                continue
            coverage[bucket + ("matched",)] += 1
            match = matches[0]
            gender_distribution[(source, dataset or "sem_dataset", ano, match.get("genero") or "nao_informado")] += 1

    write_coverage_csv(output_root / "join_coverage.csv", coverage)
    write_counter_csv(
        output_root / "gender_distribution.csv",
        gender_distribution,
        headers=["source", "dataset", "ano", "genero", "textos"],
    )
    write_jsonl(output_root / "unmatched_textos.jsonl", unmatched)
    write_jsonl(output_root / "ambiguous_matches.jsonl", ambiguous)

    manifest = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "textos_parquet_root": str(textos_parquet_root),
        "parlamentares_parquet_root": str(parlamentares_parquet_root),
        "periodos_path": str(periodos_path),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "input_files": input_files,
        "input_file_count": len(input_files),
        "textos_lidos": total_rows,
        "periodos_lidos": sum(len(rows) for source_map in periodos.values() for rows in source_map.values()),
        "unmatched_textos": len(unmatched),
        "ambiguous_matches": len(ambiguous),
        "coverage_rows": len(coverage),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_periodos(path: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    periodos: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in iter_parquet_rows(path):
        source = _string(row.get("source"))
        parlamentar_id = _string(row.get("parlamentar_id"))
        if not source or not parlamentar_id:
            continue
        periodos.setdefault(source, {}).setdefault(parlamentar_id, []).append(row)
    for source_map in periodos.values():
        for rows in source_map.values():
            rows.sort(key=lambda row: int(row.get("match_priority") or 99))
    return periodos


def match_periodos(
    periodos: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    source: str,
    parlamentar_id: str,
    data: str,
) -> list[dict[str, Any]]:
    candidates = periodos.get(source, {}).get(parlamentar_id, [])
    matches = []
    for period in candidates:
        start = _string(period.get("vigencia_inicio")) or "0001-01-01"
        end_exclusive = _string(period.get("vigencia_fim_exclusivo")) or _next_day(_string(period.get("vigencia_fim"))) or "9999-12-31"
        if start <= data < end_exclusive:
            matches.append(period)
    if len(matches) <= 1:
        return matches
    best_priority = min(int(match.get("match_priority") or 99) for match in matches)
    best = [match for match in matches if int(match.get("match_priority") or 99) == best_priority]
    return best


def iter_parquet_rows(path: Path) -> Iterator[dict[str, Any]]:
    table = pq.read_table(path)
    for row in table.to_pylist():
        if isinstance(row, dict):
            yield row


def compact_text_row(row: dict[str, Any], *, motivo: str) -> dict[str, Any]:
    return {
        "motivo": motivo,
        "texto_id": row.get("texto_id"),
        "source": row.get("source"),
        "dataset": row.get("dataset"),
        "documento_tipo": row.get("documento_tipo"),
        "data": row.get("data"),
        "ano": row.get("ano"),
        "parlamentar_id": row.get("parlamentar_id"),
        "parlamentar_nome": row.get("parlamentar_nome"),
        "raw_path": row.get("raw_path"),
    }


def write_coverage_csv(path: Path, coverage: Counter[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "dataset", "documento_tipo", "ano", "status", "textos"])
        for key, count in sorted(coverage.items()):
            writer.writerow([*key, count])


def write_counter_csv(path: Path, counter: Counter[tuple[str, ...]], *, headers: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for key, count in sorted(counter.items()):
            writer.writerow([*key, count])


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _next_day(value: str | None) -> str | None:
    if not value:
        return None
    try:
        from datetime import date, timedelta

        return (date.fromisoformat(value) + timedelta(days=1)).isoformat()
    except ValueError:
        return None


def _year_from_date(value: str | None) -> str | None:
    return value[:4] if value and len(value) >= 4 else None


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


if __name__ == "__main__":
    main()
