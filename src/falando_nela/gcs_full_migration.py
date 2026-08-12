from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from falando_nela.gcp_config import GcpContract, load_gcp_contract
from falando_nela.gcs_migration import (
    CatalogEntry,
    GcsMigrationError,
    InventorySource,
    RcloneGcsTransport,
    load_source_catalog,
    reconcile_source_catalog,
    select_sentinel,
    validate_combined,
)
from falando_nela.operations import RecoverableOperation, artifact_metadata, fingerprint
from falando_nela.raw import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)

ESTIMATED_G02_COST_USD = Decimal("0.300000")
COPY_THROUGH = ("preflight", "dry-run", "copy", "verify", "idempotency", "restore")
G01_REQUIRED_STAGES = ("preflight", "dry_run", "copy", "verify", "idempotency")
FULL_STAGES = (
    ("preflight", ()),
    ("dry_run", ("preflight",)),
    ("copy", ("dry_run",)),
    ("verify", ("copy",)),
    ("idempotency", ("verify",)),
    ("restore", ("idempotency",)),
    ("seal", ("restore",)),
)


class GcsFullMigrationError(GcsMigrationError):
    """A migração integral G02 divergiu do contrato aprovado."""


class GcsCopyConflict(GcsFullMigrationError):
    """O destino existente impede uma cópia imutável."""


class GcsCopyAmbiguous(GcsFullMigrationError):
    """Uma escrita remota não pôde ser reconciliada."""


@dataclass(frozen=True)
class GcsObjectMetadata:
    locator: str
    size_bytes: int
    md5: str
    crc32c: str
    generation: str
    metageneration: str
    storage_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "size_bytes": self.size_bytes,
            "md5": self.md5,
            "crc32c": self.crc32c,
            "generation": self.generation,
            "metageneration": self.metageneration,
            "storage_class": self.storage_class,
        }


class FullGcsTransport(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def destination_metadata(self) -> list[GcsObjectMetadata]: ...

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]: ...

    def restore_object(self, locator: str, destination: Path, *, generation: str) -> None: ...

    def publish_bytes_create_only(self, locator: str, content: bytes) -> dict[str, Any]: ...

    def read_bytes(self, locator: str) -> bytes | None: ...


class ManifestStore(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def publish_bytes_create_only(self, locator: str, content: bytes) -> dict[str, Any]: ...

    def read_bytes(self, locator: str) -> bytes | None: ...


class GcsJsonApi:
    """Acesso mínimo ao GCS com token efêmero e projeto declarado por chamada."""

    def __init__(
        self,
        *,
        project_id: str,
        bucket: str,
        access_token: Callable[[], str],
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not project_id or not bucket:
            raise GcsFullMigrationError("projeto e bucket GCS são obrigatórios")
        self.project_id = project_id
        self.bucket = bucket
        self.access_token = access_token
        self.http_transport = http_transport

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "gcs_json_api",
            "project_id": self.project_id,
            "bucket": self.bucket,
            "authentication": "short_lived_impersonated_token",
        }

    def list_objects(self, *, prefix: str) -> list[GcsObjectMetadata]:
        page_token: str | None = None
        result: list[GcsObjectMetadata] = []
        while True:
            parameters = {
                "prefix": prefix,
                "projection": "noAcl",
                "fields": (
                    "nextPageToken,items(name,size,md5Hash,crc32c,generation,"
                    "metageneration,storageClass)"
                ),
            }
            if page_token is not None:
                parameters["pageToken"] = page_token
            response = self._request(
                "GET",
                f"https://storage.googleapis.com/storage/v1/b/{quote(self.bucket, safe='')}/o",
                params=parameters,
            )
            self._require_success(response, "listagem de objetos GCS")
            try:
                payload = response.json()
                items = payload.get("items", [])
            except (ValueError, AttributeError) as exc:
                raise GcsFullMigrationError("listagem GCS retornou JSON inválido") from exc
            if not isinstance(items, list):
                raise GcsFullMigrationError("listagem GCS retornou items inválidos")
            result.extend(_metadata_from_api(item) for item in items)
            page_token = payload.get("nextPageToken")
            if page_token is None:
                break
            if not isinstance(page_token, str) or not page_token:
                raise GcsFullMigrationError("paginação GCS retornou token inválido")
        return sorted(result, key=lambda item: item.locator)

    def read_bytes(self, locator: str) -> bytes | None:
        response = self._request(
            "GET",
            self._download_url(locator),
            params={"alt": "media"},
        )
        if response.status_code == 404:
            return None
        self._require_success(response, "leitura de objeto GCS")
        return response.content

    def download(self, locator: str, destination: Path, *, generation: str) -> None:
        response = self._request(
            "GET",
            self._download_url(locator),
            params={
                "alt": "media",
                "generation": generation,
            },
        )
        self._require_success(response, "restauração de objeto GCS")
        atomic_write_bytes(destination, response.content)

    def publish_bytes_create_only(
        self,
        locator: str,
        content: bytes,
        *,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        try:
            response = self._request(
                "POST",
                (
                    "https://storage.googleapis.com/upload/storage/v1/b/"
                    f"{quote(self.bucket, safe='')}/o"
                ),
                params={
                    "uploadType": "media",
                    "name": locator,
                    "ifGenerationMatch": "0",
                },
                content=content,
                extra_headers={"Content-Type": content_type},
            )
        except httpx.HTTPError as exc:
            return self._reconcile_create(locator, content, cause=exc)
        if response.status_code in {200, 201}:
            try:
                metadata = _metadata_from_api(response.json())
            except (ValueError, GcsFullMigrationError):
                return self._reconcile_create(locator, content)
            return {"status": "created", **metadata.as_dict()}
        if response.status_code == 412 or response.status_code >= 500:
            return self._reconcile_create(locator, content)
        raise GcsFullMigrationError(
            f"publicação create-only no GCS falhou (HTTP {response.status_code})"
        )

    def _reconcile_create(
        self,
        locator: str,
        content: bytes,
        *,
        cause: Exception | None = None,
    ) -> dict[str, Any]:
        try:
            existing = self.read_bytes(locator)
        except GcsFullMigrationError as exc:
            raise GcsCopyAmbiguous("resultado da publicação create-only permaneceu ambíguo") from (
                cause or exc
            )
        if existing is None:
            raise GcsCopyAmbiguous("publicação create-only falhou e o objeto não existe") from cause
        if existing != content:
            raise GcsCopyConflict(f"manifest remoto existente diverge: {locator}")
        metadata = self._object_metadata(locator)
        return {"status": "reused_verified", **metadata.as_dict()}

    def _object_metadata(self, locator: str) -> GcsObjectMetadata:
        response = self._request(
            "GET",
            self._metadata_url(locator),
            params={"projection": "noAcl"},
        )
        self._require_success(response, "readback de metadata GCS")
        try:
            return _metadata_from_api(response.json())
        except ValueError as exc:
            raise GcsFullMigrationError("metadata GCS retornou JSON inválido") from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str],
        content: bytes | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        token = self.access_token()
        headers = {"Authorization": f"Bearer {token}"}
        headers.update(extra_headers or {})
        arguments: dict[str, Any] = {"timeout": 120.0, "headers": headers}
        if self.http_transport is not None:
            arguments["transport"] = self.http_transport
        with httpx.Client(**arguments) as client:
            return client.request(method, url, params=params, content=content)

    @staticmethod
    def _require_success(response: httpx.Response, label: str) -> None:
        if not 200 <= response.status_code < 300:
            raise GcsFullMigrationError(f"{label} falhou (HTTP {response.status_code})")

    def _metadata_url(self, locator: str) -> str:
        return (
            "https://storage.googleapis.com/storage/v1/b/"
            f"{quote(self.bucket, safe='')}/o/{quote(locator, safe='')}"
        )

    def _download_url(self, locator: str) -> str:
        return (
            "https://storage.googleapis.com/download/storage/v1/b/"
            f"{quote(self.bucket, safe='')}/o/{quote(locator, safe='')}"
        )


class RcloneG02Transport:
    def __init__(self, *, copy_transport: RcloneGcsTransport, object_store: GcsJsonApi) -> None:
        copy_descriptor = copy_transport.descriptor()
        store_descriptor = object_store.descriptor()
        if copy_descriptor.get("project_id") != store_descriptor.get(
            "project_id"
        ) or copy_descriptor.get("bucket") != store_descriptor.get("bucket"):
            raise GcsFullMigrationError("transportes G02 apontam para destinos diferentes")
        self.copy_transport = copy_transport
        self.object_store = object_store

    def descriptor(self) -> dict[str, str]:
        return {**self.copy_transport.descriptor(), "metadata_api": "gcs_json_v1"}

    def destination_metadata(self) -> list[GcsObjectMetadata]:
        prefix = f"{self.copy_transport.raw_prefix}/"
        return self.object_store.list_objects(prefix=prefix)

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]:
        return self.copy_transport.copy_entries(
            entries,
            files_from_path=files_from_path,
            combined_path=combined_path,
            dry_run=dry_run,
        )

    def restore_object(self, locator: str, destination: Path, *, generation: str) -> None:
        self.object_store.download(locator, destination, generation=generation)

    def publish_bytes_create_only(self, locator: str, content: bytes) -> dict[str, Any]:
        return self.object_store.publish_bytes_create_only(locator, content)

    def read_bytes(self, locator: str) -> bytes | None:
        return self.object_store.read_bytes(locator)


