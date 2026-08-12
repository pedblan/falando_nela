from __future__ import annotations

import base64
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

from falando_nela.gcp_config import GcpContract, SentinelConfig, load_gcp_contract
from falando_nela.gcs_full_migration import (
    GcsCopyConflict,
    GcsFullMigrationError,
    GcsJsonApi,
    GcsObjectMetadata,
    build_full_execution_plan,
    execute_gcs_cutover,
    execute_gcs_full,
    select_restore_sample,
    validate_mixed_combined,
)
from falando_nela.gcs_migration import (
    EMPTY_MD5,
    EMPTY_SHA256,
    CatalogEntry,
    load_source_catalog,
    select_sentinel,
)
from falando_nela.raw import atomic_write_json, canonical_json_bytes, sha256_file
from falando_nela.sources import SourceObject

REPO_ROOT = Path(__file__).parents[2]
CONFIG_PATH = REPO_ROOT / "config/gcp.toml"
CATALOG_PATH = (
    REPO_ROOT
    / "data_samples/operations/organize_drive"
    / "r03-drive-copy-batched-20260803/copy-catalog.jsonl"
)
BATCH_PLAN_PATH = (
    REPO_ROOT
    / "data_samples/operations/organize_drive"
    / "r03-drive-copy-batched-20260803/copy-execution-plan.json"
)
RAW_FOLDER_ID = "1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9"
TOKEN = "TOKEN-G02-NAO-PODE-VAZAR"


class FakeSource:
    def __init__(self, entries: Sequence[CatalogEntry]) -> None:
        self.entries = list(entries)
        self.list_calls = 0

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "fake-rclone",
            "scope": "drive.readonly",
            "root_folder_id": RAW_FOLDER_ID,
        }

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
        assert prefix is None
        self.list_calls += 1
        objects = []
        for entry in self.entries:
            hashes = dict(entry.provider_hashes)
            if entry.size_bytes == 0:
                hashes.pop("sha256")
            objects.append(
                SourceObject(
                    locator=entry.source_locator,
                    size_bytes=entry.size_bytes,
                    provider_hashes=hashes,
                )
            )
        return objects


class FakeFullTransport:
    def __init__(
        self,
        entries: Sequence[CatalogEntry],
        sentinel: Sequence[CatalogEntry],
        content: Mapping[str, bytes],
        *,
        fail_after_write: bool = False,
    ) -> None:
        self.entries = {item.destination_locator: item for item in entries}
        self.content = dict(content)
        self.objects = {
            item.destination_locator: self._metadata(item, generation="1") for item in sentinel
        }
        self.remote_bytes: dict[str, bytes] = {}
        self.copy_calls: list[tuple[bool, tuple[str, ...]]] = []
        self.publish_calls = 0
        self.fail_after_write = fail_after_write
        self.next_generation = 2

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "fake-gcs",
            "project_id": "falando-nela-pedblan",
            "bucket": "falando-nela-pedblan-data",
            "region": "southamerica-east1",
            "raw_prefix": "data/raw/v1",
        }

    def destination_metadata(self) -> list[GcsObjectMetadata]:
        return sorted(self.objects.values(), key=lambda item: item.locator)

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]:
        selected = tuple(item.source_locator for item in entries)
        self.copy_calls.append((dry_run, selected))
        files_from_path.parent.mkdir(parents=True, exist_ok=True)
        files_from_path.write_bytes(
            b"".join(item.source_locator.encode("utf-8") + b"\0" for item in entries)
        )
        markers = []
        for entry in entries:
            marker = "=" if entry.destination_locator in self.objects else "+"
            markers.append(f"{marker} {entry.source_locator}\n")
            if not dry_run and marker == "+":
                self.objects[entry.destination_locator] = self._metadata(
                    entry, generation=str(self.next_generation)
                )
                self.next_generation += 1
        if not dry_run and self.fail_after_write:
            self.fail_after_write = False
            raise GcsFullMigrationError("falha simulada depois da escrita")
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        combined_path.write_text("".join(markers), encoding="utf-8")
        return {"return_code": 0, "combined_sha256": sha256_file(combined_path)}

    def restore_object(self, locator: str, destination: Path, *, generation: str) -> None:
        assert generation == self.objects[locator].generation
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.content[locator])

    def publish_bytes_create_only(self, locator: str, content: bytes) -> dict[str, Any]:
        self.publish_calls += 1
        if locator in self.remote_bytes:
            if self.remote_bytes[locator] != content:
                raise GcsCopyConflict(f"manifest remoto existente diverge: {locator}")
            return {"status": "reused_verified", "generation": "manifest-1"}
        self.remote_bytes[locator] = content
        return {"status": "created", "generation": "manifest-1"}

    def read_bytes(self, locator: str) -> bytes | None:
        return self.remote_bytes.get(locator)

    @staticmethod
    def _metadata(entry: CatalogEntry, *, generation: str) -> GcsObjectMetadata:
        return GcsObjectMetadata(
            locator=entry.destination_locator,
            size_bytes=entry.size_bytes,
            md5=entry.provider_hashes["md5"],
            crc32c="AAAAAA==",
            generation=generation,
            metageneration="1",
            storage_class="STANDARD",
        )


