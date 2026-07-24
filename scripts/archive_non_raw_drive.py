from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
DEFAULT_ARCHIVE_ROOT = Path(
    "/content/drive/MyDrive/falando_nela/arquivo/"
    "data_pos_coleta_v1_arquivado_20260724"
)
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_archive_non_raw")
PROTECTED_NAME = "raw"
PLAN_FIELDS = (
    "name",
    "source",
    "destination",
    "item_type",
    "descendants",
    "files",
    "directories",
    "size_bytes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_operation_id(operation_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", operation_id):
        raise ValueError(f"operation_id invalido: {operation_id}")


def validate_roots(data_root: Path, archive_root: Path) -> None:
    data_resolved = data_root.resolve()
    archive_resolved = archive_root.resolve()
    if not data_root.is_dir():
        raise FileNotFoundError(f"raiz de dados ausente: {data_root}")
    if not (data_root / PROTECTED_NAME).is_dir():
        raise FileNotFoundError(f"raw protegido ausente: {data_root / PROTECTED_NAME}")
    if archive_resolved == data_resolved or data_resolved in archive_resolved.parents:
        raise ValueError("o arquivo deve ficar fora da raiz data")


def tree_stats(path: Path) -> dict[str, int]:
    descendants = 0
    files = 0
    directories = 0
    size_bytes = 0
    if path.is_file():
        return {
            "descendants": 0,
            "files": 1,
            "directories": 0,
            "size_bytes": path.stat().st_size,
        }
    for child in path.rglob("*"):
        descendants += 1
        if child.is_file():
            files += 1
            size_bytes += child.stat().st_size
        elif child.is_dir():
            directories += 1
    return {
        "descendants": descendants,
        "files": files,
        "directories": directories,
        "size_bytes": size_bytes,
    }


def tree_fingerprint(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    items = 0
    size_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        item_type = "file" if path.is_file() else "directory"
        size = stat.st_size if path.is_file() else 0
        digest.update(f"{relative}\0{item_type}\0{size}\n".encode())
        items += 1
        size_bytes += size
    return digest.hexdigest(), items, size_bytes


def build_plan(
    *,
    data_root: Path,
    archive_root: Path,
    operation_id: str,
) -> dict[str, Any]:
    validate_operation_id(operation_id)
    validate_roots(data_root, archive_root)
    candidates = sorted(
        (
            path
            for path in data_root.iterdir()
            if path.name != PROTECTED_NAME
        ),
        key=lambda path: path.name.casefold(),
    )
    raw_hash, raw_items, raw_size_bytes = tree_fingerprint(
        data_root / PROTECTED_NAME
    )
    rows = []
    for source in candidates:
        stats = tree_stats(source)
        rows.append(
            {
                "name": source.name,
                "source": str(source),
                "destination": str(archive_root / source.name),
                "item_type": "file" if source.is_file() else "directory",
                **stats,
            }
        )
    return {
        "operation_id": operation_id,
        "created_at": utc_now(),
        "status": "planned",
        "data_root": str(data_root),
        "archive_root": str(archive_root),
        "protected_path": str(data_root / PROTECTED_NAME),
        "protected_raw_fingerprint": raw_hash,
        "protected_raw_items": raw_items,
        "protected_raw_size_bytes": raw_size_bytes,
        "candidate_count": len(rows),
        "candidates": rows,
        "rule": "move every direct child of data except raw",
    }


def write_plan(plan: dict[str, Any], operation_root: Path) -> tuple[Path, Path]:
    if operation_root.exists():
        raise FileExistsError(
            f"operation_id ja possui artefatos: {operation_root}"
        )
    operation_root.mkdir(parents=True)
    plan_json = operation_root / "plan.json"
    plan_csv = operation_root / "plan.csv"
    plan_json.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with plan_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_FIELDS)
        writer.writeheader()
        writer.writerows(plan["candidates"])
    return plan_json, plan_csv


def load_plan(operation_root: Path) -> dict[str, Any]:
    return json.loads((operation_root / "plan.json").read_text(encoding="utf-8"))


def verify_raw(plan: dict[str, Any]) -> None:
    raw_path = Path(plan["protected_path"])
    fingerprint, items, size_bytes = tree_fingerprint(raw_path)
    expected = (
        plan["protected_raw_fingerprint"],
        plan["protected_raw_items"],
        plan["protected_raw_size_bytes"],
    )
    observed = (fingerprint, items, size_bytes)
    if observed != expected:
        raise RuntimeError(
            "raw mudou desde o plano; operacao bloqueada: "
            f"esperado={expected}, observado={observed}"
        )