def build_full_execution_plan(
    entries: Sequence[CatalogEntry],
    sentinel: Sequence[CatalogEntry],
    *,
    batch_max_files: int,
    batch_max_bytes: int,
) -> dict[str, Any]:
    if batch_max_files <= 0 or batch_max_bytes <= 0:
        raise GcsFullMigrationError("limites de lote devem ser positivos")
    sentinel_locators = {item.destination_locator for item in sentinel}
    remaining = sorted(
        (item for item in entries if item.destination_locator not in sentinel_locators),
        key=lambda item: item.destination_locator,
    )
    batches: list[dict[str, Any]] = []
    current: list[CatalogEntry] = []
    current_bytes = 0

    def flush() -> None:
        nonlocal current, current_bytes
        if not current:
            return
        batches.append(
            {
                "batch_id": f"batch-{len(batches) + 1:04d}",
                "files": len(current),
                "bytes": current_bytes,
                "destination_locators": [item.destination_locator for item in current],
            }
        )
        current = []
        current_bytes = 0

    for entry in remaining:
        if current and (
            len(current) >= batch_max_files or current_bytes + entry.size_bytes > batch_max_bytes
        ):
            flush()
        current.append(entry)
        current_bytes += entry.size_bytes
        if len(current) >= batch_max_files or current_bytes >= batch_max_bytes:
            flush()
    flush()
    return {
        "schema_version": 1,
        "files": len(entries),
        "bytes": sum(item.size_bytes for item in entries),
        "sentinel": {
            "files": len(sentinel),
            "bytes": sum(item.size_bytes for item in sentinel),
            "destination_locators": [
                item.destination_locator
                for item in sorted(sentinel, key=lambda item: item.category)
            ],
        },
        "batch_max_files": batch_max_files,
        "batch_max_bytes": batch_max_bytes,
        "batches": batches,
    }


def select_restore_sample(
    entries: Sequence[CatalogEntry],
    sentinel: Sequence[CatalogEntry],
    *,
    approved_empty_locators: Sequence[str],
    max_object_bytes: int,
) -> list[CatalogEntry]:
    if max_object_bytes <= 0:
        raise GcsFullMigrationError("limite da amostra de restauração deve ser positivo")
    selected = {item.source_locator: item for item in sentinel}
    by_source_locator = {item.source_locator: item for item in entries}
    for locator in approved_empty_locators:
        try:
            selected[locator] = by_source_locator[locator]
        except KeyError as exc:
            raise GcsFullMigrationError(f"objeto vazio aprovado ausente: {locator}") from exc
    groups: dict[tuple[str, str], list[CatalogEntry]] = {}
    eligible: list[CatalogEntry] = []
    for entry in entries:
        source, dataset = _source_dataset(entry)
        if 0 < entry.size_bytes <= max_object_bytes and re.fullmatch(
            r"[0-9a-f]{64}", entry.provider_hashes.get("sha256", "")
        ):
            eligible.append(entry)
            groups.setdefault((source, dataset), []).append(entry)
    if not eligible:
        raise GcsFullMigrationError("baseline não contém objeto restaurável dentro do limite")
    for key in sorted(groups):
        candidate = min(groups[key], key=lambda item: item.destination_locator)
        selected[candidate.source_locator] = candidate
    smallest = min(eligible, key=lambda item: (item.size_bytes, item.destination_locator))
    largest = max(eligible, key=lambda item: (item.size_bytes, item.destination_locator))
    selected[smallest.source_locator] = smallest
    selected[largest.source_locator] = largest
    return sorted(selected.values(), key=lambda item: item.destination_locator)


