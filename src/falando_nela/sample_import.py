from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from falando_nela.config import DEFAULT_SAMPLE_SEED
from falando_nela.operations import RecoverableOperation, artifact_metadata, fingerprint
from falando_nela.raw import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    deterministic_gzip,
    sha256_bytes,
    sha256_file,
    uncompressed_sha256,
)
from falando_nela.sampling import (
    PILOT_STRATUM,
    RecordContractError,
    exact_sample_size,
    selection_key,
    validate_stratum,
)
from falando_nela.sources import SourceError, SourceObject, SourceRecord

PILOT_PREFIX = "data/raw/v1/senado/plenario_discursos/ano=2010"
PILOT_EXPECTED_FILES = 11
PILOT_EXPECTED_BYTES = 89_253_442
PILOT_EXPECTED_POPULATION = 2_996
PILOT_EXPECTED_SELECTION = 30
SAMPLE_LABEL = "AMOSTRA ANUAL DE DESENVOLVIMENTO — NÃO É O CORPUS INTEGRAL"


class SampleImportError(RuntimeError):
    """A fonte ou a publicação diverge do contrato do piloto."""


class SampleSource(Protocol):
    stream_calls: int

    def descriptor(self) -> dict[str, str]: ...

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]: ...

    def iter_records(self, objects: Sequence[SourceObject]) -> Any: ...


