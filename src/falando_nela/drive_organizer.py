from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from falando_nela.operations import RecoverableOperation, artifact_metadata, fingerprint
from falando_nela.raw import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    sha256_file,
)
from falando_nela.sources import (
    BaselineMismatch,
    ProviderIdentityMap,
    RcloneConfigSnapshot,
    SourceError,
    SourceObject,
    inspect_rclone_config,
    load_g01_baseline,
    load_provider_identity_map,
    parse_redacted_rclone_config,
    pinned_rclone_remote_path,
    reconcile_baseline,
    validate_rclone_readonly_config,
)

CANONICAL_PREFIX = "data/raw/v1"
ORGANIZED_DATASETS = {
    ("camara", "ccjc_eventos"),
    ("camara", "pareceres_pec"),
    ("camara", "parlamentares"),
    ("camara", "plenario_apartes"),
    ("camara", "plenario_discursos"),
    ("senado", "ccj_notas"),
    ("senado", "congresso_discursos"),
    ("senado", "pareceres_pec"),
    ("senado", "parlamentares"),
    ("senado", "plenario_apartes"),
    ("senado", "plenario_discursos"),
}
TEXTUAL_DATASETS = {
    ("camara", "ccjc_eventos"),
    ("camara", "pareceres_pec"),
    ("camara", "plenario_discursos"),
    ("senado", "ccj_notas"),
    ("senado", "congresso_discursos"),
    ("senado", "pareceres_pec"),
    ("senado", "plenario_discursos"),
}
METADATA_ONLY_DATASETS = {
    ("camara", "parlamentares"),
    ("camara", "plenario_apartes"),
    ("senado", "parlamentares"),
    ("senado", "plenario_apartes"),
}


class LayoutError(ValueError):
    """Caminho raw não pode ser mapeado sem alterar seu contrato."""


class CopyConflict(SourceError):
    """O destino existe, diverge ou não pode ser confirmado com hash."""


class CopyResultAmbiguous(SourceError):
    """O efeito remoto não pôde ser reconciliado depois de uma falha."""


class InventorySource(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]: ...


@dataclass(frozen=True)
class LayoutClassification:
    source: str
    dataset: str
    category: str
    periodicity: str
    year: int | None = None
    month: int | None = None


@dataclass(frozen=True)
class CopyPlanEntry:
    source_locator: str
    destination_locator: str
    size_bytes: int
    provider_hashes: dict[str, str]
    category: str
    periodicity: str
    source: str
    dataset: str
    year: int | None
    month: int | None
    decision: str = "copy_immutable"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExcludedPlanEntry:
    source_locator: str
    provider_id: str | None
    size_bytes: int
    decision: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CopyPlan:
    entries: tuple[CopyPlanEntry, ...]
    excluded_out_of_scope: tuple[str, ...]
    excluded_entries: tuple[ExcludedPlanEntry, ...] = ()

    @property
    def files(self) -> int:
        return len(self.entries)

    @property
    def bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.entries)

    @property
    def excluded_files(self) -> int:
        return len(self.excluded_entries)

    @property
    def excluded_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.excluded_entries)


def classify_raw_locator(locator: str) -> LayoutClassification | None:
    path = PurePosixPath(locator)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 3:
        raise LayoutError(f"caminho raw inseguro ou incompleto: {locator}")
    source, dataset = path.parts[:2]
    scope = (source, dataset)
    if scope not in ORGANIZED_DATASETS:
        if source in {"camara", "senado"}:
            raise LayoutError(f"dataset parlamentar fora do escopo explícito: {locator}")
        return None
    if not (locator.endswith(".jsonl") or locator.endswith(".jsonl.gz")):
        raise LayoutError(f"arquivo não JSONL no escopo organizado: {locator}")
    tail = path.parts[2:]
    if tail[0] == "metadata":
        if len(tail) < 2:
            raise LayoutError(f"metadata sem arquivo: {locator}")
        return LayoutClassification(source, dataset, "metadata", "source_defined")
    if tail[0] == "transcription_queue":
        if len(tail) < 2:
            raise LayoutError(f"transcription_queue sem arquivo: {locator}")
        return LayoutClassification(source, dataset, "transcription_queue", "source_defined")
    if len(tail) < 3:
        raise LayoutError(f"partição textual incompleta: {locator}")
    year_match = re.fullmatch(r"ano=(\d{4})", tail[0])
    month_match = re.fullmatch(r"mes=(\d{2})", tail[1])
    if year_match is None or month_match is None:
        if scope in METADATA_ONLY_DATASETS:
            raise LayoutError(f"dataset metadata-only contém corpus textual: {locator}")
        raise LayoutError(f"corpus textual fora de ano=YYYY/mes=MM: {locator}")
    month = int(month_match.group(1))
    if not 1 <= month <= 12:
        raise LayoutError(f"mês inválido: {locator}")
    if scope not in TEXTUAL_DATASETS:
        raise LayoutError(f"dataset sem contrato textual mensal: {locator}")
    return LayoutClassification(
        source,
        dataset,
        "monthly_text",
        "monthly",
        year=int(year_match.group(1)),
        month=month,
    )


