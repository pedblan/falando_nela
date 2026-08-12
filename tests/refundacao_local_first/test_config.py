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


def test_settings_require_absolute_data_root_outside_clone_by_default(tmp_path: Path) -> None:
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


def test_exact_repository_data_samples_root_is_allowed_only_for_local_sample(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data_root = repo_root / "data_samples"

    settings = Settings.from_env(environ={}, repo_root=repo_root, data_root=data_root)

    assert settings.data_root == data_root
    assert settings.profile == "local"
    assert settings.data_profile == "sample_annual_1pct"
    assert not data_root.exists()

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(
            environ={"FALANDO_NELA_PROFILE": "cloud"},
            repo_root=repo_root,
            data_root=data_root,
        )

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(
            environ={"FALANDO_NELA_DATA_PROFILE": "full"},
            repo_root=repo_root,
            data_root=data_root,
            allow_full=True,
        )

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(
            environ={},
            repo_root=repo_root,
            data_root=data_root / "nested",
        )


def test_data_samples_in_another_worktree_keeps_profile_restrictions(tmp_path: Path) -> None:
    active_worktree = tmp_path / "active"
    active_worktree.mkdir()
    (active_worktree / ".git").write_text("gitdir: shared", encoding="utf-8")
    canonical_worktree = tmp_path / "canonical"
    canonical_worktree.mkdir()
    (canonical_worktree / ".git").mkdir()
    data_root = canonical_worktree / "data_samples"

    settings = Settings.from_env(environ={}, repo_root=active_worktree, data_root=data_root)
    assert settings.data_root == data_root

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(
            environ={"FALANDO_NELA_PROFILE": "cloud"},
            repo_root=active_worktree,
            data_root=data_root,
        )

    with pytest.raises(ValidationError, match="dentro do clone"):
        Settings.from_env(
            environ={},
            repo_root=active_worktree,
            data_root=canonical_worktree / "data",
        )


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
