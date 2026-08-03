from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from falando_nela.cli import _print_progress, build_parser, main
from falando_nela.drive_organizer import (
    CANONICAL_PREFIX,
    CopyConflict,
    CopyResultAmbiguous,
    LayoutError,
    RcloneCopyTransport,
    build_copy_execution_plan,
    build_copy_plan,
    classify_raw_locator,
    destination_matches,
    execute_drive_copy,
    execute_drive_dry_run,
    plan_drive_organization,
    reconcile_drive_inventory,
    validate_rclone_destination_config,
    write_copy_plan,
)
from falando_nela.raw import sha256_file
from falando_nela.sources import RcloneConfigSnapshot, SourceError, SourceObject

SOURCE_FOLDER_ID = "source-folder-id"
DESTINATION_FOLDER_ID = "destination-folder-id"
SENTINEL_TOKEN = "TOKEN-SENTINELA-NAO-PODE-VAZAR"


def test_drive_plan_defaults_match_operational_remotes() -> None:
    args = build_parser().parse_args(
        [
            "drive-organize",
            "plan",
            "--operation-id",
            "org-defaults",
            "--baseline-csv",
            "g01.csv",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            SOURCE_FOLDER_ID,
            "--destination-folder-id",
            DESTINATION_FOLDER_ID,
        ]
    )

    assert args.source_remote == "raw-source-ro"
    assert args.destination_remote == "raw-destination-rw"

    reconcile_args = build_parser().parse_args(
        [
            "drive-organize",
            "reconcile",
            "--operation-id",
            "org-reconcile-defaults",
            "--baseline-csv",
            "g01.csv",
            "--provider-identity-map",
            "provider-identity-map.json",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            SOURCE_FOLDER_ID,
        ]
    )
    assert reconcile_args.source_remote == "raw-source-ro"

    dry_run_args = build_parser().parse_args(
        [
            "drive-organize",
            "dry-run",
            "--operation-id",
            "org-dry-run-defaults",
            "--reconciliation-manifest",
            "operation.json",
            "--source-inventory",
            "source-inventory.jsonl",
            "--source-reconciliation",
            "source-reconciliation.json",
            "--provider-identity-map",
            "provider-identity-map.json",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            SOURCE_FOLDER_ID,
            "--destination-folder-id",
            DESTINATION_FOLDER_ID,
        ]
    )
    assert dry_run_args.source_remote == "raw-source-ro"
    assert dry_run_args.destination_remote == "raw-destination-rw"

    copy_args = build_parser().parse_args(
        [
            "drive-organize",
            "copy",
            "--operation-id",
            "org-copy-defaults",
            "--source-inventory",
            "source-inventory.jsonl",
            "--dry-run-operation-root",
            "operations/dry-run",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            SOURCE_FOLDER_ID,
            "--destination-folder-id",
            DESTINATION_FOLDER_ID,
        ]
    )
    assert copy_args.source_remote == "raw-source-ro"
    assert copy_args.destination_remote == "raw-destination-rw"
    assert copy_args.through == "sentinel"

    sample_args = build_parser().parse_args(
        [
            "sample",
            "pilot",
            "--operation-id",
            "sample-defaults",
            "--copy-catalog-summary",
            "copy-catalog-summary.json",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            DESTINATION_FOLDER_ID,
            "--confirm-source-folder-id",
            DESTINATION_FOLDER_ID,
        ]
    )
    assert sample_args.source_remote == "raw-source-ro"


@pytest.mark.parametrize(
    "locator",
    [
        "camara/plenario_discursos/ano=2010/mes=01/run.jsonl",
        "camara/ccjc_eventos/ano=2024/mes=07/run.jsonl.gz",
        "camara/pareceres_pec/ano=2024/mes=07/run.jsonl",
        "senado/plenario_discursos/ano=2010/mes=02/run.jsonl",
        "senado/congresso_discursos/ano=2024/mes=07/run.jsonl",
        "senado/ccj_notas/ano=2024/mes=07/run.jsonl",
        "senado/pareceres_pec/ano=2024/mes=07/run.jsonl",
    ],
)
def test_classifies_monthly_text_for_plenary_and_commissions(locator: str) -> None:
    classification = classify_raw_locator(locator)

    assert classification is not None
    assert classification.category == "monthly_text"
    assert classification.periodicity == "monthly"


