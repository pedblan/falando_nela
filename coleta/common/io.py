from __future__ import annotations

import json
import traceback
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from coleta.common.config import utc_now_iso


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class CollectionRun:
    def __init__(self, output_dir: Path, *, source: str, dataset: str, run_id: str, resume: bool) -> None:
        self.output_dir = output_dir
        self.source = source
        self.dataset = dataset
        self.run_id = run_id
        self.resume = resume
        self.started_at = utc_now_iso()
        self.record_counts: Counter[str] = Counter()
        self.partition_counts: Counter[str] = Counter()

        self.log_path = output_dir / "logs" / f"{run_id}.jsonl"
        self.manifest_path = output_dir / "manifests" / f"{run_id}.json"
        self.autosave_path = output_dir / "manifests" / f"{run_id}.autosave.json"
        self.checkpoint_path = output_dir / "checkpoints" / source / f"{dataset}.json"
        self._ensure_parent_dirs()
        self.checkpoint = self._load_checkpoint()
        self.processed_record_keys = self._load_existing_record_keys() if resume else set()
        self.write_autosave(status="started")

    def should_skip_partition(self, partition: str) -> bool:
        if not self.resume:
            return False
        run_completed = self._run_completed_partitions()
        if partition in run_completed:
            return True

        completed = self.checkpoint.get("completed_partitions", {})
        partition_checkpoint = completed.get(partition) if isinstance(completed, dict) else None
        if not isinstance(partition_checkpoint, dict):
            return False
        checkpoint_run_id = partition_checkpoint.get("run_id")
        if checkpoint_run_id is None:
            return self._has_partition_output(partition)
        return checkpoint_run_id == self.run_id

    def has_record(self, *, source_id: str, record_type: str) -> bool:
        return self._record_key(source_id=source_id, record_type=record_type) in self.processed_record_keys

    def write_record(
        self,
        *,
        partition: str,
        source_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        periodo: dict[str, str],
        payload: Any,
        record_type: str = "response",
    ) -> bool:
        record_key = self._record_key(source_id=source_id, record_type=record_type)
        if record_key in self.processed_record_keys:
            self.log("record_skipped", source_id=source_id, record_type=record_type)
            return False

        checksum = sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        record = {
            "run_id": self.run_id,
            "collected_at": utc_now_iso(),
            "source": self.source,
            "dataset": self.dataset,
            "record_type": record_type,
            "source_id": source_id,
            "partition": partition,
            "periodo": periodo,
            "request": request,
            "response": response,
            "checksum": checksum,
            "payload": payload,
        }

        raw_path = self._raw_path(partition)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_append_newline(raw_path)
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")

        self.record_counts[record_type] += 1
        self.partition_counts[partition] += 1
        self.processed_record_keys.add(record_key)
        return True

    def log(self, event: str, **fields: Any) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "run_id": self.run_id,
            "timestamp": utc_now_iso(),
            "source": self.source,
            "dataset": self.dataset,
            "event": event,
            **fields,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        self._print_progress(event, fields)

    def mark_partition_complete(self, partition: str, **metadata: Any) -> None:
        payload = {
            **metadata,
            "run_id": self.run_id,
            "completed_at": utc_now_iso(),
            "records": self.partition_counts.get(partition, 0),
        }
        completed = self.checkpoint.setdefault("completed_partitions", {})
        completed[partition] = payload
        self._run_checkpoint().setdefault("completed_partitions", {})[partition] = payload
        self._write_checkpoint()
        self.write_autosave(status="running")

    def mark_partition_failed(self, partition: str, **metadata: Any) -> None:
        payload = {
            **metadata,
            "run_id": self.run_id,
            "failed_at": utc_now_iso(),
            "records": self.partition_counts.get(partition, 0),
        }
        failed = self.checkpoint.setdefault("failed_partitions", {})
        failed[partition] = payload
        self._run_checkpoint().setdefault("failed_partitions", {})[partition] = payload
        self._write_checkpoint()
        self.write_autosave(status="running_with_failures")

    def write_autosave(self, *, status: str, **extra: Any) -> None:
        self.autosave_path.parent.mkdir(parents=True, exist_ok=True)
        autosave = self._manifest_payload(status=status, **extra)
        with self.autosave_path.open("w", encoding="utf-8") as handle:
            json.dump(autosave, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")

    def write_manifest(self, **extra: Any) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = self._manifest_payload(completed_at=utc_now_iso(), **extra)
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")
        autosave_extra = dict(extra)
        autosave_status = str(autosave_extra.pop("status", "completed"))
        self.write_autosave(status=autosave_status, **autosave_extra)

    def _manifest_payload(self, **extra: Any) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": self.source,
            "dataset": self.dataset,
            "started_at": self.started_at,
            "updated_at": utc_now_iso(),
            "output_dir": str(self.output_dir),
            "log_path": str(self.log_path),
            "autosave_path": str(self.autosave_path),
            "checkpoint_path": str(self.checkpoint_path),
            "record_counts": dict(self.record_counts),
            "partition_counts": dict(self.partition_counts),
            "processed_records_loaded": len(self.processed_record_keys),
            **extra,
        }

    def _ensure_parent_dirs(self) -> None:
        for path in [self.log_path, self.manifest_path, self.autosave_path, self.checkpoint_path]:
            path.parent.mkdir(parents=True, exist_ok=True)

    def _raw_path(self, partition: str) -> Path:
        parts = partition.split("-")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            return self.output_dir / "raw" / self.source / self.dataset / partition / f"{self.run_id}.jsonl"
        year, month = parts
        return (
            self.output_dir
            / "raw"
            / self.source
            / self.dataset
            / f"ano={year}"
            / f"mes={month}"
            / f"{self.run_id}.jsonl"
        )

    @staticmethod
    def _ensure_append_newline(path: Path) -> None:
        if not path.exists() or path.stat().st_size == 0:
            return
        with path.open("rb+") as handle:
            handle.seek(-1, 2)
            if handle.read(1) != b"\n":
                handle.write(b"\n")

    def _load_checkpoint(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            return {
                "source": self.source,
                "dataset": self.dataset,
                "created_at": utc_now_iso(),
                "completed_partitions": {},
            }
        with self.checkpoint_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_existing_record_keys(self) -> set[str]:
        root = self.output_dir / "raw" / self.source / self.dataset
        if not root.exists():
            return set()

        keys: set[str] = set()
        for path in root.rglob(f"{self.run_id}.jsonl"):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    source_id = record.get("source_id")
                    record_type = record.get("record_type")
                    if isinstance(source_id, str) and isinstance(record_type, str):
                        keys.add(self._record_key(source_id=source_id, record_type=record_type))
        return keys

    def _has_partition_output(self, partition: str) -> bool:
        path = self._raw_path(partition)
        return path.exists() and path.stat().st_size > 0

    def _run_checkpoint(self) -> dict[str, Any]:
        runs = self.checkpoint.setdefault("runs", {})
        if not isinstance(runs, dict):
            runs = {}
            self.checkpoint["runs"] = runs
        current = runs.setdefault(self.run_id, {})
        if not isinstance(current, dict):
            current = {}
            runs[self.run_id] = current
        return current

    def _run_completed_partitions(self) -> dict[str, Any]:
        runs = self.checkpoint.get("runs", {})
        if not isinstance(runs, dict):
            return {}
        current = runs.get(self.run_id, {})
        if not isinstance(current, dict):
            return {}
        completed = current.get("completed_partitions", {})
        return completed if isinstance(completed, dict) else {}

    def _write_checkpoint(self) -> None:
        self.checkpoint["updated_at"] = utc_now_iso()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(self.checkpoint, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")
        tmp_path.replace(self.checkpoint_path)

    def _print_progress(self, event: str, fields: dict[str, Any]) -> None:
        parts = []
        for key, value in fields.items():
            compact = _compact_progress_value(value)
            if compact is not None:
                parts.append(f"{key}={compact}")
        suffix = " " + " ".join(parts) if parts else ""
        print(f"[{utc_now_iso()}] {self.source}/{self.dataset} {event}{suffix}", flush=True)

    @staticmethod
    def _record_key(*, source_id: str, record_type: str) -> str:
        return f"{record_type}\t{source_id}"


def error_summary(exc: BaseException, *, include_traceback: bool = False) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
    if include_traceback:
        summary["traceback"] = "".join(traceback.format_exception(exc)).strip()
    return summary


def _compact_progress_value(value: Any) -> str | None:
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, dict):
        scalar_items = {
            key: child
            for key, child in value.items()
            if child is None or isinstance(child, (bool, int, float, str))
        }
        if not scalar_items:
            return None
        return _truncate(json.dumps(scalar_items, ensure_ascii=False, sort_keys=True, default=str))
    return None


def _truncate(value: str, limit: int = 160) -> str:
    value = value.replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
