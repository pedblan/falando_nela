from __future__ import annotations

import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXPECTED_PROJECT_ID = "falando-nela-pedblan"
EXPECTED_PROJECT_NUMBER = "818569314985"
EXPECTED_REGION = "southamerica-east1"
EXPECTED_STATE_BUCKET = "falando-nela-pedblan-tfstate"
EXPECTED_DATA_BUCKET = "falando-nela-pedblan-data"
EXPECTED_RAW_FOLDER_ID = "1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9"
EXPECTED_SOURCE_FILES = 2_887
EXPECTED_SOURCE_BYTES = 14_686_043_352
EXPECTED_SENTINEL_BYTES = 78_822
EXPECTED_BATCH_PLAN_FILE_SHA256 = "ef933d8cbe89ff5d1110c5e743fddfd2cb314711b31c9eed7dbb60fc1a56606b"
EXPECTED_EMPTY_SOURCE_LOCATORS = (
    "camara/plenario_discursos/ano=1954/mes=12/prod-historico-camara-plenario.jsonl",
    "camara/plenario_discursos/ano=1956/mes=06/prod-historico-camara-plenario.jsonl",
)
EXPECTED_BATCH_COUNT = 38
EXPECTED_BATCH_MAX_FILES = 100
EXPECTED_BATCH_MAX_BYTES = 512 * 1024 * 1024
EXPECTED_OVERSIZED_BATCH_COUNT = 4
EXPECTED_RESTORE_SAMPLE_MAX_OBJECT_BYTES = 16 * 1024 * 1024
EXPECTED_RESTORE_SAMPLE_FILES = 16
EXPECTED_RESTORE_SAMPLE_BYTES = 13_966_298
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
MD5_PATTERN = re.compile(r"[0-9a-f]{32}")


class GcpConfigError(ValueError):
    """A configuração GCP diverge do contrato versionado."""


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateConfig(StrictModel):
    bucket: str
    prefix: str
    soft_delete_retention_seconds: int = Field(ge=604_800)
    versioning: bool


class DataConfig(StrictModel):
    bucket: str
    raw_prefix: str
    processed_prefix: str
    manifests_prefix: str
    operations_prefix: str
    soft_delete_retention_seconds: int = Field(ge=604_800)
    versioning: bool


class MigratorConfig(StrictModel):
    service_account_id: str


class BudgetConfig(StrictModel):
    display_name: str
    amount_usd: int = Field(gt=0)
    current_spend_thresholds: tuple[float, ...]
    forecasted_spend_thresholds: tuple[float, ...]
    default_iam_recipients: bool
    project_level_recipients: bool


class SentinelConfig(StrictModel):
    category: Literal["metadata", "monthly_text", "transcription_queue"]
    source_locator: str
    destination_locator: str
    size_bytes: int = Field(gt=0)
    md5: str
    sha256: str

    @model_validator(mode="after")
    def validate_entry(self) -> SentinelConfig:
        _validate_relative_locator(self.source_locator)
        _validate_relative_locator(self.destination_locator)
        if not MD5_PATTERN.fullmatch(self.md5):
            raise ValueError("md5 do sentinela é inválido")
        if not SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError("sha256 do sentinela é inválido")
        return self


class MigrationConfig(StrictModel):
    source_operational_root_folder_id: str
    source_raw_folder_id: str
    source_files: int = Field(gt=0)
    source_bytes: int = Field(gt=0)
    source_catalog_sha256: str
    source_catalog_file_sha256: str
    source_batch_plan_file_sha256: str
    authoritative_raw: Literal["drive", "gcs"]
    approved_empty_source_locators: tuple[str, ...]
    batch_count: int = Field(gt=0)
    batch_max_files: int = Field(gt=0)
    batch_max_bytes: int = Field(gt=0)
    oversized_batch_count: int = Field(ge=0)
    restore_sample_max_object_bytes: int = Field(gt=0)
    restore_sample_files: int = Field(gt=0)
    restore_sample_bytes: int = Field(gt=0)
    max_cost_usd: int = Field(gt=0)
    sentinel: tuple[SentinelConfig, ...]

    @model_validator(mode="after")
    def validate_migration(self) -> MigrationConfig:
        for folder_id in (
            self.source_operational_root_folder_id,
            self.source_raw_folder_id,
        ):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
                raise ValueError("ID de pasta Drive inválido")
        for digest in (
            self.source_catalog_sha256,
            self.source_catalog_file_sha256,
            self.source_batch_plan_file_sha256,
        ):
            if not SHA256_PATTERN.fullmatch(digest):
                raise ValueError("hash de catálogo inválido")
        for locator in self.approved_empty_source_locators:
            _validate_relative_locator(locator)
        categories = [item.category for item in self.sentinel]
        if sorted(categories) != ["metadata", "monthly_text", "transcription_queue"]:
            raise ValueError("sentinela deve conter exatamente as três categorias G01")
        if len({item.source_locator for item in self.sentinel}) != len(self.sentinel):
            raise ValueError("locator de origem duplicado no sentinela")
        if len({item.destination_locator for item in self.sentinel}) != len(self.sentinel):
            raise ValueError("locator de destino duplicado no sentinela")
        return self


