from __future__ import annotations

import ast
from pathlib import Path

import pytest

from falando_nela.cli import build_parser
from falando_nela.gcp_config import GcpConfigError, load_gcp_contract

REPO_ROOT = Path(__file__).parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "gcp.toml"


def test_versioned_contract_freezes_g01_targets_and_sentinel() -> None:
    contract = load_gcp_contract(CONFIG_PATH)

    assert contract.project_id == "falando-nela-pedblan"
    assert contract.project_number == "818569314985"
    assert contract.region == "southamerica-east1"
    assert contract.state.bucket == "falando-nela-pedblan-tfstate"
    assert contract.data.bucket == "falando-nela-pedblan-data"
    assert contract.migration.source_prefix == "v1"
    assert contract.state.versioning
    assert not contract.data.versioning
    assert contract.state.soft_delete_retention_seconds == 604_800
    assert contract.data.soft_delete_retention_seconds == 604_800
    assert len(contract.migration.sentinel) == 3
    assert sum(item.size_bytes for item in contract.migration.sentinel) == 78_822


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("schema_version = 4", "schema_version = 5"),
        ('project_id = "falando-nela-pedblan"', 'project_id = "eleicoes-2026-504713"'),
        ('region = "southamerica-east1"', 'region = "us-central1"'),
    ],
)
def test_contract_rejects_unknown_or_divergent_configuration(
    tmp_path: Path, old: str, new: str
) -> None:
    candidate = tmp_path / "gcp.toml"
    candidate.write_text(
        CONFIG_PATH.read_text(encoding="utf-8").replace(old, new), encoding="utf-8"
    )

    with pytest.raises(GcpConfigError, match="diverge"):
        load_gcp_contract(candidate)


def test_contract_rejects_missing_configuration(tmp_path: Path) -> None:
    with pytest.raises(GcpConfigError, match="ausente ou inválida"):
        load_gcp_contract(tmp_path / "missing.toml")


@pytest.mark.parametrize(
    ("project_id", "bucket", "folder_id", "message"),
    [
        ("eleicoes-2026-504713", "falando-nela-pedblan-data", "raw", "project ID"),
        ("falando-nela-pedblan", "outro-bucket", "raw", "bucket"),
        ("falando-nela-pedblan", "falando-nela-pedblan-data", "outra", "pasta raw"),
    ],
)
def test_literal_target_confirmation_blocks_divergence(
    project_id: str, bucket: str, folder_id: str, message: str
) -> None:
    contract = load_gcp_contract(CONFIG_PATH)

    with pytest.raises(GcpConfigError, match=message):
        contract.confirm_targets(
            project_id=project_id,
            bucket=bucket,
            source_raw_folder_id=folder_id,
        )


def test_gcs_cli_has_safe_defaults_and_explicit_target_arguments() -> None:
    args = build_parser().parse_args(
        [
            "gcs-migrate",
            "sentinel",
            "--operation-id",
            "g01-test",
            "--source-catalog",
            "catalog.jsonl",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            "raw",
            "--confirm-source-folder-id",
            "raw",
            "--confirm-project-id",
            "falando-nela-pedblan",
            "--confirm-bucket",
            "falando-nela-pedblan-data",
            "--operator-account",
            "operator@example.invalid",
        ]
    )

    assert args.through == "preflight"
    assert args.gcp_config == Path("config/gcp.toml")
    assert args.source_remote == "raw-source-ro"
    assert args.confirm_project_id == "falando-nela-pedblan"
    assert args.operator_account == "operator@example.invalid"


def test_g02_contract_keeps_current_defaults_and_pre_cutover_authority() -> None:
    contract = load_gcp_contract(CONFIG_PATH)

    assert contract.schema_version == 4
    assert contract.budget.currency_code == "BRL"
    assert contract.budget.amount == 25
    assert contract.budget.reference_ceiling_usd == 5
    assert contract.migration.authoritative_raw == "drive"
    assert contract.migration.batch_count == 38
    assert contract.migration.batch_max_files == 100
    assert contract.migration.batch_max_bytes == 512 * 1024 * 1024
    assert contract.migration.oversized_batch_count == 4
    assert contract.migration.restore_sample_files == 16
    assert contract.migration.restore_sample_bytes == 13_966_298
    assert len(contract.migration.approved_empty_source_locators) == 2


