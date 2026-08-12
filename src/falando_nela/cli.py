from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from falando_nela.config import ConfigurationError, Settings
from falando_nela.doctor import run_doctor
from falando_nela.drive_organizer import (
    CopyConflict,
    LayoutError,
    RcloneCopyTransport,
    execute_drive_copy,
    execute_drive_dry_run,
    plan_drive_organization,
    reconcile_drive_inventory,
)
from falando_nela.gcp_config import GcpConfigError, load_gcp_contract
from falando_nela.gcs_migration import (
    GcloudImpersonatedTokenProvider,
    GcsMigrationError,
    RcloneGcsTransport,
    execute_gcs_sentinel,
)
from falando_nela.operations import OperationError
from falando_nela.sample_import import (
    PILOT_PREFIX,
    SampleImportError,
    execute_pilot_sample,
)
from falando_nela.sources import RcloneRawSource, SourceError, inspect_rclone_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="falando-nela")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="valida o ambiente local sem usar rede")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.add_argument("--data-root", type=Path)
    doctor.add_argument("--repo-root", type=Path, default=Path.cwd())
    doctor.add_argument("--allow-full", action="store_true", default=None)
    drive_organize = subcommands.add_parser(
        "drive-organize", help="prepara a organização copy-first do raw no Drive"
    )
    drive_commands = drive_organize.add_subparsers(dest="drive_command", required=True)
    drive_plan = drive_commands.add_parser(
        "plan", help="reconcilia inventário e congela o mapa sem copiar arquivos"
    )
    drive_plan.add_argument("--operation-id", required=True)
    drive_plan.add_argument("--baseline-csv", type=Path, required=True)
    drive_plan.add_argument("--rclone-config", type=Path, required=True)
    drive_plan.add_argument("--source-remote", default="raw-source-ro")
    drive_plan.add_argument("--source-folder-id", required=True)
    drive_plan.add_argument("--destination-remote", default="raw-destination-rw")
    drive_plan.add_argument("--destination-folder-id", required=True)
    drive_plan.add_argument("--data-root", type=Path)
    drive_plan.add_argument("--repo-root", type=Path, default=Path.cwd())
    drive_plan.add_argument("--json", action="store_true", dest="as_json")
    drive_reconcile = drive_commands.add_parser(
        "reconcile", help="reconcilia G01 e identidades do Drive sem copiar arquivos"
    )
    drive_reconcile.add_argument("--operation-id", required=True)
    drive_reconcile.add_argument("--baseline-csv", type=Path, required=True)
    drive_reconcile.add_argument("--provider-identity-map", type=Path, required=True)
    drive_reconcile.add_argument("--rclone-config", type=Path, required=True)
    drive_reconcile.add_argument("--source-remote", default="raw-source-ro")
    drive_reconcile.add_argument("--source-folder-id", required=True)
    drive_reconcile.add_argument("--data-root", type=Path)
    drive_reconcile.add_argument("--repo-root", type=Path, default=Path.cwd())
    drive_reconcile.add_argument("--json", action="store_true", dest="as_json")
    drive_dry_run = drive_commands.add_parser(
        "dry-run", help="ensaia o plano integral sem criar objetos no Drive"
    )
    drive_dry_run.add_argument("--operation-id", required=True)
    drive_dry_run.add_argument("--reconciliation-manifest", type=Path, required=True)
    drive_dry_run.add_argument("--source-inventory", type=Path, required=True)
    drive_dry_run.add_argument("--source-reconciliation", type=Path, required=True)
    drive_dry_run.add_argument("--provider-identity-map", type=Path, required=True)
    drive_dry_run.add_argument("--rclone-config", type=Path, required=True)
    drive_dry_run.add_argument("--source-remote", default="raw-source-ro")
    drive_dry_run.add_argument("--source-folder-id", required=True)
    drive_dry_run.add_argument("--destination-remote", default="raw-destination-rw")
    drive_dry_run.add_argument("--destination-folder-id", required=True)
    drive_dry_run.add_argument("--data-root", type=Path)
    drive_dry_run.add_argument("--repo-root", type=Path, default=Path.cwd())
    drive_dry_run.add_argument("--json", action="store_true", dest="as_json")
    drive_copy = drive_commands.add_parser(
        "copy", help="copia e reconcilia o sentinela ou toda a árvore canônica"
    )
    drive_copy.add_argument("--operation-id", required=True)
    drive_copy.add_argument("--source-inventory", type=Path, required=True)
    drive_copy.add_argument("--dry-run-operation-root", type=Path, required=True)
    drive_copy.add_argument("--rclone-config", type=Path, required=True)
    drive_copy.add_argument("--source-remote", default="raw-source-ro")
    drive_copy.add_argument("--source-folder-id", required=True)
    drive_copy.add_argument("--destination-remote", default="raw-destination-rw")
    drive_copy.add_argument("--destination-folder-id", required=True)
    drive_copy.add_argument("--through", choices=("sentinel", "all"), default="sentinel")
    drive_copy.add_argument("--batch-max-files", type=int, default=100)
    drive_copy.add_argument("--batch-max-bytes", type=int, default=512 * 1024 * 1024)
    drive_copy.add_argument("--sentinel-max-bytes", type=int, default=10 * 1024 * 1024)
    drive_copy.add_argument("--data-root", type=Path)
    drive_copy.add_argument("--repo-root", type=Path, default=Path.cwd())
    drive_copy.add_argument("--json", action="store_true", dest="as_json")
    sample = subcommands.add_parser("sample", help="materializa amostras raw aprovadas")
    sample_commands = sample.add_subparsers(dest="sample_command", required=True)
    sample_pilot = sample_commands.add_parser(
        "pilot", help="publica o piloto determinístico do Plenário do Senado em 2010"
    )
    sample_pilot.add_argument("--operation-id", required=True)
    sample_pilot.add_argument("--copy-catalog-summary", type=Path, required=True)
    sample_pilot.add_argument("--rclone-config", type=Path, required=True)
    sample_pilot.add_argument("--source-remote", default="raw-source-ro")
    sample_pilot.add_argument("--source-folder-id", required=True)
    sample_pilot.add_argument("--confirm-source-folder-id", required=True)
    sample_pilot.add_argument("--data-root", type=Path)
    sample_pilot.add_argument("--repo-root", type=Path, default=Path.cwd())
    sample_pilot.add_argument("--json", action="store_true", dest="as_json")
    gcs_migrate = subcommands.add_parser(
        "gcs-migrate", help="prepara a migração imutável e recuperável para GCS"
    )
    gcs_commands = gcs_migrate.add_subparsers(dest="gcs_command", required=True)
    gcs_sentinel = gcs_commands.add_parser(
        "sentinel", help="reconcilia, ensaia ou copia a sentinela G01"
    )
    gcs_sentinel.add_argument(
        "--through", choices=("preflight", "dry-run", "copy"), default="preflight"
    )
    gcs_sentinel.add_argument("--operation-id", required=True)
    gcs_sentinel.add_argument("--gcp-config", type=Path, default=Path("config/gcp.toml"))
    gcs_sentinel.add_argument("--source-catalog", type=Path, required=True)
    gcs_sentinel.add_argument("--rclone-config", type=Path, required=True)
    gcs_sentinel.add_argument("--source-remote", default="raw-source-ro")
    gcs_sentinel.add_argument("--source-folder-id", required=True)
    gcs_sentinel.add_argument("--confirm-source-folder-id", required=True)
    gcs_sentinel.add_argument("--confirm-project-id", required=True)
    gcs_sentinel.add_argument("--confirm-bucket", required=True)
    gcs_sentinel.add_argument("--operator-account", required=True)
    gcs_sentinel.add_argument("--data-root", type=Path)
    gcs_sentinel.add_argument("--repo-root", type=Path, default=Path.cwd())
    gcs_sentinel.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        payload, return_code = run_doctor(
            repo_root=args.repo_root,
            data_root=args.data_root,
            allow_full=args.allow_full,
        )
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_doctor(payload)
        return return_code
    if args.command == "drive-organize" and args.drive_command == "plan":
        try:
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            source = RcloneRawSource(
                remote=args.source_remote,
                config_path=args.rclone_config,
                prefix="",
                expected_folder_id=args.source_folder_id,
                config_snapshot=config_snapshot,
                include_all_files=True,
            )
            transport = RcloneCopyTransport(
                config_path=args.rclone_config,
                source_remote=args.source_remote,
                source_folder_id=args.source_folder_id,
                destination_remote=args.destination_remote,
                destination_folder_id=args.destination_folder_id,
                config_snapshot=config_snapshot,
            )
            payload = plan_drive_organization(
                source=source,
                transport=transport,
                baseline_csv=args.baseline_csv,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                source_folder_id=args.source_folder_id,
                destination_folder_id=args.destination_folder_id,
            )
        except (
            ConfigurationError,
            LayoutError,
            OSError,
            OperationError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha ao planejar organização do Drive: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_drive_plan(payload)
        return 0
    if args.command == "drive-organize" and args.drive_command == "reconcile":
        try:
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            source = RcloneRawSource(
                remote=args.source_remote,
                config_path=args.rclone_config,
                prefix="",
                expected_folder_id=args.source_folder_id,
                config_snapshot=config_snapshot,
                include_all_files=True,
            )
            payload = reconcile_drive_inventory(
                source=source,
                baseline_csv=args.baseline_csv,
                provider_identity_map_path=args.provider_identity_map,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                source_folder_id=args.source_folder_id,
            )
        except (
            ConfigurationError,
            LayoutError,
            OSError,
            OperationError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha ao reconciliar inventário do Drive: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_drive_reconciliation(payload)
        return 0
    if args.command == "drive-organize" and args.drive_command == "dry-run":
        try:
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            transport = RcloneCopyTransport(
                config_path=args.rclone_config,
                source_remote=args.source_remote,
                source_folder_id=args.source_folder_id,
                destination_remote=args.destination_remote,
                destination_folder_id=args.destination_folder_id,
                config_snapshot=config_snapshot,
            )
            payload = execute_drive_dry_run(
                transport=transport,
                reconciliation_manifest_path=args.reconciliation_manifest,
                source_inventory_path=args.source_inventory,
                source_reconciliation_path=args.source_reconciliation,
                provider_identity_map_path=args.provider_identity_map,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                source_folder_id=args.source_folder_id,
                destination_folder_id=args.destination_folder_id,
            )
        except (
            ConfigurationError,
            CopyConflict,
            LayoutError,
            OSError,
            OperationError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha no dry-run da organização do Drive: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_drive_dry_run(payload)
        return 0
    if args.command == "drive-organize" and args.drive_command == "copy":
        try:
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            source = RcloneRawSource(
                remote=args.source_remote,
                config_path=args.rclone_config,
                prefix="",
                expected_folder_id=args.source_folder_id,
                config_snapshot=config_snapshot,
                include_all_files=True,
            )
            transport = RcloneCopyTransport(
                config_path=args.rclone_config,
                source_remote=args.source_remote,
                source_folder_id=args.source_folder_id,
                destination_remote=args.destination_remote,
                destination_folder_id=args.destination_folder_id,
                config_snapshot=config_snapshot,
            )
            payload = execute_drive_copy(
                transport=transport,
                source=source,
                source_inventory_path=args.source_inventory,
                dry_run_operation_root=args.dry_run_operation_root,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                source_folder_id=args.source_folder_id,
                destination_folder_id=args.destination_folder_id,
                through=args.through,
                batch_max_files=args.batch_max_files,
                batch_max_bytes=args.batch_max_bytes,
                sentinel_max_bytes=args.sentinel_max_bytes,
                progress_callback=_print_progress,
            )
        except (
            ConfigurationError,
            CopyConflict,
            LayoutError,
            OSError,
            OperationError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha na cópia da organização do Drive: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_drive_copy(payload)
        return 0
    if args.command == "sample" and args.sample_command == "pilot":
        try:
            if args.confirm_source_folder_id != args.source_folder_id:
                raise SampleImportError("confirmação literal do ID canônico diverge")
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            source = RcloneRawSource(
                remote=args.source_remote,
                config_path=args.rclone_config,
                prefix=PILOT_PREFIX,
                expected_folder_id=args.source_folder_id,
                config_snapshot=config_snapshot,
            )
            payload = execute_pilot_sample(
                source=source,
                copy_catalog_summary_path=args.copy_catalog_summary,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                confirmed_source_folder_id=args.confirm_source_folder_id,
                sample_seed=settings.sample_seed,
                quota_bytes=settings.sample_local_quota_bytes,
                minimum_free_bytes=settings.minimum_free_bytes,
                progress_callback=_print_progress,
            )
        except (
            ConfigurationError,
            OSError,
            OperationError,
            SampleImportError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha ao materializar piloto amostral: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_sample_pilot(payload)
        return 0
    if args.command == "gcs-migrate" and args.gcs_command == "sentinel":
        try:
            settings = Settings.from_env(repo_root=args.repo_root, data_root=args.data_root)
            contract = load_gcp_contract(args.gcp_config)
            config_snapshot = inspect_rclone_config(args.rclone_config)
            source = RcloneRawSource(
                remote=args.source_remote,
                config_path=args.rclone_config,
                prefix="",
                expected_folder_id=args.source_folder_id,
                config_snapshot=config_snapshot,
                include_all_files=True,
            )
            access_token = GcloudImpersonatedTokenProvider(
                project_id=contract.project_id,
                service_account=contract.migrator_email,
                operator_account=args.operator_account,
            )
            transport = RcloneGcsTransport(
                config_path=args.rclone_config,
                source_remote=args.source_remote,
                source_folder_id=args.source_folder_id,
                project_id=contract.project_id,
                project_number=contract.project_number,
                region=contract.region,
                bucket=contract.data.bucket,
                raw_prefix=contract.data.raw_prefix,
                access_token=access_token,
            )
            payload = execute_gcs_sentinel(
                source=source,
                transport=transport,
                contract=contract,
                source_catalog_path=args.source_catalog,
                data_root=settings.data_root,
                operation_id=args.operation_id,
                confirmed_project_id=args.confirm_project_id,
                confirmed_bucket=args.confirm_bucket,
                confirmed_source_folder_id=args.confirm_source_folder_id,
                through=args.through,
                progress_callback=_print_progress,
            )
        except (
            ConfigurationError,
            GcpConfigError,
            GcsMigrationError,
            OSError,
            OperationError,
            SourceError,
            ValidationError,
        ) as exc:
            print(f"Falha na sentinela GCS: {exc}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            _print_human_gcs_sentinel(payload)
        return 0
    return 2


def _print_progress(event: dict[str, object]) -> None:
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), file=sys.stderr, flush=True)


def _print_human_doctor(payload: dict[str, object]) -> None:
    print(f"Falando Nela: {payload['status']}", file=sys.stderr)
    for check in payload["checks"]:
        assert isinstance(check, dict)
        print(f"- {check['id']}: {check['status']} — {check['detail']}", file=sys.stderr)


def _print_human_drive_plan(payload: dict[str, object]) -> None:
    print(f"Plano do Drive: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- arquivos: {payload['files']}", file=sys.stderr)
    print(f"- bytes: {payload['bytes']}", file=sys.stderr)
    print(f"- plano: {payload['copy_plan_path']}", file=sys.stderr)


def _print_human_drive_reconciliation(payload: dict[str, object]) -> None:
    print(f"Reconciliação do Drive: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- arquivos: {payload['files']}", file=sys.stderr)
    print(f"- bytes: {payload['bytes']}", file=sys.stderr)
    print(f"- relatório: {payload['reconciliation_path']}", file=sys.stderr)


def _print_human_drive_dry_run(payload: dict[str, object]) -> None:
    print(f"Dry-run do Drive: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- candidatos: {payload['files']}", file=sys.stderr)
    print(f"- bytes: {payload['bytes']}", file=sys.stderr)
    print(f"- excluídos: {payload['excluded_files']}", file=sys.stderr)
    print(f"- relatório: {payload['dry_run_summary_path']}", file=sys.stderr)


def _print_human_drive_copy(payload: dict[str, object]) -> None:
    print(f"Cópia do Drive: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- limite executado: {payload['through']}", file=sys.stderr)
    print(f"- sentinelas: {payload['sentinel_files']}", file=sys.stderr)
    print(f"- bytes sentinela: {payload['sentinel_bytes']}", file=sys.stderr)
    if payload["catalog_summary_path"] is not None:
        print(f"- catálogo: {payload['catalog_summary_path']}", file=sys.stderr)


def _print_human_sample_pilot(payload: dict[str, object]) -> None:
    print(f"Amostra piloto: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- sample_id: {payload['sample_id']}", file=sys.stderr)
    print(f"- população: {payload['population']}", file=sys.stderr)
    print(f"- selecionados: {payload['selected_count']}", file=sys.stderr)
    print(f"- manifesto: {payload['sample_manifest_path']}", file=sys.stderr)


def _print_human_gcs_sentinel(payload: dict[str, object]) -> None:
    print(f"Sentinela GCS: {payload['status']}", file=sys.stderr)
    print(f"- operação: {payload['operation_id']}", file=sys.stderr)
    print(f"- limite executado: {payload['through']}", file=sys.stderr)
    print(f"- manifesto: {payload['manifest_path']}", file=sys.stderr)
    print(f"- artefato: {payload['artifact_path']}", file=sys.stderr)