@pytest.mark.parametrize(
    ("locator", "category"),
    [
        ("camara/plenario_apartes/metadata/run.jsonl", "metadata"),
        ("senado/plenario_apartes/metadata/run.jsonl", "metadata"),
        ("senado/plenario_discursos/transcription_queue/run.jsonl", "transcription_queue"),
        ("senado/ccj_notas/metadata/run.jsonl", "metadata"),
        ("camara/parlamentares/metadata/run.jsonl", "metadata"),
        ("senado/parlamentares/metadata/run.jsonl", "metadata"),
    ],
)
def test_preserves_source_defined_metadata_and_queue(locator: str, category: str) -> None:
    classification = classify_raw_locator(locator)

    assert classification is not None
    assert classification.category == category
    assert classification.periodicity == "source_defined"


@pytest.mark.parametrize(
    "locator",
    [
        "../senado/plenario_discursos/ano=2010/mes=01/run.jsonl",
        "senado/plenario_discursos/run.jsonl",
        "senado/plenario_discursos/ano=2010/mes=13/run.jsonl",
        "senado/plenario_discursos/ano=2010/mes=01/run.csv",
        "senado/plenario_apartes/ano=2010/mes=01/run.jsonl",
    ],
)
def test_rejects_unsafe_or_non_contract_paths(locator: str) -> None:
    with pytest.raises(LayoutError):
        classify_raw_locator(locator)


def test_out_of_scope_dataset_is_explicitly_excluded() -> None:
    assert classify_raw_locator("controle/inventarios/ano=2010/run.jsonl") is None
    with pytest.raises(LayoutError, match="fora do escopo explícito"):
        classify_raw_locator("senado/outra_base/ano=2010/mes=01/run.jsonl")


def test_copy_plan_preserves_path_under_versioned_prefix(tmp_path: Path) -> None:
    objects = [
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=02/run.jsonl",
            100,
            provider_hashes={"md5": "abc"},
        ),
        SourceObject("fora/escopo/metadata/run.jsonl", 5),
    ]

    plan = build_copy_plan(objects)
    jsonl_path = tmp_path / "copy-plan.jsonl"
    summary_path = tmp_path / "copy-plan-summary.json"
    write_copy_plan(plan, jsonl_path=jsonl_path, summary_path=summary_path)

    assert plan.files == 1
    assert plan.bytes == 100
    assert plan.entries[0].destination_locator == (
        f"{CANONICAL_PREFIX}/senado/plenario_discursos/ano=2010/mes=02/run.jsonl"
    )
    assert plan.excluded_out_of_scope == ("fora/escopo/metadata/run.jsonl",)
    assert plan.excluded_files == 1
    assert plan.excluded_entries[0].decision == "exclude_out_of_scope"
    assert json.loads(jsonl_path.read_text(encoding="utf-8"))["decision"] == "copy_immutable"
    assert json.loads(summary_path.read_text(encoding="utf-8"))["categories"] == {"monthly_text": 1}


def test_copy_plan_rejects_duplicate_source_locator() -> None:
    item = SourceObject("senado/ccj_notas/metadata/run.jsonl", 10)
    with pytest.raises(LayoutError, match="duplicado"):
        build_copy_plan([item, item])


def _redacted_rclone_config(*, destination_scope: str = "drive.file") -> str:
    return "\n".join(
        [
            "[raw-source-ro]",
            "type = drive",
            "scope = drive.readonly",
            "root_folder_id = XXX",
            "token = XXX",
            "[raw-destination-rw]",
            "type = drive",
            f"scope = {destination_scope}",
            "root_folder_id = XXX",
            "token = XXX",
        ]
    )


def _write_rclone_config(path: Path) -> None:
    path.write_text("RCLONE_ENCRYPT_V0:\nconteudo-cifrado", encoding="utf-8")
    path.chmod(0o600)


def _snapshot(path: Path, *, destination_scope: str = "drive.file") -> RcloneConfigSnapshot:
    return RcloneConfigSnapshot(
        path.resolve(),
        _redacted_rclone_config(destination_scope=destination_scope),
    )