def execute_pilot_sample(
    *,
    source: SampleSource,
    copy_catalog_summary_path: Path,
    data_root: Path,
    operation_id: str,
    confirmed_source_folder_id: str,
    sample_seed: str = DEFAULT_SAMPLE_SEED,
    quota_bytes: int,
    minimum_free_bytes: int,
    expected_files: int = PILOT_EXPECTED_FILES,
    expected_bytes: int = PILOT_EXPECTED_BYTES,
    expected_population: int = PILOT_EXPECTED_POPULATION,
    expected_selection: int = PILOT_EXPECTED_SELECTION,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise SampleImportError("operation_id inválido")
    descriptor = source.descriptor()
    if descriptor.get("root_folder_id") != confirmed_source_folder_id:
        raise SampleImportError("confirmação literal do ID canônico diverge da fonte")
    if descriptor.get("scope") != "drive.readonly" and descriptor.get("kind") != "local":
        raise SampleImportError("fonte do piloto deve ser local ou drive.readonly")
    if descriptor.get("prefix") not in {None, PILOT_PREFIX}:
        raise SampleImportError("prefixo da fonte diverge do estrato piloto")
    if sample_seed != DEFAULT_SAMPLE_SEED:
        raise SampleImportError("seed do piloto diverge do contrato aprovado")
    if quota_bytes <= 0 or minimum_free_bytes <= 0:
        raise SampleImportError("quota e reserva devem ser positivas")
    resolved_data_root = data_root.expanduser().resolve(strict=False)
    resolved_data_root.mkdir(parents=True, exist_ok=True)
    catalog_summary = _load_json(copy_catalog_summary_path, "catálogo da organização")
    _validate_copy_catalog(catalog_summary, copy_catalog_summary_path)
    input_artifacts = {
        "copy_catalog_summary_sha256": sha256_file(copy_catalog_summary_path),
        "copy_catalog_sha256": catalog_summary["catalog_sha256"],
    }
    configuration = {
        "source": descriptor,
        "confirmed_source_folder_id": confirmed_source_folder_id,
        "prefix": PILOT_PREFIX,
        "stratum": PILOT_STRATUM.as_dict(),
        "sample_seed": sample_seed,
        "sample_rate": "0.01",
        "quota_bytes": quota_bytes,
        "minimum_free_bytes": minimum_free_bytes,
        "expected_files": expected_files,
        "expected_bytes": expected_bytes,
        "expected_population": expected_population,
        "expected_selection": expected_selection,
    }
    operation_root = resolved_data_root / "operations" / "sample_pilot" / operation_id
    temporary_root = resolved_data_root / "tmp" / operation_id
    operation = RecoverableOperation(
        manifest_path=operation_root / "operation.json",
        operation_id=operation_id,
        contract_version=1,
        implementation_version="r03-sample-pilot-v1",
        input_fingerprint=fingerprint(input_artifacts),
        config_fingerprint=fingerprint(configuration),
        stages=(
            ("preflight", ()),
            ("inventory", ("preflight",)),
            ("rank", ("inventory",)),
            ("freeze_selection", ("rank",)),
            ("materialize", ("freeze_selection",)),
            ("validate", ("materialize",)),
            ("publish", ("validate",)),
        ),
        configuration={**configuration, "inputs": input_artifacts},
    )
    source_inventory_path = operation_root / "pilot-source-inventory.jsonl"
    preflight_path = operation_root / "preflight.json"
    inventory_summary_path = operation_root / "inventory-summary.json"
    candidate_ledger_path = operation_root / "sample-ledger.sqlite"
    rank_summary_path = operation_root / "rank-summary.json"
    selection_manifest_path = operation_root / "selection-manifest.json"
    selected_jsonl_path = temporary_root / "selected.jsonl"
    candidate_gzip_path = temporary_root / "selected.jsonl.gz"
    validation_path = operation_root / "validation.json"

    _recover_interrupted(operation, "preflight")
    if operation.stage("preflight")["status"] == "completed":
        if not _preflight_artifacts_valid(preflight_path):
            operation.invalidate("preflight", reason="preflight_artifact_missing_or_changed")
    if operation.begin("preflight"):
        _emit_progress(progress_callback, operation_id, "preflight", "running")
        try:
            disk = shutil.disk_usage(resolved_data_root)
            required_free = quota_bytes + minimum_free_bytes
            if disk.free < required_free:
                raise SampleImportError(f"espaço livre insuficiente: {disk.free} < {required_free}")
            atomic_write_json(
                preflight_path,
                {
                    "status": "completed",
                    "free_bytes": disk.free,
                    "required_free_bytes": required_free,
                },
            )
            operation.complete("preflight", artifact=artifact_metadata(preflight_path))
            _emit_progress(progress_callback, operation_id, "preflight", "completed")
        except (OSError, SampleImportError) as exc:
            operation.fail(
                "preflight", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise

    _recover_interrupted(operation, "inventory")
    if operation.stage("inventory")["status"] == "completed":
        if not _inventory_artifacts_valid(inventory_summary_path, source_inventory_path):
            operation.invalidate("inventory", reason="inventory_artifact_missing_or_changed")
    if operation.begin("inventory"):
        _emit_progress(progress_callback, operation_id, "inventory", "running")
        try:
            objects = source.list_objects()
            if len(objects) != expected_files:
                raise SampleImportError(
                    f"arquivos do piloto divergiram: {len(objects)} != {expected_files}"
                )
            observed_bytes = sum(item.size_bytes for item in objects)
            if observed_bytes != expected_bytes:
                raise SampleImportError(
                    f"bytes do piloto divergiram: {observed_bytes} != {expected_bytes}"
                )
            _validate_objects_against_catalog(objects, catalog_summary)
            _write_inventory(source_inventory_path, objects)
            atomic_write_json(
                inventory_summary_path,
                {
                    "status": "completed",
                    "files": len(objects),
                    "bytes": observed_bytes,
                    "inventory_path": str(source_inventory_path),
                    "inventory_sha256": sha256_file(source_inventory_path),
                },
            )
            operation.complete("inventory", artifact=artifact_metadata(inventory_summary_path))
            _emit_progress(
                progress_callback,
                operation_id,
                "inventory",
                "completed",
                files=len(objects),
                bytes=observed_bytes,
            )
        except (OSError, SampleImportError, SourceError) as exc:
            operation.fail(
                "inventory", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    objects = _load_inventory(source_inventory_path)

    _recover_interrupted(operation, "rank")
    if operation.stage("rank")["status"] == "completed":
        if not _rank_artifacts_valid(rank_summary_path, candidate_ledger_path):
            operation.invalidate("rank", reason="rank_artifact_missing_or_changed")
    if operation.begin("rank"):
        _emit_progress(progress_callback, operation_id, "rank", "running")
        try:
            candidates = _rank_candidates(source, objects, sample_seed)
            if len(candidates) != expected_population:
                raise SampleImportError(
                    f"população do piloto divergiu: {len(candidates)} != {expected_population}"
                )
            _write_candidate_ledger(candidate_ledger_path, candidates)
            atomic_write_json(
                rank_summary_path,
                {
                    "status": "completed",
                    "population": len(candidates),
                    "ledger_path": str(candidate_ledger_path),
                    "ledger_sha256": sha256_file(candidate_ledger_path),
                },
            )
            operation.complete("rank", artifact=artifact_metadata(rank_summary_path))
            _emit_progress(
                progress_callback,
                operation_id,
                "rank",
                "completed",
                population=len(candidates),
            )
        except (OSError, RecordContractError, SampleImportError, SourceError) as exc:
            operation.fail("rank", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise

    _recover_interrupted(operation, "freeze_selection")
    if operation.begin("freeze_selection"):
        _emit_progress(progress_callback, operation_id, "freeze_selection", "running")
        try:
            candidates = _load_candidate_ledger(candidate_ledger_path)
            selection_size = exact_sample_size(len(candidates))
            if selection_size != expected_selection:
                raise SampleImportError(
                    f"seleção do piloto divergiu: {selection_size} != {expected_selection}"
                )
            selected = sorted(
                candidates, key=lambda item: (str(item["selection_key"]), str(item["identity"]))
            )[:selection_size]
            selection_base = {
                "schema_version": 1,
                "label": SAMPLE_LABEL,
                "seed": sample_seed,
                "stratum": PILOT_STRATUM.as_dict(),
                "population": len(candidates),
                "selected_count": selection_size,
                "input_catalog_sha256": catalog_summary["catalog_sha256"],
                "selected": selected,
            }
            selection_identity = {
                key: value for key, value in selection_base.items() if key != "input_catalog_sha256"
            }
            selection_digest = sha256_bytes(canonical_json_bytes(selection_identity))
            sample_id = f"pilot-senado-plenario-discursos-2010-{selection_digest[:16]}"
            atomic_write_json(
                selection_manifest_path,
                {**selection_base, "sample_id": sample_id, "selection_sha256": selection_digest},
            )
            operation.complete(
                "freeze_selection", artifact=artifact_metadata(selection_manifest_path)
            )
            _emit_progress(
                progress_callback,
                operation_id,
                "freeze_selection",
                "completed",
                selected_count=selection_size,
            )
        except (OSError, SampleImportError) as exc:
            operation.fail(
                "freeze_selection", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    selection_manifest = _load_json(selection_manifest_path, "manifesto de seleção")

    _recover_interrupted(operation, "materialize")
    if operation.begin("materialize"):
        _emit_progress(progress_callback, operation_id, "materialize", "running")
        try:
            selected_records = _materialize_selected(source, objects, selection_manifest)
            payload = b"".join(
                selected_records[identity] + b"\n" for identity in _selected_ids(selection_manifest)
            )
            atomic_write_bytes(selected_jsonl_path, payload)
            operation.complete("materialize", artifact=artifact_metadata(selected_jsonl_path))
            _emit_progress(
                progress_callback,
                operation_id,
                "materialize",
                "completed",
                selected_count=len(selected_records),
            )
        except (OSError, RecordContractError, SampleImportError, SourceError) as exc:
            operation.fail(
                "materialize", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise

    _recover_interrupted(operation, "validate")
    if operation.stage("validate")["status"] == "completed":
        if not _validation_artifacts_valid(validation_path, candidate_gzip_path):
            operation.invalidate("validate", reason="validation_artifact_missing_or_changed")
    if operation.begin("validate"):
        _emit_progress(progress_callback, operation_id, "validate", "running")
        try:
            gzip_metadata = deterministic_gzip(selected_jsonl_path, candidate_gzip_path)
            _validate_materialized_records(candidate_gzip_path, selection_manifest)
            atomic_write_json(
                validation_path,
                {
                    "status": "completed",
                    "selected_count": selection_manifest["selected_count"],
                    **gzip_metadata,
                },
            )
            operation.complete("validate", artifact=artifact_metadata(validation_path))
            _emit_progress(progress_callback, operation_id, "validate", "completed")
        except (OSError, SampleImportError) as exc:
            operation.fail(
                "validate", error_type=type(exc).__name__, message=str(exc), blocked=True
            )
            raise
    validation = _load_json(validation_path, "validação da amostra")
    sample_id = str(selection_manifest["sample_id"])
    publication_root = (
        resolved_data_root
        / "raw"
        / "sample_annual_1pct"
        / sample_id
        / "senado"
        / "plenario_discursos"
        / "ano=2010"
    )
    published_gzip_path = publication_root / "part-00000.jsonl.gz"
    sample_manifest_path = publication_root.parent.parent.parent / "sample-manifest.json"

    _recover_interrupted(operation, "publish")
    if operation.stage("publish")["status"] == "completed":
        if not _published_artifacts_valid(sample_manifest_path, published_gzip_path):
            operation.invalidate("publish", reason="published_artifact_missing_or_changed")
    if operation.begin("publish"):
        _emit_progress(progress_callback, operation_id, "publish", "running")
        try:
            _publish_immutable(candidate_gzip_path, published_gzip_path)
            root_bytes = _directory_size(resolved_data_root)
            if root_bytes > quota_bytes:
                raise SampleImportError(f"quota local excedida: {root_bytes} > {quota_bytes}")
            atomic_write_json(
                sample_manifest_path,
                {
                    **selection_manifest,
                    "status": "completed",
                    "output": {
                        "path": str(published_gzip_path),
                        "bytes": published_gzip_path.stat().st_size,
                        "sha256_uncompressed": validation["sha256_uncompressed"],
                        "sha256_stored_object": sha256_file(published_gzip_path),
                    },
                    "data_root_bytes": root_bytes,
                },
            )
            operation.complete("publish", artifact=artifact_metadata(sample_manifest_path))
            _emit_progress(
                progress_callback,
                operation_id,
                "publish",
                "completed",
                output_bytes=published_gzip_path.stat().st_size,
            )
        except (OSError, SampleImportError) as exc:
            operation.fail("publish", error_type=type(exc).__name__, message=str(exc), blocked=True)
            raise
    return {
        "operation_id": operation_id,
        "status": operation.snapshot()["status"],
        "manifest_path": str(operation.manifest_path),
        "sample_id": sample_id,
        "population": selection_manifest["population"],
        "selected_count": selection_manifest["selected_count"],
        "sample_manifest_path": str(sample_manifest_path),
        "output_path": str(published_gzip_path),
        "source_stream_calls": source.stream_calls,
    }


def _rank_candidates(
    source: SampleSource, objects: Sequence[SourceObject], sample_seed: str
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    identities: set[str] = set()
    for record in source.iter_records(objects):
        if not isinstance(record, SourceRecord):
            raise SampleImportError("adaptador retornou registro de tipo inválido")
        if record.value is None:
            raise SampleImportError(
                f"registro raw inválido: {record.locator}:{record.line_number}:{record.error}"
            )
        identity = validate_stratum(record.value, PILOT_STRATUM)
        if identity in identities:
            raise SampleImportError(f"identidade duplicada: {identity}")
        identities.add(identity)
        candidates.append(
            {
                "identity": identity,
                "selection_key": selection_key(identity, sample_seed),
                "locator": record.locator,
                "line_number": record.line_number,
                "raw_sha256": record.sha256,
                "raw_bytes": len(record.raw_record),
            }
        )
    return sorted(candidates, key=lambda item: (item["selection_key"], item["identity"]))


def _materialize_selected(
    source: SampleSource,
    objects: Sequence[SourceObject],
    selection_manifest: dict[str, Any],
) -> dict[str, bytes]:
    expected = {str(item["identity"]): item for item in selection_manifest["selected"]}
    materialized: dict[str, bytes] = {}
    for record in source.iter_records(objects):
        if record.value is None:
            raise SampleImportError(
                f"registro raw inválido na segunda passagem: {record.locator}:{record.line_number}"
            )
        identity = validate_stratum(record.value, PILOT_STRATUM)
        selected = expected.get(identity)
        if selected is None:
            continue
        if identity in materialized:
            raise SampleImportError(f"identidade selecionada duplicada: {identity}")
        if (
            selected["locator"] != record.locator
            or selected["line_number"] != record.line_number
            or selected["raw_sha256"] != record.sha256
        ):
            raise SampleImportError(f"registro selecionado mudou entre passagens: {identity}")
        materialized[identity] = record.raw_record
    missing = set(expected) - set(materialized)
    if missing:
        raise SampleImportError(f"registros selecionados ausentes: {len(missing)}")
    return materialized


def _validate_materialized_records(path: Path, selection_manifest: dict[str, Any]) -> None:
    import gzip

    expected = selection_manifest["selected"]
    with gzip.open(path, "rb") as handle:
        lines = [line.rstrip(b"\r\n") for line in handle if line.strip()]
    if len(lines) != len(expected):
        raise SampleImportError("contagem do gzip diverge da seleção")
    for line, selected in zip(lines, expected, strict=True):
        if sha256_bytes(line) != selected["raw_sha256"]:
            raise SampleImportError("hash de registro diverge no gzip")


def _selected_ids(selection_manifest: dict[str, Any]) -> list[str]:
    return [str(item["identity"]) for item in selection_manifest["selected"]]


def _validate_copy_catalog(summary: dict[str, Any], summary_path: Path) -> None:
    if summary.get("status") != "completed":
        raise SampleImportError("catálogo da organização não está concluído")
    catalog_path = Path(str(summary.get("catalog_path", "")))
    if not catalog_path.is_file() or sha256_file(catalog_path) != summary.get("catalog_sha256"):
        raise SampleImportError("catálogo da organização está ausente ou adulterado")
    if not summary_path.is_file():
        raise SampleImportError("resumo do catálogo está ausente")


def _validate_objects_against_catalog(
    objects: Sequence[SourceObject], summary: dict[str, Any]
) -> None:
    catalog_path = Path(str(summary["catalog_path"]))
    catalog = {str(item["destination_locator"]): item for item in _load_jsonl(catalog_path)}
    for source_object in objects:
        item = catalog.get(source_object.locator)
        if item is None or item.get("size_bytes") != source_object.size_bytes:
            raise SampleImportError(
                f"objeto do piloto diverge do catálogo: {source_object.locator}"
            )
        expected_hashes = item.get("provider_hashes")
        if not isinstance(expected_hashes, dict):
            raise SampleImportError("catálogo não contém hashes do provedor")
        common = set(expected_hashes) & set(source_object.provider_hashes)
        if not common or any(
            expected_hashes[name] != source_object.provider_hashes[name] for name in common
        ):
            raise SampleImportError(f"hash do piloto diverge do catálogo: {source_object.locator}")


def _write_inventory(path: Path, objects: Sequence[SourceObject]) -> None:
    _write_jsonl(path, [item.fingerprint_dict() for item in objects])


def _load_inventory(path: Path) -> list[SourceObject]:
    try:
        return [SourceObject(**item) for item in _load_jsonl(path)]
    except TypeError as exc:
        raise SampleImportError("inventário do piloto é inválido") from exc


def _write_candidate_ledger(path: Path, candidates: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.execute(
                """
                CREATE TABLE candidates (
                    identity TEXT PRIMARY KEY,
                    selection_key TEXT NOT NULL UNIQUE,
                    locator TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    raw_sha256 TEXT NOT NULL,
                    raw_bytes INTEGER NOT NULL
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO candidates (
                    identity, selection_key, locator, line_number, raw_sha256, raw_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["identity"],
                        item["selection_key"],
                        item["locator"],
                        item["line_number"],
                        item["raw_sha256"],
                        item["raw_bytes"],
                    )
                    for item in candidates
                ],
            )
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_candidate_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SampleImportError("ledger da amostra está ausente")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT identity, selection_key, locator, line_number, raw_sha256, raw_bytes
            FROM candidates
            ORDER BY selection_key, identity
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise SampleImportError("ledger da amostra é inválido") from exc
    finally:
        connection.close()
    return [
        {
            "identity": identity,
            "selection_key": key,
            "locator": locator,
            "line_number": line_number,
            "raw_sha256": raw_sha256,
            "raw_bytes": raw_bytes,
        }
        for identity, key, locator, line_number, raw_sha256, raw_bytes in rows
    ]


def _write_jsonl(path: Path, values: Sequence[dict[str, Any]]) -> None:
    atomic_write_bytes(path, b"".join(canonical_json_bytes(value) + b"\n" for value in values))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        values = [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleImportError(f"JSONL técnico ilegível: {path}") from exc
    if not all(isinstance(value, dict) for value in values):
        raise SampleImportError(f"JSONL técnico contém valor inválido: {path}")
    return values


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleImportError(f"{label} é ilegível") from exc
    if not isinstance(value, dict):
        raise SampleImportError(f"{label} é inválido")
    return value


def _preflight_artifacts_valid(summary_path: Path) -> bool:
    try:
        summary = _load_json(summary_path, "preflight")
        return (
            summary.get("status") == "completed"
            and isinstance(summary.get("free_bytes"), int)
            and isinstance(summary.get("required_free_bytes"), int)
        )
    except (OSError, SampleImportError):
        return False


def _inventory_artifacts_valid(summary_path: Path, inventory_path: Path) -> bool:
    try:
        summary = _load_json(summary_path, "inventário")
        objects = _load_inventory(inventory_path)
        return (
            summary.get("status") == "completed"
            and summary.get("files") == len(objects)
            and summary.get("bytes") == sum(item.size_bytes for item in objects)
            and summary.get("inventory_sha256") == sha256_file(inventory_path)
        )
    except (OSError, SampleImportError):
        return False


def _rank_artifacts_valid(summary_path: Path, ledger_path: Path) -> bool:
    try:
        summary = _load_json(summary_path, "ranking")
        return (
            ledger_path.is_file()
            and summary.get("ledger_sha256") == sha256_file(ledger_path)
            and len(_load_candidate_ledger(ledger_path)) == summary.get("population")
        )
    except (OSError, SampleImportError):
        return False


def _validation_artifacts_valid(report_path: Path, gzip_path: Path) -> bool:
    try:
        report = _load_json(report_path, "validação")
        return (
            gzip_path.is_file()
            and report.get("sha256_stored_object") == sha256_file(gzip_path)
            and report.get("sha256_uncompressed") == uncompressed_sha256(gzip_path)
        )
    except (OSError, SampleImportError):
        return False


def _published_artifacts_valid(manifest_path: Path, output_path: Path) -> bool:
    try:
        manifest = _load_json(manifest_path, "manifesto publicado")
        output = manifest.get("output")
        return (
            isinstance(output, dict)
            and output_path.is_file()
            and output.get("bytes") == output_path.stat().st_size
            and output.get("sha256_stored_object") == sha256_file(output_path)
        )
    except (OSError, SampleImportError):
        return False


def _publish_immutable(source: Path, destination: Path) -> None:
    if destination.exists():
        if destination.is_file() and sha256_file(destination) == sha256_file(source):
            return
        raise SampleImportError(f"destino publicado diverge: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{os.getpid()}.tmp"
    try:
        shutil.copyfile(source, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _directory_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _emit_progress(
    callback: Callable[[dict[str, Any]], None] | None,
    operation_id: str,
    stage: str,
    status: str,
    **details: Any,
) -> None:
    if callback is not None:
        callback(
            {
                "event": "progress",
                "operation_id": operation_id,
                "stage": stage,
                "status": status,
                **details,
            }
        )


def _recover_interrupted(operation: RecoverableOperation, stage_id: str) -> None:
    if operation.stage(stage_id)["status"] == "running":
        operation.recover_interrupted(
            stage_id,
            remote_result_ambiguous=False,
            message="execução anterior interrompida; artefatos locais serão reconciliados",
        )
