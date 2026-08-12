from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

import pytest

from falando_nela.sources import (
    BaselineMismatch,
    LocalRawSource,
    RcloneConfigSnapshot,
    RcloneRawSource,
    SourceError,
    SourceObject,
    inspect_rclone_config,
    load_g01_baseline,
    load_provider_identity_map,
    reconcile_baseline,
    validate_rclone_readonly_config,
)

SOURCE_FOLDER_ID = "source-folder-id"
SENTINEL_TOKEN = "TOKEN-SENTINELA-NAO-PODE-VAZAR"


def _redacted_readonly_config(*, scope: str = "drive.readonly") -> str:
    return "\n".join(
        [
            "[raw-source-ro]",
            "type = drive",
            f"scope = {scope}",
            "root_folder_id = XXX",
            "token = XXX",
        ]
    )


def _write_encrypted_config(path: Path) -> None:
    path.write_text("RCLONE_ENCRYPT_V0:\nconteudo-cifrado", encoding="utf-8")
    path.chmod(0o600)


def _snapshot(path: Path, *, scope: str = "drive.readonly") -> RcloneConfigSnapshot:
    return RcloneConfigSnapshot(path.resolve(), _redacted_readonly_config(scope=scope))


def test_local_source_lists_and_streams_jsonl_and_gzip(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    monthly = root / "senado/plenario_discursos/ano=2010/mes=02"
    monthly.mkdir(parents=True)
    plain = monthly / "a.jsonl"
    plain.write_bytes(b'{"source_id":"1"}\n\n')
    compressed = monthly / "b.jsonl.gz"
    with gzip.open(compressed, "wb") as handle:
        handle.write(b'{"source_id":"2"}\nlinha-invalida\n')
    (monthly / "ignorado.txt").write_text("fora do raw", encoding="utf-8")

    source = LocalRawSource(root)
    objects = source.list_objects()
    records = list(source.iter_records(reversed(objects)))

    assert [item.locator for item in objects] == [
        "senado/plenario_discursos/ano=2010/mes=02/a.jsonl",
        "senado/plenario_discursos/ano=2010/mes=02/b.jsonl.gz",
    ]
    assert [record.value for record in records[:2]] == [
        {"source_id": "1"},
        {"source_id": "2"},
    ]
    assert records[2].value is None
    assert records[2].error is not None and records[2].error.startswith("json_invalid:")
    assert source.list_calls == 1
    assert source.stream_calls == 1
    assert source.bytes_read > 0


def test_g01_baseline_load_and_reconciliation(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "g01.csv"
    baseline_csv.write_text(
        "item_type,relative_path,size_bytes\n"
        "directory,senado,0\n"
        "file,senado/a.jsonl,10\n"
        "file,camara/b.jsonl.gz,20\n",
        encoding="utf-8",
    )

    baseline = load_g01_baseline(baseline_csv)

    assert reconcile_baseline(baseline, list(reversed(baseline))) == {
        "files": 2,
        "bytes": 30,
        "missing": 0,
        "added": 0,
        "changed": 0,
        "identity_groups": [],
        "provider_ids_reconciled": 0,
    }
    with pytest.raises(BaselineMismatch, match="changed=1"):
        reconcile_baseline(baseline, [SourceObject("camara/b.jsonl.gz", 21)])
    with pytest.raises(BaselineMismatch, match="duplicado"):
        reconcile_baseline(baseline, [baseline[0], baseline[0], baseline[1]])


def test_readonly_rclone_config_requires_exact_scope_and_root(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)

    validate_rclone_readonly_config(
        _redacted_readonly_config(),
        remote="raw-source-ro",
        expected_folder_id=SOURCE_FOLDER_ID,
    )
    with pytest.raises(SourceError, match="drive.readonly"):
        validate_rclone_readonly_config(
            _redacted_readonly_config(scope="drive"),
            remote="raw-source-ro",
            expected_folder_id=SOURCE_FOLDER_ID,
        )
    with pytest.raises(SourceError, match="root_folder_id"):
        validate_rclone_readonly_config(
            _redacted_readonly_config().replace(
                "root_folder_id = XXX", "root_folder_id = other-folder-id"
            ),
            remote="raw-source-ro",
            expected_folder_id=SOURCE_FOLDER_ID,
        )


def test_rclone_config_inspection_requires_encryption_keychain_and_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    monkeypatch.delenv("RCLONE_CONFIG_PASS", raising=False)
    monkeypatch.setenv(
        "RCLONE_PASSWORD_COMMAND",
        "/usr/bin/security find-generic-password -a rclone -s falando-nela -w",
    )
    commands: list[list[str]] = []

    def config_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[1:4] == ["config", "encryption", "check"]:
            return subprocess.CompletedProcess(command, 0, "config encrypted", "")
        assert command[1:3] == ["config", "redacted"]
        return subprocess.CompletedProcess(command, 0, _redacted_readonly_config(), "")

    monkeypatch.setattr(subprocess, "run", config_run)

    snapshot = inspect_rclone_config(config, executable="true")

    assert snapshot.redacted_config == _redacted_readonly_config()
    assert SENTINEL_TOKEN not in snapshot.redacted_config
    assert all("--ask-password=false" in command for command in commands)
    assert len(commands) == 2

    config.chmod(0o644)
    with pytest.raises(SourceError, match="permissões privadas"):
        inspect_rclone_config(config, executable="true")


def test_rclone_config_inspection_never_echoes_command_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    monkeypatch.delenv("RCLONE_CONFIG_PASS", raising=False)
    monkeypatch.setenv("RCLONE_PASSWORD_COMMAND", "/usr/bin/false")

    def failed_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 7, "", f"falha com {SENTINEL_TOKEN}")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(SourceError) as captured:
        inspect_rclone_config(config, executable="true")

    assert SENTINEL_TOKEN not in str(captured.value)


def test_rclone_config_inspection_requires_password_command_not_plain_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    monkeypatch.delenv("RCLONE_CONFIG_PASS", raising=False)
    monkeypatch.delenv("RCLONE_PASSWORD_COMMAND", raising=False)

    with pytest.raises(SourceError, match="RCLONE_PASSWORD_COMMAND"):
        inspect_rclone_config(config, executable="true")

    monkeypatch.setenv("RCLONE_CONFIG_PASS", SENTINEL_TOKEN)
    monkeypatch.setenv("RCLONE_PASSWORD_COMMAND", "/usr/bin/false")
    with pytest.raises(SourceError, match="RCLONE_CONFIG_PASS") as captured:
        inspect_rclone_config(config, executable="true")

    assert SENTINEL_TOKEN not in str(captured.value)


def test_rclone_source_allowlist_and_error_do_not_expose_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    source = RcloneRawSource(
        remote="raw-source-ro",
        config_path=config,
        prefix="senado",
        expected_folder_id=SOURCE_FOLDER_ID,
        executable="true",
        config_snapshot=_snapshot(config),
    )

    command = source._command("cat", source._remote_path("file.jsonl"))
    assert command[1] == "cat"
    assert command[2] == f"raw-source-ro,root_folder_id={SOURCE_FOLDER_ID}:file.jsonl"
    with pytest.raises(SourceError, match="proibido"):
        source._command("copy", "origem", "destino")

    def failed_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 7, "", f"falha com {SENTINEL_TOKEN}")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(SourceError) as captured:
        source.list_objects()

    assert SENTINEL_TOKEN not in str(captured.value)
    assert SENTINEL_TOKEN not in str(source.descriptor())