def _entry(
    source: str,
    dataset: str,
    category: str,
    relative: str,
    content: bytes,
) -> CatalogEntry:
    source_locator = f"{source}/{dataset}/{relative}"
    return CatalogEntry(
        source=source,
        dataset=dataset,
        category=category,
        source_locator=source_locator,
        destination_locator=f"data/raw/v1/{source_locator}",
        size_bytes=len(content),
        provider_hashes={
            "md5": hashlib.md5(content, usedforsecurity=False).hexdigest(),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )


def _fixture(
    tmp_path: Path, *, fail_after_write: bool = False
) -> tuple[
    GcpContract,
    Path,
    Path,
    Path,
    Path,
    list[CatalogEntry],
    FakeSource,
    FakeFullTransport,
]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    entries = [
        _entry("senado", "pareceres_pec", "metadata", "metadata/sentinel.jsonl", b"meta"),
        _entry(
            "camara",
            "plenario_discursos",
            "monthly_text",
            "ano=1970/mes=01/sentinel.jsonl",
            b"monthly",
        ),
        _entry(
            "senado",
            "plenario_discursos",
            "transcription_queue",
            "transcription_queue/sentinel.jsonl",
            b"queue",
        ),
        _entry("camara", "ccjc_eventos", "monthly_text", "ano=2019/mes=03/item.jsonl", b"ccjc"),
        _entry(
            "camara",
            "plenario_discursos",
            "monthly_text",
            "ano=1954/mes=12/prod-historico-camara-plenario.jsonl",
            b"",
        ),
        _entry(
            "camara",
            "plenario_discursos",
            "monthly_text",
            "ano=1956/mes=06/prod-historico-camara-plenario.jsonl",
            b"",
        ),
    ]
    catalog_path = tmp_path / "catalog.jsonl"
    catalog_path.write_bytes(
        b"".join(canonical_json_bytes(item.as_dict()) + b"\n" for item in entries)
    )
    base = load_gcp_contract(CONFIG_PATH)
    sentinel_entries = entries[:3]
    sentinel = tuple(
        SentinelConfig(
            category=item.category,
            source_locator=item.source_locator,
            destination_locator=item.destination_locator,
            size_bytes=item.size_bytes,
            md5=item.provider_hashes["md5"],
            sha256=item.provider_hashes["sha256"],
        )
        for item in sentinel_entries
    )
    plan = build_full_execution_plan(
        entries, sentinel_entries, batch_max_files=2, batch_max_bytes=100
    )
    batch_plan_path = tmp_path / "batch-plan.json"
    atomic_write_json(batch_plan_path, plan)
    sample = select_restore_sample(
        entries,
        sentinel_entries,
        approved_empty_locators=base.migration.approved_empty_source_locators,
        max_object_bytes=100,
    )
    migration = base.migration.model_copy(
        update={
            "source_files": len(entries),
            "source_bytes": sum(item.size_bytes for item in entries),
            "source_catalog_sha256": "a" * 64,
            "source_catalog_file_sha256": sha256_file(catalog_path),
            "source_batch_plan_file_sha256": sha256_file(batch_plan_path),
            "batch_count": len(plan["batches"]),
            "batch_max_files": 2,
            "batch_max_bytes": 100,
            "oversized_batch_count": 0,
            "restore_sample_max_object_bytes": 100,
            "restore_sample_files": len(sample),
            "restore_sample_bytes": sum(item.size_bytes for item in sample),
            "sentinel": sentinel,
        }
    )
    contract = base.model_copy(update={"migration": migration})
    data_root = tmp_path / "data"
    data_root.mkdir()
    g01_root = data_root / "operations/gcs_migration/g01-complete"
    _write_g01_evidence(g01_root, contract)
    content = {
        item.destination_locator: (
            b"" if item.size_bytes == 0 else _content_for_entry(item, entries)
        )
        for item in entries
    }
    source = FakeSource(entries)
    transport = FakeFullTransport(
        entries, sentinel_entries, content, fail_after_write=fail_after_write
    )
    return (
        contract,
        catalog_path,
        batch_plan_path,
        g01_root,
        data_root,
        entries,
        source,
        transport,
    )


def _content_for_entry(entry: CatalogEntry, entries: Sequence[CatalogEntry]) -> bytes:
    known = {
        entries[0].destination_locator: b"meta",
        entries[1].destination_locator: b"monthly",
        entries[2].destination_locator: b"queue",
        entries[3].destination_locator: b"ccjc",
    }
    return known[entry.destination_locator]


def _write_g01_evidence(root: Path, contract: GcpContract) -> None:
    stages = []
    for stage_id in ("preflight", "dry_run", "copy", "verify", "idempotency"):
        artifact_path = root / f"{stage_id}.json"
        atomic_write_json(artifact_path, {"status": "completed", "stage": stage_id})
        stages.append(
            {
                "id": stage_id,
                "status": "completed",
                "artifact": {
                    "path": str(artifact_path),
                    "bytes": artifact_path.stat().st_size,
                    "sha256": sha256_file(artifact_path),
                },
            }
        )
    atomic_write_json(
        root / "operation.json",
        {
            "operation_id": "g01-complete",
            "configuration": {
                "project_id": contract.project_id,
                "bucket": contract.data.bucket,
                "raw_prefix": contract.data.raw_prefix,
                "source": {"root_folder_id": contract.migration.source_raw_folder_id},
                "sentinel_files": len(contract.migration.sentinel),
                "sentinel_bytes": sum(item.size_bytes for item in contract.migration.sentinel),
            },
            "stages": stages,
        },
    )


def _run_full(
    fixture,
    *,
    operation_id: str,
    through: str,
    approved_plan_sha256: str | None = None,
    approved_max_cost_usd: str | None = None,
    batch_max_files: int | None = None,
    batch_max_bytes: int | None = None,
    restore_sample_max_bytes: int | None = None,
    include_historical_batch_plan: bool = True,
) -> dict[str, Any]:
    contract, catalog, batches, g01_root, data_root, _entries, source, transport = fixture
    return execute_gcs_full(
        source=source,
        transport=transport,
        contract=contract,
        source_catalog_path=catalog,
        source_batch_plan_path=batches if include_historical_batch_plan else None,
        g01_operation_root=g01_root,
        data_root=data_root,
        operation_id=operation_id,
        implementation_revision="test-revision",
        confirmed_project_id=contract.project_id,
        confirmed_bucket=contract.data.bucket,
        confirmed_source_folder_id=RAW_FOLDER_ID,
        through=through,
        approved_plan_sha256=approved_plan_sha256,
        approved_max_cost_usd=approved_max_cost_usd,
        batch_max_files=batch_max_files or contract.migration.batch_max_files,
        batch_max_bytes=batch_max_bytes or contract.migration.batch_max_bytes,
        restore_sample_max_bytes=restore_sample_max_bytes,
    )


def test_full_pipeline_copies_verifies_restores_and_seals(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    dry_run_payload = _run_full(fixture, operation_id="g02-ok", through="dry-run")
    dry_run = json.loads(Path(dry_run_payload["artifact_path"]).read_text(encoding="utf-8"))

    payload = _run_full(
        fixture,
        operation_id="g02-ok",
        through="restore",
        approved_plan_sha256=dry_run["approval_sha256"],
        approved_max_cost_usd="1.00",
    )

    contract, _catalog, _batches, _g01, data_root, entries, _source, transport = fixture
    assert payload["status"] == "completed"
    assert len(transport.destination_metadata()) == len(entries)
    assert sum(not dry for dry, _items in transport.copy_calls) == len(
        build_full_execution_plan(
            entries,
            entries[:3],
            batch_max_files=contract.migration.batch_max_files,
            batch_max_bytes=contract.migration.batch_max_bytes,
        )["batches"]
    )
    assert transport.copy_calls[-1][0] is True
    restore = json.loads(
        (data_root / "operations/gcs_migration/g02-ok/restore.json").read_text(encoding="utf-8")
    )
    assert restore["files"] == contract.migration.restore_sample_files
    assert restore["bytes"] == contract.migration.restore_sample_bytes
    assert "largest_within_limit" in restore["selection"]["strategy"]
    assert restore["temporary_directory_removed"] is True
    migration_complete = Path(payload["artifact_path"])
    assert migration_complete.is_file()
    remote_locator = "manifests/migrations/g02/g02-ok/migration-complete.json"
    assert transport.remote_bytes[remote_locator] == migration_complete.read_bytes()
    completion = json.loads(migration_complete.read_text(encoding="utf-8"))
    assert completion["approval"]["plan_sha256"] == dry_run["approval_sha256"]
    assert completion["approval"]["max_cost_usd"] == "1.00"
    assert completion["operational_parameters"]["batches"] >= 1
    manifest_text = Path(payload["manifest_path"]).read_text(encoding="utf-8")
    assert TOKEN not in manifest_text
    assert "operator@example.invalid" not in manifest_text

    copy_calls = list(transport.copy_calls)
    repeated = _run_full(
        fixture,
        operation_id="g02-ok",
        through="restore",
        approved_plan_sha256=dry_run["approval_sha256"],
        approved_max_cost_usd="1.00",
    )
    assert repeated["status"] == "completed"
    assert transport.copy_calls == copy_calls


def test_copy_requires_exact_human_approval_and_cost_ceiling(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    dry = _run_full(fixture, operation_id="approval", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]

    with pytest.raises(GcsFullMigrationError, match="não foi aprovado"):
        _run_full(
            fixture,
            operation_id="approval",
            through="copy",
            approved_plan_sha256="0" * 64,
            approved_max_cost_usd="1.00",
        )
    with pytest.raises(GcsFullMigrationError, match="teto de custo"):
        _run_full(
            fixture,
            operation_id="approval",
            through="copy",
            approved_plan_sha256=approval,
            approved_max_cost_usd="NaN",
        )
    assert all(dry_run for dry_run, _locators in fixture[-1].copy_calls)


def test_pipeline_accepts_adjusted_batches_restore_limit_and_cost_ceiling(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    options = {
        "batch_max_files": 1,
        "batch_max_bytes": 50,
        "restore_sample_max_bytes": 50,
        "include_historical_batch_plan": False,
    }
    dry = _run_full(
        fixture,
        operation_id="flexible",
        through="dry-run",
        **options,
    )
    operation_root = Path(dry["artifact_path"]).parent
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]

    result = _run_full(
        fixture,
        operation_id="flexible",
        through="restore",
        approved_plan_sha256=approval,
        approved_max_cost_usd="2.00",
        **options,
    )

    execution_plan = json.loads(
        (operation_root / "copy-execution-plan.json").read_text(encoding="utf-8")
    )
    restore = json.loads((operation_root / "restore.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert len(execution_plan["batches"]) == 3
    assert restore["files"] >= 5
    assert restore["bytes"] <= sum(item.size_bytes for item in fixture[5])


def test_preflight_blocks_incomplete_g01_and_unexpected_destination(tmp_path: Path) -> None:
    incomplete = _fixture(tmp_path / "incomplete")
    manifest_path = incomplete[3] / "operation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    next(item for item in manifest["stages"] if item["id"] == "copy")["status"] = "pending"
    atomic_write_json(manifest_path, manifest)

    with pytest.raises(GcsFullMigrationError, match="gate G01 incompleto"):
        _run_full(incomplete, operation_id="blocked-g01", through="preflight")

    unexpected = _fixture(tmp_path / "unexpected")
    extra = copy.copy(unexpected[-1].destination_metadata()[0])
    unexpected[-1].objects["data/raw/v1/unexpected.jsonl"] = GcsObjectMetadata(
        **{**extra.as_dict(), "locator": "data/raw/v1/unexpected.jsonl"}
    )

    with pytest.raises(GcsCopyConflict, match="destino GCS divergiu"):
        _run_full(unexpected, operation_id="blocked-extra", through="preflight")


@pytest.mark.parametrize("mode", ["wrong", "missing", "unexpected", "removal", "error"])
def test_mixed_dry_run_rejects_wrong_or_unexpected_markers(tmp_path: Path, mode: str) -> None:
    fixture = _fixture(tmp_path)
    entries = fixture[5]
    combined = tmp_path / "combined.txt"
    exact = {item.source_locator for item in entries[:3]}
    lines = [
        f"{'=' if item.source_locator in exact else '+'} {item.source_locator}\n"
        for item in entries
    ]
    if mode == "wrong":
        lines[0] = f"+ {entries[0].source_locator}\n"
    elif mode == "missing":
        lines.pop()
    elif mode == "unexpected":
        lines.append("+ unexpected.jsonl\n")
    elif mode == "removal":
        lines[0] = f"- {entries[0].source_locator}\n"
    else:
        lines[0] = f"! {entries[0].source_locator}\n"
    combined.write_text("".join(lines), encoding="utf-8")

    with pytest.raises(GcsFullMigrationError, match="dry-run integral divergiu"):
        validate_mixed_combined(entries, combined, exact_locators=exact)


def test_ambiguous_batch_is_reconciled_without_duplicate_write(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, fail_after_write=True)
    dry = _run_full(fixture, operation_id="ambiguous", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]

    payload = _run_full(
        fixture,
        operation_id="ambiguous",
        through="copy",
        approved_plan_sha256=approval,
        approved_max_cost_usd="1.00",
    )

    assert payload["status"] == "completed"
    progress = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    assert progress["completed_files"] == 3
    written = [
        locator
        for dry_run, locators in fixture[-1].copy_calls
        if not dry_run
        for locator in locators
    ]
    assert len(written) == len(set(written)) == 3


def test_partial_copy_resume_reuses_verified_object(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    dry = _run_full(fixture, operation_id="partial", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]
    pending = fixture[5][3]
    fixture[-1].objects[pending.destination_locator] = fixture[-1]._metadata(
        pending, generation="resume-1"
    )

    payload = _run_full(
        fixture,
        operation_id="partial",
        through="copy",
        approved_plan_sha256=approval,
        approved_max_cost_usd="1.00",
    )

    written = [
        locator
        for dry_run, locators in fixture[-1].copy_calls
        if not dry_run
        for locator in locators
    ]
    assert payload["status"] == "completed"
    assert pending.source_locator not in written


def test_process_interruption_after_write_is_reconciled_conservatively(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    dry = _run_full(fixture, operation_id="interrupted", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]
    operation_root = Path(dry["artifact_path"]).parent
    manifest_path = operation_root / "operation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    copy_stage = next(item for item in manifest["stages"] if item["id"] == "copy")
    copy_stage.update(
        {
            "status": "running",
            "attempts": 1,
            "started_at": "2026-08-11T00:00:00Z",
            "attempt_history": [
                {
                    "number": 1,
                    "status": "running",
                    "started_at": "2026-08-11T00:00:00Z",
                    "completed_at": None,
                    "error": None,
                    "remote_result_ambiguous": False,
                }
            ],
        }
    )
    atomic_write_json(manifest_path, manifest)
    for entry in fixture[5][3:]:
        fixture[-1].objects[entry.destination_locator] = fixture[-1]._metadata(
            entry, generation=f"interrupted-{entry.source_locator}"
        )

    payload = _run_full(
        fixture,
        operation_id="interrupted",
        through="copy",
        approved_plan_sha256=approval,
        approved_max_cost_usd="1.00",
    )

    progress = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    assert progress["objects_written"] == 3
    assert all(
        result["status"] == "reconciled_after_interruption"
        for result in progress["results"].values()
    )
    assert all(dry_run for dry_run, _locators in fixture[-1].copy_calls)


def test_changed_linked_preflight_artifact_is_rebuilt(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    payload = _run_full(fixture, operation_id="resume", through="preflight")
    source = fixture[-2]
    execution_plan = Path(payload["artifact_path"]).parent / "copy-execution-plan.json"
    execution_plan.write_text("changed", encoding="utf-8")

    second = _run_full(fixture, operation_id="resume", through="preflight")

    assert second["status"] == "completed"
    assert source.list_calls == 2


def test_cutover_requires_digest_then_is_resumable_and_create_only(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    dry = _run_full(fixture, operation_id="cutover", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]
    full = _run_full(
        fixture,
        operation_id="cutover",
        through="restore",
        approved_plan_sha256=approval,
        approved_max_cost_usd="1.00",
    )
    contract, _catalog, _batches, _g01, _data, _entries, _source, store = fixture
    operation_root = Path(full["artifact_path"]).parent
    config_path = tmp_path / "gcp.toml"
    config_path.write_bytes(CONFIG_PATH.read_bytes())

    with pytest.raises(GcsFullMigrationError, match="aprovação humana"):
        execute_gcs_cutover(
            store=store,
            contract=contract,
            gcp_config_path=config_path,
            operation_root=operation_root,
            confirmed_project_id=contract.project_id,
            confirmed_bucket=contract.data.bucket,
            confirmed_source_folder_id=RAW_FOLDER_ID,
            approved_migration_manifest_sha256="0" * 64,
            confirmed_authoritative_raw="gcs",
        )

    migration_sha = sha256_file(operation_root / "migration-complete.json")
    first = execute_gcs_cutover(
        store=store,
        contract=contract,
        gcp_config_path=config_path,
        operation_root=operation_root,
        confirmed_project_id=contract.project_id,
        confirmed_bucket=contract.data.bucket,
        confirmed_source_folder_id=RAW_FOLDER_ID,
        approved_migration_manifest_sha256=migration_sha,
        confirmed_authoritative_raw="gcs",
    )
    updated_contract = load_gcp_contract(config_path)
    second = execute_gcs_cutover(
        store=store,
        contract=updated_contract,
        gcp_config_path=config_path,
        operation_root=operation_root,
        confirmed_project_id=updated_contract.project_id,
        confirmed_bucket=updated_contract.data.bucket,
        confirmed_source_folder_id=RAW_FOLDER_ID,
        approved_migration_manifest_sha256=migration_sha,
        confirmed_authoritative_raw="gcs",
    )

    assert first["status"] == second["status"] == "completed"
    assert updated_contract.migration.authoritative_raw == "gcs"
    assert store.read_bytes("manifests/migrations/g02/cutover/cutover.json") is not None


def test_cutover_conflict_preserves_drive_authority(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    dry = _run_full(fixture, operation_id="cutover-conflict", through="dry-run")
    approval = json.loads(Path(dry["artifact_path"]).read_text(encoding="utf-8"))["approval_sha256"]
    full = _run_full(
        fixture,
        operation_id="cutover-conflict",
        through="restore",
        approved_plan_sha256=approval,
        approved_max_cost_usd="1.00",
    )
    contract, _catalog, _batches, _g01, _data, _entries, _source, store = fixture
    operation_root = Path(full["artifact_path"]).parent
    config_path = tmp_path / "gcp.toml"
    config_path.write_bytes(CONFIG_PATH.read_bytes())
    locator = "manifests/migrations/g02/cutover-conflict/cutover.json"
    store.remote_bytes[locator] = b"conflict\n"

    with pytest.raises(GcsCopyConflict, match="manifest remoto existente diverge"):
        execute_gcs_cutover(
            store=store,
            contract=contract,
            gcp_config_path=config_path,
            operation_root=operation_root,
            confirmed_project_id=contract.project_id,
            confirmed_bucket=contract.data.bucket,
            confirmed_source_folder_id=RAW_FOLDER_ID,
            approved_migration_manifest_sha256=sha256_file(
                operation_root / "migration-complete.json"
            ),
            confirmed_authoritative_raw="gcs",
        )

    assert load_gcp_contract(config_path).migration.authoritative_raw == "drive"


def test_cutover_rejects_missing_operation(tmp_path: Path) -> None:
    contract = load_gcp_contract(CONFIG_PATH)
    fixture = _fixture(tmp_path / "store")

    with pytest.raises(GcsFullMigrationError, match="operação integral G02 ausente"):
        execute_gcs_cutover(
            store=fixture[-1],
            contract=contract,
            gcp_config_path=CONFIG_PATH,
            operation_root=tmp_path / "missing",
            confirmed_project_id=contract.project_id,
            confirmed_bucket=contract.data.bucket,
            confirmed_source_folder_id=RAW_FOLDER_ID,
            approved_migration_manifest_sha256="a" * 64,
            confirmed_authoritative_raw="gcs",
        )


def test_gcs_json_api_declares_project_and_create_only_precondition() -> None:
    requests: list[httpx.Request] = []
    md5_base64 = base64.b64encode(hashlib.md5(b"x", usedforsecurity=False).digest()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        metadata = {
            "name": "data/raw/v1/item.jsonl",
            "size": "1",
            "md5Hash": md5_base64,
            "crc32c": "AAAAAA==",
            "generation": "1",
            "metageneration": "1",
            "storageClass": "STANDARD",
        }
        if request.method == "GET" and request.url.params.get("prefix"):
            return httpx.Response(200, json={"items": [metadata]})
        return httpx.Response(200, json={**metadata, "name": "manifests/test.json"})

    api = GcsJsonApi(
        project_id="falando-nela-pedblan",
        bucket="falando-nela-pedblan-data",
        access_token=lambda: TOKEN,
        http_transport=httpx.MockTransport(handler),
    )

    objects = api.list_objects(prefix="data/raw/v1/")
    api.publish_bytes_create_only("manifests/test.json", b"{}\n")

    assert objects[0].md5 == hashlib.md5(b"x", usedforsecurity=False).hexdigest()
    assert api.descriptor()["project_id"] == "falando-nela-pedblan"
    assert all("userProject" not in request.url.params for request in requests)
    assert all("x-goog-user-project" not in request.headers for request in requests)
    post = next(request for request in requests if request.method == "POST")
    assert post.url.params["ifGenerationMatch"] == "0"
    assert "/b/falando-nela-pedblan-data/o" in post.url.path
    assert TOKEN not in json.dumps(api.descriptor())


def test_real_catalog_normalizes_zeros_and_defaults_reproduce_historical_plan() -> None:
    if not CATALOG_PATH.exists() or not BATCH_PLAN_PATH.exists():
        pytest.skip("evidência operacional ignorada pelo Git não está presente")
    contract = load_gcp_contract(CONFIG_PATH)
    catalog = load_source_catalog(CATALOG_PATH, contract)
    sentinel = select_sentinel(catalog, contract.migration.sentinel)
    plan = build_full_execution_plan(
        catalog,
        sentinel,
        batch_max_files=contract.migration.batch_max_files,
        batch_max_bytes=contract.migration.batch_max_bytes,
    )
    frozen = json.loads(BATCH_PLAN_PATH.read_text(encoding="utf-8"))
    sample = select_restore_sample(
        catalog,
        sentinel,
        approved_empty_locators=contract.migration.approved_empty_source_locators,
        max_object_bytes=contract.migration.restore_sample_max_object_bytes,
    )
    zeros = [item for item in catalog if item.size_bytes == 0]

    assert len(zeros) == 2
    assert all(item.provider_hashes == {"md5": EMPTY_MD5, "sha256": EMPTY_SHA256} for item in zeros)
    assert plan["batches"] == frozen["batches"]
    assert len(plan["batches"]) == 38
    selected = {item.source_locator for item in sample}
    required = {
        *(item.source_locator for item in sentinel),
        *contract.migration.approved_empty_source_locators,
    }
    assert required <= selected
    assert max(item.size_bytes for item in sample) <= (
        contract.migration.restore_sample_max_object_bytes
    )
