from __future__ import annotations

import re
import tomllib
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXPECTED_PROJECT_ID = "falando-nela-pedblan"
EXPECTED_PROJECT_NUMBER = "818569314985"
EXPECTED_REGION = "southamerica-east1"
EXPECTED_STATE_BUCKET = "falando-nela-pedblan-tfstate"
EXPECTED_DATA_BUCKET = "falando-nela-pedblan-data"
EXPECTED_RAW_FOLDER_ID = "1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9"
EXPECTED_SOURCE_PREFIX = "v1"
EXPECTED_SOURCE_FILES = 2_887
EXPECTED_SOURCE_BYTES = 14_686_043_352
EXPECTED_SENTINEL_BYTES = 78_822
EXPECTED_BATCH_PLAN_FILE_SHA256 = "ef933d8cbe89ff5d1110c5e743fddfd2cb314711b31c9eed7dbb60fc1a56606b"
EXPECTED_G03_SELECTION_SHA256 = "8e6d879159078db7f6549a5997aded0ae29d2dda1311609b0353493f9525a1dc"
EXPECTED_EMPTY_SOURCE_LOCATORS = (
    "camara/plenario_discursos/ano=1954/mes=12/prod-historico-camara-plenario.jsonl",
    "camara/plenario_discursos/ano=1956/mes=06/prod-historico-camara-plenario.jsonl",
)
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


class PipelineConfig(StrictModel):
    service_account_id: str
    artifact_repository_id: str
    image_name: str
    job_name: str
    selection_manifest_sha256: str
    task_count: int = Field(gt=0)
    parallelism: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    cpu: Literal["1"]
    memory: Literal["1Gi"]
    timeout_seconds: int = Field(gt=0)
    max_cost_usd: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_pipeline(self) -> PipelineConfig:
        identifiers = (
            self.service_account_id,
            self.artifact_repository_id,
            self.image_name,
            self.job_name,
        )
        if any(not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", item) for item in identifiers):
            raise ValueError("identificador G03 inválido")
        if not SHA256_PATTERN.fullmatch(self.selection_manifest_sha256):
            raise ValueError("hash da seleção G03 inválido")
        return self


class MarimoConfig(StrictModel):
    operation_id: str
    parquet_locator: str
    parquet_schema: str
    expected_records: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_marimo(self) -> MarimoConfig:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.operation_id):
            raise ValueError("operation_id G04 inválido")
        _validate_relative_locator(self.parquet_locator)
        if f"operation_id={self.operation_id}/" not in self.parquet_locator:
            raise ValueError("locator G04 diverge do operation_id")
        if not self.parquet_schema:
            raise ValueError("schema G04 vazio")
        return self


class BudgetConfig(StrictModel):
    display_name: str
    currency_code: Literal["BRL"]
    amount: int = Field(gt=0)
    reference_ceiling_usd: int = Field(gt=0)
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
    source_prefix: str
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
        _validate_relative_locator(self.source_prefix)
        categories = [item.category for item in self.sentinel]
        if sorted(categories) != ["metadata", "monthly_text", "transcription_queue"]:
            raise ValueError("sentinela deve conter exatamente as três categorias G01")
        if len({item.source_locator for item in self.sentinel}) != len(self.sentinel):
            raise ValueError("locator de origem duplicado no sentinela")
        if len({item.destination_locator for item in self.sentinel}) != len(self.sentinel):
            raise ValueError("locator de destino duplicado no sentinela")
        return self


class GcpContract(StrictModel):
    schema_version: Literal[6]
    project_id: str
    project_number: str
    region: str
    state: StateConfig
    data: DataConfig
    migrator: MigratorConfig
    pipeline: PipelineConfig
    marimo: MarimoConfig
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
            "migration.source_prefix": (
                self.migration.source_prefix,
                EXPECTED_SOURCE_PREFIX,
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
            "migrator.service_account_id": (
                self.migrator.service_account_id,
                "fn-migrator",
            ),
            "pipeline.service_account_id": (
                self.pipeline.service_account_id,
                "fn-pipeline",
            ),
            "pipeline.artifact_repository_id": (
                self.pipeline.artifact_repository_id,
                "falando-nela",
            ),
            "pipeline.image_name": (self.pipeline.image_name, "parquet-pilot"),
            "pipeline.job_name": (self.pipeline.job_name, "fn-parquet-pilot"),
            "pipeline.selection_manifest_sha256": (
                self.pipeline.selection_manifest_sha256,
                EXPECTED_G03_SELECTION_SHA256,
            ),
            "pipeline.task_count": (self.pipeline.task_count, 1),
            "pipeline.parallelism": (self.pipeline.parallelism, 1),
            "pipeline.max_retries": (self.pipeline.max_retries, 0),
            "pipeline.cpu": (self.pipeline.cpu, "1"),
            "pipeline.memory": (self.pipeline.memory, "1Gi"),
            "pipeline.timeout_seconds": (self.pipeline.timeout_seconds, 600),
            "pipeline.max_cost_usd": (self.pipeline.max_cost_usd, Decimal("0.10")),
            "marimo.operation_id": (self.marimo.operation_id, "g03-pilot-20260812-t120"),
            "marimo.parquet_locator": (
                self.marimo.parquet_locator,
                "data/processed/v1/g03/senado/plenario_discursos/ano=2010/"
                "operation_id=g03-pilot-20260812-t120/part-00000.parquet",
            ),
            "marimo.parquet_schema": (
                self.marimo.parquet_schema,
                "g03-senado-plenario-discursos-v1",
            ),
            "marimo.expected_records": (self.marimo.expected_records, 30),
            "budget.display_name": (self.budget.display_name, "falando-nela-gcp-first"),
            "budget.currency_code": (self.budget.currency_code, "BRL"),
            "budget.amount": (self.budget.amount, 25),
            "budget.reference_ceiling_usd": (self.budget.reference_ceiling_usd, 5),
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

    @property
    def pipeline_email(self) -> str:
        return f"{self.pipeline.service_account_id}@{self.project_id}.iam.gserviceaccount.com"

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

    def confirm_pipeline_targets(
        self,
        *,
        project_id: str,
        region: str,
        bucket: str,
        authoritative_raw: str,
    ) -> None:
        if project_id != self.project_id:
            raise GcpConfigError("confirmação literal do project ID diverge")
        if region != self.region:
            raise GcpConfigError("confirmação literal da região diverge")
        if bucket != self.data.bucket:
            raise GcpConfigError("confirmação literal do bucket diverge")
        if authoritative_raw != "gcs" or self.migration.authoritative_raw != "gcs":
            raise GcpConfigError("GCS ainda não foi confirmado como autoridade raw")


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
