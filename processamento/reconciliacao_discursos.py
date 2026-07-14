from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd


TARGETS = {
    "plenario_discursos": {"arena": "senado", "house": "SF"},
    "congresso_discursos": {"arena": "congresso", "house": "CN"},
}
TARGET_YEARS = (2015, 2016)
LAYERS = ("discovered", "raw", "raw_text", "processed", "parquet", "snapshot")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcilia o backfill 2015-2016 de Senado/Congresso por texto_id."
    )
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--cycle-dir", required=True)
    parser.add_argument("--phase", choices=["pre", "post"], required=True)
    parser.add_argument("--snapshot-path", default=None)
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = reconcile_discursos(
        data_root=Path(args.data_root),
        cycle_dir=Path(args.cycle_dir),
        phase=args.phase,
        snapshot_path=Path(args.snapshot_path) if args.snapshot_path else None,
        strict=args.strict,
    )
    print(result["summary_path"])


def reconcile_discursos(
    *,
    data_root: Path,
    cycle_dir: Path,
    phase: str,
    snapshot_path: Path | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    if phase not in {"pre", "post"}:
        raise ValueError("phase deve ser pre ou post")
    data_root = data_root.expanduser()
    cycle_dir = cycle_dir.expanduser()
    cycle_dir.mkdir(parents=True, exist_ok=True)

    layers, probes, conflicts, inputs = load_layers(data_root, snapshot_path=snapshot_path)
    senator_probes_path = cycle_dir / "senator_endpoint_probes.jsonl"
    if senator_probes_path.exists():
        probes.extend(iter_jsonl(senator_probes_path))
    control_root = cycle_dir / "control_data" / "raw" / "senado"
    for path in sorted(control_root.rglob("*.jsonl")) if control_root.exists() else []:
        for record in iter_jsonl(path):
            if record.get("record_type") in {
                "discursos_periodo_metadata",
                "discursos_historical_discovery",
            }:
                probes.append(_probe_record(record, path, data_root))
    reconciliation = build_reconciliation(layers)
    coverage = build_coverage(layers, phase=phase)
    gates = reconciliation_gates(reconciliation, snapshot_required=snapshot_path is not None)
    parquet_fingerprints = parquet_scope_fingerprints(data_root)
    drift = {"compared_to": None, "out_of_scope_changes": []}
    if phase == "post":
        pre_inventory_path = cycle_dir / "inventory_pre.json"
        if pre_inventory_path.exists():
            pre_inventory = json.loads(pre_inventory_path.read_text(encoding="utf-8"))
            before = _dict(pre_inventory.get("parquet_scope_fingerprints"))
            drift = compare_scope_fingerprints(before, parquet_fingerprints)
            drift["compared_to"] = str(pre_inventory_path)
            gates["out_of_scope_invariant"] = not drift["out_of_scope_changes"]
        else:
            gates["out_of_scope_invariant"] = False
            drift["out_of_scope_changes"] = ["inventory_pre.json ausente"]
    coverage_pre_path = cycle_dir / "coverage_pre.csv"
    coverage_pre = (
        pd.read_csv(coverage_pre_path)
        if phase == "post" and coverage_pre_path.exists()
        else coverage
    )
    classifications = Counter(
        str(probe["classification"])
        for probe in probes
        if probe.get("classification")
    )

    coverage_path = cycle_dir / f"coverage_{phase}.csv"
    _write_dataframe(coverage, coverage_path)
    outputs = [artifact(coverage_path, rows=len(coverage))]
    inventory_path = cycle_dir / f"inventory_{phase}.json"
    inventory = {
        "phase": phase,
        "data_root": str(data_root),
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
        "inputs": [artifact(path) for path in sorted(inputs) if path.exists()],
        "parquet_scope_fingerprints": parquet_fingerprints,
    }
    _write_json(inventory, inventory_path)
    outputs.append(artifact(inventory_path))

    probes_path = cycle_dir / "source_probes.jsonl"
    conflicts_path = cycle_dir / "source_conflicts.jsonl"
    if phase == "post" or not probes_path.exists():
        _write_jsonl(probes, probes_path)
        _write_jsonl(conflicts, conflicts_path)
    outputs.extend(
        [
            artifact(probes_path, rows=len(probes)),
            artifact(conflicts_path, rows=len(conflicts)),
        ]
    )

    reconciliation_path = cycle_dir / "reconciliation_ids.parquet"
    if phase == "post":
        _write_dataframe(reconciliation, reconciliation_path)
        outputs.append(artifact(reconciliation_path, rows=len(reconciliation)))

    summary = {
        "schema_version": 1,
        "phase": phase,
        "data_root": str(data_root),
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
        "target_years": list(TARGET_YEARS),
        "targets": TARGETS,
        "inputs": inventory["inputs"],
        "outputs": outputs,
        "counts": {
            layer: sum(len(values) for values in by_dataset.values())
            for layer, by_dataset in layers.items()
        },
        "coverage_counts": {
            "pre": _coverage_totals(coverage_pre),
            phase: _coverage_totals(coverage),
        },
        "statuses": reconciliation["status"].value_counts(dropna=False).to_dict(),
        "source_classifications": dict(sorted(classifications.items())),
        "source_classification": (
            "source_anomaly"
            if classifications.get("source_anomaly")
            else "primary_recovered"
            if classifications.get("primary_recovered")
            else "unresolved"
        ),
        "drift": drift,
        "gates": gates,
        "passed": all(gates.values()),
    }
    summary_path = cycle_dir / "summary.json"
    summary["summary_path"] = str(summary_path)
    _write_json(summary, summary_path)
    if strict and not summary["passed"]:
        failed = sorted(name for name, passed in gates.items() if not passed)
        raise ValueError(f"Reconciliacao incompleta: {failed}. Consulte {summary_path}")
    return summary


def load_layers(
    data_root: Path,
    *,
    snapshot_path: Path | None,
) -> tuple[
    dict[str, dict[str, dict[str, dict[str, Any]]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[Path],
]:
    layers: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
        layer: {dataset: {} for dataset in TARGETS} for layer in LAYERS
    }
    probes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    inputs: set[Path] = set()

    for dataset, target in TARGETS.items():
        raw_root = data_root / "raw" / "senado" / dataset
        for path in sorted(raw_root.rglob("*.jsonl")) if raw_root.exists() else []:
            inputs.add(path)
            for record in iter_jsonl(path):
                record_type = str(record.get("record_type") or "")
                if record_type == "discursos_periodo_metadata":
                    if _period_intersects_target(record.get("periodo")):
                        probes.append(_probe_record(record, path, data_root))
                    continue
                if record_type == "discursos_historical_discovery":
                    payload = _dict(record.get("payload"))
                    if str(payload.get("house")) != target["house"]:
                        continue
                    probes.append(_probe_record(record, path, data_root))
                    audit = _dict(payload.get("audit"))
                    if audit.get("primary_missing_in_portal"):
                        conflicts.append(
                            {
                                "dataset": dataset,
                                "partition": payload.get("partition"),
                                "type": "primary_missing_in_portal",
                                "ids": audit["primary_missing_in_portal"],
                                "raw_path": _relative(path, data_root),
                            }
                        )
                    for item in _list(payload.get("items")):
                        code = str(_dict(item).get("codigo_pronunciamento") or "")
                        if not code:
                            continue
                        metadata = _dict(_dict(item).get("metadata"))
                        speech = _dict(metadata.get("pronunciamento"))
                        day = _date_string(speech.get("Data"))
                        if not _target_date(day):
                            continue
                        text_id = _text_id(dataset, code)
                        _put(
                            layers["discovered"][dataset],
                            text_id,
                            {
                                "texto_id": text_id,
                                "codigo_pronunciamento": code,
                                "data": day,
                                "ano": int(day[:4]),
                                "mes": int(day[5:7]),
                                "house": target["house"],
                                "raw_path": _relative(path, data_root),
                            },
                        )
                    continue
                if record_type != "pronunciamento_texto":
                    continue
                payload = _dict(record.get("payload"))
                code = str(payload.get("codigo_pronunciamento") or payload.get("CodigoPronunciamento") or "")
                metadata = _dict(payload.get("metadata"))
                speech = _dict(metadata.get("pronunciamento"))
                session = _dict(metadata.get("sessao"))
                day = _date_string(speech.get("Data") or session.get("DataSessao"))
                if not code or not _target_date(day):
                    continue
                text_id = _text_id(dataset, code)
                raw_row = {
                    "texto_id": text_id,
                    "codigo_pronunciamento": code,
                    "data": day,
                    "ano": int(day[:4]),
                    "mes": int(day[5:7]),
                    "house": target["house"],
                    "texto_status": payload.get("texto_status"),
                    "metodo_obtencao": payload.get("metodo_obtencao"),
                    "raw_run_id": record.get("run_id"),
                    "raw_path": _relative(path, data_root),
                }
                _put(layers["raw"][dataset], text_id, raw_row)
                if str(payload.get("texto") or payload.get("TextoIntegral") or "").strip():
                    _put(layers["raw_text"][dataset], text_id, raw_row)

    processed_root = data_root / "processed" / "textos_parlamentares" / "v1"
    for path in sorted(processed_root.rglob("*.jsonl")) if processed_root.exists() else []:
        inputs.add(path)
        for record in iter_jsonl(path):
            dataset = str(record.get("dataset") or "")
            if record.get("source") != "senado" or dataset not in TARGETS:
                continue
            day = _date_string(record.get("data"))
            if not _target_date(day):
                continue
            text_id = str(record.get("texto_id") or "")
            if text_id:
                _put(layers["processed"][dataset], text_id, _layer_row(record, day, path, data_root))

    parquet_root = processed_root / "parquet"
    for dataset in TARGETS:
        path = parquet_root / f"senado__{dataset}.parquet"
        if not path.exists():
            continue
        inputs.add(path)
        frame = pd.read_parquet(path)
        for record in frame.to_dict("records"):
            day = _date_string(record.get("data"))
            if not _target_date(day):
                continue
            text_id = str(record.get("texto_id") or "")
            if text_id:
                _put(layers["parquet"][dataset], text_id, _layer_row(record, day, path, data_root))

    if snapshot_path is not None and snapshot_path.exists():
        inputs.add(snapshot_path)
        snapshot = pd.read_parquet(snapshot_path)
        for record in snapshot.to_dict("records"):
            arena = str(record.get("arena") or "")
            dataset = next((name for name, spec in TARGETS.items() if spec["arena"] == arena), None)
            day = _date_string(record.get("data") or record.get("data_analise"))
            if dataset and _target_date(day):
                text_id = str(record.get("texto_id") or "")
                if text_id:
                    _put(layers["snapshot"][dataset], text_id, _layer_row(record, day, snapshot_path, data_root))
        duplicate_path = snapshot_path.parent / "duplicate_audit.csv"
        if duplicate_path.exists():
            inputs.add(duplicate_path)
            duplicate_frame = pd.read_csv(duplicate_path)
            for record in duplicate_frame.to_dict("records"):
                if record.get("status") != "auto_remove_senado":
                    continue
                text_id = str(record.get("senado_texto_id") or "")
                if text_id:
                    layers.setdefault("snapshot_duplicate_removed", {}).setdefault("plenario_discursos", {})[
                        text_id
                    ] = {"texto_id": text_id}
    return layers, probes, conflicts, inputs


def build_reconciliation(
    layers: dict[str, dict[str, dict[str, dict[str, Any]]]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    duplicate_removed = layers.get("snapshot_duplicate_removed", {})
    for dataset, target in TARGETS.items():
        ids = set().union(*(set(layers[layer][dataset]) for layer in LAYERS))
        for text_id in sorted(ids):
            discovered = text_id in layers["discovered"][dataset]
            raw = text_id in layers["raw"][dataset]
            raw_text = text_id in layers["raw_text"][dataset]
            processed = text_id in layers["processed"][dataset]
            parquet = text_id in layers["parquet"][dataset]
            snapshot = text_id in layers["snapshot"][dataset]
            removed = text_id in duplicate_removed.get(dataset, {})
            metadata = next(
                (
                    layers[layer][dataset][text_id]
                    for layer in LAYERS
                    if text_id in layers[layer][dataset]
                ),
                {},
            )
            rows.append(
                {
                    "texto_id": text_id,
                    "codigo_pronunciamento": metadata.get("codigo_pronunciamento")
                    or text_id.rsplit(":", 1)[-1],
                    "source": "senado",
                    "dataset": dataset,
                    "arena": target["arena"],
                    "house": target["house"],
                    "data": metadata.get("data"),
                    "ano": metadata.get("ano"),
                    "mes": metadata.get("mes"),
                    "discovered": discovered,
                    "raw": raw,
                    "raw_text": raw_text,
                    "processed": processed,
                    "parquet": parquet,
                    "snapshot": snapshot,
                    "snapshot_duplicate_removed": removed,
                    "texto_status": layers["raw"][dataset].get(text_id, {}).get("texto_status"),
                    "metodo_obtencao": layers["raw"][dataset].get(text_id, {}).get("metodo_obtencao"),
                    "status": _status(
                        discovered=discovered,
                        raw=raw,
                        raw_text=raw_text,
                        processed=processed,
                        parquet=parquet,
                        snapshot=snapshot,
                        removed=removed,
                    ),
                }
            )
    columns = [
        "texto_id",
        "codigo_pronunciamento",
        "source",
        "dataset",
        "arena",
        "house",
        "data",
        "ano",
        "mes",
        "discovered",
        "raw",
        "raw_text",
        "processed",
        "parquet",
        "snapshot",
        "snapshot_duplicate_removed",
        "texto_status",
        "metodo_obtencao",
        "status",
    ]
    return pd.DataFrame(rows, columns=columns)


def parquet_scope_fingerprints(data_root: Path) -> dict[str, dict[str, Any]]:
    parquet_root = data_root / "processed" / "textos_parlamentares" / "v1" / "parquet"
    fingerprints: dict[str, dict[str, Any]] = {}
    for path in sorted(parquet_root.glob("*.parquet")) if parquet_root.exists() else []:
        frame = pd.read_parquet(path)
        if "texto_id" not in frame or "texto" not in frame:
            continue
        target_dataset = next(
            (
                dataset
                for dataset in TARGETS
                if path.name == f"senado__{dataset}.parquet"
            ),
            None,
        )
        if target_dataset and "data" in frame:
            years = pd.to_datetime(frame["data"], errors="coerce").dt.year
            in_scope = years.isin(TARGET_YEARS)
        else:
            in_scope = pd.Series(False, index=frame.index)
        out_of_scope = frame.loc[~in_scope]
        fingerprints[path.name] = {
            "path": str(path),
            "rows": len(frame),
            "full_text_id_text_sha256": _frame_text_fingerprint(frame),
            "in_scope_rows": int(in_scope.sum()),
            "out_of_scope_rows": len(out_of_scope),
            "out_of_scope_text_id_text_sha256": _frame_text_fingerprint(out_of_scope),
            "target_dataset": target_dataset,
        }
    return fingerprints


def compare_scope_fingerprints(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    changes: list[str] = []
    for name in sorted(set(before).union(after)):
        old = _dict(before.get(name))
        new = _dict(after.get(name))
        if not old or not new:
            changes.append(f"{name}: arquivo ausente em {'pre' if not old else 'post'}")
            continue
        key = (
            "out_of_scope_text_id_text_sha256"
            if old.get("target_dataset") or new.get("target_dataset")
            else "full_text_id_text_sha256"
        )
        row_key = "out_of_scope_rows" if key.startswith("out_of_scope") else "rows"
        if old.get(key) != new.get(key) or old.get(row_key) != new.get(row_key):
            changes.append(f"{name}: conteúdo fora do escopo mudou")
    return {"out_of_scope_changes": changes}


def build_coverage(
    layers: dict[str, dict[str, dict[str, dict[str, Any]]]],
    *,
    phase: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dataset, target in TARGETS.items():
        for year in TARGET_YEARS:
            for month in range(1, 13):
                for layer in LAYERS:
                    count = sum(
                        1
                        for row in layers[layer][dataset].values()
                        if row.get("ano") == year and row.get("mes") == month
                    )
                    rows.append(
                        {
                            "phase": phase,
                            "source": "senado",
                            "dataset": dataset,
                            "arena": target["arena"],
                            "ano": year,
                            "mes": month,
                            "layer": layer,
                            "count": count,
                        }
                    )
    return pd.DataFrame(rows)


def reconciliation_gates(
    frame: pd.DataFrame,
    *,
    snapshot_required: bool,
) -> dict[str, bool]:
    if frame.empty:
        return {
            "discovery_nonempty": False,
            "discovered_equals_raw": False,
            "raw_text_equals_processed": False,
            "processed_equals_parquet": False,
            "parquet_reaches_snapshot": not snapshot_required,
            "sentinels": False,
        }
    discovered_rows = frame.loc[frame["discovered"]]
    expected_sentinels = {
        _text_id("plenario_discursos", "414849"),
        _text_id("plenario_discursos", "422757"),
        _text_id("congresso_discursos", "411219"),
        _text_id("congresso_discursos", "426642"),
    }
    return {
        "discovery_nonempty": bool(
            all(
                not discovered_rows.loc[discovered_rows["dataset"].eq(dataset)].empty
                for dataset in TARGETS
            )
        ),
        "discovered_equals_raw": bool((frame["discovered"] == frame["raw"]).all()),
        "raw_text_equals_processed": bool((frame["raw_text"] == frame["processed"]).all()),
        "processed_equals_parquet": bool((frame["processed"] == frame["parquet"]).all()),
        "parquet_reaches_snapshot": bool(
            (frame["parquet"] == (frame["snapshot"] | frame["snapshot_duplicate_removed"])).all()
        )
        if snapshot_required
        else True,
        "sentinels": expected_sentinels.issubset(set(frame.loc[frame["discovered"], "texto_id"])),
    }


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL invalido em {path}:{line_number}") from exc
            if isinstance(value, dict):
                yield value


def artifact(path: Path, *, rows: int | None = None) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
        "rows": rows,
    }


def _status(
    *,
    discovered: bool,
    raw: bool,
    raw_text: bool,
    processed: bool,
    parquet: bool,
    snapshot: bool,
    removed: bool,
) -> str:
    if not discovered:
        return "not_discovered"
    if not raw:
        return "raw_missing"
    if not raw_text:
        return "text_unavailable"
    if not processed:
        return "normalization_loss"
    if not parquet:
        return "parquet_loss"
    if not snapshot:
        return "snapshot_duplicate_removed" if removed else "snapshot_filter_loss"
    return "covered"


def _put(target: dict[str, dict[str, Any]], key: str, row: dict[str, Any]) -> None:
    current = target.get(key)
    if current is None:
        target[key] = row
        return
    for field in ("data", "ano", "mes", "house"):
        if current.get(field) not in {None, row.get(field)} and row.get(field) is not None:
            raise ValueError(f"Conflito de {field} para {key}: {current.get(field)} != {row.get(field)}")


def _layer_row(record: dict[str, Any], day: str, path: Path, data_root: Path) -> dict[str, Any]:
    return {
        "texto_id": str(record.get("texto_id") or ""),
        "codigo_pronunciamento": record.get("pronunciamento_id"),
        "data": day,
        "ano": int(day[:4]),
        "mes": int(day[5:7]),
        "raw_path": _relative(path, data_root),
    }


def _probe_record(record: dict[str, Any], path: Path, data_root: Path) -> dict[str, Any]:
    payload = _dict(record.get("payload"))
    probe = {
        "run_id": record.get("run_id"),
        "collected_at": record.get("collected_at"),
        "source": record.get("source"),
        "dataset": record.get("dataset"),
        "record_type": record.get("record_type"),
        "source_id": record.get("source_id"),
        "periodo": record.get("periodo"),
        "request": record.get("request"),
        "response": record.get("response"),
        "checksum": record.get("checksum"),
        "raw_path": _relative(path, data_root),
    }
    if record.get("record_type") == "discursos_historical_discovery":
        audit = _dict(payload.get("audit"))
        if audit.get("primary_empty_portal_nonempty"):
            probe["classification"] = "source_anomaly"
        elif int(audit.get("primary_count") or 0) > 0:
            probe["classification"] = "primary_recovered"
        elif int(audit.get("portal_house_count") or 0) == 0:
            probe["classification"] = "concordant_empty"
    return probe


def _period_intersects_target(value: Any) -> bool:
    period = _dict(value)
    start = _date_string(period.get("data_inicio"))
    end = _date_string(period.get("data_fim"))
    return bool(start and end and start[:4] <= "2016" and end[:4] >= "2015")


def _target_date(value: str) -> bool:
    return len(value) >= 7 and value[:4].isdigit() and int(value[:4]) in TARGET_YEARS


def _date_string(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _text_id(dataset: str, code: str) -> str:
    return f"senado:{dataset}:pronunciamento:{code}"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _frame_text_fingerprint(frame: pd.DataFrame) -> str:
    digest = sha256()
    canonical = frame[["texto_id", "texto"]].fillna("").astype(str).sort_values(
        ["texto_id", "texto"], kind="stable"
    )
    for texto_id, texto in canonical.itertuples(index=False, name=None):
        digest.update(json.dumps([texto_id, texto], ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _coverage_totals(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty:
        return {}
    grouped = frame.groupby(["dataset", "layer"], dropna=False)["count"].sum()
    return {
        f"{dataset}/{layer}": int(count)
        for (dataset, layer), count in grouped.items()
    }


def _write_dataframe(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=path.suffix, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        if path.suffix == ".csv":
            frame.to_csv(temporary, index=False)
        elif path.suffix == ".parquet":
            frame.to_parquet(temporary, index=False)
        else:
            raise ValueError(f"Formato tabular nao suportado: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(payload: dict[str, Any], path: Path) -> None:
    _write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", path)


def _write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
    _write_text(text, path)


def _write_text(value: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value.encode("utf-8"))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
