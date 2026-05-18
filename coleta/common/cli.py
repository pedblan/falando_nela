from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from coleta.common.config import (
    BASELINE_END,
    BASELINE_START,
    DEFAULT_DEV_DATA_DIR,
    PROD_DATA_ROOT_ENV,
    RuntimeConfig,
    parse_iso_date,
)


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--data-inicio", default=BASELINE_START.isoformat())
    parser.add_argument("--data-fim", default=BASELINE_END.isoformat())
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--sample", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id", default=None)
    return parser


def parse_runtime_args(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> RuntimeConfig:
    args = parser.parse_args(argv)
    data_inicio = parse_iso_date(args.data_inicio)
    data_fim = parse_iso_date(args.data_fim)
    if data_inicio > data_fim:
        parser.error("--data-inicio nao pode ser posterior a --data-fim")

    sample = args.sample if args.sample is not None else args.mode == "dev"
    sample_limit = args.sample_limit
    if sample_limit is None and args.mode == "dev":
        sample_limit = 5
    if sample_limit is not None and sample_limit <= 0:
        parser.error("--sample-limit deve ser positivo")
    output_dir = resolve_output_dir(
        mode=args.mode,
        output_dir=args.output_dir,
        cwd=Path.cwd(),
        env=os.environ,
        parser=parser,
    )

    return RuntimeConfig(
        data_inicio=data_inicio,
        data_fim=data_fim,
        mode=args.mode,
        output_dir=output_dir,
        sample=bool(sample),
        sample_limit=sample_limit,
        resume=bool(args.resume),
        run_id=args.run_id or uuid4().hex,
    )


def resolve_output_dir(
    *,
    mode: str,
    output_dir: str | None,
    cwd: Path,
    env: os._Environ[str] | dict[str, str],
    parser: argparse.ArgumentParser | None = None,
) -> Path:
    raw_output_dir = output_dir or env.get(PROD_DATA_ROOT_ENV) or None

    if raw_output_dir is None:
        if mode == "dev":
            return DEFAULT_DEV_DATA_DIR
        _fail(
            f"--mode prod exige --output-dir ou {PROD_DATA_ROOT_ENV}",
            parser,
        )

    resolved = Path(raw_output_dir).expanduser()
    if mode == "prod" and _is_inside_repo(resolved, cwd):
        _fail(
            "Em --mode prod, use um diretorio externo ao repositorio "
            f"(por exemplo, /content/drive/MyDrive/falando_nela/data via {PROD_DATA_ROOT_ENV}).",
            parser,
        )
    return resolved


def _is_inside_repo(path: Path, cwd: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_cwd = cwd.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_cwd)
    except ValueError:
        return False
    return True


def _fail(message: str, parser: argparse.ArgumentParser | None) -> None:
    if parser is None:
        raise ValueError(message)
    parser.error(message)
