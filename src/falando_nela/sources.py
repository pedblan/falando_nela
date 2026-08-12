from __future__ import annotations

import configparser
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from falando_nela.config import DEFAULT_DRIVE_SOURCE_FOLDER_ID
from falando_nela.raw import sha256_file


class SourceError(RuntimeError):
    """Falha segura ao listar ou ler uma origem raw."""


class BaselineMismatch(SourceError):
    """A listagem atual diverge do inventário G01 congelado."""


@dataclass(frozen=True)
class RcloneConfigSnapshot:
    """Visão efêmera e redigida de uma configuração rclone cifrada."""

    config_path: Path
    redacted_config: str


@dataclass(frozen=True)
class SourceObject:
    locator: str
    size_bytes: int
    sha256: str | None = None
    provider_hashes: dict[str, str] = field(default_factory=dict)
    modified_time: str | None = None
    provider_id: str | None = None

    def fingerprint_dict(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "size_bytes": self.size_bytes,
            "provider_id": self.provider_id,
            "sha256": self.sha256,
            "provider_hashes": dict(sorted(self.provider_hashes.items())),
            "modified_time": self.modified_time,
        }


@dataclass(frozen=True)
class ProviderIdentityGroup:
    group_id: str
    observed_locator: str
    provider_ids: tuple[str, ...]
    baseline_locators: tuple[str, ...]
    size_bytes: int
    sha256: str
    decision: str

    def fingerprint_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "observed_locator": self.observed_locator,
            "provider_ids": list(self.provider_ids),
            "baseline_locators": list(self.baseline_locators),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class ProviderIdentityMap:
    schema_version: int
    source_folder_id: str
    baseline_file_id: str
    baseline_sha256: str
    groups: tuple[ProviderIdentityGroup, ...]

    def fingerprint_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_folder_id": self.source_folder_id,
            "baseline_file_id": self.baseline_file_id,
            "baseline_sha256": self.baseline_sha256,
            "groups": [group.fingerprint_dict() for group in self.groups],
        }


@dataclass(frozen=True)
class SourceRecord:
    locator: str
    line_number: int
    raw_record: bytes
    value: dict[str, Any] | None
    error: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw_record).hexdigest()


class LocalRawSource:
    kind = "local"

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise SourceError(f"origem local não é diretório: {self.root}")
        self.list_calls = 0
        self.stream_calls = 0
        self.bytes_read = 0

    def descriptor(self) -> dict[str, str]:
        return {"kind": self.kind, "root": str(self.root)}

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
        self.list_calls += 1
        base = self.root if not prefix else _safe_local_prefix(self.root, prefix)
        objects: list[SourceObject] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not _supported_raw_name(path.name):
                continue
            objects.append(
                SourceObject(
                    locator=path.relative_to(self.root).as_posix(),
                    size_bytes=path.stat().st_size,
                    sha256=sha256_file(path),
                )
            )
        return objects

    def iter_records(self, objects: Sequence[SourceObject]) -> Iterator[SourceRecord]:
        self.stream_calls += 1
        for source_object in sorted(objects, key=lambda item: item.locator):
            path = _safe_local_prefix(self.root, source_object.locator)
            with _open_local(path) as handle:
                yield from self._iter_handle(handle, source_object.locator)

    def _iter_handle(self, handle: BinaryIO, locator: str) -> Iterator[SourceRecord]:
        for line_number, raw_line in enumerate(handle, start=1):
            self.bytes_read += len(raw_line)
            raw_record = raw_line.rstrip(b"\r\n")
            if not raw_record.strip():
                continue
            yield _decode_record(locator, line_number, raw_record)


