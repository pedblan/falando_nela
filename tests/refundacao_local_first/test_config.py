from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from falando_nela.config import GIB, ConfigurationError, Settings, parse_byte_size


def test_settings_use_safe_local_defaults(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    repo_root.mkdir()

    settings = Settings.from_env(environ={}, repo_root=repo_root, data_root=data_root)

    assert settings.data_root == data_root
    assert settings.temp_root == data_root / "tmp"
    assert settings.data_profile == "sample_annual_1pct"
    assert settings.duckdb_memory_limit == "4GB"
    assert settings.duckdb_threads == 4
    assert settings.sample_local_quota_bytes == 2 * GIB
    assert settings.minimum_free_bytes == 5 * GIB
    assert not data_root.exists()


def test_settings_require_external_absolute_data_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(ConfigurationError, match="não está configurado"):
        Settings.from_env(environ={}, repo_root=repo_root)

    with pytest.raises(ValidationError, match="caminho absoluto"):
        Settings.from_env(environ={}, repo_root=repo_root, data_root=Path("relative"))

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(environ={}, repo_root=repo_root, data_root=repo_root / "data")

    with pytest.raises(ValidationError, match="raiz do volume"):
        Settings.from_env(environ={}, repo_root=repo_root, data_root=Path("/"))

    with pytest.raises(ValidationError, match="pasta pessoal"):
        Settings.from_env(environ={}, repo_root=repo_root, data_root=Path.home())


def test_full_profile_requires_explicit_opt_in(tmp_path: Path) -> None:
    env = {"FALANDO_NELA_DATA_PROFILE": "full"}
    with pytest.raises(ValidationError, match="ALLOW_FULL"):
        Settings.from_env(
            environ=env,
            repo_root=tmp_path / "repo",
            data_root=tmp_path / "data",
        )

    settings = Settings.from_env(
        environ=env,
        repo_root=tmp_path / "repo",
        data_root=tmp_path / "data",
        allow_full=True,
    )
    assert settings.data_profile == "full"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1B", 1), ("2KiB", 2 * 1024), ("3MiB", 3 * 1024**2), ("4GiB", 4 * GIB)],
)
def test_parse_byte_size(raw: str, expected: int) -> None:
    assert parse_byte_size(raw) == expected