def execute_gcs_full(
    *,
    source: InventorySource,
    transport: FullGcsTransport,
    contract: GcpContract,
    source_catalog_path: Path,
    source_batch_plan_path: Path | None,
    g01_operation_root: Path,
    data_root: Path,
    operation_id: str,
    implementation_revision: str,
    confirmed_project_id: str,
    confirmed_bucket: str,
    confirmed_source_folder_id: str,
    through: str,
    approved_plan_sha256: str | None = None,
    approved_max_cost_usd: str | None = None,
    batch_max_files: int = 100,
    batch_max_bytes: int = 512 * 1024 * 1024,
    restore_sample_max_bytes: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _validate_operation_id(operation_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:+/-]{0,199}", implementation_revision):
        raise GcsFullMigrationError("revisão da implementação G02 é inválida")
    if through not in COPY_THROUGH:
        raise GcsFullMigrationError(f"through inválido: {through}")
    contract.confirm_targets(
        project_id=confirmed_project_id,
        bucket=confirmed_bucket,
        source_raw_folder_id=confirmed_source_folder_id,
    )
    if contract.migration.authoritative_raw != "drive":
        raise GcsFullMigrationError("G02 já foi cortada ou a autoridade raw não é Drive")
    if batch_max_files <= 0 or batch_max_bytes <= 0:
        raise GcsFullMigrationError("limites de lote devem ser positivos")
    effective_restore_max_bytes = (
        contract.migration.restore_sample_max_object_bytes
        if restore_sample_max_bytes is None
        else restore_sample_max_bytes
    )
    if effective_restore_max_bytes <= 0:
        raise GcsFullMigrationError("limite da amostra de restauração deve ser positivo")
    descriptor = source.descriptor()
    if descriptor.get("scope") != "drive.readonly":
        raise GcsFullMigrationError("origem G02 deve usar scope drive.readonly")
    if descriptor.get("root_folder_id") != contract.migration.source_raw_folder_id:
        raise GcsFullMigrationError("origem G02 não está fixada na pasta raw aprovada")
    transport_descriptor = transport.descriptor()
    _validate_transport_descriptor(transport_descriptor, contract)
    if (
        transport_descriptor.get("raw_prefix") != contract.data.raw_prefix
        or transport_descriptor.get("region") != contract.region
    ):
        raise GcsFullMigrationError("transport GCS diverge do prefixo ou região G02")

    resolved_root = data_root.expanduser().resolve(strict=True)
    resolved_catalog = source_catalog_path.expanduser().resolve(strict=True)
    resolved_batch_plan = (
        source_batch_plan_path.expanduser().resolve(strict=True)
        if source_batch_plan_path is not None
        else None
    )
    resolved_g01_root = g01_operation_root.expanduser().resolve(strict=True)
    if not resolved_g01_root.is_relative_to(resolved_root):
        raise GcsFullMigrationError("operação G01 deve estar sob a raiz de dados")
    catalog = load_source_catalog(resolved_catalog, contract)
    sentinel = select_sentinel(catalog, contract.migration.sentinel)
    generated_plan = build_full_execution_plan(
        catalog,
        sentinel,
        batch_max_files=batch_max_files,
        batch_max_bytes=batch_max_bytes,
    )
    if resolved_batch_plan is not None:
        _validate_source_batch_plan(resolved_batch_plan, catalog, contract)
    _validate_restore_sample(
        catalog,
        sentinel,
        contract,
        max_object_bytes=effective_restore_max_bytes,
    )
    g01_evidence = validate_g01_completion(resolved_g01_root, contract)

    operation_root = resolved_root / "operations" / "gcs_migration" / operation_id
    manifest_path = operation_root / "operation.json"
    paths = _full_paths(operation_root)
    public_configuration = {
        "project_id": contract.project_id,
        "region": contract.region,
        "bucket": contract.data.bucket,
        "raw_prefix": contract.data.raw_prefix,
        "implementation_revision": implementation_revision,
        "source": descriptor,
        "transport": transport_descriptor,
        "source_catalog": str(resolved_catalog),
        "source_catalog_file_sha256": sha256_file(resolved_catalog),
        "source_catalog_logical_sha256": contract.migration.source_catalog_sha256,
        "source_batch_plan": str(resolved_batch_plan) if resolved_batch_plan else None,
        "source_batch_plan_sha256": (
            sha256_file(resolved_batch_plan) if resolved_batch_plan else None
        ),
        "g01_operation_root": str(resolved_g01_root),
        "g01_evidence_sha256": g01_evidence["manifest_sha256"],
        "batch_max_files": batch_max_files,
        "batch_max_bytes": batch_max_bytes,
        "restore_sample_max_bytes": effective_restore_max_bytes,
        "through_contract": list(COPY_THROUGH),
        "estimated_cost_usd": format(ESTIMATED_G02_COST_USD, "f"),
    }
    operation = RecoverableOperation(
        manifest_path=manifest_path,
        operation_id=operation_id,
        contract_version=2,
        implementation_version="g02-gcs-full-v1",
        input_fingerprint=fingerprint(
            {
                "contract": contract.model_dump(mode="json"),
                "catalog_sha256": sha256_file(resolved_catalog),
                "batch_plan_sha256": (
                    sha256_file(resolved_batch_plan) if resolved_batch_plan else None
                ),
                "g01_manifest_sha256": g01_evidence["manifest_sha256"],
            }
        ),
        config_fingerprint=fingerprint(public_configuration),
        stages=FULL_STAGES,
        configuration=public_configuration,
    )
    _recover_full_interrupted(operation)
    _invalidate_broken_preflight_links(operation, paths)

    if operation.begin("preflight"):
        _emit(progress_callback, operation_id, "preflight", "running")
        try:
            observed_source = source.list_objects()
            source_summary = reconcile_source_catalog(catalog, observed_source)
            _write_source_inventory(observed_source, paths["source_inventory"])
            metadata = transport.destination_metadata()
            destination = _verify_destination_metadata(
                sentinel,
                metadata,
                exact_locators={item.destination_locator for item in sentinel},
            )
            atomic_write_json(paths["execution_plan"], generated_plan)
            atomic_write_json(
                paths["preflight"],
                {
                    "status": "completed",
                    "source": source_summary,
                    "destination": _metadata_summary(destination),
                    "g01": g01_evidence,
                    "execution_plan_path": str(paths["execution_plan"]),
                    "execution_plan_sha256": sha256_file(paths["execution_plan"]),
                    "source_inventory_path": str(paths["source_inventory"]),
                    "source_inventory_sha256": sha256_file(paths["source_inventory"]),
                },
            )
            operation.complete("preflight", artifact=artifact_metadata(paths["preflight"]))
            _emit(progress_callback, operation_id, "preflight", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "preflight", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    if through == "preflight":
        return _full_payload(operation, through, paths["preflight"])
    _require_preflight_links(paths)

    if operation.begin("dry_run"):
        _emit(progress_callback, operation_id, "dry_run", "running")
        try:
            metadata = transport.destination_metadata()
            _verify_destination_metadata(
                sentinel,
                metadata,
                exact_locators={item.destination_locator for item in sentinel},
            )
            transport.copy_entries(
                catalog,
                files_from_path=paths["dry_run_locators"],
                combined_path=paths["dry_run_combined"],
                dry_run=True,
            )
            summary = validate_mixed_combined(
                catalog,
                paths["dry_run_combined"],
                exact_locators={item.source_locator for item in sentinel},
            )
            approval_payload = {
                "project_id": contract.project_id,
                "bucket": contract.data.bucket,
                "implementation_revision": implementation_revision,
                "source_folder_id": contract.migration.source_raw_folder_id,
                "catalog_sha256": sha256_file(resolved_catalog),
                "execution_plan_sha256": sha256_file(paths["execution_plan"]),
                "combined_sha256": sha256_file(paths["dry_run_combined"]),
                "files": len(catalog),
                "bytes": sum(item.size_bytes for item in catalog),
                "batches": len(generated_plan["batches"]),
                "batch_max_files": batch_max_files,
                "batch_max_bytes": batch_max_bytes,
                "restore_sample_max_bytes": effective_restore_max_bytes,
                "transport": transport_descriptor,
                "estimated_cost_usd": format(ESTIMATED_G02_COST_USD, "f"),
            }
            atomic_write_json(
                paths["dry_run"],
                {
                    "status": "completed",
                    **summary,
                    **approval_payload,
                    "combined_path": str(paths["dry_run_combined"]),
                    "approval_sha256": fingerprint(approval_payload).removeprefix("sha256:"),
                },
            )
            operation.complete("dry_run", artifact=artifact_metadata(paths["dry_run"]))
            _emit(progress_callback, operation_id, "dry_run", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail("dry_run", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise
    if through == "dry-run":
        return _full_payload(operation, through, paths["dry_run"])
    _require_copy_approval(
        paths["dry_run"],
        approved_plan_sha256=approved_plan_sha256,
        approved_max_cost_usd=approved_max_cost_usd,
        contract=contract,
    )

    if operation.begin("copy"):
        _emit(progress_callback, operation_id, "copy", "running")
        try:
            progress = _load_copy_progress(paths["copy_progress"])
            progress["approval"] = {
                "plan_sha256": approved_plan_sha256,
                "max_cost_usd": str(approved_max_cost_usd),
            }
            entry_by_destination = {item.destination_locator: item for item in catalog}
            attempt = int(operation.stage("copy")["attempts"])
            previous_result_ambiguous = any(
                item.get("remote_result_ambiguous") is True
                for item in operation.stage("copy")["attempt_history"][:-1]
            )
            for batch in generated_plan["batches"]:
                _copy_batch(
                    transport=transport,
                    catalog=catalog,
                    batch=batch,
                    entry_by_destination=entry_by_destination,
                    operation_root=operation_root,
                    progress=progress,
                    progress_path=paths["copy_progress"],
                    attempt=attempt,
                    previous_result_ambiguous=previous_result_ambiguous,
                    operation_id=operation_id,
                    callback=progress_callback,
                )
            progress["status"] = "completed"
            progress["completed_files"] = len(progress["results"])
            progress["completed_bytes"] = sum(
                entry_by_destination[locator].size_bytes for locator in progress["results"]
            )
            atomic_write_json(paths["copy_progress"], progress)
            operation.complete(
                "copy",
                artifact=artifact_metadata(paths["copy_progress"]),
                usage={
                    "objects_written": int(progress["objects_written"]),
                    "bytes_written": int(progress["bytes_written"]),
                },
                estimated_cost_usd=format(ESTIMATED_G02_COST_USD, "f"),
            )
            _emit(progress_callback, operation_id, "copy", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "copy",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
                remote_result_ambiguous=isinstance(exc, GcsCopyAmbiguous),
            )
            raise
    if through == "copy":
        return _full_payload(operation, through, paths["copy_progress"])

    if operation.begin("verify"):
        _emit(progress_callback, operation_id, "verify", "running")
        try:
            metadata = _verify_destination_metadata(catalog, transport.destination_metadata())
            reconcile_source_catalog(catalog, source.list_objects())
            _write_final_catalog(catalog, metadata, paths["final_catalog"])
            verification = {
                "status": "completed",
                **_metadata_summary(metadata),
                "source_status": "unchanged",
                "source_catalog_logical_sha256": contract.migration.source_catalog_sha256,
                "final_catalog_path": str(paths["final_catalog"]),
                "final_catalog_sha256": sha256_file(paths["final_catalog"]),
                "metadata_fingerprint": fingerprint([item.as_dict() for item in metadata]),
            }
            atomic_write_json(paths["verification"], verification)
            operation.complete("verify", artifact=artifact_metadata(paths["verification"]))
            _emit(progress_callback, operation_id, "verify", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail("verify", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise
    if through == "verify":
        return _full_payload(operation, through, paths["verification"])

    if operation.begin("idempotency"):
        _emit(progress_callback, operation_id, "idempotency", "running")
        try:
            before = _verify_destination_metadata(catalog, transport.destination_metadata())
            transport.copy_entries(
                catalog,
                files_from_path=paths["idempotency_locators"],
                combined_path=paths["idempotency_combined"],
                dry_run=True,
            )
            markers = validate_combined(catalog, paths["idempotency_combined"], expected_marker="=")
            after = _verify_destination_metadata(catalog, transport.destination_metadata())
            if before != after:
                raise GcsFullMigrationError("generations mudaram durante a prova idempotente")
            atomic_write_json(
                paths["idempotency"],
                {
                    "status": "completed",
                    **markers,
                    "objects_written": 0,
                    "bytes_written": 0,
                    "metadata_fingerprint": fingerprint([item.as_dict() for item in after]),
                    "combined_path": str(paths["idempotency_combined"]),
                    "combined_sha256": sha256_file(paths["idempotency_combined"]),
                },
            )
            operation.complete(
                "idempotency",
                artifact=artifact_metadata(paths["idempotency"]),
                usage={"objects_written": 0, "bytes_written": 0},
            )
            _emit(progress_callback, operation_id, "idempotency", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "idempotency", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    if through == "idempotency":
        return _full_payload(operation, through, paths["idempotency"])

    if operation.begin("restore"):
        _emit(progress_callback, operation_id, "restore", "running")
        restore_root = Path(tempfile.mkdtemp(prefix=f"falando-nela-g02-{operation_id}-"))
        try:
            metadata = _verify_destination_metadata(catalog, transport.destination_metadata())
            by_locator = {item.locator: item for item in metadata}
            sample = select_restore_sample(
                catalog,
                sentinel,
                approved_empty_locators=contract.migration.approved_empty_source_locators,
                max_object_bytes=effective_restore_max_bytes,
            )
            restored: list[dict[str, Any]] = []
            for entry in sample:
                current = by_locator[entry.destination_locator]
                relative = entry.destination_locator.removeprefix(f"{contract.data.raw_prefix}/")
                destination = restore_root / relative
                transport.restore_object(
                    entry.destination_locator,
                    destination,
                    generation=current.generation,
                )
                if (
                    destination.stat().st_size != entry.size_bytes
                    or sha256_file(destination) != entry.provider_hashes["sha256"]
                ):
                    raise GcsFullMigrationError(
                        f"objeto restaurado divergiu: {entry.destination_locator}"
                    )
                restored.append(
                    {
                        "locator": entry.destination_locator,
                        "generation": current.generation,
                        "size_bytes": entry.size_bytes,
                        "sha256": entry.provider_hashes["sha256"],
                    }
                )
            atomic_write_json(
                paths["restore"],
                {
                    "status": "completed",
                    "files": len(restored),
                    "bytes": sum(item["size_bytes"] for item in restored),
                    "selection": {
                        "strategy": (
                            "sentinels+known_empty+source_dataset+smallest+largest_within_limit"
                        ),
                        "max_object_bytes": effective_restore_max_bytes,
                    },
                    "objects": restored,
                    "temporary_directory_removed": True,
                },
            )
            operation.complete("restore", artifact=artifact_metadata(paths["restore"]))
            _emit(progress_callback, operation_id, "restore", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail("restore", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise
        finally:
            shutil.rmtree(restore_root, ignore_errors=True)

    if operation.begin("seal"):
        _emit(progress_callback, operation_id, "seal", "running")
        remote_locator = (
            f"{contract.data.manifests_prefix}/migrations/g02/{operation_id}/"
            "migration-complete.json"
        )
        try:
            copy_progress = _load_json_object(paths["copy_progress"], "progresso G02")
            restore_summary = _load_json_object(paths["restore"], "restauração G02")
            dry_run_summary = _load_json_object(paths["dry_run"], "dry-run G02")
            migration_complete = {
                "schema_version": 1,
                "status": "migration_complete",
                "operation_id": operation_id,
                "project_id": contract.project_id,
                "bucket": contract.data.bucket,
                "raw_prefix": contract.data.raw_prefix,
                "source_catalog_logical_sha256": contract.migration.source_catalog_sha256,
                "source_catalog_file_sha256": contract.migration.source_catalog_file_sha256,
                "final_catalog_sha256": sha256_file(paths["final_catalog"]),
                "verification_sha256": sha256_file(paths["verification"]),
                "idempotency_sha256": sha256_file(paths["idempotency"]),
                "restore_sha256": sha256_file(paths["restore"]),
                "files": contract.migration.source_files,
                "bytes": contract.migration.source_bytes,
                "approval": copy_progress.get("approval"),
                "estimated_cost_usd": dry_run_summary["estimated_cost_usd"],
                "operational_parameters": {
                    "batches": len(generated_plan["batches"]),
                    "batch_max_files": batch_max_files,
                    "batch_max_bytes": batch_max_bytes,
                    "transport": transport_descriptor,
                },
                "restore": {
                    "files": restore_summary["files"],
                    "bytes": restore_summary["bytes"],
                    "selection": restore_summary["selection"],
                },
                "remote_locator": remote_locator,
            }
            atomic_write_json(paths["migration_complete"], migration_complete)
            publication = transport.publish_bytes_create_only(
                remote_locator, paths["migration_complete"].read_bytes()
            )
            if transport.read_bytes(remote_locator) != paths["migration_complete"].read_bytes():
                raise GcsCopyAmbiguous("readback do manifest migration-complete divergiu")
            atomic_write_json(paths["seal"], {"status": "completed", **publication})
            operation.complete(
                "seal",
                artifact=artifact_metadata(paths["migration_complete"]),
                remote_id=str(publication.get("generation", "")),
            )
            _emit(progress_callback, operation_id, "seal", "completed")
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "seal",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
                remote_result_ambiguous=isinstance(exc, GcsCopyAmbiguous),
            )
            raise
    return _full_payload(operation, through, paths["migration_complete"])


def execute_gcs_cutover(
    *,
    store: ManifestStore,
    contract: GcpContract,
    gcp_config_path: Path,
    operation_root: Path,
    confirmed_project_id: str,
    confirmed_bucket: str,
    confirmed_source_folder_id: str,
    approved_migration_manifest_sha256: str,
    confirmed_authoritative_raw: str,
) -> dict[str, Any]:
    contract.confirm_targets(
        project_id=confirmed_project_id,
        bucket=confirmed_bucket,
        source_raw_folder_id=confirmed_source_folder_id,
    )
    _validate_transport_descriptor(store.descriptor(), contract)
    if confirmed_authoritative_raw != "gcs":
        raise GcsFullMigrationError("confirmação literal da autoridade raw deve ser gcs")
    try:
        resolved_root = operation_root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise GcsFullMigrationError("operação integral G02 ausente") from exc
    migration_complete_path = resolved_root / "migration-complete.json"
    full_manifest_path = resolved_root / "operation.json"
    _validate_completed_full_operation(full_manifest_path, migration_complete_path)
    observed_approval = sha256_file(migration_complete_path)
    if approved_migration_manifest_sha256 != observed_approval:
        raise GcsFullMigrationError("aprovação humana não corresponde ao manifest de migração")
    try:
        migration_complete = json.loads(migration_complete_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcsFullMigrationError("manifest de migração é inválido") from exc
    if migration_complete.get("operation_id") != resolved_root.name:
        raise GcsFullMigrationError("operation_id do manifest de migração diverge")
    operation_id = str(migration_complete["operation_id"])
    remote_locator = f"{contract.data.manifests_prefix}/migrations/g02/{operation_id}/cutover.json"
    paths = {
        "manifest": resolved_root / "cutover-operation.json",
        "payload": resolved_root / "cutover.json",
        "publish": resolved_root / "cutover-publish.json",
        "config": resolved_root / "cutover-config.json",
        "readback": resolved_root / "cutover-readback.json",
    }
    configuration = {
        "project_id": contract.project_id,
        "bucket": contract.data.bucket,
        "raw_prefix": contract.data.raw_prefix,
        "gcp_config_path": str(gcp_config_path.expanduser().resolve()),
        "migration_complete_sha256": observed_approval,
        "target_authoritative_raw": "gcs",
        "remote_locator": remote_locator,
        "store": store.descriptor(),
    }
    operation = RecoverableOperation(
        manifest_path=paths["manifest"],
        operation_id=f"{operation_id}-cutover",
        contract_version=1,
        implementation_version="g02-gcs-cutover-v1",
        input_fingerprint=fingerprint(
            {"migration_complete_sha256": observed_approval, "target": "gcs"}
        ),
        config_fingerprint=fingerprint(configuration),
        stages=(
            ("validate", ()),
            ("publish", ("validate",)),
            ("update_config", ("publish",)),
            ("readback", ("update_config",)),
        ),
        configuration=configuration,
    )
    _recover_cutover_interrupted(operation)

    if operation.begin("validate"):
        payload = {
            "schema_version": 1,
            "status": "approved_cutover",
            "operation_id": operation_id,
            "project_id": contract.project_id,
            "bucket": contract.data.bucket,
            "raw_prefix": contract.data.raw_prefix,
            "authoritative_raw": "gcs",
            "migration_complete_sha256": observed_approval,
            "remote_locator": remote_locator,
        }
        atomic_write_json(paths["payload"], payload)
        operation.complete("validate", artifact=artifact_metadata(paths["payload"]))

    if operation.begin("publish"):
        try:
            publication = store.publish_bytes_create_only(
                remote_locator, paths["payload"].read_bytes()
            )
            atomic_write_json(paths["publish"], {"status": "completed", **publication})
            operation.complete(
                "publish",
                artifact=artifact_metadata(paths["publish"]),
                remote_id=str(publication.get("generation", "")),
            )
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "publish",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
                remote_result_ambiguous=isinstance(exc, GcsCopyAmbiguous),
            )
            raise

    if operation.begin("update_config"):
        try:
            status = _set_authoritative_raw_gcs(gcp_config_path)
            updated = load_gcp_contract(gcp_config_path)
            if updated.migration.authoritative_raw != "gcs":
                raise GcsFullMigrationError("readback local não confirmou autoridade GCS")
            atomic_write_json(
                paths["config"],
                {
                    "status": status,
                    "authoritative_raw": "gcs",
                    "config_sha256": sha256_file(gcp_config_path),
                },
            )
            operation.complete("update_config", artifact=artifact_metadata(paths["config"]))
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "update_config", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise

    if operation.begin("readback"):
        try:
            if store.read_bytes(remote_locator) != paths["payload"].read_bytes():
                raise GcsFullMigrationError("readback remoto do cutover divergiu")
            updated = load_gcp_contract(gcp_config_path)
            if updated.migration.authoritative_raw != "gcs":
                raise GcsFullMigrationError("readback do config não confirmou o corte")
            atomic_write_json(
                paths["readback"],
                {
                    "status": "completed",
                    "authoritative_raw": "gcs",
                    "remote_locator": remote_locator,
                    "remote_sha256": sha256_file(paths["payload"]),
                },
            )
            operation.complete("readback", artifact=artifact_metadata(paths["readback"]))
        except (GcsMigrationError, OSError) as exc:
            operation.fail(
                "readback", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    return {
        "operation_id": operation_id,
        "status": operation.stage("readback")["status"],
        "manifest_path": str(paths["manifest"]),
        "artifact_path": str(paths["readback"]),
        "authoritative_raw": "gcs",
    }


def validate_g01_completion(operation_root: Path, contract: GcpContract) -> dict[str, Any]:
    manifest_path = operation_root / "operation.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcsFullMigrationError("manifest G01 ausente ou inválido") from exc
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise GcsFullMigrationError("configuração do manifest G01 é inválida")
    source_configuration = configuration.get("source")
    if not isinstance(source_configuration, dict):
        raise GcsFullMigrationError("origem do manifest G01 é inválida")
    if (
        configuration.get("project_id") != contract.project_id
        or configuration.get("bucket") != contract.data.bucket
        or configuration.get("raw_prefix") != contract.data.raw_prefix
        or source_configuration.get("root_folder_id") != contract.migration.source_raw_folder_id
        or configuration.get("sentinel_files") != len(contract.migration.sentinel)
        or configuration.get("sentinel_bytes")
        != sum(item.size_bytes for item in contract.migration.sentinel)
    ):
        raise GcsFullMigrationError("manifest G01 diverge dos alvos de G02")
    stages = {item.get("id"): item for item in payload.get("stages", []) if isinstance(item, dict)}
    for stage_id in G01_REQUIRED_STAGES:
        stage = stages.get(stage_id)
        if not isinstance(stage, dict) or stage.get("status") != "completed":
            raise GcsFullMigrationError(f"gate G01 incompleto: {stage_id}")
        artifact = stage.get("artifact")
        if not isinstance(artifact, dict) or not _artifact_matches(artifact):
            raise GcsFullMigrationError(f"evidência G01 ausente ou alterada: {stage_id}")
        if not Path(str(artifact["path"])).resolve().is_relative_to(operation_root):
            raise GcsFullMigrationError(f"evidência G01 fora da operação: {stage_id}")
    return {
        "status": "completed",
        "operation_id": payload.get("operation_id"),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
    }


def validate_mixed_combined(
    entries: Sequence[CatalogEntry],
    combined_path: Path,
    *,
    exact_locators: set[str],
) -> dict[str, Any]:
    expected = {item.source_locator for item in entries}
    observed: dict[str, str] = {}
    try:
        for line in combined_path.read_text(encoding="utf-8").splitlines():
            if len(line) < 3 or line[1:2] != " ":
                raise ValueError
            marker, locator = line[0], line[2:]
            if marker not in {"+", "=", "-", "*", "!"} or locator in observed:
                raise ValueError
            observed[locator] = marker
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise GcsFullMigrationError("relatório combinado integral é inválido") from exc
    wrong = {
        locator
        for locator, marker in observed.items()
        if marker != ("=" if locator in exact_locators else "+")
    }
    if expected != set(observed) or wrong:
        raise GcsFullMigrationError(
            "dry-run integral divergiu: "
            f"missing={len(expected - set(observed))}, "
            f"unexpected={len(set(observed) - expected)}, wrong={len(wrong)}"
        )
    pending = len(entries) - len(exact_locators)
    return {
        "files": len(entries),
        "bytes": sum(item.size_bytes for item in entries),
        "markers": {"=": len(exact_locators), "+": pending, "-": 0, "*": 0, "!": 0},
    }


def _copy_batch(
    *,
    transport: FullGcsTransport,
    catalog: Sequence[CatalogEntry],
    batch: Mapping[str, Any],
    entry_by_destination: Mapping[str, CatalogEntry],
    operation_root: Path,
    progress: dict[str, Any],
    progress_path: Path,
    attempt: int,
    previous_result_ambiguous: bool,
    operation_id: str,
    callback: Callable[[dict[str, Any]], None] | None,
) -> None:
    batch_id = str(batch["batch_id"])
    batch_entries = [entry_by_destination[str(item)] for item in batch["destination_locators"]]
    observed_before = _verify_destination_subset(catalog, transport.destination_metadata())
    observed_map = {item.locator: item for item in observed_before}
    missing = [item for item in batch_entries if item.destination_locator not in observed_map]
    for entry in batch_entries:
        current = observed_map.get(entry.destination_locator)
        if current is not None and not _metadata_matches(entry, current):
            raise GcsCopyConflict(f"destino existente diverge: {entry.destination_locator}")
    requested_files = len(missing)
    reconciled_after_interruption = [
        item
        for item in batch_entries
        if previous_result_ambiguous
        and item.destination_locator in observed_map
        and item.destination_locator not in progress["results"]
    ]
    result_status = "reused_verified"
    combined_sha256: str | None = None
    if missing:
        digest = fingerprint([item.source_locator for item in missing]).removeprefix("sha256:")[:12]
        stem = f"{batch_id}-attempt-{attempt:02d}-{digest}"
        files_from_path = operation_root / "batches" / f"{stem}-locators.bin"
        combined_path = operation_root / "batches" / f"{stem}-combined.txt"
        try:
            result = transport.copy_entries(
                missing,
                files_from_path=files_from_path,
                combined_path=combined_path,
                dry_run=False,
            )
            validate_combined(missing, combined_path, expected_marker="+")
            combined_sha256 = str(result["combined_sha256"])
            result_status = "copied_verified"
        except (GcsMigrationError, OSError) as exc:
            observed_after_error = _verify_destination_subset(
                catalog, transport.destination_metadata()
            )
            after_error_map = {item.locator: item for item in observed_after_error}
            if not all(
                entry.destination_locator in after_error_map
                and _metadata_matches(entry, after_error_map[entry.destination_locator])
                for entry in batch_entries
            ):
                raise GcsCopyAmbiguous(f"lote {batch_id} permaneceu ambíguo após readback") from exc
            result_status = "reconciled_after_error"
    observed_after = _verify_destination_subset(catalog, transport.destination_metadata())
    after_map = {item.locator: item for item in observed_after}
    for entry in batch_entries:
        current = after_map.get(entry.destination_locator)
        if current is None or not _metadata_matches(entry, current):
            raise GcsCopyConflict(f"lote {batch_id} não foi reconciliado integralmente")
        progress["results"][entry.destination_locator] = {
            "status": (
                result_status
                if entry in missing
                else (
                    "reconciled_after_interruption"
                    if entry in reconciled_after_interruption
                    else "reused_verified"
                )
            ),
            "batch_id": batch_id,
            "generation": current.generation,
        }
    conservatively_written = [*missing, *reconciled_after_interruption]
    progress["objects_written"] = int(progress["objects_written"]) + len(conservatively_written)
    progress["bytes_written"] = int(progress["bytes_written"]) + sum(
        item.size_bytes for item in conservatively_written
    )
    progress["completed_files"] = len(progress["results"])
    atomic_write_json(progress_path, progress)
    summary_path = operation_root / "batches" / f"{batch_id}-attempt-{attempt:02d}-summary.json"
    atomic_write_json(
        summary_path,
        {
            "status": "completed",
            "batch_id": batch_id,
            "attempt": attempt,
            "planned_files": len(batch_entries),
            "requested_files": requested_files,
            "verified_files": len(batch_entries),
            "combined_sha256": combined_sha256,
        },
    )
    _emit(
        callback,
        operation_id,
        "copy",
        "batch_completed",
        batch_id=batch_id,
        completed_files=int(progress["completed_files"]),
    )


def _validate_source_batch_plan(
    path: Path, catalog: Sequence[CatalogEntry], contract: GcpContract
) -> None:
    if sha256_file(path) != contract.migration.source_batch_plan_file_sha256:
        raise GcsFullMigrationError("arquivo do plano histórico de lotes divergiu")
    try:
        frozen = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcsFullMigrationError("plano histórico de lotes é inválido") from exc
    try:
        locators = [str(item) for item in frozen["sentinel"]["destination_locators"]]
        for batch in frozen["batches"]:
            locators.extend(str(item) for item in batch["destination_locators"])
        files = int(frozen["files"])
        size_bytes = int(frozen["bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GcsFullMigrationError("plano histórico de lotes é inválido") from exc
    expected = {item.destination_locator for item in catalog}
    if (
        files != len(catalog)
        or size_bytes != sum(item.size_bytes for item in catalog)
        or len(locators) != len(set(locators))
        or set(locators) != expected
    ):
        raise GcsFullMigrationError("plano histórico não representa a baseline integral")


def _validate_restore_sample(
    catalog: Sequence[CatalogEntry],
    sentinel: Sequence[CatalogEntry],
    contract: GcpContract,
    *,
    max_object_bytes: int,
) -> None:
    sample = select_restore_sample(
        catalog,
        sentinel,
        approved_empty_locators=contract.migration.approved_empty_source_locators,
        max_object_bytes=max_object_bytes,
    )
    required = {
        *(item.source_locator for item in sentinel),
        *contract.migration.approved_empty_source_locators,
    }
    if not required.issubset({item.source_locator for item in sample}):
        raise GcsFullMigrationError("amostra não cobre sentinelas e vazios aprovados")


def _verify_destination_subset(
    catalog: Sequence[CatalogEntry], observed: Sequence[GcsObjectMetadata]
) -> list[GcsObjectMetadata]:
    expected = {item.destination_locator: item for item in catalog}
    unique = _unique_metadata(observed)
    unexpected = set(unique) - set(expected)
    if unexpected:
        raise GcsCopyConflict(f"destino GCS contém {len(unexpected)} objeto(s) inesperado(s)")
    for locator, current in unique.items():
        if not _metadata_matches(expected[locator], current):
            raise GcsCopyConflict(f"objeto GCS divergiu: {locator}")
    return sorted(unique.values(), key=lambda item: item.locator)


def _verify_destination_metadata(
    entries: Sequence[CatalogEntry],
    observed: Sequence[GcsObjectMetadata],
    *,
    exact_locators: set[str] | None = None,
) -> list[GcsObjectMetadata]:
    expected = {item.destination_locator: item for item in entries}
    wanted = set(expected) if exact_locators is None else exact_locators
    unique = _unique_metadata(observed)
    if set(unique) != wanted:
        raise GcsCopyConflict(
            "destino GCS divergiu: "
            f"missing={len(wanted - set(unique))}, unexpected={len(set(unique) - wanted)}"
        )
    for locator, current in unique.items():
        if locator not in expected or not _metadata_matches(expected[locator], current):
            raise GcsCopyConflict(f"metadata GCS divergiu: {locator}")
    return sorted(unique.values(), key=lambda item: item.locator)


def _metadata_matches(entry: CatalogEntry, metadata: GcsObjectMetadata) -> bool:
    return (
        metadata.size_bytes == entry.size_bytes
        and metadata.md5 == entry.provider_hashes.get("md5")
        and bool(metadata.crc32c)
        and bool(metadata.generation)
        and bool(metadata.metageneration)
        and bool(metadata.storage_class)
    )


def _unique_metadata(
    objects: Sequence[GcsObjectMetadata],
) -> dict[str, GcsObjectMetadata]:
    result: dict[str, GcsObjectMetadata] = {}
    for item in objects:
        if item.locator in result:
            raise GcsCopyConflict(f"metadata GCS duplicada: {item.locator}")
        result[item.locator] = item
    return result


def _metadata_summary(metadata: Sequence[GcsObjectMetadata]) -> dict[str, Any]:
    return {
        "files": len(metadata),
        "bytes": sum(item.size_bytes for item in metadata),
        "metadata_fingerprint": fingerprint([item.as_dict() for item in metadata]),
    }


def _metadata_from_api(value: Any) -> GcsObjectMetadata:
    if not isinstance(value, dict):
        raise GcsFullMigrationError("metadata GCS inválida")
    try:
        md5 = base64.b64decode(str(value["md5Hash"]), validate=True).hex()
        metadata = GcsObjectMetadata(
            locator=str(value["name"]),
            size_bytes=int(value["size"]),
            md5=md5,
            crc32c=str(value["crc32c"]),
            generation=str(value["generation"]),
            metageneration=str(value["metageneration"]),
            storage_class=str(value["storageClass"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GcsFullMigrationError("metadata GCS incompleta") from exc
    if (
        not metadata.locator
        or metadata.size_bytes < 0
        or not re.fullmatch(r"[0-9a-f]{32}", metadata.md5)
        or not all(
            (
                metadata.crc32c,
                metadata.generation,
                metadata.metageneration,
                metadata.storage_class,
            )
        )
    ):
        raise GcsFullMigrationError("metadata GCS inválida")
    return metadata


def _source_dataset(entry: CatalogEntry) -> tuple[str, str]:
    parts = entry.source_locator.split("/")
    source = entry.source or (parts[0] if parts else "")
    dataset = entry.dataset or (parts[1] if len(parts) > 1 else "")
    if not source or not dataset:
        raise GcsFullMigrationError(f"source/dataset ausente: {entry.source_locator}")
    return source, dataset


def _require_copy_approval(
    dry_run_path: Path,
    *,
    approved_plan_sha256: str | None,
    approved_max_cost_usd: str | None,
    contract: GcpContract,
) -> None:
    dry_run = _load_json_object(dry_run_path, "dry-run G02")
    if approved_plan_sha256 != dry_run.get("approval_sha256"):
        raise GcsFullMigrationError("digest do plano de cópia não foi aprovado")
    try:
        ceiling = Decimal(str(approved_max_cost_usd))
    except (InvalidOperation, ValueError) as exc:
        raise GcsFullMigrationError("teto de custo aprovado é inválido") from exc
    estimated = Decimal(str(dry_run["estimated_cost_usd"]))
    if (
        not ceiling.is_finite()
        or ceiling < estimated
        or ceiling > Decimal(contract.budget.reference_ceiling_usd)
    ):
        raise GcsFullMigrationError("teto de custo aprovado está fora do contrato G02")


def _set_authoritative_raw_gcs(config_path: Path) -> str:
    resolved = config_path.expanduser().resolve(strict=True)
    content = resolved.read_text(encoding="utf-8")
    drive_line = 'authoritative_raw = "drive"'
    gcs_line = 'authoritative_raw = "gcs"'
    if content.count(gcs_line) == 1 and drive_line not in content:
        return "already_gcs"
    if content.count(drive_line) != 1 or gcs_line in content:
        raise GcsFullMigrationError("configuração não contém transição raw inequívoca")
    atomic_write_bytes(resolved, content.replace(drive_line, gcs_line).encode("utf-8"))
    return "updated"


def _validate_completed_full_operation(manifest_path: Path, migration_path: Path) -> None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcsFullMigrationError("manifest integral G02 é inválido") from exc
    stages = {item.get("id"): item for item in payload.get("stages", []) if isinstance(item, dict)}
    if any(stages.get(stage_id, {}).get("status") != "completed" for stage_id, _ in FULL_STAGES):
        raise GcsFullMigrationError("migração integral G02 ainda não está concluída")
    seal_artifact = stages["seal"].get("artifact")
    if not isinstance(seal_artifact, dict) or not _artifact_matches(seal_artifact):
        raise GcsFullMigrationError("evidência selada de G02 está ausente ou alterada")
    if Path(str(seal_artifact["path"])).resolve() != migration_path.resolve():
        raise GcsFullMigrationError("manifest selado de G02 aponta para outro artefato")


def _validate_transport_descriptor(value: Mapping[str, str], contract: GcpContract) -> None:
    if (
        value.get("project_id") != contract.project_id
        or value.get("bucket") != contract.data.bucket
    ):
        raise GcsFullMigrationError("transport GCS diverge do projeto ou bucket explícito")


def _artifact_matches(value: Mapping[str, Any]) -> bool:
    path = Path(str(value.get("path", "")))
    return (
        path.is_file()
        and path.stat().st_size == value.get("bytes")
        and sha256_file(path) == value.get("sha256")
    )


def _load_copy_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "status": "running",
            "completed_files": 0,
            "completed_bytes": 0,
            "objects_written": 0,
            "bytes_written": 0,
            "results": {},
        }
    payload = _load_json_object(path, "progresso de cópia G02")
    if not isinstance(payload.get("results"), dict):
        raise GcsFullMigrationError("progresso de cópia G02 é inválido")
    return payload


def _write_source_inventory(objects: Sequence[Any], path: Path) -> None:
    payload = b"".join(
        canonical_json_bytes(item.fingerprint_dict()) + b"\n"
        for item in sorted(objects, key=lambda current: current.locator)
    )
    atomic_write_bytes(path, payload)


def _write_final_catalog(
    entries: Sequence[CatalogEntry], metadata: Sequence[GcsObjectMetadata], path: Path
) -> None:
    by_locator = {item.locator: item for item in metadata}
    payload = b"".join(
        canonical_json_bytes(
            {
                "source": entry.source,
                "dataset": entry.dataset,
                "category": entry.category,
                "source_locator": entry.source_locator,
                "destination_locator": entry.destination_locator,
                "size_bytes": entry.size_bytes,
                "expected_md5": entry.provider_hashes["md5"],
                "expected_sha256": entry.provider_hashes["sha256"],
                "observed_gcs": by_locator[entry.destination_locator].as_dict(),
                "status": "verified",
            }
        )
        + b"\n"
        for entry in sorted(entries, key=lambda item: item.destination_locator)
    )
    atomic_write_bytes(path, payload)


def _full_paths(root: Path) -> dict[str, Path]:
    return {
        "source_inventory": root / "source-inventory.jsonl",
        "execution_plan": root / "copy-execution-plan.json",
        "preflight": root / "preflight.json",
        "dry_run_locators": root / "dry-run-locators.bin",
        "dry_run_combined": root / "dry-run-combined.txt",
        "dry_run": root / "dry-run.json",
        "copy_progress": root / "copy-progress.json",
        "final_catalog": root / "final-catalog.jsonl",
        "verification": root / "verification.json",
        "idempotency_locators": root / "idempotency-locators.bin",
        "idempotency_combined": root / "idempotency-combined.txt",
        "idempotency": root / "idempotency.json",
        "restore": root / "restore.json",
        "migration_complete": root / "migration-complete.json",
        "seal": root / "seal.json",
    }


def _invalidate_broken_preflight_links(
    operation: RecoverableOperation, paths: Mapping[str, Path]
) -> None:
    if operation.stage("preflight")["status"] != "completed":
        return
    if not operation.artifact_is_valid("preflight"):
        return
    try:
        _require_preflight_links(paths)
    except GcsFullMigrationError:
        operation.invalidate("preflight", reason="linked_artifact_missing_or_changed")


def _require_preflight_links(paths: Mapping[str, Path]) -> None:
    preflight = _load_json_object(paths["preflight"], "preflight G02")
    for key, path_key in (
        ("execution_plan_sha256", "execution_plan"),
        ("source_inventory_sha256", "source_inventory"),
    ):
        path = paths[path_key]
        if not path.is_file() or sha256_file(path) != preflight.get(key):
            raise GcsFullMigrationError(f"artefato ligado ao preflight divergiu: {path_key}")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GcsFullMigrationError(f"{label} ausente ou inválido") from exc
    if not isinstance(payload, dict):
        raise GcsFullMigrationError(f"{label} não é objeto JSON")
    return payload


def _recover_full_interrupted(operation: RecoverableOperation) -> None:
    for stage_id, _dependencies in FULL_STAGES:
        if operation.stage(stage_id)["status"] == "running":
            operation.recover_interrupted(
                stage_id,
                remote_result_ambiguous=stage_id in {"copy", "seal"},
                message="execução G02 interrompida; efeitos serão reconciliados",
            )


def _recover_cutover_interrupted(operation: RecoverableOperation) -> None:
    for stage_id in ("validate", "publish", "update_config", "readback"):
        if operation.stage(stage_id)["status"] == "running":
            operation.recover_interrupted(
                stage_id,
                remote_result_ambiguous=stage_id == "publish",
                message="cutover G02 interrompido; estado será reconciliado",
            )


def _validate_operation_id(operation_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise GcsFullMigrationError("operation_id G02 inválido")


def _full_payload(
    operation: RecoverableOperation, through: str, artifact_path: Path
) -> dict[str, Any]:
    stage_id = through.replace("-", "_")
    if through == "restore":
        stage_id = "seal"
    return {
        "operation_id": operation.snapshot()["operation_id"],
        "through": through,
        "status": operation.stage(stage_id)["status"],
        "manifest_path": str(operation.manifest_path),
        "artifact_path": str(artifact_path),
    }


def _emit(
    callback: Callable[[dict[str, Any]], None] | None,
    operation_id: str,
    stage: str,
    status: str,
    **details: Any,
) -> None:
    if callback is not None:
        callback({"operation_id": operation_id, "stage": stage, "status": status, **details})
