from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_DRIVE_SOURCE_FOLDER_ID = "1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W"
DEFAULT_SAMPLE_SEED = "falando-nela-amostra-anual-v1"
GIB = 1024**3


class ConfigurationError(ValueError):
    """Configuração recusada antes de qualquer efeito externo ou escrita."""


def parse_byte_size(value: str | int) -> int:
    if isinstance(value, int):
        if value < 0:
            raise ConfigurationError("O tamanho não pode ser negativo.")
        return value
    match = re.fullmatch(r"\s*(\d+)\s*(B|KiB|MiB|GiB)\s*", value, re.IGNORECASE)
    if match is None:
        raise ConfigurationError(f"Tamanho inválido: {value!r}.")
    number = int(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": GIB}[unit]
    return number * multiplier


def parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "sim"}:
        return True
    if normalized in {"0", "false", "no", "não", "nao"}:
        return False
    raise ConfigurationError(f"Booleano inválido: {value!r}.")


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _containing_git_checkout(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_root: Path
    repo_root: Path
    profile: Literal["local", "cloud"] = "local"
    data_profile: Literal["sample_annual_1pct", "full"] = "sample_annual_1pct"
    allow_full: bool = False
    duckdb_memory_limit: str = "4GB"
    duckdb_threads: int = Field(default=4, ge=1, le=4)
    temp_root: Path
    drive_source: str | None = None
    drive_source_folder_id: str = DEFAULT_DRIVE_SOURCE_FOLDER_ID
    backup_remote: str = "drive-backup"
    sample_seed: str = DEFAULT_SAMPLE_SEED
    sample_local_quota_bytes: int = 2 * GIB
    minimum_free_bytes: int = 5 * GIB

    @model_validator(mode="after")
    def validate_boundaries(self) -> Settings:
        data_root = _resolved(self.data_root)
        repo_root = _resolved(self.repo_root)
        temp_root = _resolved(self.temp_root)
        containing_checkout = _containing_git_checkout(data_root)
        if not self.data_root.expanduser().is_absolute():
            raise ValueError("FALANDO_NELA_DATA_ROOT deve ser um caminho absoluto.")
        if data_root in {_resolved(Path("/")), _resolved(Path.home())}:
            raise ValueError(
                "FALANDO_NELA_DATA_ROOT não pode ser a raiz do volume nem a pasta pessoal."
            )
        allowed_repository_sample_root = (
            data_root
            in {
                repo_root / "data_samples",
                (
                    containing_checkout / "data_samples"
                    if containing_checkout is not None
                    else repo_root / "__no_containing_checkout__"
                ),
            }
            and self.profile == "local"
            and self.data_profile == "sample_annual_1pct"
        )
        if (
            data_root == repo_root
            or data_root.is_relative_to(repo_root)
            or containing_checkout is not None
        ) and not allowed_repository_sample_root:
            raise ValueError("FALANDO_NELA_DATA_ROOT não pode ficar dentro do clone Git.")
        if data_root.exists() and not data_root.is_dir():
            raise ValueError("FALANDO_NELA_DATA_ROOT existente deve ser um diretório.")
        if temp_root != data_root and not temp_root.is_relative_to(data_root):
            raise ValueError("FALANDO_NELA_TEMP_ROOT deve ficar dentro da raiz de dados.")
        if self.data_profile == "full" and not self.allow_full:
            raise ValueError("O profile full exige FALANDO_NELA_ALLOW_FULL=true.")
        if not self.sample_seed.strip():
            raise ValueError("FALANDO_NELA_SAMPLE_SEED não pode ser vazio.")
        if self.sample_local_quota_bytes <= 0:
            raise ValueError("A quota local deve ser positiva.")
        if self.minimum_free_bytes <= 0:
            raise ValueError("A reserva de espaço deve ser positiva.")
        object.__setattr__(self, "data_root", data_root)
        object.__setattr__(self, "repo_root", repo_root)
        object.__setattr__(self, "temp_root", temp_root)
        return self

    @classmethod
    def from_env(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        repo_root: Path | None = None,
        data_root: Path | None = None,
        allow_full: bool | None = None,
    ) -> Settings:
        env = os.environ if environ is None else environ
        raw_data_root = data_root or _required_data_root(env)
        resolved_repo = _resolved(repo_root or Path.cwd())
        temp_value = env.get("FALANDO_NELA_TEMP_ROOT")
        temp_root = Path(temp_value) if temp_value else raw_data_root / "tmp"
        return cls(
            data_root=raw_data_root,
            repo_root=resolved_repo,
            profile=env.get("FALANDO_NELA_PROFILE", "local"),
            data_profile=env.get("FALANDO_NELA_DATA_PROFILE", "sample_annual_1pct"),
            allow_full=(
                parse_bool(env.get("FALANDO_NELA_ALLOW_FULL")) if allow_full is None else allow_full
            ),
            duckdb_memory_limit=env.get("FALANDO_NELA_DUCKDB_MEMORY_LIMIT", "4GB"),
            duckdb_threads=int(env.get("FALANDO_NELA_DUCKDB_THREADS", "4")),
            temp_root=temp_root,
            drive_source=env.get("FALANDO_NELA_DRIVE_SOURCE"),
            drive_source_folder_id=env.get(
                "FALANDO_NELA_DRIVE_SOURCE_FOLDER_ID",
                DEFAULT_DRIVE_SOURCE_FOLDER_ID,
            ),
            backup_remote=env.get("FALANDO_NELA_RCLONE_BACKUP_REMOTE", "drive-backup"),
            sample_seed=env.get("FALANDO_NELA_SAMPLE_SEED", DEFAULT_SAMPLE_SEED),
            sample_local_quota_bytes=parse_byte_size(
                env.get("FALANDO_NELA_SAMPLE_LOCAL_QUOTA", "2GiB")
            ),
            minimum_free_bytes=parse_byte_size(env.get("FALANDO_NELA_MINIMUM_FREE", "5GiB")),
        )

    def public_dict(self) -> dict[str, object]:
        """Configuração segura para diagnóstico; nunca inclui tokens ou segredos."""
        return {
            "data_root": str(self.data_root),
            "profile": self.profile,
            "data_profile": self.data_profile,
            "duckdb_memory_limit": self.duckdb_memory_limit,
            "duckdb_threads": self.duckdb_threads,
            "temp_root": str(self.temp_root),
            "drive_source_configured": bool(self.drive_source),
            "drive_source_folder_id": self.drive_source_folder_id,
            "sample_seed": self.sample_seed,
            "sample_local_quota_bytes": self.sample_local_quota_bytes,
            "minimum_free_bytes": self.minimum_free_bytes,
        }


def _required_data_root(environ: Mapping[str, str]) -> Path:
    value = environ.get("FALANDO_NELA_DATA_ROOT")
    if value is None or not value.strip():
        raise ConfigurationError("FALANDO_NELA_DATA_ROOT não está configurado.")
    return Path(value)
