from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from falando_nela.doctor import run_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="falando-nela")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="valida o ambiente local sem usar rede")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.add_argument("--data-root", type=Path)
    doctor.add_argument("--repo-root", type=Path, default=Path.cwd())
    doctor.add_argument("--allow-full", action="store_true", default=None)
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
    return 2


def _print_human_doctor(payload: dict[str, object]) -> None:
    print(f"Falando Nela: {payload['status']}", file=sys.stderr)
    for check in payload["checks"]:
        assert isinstance(check, dict)
        print(f"- {check['id']}: {check['status']} — {check['detail']}", file=sys.stderr)
