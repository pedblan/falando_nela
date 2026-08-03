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
    execute_drive_dry_run,
    plan_drive_organization,
    reconcile_drive_inventory,
)
from falando_nela.operations import OperationError
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
    return 2


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