def build_copy_plan(
    objects: Sequence[SourceObject],
    *,
    canonical_prefix: str = CANONICAL_PREFIX,
    exclusion_decisions: Mapping[str, str] | None = None,
) -> CopyPlan:
    prefix = _safe_prefix(canonical_prefix)
    decisions = dict(exclusion_decisions or {})
    entries: list[CopyPlanEntry] = []
    excluded: list[str] = []
    excluded_entries: list[ExcludedPlanEntry] = []
    consumed_exclusions: set[str] = set()
    destinations: dict[str, str] = {}
    sources: set[str] = set()
    for source_object in sorted(objects, key=lambda item: (item.locator, item.provider_id or "")):
        provider_id = source_object.provider_id
        explicit_decision = decisions.get(provider_id) if provider_id is not None else None
        if explicit_decision is not None:
            consumed_exclusions.add(provider_id)
            excluded.append(source_object.locator)
            excluded_entries.append(
                ExcludedPlanEntry(
                    source_locator=source_object.locator,
                    provider_id=provider_id,
                    size_bytes=source_object.size_bytes,
                    decision=explicit_decision,
                )
            )
            continue
        if source_object.locator in sources:
            raise LayoutError(f"locator de origem duplicado: {source_object.locator}")
        sources.add(source_object.locator)
        classification = classify_raw_locator(source_object.locator)
        if classification is None:
            excluded.append(source_object.locator)
            excluded_entries.append(
                ExcludedPlanEntry(
                    source_locator=source_object.locator,
                    provider_id=provider_id,
                    size_bytes=source_object.size_bytes,
                    decision="exclude_out_of_scope",
                )
            )
            continue
        destination = f"{prefix}/{source_object.locator}"
        previous = destinations.get(destination)
        if previous is not None:
            raise LayoutError(f"colisão de destino entre {previous} e {source_object.locator}")
        destinations[destination] = source_object.locator
        entries.append(
            CopyPlanEntry(
                source_locator=source_object.locator,
                destination_locator=destination,
                size_bytes=source_object.size_bytes,
                provider_hashes=dict(sorted(source_object.provider_hashes.items())),
                category=classification.category,
                periodicity=classification.periodicity,
                source=classification.source,
                dataset=classification.dataset,
                year=classification.year,
                month=classification.month,
            )
        )
    missing_exclusions = sorted(set(decisions) - consumed_exclusions)
    if missing_exclusions:
        raise LayoutError(f"IDs de exclusão ausentes no inventário: {len(missing_exclusions)}")
    return CopyPlan(
        tuple(entries),
        tuple(sorted(excluded)),
        tuple(
            sorted(
                excluded_entries,
                key=lambda item: (item.source_locator, item.provider_id or ""),
            )
        ),
    )


def write_copy_plan(
    plan: CopyPlan,
    *,
    jsonl_path: Path,
    summary_path: Path,
    files_from_path: Path | None = None,
) -> None:
    payload = b"".join(canonical_json_bytes(entry.as_dict()) + b"\n" for entry in plan.entries)
    atomic_write_bytes(jsonl_path, payload)
    if files_from_path is not None:
        write_files_from0(plan.entries, files_from_path)
    categories: dict[str, int] = {}
    for entry in plan.entries:
        categories[entry.category] = categories.get(entry.category, 0) + 1
    summary: dict[str, Any] = {
        "files": plan.files,
        "bytes": plan.bytes,
        "excluded_files": plan.excluded_files,
        "excluded_bytes": plan.excluded_bytes,
        "excluded": [item.as_dict() for item in plan.excluded_entries],
        "excluded_out_of_scope": list(plan.excluded_out_of_scope),
        "categories": dict(sorted(categories.items())),
        "plan_path": str(jsonl_path),
        "plan_sha256": sha256_file(jsonl_path),
    }
    if files_from_path is not None:
        summary.update(
            {
                "files_from_path": str(files_from_path),
                "files_from_sha256": sha256_file(files_from_path),
                "files_from_bytes": files_from_path.stat().st_size,
            }
        )
    atomic_write_json(summary_path, summary)


def write_files_from0(entries: Sequence[CopyPlanEntry], path: Path) -> None:
    locators: list[bytes] = []
    for entry in entries:
        if any(character in entry.source_locator for character in ("\x00", "\r", "\n")):
            raise LayoutError(f"locator incompatível com relatório: {entry.source_locator!r}")
        locators.append(entry.source_locator.encode("utf-8"))
    atomic_write_bytes(path, b"\x00".join(locators) + (b"\x00" if locators else b""))


def load_copy_plan(path: Path) -> CopyPlan:
    entries: list[CopyPlanEntry] = []
    try:
        for raw_line in path.read_bytes().splitlines():
            if not raw_line.strip():
                continue
            item = json.loads(raw_line)
            if not isinstance(item, dict):
                raise ValueError("entrada não é objeto")
            entries.append(CopyPlanEntry(**item))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LayoutError("plano de cópia é ilegível") from exc
    if not entries:
        raise LayoutError("plano de cópia está vazio")
    return CopyPlan(tuple(entries), ())