class GcpContract(StrictModel):
    schema_version: Literal[2]
    project_id: str
    project_number: str
    region: str
    state: StateConfig
    data: DataConfig
    migrator: MigratorConfig
    budget: BudgetConfig
    migration: MigrationConfig

    @model_validator(mode="after")
    def validate_contract(self) -> GcpContract:
        expected = {
            "project_id": (self.project_id, EXPECTED_PROJECT_ID),
            "project_number": (self.project_number, EXPECTED_PROJECT_NUMBER),
            "region": (self.region, EXPECTED_REGION),
            "state.bucket": (self.state.bucket, EXPECTED_STATE_BUCKET),
            "data.bucket": (self.data.bucket, EXPECTED_DATA_BUCKET),
            "data.raw_prefix": (self.data.raw_prefix, "data/raw/v1"),
            "migration.source_raw_folder_id": (
                self.migration.source_raw_folder_id,
                EXPECTED_RAW_FOLDER_ID,
            ),
            "migration.source_files": (self.migration.source_files, EXPECTED_SOURCE_FILES),
            "migration.source_bytes": (self.migration.source_bytes, EXPECTED_SOURCE_BYTES),
            "migration.source_batch_plan_file_sha256": (
                self.migration.source_batch_plan_file_sha256,
                EXPECTED_BATCH_PLAN_FILE_SHA256,
            ),
            "migration.approved_empty_source_locators": (
                self.migration.approved_empty_source_locators,
                EXPECTED_EMPTY_SOURCE_LOCATORS,
            ),
            "migration.batch_count": (
                self.migration.batch_count,
                EXPECTED_BATCH_COUNT,
            ),
            "migration.batch_max_files": (
                self.migration.batch_max_files,
                EXPECTED_BATCH_MAX_FILES,
            ),
            "migration.batch_max_bytes": (
                self.migration.batch_max_bytes,
                EXPECTED_BATCH_MAX_BYTES,
            ),
            "migration.oversized_batch_count": (
                self.migration.oversized_batch_count,
                EXPECTED_OVERSIZED_BATCH_COUNT,
            ),
            "migration.restore_sample_max_object_bytes": (
                self.migration.restore_sample_max_object_bytes,
                EXPECTED_RESTORE_SAMPLE_MAX_OBJECT_BYTES,
            ),
            "migration.restore_sample_files": (
                self.migration.restore_sample_files,
                EXPECTED_RESTORE_SAMPLE_FILES,
            ),
            "migration.restore_sample_bytes": (
                self.migration.restore_sample_bytes,
                EXPECTED_RESTORE_SAMPLE_BYTES,
            ),
            "migration.max_cost_usd": (self.migration.max_cost_usd, 1),
            "migrator.service_account_id": (
                self.migrator.service_account_id,
                "fn-migrator",
            ),
            "budget.display_name": (self.budget.display_name, "falando-nela-gcp-first"),
            "budget.amount_usd": (self.budget.amount_usd, 5),
        }
        divergences = [key for key, (observed, wanted) in expected.items() if observed != wanted]
        if divergences:
            raise ValueError(f"configuração GCP divergiu: {', '.join(divergences)}")
        if self.state.soft_delete_retention_seconds != 604_800 or not self.state.versioning:
            raise ValueError("proteção do state divergiu do contrato G01")
        if self.data.soft_delete_retention_seconds != 604_800 or self.data.versioning:
            raise ValueError("proteção do bucket de dados divergiu do contrato G01")
        if self.budget.current_spend_thresholds != (0.5, 0.9, 1.0):
            raise ValueError("thresholds atuais do budget divergiram")
        if self.budget.forecasted_spend_thresholds != (1.0,):
            raise ValueError("threshold previsto do budget divergiu")
        if not self.budget.default_iam_recipients or not self.budget.project_level_recipients:
            raise ValueError("destinatários IAM do budget devem permanecer ativos")
        if sum(item.size_bytes for item in self.migration.sentinel) != EXPECTED_SENTINEL_BYTES:
            raise ValueError("bytes do sentinela divergiram")
        for item in self.migration.sentinel:
            expected_destination = f"{self.data.raw_prefix}/{item.source_locator}"
            if item.destination_locator != expected_destination:
                raise ValueError("locator de destino não preserva a origem sob data/raw/v1")
        return self

    @property
    def migrator_email(self) -> str:
        return f"{self.migrator.service_account_id}@{self.project_id}.iam.gserviceaccount.com"

    def confirm_targets(
        self,
        *,
        project_id: str,
        bucket: str,
        source_raw_folder_id: str,
    ) -> None:
        if project_id != self.project_id:
            raise GcpConfigError("confirmação literal do project ID diverge")
        if bucket != self.data.bucket:
            raise GcpConfigError("confirmação literal do bucket diverge")
        if source_raw_folder_id != self.migration.source_raw_folder_id:
            raise GcpConfigError("confirmação literal da pasta raw diverge")


def load_gcp_contract(path: Path) -> GcpContract:
    try:
        resolved = path.expanduser().resolve(strict=True)
        with resolved.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GcpConfigError("configuração GCP ausente ou inválida") from exc
    try:
        return GcpContract.model_validate(payload)
    except ValueError as exc:
        raise GcpConfigError("configuração GCP diverge do contrato versionado") from exc


def _validate_relative_locator(locator: str) -> None:
    normalized = locator.strip("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or ":" in normalized
        or any(ord(character) < 32 for character in normalized)
    ):
        raise ValueError("locator inseguro")
