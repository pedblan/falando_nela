from __future__ import annotations

import gzip
import io
import json
import re
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

import httpx

from falando_nela.gcs_full_migration import GcsJsonApi
from falando_nela.operations import RecoverableOperation, artifact_metadata, fingerprint
from falando_nela.raw import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

CONTRACT_VERSION = 1
PARQUET_SCHEMA_VERSION = "g03-senado-plenario-discursos-v1"
COMPRESSION = "zstd"
STAGES = (
    ("materialize_input", ()),
    ("write_parquet", ("materialize_input",)),
    ("validate", ("write_parquet",)),
    ("publish", ("validate",)),
)
THROUGH_ORDER = tuple(stage_id for stage_id, _ in STAGES)
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ParquetPipelineError(RuntimeError):
    """Entrada, estado ou saída inválida do piloto Parquet G03."""


class ObjectStore(Protocol):
    def descriptor(self) -> dict[str, str]: ...

    def read_bytes(self, locator: str) -> bytes | None: ...

    def publish_bytes_create_only(
        self, locator: str, content: bytes, *, content_type: str
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SelectionEntry:
    identity: str
    line_number: int
    source_locator: str
    raw_bytes: int
    raw_sha256: str


@dataclass(frozen=True)
class SelectionManifest:
    sample_id: str
    stored_object_sha256: str
    uncompressed_sha256: str
    entries: tuple[SelectionEntry, ...]
    file_sha256: str


@dataclass(frozen=True)
class ParquetPilotConfig:
    project_id: str
    region: str
    bucket: str
    processed_prefix: str
    manifests_prefix: str

    def validate(self) -> ParquetPilotConfig:
        if not self.project_id or not self.region or not self.bucket:
            raise ParquetPipelineError("projeto, região e bucket são obrigatórios")
        _validate_locator(self.processed_prefix)
        _validate_locator(self.manifests_prefix)
        return self


class LocalObjectStore:
    """Store create-only para fixtures e validação sem credenciais."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def descriptor(self) -> dict[str, str]:
        return {"kind": "local", "root": str(self.root)}

    def read_bytes(self, locator: str) -> bytes | None:
        path = self._path(locator)
        return path.read_bytes() if path.is_file() else None

    def publish_bytes_create_only(
        self, locator: str, content: bytes, *, content_type: str
    ) -> dict[str, Any]:
        del content_type
        path = self._path(locator)
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise ParquetPipelineError(f"objeto local existente diverge: {locator}")
            status = "reused_verified"
        else:
            atomic_write_bytes(path, content)
            status = "created"
        return {
            "status": status,
            "locator": locator,
            "bytes": len(content),
            "sha256": sha256_bytes(content),
        }

    def _path(self, locator: str) -> Path:
        _validate_locator(locator)
        path = (self.root / PurePosixPath(locator)).resolve()
        if not path.is_relative_to(self.root):
            raise ParquetPipelineError("locator escapou da raiz local")
        return path


class GcsObjectStore:
    def __init__(self, api: GcsJsonApi) -> None:
        self.api = api

    def descriptor(self) -> dict[str, str]:
        return {
            **self.api.descriptor(),
            "authentication": "attached_service_account_metadata_token",
        }

    def read_bytes(self, locator: str) -> bytes | None:
        return self.api.read_bytes(locator)

    def publish_bytes_create_only(
        self, locator: str, content: bytes, *, content_type: str
    ) -> dict[str, Any]:
        return self.api.publish_bytes_create_only(locator, content, content_type=content_type)


class MetadataServerTokenProvider:
    """Token curto da service account anexada ao Cloud Run Job."""

    def __init__(self, *, http_transport: httpx.BaseTransport | None = None) -> None:
        self.http_transport = http_transport
        self._token: str | None = None
        self._expires_at = 0.0

    def __call__(self) -> str:
        now = time.monotonic()
        if self._token is not None and now < self._expires_at - 60:
            return self._token
        arguments: dict[str, Any] = {
            "timeout": 10.0,
            "headers": {"Metadata-Flavor": "Google"},
        }
        if self.http_transport is not None:
            arguments["transport"] = self.http_transport
        with httpx.Client(**arguments) as client:
            response = client.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/"
                "service-accounts/default/token"
            )
        if response.status_code != 200:
            raise ParquetPipelineError(
                f"metadata server recusou token (HTTP {response.status_code})"
            )
        try:
            payload = response.json()
            token = payload["access_token"]
            expires_in = int(payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ParquetPipelineError("metadata server retornou token inválido") from exc
        if not isinstance(token, str) or not token or expires_in <= 0:
            raise ParquetPipelineError("metadata server retornou token inválido")
        self._token = token
        self._expires_at = now + expires_in
        return token


def load_selection_manifest(path: Path) -> SelectionManifest:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ParquetPipelineError("selection manifest ausente ou inválido") from exc
    try:
        if payload["schema_version"] != 1:
            raise ValueError("schema_version")
        sample_id = _required_string(payload["sample_id"], "sample_id")
        input_data = payload["input"]
        stored_sha = _required_sha256(input_data["stored_object_sha256"], "stored_object")
        uncompressed_sha = _required_sha256(input_data["uncompressed_sha256"], "uncompressed")
        selected = payload["selected"]
        if not isinstance(selected, list) or input_data["records"] != len(selected):
            raise ValueError("records")
        entries = tuple(_parse_selection_entry(item) for item in selected)
    except (KeyError, TypeError, ValueError) as exc:
        raise ParquetPipelineError("selection manifest diverge do contrato G03") from exc
    if not entries:
        raise ParquetPipelineError("selection manifest vazio")
    if len({entry.identity for entry in entries}) != len(entries):
        raise ParquetPipelineError("identidade duplicada no selection manifest")
    if len({entry.raw_sha256 for entry in entries}) != len(entries):
        raise ParquetPipelineError("hash raw duplicado no selection manifest")
    return SelectionManifest(
        sample_id=sample_id,
        stored_object_sha256=stored_sha,
        uncompressed_sha256=uncompressed_sha,
        entries=entries,
        file_sha256=sha256_bytes(raw),
    )


def execute_parquet_pilot(
    *,
    operation_id: str,
    implementation_revision: str,
    selection_manifest_path: Path,
    operation_root: Path,
    publish_store: ObjectStore,
    config: ParquetPilotConfig,
    source_store: ObjectStore | None = None,
    local_input_path: Path | None = None,
    through: Literal["materialize_input", "write_parquet", "validate", "publish"] = ("publish"),
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", operation_id):
        raise ParquetPipelineError("operation_id inválido")
    if not implementation_revision.strip():
        raise ParquetPipelineError("implementation_revision é obrigatória")
    config.validate()
    selection = load_selection_manifest(selection_manifest_path)
    if (source_store is None) == (local_input_path is None):
        raise ParquetPipelineError("escolha exatamente uma origem: local ou GCS")
    if local_input_path is not None:
        resolved_input = local_input_path.expanduser().resolve(strict=True)
        source_kind = "local"
        source_fingerprint = sha256_file(resolved_input)
    else:
        resolved_input = None
        source_kind = "gcs"
        source_fingerprint = selection.uncompressed_sha256

    operation_root = operation_root.expanduser().resolve()
    operation_root.mkdir(parents=True, exist_ok=True)
    manifest_path = operation_root / "operation.json"
    selected_path = operation_root / "selected.jsonl"
    parquet_path = operation_root / "part-00000.parquet"
    validation_path = operation_root / "validation.json"
    result_manifest_path = operation_root / "result-manifest.json"
    receipt_path = operation_root / "publish-receipt.json"
    parquet_locator, manifest_locator = _output_locators(config, operation_id)
    public_configuration = {
        "implementation_revision": implementation_revision,
        "source_kind": source_kind,
        "project_id": config.project_id,
        "region": config.region,
        "bucket": config.bucket,
        "processed_prefix": config.processed_prefix,
        "manifests_prefix": config.manifests_prefix,
        "selection_manifest_sha256": selection.file_sha256,
        "schema_version": PARQUET_SCHEMA_VERSION,
        "compression": COMPRESSION,
    }
    operation = RecoverableOperation(
        manifest_path=manifest_path,
        operation_id=operation_id,
        contract_version=CONTRACT_VERSION,
        implementation_version=implementation_revision,
        input_fingerprint=fingerprint(
            {
                "selection_manifest_sha256": selection.file_sha256,
                "selected_uncompressed_sha256": selection.uncompressed_sha256,
                "source_fingerprint": source_fingerprint,
            }
        ),
        config_fingerprint=fingerprint(public_configuration),
        stages=STAGES,
        configuration=public_configuration,
    )

    actions: dict[str, Callable[[], Path]] = {
        "materialize_input": lambda: _materialize_input(
            selection=selection,
            destination=selected_path,
            source_store=source_store,
            local_input_path=resolved_input,
        ),
        "write_parquet": lambda: _write_parquet(
            selected_path=selected_path,
            destination=parquet_path,
            selection=selection,
        ),
        "validate": lambda: _validate_parquet(
            selected_path=selected_path,
            parquet_path=parquet_path,
            destination=validation_path,
            selection=selection,
        ),
        "publish": lambda: _publish(
            operation_id=operation_id,
            implementation_revision=implementation_revision,
            selection=selection,
            source_kind=source_kind,
            parquet_path=parquet_path,
            validation_path=validation_path,
            result_manifest_path=result_manifest_path,
            receipt_path=receipt_path,
            store=publish_store,
            parquet_locator=parquet_locator,
            manifest_locator=manifest_locator,
            failure_injector=failure_injector,
        ),
    }
    last_index = THROUGH_ORDER.index(through)
    reused: list[str] = []
    executed: list[str] = []
    for stage_id in THROUGH_ORDER[: last_index + 1]:
        if stage_id == "publish" and operation.artifact_is_valid(stage_id):
            if _published_objects_match(
                store=publish_store,
                parquet_locator=parquet_locator,
                parquet_path=parquet_path,
                manifest_locator=manifest_locator,
                manifest_path=result_manifest_path,
            ):
                reused.append(stage_id)
                continue
            operation.invalidate(stage_id, reason="published_object_missing")
        if operation.artifact_is_valid(stage_id):
            reused.append(stage_id)
            continue
        stage = operation.stage(stage_id)
        if stage["status"] == "running":
            if stage_id == "publish":
                try:
                    artifact_path = actions[stage_id]()
                    operation.complete(stage_id, artifact=artifact_metadata(artifact_path))
                    executed.append(stage_id)
                    continue
                except Exception as exc:
                    operation.fail(
                        stage_id,
                        error_type=type(exc).__name__,
                        message=str(exc),
                        remote_result_ambiguous=True,
                    )
                    raise
            operation.recover_interrupted(
                stage_id,
                remote_result_ambiguous=False,
                message="etapa local interrompida; artefato será reconstruído",
            )
        operation.begin(stage_id)
        try:
            if failure_injector is not None:
                failure_injector(f"before:{stage_id}")
            artifact_path = actions[stage_id]()
            if failure_injector is not None:
                failure_injector(f"after:{stage_id}")
            operation.complete(stage_id, artifact=artifact_metadata(artifact_path))
            executed.append(stage_id)
        except Exception as exc:
            operation.fail(
                stage_id,
                error_type=type(exc).__name__,
                message=str(exc),
                remote_result_ambiguous=(stage_id == "publish"),
            )
            raise

    validation = (
        json.loads(validation_path.read_text(encoding="utf-8"))
        if validation_path.is_file()
        else None
    )
    return {
        "status": "completed" if through == "publish" else f"completed_through_{through}",
        "operation_id": operation_id,
        "through": through,
        "source_kind": source_kind,
        "records": len(selection.entries),
        "manifest_path": str(manifest_path),
        "parquet_path": str(parquet_path) if parquet_path.is_file() else None,
        "parquet_locator": parquet_locator if through == "publish" else None,
        "result_manifest_locator": manifest_locator if through == "publish" else None,
        "parquet_sha256": validation.get("parquet_sha256") if validation else None,
        "logical_sha256": validation.get("logical_sha256") if validation else None,
        "executed_stages": executed,
        "reused_stages": reused,
    }


def _materialize_input(
    *,
    selection: SelectionManifest,
    destination: Path,
    source_store: ObjectStore | None,
    local_input_path: Path | None,
) -> Path:
    if local_input_path is not None:
        selected_lines = _select_from_local_input(local_input_path, selection)
    else:
        assert source_store is not None
        selected_lines = _select_from_store(source_store, selection)
    content = b"".join(line + b"\n" for line in selected_lines)
    if sha256_bytes(content) != selection.uncompressed_sha256:
        raise ParquetPipelineError("JSONL selecionado diverge do hash congelado")
    atomic_write_bytes(destination, content)
    return destination


def _select_from_local_input(path: Path, selection: SelectionManifest) -> list[bytes]:
    content = path.read_bytes()
    if path.name.endswith(".jsonl.gz"):
        if sha256_bytes(content) != selection.stored_object_sha256:
            raise ParquetPipelineError("gzip local diverge do hash congelado")
        try:
            content = gzip.decompress(content)
        except gzip.BadGzipFile as exc:
            raise ParquetPipelineError("gzip local inválido") from exc
    elif not path.name.endswith(".jsonl"):
        raise ParquetPipelineError("entrada local deve ser .jsonl ou .jsonl.gz")
    available: dict[str, bytes] = {}
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        _decode_record(line, label=f"{path.name}:{line_number}")
        digest = sha256_bytes(line)
        if digest in available:
            raise ParquetPipelineError("hash raw duplicado na entrada local")
        available[digest] = line
    return _ordered_and_validated_lines(available, selection)


def _select_from_store(store: ObjectStore, selection: SelectionManifest) -> list[bytes]:
    by_locator: dict[str, list[SelectionEntry]] = defaultdict(list)
    for entry in selection.entries:
        by_locator[entry.source_locator].append(entry)
    available: dict[str, bytes] = {}
    for locator in sorted(by_locator):
        content = store.read_bytes(locator)
        if content is None:
            raise ParquetPipelineError(f"objeto raw ausente: {locator}")
        lines = content.splitlines()
        for entry in by_locator[locator]:
            if entry.line_number > len(lines):
                raise ParquetPipelineError(f"linha raw ausente: {locator}:{entry.line_number}")
            line = lines[entry.line_number - 1]
            if not line.strip():
                raise ParquetPipelineError(f"linha raw vazia: {locator}:{entry.line_number}")
            available[entry.raw_sha256] = line
    return _ordered_and_validated_lines(available, selection)


def _ordered_and_validated_lines(
    available: Mapping[str, bytes], selection: SelectionManifest
) -> list[bytes]:
    ordered: list[bytes] = []
    for entry in selection.entries:
        line = available.get(entry.raw_sha256)
        if line is None:
            raise ParquetPipelineError(f"registro selecionado ausente: {entry.raw_sha256}")
        if len(line) != entry.raw_bytes or sha256_bytes(line) != entry.raw_sha256:
            raise ParquetPipelineError(f"bytes raw divergiram: {entry.raw_sha256}")
        record = _decode_record(line, label=entry.raw_sha256)
        if _record_identity(record) != entry.identity:
            raise ParquetPipelineError(f"identidade raw divergiu: {entry.raw_sha256}")
        ordered.append(line)
    return ordered


def _write_parquet(
    *,
    selected_path: Path,
    destination: Path,
    selection: SelectionManifest,
) -> Path:
    pa, pq = _pyarrow()
    rows = [_normalized_row(line) for line in selected_path.read_bytes().splitlines() if line]
    rows.sort(key=lambda row: row["source_id"])
    schema = _arrow_schema(pa).with_metadata(
        {
            b"falando_nela_schema": PARQUET_SCHEMA_VERSION.encode(),
            b"selection_manifest_sha256": selection.file_sha256.encode(),
            b"compression": COMPRESSION.encode(),
        }
    )
    table = pa.Table.from_pylist(rows, schema=schema)
    sink = io.BytesIO()
    pq.write_table(
        table,
        sink,
        version="2.6",
        data_page_version="2.0",
        compression=COMPRESSION,
        compression_level=9,
        use_dictionary=False,
        write_statistics=True,
        row_group_size=len(rows),
        store_schema=True,
        use_compliant_nested_type=True,
    )
    atomic_write_bytes(destination, sink.getvalue())
    return destination


def _validate_parquet(
    *,
    selected_path: Path,
    parquet_path: Path,
    destination: Path,
    selection: SelectionManifest,
) -> Path:
    pa, pq = _pyarrow()
    parquet = pq.ParquetFile(parquet_path)
    expected_schema = _arrow_schema(pa)
    if parquet.schema_arrow.remove_metadata() != expected_schema:
        raise ParquetPipelineError("schema Parquet diverge do contrato G03")
    if parquet.metadata.num_rows != len(selection.entries) or parquet.metadata.num_row_groups != 1:
        raise ParquetPipelineError("contagem ou row groups do Parquet divergiram")
    compressions = {
        parquet.metadata.row_group(group).column(column).compression
        for group in range(parquet.metadata.num_row_groups)
        for column in range(parquet.metadata.num_columns)
    }
    if compressions != {"ZSTD"}:
        raise ParquetPipelineError("compressão Parquet diverge de Zstandard")
    table_rows = parquet.read().to_pylist()
    expected_rows = [
        _normalized_row(line) for line in selected_path.read_bytes().splitlines() if line
    ]
    expected_rows.sort(key=lambda row: row["source_id"])
    if table_rows != expected_rows:
        raise ParquetPipelineError("conteúdo lógico do Parquet divergiu")
    logical_sha256 = sha256_bytes(canonical_json_bytes(table_rows))
    payload = {
        "schema_version": 1,
        "parquet_schema_version": PARQUET_SCHEMA_VERSION,
        "selection_manifest_sha256": selection.file_sha256,
        "selected_jsonl_sha256": sha256_file(selected_path),
        "records": len(table_rows),
        "row_groups": parquet.metadata.num_row_groups,
        "compression": COMPRESSION,
        "parquet_bytes": parquet_path.stat().st_size,
        "parquet_sha256": sha256_file(parquet_path),
        "logical_sha256": logical_sha256,
    }
    atomic_write_json(destination, payload)
    return destination


def _publish(
    *,
    operation_id: str,
    implementation_revision: str,
    selection: SelectionManifest,
    source_kind: str,
    parquet_path: Path,
    validation_path: Path,
    result_manifest_path: Path,
    receipt_path: Path,
    store: ObjectStore,
    parquet_locator: str,
    manifest_locator: str,
    failure_injector: Callable[[str], None] | None,
) -> Path:
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    result_manifest = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "operation_id": operation_id,
        "implementation_revision": implementation_revision,
        "source_kind": source_kind,
        "sample_id": selection.sample_id,
        "selection_manifest_sha256": selection.file_sha256,
        "selected_jsonl_sha256": validation["selected_jsonl_sha256"],
        "records": validation["records"],
        "parquet": {
            "locator": parquet_locator,
            "bytes": validation["parquet_bytes"],
            "sha256": validation["parquet_sha256"],
            "logical_sha256": validation["logical_sha256"],
            "schema_version": PARQUET_SCHEMA_VERSION,
            "compression": COMPRESSION,
        },
    }
    atomic_write_json(result_manifest_path, result_manifest)
    parquet_result = store.publish_bytes_create_only(
        parquet_locator,
        parquet_path.read_bytes(),
        content_type="application/vnd.apache.parquet",
    )
    if failure_injector is not None:
        failure_injector("publish:after_parquet")
    manifest_result = store.publish_bytes_create_only(
        manifest_locator,
        result_manifest_path.read_bytes(),
        content_type="application/json",
    )
    if failure_injector is not None:
        failure_injector("publish:after_manifest")
    atomic_write_json(
        receipt_path,
        {
            "schema_version": 1,
            "store": store.descriptor(),
            "parquet": parquet_result,
            "manifest": manifest_result,
        },
    )
    return receipt_path


def _published_objects_match(
    *,
    store: ObjectStore,
    parquet_locator: str,
    parquet_path: Path,
    manifest_locator: str,
    manifest_path: Path,
) -> bool:
    if not parquet_path.is_file() or not manifest_path.is_file():
        return False
    parquet_remote = store.read_bytes(parquet_locator)
    manifest_remote = store.read_bytes(manifest_locator)
    if parquet_remote is not None and parquet_remote != parquet_path.read_bytes():
        raise ParquetPipelineError("Parquet publicado diverge do artefato local")
    if manifest_remote is not None and manifest_remote != manifest_path.read_bytes():
        raise ParquetPipelineError("manifest publicado diverge do artefato local")
    return parquet_remote is not None and manifest_remote is not None


def _output_locators(config: ParquetPilotConfig, operation_id: str) -> tuple[str, str]:
    parquet = (
        f"{config.processed_prefix}/g03/senado/plenario_discursos/ano=2010/"
        f"operation_id={operation_id}/part-00000.parquet"
    )
    manifest = f"{config.manifests_prefix}/processing/g03/{operation_id}/manifest.json"
    _validate_locator(parquet)
    _validate_locator(manifest)
    return parquet, manifest


def _normalized_row(line: bytes) -> dict[str, Any]:
    record = _decode_record(line, label="selected.jsonl")
    payload = _mapping(record.get("payload"))
    metadata = _mapping(payload.get("metadata"))
    pronouncement = _mapping(metadata.get("pronunciamento"))
    session = _mapping(metadata.get("sessao"))
    speech_type = _mapping(pronouncement.get("TipoUsoPalavra"))
    period = _mapping(record.get("periodo"))
    text = _optional_string(payload.get("texto")) or _optional_string(payload.get("TextoIntegral"))
    return {
        "source": _required_string(record.get("source"), "source"),
        "dataset": _required_string(record.get("dataset"), "dataset"),
        "record_type": _required_string(record.get("record_type"), "record_type"),
        "source_id": _required_string(record.get("source_id"), "source_id"),
        "raw_sha256": sha256_bytes(line),
        "checksum": _optional_string(record.get("checksum")),
        "collected_at": _optional_string(record.get("collected_at")),
        "coverage_start_date": _optional_string(period.get("data_inicio")),
        "coverage_end_date": _optional_string(period.get("data_fim")),
        "partition": _optional_string(record.get("partition")),
        "run_id": _optional_string(record.get("run_id")),
        "pronouncement_id": _optional_string(payload.get("codigo_pronunciamento"))
        or _optional_string(pronouncement.get("CodigoPronunciamento")),
        "pronouncement_date": _optional_string(pronouncement.get("Data")),
        "plenary_session_id": _optional_string(session.get("CodigoSessao")),
        "legislative_session_id": _optional_string(session.get("CodigoSessaoLegislativa")),
        "session_date": _optional_string(session.get("DataSessao")),
        "session_type": _optional_string(session.get("TipoSessao")),
        "author_name": _optional_string(pronouncement.get("NomeAutor")),
        "author_type": _optional_string(pronouncement.get("TipoAutor")),
        "author_function": _optional_string(pronouncement.get("FuncaoAutor")),
        "party": _optional_string(pronouncement.get("Partido")),
        "federative_unit": _optional_string(pronouncement.get("UF")),
        "speech_type_code": _optional_string(speech_type.get("Codigo")),
        "speech_type_description": _optional_string(speech_type.get("Descricao")),
        "speech_type_active": _optional_string(speech_type.get("IndicadorAtivo")),
        "retrieval_method": _optional_string(payload.get("metodo_obtencao")),
        "text_status": _optional_string(payload.get("texto_status")),
        "text": text,
        "text_sha256": sha256_bytes((text or "").encode("utf-8")),
        "text_bytes": len((text or "").encode("utf-8")),
    }


def g03_arrow_schema(pa: Any) -> Any:
    nullable_strings = (
        "checksum",
        "collected_at",
        "coverage_start_date",
        "coverage_end_date",
        "partition",
        "run_id",
        "pronouncement_id",
        "pronouncement_date",
        "plenary_session_id",
        "legislative_session_id",
        "session_date",
        "session_type",
        "author_name",
        "author_type",
        "author_function",
        "party",
        "federative_unit",
        "speech_type_code",
        "speech_type_description",
        "speech_type_active",
        "retrieval_method",
        "text_status",
        "text",
    )
    fields = [
        pa.field("source", pa.string(), nullable=False),
        pa.field("dataset", pa.string(), nullable=False),
        pa.field("record_type", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("raw_sha256", pa.string(), nullable=False),
    ]
    fields.extend(pa.field(name, pa.string(), nullable=True) for name in nullable_strings)
    fields.extend(
        (
            pa.field("text_sha256", pa.string(), nullable=False),
            pa.field("text_bytes", pa.int64(), nullable=False),
        )
    )
    return pa.schema(fields)


def _arrow_schema(pa: Any) -> Any:
    return g03_arrow_schema(pa)


def _record_identity(record: Mapping[str, Any]) -> str:
    period = _mapping(record.get("periodo"))
    start = _required_string(period.get("data_inicio"), "periodo.data_inicio")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
        raise ParquetPipelineError("periodo.data_inicio inválido")
    identity = {
        "dataset": _required_string(record.get("dataset"), "dataset"),
        "record_type": _required_string(record.get("record_type"), "record_type"),
        "source": _required_string(record.get("source"), "source"),
        "source_id": _required_string(record.get("source_id"), "source_id"),
        "substantive_year": int(start[:4]),
    }
    return canonical_json_bytes(identity).decode("utf-8")


def _parse_selection_entry(value: Any) -> SelectionEntry:
    if not isinstance(value, dict):
        raise ValueError("selection entry")
    entry = SelectionEntry(
        identity=_required_string(value["identity"], "identity"),
        line_number=int(value["line_number"]),
        source_locator=_required_string(value["source_locator"], "source_locator"),
        raw_bytes=int(value["raw_bytes"]),
        raw_sha256=_required_sha256(value["raw_sha256"], "raw_sha256"),
    )
    if entry.line_number <= 0 or entry.raw_bytes <= 0:
        raise ValueError("line_number/raw_bytes")
    _validate_locator(entry.source_locator)
    identity = json.loads(entry.identity)
    if canonical_json_bytes(identity).decode("utf-8") != entry.identity:
        raise ValueError("identity")
    return entry


def _decode_record(line: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParquetPipelineError(f"JSON inválido em {label}") from exc
    if not isinstance(value, dict):
        raise ParquetPipelineError(f"registro JSON não é objeto em {label}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} ausente")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_sha256(value: Any, label: str) -> str:
    string = _required_string(value, label)
    if not SHA256_RE.fullmatch(string):
        raise ValueError(label)
    return string


def _validate_locator(locator: str) -> None:
    normalized = locator.strip("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized != locator
        or path.is_absolute()
        or ".." in path.parts
        or ":" in locator
        or any(ord(character) < 32 for character in locator)
    ):
        raise ParquetPipelineError("locator inseguro")


def _pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ParquetPipelineError(
            "pyarrow é obrigatório; instale o grupo de dependências cloud"
        ) from exc
    return pa, pq
