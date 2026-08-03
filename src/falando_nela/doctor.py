from __future__ import annotations

import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from falando_nela.config import ConfigurationError, Settings


def run_doctor(
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    data_root: Path | None = None,
    allow_full: bool | None = None,
) -> tuple[dict[str, object], int]:
    checks: list[dict[str, object]] = []
    python_ok = sys.version_info[:2] == (3, 13)
    checks.append(
        {
            "id": "python",
            "status": "ok" if python_ok else "error",
            "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    )
    try:
        settings = Settings.from_env(
            environ=environ,
            repo_root=repo_root,
            data_root=data_root,
            allow_full=allow_full,
        )
    except (ConfigurationError, ValidationError, ValueError) as exc:
        checks.append({"id": "configuration", "status": "error", "detail": str(exc)})
        return {"status": "error", "checks": checks, "configuration": None}, 2

    checks.append(
        {
            "id": "configuration",
            "status": "ok",
            "detail": "configuração validada sem criar a raiz de dados",
        }
    )
    checks.append(
        {
            "id": "data_root_exists",
            "status": "ok" if settings.data_root.exists() else "warning",
            "detail": str(settings.data_root),
        }
    )
    capacity_root = _nearest_existing_parent(settings.data_root)
    free_bytes = shutil.disk_usage(capacity_root).free
    required_free_bytes = settings.sample_local_quota_bytes + settings.minimum_free_bytes
    capacity_ok = free_bytes >= required_free_bytes
    checks.append(
        {
            "id": "disk_capacity",
            "status": "ok" if capacity_ok else "error",
            "detail": {
                "probe_path": str(capacity_root),
                "free_bytes": free_bytes,
                "required_free_bytes": required_free_bytes,
            },
        }
    )
    rclone = shutil.which("rclone")
    checks.append(
        {
            "id": "rclone",
            "status": "ok" if rclone else "optional_missing",
            "detail": rclone or "necessário apenas a partir de R03",
        }
    )
    status = "ok" if python_ok and capacity_ok else "error"
    return {
        "status": status,
        "checks": checks,
        "configuration": settings.public_dict(),
    }, 0 if status == "ok" else 2


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return parent
        candidate = parent
    return candidate