def write_source_inventory(objects: Sequence[SourceObject], path: Path) -> None:
    payload = b"".join(
        canonical_json_bytes(item.fingerprint_dict()) + b"\n"
        for item in sorted(objects, key=lambda item: (item.locator, item.provider_id or ""))
    )
    atomic_write_bytes(path, payload)


def load_source_inventory(path: Path) -> list[SourceObject]:
    objects: list[SourceObject] = []
    try:
        lines = path.read_bytes().splitlines()
        for line in lines:
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("item não é objeto")
            locator = item.get("locator")
            size_bytes = item.get("size_bytes")
            if not isinstance(locator, str) or not isinstance(size_bytes, int):
                raise ValueError("locator ou size inválido")
            raw_hashes = item.get("provider_hashes", {})
            if not isinstance(raw_hashes, dict):
                raise ValueError("provider_hashes inválido")
            objects.append(
                SourceObject(
                    locator=locator,
                    size_bytes=size_bytes,
                    provider_id=(
                        item.get("provider_id")
                        if isinstance(item.get("provider_id"), str)
                        else None
                    ),
                    sha256=item.get("sha256") if isinstance(item.get("sha256"), str) else None,
                    provider_hashes={str(key): str(value) for key, value in raw_hashes.items()},
                    modified_time=(
                        item.get("modified_time")
                        if isinstance(item.get("modified_time"), str)
                        else None
                    ),
                )
            )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise LayoutError("inventário de origem é ilegível") from exc
    return sorted(objects, key=lambda item: (item.locator, item.provider_id or ""))


def validate_rclone_destination_config(
    redacted_config: str, *, remote: str, expected_folder_id: str
) -> None:
    pinned_rclone_remote_path(remote, expected_folder_id)
    parser = parse_redacted_rclone_config(redacted_config)
    if not parser.has_section(remote):
        raise SourceError(f"remote rclone ausente: {remote}")
    if parser.get(remote, "type", fallback="").strip() != "drive":
        raise SourceError("o remote de destino deve usar type=drive")
    if parser.get(remote, "scope", fallback="").strip() != "drive.file":
        raise SourceError("o remote de destino deve usar scope=drive.file")
    configured_root = parser.get(remote, "root_folder_id", fallback="").strip()
    if configured_root not in {expected_folder_id, "XXX"}:
        raise SourceError("root_folder_id do destino não coincide com a pasta aprovada")