def test_rclone_source_can_inventory_all_files_for_g01_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    payload = (
        '[{"Path":"senado/run.jsonl","Size":10,"ID":"raw-id"},'
        '{"Path":"controle.ipynb","Size":20,"ID":"notebook-id"},'
        '{"Path":"LEIAME","Size":30,"ID":"readme-id"}]'
    )

    def listed(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, payload, "")

    monkeypatch.setattr(subprocess, "run", listed)
    common = {
        "remote": "raw-source-ro",
        "config_path": config,
        "prefix": "",
        "expected_folder_id": SOURCE_FOLDER_ID,
        "executable": "true",
        "config_snapshot": _snapshot(config),
    }

    raw_only = RcloneRawSource(**common).list_objects()
    all_files = RcloneRawSource(**common, include_all_files=True).list_objects()

    assert [item.locator for item in raw_only] == ["senado/run.jsonl"]
    assert [item.locator for item in all_files] == [
        "LEIAME",
        "controle.ipynb",
        "senado/run.jsonl",
    ]
    assert [item.provider_id for item in all_files] == [
        "readme-id",
        "notebook-id",
        "raw-id",
    ]


def test_rclone_source_can_expose_locators_relative_to_physical_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "rclone.conf"
    _write_encrypted_config(config)
    payload = '[{"Path":"senado/run.jsonl","Size":10,"ID":"raw-id"}]'
    commands: list[list[str]] = []

    def listed(command, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(list(command))
        return subprocess.CompletedProcess([], 0, payload, "")

    monkeypatch.setattr(subprocess, "run", listed)
    source = RcloneRawSource(
        remote="raw-source-ro",
        config_path=config,
        prefix="v1",
        expected_folder_id=SOURCE_FOLDER_ID,
        executable="true",
        config_snapshot=_snapshot(config),
        include_all_files=True,
        locators_relative_to_prefix=True,
    )

    objects = source.list_objects()

    assert [item.locator for item in objects] == ["senado/run.jsonl"]
    assert commands[0][2] == f"raw-source-ro,root_folder_id={SOURCE_FOLDER_ID}:v1"
    assert source.descriptor()["prefix"] == "v1"
    assert source.descriptor()["locators"] == "relative_to_prefix"


def test_provider_identity_map_reconciles_duplicate_drive_paths(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "g01.csv"
    baseline_csv.write_text(
        "item_type,relative_path,size_bytes\n"
        "file,camara/ano=1900/Untitled,306\n"
        "file,camara/ano=1900/Untitled (1),306\n"
        "file,senado/run.jsonl,10\n",
        encoding="utf-8",
    )
    identity_path = tmp_path / "provider-identity-map.json"
    identity_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_folder_id": SOURCE_FOLDER_ID,
                "baseline_file_id": "baseline-file-id",
                "baseline_sha256": "a" * 64,
                "groups": [
                    {
                        "group_id": "untitled-collision",
                        "observed_locator": "camara/ano=1900/Untitled",
                        "provider_ids": ["drive-a", "drive-b"],
                        "baseline_locators": [
                            "camara/ano=1900/Untitled",
                            "camara/ano=1900/Untitled (1)",
                        ],
                        "size_bytes": 306,
                        "sha256": "b" * 64,
                        "decision": "exclude_unsupported_format",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    baseline = load_g01_baseline(baseline_csv)
    identity_map = load_provider_identity_map(identity_path)
    current = [
        SourceObject(
            "camara/ano=1900/Untitled",
            306,
            provider_hashes={"sha256": "b" * 64},
            provider_id="drive-a",
        ),
        SourceObject(
            "camara/ano=1900/Untitled",
            306,
            provider_hashes={"sha256": "b" * 64},
            provider_id="drive-b",
        ),
        SourceObject("senado/run.jsonl", 10, provider_id="drive-c"),
    ]

    summary = reconcile_baseline(baseline, current, identity_map=identity_map)

    assert summary["files"] == 3
    assert summary["bytes"] == 622
    assert summary["provider_ids_reconciled"] == 2
    assert summary["identity_groups"][0]["group_id"] == "untitled-collision"

    with pytest.raises(BaselineMismatch, match="provider_id ausente"):
        reconcile_baseline(baseline, [current[0], current[2]], identity_map=identity_map)