class RcloneRawSource:
    kind = "rclone"

    def __init__(
        self,
        *,
        remote: str,
        config_path: Path,
        prefix: str,
        expected_folder_id: str = DEFAULT_DRIVE_SOURCE_FOLDER_ID,
        executable: str = "rclone",
        config_snapshot: RcloneConfigSnapshot | None = None,
        include_all_files: bool = False,
        locators_relative_to_prefix: bool = False,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", remote):
            raise SourceError("nome de remote rclone inválido")
        self.remote = remote
        self.config_path = config_path.expanduser().resolve(strict=True)
        self.prefix = _safe_remote_prefix(prefix)
        self.expected_folder_id = expected_folder_id
        self.include_all_files = include_all_files
        self.locators_relative_to_prefix = locators_relative_to_prefix
        pinned_rclone_remote_path(self.remote, self.expected_folder_id)
        self.executable = executable
        if shutil.which(self.executable) is None:
            raise SourceError("rclone não está instalado ou não está no PATH")
        snapshot = config_snapshot or inspect_rclone_config(
            self.config_path,
            executable=self.executable,
        )
        _validate_snapshot_path(snapshot, self.config_path)
        validate_rclone_readonly_config(
            snapshot.redacted_config,
            remote=self.remote,
            expected_folder_id=self.expected_folder_id,
        )
        self.list_calls = 0
        self.stream_calls = 0
        self.bytes_read = 0

    def descriptor(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "remote": self.remote,
            "prefix": self.prefix,
            "root_folder_id": self.expected_folder_id,
            "scope": "drive.readonly",
            "listing": "all_files" if self.include_all_files else "raw_only",
            "locators": (
                "relative_to_prefix" if self.locators_relative_to_prefix else "root_relative"
            ),
        }

    def list_objects(self, prefix: str | None = None) -> list[SourceObject]:
        self.list_calls += 1
        selected_prefix = self.prefix if prefix is None else _safe_remote_prefix(prefix)
        result = self._run(
            "lsjson",
            self._remote_path(selected_prefix),
            "--recursive",
            "--files-only",
            "--hash",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SourceError("rclone lsjson retornou JSON inválido") from exc
        if not isinstance(payload, list):
            raise SourceError("rclone lsjson não retornou uma lista")
        objects: list[SourceObject] = []
        for item in payload:
            if not isinstance(item, dict) or item.get("IsDir") is True:
                continue
            relative = item.get("Path")
            size = item.get("Size")
            if not isinstance(relative, str) or not isinstance(size, int):
                raise SourceError("item inválido em rclone lsjson")
            locator = (
                _safe_remote_prefix(relative)
                if self.locators_relative_to_prefix
                else _join_remote(selected_prefix, relative)
            )
            if not self.include_all_files and not _supported_raw_name(locator):
                continue
            hashes = item.get("Hashes") if isinstance(item.get("Hashes"), dict) else {}
            objects.append(
                SourceObject(
                    locator=locator,
                    size_bytes=size,
                    provider_id=(str(item.get("ID")) if isinstance(item.get("ID"), str) else None),
                    provider_hashes={str(key): str(value) for key, value in hashes.items()},
                    modified_time=str(item.get("ModTime")) if item.get("ModTime") else None,
                )
            )
        return sorted(objects, key=lambda item: (item.locator, item.provider_id or ""))

    def iter_records(self, objects: Sequence[SourceObject]) -> Iterator[SourceRecord]:
        self.stream_calls += 1
        for source_object in sorted(objects, key=lambda item: item.locator):
            physical_locator = (
                _join_remote(self.prefix, source_object.locator)
                if self.locators_relative_to_prefix
                else source_object.locator
            )
            command = self._command("cat", self._remote_path(physical_locator))
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None
            assert process.stderr is not None
            try:
                if source_object.locator.endswith(".gz"):
                    stream: BinaryIO = gzip.GzipFile(fileobj=process.stdout, mode="rb")
                else:
                    stream = process.stdout
                with stream:
                    for line_number, raw_line in enumerate(stream, start=1):
                        self.bytes_read += len(raw_line)
                        raw_record = raw_line.rstrip(b"\r\n")
                        if not raw_record.strip():
                            continue
                        yield _decode_record(source_object.locator, line_number, raw_record)
            finally:
                process.stdout.close()
            process.stderr.read()
            return_code = process.wait()
            if return_code != 0:
                raise SourceError(_safe_rclone_error("cat", return_code))

    def _remote_path(self, locator: str) -> str:
        return pinned_rclone_remote_path(
            self.remote,
            self.expected_folder_id,
            locator,
        )

    def _command(self, subcommand: str, *arguments: str) -> list[str]:
        if subcommand not in {"lsjson", "cat"}:
            raise SourceError(f"subcomando rclone proibido na origem: {subcommand}")
        return [
            self.executable,
            subcommand,
            *arguments,
            "--config",
            str(self.config_path),
            "--ask-password=false",
        ]

    def _run(self, subcommand: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            self._command(subcommand, *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SourceError(_safe_rclone_error(subcommand, result.returncode))
        return result


def validate_rclone_readonly_config(
    redacted_config: str,
    *,
    remote: str,
    expected_folder_id: str = DEFAULT_DRIVE_SOURCE_FOLDER_ID,
) -> None:
    pinned_rclone_remote_path(remote, expected_folder_id)
    parser = parse_redacted_rclone_config(redacted_config)
    if not parser.has_section(remote):
        raise SourceError(f"remote rclone ausente: {remote}")
    if parser.get(remote, "type", fallback="").strip() != "drive":
        raise SourceError("o remote de origem deve usar type=drive")
    if parser.get(remote, "scope", fallback="").strip() != "drive.readonly":
        raise SourceError("o remote de origem deve usar scope=drive.readonly")
    configured_root = parser.get(remote, "root_folder_id", fallback="").strip()
    if configured_root not in {expected_folder_id, "XXX"}:
        raise SourceError("root_folder_id do remote não coincide com a pasta aprovada")


def inspect_rclone_config(
    config_path: Path,
    *,
    executable: str = "rclone",
) -> RcloneConfigSnapshot:
    """Confirma cifra e obtém somente a projeção redigida via rclone."""

    try:
        resolved = config_path.expanduser().resolve(strict=True)
        mode = resolved.stat().st_mode
    except OSError as exc:
        raise SourceError("configuração rclone ausente ou inacessível") from exc
    if not resolved.is_file():
        raise SourceError("configuração rclone não é um arquivo regular")
    if mode & 0o077:
        raise SourceError(
            "configuração rclone deve ter permissões privadas (0600 ou mais restritas)"
        )
    if shutil.which(executable) is None:
        raise SourceError("rclone não está instalado ou não está no PATH")
    if os.environ.get("RCLONE_CONFIG_PASS"):
        raise SourceError(
            "RCLONE_CONFIG_PASS não é aceito; use RCLONE_PASSWORD_COMMAND com o Chaves do macOS"
        )
    if not os.environ.get("RCLONE_PASSWORD_COMMAND"):
        raise SourceError(
            "RCLONE_PASSWORD_COMMAND deve recuperar a senha cifrada pelo Chaves do macOS"
        )

    encryption_check = _run_rclone_config_command(
        executable,
        resolved,
        "config",
        "encryption",
        "check",
    )
    if encryption_check.returncode != 0:
        raise SourceError(
            "a configuração rclone deve estar cifrada e desbloqueável sem prompt interativo"
        )
    redacted = _run_rclone_config_command(
        executable,
        resolved,
        "config",
        "redacted",
    )
    if redacted.returncode != 0:
        raise SourceError("não foi possível inspecionar a configuração rclone de forma redigida")
    parse_redacted_rclone_config(redacted.stdout)
    return RcloneConfigSnapshot(resolved, redacted.stdout)


def parse_redacted_rclone_config(redacted_config: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(interpolation=None)
    try:
        parser.read_string(redacted_config)
    except configparser.Error as exc:
        raise SourceError("a projeção redigida da configuração rclone é inválida") from exc
    if not parser.sections():
        raise SourceError("a projeção redigida da configuração rclone está vazia")
    return parser


def _run_rclone_config_command(
    executable: str,
    config_path: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                executable,
                *arguments,
                "--config",
                str(config_path),
                "--ask-password=false",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceError("falha segura ao inspecionar a configuração rclone") from exc


def _validate_snapshot_path(snapshot: RcloneConfigSnapshot, expected: Path) -> None:
    if snapshot.config_path != expected:
        raise SourceError("snapshot rclone não pertence ao arquivo de configuração informado")


def load_g01_baseline(path: Path) -> list[SourceObject]:
    objects: list[SourceObject] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("item_type") != "file":
                    continue
                locator = row.get("relative_path", "")
                raw_size = row.get("size_bytes", "")
                if not locator or not raw_size:
                    raise BaselineMismatch("linha de arquivo incompleta na baseline G01")
                objects.append(SourceObject(locator=locator, size_bytes=int(raw_size)))
    except (OSError, csv.Error, ValueError) as exc:
        raise BaselineMismatch("não foi possível ler a baseline G01") from exc
    if not objects:
        raise BaselineMismatch("baseline G01 não contém arquivos")
    return sorted(objects, key=lambda item: item.locator)


def load_provider_identity_map(path: Path) -> ProviderIdentityMap:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineMismatch("mapa de identidades do provedor é ilegível") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise BaselineMismatch("schema do mapa de identidades do provedor é inválido")
    source_folder_id = payload.get("source_folder_id")
    baseline_file_id = payload.get("baseline_file_id")
    baseline_sha256 = payload.get("baseline_sha256")
    raw_groups = payload.get("groups")
    if not isinstance(source_folder_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", source_folder_id
    ):
        raise BaselineMismatch("source_folder_id inválido no mapa de identidades")
    if not isinstance(baseline_file_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", baseline_file_id
    ):
        raise BaselineMismatch("baseline_file_id inválido no mapa de identidades")
    if not isinstance(baseline_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", baseline_sha256):
        raise BaselineMismatch("baseline_sha256 inválido no mapa de identidades")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise BaselineMismatch("mapa de identidades não contém grupos")
    groups: list[ProviderIdentityGroup] = []
    group_ids: set[str] = set()
    provider_ids: set[str] = set()
    baseline_locators: set[str] = set()
    for item in raw_groups:
        if not isinstance(item, dict):
            raise BaselineMismatch("grupo inválido no mapa de identidades")
        group_id = item.get("group_id")
        observed_locator = item.get("observed_locator")
        raw_provider_ids = item.get("provider_ids")
        raw_baseline_locators = item.get("baseline_locators")
        size_bytes = item.get("size_bytes")
        content_sha256 = item.get("sha256")
        decision = item.get("decision")
        if not isinstance(group_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", group_id
        ):
            raise BaselineMismatch("group_id inválido no mapa de identidades")
        if group_id in group_ids:
            raise BaselineMismatch("group_id duplicado no mapa de identidades")
        group_ids.add(group_id)
        if not isinstance(observed_locator, str):
            raise BaselineMismatch("observed_locator inválido no mapa de identidades")
        _safe_remote_prefix(observed_locator)
        if (
            not isinstance(raw_provider_ids, list)
            or not raw_provider_ids
            or not all(
                isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value)
                for value in raw_provider_ids
            )
        ):
            raise BaselineMismatch("provider_ids inválidos no mapa de identidades")
        if (
            not isinstance(raw_baseline_locators, list)
            or len(raw_baseline_locators) != len(raw_provider_ids)
            or not all(isinstance(value, str) for value in raw_baseline_locators)
        ):
            raise BaselineMismatch("baseline_locators inválidos no mapa de identidades")
        normalized_baseline_locators = tuple(
            _safe_remote_prefix(value) for value in raw_baseline_locators
        )
        normalized_provider_ids = tuple(str(value) for value in raw_provider_ids)
        if len(set(normalized_provider_ids)) != len(normalized_provider_ids):
            raise BaselineMismatch("provider_id duplicado dentro do grupo")
        if len(set(normalized_baseline_locators)) != len(normalized_baseline_locators):
            raise BaselineMismatch("baseline_locator duplicado dentro do grupo")
        if provider_ids.intersection(normalized_provider_ids):
            raise BaselineMismatch("provider_id repetido entre grupos")
        if baseline_locators.intersection(normalized_baseline_locators):
            raise BaselineMismatch("baseline_locator repetido entre grupos")
        provider_ids.update(normalized_provider_ids)
        baseline_locators.update(normalized_baseline_locators)
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise BaselineMismatch("size_bytes inválido no mapa de identidades")
        if not isinstance(content_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise BaselineMismatch("sha256 inválido no mapa de identidades")
        if decision != "exclude_unsupported_format":
            raise BaselineMismatch("decisão não permitida no mapa de identidades")
        groups.append(
            ProviderIdentityGroup(
                group_id=group_id,
                observed_locator=observed_locator,
                provider_ids=normalized_provider_ids,
                baseline_locators=normalized_baseline_locators,
                size_bytes=size_bytes,
                sha256=content_sha256,
                decision=decision,
            )
        )
    return ProviderIdentityMap(
        schema_version=1,
        source_folder_id=source_folder_id,
        baseline_file_id=baseline_file_id,
        baseline_sha256=baseline_sha256,
        groups=tuple(sorted(groups, key=lambda group: group.group_id)),
    )


def reconcile_baseline(
    baseline: Sequence[SourceObject],
    current: Sequence[SourceObject],
    *,
    identity_map: ProviderIdentityMap | None = None,
) -> dict[str, Any]:
    expected_objects = _unique_object_map(baseline, label="baseline")
    observed_objects = list(current)
    reconciled_groups: list[dict[str, Any]] = []
    consumed_provider_ids: set[str] = set()
    consumed_baseline_locators: set[str] = set()
    if identity_map is not None:
        current_by_provider_id: dict[str, SourceObject] = {}
        for item in current:
            if item.provider_id is None:
                continue
            if item.provider_id in current_by_provider_id:
                raise BaselineMismatch("provider_id duplicado no inventário atual")
            current_by_provider_id[item.provider_id] = item
        for group in identity_map.groups:
            expected_group: list[SourceObject] = []
            observed_group: list[SourceObject] = []
            for locator in group.baseline_locators:
                expected_item = expected_objects.get(locator)
                if expected_item is None:
                    raise BaselineMismatch(f"baseline_locator ausente para grupo {group.group_id}")
                expected_group.append(expected_item)
            for provider_id in group.provider_ids:
                observed_item = current_by_provider_id.get(provider_id)
                if observed_item is None:
                    raise BaselineMismatch(f"provider_id ausente para grupo {group.group_id}")
                observed_group.append(observed_item)
            if any(item.locator != group.observed_locator for item in observed_group):
                raise BaselineMismatch(f"locator observado diverge no grupo {group.group_id}")
            if any(item.size_bytes != group.size_bytes for item in expected_group):
                raise BaselineMismatch(f"tamanho G01 diverge no grupo {group.group_id}")
            if any(item.size_bytes != group.size_bytes for item in observed_group):
                raise BaselineMismatch(f"tamanho Drive diverge no grupo {group.group_id}")
            if any(item.provider_hashes.get("sha256") != group.sha256 for item in observed_group):
                raise BaselineMismatch(f"hash Drive diverge no grupo {group.group_id}")
            consumed_provider_ids.update(group.provider_ids)
            consumed_baseline_locators.update(group.baseline_locators)
            reconciled_groups.append(
                {
                    "group_id": group.group_id,
                    "provider_ids": list(group.provider_ids),
                    "baseline_locators": list(group.baseline_locators),
                    "observed_locator": group.observed_locator,
                    "files": len(group.provider_ids),
                    "bytes": group.size_bytes * len(group.provider_ids),
                    "sha256": group.sha256,
                    "decision": group.decision,
                }
            )
    expected = _unique_size_map(
        [
            item
            for locator, item in expected_objects.items()
            if locator not in consumed_baseline_locators
        ],
        label="baseline",
    )
    observed = _unique_size_map(
        [item for item in observed_objects if item.provider_id not in consumed_provider_ids],
        label="inventário atual",
    )
    missing = sorted(set(expected) - set(observed))
    added = sorted(set(observed) - set(expected))
    changed = sorted(
        locator
        for locator in set(expected) & set(observed)
        if expected[locator] != observed[locator]
    )
    if missing or added or changed:
        raise BaselineMismatch(
            "baseline G01 divergiu: "
            f"missing={len(missing)}, added={len(added)}, changed={len(changed)}"
        )
    return {
        "files": len(current),
        "bytes": sum(item.size_bytes for item in current),
        "missing": 0,
        "added": 0,
        "changed": 0,
        "identity_groups": reconciled_groups,
        "provider_ids_reconciled": len(consumed_provider_ids),
    }


def _unique_object_map(objects: Sequence[SourceObject], *, label: str) -> dict[str, SourceObject]:
    result: dict[str, SourceObject] = {}
    for item in objects:
        if item.locator in result:
            raise BaselineMismatch(f"locator duplicado em {label}: {item.locator}")
        result[item.locator] = item
    return result


def _unique_size_map(objects: Sequence[SourceObject], *, label: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in objects:
        if item.locator in result:
            raise BaselineMismatch(f"locator duplicado em {label}: {item.locator}")
        result[item.locator] = item.size_bytes
    return result


def _decode_record(locator: str, line_number: int, raw_record: bytes) -> SourceRecord:
    try:
        value = json.loads(raw_record)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return SourceRecord(locator, line_number, raw_record, None, f"json_invalid:{exc.msg}")
    if not isinstance(value, dict):
        return SourceRecord(locator, line_number, raw_record, None, "json_not_object")
    return SourceRecord(locator, line_number, raw_record, value)


def _open_local(path: Path) -> BinaryIO:
    if path.name.endswith(".jsonl.gz"):
        return gzip.open(path, "rb")
    return path.open("rb")


def _supported_raw_name(name: str) -> bool:
    return name.endswith(".jsonl") or name.endswith(".jsonl.gz")


def _safe_local_prefix(root: Path, prefix: str) -> Path:
    relative = PurePosixPath(prefix)
    if relative.is_absolute() or ".." in relative.parts:
        raise SourceError("prefixo local inseguro")
    resolved = root.joinpath(*relative.parts).resolve(strict=True)
    if resolved != root and not resolved.is_relative_to(root):
        raise SourceError("prefixo local escapou da origem")
    return resolved


def _safe_remote_prefix(prefix: str) -> str:
    normalized = prefix.strip("/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise SourceError("prefixo remoto inseguro")
    return "" if normalized == "." else normalized


def pinned_rclone_remote_path(remote: str, folder_id: str, locator: str = "") -> str:
    """Fixa o ID da raiz na própria referência rclone, sem ler segredos."""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", remote):
        raise SourceError("nome de remote rclone inválido")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
        raise SourceError("root_folder_id rclone inválido")
    safe_locator = _safe_remote_prefix(locator)
    return f"{remote},root_folder_id={folder_id}:{safe_locator}"


def _join_remote(prefix: str, relative: str) -> str:
    safe_relative = _safe_remote_prefix(relative)
    return f"{prefix}/{safe_relative}".strip("/")


def _safe_rclone_error(subcommand: str, return_code: int) -> str:
    # stderr pode conter URLs assinadas, tokens ou trechos da configuração.
    return f"rclone {subcommand} falhou (exit {return_code}); consulte o log local protegido"