def execute_plan(
    *,
    operation_root: Path,
    confirmation: str,
) -> dict[str, Any]:
    plan = load_plan(operation_root)
    operation_id = str(plan["operation_id"])
    if confirmation != operation_id:
        raise ValueError("confirmacao nao corresponde ao operation_id")

    data_root = Path(plan["data_root"])
    archive_root = Path(plan["archive_root"])
    validate_roots(data_root, archive_root)
    verify_raw(plan)

    archive_root.mkdir(parents=True, exist_ok=True)
    current_non_raw = {
        path.name for path in data_root.iterdir() if path.name != PROTECTED_NAME
    }
    planned_names = {row["name"] for row in plan["candidates"]}
    unexpected_sources = sorted(current_non_raw - planned_names)
    if unexpected_sources:
        raise RuntimeError(
            "novos itens nao-raw apareceram desde o plano: "
            f"{unexpected_sources}"
        )
    allowed_archive_names = planned_names | {f"{operation_id}.manifest.json"}
    unexpected_archive = sorted(
        path.name
        for path in archive_root.iterdir()
        if path.name not in allowed_archive_names
    )
    if unexpected_archive:
        raise RuntimeError(
            "destino contem itens que nao pertencem ao plano: "
            f"{unexpected_archive}"
        )

    events: list[dict[str, str]] = []
    execution_path = operation_root / "execution.json"
    for row in plan["candidates"]:
        source = Path(row["source"])
        destination = Path(row["destination"])
        if source.exists() and destination.exists():
            raise RuntimeError(
                f"item existe na origem e no destino: {row['name']}"
            )
        if not source.exists() and not destination.exists():
            raise FileNotFoundError(
                f"item ausente na origem e no destino: {row['name']}"
            )
        if source.exists():
            shutil.move(str(source), str(destination))
            state = "moved"
        else:
            state = "already_moved"
        events.append(
            {
                "name": row["name"],
                "source": str(source),
                "destination": str(destination),
                "state": state,
                "moved_at": utc_now(),
            }
        )
        execution_path.write_text(
            json.dumps(
                {
                    "operation_id": operation_id,
                    "status": "running",
                    "events": events,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    verify_raw(plan)
    remaining = sorted(path.name for path in data_root.iterdir())
    if remaining != [PROTECTED_NAME]:
        raise RuntimeError(f"itens inesperados permaneceram em data: {remaining}")
    missing = [
        row["name"]
        for row in plan["candidates"]
        if not Path(row["destination"]).exists()
    ]
    if missing:
        raise RuntimeError(f"itens ausentes no arquivo: {missing}")

    execution = {
        "operation_id": operation_id,
        "status": "succeeded",
        "finished_at": utc_now(),
        "data_root_children": remaining,
        "archive_root": str(archive_root),
        "moved_items": len(events),
        "events": events,
        "raw_fingerprint": plan["protected_raw_fingerprint"],
        "raw_items": plan["protected_raw_items"],
        "raw_size_bytes": plan["protected_raw_size_bytes"],
    }
    execution_path.write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    archive_manifest = archive_root / f"{operation_id}.manifest.json"
    archive_manifest.write_text(
        json.dumps(execution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return execution


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arquiva todos os filhos de data exceto raw."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--operation-id", required=True)
    plan_parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    plan_parser.add_argument(
        "--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT
    )
    plan_parser.add_argument(
        "--output-base", type=Path, default=DEFAULT_OUTPUT_BASE
    )
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--operation-id", required=True)
    execute_parser.add_argument("--confirm", required=True)
    execute_parser.add_argument(
        "--output-base", type=Path, default=DEFAULT_OUTPUT_BASE
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    operation_root = args.output_base / args.operation_id
    if args.command == "plan":
        plan = build_plan(
            data_root=args.data_root,
            archive_root=args.archive_root,
            operation_id=args.operation_id,
        )
        plan_json, plan_csv = write_plan(plan, operation_root)
        print(f"Plano: {plan_json}")
        print(f"Tabela: {plan_csv}")
        print(f"Itens candidatos: {plan['candidate_count']}")
        print("Drive alterado: nao")
        return 0
    execution = execute_plan(
        operation_root=operation_root,
        confirmation=args.confirm,
    )
    print(json.dumps(execution, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
