from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from falando_nela.gcp_config import GcpContract, SentinelConfig, load_gcp_contract
from falando_nela.gcs_migration import (
    EMPTY_MD5,
    CatalogEntry,
    GcloudImpersonatedTokenProvider,
    GcsMigrationError,
    RcloneGcsTransport,
    execute_gcs_sentinel,
    load_source_catalog,
    reconcile_source_catalog,
)
from falando_nela.operations import OperationError
from falando_nela.raw import canonical_json_bytes, sha256_file
from falando_nela.sources import SourceError, SourceObject

REPO_ROOT = Path(__file__).parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "gcp.toml"
RAW_FOLDER_ID = "1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9"
TOKEN = "TOKEN-SENTINELA-NAO-PODE-VAZAR"


class FakeSource:
    def __init__(self, objects: Sequence[SourceObject]) -> None:
        self.objects = list(objects)
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
        return list(self.objects)


class FakeTransport:
    def __init__(
        self,
        entries: Sequence[CatalogEntry],
        *,
        existing: Sequence[SourceObject] = (),
        fail_after_copy: bool = False,
    ) -> None:
        self.entries = list(entries)
        self.objects = list(existing)
        self.sha256 = {item.destination_locator: item.provider_hashes["sha256"] for item in entries}
        self.fail_after_copy = fail_after_copy
        self.copy_calls: list[bool] = []

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": "fake-gcs",
            "project_id": "falando-nela-pedblan",
            "project_number": "818569314985",
            "region": "southamerica-east1",
            "bucket": "falando-nela-pedblan-data",
        }

    def destination_inventory(self) -> list[SourceObject]:
        return list(self.objects)

    def copy_entries(
        self,
        entries: Sequence[CatalogEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
        dry_run: bool,
    ) -> dict[str, Any]:
        files_from_path.parent.mkdir(parents=True, exist_ok=True)
        files_from_path.write_bytes(
            b"".join(item.source_locator.encode("utf-8") + b"\0" for item in entries)
        )
        assert files_from_path.read_bytes().count(b"\0") == len(entries)
        marker = "=" if self.objects else "+"
        self.copy_calls.append(dry_run)
        if not dry_run and not self.objects:
            self.objects = [
                SourceObject(
                    locator=item.destination_locator,
                    size_bytes=item.size_bytes,
                    provider_hashes={"md5": item.provider_hashes["md5"]},
                )
                for item in entries
            ]
            if self.fail_after_copy:
                self.fail_after_copy = False
                raise GcsMigrationError("resultado remoto simulado como ambíguo")
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        combined_path.write_text(
            "".join(f"{marker} {item.source_locator}\n" for item in entries),
            encoding="utf-8",
        )
        return {
            "return_code": 0,
            "combined_sha256": sha256_file(combined_path),
        }

    def object_sha256(self, locator: str) -> str:
        return self.sha256[locator]


def _entry(index: int, category: str) -> CatalogEntry:
    source = f"senado/base-{index}/metadata/item-{index}.jsonl"
    return CatalogEntry(
        category=category,
        source_locator=source,
        destination_locator=f"data/raw/v1/{source}",
        size_bytes=index * 10,
        provider_hashes={"md5": f"{index:032x}", "sha256": f"{index:064x}"},
    )


def _fixture_contract_and_catalog(tmp_path: Path) -> tuple[GcpContract, Path, list[CatalogEntry]]:
    entries = [
        _entry(1, "metadata"),
        _entry(2, "monthly_text"),
        _entry(3, "transcription_queue"),
    ]
    catalog_path = tmp_path / "catalog.jsonl"
    catalog_path.write_bytes(
        b"".join(canonical_json_bytes(item.as_dict()) + b"\n" for item in entries)
    )
    contract = load_gcp_contract(CONFIG_PATH)
    migration = contract.migration.model_copy(
        update={
            "source_files": len(entries),
            "source_bytes": sum(item.size_bytes for item in entries),
            "source_catalog_sha256": "a" * 64,
            "source_catalog_file_sha256": sha256_file(catalog_path),
            "sentinel": tuple(
                SentinelConfig(
                    category=item.category,
                    source_locator=item.source_locator,
                    destination_locator=item.destination_locator,
                    size_bytes=item.size_bytes,
                    md5=item.provider_hashes["md5"],
                    sha256=item.provider_hashes["sha256"],
                )
                for item in entries
            ),
        }
    )
    return contract.model_copy(update={"migration": migration}), catalog_path, entries


def _source_objects(entries: Sequence[CatalogEntry]) -> list[SourceObject]:
    return [
        SourceObject(
            locator=item.source_locator,
            size_bytes=item.size_bytes,
            provider_hashes=item.provider_hashes,
        )
        for item in entries
    ]


def _run(
    tmp_path: Path,
    *,
    operation_id: str,
    contract: GcpContract,
    catalog_path: Path,
    source: FakeSource,
    transport: FakeTransport,
    through: str,
) -> dict[str, Any]:
    data_root = tmp_path / "data"
    data_root.mkdir(exist_ok=True)
    return execute_gcs_sentinel(
        source=source,
        transport=transport,
        contract=contract,
        source_catalog_path=catalog_path,
        data_root=data_root,
        operation_id=operation_id,
        confirmed_project_id="falando-nela-pedblan",
        confirmed_bucket="falando-nela-pedblan-data",
        confirmed_source_folder_id=RAW_FOLDER_ID,
        through=through,
    )


@pytest.mark.parametrize("mode", ["missing", "unexpected", "changed"])
def test_preflight_blocks_inventory_divergence(tmp_path: Path, mode: str) -> None:
    _contract, _catalog, entries = _fixture_contract_and_catalog(tmp_path)
    objects = _source_objects(entries)
    if mode == "missing":
        objects.pop()
    elif mode == "unexpected":
        objects.append(SourceObject("extra.jsonl", 1, provider_hashes={"md5": "a"}))
    else:
        objects[0] = SourceObject(
            objects[0].locator,
            objects[0].size_bytes + 1,
            provider_hashes=objects[0].provider_hashes,
        )

    with pytest.raises(GcsMigrationError, match="inventário Drive divergiu"):
        reconcile_source_catalog(entries, objects)


def test_preflight_persists_safe_source_failure_as_blocked(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)

    class FailingSource(FakeSource):
        def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
            raise SourceError("rclone lsjson falhou (exit 1); consulte o log local protegido")

    with pytest.raises(SourceError, match="rclone lsjson falhou"):
        _run(
            tmp_path,
            operation_id="source-failed",
            contract=contract,
            catalog_path=catalog_path,
            source=FailingSource(_source_objects(entries)),
            transport=FakeTransport(entries),
            through="preflight",
        )

    manifest = json.loads(
        (tmp_path / "data/operations/gcs_migration/source-failed/operation.json").read_text(
            encoding="utf-8"
        )
    )
    preflight = next(item for item in manifest["stages"] if item["id"] == "preflight")
    assert preflight["status"] == "blocked"
    assert preflight["error"]["type"] == "SourceError"


def test_copy_verifies_and_proves_idempotency(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    source = FakeSource(_source_objects(entries))
    transport = FakeTransport(entries)

    payload = _run(
        tmp_path,
        operation_id="copy-ok",
        contract=contract,
        catalog_path=catalog_path,
        source=source,
        transport=transport,
        through="copy",
    )

    assert payload["status"] == "completed"
    assert transport.copy_calls == [True, False, False]
    idempotency = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    assert idempotency["markers"] == {"=": 3}
    assert idempotency["objects_written"] == 0
    assert idempotency["combined_sha256"] == sha256_file(
        tmp_path / "data/operations/gcs_migration/copy-ok/idempotency-combined.txt"
    )
    manifest = Path(payload["manifest_path"]).read_text(encoding="utf-8")
    assert TOKEN not in manifest
    assert "operator@example.invalid" not in manifest


def test_dry_run_accepts_only_an_already_verified_sentinel(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    existing = [
        SourceObject(
            item.destination_locator,
            item.size_bytes,
            provider_hashes={"md5": item.provider_hashes["md5"]},
        )
        for item in entries
    ]
    source = FakeSource(_source_objects(entries))
    transport = FakeTransport(entries, existing=existing)

    payload = _run(
        tmp_path,
        operation_id="dry-compatible",
        contract=contract,
        catalog_path=catalog_path,
        source=source,
        transport=transport,
        through="dry-run",
    )

    result = json.loads(Path(payload["artifact_path"]).read_text(encoding="utf-8"))
    assert result["destination_status"] == "sentinel_already_verified"
    assert result["markers"] == {"=": 3}


def test_dry_run_blocks_conflicting_destination(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    transport = FakeTransport(entries, existing=[SourceObject("data/raw/v1/conflict", 1)])

    with pytest.raises(GcsMigrationError, match="destino GCS divergiu"):
        _run(
            tmp_path,
            operation_id="dry-conflict",
            contract=contract,
            catalog_path=catalog_path,
            source=FakeSource(_source_objects(entries)),
            transport=transport,
            through="dry-run",
        )


def test_ambiguous_copy_is_reconciled_only_when_destination_is_exact(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    transport = FakeTransport(entries, fail_after_copy=True)

    payload = _run(
        tmp_path,
        operation_id="copy-reconciled",
        contract=contract,
        catalog_path=catalog_path,
        source=FakeSource(_source_objects(entries)),
        transport=transport,
        through="copy",
    )

    assert payload["status"] == "completed"
    copy_result = json.loads(
        (tmp_path / "data/operations/gcs_migration/copy-reconciled/copy.json").read_text(
            encoding="utf-8"
        )
    )
    assert copy_result["status"] == "reconciled_after_error"


def test_ambiguous_copy_blocks_when_destination_cannot_be_reconciled(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)

    class UnreconciledTransport(FakeTransport):
        def copy_entries(self, *args, dry_run: bool, **kwargs):
            if dry_run:
                return super().copy_entries(*args, dry_run=True, **kwargs)
            raise GcsMigrationError("resultado remoto simulado como ambíguo")

    with pytest.raises(GcsMigrationError, match="ambíguo"):
        _run(
            tmp_path,
            operation_id="copy-blocked",
            contract=contract,
            catalog_path=catalog_path,
            source=FakeSource(_source_objects(entries)),
            transport=UnreconciledTransport(entries),
            through="copy",
        )

    manifest = json.loads(
        (tmp_path / "data/operations/gcs_migration/copy-blocked/operation.json").read_text(
            encoding="utf-8"
        )
    )
    copy_stage = next(item for item in manifest["stages"] if item["id"] == "copy")
    assert copy_stage["status"] == "blocked"
    assert copy_stage["remote_result_ambiguous"] is True


def test_changed_artifact_is_rebuilt_and_changed_config_is_rejected(tmp_path: Path) -> None:
    contract, catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    source = FakeSource(_source_objects(entries))
    transport = FakeTransport(entries)
    first = _run(
        tmp_path,
        operation_id="resume",
        contract=contract,
        catalog_path=catalog_path,
        source=source,
        transport=transport,
        through="preflight",
    )
    Path(first["artifact_path"]).write_text("changed", encoding="utf-8")

    second = _run(
        tmp_path,
        operation_id="resume",
        contract=contract,
        catalog_path=catalog_path,
        source=source,
        transport=transport,
        through="preflight",
    )
    assert second["status"] == "completed"
    assert source.list_calls == 2

    with pytest.raises(OperationError, match="entrada ou configuração diferente"):
        _run(
            tmp_path,
            operation_id="resume",
            contract=contract.model_copy(update={"region": "us-central1"}),
            catalog_path=catalog_path,
            source=source,
            transport=transport,
            through="preflight",
        )


def test_impersonation_command_is_explicit_and_token_is_not_an_argument() -> None:
    provider = GcloudImpersonatedTokenProvider(
        project_id="falando-nela-pedblan",
        service_account="fn-migrator@falando-nela-pedblan.iam.gserviceaccount.com",
        operator_account="operator@example.invalid",
        executable="true",
    )

    command = provider.command()

    assert "--project=falando-nela-pedblan" in command
    assert (
        "--impersonate-service-account=fn-migrator@falando-nela-pedblan.iam.gserviceaccount.com"
        in command
    )
    assert TOKEN not in command
    assert "config" not in command


def test_rclone_receives_token_only_in_environment_and_cannot_mutate_bucket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "rclone.conf"
    config_path.write_text("[raw-source-ro]\ntype = drive\n", encoding="utf-8")
    entry = _entry(1, "metadata")
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command, **kwargs):
        environment = kwargs["env"]
        calls.append((list(command), dict(environment)))
        combined = Path(command[command.index("--combined") + 1])
        combined.write_text(f"+ {entry.source_locator}\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transport = RcloneGcsTransport(
        config_path=config_path,
        source_remote="raw-source-ro",
        source_folder_id=RAW_FOLDER_ID,
        source_prefix="v1",
        project_id="falando-nela-pedblan",
        project_number="818569314985",
        region="southamerica-east1",
        bucket="falando-nela-pedblan-data",
        raw_prefix="data/raw/v1",
        access_token=lambda: TOKEN,
        transfers=8,
        retries=2,
        low_level_retries=3,
        executable="rclone",
    )
    files_from = tmp_path / "files.bin"
    combined = tmp_path / "combined.txt"

    transport.copy_entries(
        [entry],
        files_from_path=files_from,
        combined_path=combined,
        dry_run=True,
    )

    command, environment = calls[0]
    assert command[1] == "copy"
    assert TOKEN not in command
    assert environment["RCLONE_CONFIG_GCSTARGET_ACCESS_TOKEN"] == TOKEN
    assert environment["RCLONE_CONFIG_GCSTARGET_PROJECT_NUMBER"] == "818569314985"
    assert environment["RCLONE_CONFIG_GCSTARGET_ENV_AUTH"] == "false"
    assert environment["CLOUDSDK_CORE_PROJECT"] == "falando-nela-pedblan"
    assert environment["GOOGLE_CLOUD_PROJECT"] == "falando-nela-pedblan"
    assert "gcstarget:falando-nela-pedblan-data/data/raw/v1" in command
    assert f"raw-source-ro,root_folder_id={RAW_FOLDER_ID}:v1" in command
    assert {"--immutable", "--checksum", "--check-first", "--dry-run"} <= set(command)
    assert command[command.index("--transfers") + 1] == "8"
    assert command[command.index("--retries") + 1] == "2"
    assert command[command.index("--low-level-retries") + 1] == "3"
    assert not {"sync", "move", "delete", "purge", "mkdir"} & set(command)
    assert TOKEN not in json.dumps(transport.descriptor())


def test_failed_token_generation_redacts_subprocess_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = GcloudImpersonatedTokenProvider(
        project_id="falando-nela-pedblan",
        service_account="fn-migrator@falando-nela-pedblan.iam.gserviceaccount.com",
        operator_account="operator@example.invalid",
        executable="true",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, TOKEN, TOKEN),
    )

    with pytest.raises(GcsMigrationError) as captured:
        provider()

    assert TOKEN not in str(captured.value)


def test_implementation_has_no_global_auth_or_destructive_gcp_commands() -> None:
    implementation = (REPO_ROOT / "src/falando_nela/gcs_migration.py").read_text(encoding="utf-8")
    implementation += (REPO_ROOT / "src/falando_nela/gcs_full_migration.py").read_text(
        encoding="utf-8"
    )
    implementation += (REPO_ROOT / "src/falando_nela/cli.py").read_text(encoding="utf-8")

    assert "application-default login" not in implementation
    assert "gcloud config set project" not in implementation
    assert "service-accounts keys create" not in implementation


def test_real_catalog_hash_and_frozen_sentinels_match_when_local_evidence_exists() -> None:
    catalog = (
        REPO_ROOT
        / "data_samples/operations/organize_drive"
        / "r03-drive-copy-batched-20260803/copy-catalog.jsonl"
    )
    if not catalog.exists():
        pytest.skip("catálogo operacional ignorado pelo Git não está presente")

    contract = load_gcp_contract(CONFIG_PATH)

    assert sha256_file(catalog) == contract.migration.source_catalog_file_sha256
    assert sum(1 for _line in catalog.open(encoding="utf-8")) == 2_887
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == (
        "cabe9aae5071d25bdae6459b99064d2ed37110ffaed0c30b95867dd798d22319"
    )


@pytest.mark.parametrize("mode", ["unapproved_zero", "nonempty_without_sha256"])
def test_catalog_rejects_incomplete_or_unapproved_hashes(tmp_path: Path, mode: str) -> None:
    contract, _catalog_path, entries = _fixture_contract_and_catalog(tmp_path)
    invalid = (
        CatalogEntry(
            category="monthly_text",
            source_locator="camara/outro/ano=2000/mes=01/vazio.jsonl",
            destination_locator="data/raw/v1/camara/outro/ano=2000/mes=01/vazio.jsonl",
            size_bytes=0,
            provider_hashes={"md5": EMPTY_MD5},
        )
        if mode == "unapproved_zero"
        else CatalogEntry(
            category="monthly_text",
            source_locator="camara/outro/ano=2000/mes=01/incompleto.jsonl",
            destination_locator="data/raw/v1/camara/outro/ano=2000/mes=01/incompleto.jsonl",
            size_bytes=10,
            provider_hashes={"md5": "a" * 32},
        )
    )
    catalog_path = tmp_path / "catalog-with-zero.jsonl"
    catalog_entries = [*entries, invalid]
    catalog_path.write_bytes(
        b"".join(canonical_json_bytes(item.as_dict()) + b"\n" for item in catalog_entries)
    )
    migration = contract.migration.model_copy(
        update={
            "source_files": len(catalog_entries),
            "source_bytes": sum(item.size_bytes for item in catalog_entries),
            "source_catalog_file_sha256": sha256_file(catalog_path),
        }
    )

    with pytest.raises(GcsMigrationError, match="catálogo de origem é inválido"):
        load_source_catalog(catalog_path, contract.model_copy(update={"migration": migration}))