def _transport(config: Path) -> RcloneCopyTransport:
    return RcloneCopyTransport(
        config_path=config,
        source_remote="raw-source-ro",
        source_folder_id=SOURCE_FOLDER_ID,
        destination_remote="raw-destination-rw",
        destination_folder_id=DESTINATION_FOLDER_ID,
        executable="true",
        config_snapshot=_snapshot(config),
    )


def test_destination_config_requires_minimal_writable_scope(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    validate_rclone_destination_config(
        _redacted_rclone_config(),
        remote="raw-destination-rw",
        expected_folder_id=DESTINATION_FOLDER_ID,
    )
    with pytest.raises(SourceError, match="drive.file"):
        validate_rclone_destination_config(
            _redacted_rclone_config(destination_scope="drive"),
            remote="raw-destination-rw",
            expected_folder_id=DESTINATION_FOLDER_ID,
        )
    with pytest.raises(SourceError, match="root_folder_id"):
        validate_rclone_destination_config(
            _redacted_rclone_config().replace(
                "scope = drive.file\nroot_folder_id = XXX",
                "scope = drive.file\nroot_folder_id = other-folder-id",
            ),
            remote="raw-destination-rw",
            expected_folder_id=DESTINATION_FOLDER_ID,
        )


def test_copy_command_is_immutable_dry_run_and_contains_no_token(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    transport = _transport(config)
    entry = build_copy_plan(
        [
            SourceObject(
                "senado/plenario_discursos/ano=2010/mes=02/run.jsonl",
                100,
                provider_hashes={"md5": "abc"},
            )
        ]
    ).entries[0]

    command = transport.copy_command(entry, dry_run=True)

    assert command[1] == "copyto"
    assert command[2].startswith(f"raw-source-ro,root_folder_id={SOURCE_FOLDER_ID}:")
    assert command[3].startswith(f"raw-destination-rw,root_folder_id={DESTINATION_FOLDER_ID}:")
    assert "--immutable" in command
    assert "--dry-run" in command
    assert "--server-side-across-configs" not in command
    assert "--ask-password=false" in command
    assert all(forbidden not in command for forbidden in ("sync", "move", "delete", "purge"))
    assert SENTINEL_TOKEN not in " ".join(command)

    files_from = tmp_path / "files.bin"
    combined = tmp_path / "combined.txt"
    aggregate = transport.dry_run_command(
        files_from_path=files_from,
        combined_path=combined,
    )
    assert aggregate[1] == "copy"
    assert aggregate[2] == f"raw-source-ro,root_folder_id={SOURCE_FOLDER_ID}:"
    assert aggregate[3] == (
        f"raw-destination-rw,root_folder_id={DESTINATION_FOLDER_ID}:{CANONICAL_PREFIX}"
    )
    for required in (
        "--files-from0",
        "--combined",
        "--dry-run",
        "--immutable",
        "--checksum",
        "--check-first",
    ):
        assert required in aggregate
    assert aggregate[aggregate.index("--retries") + 1] == "1"
    assert all(forbidden not in aggregate for forbidden in ("sync", "move", "delete", "purge"))
    batch = transport.copy_batch_command(
        files_from_path=files_from,
        combined_path=combined,
    )
    assert batch[1] == "copy"
    assert "--files-from0" in batch
    assert "--immutable" in batch
    assert "--checksum" in batch
    assert batch[batch.index("--transfers") + 1] == "4"
    assert "--server-side-across-configs" not in batch


def test_copy_error_and_destination_verification_do_not_accept_weak_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    transport = _transport(config)
    entry = build_copy_plan(
        [
            SourceObject(
                "senado/ccj_notas/metadata/run.jsonl",
                100,
                provider_hashes={"md5": "abc"},
            )
        ]
    ).entries[0]

    def failed_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 9, "", f"falha com {SENTINEL_TOKEN}")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(SourceError) as captured:
        transport.execute_copy(entry, dry_run=False)
    assert SENTINEL_TOKEN not in str(captured.value)

    assert (
        destination_matches(
            entry,
            SourceObject(entry.destination_locator, 100, provider_hashes={}),
        )
        is False
    )
    assert (
        destination_matches(
            entry,
            SourceObject(entry.destination_locator, 100, provider_hashes={"md5": "other"}),
        )
        is False
    )
    assert (
        destination_matches(
            entry,
            SourceObject(entry.destination_locator, 100, provider_hashes={"md5": "abc"}),
        )
        is True
    )


class _FakeSource:
    def __init__(self, objects: list[SourceObject]) -> None:
        self.objects = objects
        self.list_calls = 0

    def descriptor(self) -> dict[str, str]:
        return {"kind": "fixture", "root": "fixture-raw"}

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
        assert prefix == ""
        self.list_calls += 1
        return self.objects


class _FakeTransport:
    destination_remote = "raw-destination-rw"

    def __init__(self, entries: int = 0) -> None:
        self.entries = entries
        self.list_calls = 0

    def destination_entry_count(self) -> int:
        self.list_calls += 1
        return self.entries


class _FakeDryRunTransport:
    source_remote = "raw-source-ro"
    destination_remote = "raw-destination-rw"

    def __init__(self) -> None:
        self.list_calls = 0
        self.dry_run_calls = 0

    def destination_entry_count(self) -> int:
        self.list_calls += 1
        return 0

    def execute_dry_run(
        self,
        entries: tuple[object, ...],
        *,
        files_from_path: Path,
        combined_path: Path,
    ) -> dict[str, object]:
        self.dry_run_calls += 1
        assert files_from_path.read_bytes().endswith(b"\0")
        typed_entries = list(entries)
        combined_path.write_text(
            "".join(f"+ {entry.source_locator}\n" for entry in typed_entries),  # type: ignore[attr-defined]
            encoding="utf-8",
        )
        return {
            "files": len(typed_entries),
            "bytes": sum(entry.size_bytes for entry in typed_entries),  # type: ignore[attr-defined]
            "markers": {"+": len(typed_entries), "=": 0, "-": 0, "*": 0, "!": 0},
            "return_code": 0,
            "combined_path": str(combined_path),
            "combined_sha256": sha256_file(combined_path),
            "combined_bytes": combined_path.stat().st_size,
        }


def _write_baseline(path: Path, objects: list[SourceObject]) -> None:
    rows = ["item_type,relative_path,size_bytes"]
    rows.extend(f"file,{item.locator},{item.size_bytes}" for item in objects)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_identity_map(
    path: Path,
    *,
    baseline: Path,
    provider_id: str,
    locator: str,
    size_bytes: int,
    content_sha256: str,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_folder_id": SOURCE_FOLDER_ID,
                "baseline_file_id": "baseline-file-id",
                "baseline_sha256": sha256_file(baseline),
                "groups": [
                    {
                        "group_id": "unsupported-item",
                        "observed_locator": locator,
                        "provider_ids": [provider_id],
                        "baseline_locators": [locator],
                        "size_bytes": size_bytes,
                        "sha256": content_sha256,
                        "decision": "exclude_unsupported_format",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_drive_reconciliation_is_recoverable_and_preserves_provider_id(
    tmp_path: Path,
) -> None:
    content_sha256 = "a" * 64
    locator = "camara/plenario_discursos/metadata/Untitled0.ipynb"
    objects = [
        SourceObject(
            locator,
            324,
            provider_hashes={"sha256": content_sha256},
            provider_id="drive-item-id",
        ),
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=02/run.jsonl",
            100,
            provider_id="raw-item-id",
        ),
    ]
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, objects)
    identity_map = tmp_path / "provider-identity-map.json"
    _write_identity_map(
        identity_map,
        baseline=baseline,
        provider_id="drive-item-id",
        locator=locator,
        size_bytes=324,
        content_sha256=content_sha256,
    )
    source = _FakeSource(objects)
    data_root = tmp_path / "data"

    first = reconcile_drive_inventory(
        source=source,
        baseline_csv=baseline,
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="org-reconcile-001",
        source_folder_id=SOURCE_FOLDER_ID,
    )
    second = reconcile_drive_inventory(
        source=source,
        baseline_csv=baseline,
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="org-reconcile-001",
        source_folder_id=SOURCE_FOLDER_ID,
    )

    assert first == second
    assert first["status"] == "completed"
    assert first["files"] == 2
    assert first["provider_ids_reconciled"] == 1
    assert source.list_calls == 1
    inventory = Path(str(first["inventory_path"])).read_text(encoding="utf-8")
    assert "drive-item-id" in inventory

    Path(str(first["reconciliation_path"])).write_text("adulterado", encoding="utf-8")
    reconcile_drive_inventory(
        source=source,
        baseline_csv=baseline,
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="org-reconcile-001",
        source_folder_id=SOURCE_FOLDER_ID,
    )
    assert source.list_calls == 1


def test_integral_dry_run_reuses_reconciliation_and_is_recoverable(tmp_path: Path) -> None:
    content_sha256 = "a" * 64
    excluded_locator = "camara/plenario_discursos/metadata/Untitled0.ipynb"
    raw_locator = "senado/plenario_discursos/ano=2010/mes=02/run.jsonl"
    objects = [
        SourceObject(
            excluded_locator,
            324,
            provider_hashes={"sha256": content_sha256},
            provider_id="drive-item-id",
        ),
        SourceObject(raw_locator, 100, provider_id="raw-item-id"),
    ]
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, objects)
    identity_map = tmp_path / "provider-identity-map.json"
    _write_identity_map(
        identity_map,
        baseline=baseline,
        provider_id="drive-item-id",
        locator=excluded_locator,
        size_bytes=324,
        content_sha256=content_sha256,
    )
    data_root = tmp_path / "data"
    reconciliation = reconcile_drive_inventory(
        source=_FakeSource(objects),
        baseline_csv=baseline,
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="org-reconcile-for-dry-run",
        source_folder_id=SOURCE_FOLDER_ID,
    )
    transport = _FakeDryRunTransport()
    arguments = {
        "transport": transport,
        "reconciliation_manifest_path": Path(str(reconciliation["manifest_path"])),
        "source_inventory_path": Path(str(reconciliation["inventory_path"])),
        "source_reconciliation_path": Path(str(reconciliation["reconciliation_path"])),
        "provider_identity_map_path": identity_map,
        "data_root": data_root,
        "operation_id": "org-dry-run-001",
        "source_folder_id": SOURCE_FOLDER_ID,
        "destination_folder_id": DESTINATION_FOLDER_ID,
    }

    first = execute_drive_dry_run(**arguments)  # type: ignore[arg-type]
    second = execute_drive_dry_run(**arguments)  # type: ignore[arg-type]

    assert first == second
    assert first["status"] == "completed"
    assert first["files"] == 1
    assert first["bytes"] == 100
    assert first["excluded_files"] == 1
    assert first["destination_entries_after"] == 0
    assert transport.dry_run_calls == 1
    assert transport.list_calls == 2
    summary = json.loads(Path(str(first["copy_plan_summary_path"])).read_text(encoding="utf-8"))
    assert summary["excluded"] == [
        {
            "decision": "exclude_unsupported_format",
            "provider_id": "drive-item-id",
            "size_bytes": 324,
            "source_locator": excluded_locator,
        }
    ]

    Path(str(first["combined_path"])).write_text("adulterado\n", encoding="utf-8")
    execute_drive_dry_run(**arguments)  # type: ignore[arg-type]
    assert transport.dry_run_calls == 2
    assert transport.list_calls == 4


def test_plan_operation_is_recoverable_and_skips_completed_remote_reads(tmp_path: Path) -> None:
    objects = [
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=02/run.jsonl",
            100,
            provider_hashes={"MD5": "abc"},
        ),
        SourceObject("senado/plenario_apartes/metadata/run.jsonl", 20),
    ]
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, objects)
    source = _FakeSource(objects)
    transport = _FakeTransport()
    data_root = tmp_path / "data"

    first = plan_drive_organization(
        source=source,
        transport=transport,  # type: ignore[arg-type]
        baseline_csv=baseline,
        data_root=data_root,
        operation_id="org-001",
        source_folder_id=SOURCE_FOLDER_ID,
        destination_folder_id=DESTINATION_FOLDER_ID,
    )
    second = plan_drive_organization(
        source=source,
        transport=transport,  # type: ignore[arg-type]
        baseline_csv=baseline,
        data_root=data_root,
        operation_id="org-001",
        source_folder_id=SOURCE_FOLDER_ID,
        destination_folder_id=DESTINATION_FOLDER_ID,
    )

    assert first == second
    assert first["status"] == "completed"
    assert first["files"] == 2
    assert source.list_calls == 1
    assert transport.list_calls == 1
    manifest = json.loads(Path(str(first["manifest_path"])).read_text(encoding="utf-8"))
    assert manifest["implementation_version"] == "r03-drive-organization-v2"
    assert manifest["configuration"]["destination_scope"] == "drive.file"
    assert manifest["configuration"]["transfer_mode"] == "client_streaming"

    Path(str(first["inventory_path"])).write_text("adulterado", encoding="utf-8")
    plan_drive_organization(
        source=source,
        transport=transport,  # type: ignore[arg-type]
        baseline_csv=baseline,
        data_root=data_root,
        operation_id="org-001",
        source_folder_id=SOURCE_FOLDER_ID,
        destination_folder_id=DESTINATION_FOLDER_ID,
    )
    assert source.list_calls == 2
    assert transport.list_calls == 1


