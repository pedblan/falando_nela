from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .config import AnalysisConfig, resolve_input_paths, resolve_output_root


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_inputs(
    config: AnalysisConfig,
    data_root: str | Path,
    *,
    arenas: Iterable[str] | None = None,
    optional: bool = False,
) -> dict[str, pd.DataFrame]:
    requested = list(arenas or config.raw["arenas"])
    paths = resolve_input_paths(config, data_root)
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for arena in requested:
        path = paths[arena]
        if path.exists():
            frames[arena] = pd.read_parquet(path)
        else:
            missing.append(f"{arena}: {path}")
    if missing and not optional:
        raise FileNotFoundError("Entradas ausentes:\n" + "\n".join(missing))
    return frames


def read_optional_parquet(path: str | Path) -> pd.DataFrame:
    resolved = Path(path)
    return pd.read_parquet(resolved) if resolved.exists() else pd.DataFrame()


def input_inventory(config: AnalysisConfig, data_root: str | Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, path in resolve_input_paths(config, data_root).items():
        exists = path.exists()
        rows.append(
            {
                "entrada": name,
                "caminho": str(path),
                "existe": exists,
                "tamanho_bytes": path.stat().st_size if exists else None,
                "sha256": sha256_file(path) if exists else None,
            }
        )
    return pd.DataFrame(rows)


def prepare_run_directory(
    config: AnalysisConfig,
    data_root: str | Path,
    run_id: str,
    *,
    stage: str | None = None,
    overwrite: bool = False,
) -> Path:
    root = resolve_output_root(config, data_root, run_id)
    protected = root / stage if stage else root
    if protected.exists() and any(protected.iterdir()) and not overwrite:
        raise FileExistsError(f"Etapa existente: {protected}. Use overwrite=True conscientemente.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_json_atomic(path: str | Path, payload: Mapping[str, Any] | list[Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n"
    _write_bytes_atomic(destination, encoded.encode("utf-8"))
    return destination


def write_dataframe_atomic(frame: pd.DataFrame, path: str | Path, *, index: bool = False) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = destination.suffix.lower()
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=suffix, delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        if suffix == ".parquet":
            frame.to_parquet(temp_path, index=index)
        elif suffix == ".csv":
            frame.to_csv(temp_path, index=index)
        elif suffix == ".jsonl":
            frame.to_json(temp_path, orient="records", lines=True, force_ascii=False, date_format="iso")
        else:
            raise ValueError(f"Formato tabular nao suportado: {suffix}")
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)
    return destination


def artifact_record(path: str | Path, *, rows: int | None = None) -> dict[str, Any]:
    resolved = Path(path)
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
        "rows": rows,
    }


def base_manifest(
    *,
    config: AnalysisConfig,
    run_id: str,
    stage: str,
    inputs: Iterable[Mapping[str, Any]] = (),
    outputs: Iterable[Mapping[str, Any]] = (),
    counts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "analysis_version": config.raw["analysis_version"],
        "run_id": run_id,
        "stage": stage,
        "created_at": utc_now_iso(),
        "configuration": config.to_dict(),
        "inputs": list(inputs),
        "outputs": list(outputs),
        "counts": dict(counts or {}),
    }


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Tipo nao serializavel: {type(value)!r}")
