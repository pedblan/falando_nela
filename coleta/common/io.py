from __future__ import annotations

import json
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
        self.checkpoint_path = output_dir / "checkpoints" / source / f"{dataset}.json"
        self._ensure_parent_dirs()
        self.checkpoint = self._load_checkpoint()

    def should_skip_partition(self, partition: str) -> bool:
        return self.resume and partition in self.checkpoint.get("completed_partitions", {})

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
    ) -> None:
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
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")

        self.record_counts[record_type] += 1
        self.partition_counts[partition] += 1

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

    def mark_partition_complete(self, partition: str, **metadata: Any) -> None:
        completed = self.checkpoint.setdefault("completed_partitions", {})
        completed[partition] = {
            "completed_at": utc_now_iso(),
            "records": self.partition_counts.get(partition, 0),
            **metadata,
        }
        self._write_checkpoint()

    def write_manifest(self, **extra: Any) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": self.run_id,
            "source": self.source,
            "dataset": self.dataset,
            "started_at": self.started_at,
            "completed_at": utc_now_iso(),
            "output_dir": str(self.output_dir),
            "log_path": str(self.log_path),
            "checkpoint_path": str(self.checkpoint_path),
            "record_counts": dict(self.record_counts),
            "partition_counts": dict(self.partition_counts),
            **extra,
        }
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")

    def _ensure_parent_dirs(self) -> None:
        for path in [self.log_path, self.manifest_path, self.checkpoint_path]:
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

    def _write_checkpoint(self) -> None:
        self.checkpoint["updated_at"] = utc_now_iso()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(self.checkpoint, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")
        tmp_path.replace(self.checkpoint_path)
