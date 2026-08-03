from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, BinaryIO


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    atomic_write_bytes(path, canonical_json_bytes(value) + b"\n")


def deterministic_gzip(
    input_path: Path, output_path: Path, *, compresslevel: int = 9
) -> dict[str, Any]:
    """Compacta bytes sem nome ou horário variáveis e publica atomicamente."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    temporary = Path(temporary_name)
    uncompressed = hashlib.sha256()
    try:
        with input_path.open("rb") as source, os.fdopen(descriptor, "wb") as raw_target:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=compresslevel,
                fileobj=raw_target,
                mtime=0,
            ) as compressed:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    uncompressed.update(chunk)
                    compressed.write(chunk)
            raw_target.flush()
            os.fsync(raw_target.fileno())
        os.replace(temporary, output_path)
        _fsync_directory(output_path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "path": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256_uncompressed": uncompressed.hexdigest(),
        "sha256_stored_object": sha256_file(output_path),
    }


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with _open_raw(path) as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            value = json.loads(raw_line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: o registro JSONL não é um objeto.")
            yield value


def uncompressed_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _open_raw(path) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_raw(path: Path) -> BinaryIO:
    if path.name.endswith(".jsonl.gz"):
        return gzip.open(path, "rb")
    if path.name.endswith(".jsonl"):
        return path.open("rb")
    raise ValueError(f"Formato raw não suportado em R02: {path.name}.")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
