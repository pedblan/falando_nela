from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from falando_nela.gcp_config import GcpContract, SentinelConfig
from falando_nela.operations import RecoverableOperation, artifact_metadata, fingerprint
from falando_nela.raw import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)
from falando_nela.sources import SourceError, SourceObject, pinned_rclone_remote_path

EMPTY_MD5 = "d41d8cd98f00b204e9800998ecf8427e"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
APPROVED_EMPTY_SOURCE_LOCATORS = frozenset(
    {
        "camara/plenario_discursos/ano=1954/mes=12/prod-historico-camara-plenario.jsonl",
        "camara/plenario_discursos/ano=1956/mes=06/prod-historico-camara-plenario.jsonl",
    }
)


class GcsMigrationError(RuntimeError):
    """A fundação ou a sentinela GCS divergiu do contrato G01."""


@dataclass(frozen=True)
class CatalogEntry:
    category: str
    source_locator: str
    destination_locator: str
    size_bytes: int
    provider_hashes: dict[str, str]
    source: str | None = None
    dataset: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {
            "category": self.category,
            "source_locator": self.source_locator,
            "destination_locator": self.destination_locator,
            "size_bytes": self.size_bytes,
            "provider_hashes": dict(sorted(self.provider_hashes.items())),
        }
        if self.source is not None:
            result["source"] = self.source
        if self.dataset is not None:
            result["dataset"] = self.dataset
        return result


class InventorySource(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]: ...


class GcsTransport(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def destination_inventory(self) -> list[SourceObject]: ...

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]: ...

    def object_sha256(self, locator: str) -> str: ...