class RcloneCopyTransport:
    def __init__(
        self,
        *,
        config_path: Path,
        source_remote: str,
        source_folder_id: str,
        destination_remote: str,
        destination_folder_id: str,
        executable: str = "rclone",
        config_snapshot: RcloneConfigSnapshot | None = None,
    ) -> None:
        if source_remote == destination_remote:
            raise SourceError("origem e destino devem usar remotes distintos")
        for remote in (source_remote, destination_remote):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", remote):
                raise SourceError("nome de remote rclone inválido")
        self.config_path = config_path.expanduser().resolve(strict=True)
        self.source_remote = source_remote
        self.source_folder_id = source_folder_id
        self.destination_remote = destination_remote
        self.destination_folder_id = destination_folder_id
        pinned_rclone_remote_path(self.source_remote, self.source_folder_id)
        pinned_rclone_remote_path(self.destination_remote, self.destination_folder_id)
        self.executable = executable
        if shutil.which(self.executable) is None:
            raise SourceError("rclone não está instalado ou não está no PATH")
        snapshot = config_snapshot or inspect_rclone_config(
            self.config_path,
            executable=self.executable,
        )
        if snapshot.config_path != self.config_path:
            raise SourceError("snapshot rclone não pertence ao arquivo de configuração informado")
        validate_rclone_readonly_config(
            snapshot.redacted_config,
            remote=source_remote,
            expected_folder_id=source_folder_id,
        )
        validate_rclone_destination_config(
            snapshot.redacted_config,
            remote=destination_remote,
            expected_folder_id=destination_folder_id,
        )

    def copy_command(self, entry: CopyPlanEntry, *, dry_run: bool) -> list[str]:
        command = [
            self.executable,
            "copyto",
            pinned_rclone_remote_path(
                self.source_remote,
                self.source_folder_id,
                entry.source_locator,
            ),
            pinned_rclone_remote_path(
                self.destination_remote,
                self.destination_folder_id,
                entry.destination_locator,
            ),
            "--immutable",
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]
        if dry_run:
            command.append("--dry-run")
        return command

    def execute_copy(self, entry: CopyPlanEntry, *, dry_run: bool) -> dict[str, Any]:
        result = subprocess.run(
            self.copy_command(entry, dry_run=dry_run),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SourceError(
                f"rclone copyto falhou (exit {result.returncode}); consulte o log local protegido"
            )
        return {
            "source_locator": entry.source_locator,
            "destination_locator": entry.destination_locator,
            "dry_run": dry_run,
            "return_code": result.returncode,
        }

    def dry_run_command(self, *, files_from_path: Path, combined_path: Path) -> list[str]:
        return [
            self.executable,
            "copy",
            pinned_rclone_remote_path(
                self.source_remote,
                self.source_folder_id,
            ),
            pinned_rclone_remote_path(
                self.destination_remote,
                self.destination_folder_id,
                CANONICAL_PREFIX,
            ),
            "--files-from0",
            str(files_from_path),
            "--combined",
            str(combined_path),
            "--dry-run",
            "--immutable",
            "--checksum",
            "--check-first",
            "--retries",
            "1",
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]

    def execute_dry_run(
        self,
        entries: Sequence[CopyPlanEntry],
        *,
        files_from_path: Path,
        combined_path: Path,
    ) -> dict[str, Any]:
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{combined_path.name}.",
            suffix=".rclone.tmp",
            dir=combined_path.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            result = subprocess.run(
                self.dry_run_command(
                    files_from_path=files_from_path,
                    combined_path=temporary,
                ),
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise SourceError(
                    f"rclone dry-run falhou (exit {result.returncode}); "
                    "consulte o log local protegido"
                )
            summary = validate_combined_dry_run(entries, temporary)
            atomic_write_bytes(combined_path, temporary.read_bytes())
            return {
                **summary,
                "return_code": result.returncode,
                "combined_path": str(combined_path),
                "combined_sha256": sha256_file(combined_path),
                "combined_bytes": combined_path.stat().st_size,
            }
        finally:
            temporary.unlink(missing_ok=True)

    def destination_stat_command(self, entry: CopyPlanEntry) -> list[str]:
        return [
            self.executable,
            "lsjson",
            pinned_rclone_remote_path(
                self.destination_remote,
                self.destination_folder_id,
                entry.destination_locator,
            ),
            "--stat",
            "--hash",
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]

    def destination_list_command(self) -> list[str]:
        return [
            self.executable,
            "lsjson",
            pinned_rclone_remote_path(
                self.destination_remote,
                self.destination_folder_id,
            ),
            "--recursive",
            "--hash",
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]

    def destination_entry_count(self) -> int:
        result = subprocess.run(
            self.destination_list_command(),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SourceError(
                f"rclone lsjson do destino falhou (exit {result.returncode}); "
                "consulte o log local protegido"
            )
        try:
            items = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SourceError("rclone lsjson do destino retornou JSON inválido") from exc
        if not isinstance(items, list):
            raise SourceError("rclone lsjson do destino não retornou uma lista")
        return len(items)

    def destination_stat(self, entry: CopyPlanEntry) -> SourceObject | None:
        result = subprocess.run(
            self.destination_stat_command(entry),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            lowered = result.stderr.lower()
            if "not found" in lowered or "directory not found" in lowered:
                return None
            raise SourceError("não foi possível reconciliar o destino")
        try:
            item = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SourceError("rclone lsjson --stat retornou JSON inválido") from exc
        if not isinstance(item, dict) or not isinstance(item.get("Size"), int):
            raise SourceError("rclone lsjson --stat retornou objeto inválido")
        hashes = item.get("Hashes") if isinstance(item.get("Hashes"), dict) else {}
        return SourceObject(
            locator=entry.destination_locator,
            size_bytes=item["Size"],
            provider_hashes={str(key): str(value) for key, value in hashes.items()},
            modified_time=str(item.get("ModTime")) if item.get("ModTime") else None,
        )

    def copy_entry(self, entry: CopyPlanEntry, *, dry_run: bool) -> dict[str, Any]:
        observed_before = self.destination_stat(entry)
        if observed_before is not None:
            if not destination_matches(entry, observed_before):
                raise CopyConflict(f"destino existente diverge: {entry.destination_locator}")
            return {
                "source_locator": entry.source_locator,
                "destination_locator": entry.destination_locator,
                "status": "reused_verified",
                "dry_run": dry_run,
            }
        if dry_run:
            self.execute_copy(entry, dry_run=True)
            return {
                "source_locator": entry.source_locator,
                "destination_locator": entry.destination_locator,
                "status": "dry_run_planned",
                "dry_run": True,
            }
        try:
            self.execute_copy(entry, dry_run=False)
        except SourceError as exc:
            observed_after_error = self.destination_stat(entry)
            if observed_after_error is not None and destination_matches(
                entry, observed_after_error
            ):
                return {
                    "source_locator": entry.source_locator,
                    "destination_locator": entry.destination_locator,
                    "status": "reconciled_after_error",
                    "dry_run": False,
                }
            raise CopyResultAmbiguous(
                f"resultado remoto ambíguo: {entry.destination_locator}"
            ) from exc
        observed_after = self.destination_stat(entry)
        if observed_after is None or not destination_matches(entry, observed_after):
            raise CopyConflict(f"cópia não confirmada por hash: {entry.destination_locator}")
        return {
            "source_locator": entry.source_locator,
            "destination_locator": entry.destination_locator,
            "status": "copied_verified",
            "dry_run": False,
        }


def destination_matches(entry: CopyPlanEntry, observed: SourceObject) -> bool:
    if entry.size_bytes != observed.size_bytes:
        return False
    common_hashes = set(entry.provider_hashes) & set(observed.provider_hashes)
    if not common_hashes:
        return False
    return all(
        entry.provider_hashes[name] == observed.provider_hashes[name] for name in common_hashes
    )


def validate_combined_dry_run(
    entries: Sequence[CopyPlanEntry], combined_path: Path
) -> dict[str, Any]:
    expected = {entry.source_locator for entry in entries}
    if len(expected) != len(entries):
        raise LayoutError("plano do dry-run contém locator duplicado")
    observed: dict[str, str] = {}
    try:
        for line in combined_path.read_text(encoding="utf-8").splitlines():
            if len(line) < 3 or line[1:2] != " ":
                raise ValueError("linha combinada inválida")
            marker, locator = line[0], line[2:]
            if marker not in {"+", "=", "-", "*", "!"} or not locator:
                raise ValueError("marcador combinado inválido")
            if locator in observed:
                raise ValueError("locator duplicado no relatório combinado")
            observed[locator] = marker
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise LayoutError("relatório combinado do dry-run é inválido") from exc
    missing = sorted(expected - set(observed))
    added = sorted(set(observed) - expected)
    unexpected_markers = sorted(locator for locator, marker in observed.items() if marker != "+")
    if missing or added or unexpected_markers:
        raise CopyConflict(
            "dry-run divergiu do plano: "
            f"missing={len(missing)}, added={len(added)}, "
            f"unexpected_markers={len(unexpected_markers)}"
        )
    return {
        "files": len(entries),
        "bytes": sum(entry.size_bytes for entry in entries),
        "markers": {"+": len(entries), "=": 0, "-": 0, "*": 0, "!": 0},
    }


def reconcile_drive_inventory(
    *,
    source: InventorySource,
    baseline_csv: Path,
    provider_identity_map_path: Path,
    data_root: Path,
    operation_id: str,
    source_folder_id: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise LayoutError("operation_id inválido")
    baseline = load_g01_baseline(baseline_csv)
    identity_map = load_provider_identity_map(provider_identity_map_path)
    _validate_identity_map_inputs(
        identity_map,
        baseline_csv=baseline_csv,
        source_folder_id=source_folder_id,
    )
    operation_root = data_root / "operations" / "organize_drive" / operation_id
    configuration = {
        "source": source.descriptor(),
        "source_folder_id": source_folder_id,
        "baseline_file_id": identity_map.baseline_file_id,
        "baseline_sha256": identity_map.baseline_sha256,
        "identity_map": identity_map.fingerprint_dict(),
        "mode": "read_only_reconciliation",
    }
    operation = RecoverableOperation(
        manifest_path=operation_root / "operation.json",
        operation_id=operation_id,
        contract_version=1,
        implementation_version="r03-drive-reconciliation-v1",
        input_fingerprint=fingerprint(
            {
                "baseline": [item.fingerprint_dict() for item in baseline],
                "identity_map": identity_map.fingerprint_dict(),
            }
        ),
        config_fingerprint=fingerprint(configuration),
        stages=(("discover", ()), ("reconcile", ("discover",))),
        configuration=configuration,
    )
    inventory_path = operation_root / "source-inventory.jsonl"
    reconciliation_path = operation_root / "source-reconciliation.json"

    _recover_readonly_interruption(operation, "discover")
    if operation.begin("discover"):
        try:
            current = source.list_objects(prefix="")
            write_source_inventory(current, inventory_path)
            operation.complete("discover", artifact=artifact_metadata(inventory_path))
        except (LayoutError, OSError, SourceError) as exc:
            operation.fail(
                "discover",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    current = load_source_inventory(inventory_path)

    _recover_readonly_interruption(operation, "reconcile")
    if operation.begin("reconcile"):
        try:
            summary = reconcile_baseline(baseline, current, identity_map=identity_map)
            atomic_write_json(
                reconciliation_path,
                {
                    "operation_id": operation_id,
                    "source_folder_id": source_folder_id,
                    "baseline": {
                        "file_id": identity_map.baseline_file_id,
                        "path": str(baseline_csv),
                        "sha256": identity_map.baseline_sha256,
                        "bytes": baseline_csv.stat().st_size,
                    },
                    "identity_map_sha256": sha256_file(provider_identity_map_path),
                    "summary": summary,
                    "status": "reconciled",
                },
            )
            operation.complete("reconcile", artifact=artifact_metadata(reconciliation_path))
        except (BaselineMismatch, LayoutError, OSError, SourceError) as exc:
            operation.fail(
                "reconcile",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    try:
        report = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LayoutError("relatório de reconciliação é ilegível") from exc
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise LayoutError("resumo de reconciliação é inválido")
    return {
        "operation_id": operation_id,
        "status": operation.snapshot()["status"],
        "manifest_path": str(operation.manifest_path),
        "inventory_path": str(inventory_path),
        "reconciliation_path": str(reconciliation_path),
        "files": summary.get("files"),
        "bytes": summary.get("bytes"),
        "provider_ids_reconciled": summary.get("provider_ids_reconciled"),
    }


def _validate_identity_map_inputs(
    identity_map: ProviderIdentityMap,
    *,
    baseline_csv: Path,
    source_folder_id: str,
) -> None:
    if identity_map.source_folder_id != source_folder_id:
        raise BaselineMismatch("source_folder_id diverge do mapa de identidades")
    if sha256_file(baseline_csv) != identity_map.baseline_sha256:
        raise BaselineMismatch("SHA-256 do CSV G01 diverge do mapa de identidades")


def execute_drive_dry_run(
    *,
    transport: RcloneCopyTransport,
    reconciliation_manifest_path: Path,
    source_inventory_path: Path,
    source_reconciliation_path: Path,
    provider_identity_map_path: Path,
    data_root: Path,
    operation_id: str,
    source_folder_id: str,
    destination_folder_id: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise LayoutError("operation_id inválido")
    identity_map = load_provider_identity_map(provider_identity_map_path)
    if identity_map.source_folder_id != source_folder_id:
        raise BaselineMismatch("source_folder_id diverge do mapa de identidades")
    current = load_source_inventory(source_inventory_path)
    _validate_reconciliation_artifacts(
        manifest_path=reconciliation_manifest_path,
        inventory_path=source_inventory_path,
        reconciliation_path=source_reconciliation_path,
        identity_map_path=provider_identity_map_path,
        identity_map=identity_map,
        current=current,
        source_folder_id=source_folder_id,
    )
    exclusion_decisions = {
        provider_id: group.decision
        for group in identity_map.groups
        for provider_id in group.provider_ids
    }
    input_artifacts = {
        "reconciliation_manifest_sha256": sha256_file(reconciliation_manifest_path),
        "source_inventory_sha256": sha256_file(source_inventory_path),
        "source_reconciliation_sha256": sha256_file(source_reconciliation_path),
        "identity_map_sha256": sha256_file(provider_identity_map_path),
    }
    configuration = {
        "canonical_prefix": CANONICAL_PREFIX,
        "source_remote": transport.source_remote,
        "source_folder_id": source_folder_id,
        "destination_remote": transport.destination_remote,
        "destination_folder_id": destination_folder_id,
        "destination_scope": "drive.file",
        "mode": "aggregate_dry_run",
        "command_contract": [
            "copy",
            "--files-from0",
            "--dry-run",
            "--immutable",
            "--checksum",
            "--check-first",
            "--retries=1",
        ],
    }
    operation_root = data_root / "operations" / "organize_drive" / operation_id
    operation = RecoverableOperation(
        manifest_path=operation_root / "operation.json",
        operation_id=operation_id,
        contract_version=1,
        implementation_version="r03-drive-dry-run-v1",
        input_fingerprint=fingerprint(input_artifacts),
        config_fingerprint=fingerprint(configuration),
        stages=(
            ("prepare", ()),
            ("destination_preflight", ("prepare",)),
            ("dry_run", ("prepare", "destination_preflight")),
        ),
        configuration={**configuration, "inputs": input_artifacts},
    )
    plan_path = operation_root / "copy-plan.jsonl"
    plan_summary_path = operation_root / "copy-plan-summary.json"
    files_from_path = operation_root / "copy-locators.bin"
    destination_preflight_path = operation_root / "destination-preflight.json"
    combined_path = operation_root / "dry-run-combined.txt"
    dry_run_summary_path = operation_root / "dry-run-summary.json"

    _recover_readonly_interruption(operation, "prepare")
    if operation.stage("prepare")["status"] == "completed":
        try:
            _validate_prepared_plan(plan_summary_path, plan_path, files_from_path)
        except (LayoutError, OSError):
            operation.invalidate("prepare", reason="prepared_artifact_missing_or_changed")
    if operation.begin("prepare"):
        try:
            plan = build_copy_plan(current, exclusion_decisions=exclusion_decisions)
            write_copy_plan(
                plan,
                jsonl_path=plan_path,
                summary_path=plan_summary_path,
                files_from_path=files_from_path,
            )
            operation.complete("prepare", artifact=artifact_metadata(plan_summary_path))
        except (LayoutError, OSError) as exc:
            operation.fail(
                "prepare",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    plan = load_copy_plan(plan_path)
    plan_summary = _load_json_object(plan_summary_path, label="resumo do plano")

    preflight_executed = False
    _recover_readonly_interruption(operation, "destination_preflight")
    if operation.begin("destination_preflight"):
        preflight_executed = True
        try:
            _write_empty_destination_preflight(
                transport,
                destination_folder_id=destination_folder_id,
                output_path=destination_preflight_path,
            )
            operation.complete(
                "destination_preflight",
                artifact=artifact_metadata(destination_preflight_path),
            )
        except SourceError as exc:
            operation.fail(
                "destination_preflight",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise

    _recover_readonly_interruption(operation, "dry_run")
    if operation.stage("dry_run")["status"] == "completed":
        try:
            _validate_dry_run_artifacts(dry_run_summary_path, combined_path, plan.entries)
        except (LayoutError, OSError, SourceError):
            operation.invalidate("dry_run", reason="dry_run_artifact_missing_or_changed")
    if operation.stage("dry_run")["status"] != "completed" and not preflight_executed:
        operation.invalidate("destination_preflight", reason="fresh_preflight_before_dry_run")
        if operation.begin("destination_preflight"):
            try:
                _write_empty_destination_preflight(
                    transport,
                    destination_folder_id=destination_folder_id,
                    output_path=destination_preflight_path,
                )
                operation.complete(
                    "destination_preflight",
                    artifact=artifact_metadata(destination_preflight_path),
                )
            except SourceError as exc:
                operation.fail(
                    "destination_preflight",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    blocked=True,
                )
                raise
    if operation.begin("dry_run"):
        try:
            dry_run_result = transport.execute_dry_run(
                plan.entries,
                files_from_path=files_from_path,
                combined_path=combined_path,
            )
            destination_entries_after = transport.destination_entry_count()
            if destination_entries_after != 0:
                raise CopyConflict(
                    "dry-run produziu ou encontrou entradas no destino: "
                    f"{destination_entries_after}"
                )
            atomic_write_json(
                dry_run_summary_path,
                {
                    **dry_run_result,
                    "operation_id": operation_id,
                    "status": "completed",
                    "dry_run": True,
                    "destination_entries_after": 0,
                    "plan_sha256": sha256_file(plan_path),
                    "files_from_sha256": sha256_file(files_from_path),
                    "excluded_files": plan_summary.get("excluded_files"),
                    "excluded_bytes": plan_summary.get("excluded_bytes"),
                },
            )
            operation.complete("dry_run", artifact=artifact_metadata(dry_run_summary_path))
        except (CopyConflict, LayoutError, OSError, SourceError) as exc:
            operation.fail(
                "dry_run",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    dry_run_summary = _load_json_object(dry_run_summary_path, label="resumo do dry-run")
    return {
        "operation_id": operation_id,
        "status": operation.snapshot()["status"],
        "manifest_path": str(operation.manifest_path),
        "copy_plan_path": str(plan_path),
        "copy_plan_summary_path": str(plan_summary_path),
        "files_from_path": str(files_from_path),
        "combined_path": str(combined_path),
        "dry_run_summary_path": str(dry_run_summary_path),
        "files": dry_run_summary.get("files"),
        "bytes": dry_run_summary.get("bytes"),
        "excluded_files": dry_run_summary.get("excluded_files"),
        "destination_entries_after": dry_run_summary.get("destination_entries_after"),
    }


def _validate_reconciliation_artifacts(
    *,
    manifest_path: Path,
    inventory_path: Path,
    reconciliation_path: Path,
    identity_map_path: Path,
    identity_map: ProviderIdentityMap,
    current: Sequence[SourceObject],
    source_folder_id: str,
) -> None:
    manifest = _load_json_object(manifest_path, label="manifesto de reconciliação")
    if manifest.get("status") != "completed":
        raise BaselineMismatch("reconciliação G01 não está concluída")
    stages = manifest.get("stages")
    if not isinstance(stages, list):
        raise BaselineMismatch("etapas da reconciliação G01 são inválidas")
    stage_by_id = {
        item.get("id"): item for item in stages if isinstance(item, dict) and item.get("id")
    }
    for stage_id, path in (
        ("discover", inventory_path),
        ("reconcile", reconciliation_path),
    ):
        stage = stage_by_id.get(stage_id)
        if not isinstance(stage, dict) or stage.get("status") != "completed":
            raise BaselineMismatch(f"etapa G01 incompleta: {stage_id}")
        artifact = stage.get("artifact")
        if not isinstance(artifact, dict):
            raise BaselineMismatch(f"artefato G01 ausente: {stage_id}")
        if Path(str(artifact.get("path", ""))).resolve() != path.resolve():
            raise BaselineMismatch(f"caminho do artefato G01 diverge: {stage_id}")
        if artifact.get("bytes") != path.stat().st_size or artifact.get("sha256") != sha256_file(
            path
        ):
            raise BaselineMismatch(f"artefato G01 diverge do manifest: {stage_id}")
    report = _load_json_object(reconciliation_path, label="relatório de reconciliação")
    summary = report.get("summary")
    if (
        report.get("status") != "reconciled"
        or report.get("source_folder_id") != source_folder_id
        or report.get("identity_map_sha256") != sha256_file(identity_map_path)
        or not isinstance(summary, dict)
    ):
        raise BaselineMismatch("relatório de reconciliação G01 é incompatível")
    expected_provider_ids = sum(len(group.provider_ids) for group in identity_map.groups)
    if (
        summary.get("files") != len(current)
        or summary.get("bytes") != sum(item.size_bytes for item in current)
        or summary.get("missing") != 0
        or summary.get("added") != 0
        or summary.get("changed") != 0
        or summary.get("provider_ids_reconciled") != expected_provider_ids
    ):
        raise BaselineMismatch("contagens do inventário G01 reconciliado divergem")


def _validate_prepared_plan(summary_path: Path, plan_path: Path, files_from_path: Path) -> None:
    summary = _load_json_object(summary_path, label="resumo do plano")
    if (
        summary.get("plan_sha256") != sha256_file(plan_path)
        or summary.get("files_from_sha256") != sha256_file(files_from_path)
        or summary.get("files_from_bytes") != files_from_path.stat().st_size
    ):
        raise LayoutError("artefatos preparados do dry-run divergiram")
    plan = load_copy_plan(plan_path)
    if summary.get("files") != plan.files or summary.get("bytes") != plan.bytes:
        raise LayoutError("contagens do plano preparado divergiram")


def _validate_dry_run_artifacts(
    summary_path: Path,
    combined_path: Path,
    entries: Sequence[CopyPlanEntry],
) -> None:
    summary = _load_json_object(summary_path, label="resumo do dry-run")
    observed = validate_combined_dry_run(entries, combined_path)
    if (
        summary.get("status") != "completed"
        or summary.get("dry_run") is not True
        or summary.get("destination_entries_after") != 0
        or summary.get("combined_sha256") != sha256_file(combined_path)
        or summary.get("files") != observed["files"]
        or summary.get("bytes") != observed["bytes"]
        or summary.get("markers") != observed["markers"]
    ):
        raise LayoutError("artefatos concluídos do dry-run divergiram")


def _write_empty_destination_preflight(
    transport: RcloneCopyTransport,
    *,
    destination_folder_id: str,
    output_path: Path,
) -> None:
    destination_entries = transport.destination_entry_count()
    if destination_entries != 0:
        raise CopyConflict(f"pasta de destino não está vazia: {destination_entries} itens")
    atomic_write_json(
        output_path,
        {
            "destination_folder_id": destination_folder_id,
            "entries": 0,
            "status": "empty",
        },
    )


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LayoutError(f"{label} é ilegível") from exc
    if not isinstance(value, dict):
        raise LayoutError(f"{label} não é objeto JSON")
    return value


def plan_drive_organization(
    *,
    source: InventorySource,
    transport: RcloneCopyTransport,
    baseline_csv: Path,
    data_root: Path,
    operation_id: str,
    source_folder_id: str,
    destination_folder_id: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise LayoutError("operation_id inválido")
    operation_root = data_root / "operations" / "organize_drive" / operation_id
    baseline = load_g01_baseline(baseline_csv)
    configuration = {
        "canonical_prefix": CANONICAL_PREFIX,
        "source": source.descriptor(),
        "source_folder_id": source_folder_id,
        "destination_remote": transport.destination_remote,
        "destination_folder_id": destination_folder_id,
        "destination_scope": "drive.file",
        "transfer_mode": "client_streaming",
    }
    operation = RecoverableOperation(
        manifest_path=operation_root / "operation.json",
        operation_id=operation_id,
        contract_version=1,
        implementation_version="r03-drive-organization-v2",
        input_fingerprint=fingerprint([item.fingerprint_dict() for item in baseline]),
        config_fingerprint=fingerprint(configuration),
        stages=(
            ("discover", ()),
            ("destination_preflight", ()),
            ("map", ("discover", "destination_preflight")),
        ),
        configuration=configuration,
    )
    inventory_path = operation_root / "source-inventory.jsonl"
    destination_preflight_path = operation_root / "destination-preflight.json"
    plan_path = operation_root / "copy-plan.jsonl"
    summary_path = operation_root / "copy-plan-summary.json"

    _recover_readonly_interruption(operation, "discover")
    if operation.begin("discover"):
        try:
            current = source.list_objects(prefix="")
            reconcile_baseline(baseline, current)
            write_source_inventory(current, inventory_path)
            operation.complete("discover", artifact=artifact_metadata(inventory_path))
        except (BaselineMismatch, LayoutError, SourceError) as exc:
            operation.fail(
                "discover",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    current = load_source_inventory(inventory_path)

    _recover_readonly_interruption(operation, "destination_preflight")
    if operation.begin("destination_preflight"):
        try:
            destination_entries = transport.destination_entry_count()
            if destination_entries != 0:
                raise CopyConflict(f"pasta de destino não está vazia: {destination_entries} itens")
            atomic_write_json(
                destination_preflight_path,
                {
                    "destination_folder_id": destination_folder_id,
                    "entries": 0,
                    "status": "empty",
                },
            )
            operation.complete(
                "destination_preflight",
                artifact=artifact_metadata(destination_preflight_path),
            )
        except SourceError as exc:
            operation.fail(
                "destination_preflight",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
                remote_result_ambiguous=False,
            )
            raise

    _recover_readonly_interruption(operation, "map")
    if operation.begin("map"):
        try:
            plan = build_copy_plan(current)
            write_copy_plan(plan, jsonl_path=plan_path, summary_path=summary_path)
            operation.complete("map", artifact=artifact_metadata(summary_path))
        except LayoutError as exc:
            operation.fail(
                "map",
                error_type=type(exc).__name__,
                message=str(exc),
                blocked=True,
            )
            raise
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LayoutError("resumo do plano é ilegível") from exc
    return {
        "operation_id": operation_id,
        "status": operation.snapshot()["status"],
        "manifest_path": str(operation.manifest_path),
        "inventory_path": str(inventory_path),
        "copy_plan_path": str(plan_path),
        "summary_path": str(summary_path),
        "files": summary["files"],
        "bytes": summary["bytes"],
        "excluded_out_of_scope": len(summary["excluded_out_of_scope"]),
    }


def _recover_readonly_interruption(operation: RecoverableOperation, stage_id: str) -> None:
    if operation.stage(stage_id)["status"] == "running":
        operation.recover_interrupted(
            stage_id,
            remote_result_ambiguous=False,
            message="execução anterior interrompida em etapa read-only ou local",
        )


def _safe_prefix(prefix: str) -> str:
    normalized = prefix.strip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise LayoutError("prefixo canônico inseguro")
    return normalized
