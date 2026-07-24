from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.archive_non_raw_drive import (
    build_plan,
    execute_plan,
    tree_fingerprint,
    write_plan,
)


def make_tree(root: Path) -> tuple[Path, Path]:
    data_root = root / "falando_nela" / "data"
    archive_root = root / "falando_nela" / "arquivo" / "v1"
    (data_root / "raw" / "senado").mkdir(parents=True)
    (data_root / "raw" / "senado" / "2010.json").write_text(
        "raw", encoding="utf-8"
    )
    (data_root / "processed").mkdir()
    (data_root / "processed" / "base.parquet").write_bytes(b"parquet")
    (data_root / "operations").mkdir()
    (data_root / "Untitled0.ipynb").write_text("{}", encoding="utf-8")
    return data_root, archive_root


def test_plan_protects_raw_and_lists_every_other_direct_child(
    tmp_path: Path,
) -> None:
    data_root, archive_root = make_tree(tmp_path)
    plan = build_plan(
        data_root=data_root,
        archive_root=archive_root,
        operation_id="archive-non-raw-test",
    )

    assert [row["name"] for row in plan["candidates"]] == [
        "operations",
        "processed",
        "Untitled0.ipynb",
    ]
    assert plan["protected_path"] == str(data_root / "raw")
    assert plan["candidate_count"] == 3


def test_execute_moves_non_raw_and_preserves_raw_fingerprint(
    tmp_path: Path,
) -> None:
    data_root, archive_root = make_tree(tmp_path)
    raw_before = tree_fingerprint(data_root / "raw")
    operation_root = tmp_path / "runtime" / "archive-non-raw-test"
    plan = build_plan(
        data_root=data_root,
        archive_root=archive_root,
        operation_id="archive-non-raw-test",
    )
    write_plan(plan, operation_root)

    execution = execute_plan(
        operation_root=operation_root,
        confirmation="archive-non-raw-test",
    )

    assert execution["status"] == "succeeded"
    assert sorted(path.name for path in data_root.iterdir()) == ["raw"]
    assert tree_fingerprint(data_root / "raw") == raw_before
    assert (archive_root / "processed" / "base.parquet").read_bytes() == b"parquet"
    assert (archive_root / "archive-non-raw-test.manifest.json").exists()


def test_execute_requires_literal_confirmation(tmp_path: Path) -> None:
    data_root, archive_root = make_tree(tmp_path)
    operation_root = tmp_path / "runtime" / "archive-non-raw-test"
    plan = build_plan(
        data_root=data_root,
        archive_root=archive_root,
        operation_id="archive-non-raw-test",
    )
    write_plan(plan, operation_root)

    with pytest.raises(ValueError, match="confirmacao"):
        execute_plan(operation_root=operation_root, confirmation="sim")
    assert sorted(path.name for path in data_root.iterdir()) == [
        "Untitled0.ipynb",
        "operations",
        "processed",
        "raw",
    ]


def test_execute_resumes_after_one_planned_item_was_moved(
    tmp_path: Path,
) -> None:
    data_root, archive_root = make_tree(tmp_path)
    operation_root = tmp_path / "runtime" / "archive-non-raw-test"
    plan = build_plan(
        data_root=data_root,
        archive_root=archive_root,
        operation_id="archive-non-raw-test",
    )
    write_plan(plan, operation_root)
    archive_root.mkdir(parents=True)
    (data_root / "operations").rename(archive_root / "operations")

    execution = execute_plan(
        operation_root=operation_root,
        confirmation="archive-non-raw-test",
    )

    states = {event["name"]: event["state"] for event in execution["events"]}
    assert states["operations"] == "already_moved"
    assert states["processed"] == "moved"
    assert sorted(path.name for path in data_root.iterdir()) == ["raw"]


def test_plan_is_not_overwritten(tmp_path: Path) -> None:
    data_root, archive_root = make_tree(tmp_path)
    operation_root = tmp_path / "runtime" / "archive-non-raw-test"
    plan = build_plan(
        data_root=data_root,
        archive_root=archive_root,
        operation_id="archive-non-raw-test",
    )
    write_plan(plan, operation_root)

    with pytest.raises(FileExistsError, match="ja possui"):
        write_plan(plan, operation_root)
    assert json.loads((operation_root / "plan.json").read_text())["status"] == (
        "planned"
    )