def test_plan_operation_blocks_nonempty_destination(tmp_path: Path) -> None:
    objects = [SourceObject("senado/ccj_notas/metadata/run.jsonl", 10)]
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, objects)

    with pytest.raises(CopyConflict, match="não está vazia"):
        plan_drive_organization(
            source=_FakeSource(objects),
            transport=_FakeTransport(entries=1),  # type: ignore[arg-type]
            baseline_csv=baseline,
            data_root=tmp_path / "data",
            operation_id="org-nonempty",
            source_folder_id=SOURCE_FOLDER_ID,
            destination_folder_id=DESTINATION_FOLDER_ID,
        )


def test_copy_entry_reconciles_before_retry_and_never_overwrites(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    transport = _transport(config)
    entry = build_copy_plan(
        [
            SourceObject(
                "senado/ccj_notas/metadata/run.jsonl",
                100,
                provider_hashes={"MD5": "abc"},
            )
        ]
    ).entries[0]
    matching = SourceObject(
        entry.destination_locator,
        100,
        provider_hashes={"MD5": "abc"},
    )
    calls: list[bool] = []

    transport.destination_stat = lambda _entry: matching  # type: ignore[method-assign]
    transport.execute_copy = (  # type: ignore[method-assign]
        lambda _entry, *, dry_run: calls.append(dry_run) or {}
    )
    assert transport.copy_entry(entry, dry_run=False)["status"] == "reused_verified"
    assert calls == []

    divergent = SourceObject(
        entry.destination_locator,
        100,
        provider_hashes={"MD5": "other"},
    )
    transport.destination_stat = lambda _entry: divergent  # type: ignore[method-assign]
    with pytest.raises(CopyConflict, match="diverge"):
        transport.copy_entry(entry, dry_run=False)


def test_copy_entry_reconciles_ambiguous_remote_result(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    transport = _transport(config)
    entry = build_copy_plan(
        [
            SourceObject(
                "senado/ccj_notas/metadata/run.jsonl",
                100,
                provider_hashes={"MD5": "abc"},
            )
        ]
    ).entries[0]
    matching = SourceObject(
        entry.destination_locator,
        100,
        provider_hashes={"MD5": "abc"},
    )
    observed: list[SourceObject | None] = [None, matching]
    transport.destination_stat = lambda _entry: observed.pop(0)  # type: ignore[method-assign]

    def ambiguous_copy(_entry: object, *, dry_run: bool) -> dict[str, object]:
        assert dry_run is False
        raise SourceError("falha segura")

    transport.execute_copy = ambiguous_copy  # type: ignore[method-assign]
    assert transport.copy_entry(entry, dry_run=False)["status"] == "reconciled_after_error"

    observed = [None, None]
    with pytest.raises(CopyResultAmbiguous):
        transport.copy_entry(entry, dry_run=False)


def test_cli_failure_is_nonzero_and_does_not_echo_rclone_token(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    repo_root.mkdir()
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, [SourceObject("senado/ccj_notas/metadata/run.jsonl", 10)])
    config = tmp_path / "rclone.conf"
    _write_rclone_config(config)
    invalid_snapshot = RcloneConfigSnapshot(
        config.resolve(),
        _redacted_rclone_config().replace("drive.readonly", "drive"),
    )
    monkeypatch.setattr("falando_nela.cli.inspect_rclone_config", lambda *_args: invalid_snapshot)
    monkeypatch.setattr(shutil, "which", lambda _executable: "/usr/bin/true")

    return_code = main(
        [
            "drive-organize",
            "plan",
            "--operation-id",
            "org-cli",
            "--baseline-csv",
            str(baseline),
            "--rclone-config",
            str(config),
            "--source-folder-id",
            SOURCE_FOLDER_ID,
            "--destination-folder-id",
            DESTINATION_FOLDER_ID,
            "--repo-root",
            str(repo_root),
            "--data-root",
            str(data_root),
        ]
    )

    captured = capsys.readouterr()
    assert return_code == 2
    assert "drive.readonly" in captured.err
    assert SENTINEL_TOKEN not in captured.err
    assert "Traceback" not in captured.err


def test_progress_event_is_json_on_stderr_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    event = {"event": "progress", "stage": "copy_batches", "completed_files": 12}

    _print_progress(event)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == event


def test_copy_execution_plan_selects_three_categories_and_bounded_batches() -> None:
    objects = [
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=02/a.jsonl",
            8,
            provider_hashes={"MD5": "a"},
        ),
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=03/b.jsonl",
            20,
            provider_hashes={"MD5": "b"},
        ),
        SourceObject(
            "senado/plenario_discursos/metadata/c.jsonl",
            4,
            provider_hashes={"MD5": "c"},
        ),
        SourceObject(
            "senado/plenario_discursos/transcription_queue/d.jsonl",
            6,
            provider_hashes={"MD5": "d"},
        ),
        SourceObject(
            "senado/ccj_notas/ano=2010/mes=01/e.jsonl",
            30,
            provider_hashes={"MD5": "e"},
        ),
    ]

    execution = build_copy_execution_plan(
        build_copy_plan(objects), batch_max_files=1, batch_max_bytes=25
    )

    assert execution["sentinel"]["files"] == 3
    assert execution["sentinel"]["bytes"] == 18
    assert [batch["files"] for batch in execution["batches"]] == [1, 1]
    assert [batch["bytes"] for batch in execution["batches"]] == [30, 20]


