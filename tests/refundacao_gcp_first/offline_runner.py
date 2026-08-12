from __future__ import annotations

import runpy
import socket
import sys
from pathlib import Path


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("O subprocesso de teste não pode acessar a rede externa.")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("uso: offline_runner.py ARQUIVO_PYTHON")
    socket.create_connection = _blocked
    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
    runpy.run_path(str(Path(sys.argv[1]).resolve(strict=True)), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