def test_g02_contract_accepts_safe_operational_adjustments(tmp_path: Path) -> None:
    candidate = tmp_path / "gcp.toml"
    content = CONFIG_PATH.read_text(encoding="utf-8")
    replacements = {
        "batch_count = 38": "batch_count = 57",
        "batch_max_files = 100": "batch_max_files = 50",
        "batch_max_bytes = 536870912": "batch_max_bytes = 268435456",
        "oversized_batch_count = 4": "oversized_batch_count = 7",
        "restore_sample_max_object_bytes = 16777216": ("restore_sample_max_object_bytes = 8388608"),
        "restore_sample_files = 16": "restore_sample_files = 18",
        "restore_sample_bytes = 13966298": "restore_sample_bytes = 15000000",
        "max_cost_usd = 1": "max_cost_usd = 2",
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    candidate.write_text(content, encoding="utf-8")

    contract = load_gcp_contract(candidate)

    assert contract.migration.batch_max_files == 50
    assert contract.migration.restore_sample_max_object_bytes == 8 * 1024 * 1024
    assert contract.migration.max_cost_usd == 2


def test_full_and_cutover_cli_require_explicit_targets_and_approvals() -> None:
    full = build_parser().parse_args(
        [
            "gcs-migrate",
            "full",
            "--operation-id",
            "g02-test",
            "--implementation-revision",
            "test-revision",
            "--source-catalog",
            "catalog.jsonl",
            "--source-batch-plan",
            "batches.json",
            "--g01-operation-root",
            "g01",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            "raw",
            "--confirm-source-folder-id",
            "raw",
            "--confirm-project-id",
            "falando-nela-pedblan",
            "--confirm-bucket",
            "falando-nela-pedblan-data",
            "--operator-account",
            "operator@example.invalid",
        ]
    )
    cutover = build_parser().parse_args(
        [
            "gcs-migrate",
            "cutover",
            "--operation-root",
            "g02",
            "--confirm-source-folder-id",
            "raw",
            "--confirm-project-id",
            "falando-nela-pedblan",
            "--confirm-bucket",
            "falando-nela-pedblan-data",
            "--operator-account",
            "operator@example.invalid",
            "--approve-migration-manifest-sha256",
            "a" * 64,
            "--confirm-authoritative-raw",
            "gcs",
        ]
    )

    assert full.through == "preflight"
    assert full.source_batch_plan == Path("batches.json")
    assert full.confirm_project_id == "falando-nela-pedblan"
    assert full.approve_plan_sha256 is None
    assert cutover.confirm_authoritative_raw == "gcs"
    assert cutover.approve_migration_manifest_sha256 == "a" * 64


def test_full_cli_allows_plan_and_runtime_tuning_without_frozen_batch_file() -> None:
    full = build_parser().parse_args(
        [
            "gcs-migrate",
            "full",
            "--operation-id",
            "g02-flex",
            "--implementation-revision",
            "test-revision",
            "--source-catalog",
            "catalog.jsonl",
            "--g01-operation-root",
            "g01",
            "--rclone-config",
            "rclone.conf",
            "--source-folder-id",
            "raw",
            "--confirm-source-folder-id",
            "raw",
            "--confirm-project-id",
            "falando-nela-pedblan",
            "--confirm-bucket",
            "falando-nela-pedblan-data",
            "--operator-account",
            "operator@example.invalid",
            "--batch-max-files",
            "50",
            "--batch-max-bytes",
            "268435456",
            "--restore-sample-max-bytes",
            "8388608",
            "--transfers",
            "8",
            "--retries",
            "2",
            "--low-level-retries",
            "3",
        ]
    )

    assert full.source_batch_plan is None
    assert full.batch_max_files == 50
    assert full.restore_sample_max_bytes == 8 * 1024 * 1024
    assert (full.transfers, full.retries, full.low_level_retries) == (8, 2, 3)


def test_full_cli_wires_revision_only_to_integral_migration() -> None:
    tree = ast.parse((REPO_ROOT / "src/falando_nela/cli.py").read_text(encoding="utf-8"))

    def keywords(function_name: str) -> set[str]:
        call = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function_name
        )
        return {item.arg for item in call.keywords if item.arg is not None}

    assert "implementation_revision" in keywords("execute_gcs_full")
    assert "implementation_revision" not in keywords("execute_gcs_sentinel")


def test_iac_never_uses_gcloud_default_or_implicit_project() -> None:
    versions = (REPO_ROOT / "infra/gcp/versions.tf").read_text(encoding="utf-8")
    main = (REPO_ROOT / "infra/gcp/main.tf").read_text(encoding="utf-8")
    variables = (REPO_ROOT / "infra/gcp/variables.tf").read_text(encoding="utf-8")
    all_iac = versions + main + variables

    assert "project               = var.project_id" in versions
    assert "billing_project       = var.project_id" in versions
    assert "user_project_override = true" in versions
    assert "projects/${var.project_number}" in main
    assert 'project_number == "818569314985"' in variables
    assert "gcloud config set project" not in all_iac