class GcloudImpersonatedTokenProvider:
    def __init__(
        self,
        *,
        project_id: str,
        service_account: str,
        operator_account: str,
        executable: str = "gcloud",
    ) -> None:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+", operator_account):
            raise GcsMigrationError("conta operadora inválida")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.iam\.gserviceaccount\.com", service_account):
            raise GcsMigrationError("service account migradora inválida")
        if shutil.which(executable) is None:
            raise GcsMigrationError("gcloud não está instalado ou não está no PATH")
        self.project_id = project_id
        self.service_account = service_account
        self.operator_account = operator_account
        self.executable = executable

    def command(self) -> list[str]:
        return [
            self.executable,
            "auth",
            "print-access-token",
            self.operator_account,
            f"--impersonate-service-account={self.service_account}",
            f"--project={self.project_id}",
            "--lifetime=3600s",
            "--quiet",
        ]

    def __call__(self) -> str:
        result = subprocess.run(
            self.command(),
            check=False,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if result.returncode != 0 or not value or any(character.isspace() for character in value):
            raise GcsMigrationError(
                "não foi possível obter token curto por impersonação; consulte o diagnóstico seguro"
            )
        return value


class RcloneGcsTransport:
    remote_name = "gcstarget"

    def __init__(
        self,
        *,
        config_path: Path,
        source_remote: str,
        source_folder_id: str,
        source_prefix: str,
        project_id: str,
        project_number: str,
        region: str,
        bucket: str,
        raw_prefix: str,
        access_token: Callable[[], str],
        transfers: int = 4,
        retries: int = 1,
        low_level_retries: int = 1,
        executable: str = "rclone",
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", source_remote):
            raise GcsMigrationError("remote rclone de origem inválido")
        self.config_path = config_path.expanduser().resolve(strict=True)
        self.source_remote = source_remote
        self.source_folder_id = source_folder_id
        self.source_prefix = source_prefix.strip("/")
        self.project_id = project_id
        if not re.fullmatch(r"[1-9][0-9]{5,20}", project_number):
            raise GcsMigrationError("número do projeto GCP inválido")
        self.project_number = project_number
        self.region = region
        self.bucket = bucket
        self.raw_prefix = raw_prefix.strip("/")
        self.access_token = access_token
        if not 1 <= transfers <= 16:
            raise GcsMigrationError("transfers deve ficar entre 1 e 16")
        if not 1 <= retries <= 5:
            raise GcsMigrationError("retries deve ficar entre 1 e 5")
        if not 1 <= low_level_retries <= 10:
            raise GcsMigrationError("low-level-retries deve ficar entre 1 e 10")
        self.transfers = transfers
        self.retries = retries
        self.low_level_retries = low_level_retries
        self.executable = executable
        if shutil.which(executable) is None:
            raise GcsMigrationError("rclone não está instalado ou não está no PATH")
        pinned_rclone_remote_path(source_remote, source_folder_id, self.source_prefix)

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "rclone_gcs",
            "project_id": self.project_id,
            "project_number": self.project_number,
            "region": self.region,
            "bucket": self.bucket,
            "raw_prefix": self.raw_prefix,
            "source_remote": self.source_remote,
            "source_folder_id": self.source_folder_id,
            "source_prefix": self.source_prefix,
            "authentication": "short_lived_impersonated_token",
            "transfers": str(self.transfers),
            "retries": str(self.retries),
            "low_level_retries": str(self.low_level_retries),
        }

    def destination_inventory(self) -> list[SourceObject]:
        result = self._run(
            [
                self.executable,
                "lsjson",
                self._destination_root(),
                "--recursive",
                "--files-only",
                "--hash",
                "--config",
                str(self.config_path),
                "--ask-password=false",
            ]
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GcsMigrationError("inventário GCS retornou JSON inválido") from exc
        if not isinstance(payload, list):
            raise GcsMigrationError("inventário GCS não retornou uma lista")
        objects: list[SourceObject] = []
        for item in payload:
            if not isinstance(item, dict) or item.get("IsDir") is True:
                continue
            relative = item.get("Path")
            size = item.get("Size")
            if not isinstance(relative, str) or not isinstance(size, int):
                raise GcsMigrationError("item inválido no inventário GCS")
            raw_hashes = item.get("Hashes") if isinstance(item.get("Hashes"), dict) else {}
            objects.append(
                SourceObject(
                    locator=f"{self.raw_prefix}/{relative}",
                    size_bytes=size,
                    provider_hashes=_normalize_hashes(raw_hashes),
                )
            )
        return sorted(objects, key=lambda item: item.locator)

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]:
        write_files_from0(entries, files_from_path)
        command = [
            self.executable,
            "copy",
            pinned_rclone_remote_path(
                self.source_remote, self.source_folder_id, self.source_prefix
            ),
            self._destination_root(),
            "--files-from0",
            str(files_from_path),
            "--immutable",
            "--checksum",
            "--check-first",
            "--retries",
            str(self.retries),
            "--low-level-retries",
            str(self.low_level_retries),
            "--transfers",
            str(self.transfers),
            "--combined",
            str(combined_path),
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]
        if dry_run:
            command.append("--dry-run")
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        result = self._run(command)
        if not combined_path.is_file():
            raise GcsMigrationError("rclone não produziu relatório combinado")
        return {
            "return_code": result.returncode,
            "combined_path": str(combined_path),
            "combined_sha256": sha256_file(combined_path),
            "combined_bytes": combined_path.stat().st_size,
        }

    def object_sha256(self, locator: str) -> str:
        expected_prefix = f"{self.raw_prefix}/"
        if not locator.startswith(expected_prefix):
            raise GcsMigrationError("locator GCS está fora do prefixo raw")
        remote_path = f"{self.remote_name}:{self.bucket}/{locator}"
        process = subprocess.Popen(
            [
                self.executable,
                "cat",
                remote_path,
                "--config",
                str(self.config_path),
                "--ask-password=false",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._environment(),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        digest = hashlib.sha256()
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(chunk)
        process.stdout.close()
        process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            raise GcsMigrationError("não foi possível calcular SHA-256 do objeto GCS")
        return digest.hexdigest()

    def _destination_root(self) -> str:
        return f"{self.remote_name}:{self.bucket}/{self.raw_prefix}"

    def _environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        for name in (
            "CLOUDSDK_CORE_PROJECT",
            "GCLOUD_PROJECT",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_QUOTA_PROJECT",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_OAUTH_ACCESS_TOKEN",
            "RCLONE_GCS_ACCESS_TOKEN",
            "RCLONE_GCS_SERVICE_ACCOUNT_CREDENTIALS",
            "RCLONE_GCS_SERVICE_ACCOUNT_FILE",
        ):
            environment.pop(name, None)
        environment.update(
            {
                "CLOUDSDK_CORE_PROJECT": self.project_id,
                "GCLOUD_PROJECT": self.project_id,
                "GOOGLE_CLOUD_PROJECT": self.project_id,
                "RCLONE_CONFIG_GCSTARGET_TYPE": "gcs",
                "RCLONE_CONFIG_GCSTARGET_ACCESS_TOKEN": self.access_token(),
                "RCLONE_CONFIG_GCSTARGET_BUCKET_POLICY_ONLY": "true",
                "RCLONE_CONFIG_GCSTARGET_ENV_AUTH": "false",
                "RCLONE_CONFIG_GCSTARGET_NO_CHECK_BUCKET": "true",
                "RCLONE_CONFIG_GCSTARGET_PROJECT_NUMBER": self.project_number,
            }
        )
        return environment

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=self._environment(),
        )
        if result.returncode != 0:
            raise GcsMigrationError(
                f"rclone GCS falhou (exit {result.returncode}); consulte o log seguro"
            )
        return result


def load_source_catalog(path: Path, contract: GcpContract) -> list[CatalogEntry]:
    resolved = path.expanduser().resolve(strict=True)
    if sha256_file(resolved) != contract.migration.source_catalog_file_sha256:
        raise GcsMigrationError("arquivo de catálogo divergiu do hash aprovado")
    entries: list[CatalogEntry] = []
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError
                raw_hashes = item.get("provider_hashes")
                entry = CatalogEntry(
                    category=str(item["category"]),
                    source_locator=str(item["source_locator"]),
                    destination_locator=str(item["destination_locator"]),
                    size_bytes=int(item["size_bytes"]),
                    provider_hashes=_normalize_hashes(
                        raw_hashes if isinstance(raw_hashes, dict) else {}
                    ),
                    source=str(item["source"]) if item.get("source") is not None else None,
                    dataset=str(item["dataset"]) if item.get("dataset") is not None else None,
                )
                if (
                    entry.source_locator in contract.migration.approved_empty_source_locators
                    and entry.size_bytes == 0
                    and entry.provider_hashes == {"md5": EMPTY_MD5}
                ):
                    entry = CatalogEntry(
                        category=entry.category,
                        source_locator=entry.source_locator,
                        destination_locator=entry.destination_locator,
                        size_bytes=entry.size_bytes,
                        provider_hashes={"md5": EMPTY_MD5, "sha256": EMPTY_SHA256},
                        source=entry.source,
                        dataset=entry.dataset,
                    )
                _validate_catalog_entry(entry)
                entries.append(entry)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise GcsMigrationError("catálogo de origem é inválido") from exc
    if len(entries) != contract.migration.source_files:
        raise GcsMigrationError("contagem do catálogo divergiu do contrato")
    if sum(item.size_bytes for item in entries) != contract.migration.source_bytes:
        raise GcsMigrationError("bytes do catálogo divergiram do contrato")
    if len({item.source_locator for item in entries}) != len(entries):
        raise GcsMigrationError("catálogo contém locator de origem duplicado")
    if len({item.destination_locator for item in entries}) != len(entries):
        raise GcsMigrationError("catálogo contém locator de destino duplicado")
    return sorted(entries, key=lambda item: item.source_locator)


def reconcile_source_catalog(
    expected: Sequence[CatalogEntry], observed: Sequence[SourceObject]
) -> dict[str, int]:
    expected_by_locator = {item.source_locator: item for item in expected}
    observed_by_locator = _unique_source_objects(observed)
    missing = sorted(set(expected_by_locator) - set(observed_by_locator))
    unexpected = sorted(set(observed_by_locator) - set(expected_by_locator))
    changed: list[str] = []
    for locator in sorted(set(expected_by_locator) & set(observed_by_locator)):
        wanted = expected_by_locator[locator]
        current = observed_by_locator[locator]
        hashes = _normalized_observed_hashes(current)
        if wanted.size_bytes != current.size_bytes or any(
            hashes.get(name) != value for name, value in wanted.provider_hashes.items()
        ):
            changed.append(locator)
    if missing or unexpected or changed:
        raise GcsMigrationError(
            "inventário Drive divergiu: "
            f"missing={len(missing)}, unexpected={len(unexpected)}, changed={len(changed)}"
        )
    return {
        "files": len(observed),
        "bytes": sum(item.size_bytes for item in observed),
        "missing": 0,
        "unexpected": 0,
        "changed": 0,
    }


def select_sentinel(
    catalog: Sequence[CatalogEntry], configured: Sequence[SentinelConfig]
) -> list[CatalogEntry]:
    by_source = {item.source_locator: item for item in catalog}
    selected: list[CatalogEntry] = []
    for wanted in configured:
        entry = by_source.get(wanted.source_locator)
        if entry is None:
            raise GcsMigrationError(f"sentinela ausente do catálogo: {wanted.source_locator}")
        if (
            entry.category != wanted.category
            or entry.destination_locator != wanted.destination_locator
            or entry.size_bytes != wanted.size_bytes
            or entry.provider_hashes.get("md5") != wanted.md5
            or entry.provider_hashes.get("sha256") != wanted.sha256
        ):
            raise GcsMigrationError(f"sentinela divergiu: {wanted.source_locator}")
        selected.append(entry)
    return sorted(selected, key=lambda item: item.category)


def validate_combined(
    entries: Sequence[CatalogEntry], combined_path: Path, *, expected_marker: str
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
        raise GcsMigrationError("relatório combinado do rclone é inválido") from exc
    missing = expected - set(observed)
    unexpected = set(observed) - expected
    wrong = {locator for locator, marker in observed.items() if marker != expected_marker}
    if missing or unexpected or wrong:
        raise GcsMigrationError(
            "relatório rclone divergiu: "
            f"missing={len(missing)}, unexpected={len(unexpected)}, wrong={len(wrong)}"
        )
    return {
        "files": len(entries),
        "bytes": sum(item.size_bytes for item in entries),
        "markers": {expected_marker: len(entries)},
    }


def verify_destination(entries: Sequence[CatalogEntry], transport: GcsTransport) -> dict[str, Any]:
    observed = {item.locator: item for item in transport.destination_inventory()}
    expected_locators = {item.destination_locator for item in entries}
    if set(observed) != expected_locators:
        raise GcsMigrationError(
            "destino GCS divergiu: "
            f"missing={len(expected_locators - set(observed))}, "
            f"unexpected={len(set(observed) - expected_locators)}"
        )
    results: list[dict[str, Any]] = []
    for entry in entries:
        current = observed[entry.destination_locator]
        hashes = _normalize_hashes(current.provider_hashes)
        sha256 = transport.object_sha256(entry.destination_locator)
        if (
            current.size_bytes != entry.size_bytes
            or hashes.get("md5") != entry.provider_hashes.get("md5")
            or sha256 != entry.provider_hashes.get("sha256")
        ):
            raise GcsMigrationError(f"objeto GCS divergiu: {entry.destination_locator}")
        results.append(
            {
                "locator": entry.destination_locator,
                "size_bytes": current.size_bytes,
                "md5": hashes["md5"],
                "sha256": sha256,
            }
        )
    return {
        "status": "verified",
        "files": len(results),
        "bytes": sum(item["size_bytes"] for item in results),
        "objects": results,
    }


def execute_gcs_sentinel(
    *,
    source: InventorySource,
    transport: GcsTransport,
    contract: GcpContract,
    source_catalog_path: Path,
    data_root: Path,
    operation_id: str,
    confirmed_project_id: str,
    confirmed_bucket: str,
    confirmed_source_folder_id: str,
    through: str,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise GcsMigrationError("operation_id inválido")
    if through not in {"preflight", "dry-run", "copy"}:
        raise GcsMigrationError("through deve ser preflight, dry-run ou copy")
    contract.confirm_targets(
        project_id=confirmed_project_id,
        bucket=confirmed_bucket,
        source_raw_folder_id=confirmed_source_folder_id,
    )
    descriptor = source.descriptor()
    if descriptor.get("scope") != "drive.readonly":
        raise GcsMigrationError("origem deve usar scope drive.readonly")
    if descriptor.get("root_folder_id") != contract.migration.source_raw_folder_id:
        raise GcsMigrationError("origem não está fixada na pasta raw aprovada")
    resolved_root = data_root.expanduser().resolve(strict=True)
    resolved_catalog = source_catalog_path.expanduser().resolve(strict=True)
    catalog = load_source_catalog(resolved_catalog, contract)
    sentinel = select_sentinel(catalog, contract.migration.sentinel)
    operation_root = resolved_root / "operations" / "gcs_migration" / operation_id
    manifest_path = operation_root / "operation.json"
    source_inventory_path = operation_root / "source-inventory.jsonl"
    preflight_path = operation_root / "preflight.json"
    sentinel_path = operation_root / "sentinel-manifest.json"
    files_from_path = operation_root / "sentinel-locators.bin"
    dry_run_combined_path = operation_root / "dry-run-combined.txt"
    dry_run_path = operation_root / "dry-run.json"
    copy_combined_path = operation_root / "copy-combined.txt"
    copy_path = operation_root / "copy.json"
    verification_path = operation_root / "verification.json"
    idempotency_combined_path = operation_root / "idempotency-combined.txt"
    idempotency_path = operation_root / "idempotency.json"
    public_configuration = {
        "project_id": contract.project_id,
        "region": contract.region,
        "bucket": contract.data.bucket,
        "raw_prefix": contract.data.raw_prefix,
        "source": descriptor,
        "source_catalog": str(resolved_catalog),
        "source_catalog_sha256": sha256_file(resolved_catalog),
        "sentinel_files": len(sentinel),
        "sentinel_bytes": sum(item.size_bytes for item in sentinel),
        "through_contract": ["preflight", "dry-run", "copy", "verify", "idempotency"],
        "transport": transport.descriptor(),
    }
    operation = RecoverableOperation(
        manifest_path=manifest_path,
        operation_id=operation_id,
        contract_version=1,
        implementation_version="g01-gcs-sentinel-v1",
        input_fingerprint=fingerprint(
            {
                "gcp_contract": contract.model_dump(mode="json"),
                "source_catalog_sha256": sha256_file(resolved_catalog),
            }
        ),
        config_fingerprint=fingerprint(public_configuration),
        stages=(
            ("preflight", ()),
            ("dry_run", ("preflight",)),
            ("copy", ("dry_run",)),
            ("verify", ("copy",)),
            ("idempotency", ("verify",)),
        ),
        configuration=public_configuration,
    )
    _recover_interrupted(operation)

    if operation.begin("preflight"):
        _emit(progress_callback, operation_id, "preflight", "running")
        try:
            observed = source.list_objects()
            summary = reconcile_source_catalog(catalog, observed)
            _write_source_inventory(observed, source_inventory_path)
            atomic_write_json(
                sentinel_path,
                {
                    "schema_version": 1,
                    "files": len(sentinel),
                    "bytes": sum(item.size_bytes for item in sentinel),
                    "entries": [item.as_dict() for item in sentinel],
                },
            )
            atomic_write_json(
                preflight_path,
                {
                    "status": "completed",
                    **summary,
                    "source_inventory_path": str(source_inventory_path),
                    "source_inventory_sha256": sha256_file(source_inventory_path),
                    "sentinel_manifest_path": str(sentinel_path),
                    "sentinel_manifest_sha256": sha256_file(sentinel_path),
                },
            )
            operation.complete("preflight", artifact=artifact_metadata(preflight_path))
            _emit(progress_callback, operation_id, "preflight", "completed")
        except (GcsMigrationError, OSError, SourceError) as exc:
            operation.fail(
                "preflight", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    if through == "preflight":
        return _payload(operation, through, preflight_path)

    if operation.begin("dry_run"):
        _emit(progress_callback, operation_id, "dry_run", "running")
        try:
            destination = transport.destination_inventory()
            expected_marker = "+"
            destination_status = "empty"
            if destination:
                verify_destination(sentinel, transport)
                expected_marker = "="
                destination_status = "sentinel_already_verified"
            transport.copy_entries(
                sentinel,
                files_from_path=files_from_path,
                combined_path=dry_run_combined_path,
                dry_run=True,
            )
            summary = validate_combined(
                sentinel,
                dry_run_combined_path,
                expected_marker=expected_marker,
            )
            atomic_write_json(
                dry_run_path,
                {
                    "status": "completed",
                    "destination_status": destination_status,
                    **summary,
                    "combined_path": str(dry_run_combined_path),
                    "combined_sha256": sha256_file(dry_run_combined_path),
                },
            )
            operation.complete("dry_run", artifact=artifact_metadata(dry_run_path))
            _emit(progress_callback, operation_id, "dry_run", "completed")
        except (GcsMigrationError, OSError, SourceError) as exc:
            operation.fail("dry_run", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise
    if through == "dry-run":
        return _payload(operation, through, dry_run_path)

    if operation.begin("copy"):
        _emit(progress_callback, operation_id, "copy", "running")
        try:
            copy_report = transport.copy_entries(
                sentinel,
                files_from_path=files_from_path,
                combined_path=copy_combined_path,
                dry_run=False,
            )
            summary = validate_combined(sentinel, copy_combined_path, expected_marker="+")
            atomic_write_json(
                copy_path,
                {
                    "status": "completed",
                    **summary,
                    "combined_path": str(copy_combined_path),
                    "combined_sha256": copy_report["combined_sha256"],
                },
            )
            operation.complete(
                "copy",
                artifact=artifact_metadata(copy_path),
                usage={"objects_written": len(sentinel), "bytes_written": summary["bytes"]},
                estimated_cost_usd="0.000001",
            )
            _emit(progress_callback, operation_id, "copy", "completed")
        except (GcsMigrationError, OSError, SourceError) as exc:
            try:
                reconciled = verify_destination(sentinel, transport)
            except GcsMigrationError as reconciliation_error:
                operation.fail(
                    "copy",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    blocked=True,
                    remote_result_ambiguous=True,
                )
                raise GcsMigrationError(
                    f"{exc}; o destino não pôde ser reconciliado com segurança"
                ) from reconciliation_error
            atomic_write_json(
                copy_path,
                {**reconciled, "status": "reconciled_after_error"},
            )
            operation.complete(
                "copy",
                artifact=artifact_metadata(copy_path),
                usage={"objects_reconciled": len(sentinel)},
                estimated_cost_usd="0.000001",
            )

    if operation.begin("verify"):
        _emit(progress_callback, operation_id, "verify", "running")
        try:
            verification = verify_destination(sentinel, transport)
            atomic_write_json(verification_path, verification)
            operation.complete("verify", artifact=artifact_metadata(verification_path))
            _emit(progress_callback, operation_id, "verify", "completed")
        except (GcsMigrationError, OSError, SourceError) as exc:
            operation.fail("verify", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise

    if operation.begin("idempotency"):
        _emit(progress_callback, operation_id, "idempotency", "running")
        try:
            before = verify_destination(sentinel, transport)
            idempotency_report = transport.copy_entries(
                sentinel,
                files_from_path=files_from_path,
                combined_path=idempotency_combined_path,
                dry_run=False,
            )
            markers = validate_combined(sentinel, idempotency_combined_path, expected_marker="=")
            after = verify_destination(sentinel, transport)
            if before != after:
                raise GcsMigrationError("destino mudou durante a prova de idempotência")
            atomic_write_json(
                idempotency_path,
                {
                    "status": "completed",
                    **markers,
                    "objects_written": 0,
                    "combined_path": str(idempotency_combined_path),
                    "combined_sha256": idempotency_report["combined_sha256"],
                    "verification_sha256": fingerprint(after),
                },
            )
            operation.complete(
                "idempotency",
                artifact=artifact_metadata(idempotency_path),
                usage={"objects_written": 0, "bytes_written": 0},
            )
            _emit(progress_callback, operation_id, "idempotency", "completed")
        except (GcsMigrationError, OSError, SourceError) as exc:
            operation.fail(
                "idempotency", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    return _payload(operation, through, idempotency_path)


def write_files_from0(entries: Sequence[CatalogEntry], path: Path) -> None:
    payload = b"".join(item.source_locator.encode("utf-8") + b"\0" for item in entries)
    atomic_write_bytes(path, payload)


def _validate_catalog_entry(entry: CatalogEntry) -> None:
    if (
        not entry.source_locator
        or entry.source_locator.startswith("/")
        or ".." in Path(entry.source_locator).parts
        or any(ord(character) < 32 for character in entry.source_locator)
    ):
        raise ValueError
    if entry.destination_locator != f"data/raw/v1/{entry.source_locator}":
        raise ValueError
    if entry.size_bytes < 0:
        raise ValueError
    if entry.size_bytes == 0 and (
        entry.source_locator not in APPROVED_EMPTY_SOURCE_LOCATORS
        or entry.provider_hashes.get("md5") != EMPTY_MD5
        or entry.provider_hashes.get("sha256") != EMPTY_SHA256
    ):
        raise ValueError
    if not re.fullmatch(r"[0-9a-f]{32}", entry.provider_hashes.get("md5", "")):
        raise ValueError
    if not re.fullmatch(r"[0-9a-f]{64}", entry.provider_hashes.get("sha256", "")):
        raise ValueError


def _normalize_hashes(value: Mapping[str, Any]) -> dict[str, str]:
    aliases = {"sha-1": "sha1", "sha-256": "sha256", "crc-32c": "crc32c"}
    return {
        aliases.get(str(key).casefold(), str(key).casefold()): str(item).casefold()
        for key, item in value.items()
    }


def _normalized_observed_hashes(value: SourceObject) -> dict[str, str]:
    hashes = _normalize_hashes(value.provider_hashes)
    if value.size_bytes == 0 and hashes.get("md5") == EMPTY_MD5:
        hashes.setdefault("sha256", EMPTY_SHA256)
    return hashes


def _unique_source_objects(objects: Sequence[SourceObject]) -> dict[str, SourceObject]:
    result: dict[str, SourceObject] = {}
    for item in objects:
        if item.locator in result:
            raise GcsMigrationError(f"locator duplicado no inventário: {item.locator}")
        result[item.locator] = item
    return result


def _write_source_inventory(objects: Sequence[SourceObject], path: Path) -> None:
    content = b"".join(
        canonical_json_bytes(item.fingerprint_dict()) + b"\n"
        for item in sorted(objects, key=lambda current: current.locator)
    )
    atomic_write_bytes(path, content)


def _recover_interrupted(operation: RecoverableOperation) -> None:
    for stage_id in ("preflight", "dry_run", "copy", "verify", "idempotency"):
        if operation.stage(stage_id)["status"] == "running":
            operation.recover_interrupted(
                stage_id,
                remote_result_ambiguous=stage_id in {"copy", "idempotency"},
                message="execução anterior foi interrompida; destino será reconciliado",
            )


def _emit(
    callback: Callable[[dict[str, Any]], None] | None,
    operation_id: str,
    stage: str,
    status: str,
) -> None:
    if callback is not None:
        callback({"operation_id": operation_id, "stage": stage, "status": status})


def _payload(operation: RecoverableOperation, through: str, artifact_path: Path) -> dict[str, Any]:
    return {
        "operation_id": operation.snapshot()["operation_id"],
        "through": through,
        "status": operation.stage(through.replace("-", "_"))["status"]
        if through != "copy"
        else operation.stage("idempotency")["status"],
        "manifest_path": str(operation.manifest_path),
        "artifact_path": str(artifact_path),
    }