class _FakeCopyExecutionTransport:
    source_remote = "raw-source-ro"
    destination_remote = "raw-destination-rw"

    def __init__(
        self,
        source_objects: list[SourceObject],
        *,
        fail_batch_once: bool = False,
    ) -> None:
        self.objects: dict[str, SourceObject] = {}
        self.copy_calls = 0
        self.batch_calls = 0
        self.fail_batch_once = fail_batch_once
        self.entries_by_source = {
            entry.source_locator: entry
            for entry in build_copy_plan(
                [item for item in source_objects if item.locator.endswith(".jsonl")]
            ).entries
        }

    def destination_inventory(self) -> list[SourceObject]:
        return sorted(self.objects.values(), key=lambda item: item.locator)

    def destination_stat(self, entry: object) -> SourceObject | None:
        return self.objects.get(entry.destination_locator)  # type: ignore[attr-defined]

    def copy_entry(self, entry: object, *, dry_run: bool) -> dict[str, object]:
        assert not dry_run
        self.copy_calls += 1
        copied = SourceObject(
            entry.destination_locator,  # type: ignore[attr-defined]
            entry.size_bytes,  # type: ignore[attr-defined]
            provider_hashes=entry.provider_hashes,  # type: ignore[attr-defined]
        )
        self.objects[copied.locator] = copied
        return {
            "source_locator": entry.source_locator,  # type: ignore[attr-defined]
            "destination_locator": entry.destination_locator,  # type: ignore[attr-defined]
            "status": "copied_verified",
            "dry_run": False,
        }

    def execute_copy_batch(
        self,
        *,
        files_from_path: Path,
        combined_path: Path,
    ) -> dict[str, object]:
        self.batch_calls += 1
        locators = [
            item.decode("utf-8") for item in files_from_path.read_bytes().split(b"\0") if item
        ]
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        if self.fail_batch_once:
            self.fail_batch_once = False
            combined_path.write_text("")
            return {
                "return_code": 1,
                "combined_path": str(combined_path),
                "combined_sha256": sha256_file(combined_path),
                "combined_bytes": 0,
            }
        combined_path.write_text("".join(f"+ {locator}\n" for locator in locators))
        for locator in locators:
            self.copy_entry(self.entries_by_source[locator], dry_run=False)
        return {
            "return_code": 0,
            "combined_path": str(combined_path),
            "combined_sha256": sha256_file(combined_path),
            "combined_bytes": combined_path.stat().st_size,
        }


