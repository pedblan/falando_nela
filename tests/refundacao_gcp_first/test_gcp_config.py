from __future__ import annotations

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
    assert contract.state.versioning
    assert not contract.data.versioning
    assert contract.state.soft_delete_retention_seconds == 604_800
    assert contract.data.soft_delete_retention_seconds == 604_800
    assert len(contract.migration.sentinel) == 3
    assert sum(item.size_bytes for item in contract.migration.sentinel) == 78_822


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("schema_version = 1", "schema_version = 2"),
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
