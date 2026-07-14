from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator, Sequence

from coleta.common.config import format_senado_date
from coleta.common.http import OpenDataClient
from coleta.parlamentares.collect import extract_senado_parlamentar_ids, legislaturas_for_period


BASE_URL = "https://legis.senado.leg.br/"
SENATOR_SPEECH_ENDPOINT = "dadosabertos/senador/{codigo}/discursos"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Arquiva probes do endpoint de discursos por senador para a recuperação 2015-2016."
    )
    parser.add_argument("--cycle-dir", required=True)
    parser.add_argument("--data-inicio", default="2015-01-01")
    parser.add_argument("--data-fim", default="2016-12-31")
    parser.add_argument("--limit-senators", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = audit_senator_endpoint(
        cycle_dir=Path(args.cycle_dir),
        start=date.fromisoformat(args.data_inicio),
        end=date.fromisoformat(args.data_fim),
        limit_senators=args.limit_senators,
        resume=args.resume,
        strict=args.strict,
    )
    print(result["summary_path"])


def audit_senator_endpoint(
    *,
    cycle_dir: Path,
    start: date,
    end: date,
    limit_senators: int | None = None,
    resume: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    if start > end:
        raise ValueError("data_inicio posterior a data_fim")
    if limit_senators is not None and limit_senators <= 0:
        raise ValueError("limit_senators deve ser positivo")
    cycle_dir.mkdir(parents=True, exist_ok=True)
    output_path = cycle_dir / "senator_endpoint_probes.jsonl"
    existing = list(iter_jsonl(output_path)) if resume and output_path.exists() else []
    by_key = {str(record.get("probe_key")): record for record in existing}
    errors: list[dict[str, Any]] = []

    legislatures = legislaturas_for_period(start, end)
    if not legislatures:
        raise ValueError("Nenhuma legislatura encontrada para o período")
    legislature_path = f"dadosabertos/senador/lista/legislatura/{min(legislatures)}/{max(legislatures)}.json"
    with OpenDataClient(BASE_URL, min_interval_seconds=0.11) as client:
        if "senators" not in by_key:
            result = client.get_json(legislature_path)
            by_key["senators"] = probe_record(
                probe_key="senators",
                request={"method": "GET", "path": legislature_path, "params": {}},
                response=result.response_metadata,
                payload=result.data,
            )
            _write_jsonl(by_key.values(), output_path)

        senator_ids = extract_senado_parlamentar_ids(by_key["senators"].get("payload"))
        senator_ids = sorted(set(senator_ids), key=int)
        if limit_senators is not None:
            senator_ids = senator_ids[:limit_senators]

        for year in range(start.year, end.year + 1):
            year_start = max(start, date(year, 1, 1))
            year_end = min(end, date(year, 12, 31))
            for house in ("SF", "CN"):
                for senator_id in senator_ids:
                    probe_key = f"{house}:{year}:{senator_id}"
                    if probe_key in by_key:
                        continue
                    endpoint = SENATOR_SPEECH_ENDPOINT.format(codigo=senator_id)
                    params = {
                        "casa": house,
                        "dataInicio": format_senado_date(year_start),
                        "dataFim": format_senado_date(year_end),
                        "v": 5,
                    }
                    try:
                        result = client.get_json(endpoint, params=params)
                        by_key[probe_key] = probe_record(
                            probe_key=probe_key,
                            request={"method": "GET", "path": endpoint, "params": params},
                            response=result.response_metadata,
                            payload=result.data,
                        )
                    except Exception as exc:
                        error = {
                            "probe_key": probe_key,
                            "request": {"method": "GET", "path": endpoint, "params": params},
                            "error": {"type": type(exc).__name__, "message": str(exc)},
                        }
                        errors.append(error)
                        by_key[probe_key] = probe_record(
                            probe_key=probe_key,
                            request=error["request"],
                            response={"status": "error"},
                            payload=None,
                            error=error["error"],
                        )
                    _write_jsonl(by_key.values(), output_path)

    ids_by_house_year: dict[str, list[str]] = {}
    for year in range(start.year, end.year + 1):
        for house in ("SF", "CN"):
            ids: set[str] = set()
            prefix = f"{house}:{year}:"
            for key, record in by_key.items():
                if key.startswith(prefix):
                    ids.update(extract_pronunciamento_codes(record.get("payload")))
            ids_by_house_year[f"{house}/{year}"] = sorted(ids, key=int)
    summary = {
        "schema_version": 1,
        "source": "senado",
        "strategy": "senator-discourses-diagnostic",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "senators": len(senator_ids),
        "limited": limit_senators is not None,
        "requests": len(by_key) - 1,
        "errors": len(errors),
        "ids_by_house_year": {key: len(value) for key, value in ids_by_house_year.items()},
        "output_path": str(output_path),
        "summary_path": str(cycle_dir / "senator_endpoint_summary.json"),
    }
    _write_json(summary, Path(summary["summary_path"]))
    if strict and errors:
        raise ValueError(f"Probes por senador com {len(errors)} erros; consulte {output_path}")
    return summary


def extract_pronunciamento_codes(payload: Any) -> list[str]:
    codes: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.casefold() in {"codigopronunciamento", "codigo_pronunciamento"} and child is not None:
                    codes.add(str(child))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(codes, key=int)


def probe_record(
    *,
    probe_key: str,
    request: dict[str, Any],
    response: dict[str, Any],
    payload: Any,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "probe_key": probe_key,
        "collected_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "senado",
        "record_type": "senator_discourses_probe",
        "request": request,
        "response": response,
        "checksum": sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "payload": payload,
        "pronunciamento_ids": extract_pronunciamento_codes(payload),
    }
    if error:
        record["error"] = error
    return record


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def _write_jsonl(records: Any, path: Path) -> None:
    ordered = sorted(records, key=lambda record: str(record.get("probe_key")))
    text = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n" for record in ordered)
    _write_text(text, path)


def _write_json(payload: dict[str, Any], path: Path) -> None:
    _write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", path)


def _write_text(value: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value.encode("utf-8"))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