def test_drive_copy_stops_at_sentinel_then_resumes_all_without_duplicate_copy(
    tmp_path: Path,
) -> None:
    objects = [
        SourceObject(
            "controle.ipynb",
            3,
            provider_hashes={"sha256": "e" * 64},
            provider_id="excluded-id",
        ),
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=02/a.jsonl",
            8,
            provider_hashes={"MD5": "a"},
            provider_id="a-id",
        ),
        SourceObject(
            "senado/plenario_discursos/ano=2010/mes=03/b.jsonl",
            20,
            provider_hashes={"MD5": "b"},
            provider_id="b-id",
        ),
        SourceObject(
            "senado/plenario_discursos/metadata/c.jsonl",
            4,
            provider_hashes={"MD5": "c"},
            provider_id="c-id",
        ),
        SourceObject(
            "senado/plenario_discursos/transcription_queue/d.jsonl",
            6,
            provider_hashes={"MD5": "d"},
            provider_id="d-id",
        ),
    ]
    baseline = tmp_path / "g01.csv"
    _write_baseline(baseline, objects)
    identity_map = tmp_path / "provider-identity-map.json"
    _write_identity_map(
        identity_map,
        baseline=baseline,
        provider_id="excluded-id",
        locator="controle.ipynb",
        size_bytes=3,
        content_sha256="e" * 64,
    )
    data_root = tmp_path / "data"
    source = _FakeSource(objects)
    reconciliation = reconcile_drive_inventory(
        source=source,
        baseline_csv=baseline,
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="copy-reconciliation",
        source_folder_id=SOURCE_FOLDER_ID,
    )
    dry_run = execute_drive_dry_run(
        transport=_FakeDryRunTransport(),  # type: ignore[arg-type]
        reconciliation_manifest_path=Path(str(reconciliation["manifest_path"])),
        source_inventory_path=Path(str(reconciliation["inventory_path"])),
        source_reconciliation_path=Path(str(reconciliation["reconciliation_path"])),
        provider_identity_map_path=identity_map,
        data_root=data_root,
        operation_id="copy-dry-run",
        source_folder_id=SOURCE_FOLDER_ID,
        destination_folder_id=DESTINATION_FOLDER_ID,
    )
    transport = _FakeCopyExecutionTransport(objects, fail_batch_once=True)
    progress_events: list[dict[str, object]] = []
    arguments = {
        "transport": transport,
        "source": source,
        "source_inventory_path": Path(str(reconciliation["inventory_path"])),
        "dry_run_operation_root": Path(str(dry_run["manifest_path"])).parent,
        "data_root": data_root,
        "operation_id": "copy-real",
        "source_folder_id": SOURCE_FOLDER_ID,
        "destination_folder_id": DESTINATION_FOLDER_ID,
        "batch_max_files": 1,
        "batch_max_bytes": 25,
        "progress_callback": progress_events.append,
    }

    sentinel = execute_drive_copy(**arguments, through="sentinel")  # type: ignore[arg-type]
    assert sentinel["sentinel_files"] == 3
    assert transport.copy_calls == 3

    with pytest.raises(CopyResultAmbiguous, match="batch-0001.*missing=1"):
        execute_drive_copy(**arguments, through="all")  # type: ignore[arg-type]
    assert transport.copy_calls == 3
    assert transport.batch_calls == 1

    completed = execute_drive_copy(**arguments, through="all")  # type: ignore[arg-type]
    assert completed["status"] == "completed"
    assert transport.copy_calls == 4
    assert transport.batch_calls == 2
    assert Path(str(completed["catalog_summary_path"])).is_file()

    repeated = execute_drive_copy(**arguments, through="all")  # type: ignore[arg-type]
    assert repeated == completed
    assert transport.copy_calls == 4
    assert transport.batch_calls == 2
    assert {event["stage"] for event in progress_events} == {
        "copy_sentinel",
        "copy_batches",
    }
    assert any(event["status"] == "copied_verified" for event in progress_events)
