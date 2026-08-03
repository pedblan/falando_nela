from __future__ import annotations

import json
from pathlib import Path

from falando_nela.cli import main
from falando_nela.doctor import run_doctor


def test_doctor_reports_missing_data_root_without_network(tmp_path: Path) -> None:
    payload, return_code = run_doctor(environ={}, repo_root=tmp_path / "repo")

    assert return_code == 2
    assert payload["status"] == "error"
    assert payload["configuration"] is None


def test_doctor_accepts_external_root_without_creating_it(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "external-data"
    repo_root.mkdir()

    payload, return_code = run_doctor(
        environ={},
        repo_root=repo_root,
        data_root=data_root,
    )

    assert return_code == 0
    assert payload["status"] == "ok"
    assert not data_root.exists()
    capacity = next(check for check in payload["checks"] if check["id"] == "disk_capacity")
    assert capacity["status"] == "ok"
    assert capacity["detail"]["required_free_bytes"] == 7 * 1024**3


def test_cli_json_keeps_stdout_machine_readable(tmp_path: Path, capsys) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "external-data"
    repo_root.mkdir()

    return_code = main(
        [
            "doctor",
            "--json",
            "--repo-root",
            str(repo_root),
            "--data-root",
            str(data_root),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert return_code == 0
    assert captured.err == ""
    assert payload["configuration"]["data_root"] == str(data_root)
