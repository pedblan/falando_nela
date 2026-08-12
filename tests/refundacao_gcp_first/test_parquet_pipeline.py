from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
import pytest

from falando_nela.cli import build_parser
from falando_nela.operations import OperationError
from falando_nela.parquet_pipeline import (
    LocalObjectStore,
    MetadataServerTokenProvider,
    ParquetPilotConfig,
    ParquetPipelineError,
    execute_parquet_pilot,
    load_selection_manifest,
)
from falando_nela.raw import canonical_json_bytes, sha256_bytes, sha256_file

REPO_ROOT = Path(__file__).parents[2]
PRODUCTION_SELECTION = REPO_ROOT / "specs/refundacao_gcp_first/g03_parquet_cloud_run/selection.json"


class CountingStore(LocalObjectStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.reads = 0
        self.publish_calls = 0
        self.creates = 0

    def read_bytes(self, locator: str) -> bytes | None:
        self.reads += 1
        return super().read_bytes(locator)

    def publish_bytes_create_only(
        self, locator: str, content: bytes, *, content_type: str
    ) -> dict[str, Any]:
        self.publish_calls += 1
        existed = self.read_bytes(locator) is not None
        result = super().publish_bytes_create_only(locator, content, content_type=content_type)
        if not existed:
            self.creates += 1
        return result


def _record(index: int) -> dict[str, Any]:
    speech_id = 380_000 + index
    date = f"2010-0{index + 1}-0{index + 1}"
    text = f"Pronunciamento de teste {index}."
    return {
        "checksum": sha256_bytes(text.encode()),
        "collected_at": "2026-05-29T03:13:54+00:00",
        "dataset": "plenario_discursos",
        "partition": date[:7],
        "payload": {
            "codigo_pronunciamento": str(speech_id),
            "metadata": {
                "pronunciamento": {
                    "CodigoPronunciamento": str(speech_id),
                    "Data": date,
                    "FuncaoAutor": "SENADOR",
                    "NomeAutor": f"Pessoa {index}",
                    "Partido": "ABC",
                    "TipoAutor": "Senador(a)",
                    "TipoUsoPalavra": {
                        "Codigo": "1",
                        "Descricao": "Discurso",
                        "IndicadorAtivo": "Sim",
                    },
                    "UF": "DF",
                },
                "sessao": {
                    "CodigoSessao": str(20_000 + index),
                    "CodigoSessaoLegislativa": "843",
                    "DataSessao": date,
                    "TipoSessao": "NDL",
                },
            },
            "metodo_obtencao": "fixture",
            "texto": text,
            "texto_status": "disponivel",
        },
        "periodo": {"data_inicio": date, "data_fim": date},
        "record_type": "pronunciamento_texto",
        "run_id": "g03-fixture",
        "source": "senado",
        "source_id": f"SF:pronunciamento:{speech_id}",
    }


def _fixture(tmp_path: Path, *, records: int = 3) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    values = [_record(index) for index in range(records)]
    lines = [canonical_json_bytes(value) for value in values]
    jsonl = b"".join(line + b"\n" for line in lines)
    jsonl_path = tmp_path / "fixture.jsonl"
    gzip_path = tmp_path / "fixture.jsonl.gz"
    jsonl_path.write_bytes(jsonl)
    gzip_path.write_bytes(gzip.compress(jsonl, compresslevel=9, mtime=0))
    locator = "data/raw/v1/senado/plenario_discursos/ano=2010/mes=01/fixture.jsonl"
    selected = []
    for line_number, (value, line) in enumerate(zip(values, lines, strict=True), start=1):
        identity = {
            "dataset": value["dataset"],
            "record_type": value["record_type"],
            "source": value["source"],
            "source_id": value["source_id"],
            "substantive_year": 2010,
        }
        selected.append(
            {
                "identity": canonical_json_bytes(identity).decode(),
                "line_number": line_number,
                "source_locator": locator,
                "raw_bytes": len(line),
                "raw_sha256": sha256_bytes(line),
            }
        )
    selection_path = tmp_path / "selection.json"
    selection_path.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": 1,
                "sample_id": "g03-fixture",
                "label": "fixture",
                "input": {
                    "stored_object_sha256": sha256_file(gzip_path),
                    "uncompressed_sha256": sha256_bytes(jsonl),
                    "records": records,
                },
                "selected": selected,
            }
        )
        + b"\n"
    )
    source_root = tmp_path / "source"
    source_path = source_root / locator
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(jsonl)
    return {
        "jsonl": jsonl_path,
        "gzip": gzip_path,
        "selection": selection_path,
        "source_root": source_root,
    }


def _config() -> ParquetPilotConfig:
    return ParquetPilotConfig(
        project_id="falando-nela-pedblan",
        region="southamerica-east1",
        bucket="falando-nela-pedblan-data",
        processed_prefix="data/processed/v1",
        manifests_prefix="manifests",
    )


def _execute(
    tmp_path: Path,
    fixture: dict[str, Path],
    *,
    operation_id: str,
    local_input: Path | None = None,
    source_store: LocalObjectStore | None = None,
    publish_store: LocalObjectStore | None = None,
    through: str = "publish",
    failure_injector=None,
) -> dict[str, Any]:
    return execute_parquet_pilot(
        operation_id=operation_id,
        implementation_revision="test-revision",
        selection_manifest_path=fixture["selection"],
        operation_root=tmp_path / "operations" / operation_id,
        publish_store=publish_store or CountingStore(tmp_path / "published"),
        config=_config(),
        source_store=source_store,
        local_input_path=local_input,
        through=through,  # type: ignore[arg-type]
        failure_injector=failure_injector,
    )


def test_production_selection_freezes_30_unique_records_and_config_hash() -> None:
    selection = load_selection_manifest(PRODUCTION_SELECTION)

    assert len(selection.entries) == 30
    assert len({entry.identity for entry in selection.entries}) == 30
    assert len({entry.raw_sha256 for entry in selection.entries}) == 30
    assert (
        selection.file_sha256 == "8e6d879159078db7f6549a5997aded0ae29d2dda1311609b0353493f9525a1dc"
    )
    assert selection.uncompressed_sha256 == (
        "1f887cd8363fce4aeb4e5ceb7d704be50a363af921beecddbda2cf75005ac484"
    )


@pytest.mark.parametrize("suffix", ("jsonl", "gzip"))
def test_local_jsonl_and_gzip_produce_deterministic_parquet(tmp_path: Path, suffix: str) -> None:
    fixture = _fixture(tmp_path / suffix)
    first = _execute(
        tmp_path / suffix,
        fixture,
        operation_id="g03-first",
        local_input=fixture[suffix],
        through="validate",
    )
    second = _execute(
        tmp_path / suffix,
        fixture,
        operation_id="g03-second",
        local_input=fixture[suffix],
        through="validate",
    )

    assert first["records"] == 3
    assert first["parquet_sha256"] == second["parquet_sha256"]
    assert first["logical_sha256"] == second["logical_sha256"]
    parquet = pq.ParquetFile(first["parquet_path"])
    assert parquet.metadata.format_version == "2.6"
    assert parquet.metadata.num_rows == 3
    assert parquet.metadata.num_row_groups == 1
    compressions = {
        parquet.metadata.row_group(0).column(column).compression
        for column in range(parquet.metadata.num_columns)
    }
    assert compressions == {"ZSTD"}
    assert parquet.schema_arrow.names[:5] == [
        "source",
        "dataset",
        "record_type",
        "source_id",
        "raw_sha256",
    ]
    required = {"source", "dataset", "record_type", "source_id", "raw_sha256"}
    required.update({"text_sha256", "text_bytes"})
    assert all(not parquet.schema_arrow.field(name).nullable for name in required)
    assert all(
        parquet.schema_arrow.field(name).nullable
        for name in set(parquet.schema_arrow.names) - required
    )
    assert str(parquet.schema_arrow.field("text_bytes").type) == "int64"


def test_store_materialization_matches_direct_input(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    local = _execute(
        tmp_path,
        fixture,
        operation_id="g03-local",
        local_input=fixture["gzip"],
        through="validate",
    )
    gcs_simulated = _execute(
        tmp_path,
        fixture,
        operation_id="g03-gcs",
        source_store=CountingStore(fixture["source_root"]),
        through="validate",
    )

    assert local["parquet_sha256"] == gcs_simulated["parquet_sha256"]
    assert local["logical_sha256"] == gcs_simulated["logical_sha256"]


def test_invalid_format_json_and_raw_hash_are_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    invalid_extension = tmp_path / "fixture.txt"
    invalid_extension.write_bytes(fixture["jsonl"].read_bytes())
    with pytest.raises(ParquetPipelineError, match=".jsonl"):
        _execute(
            tmp_path,
            fixture,
            operation_id="g03-extension",
            local_input=invalid_extension,
        )

    invalid_json = tmp_path / "invalid.jsonl"
    invalid_json.write_text("{invalid}\n", encoding="utf-8")
    with pytest.raises(ParquetPipelineError, match="JSON inválido"):
        _execute(
            tmp_path,
            fixture,
            operation_id="g03-json",
            local_input=invalid_json,
        )

    source_path = next(fixture["source_root"].rglob("*.jsonl"))
    source_path.write_bytes(source_path.read_bytes().replace(b"teste 1", b"alterado"))
    publish_store = CountingStore(tmp_path / "published-invalid")
    with pytest.raises(ParquetPipelineError, match="bytes raw divergiram"):
        _execute(
            tmp_path,
            fixture,
            operation_id="g03-hash",
            source_store=LocalObjectStore(fixture["source_root"]),
            publish_store=publish_store,
        )
    assert publish_store.publish_calls == 0


def test_locator_line_and_identity_divergence_are_rejected(tmp_path: Path) -> None:
    unsafe = _fixture(tmp_path / "unsafe")
    payload = json.loads(unsafe["selection"].read_text(encoding="utf-8"))
    payload["selected"][0]["source_locator"] = "../escape.jsonl"
    unsafe["selection"].write_bytes(canonical_json_bytes(payload) + b"\n")
    with pytest.raises(ParquetPipelineError, match="locator inseguro"):
        load_selection_manifest(unsafe["selection"])

    missing_line = _fixture(tmp_path / "line")
    payload = json.loads(missing_line["selection"].read_text(encoding="utf-8"))
    payload["selected"][0]["line_number"] = 999
    missing_line["selection"].write_bytes(canonical_json_bytes(payload) + b"\n")
    with pytest.raises(ParquetPipelineError, match="linha raw ausente"):
        _execute(
            tmp_path / "line",
            missing_line,
            operation_id="g03-line",
            source_store=LocalObjectStore(missing_line["source_root"]),
        )

    changed_identity = _fixture(tmp_path / "identity")
    payload = json.loads(changed_identity["selection"].read_text(encoding="utf-8"))
    identity = json.loads(payload["selected"][0]["identity"])
    identity["source_id"] = "SF:pronunciamento:999999"
    payload["selected"][0]["identity"] = canonical_json_bytes(identity).decode()
    changed_identity["selection"].write_bytes(canonical_json_bytes(payload) + b"\n")
    with pytest.raises(ParquetPipelineError, match="identidade raw divergiu"):
        _execute(
            tmp_path / "identity",
            changed_identity,
            operation_id="g03-identity-mismatch",
            source_store=LocalObjectStore(changed_identity["source_root"]),
        )


def test_publish_is_create_only_and_completed_resume_does_not_rewrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = CountingStore(tmp_path / "published")
    first = _execute(
        tmp_path,
        fixture,
        operation_id="g03-resume",
        local_input=fixture["gzip"],
        publish_store=store,
    )
    creates_after_first = store.creates
    second = _execute(
        tmp_path,
        fixture,
        operation_id="g03-resume",
        local_input=fixture["gzip"],
        publish_store=store,
    )

    assert first["executed_stages"] == [
        "materialize_input",
        "write_parquet",
        "validate",
        "publish",
    ]
    assert second["executed_stages"] == []
    assert second["reused_stages"] == [
        "materialize_input",
        "write_parquet",
        "validate",
        "publish",
    ]
    assert store.creates == creates_after_first == 2


def test_interruption_after_first_remote_effect_reconciles_without_replacement(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    store = CountingStore(tmp_path / "published")

    def interrupt(boundary: str) -> None:
        if boundary == "publish:after_parquet":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _execute(
            tmp_path,
            fixture,
            operation_id="g03-interrupted",
            local_input=fixture["gzip"],
            publish_store=store,
            failure_injector=interrupt,
        )
    assert store.creates == 1

    resumed = _execute(
        tmp_path,
        fixture,
        operation_id="g03-interrupted",
        local_input=fixture["gzip"],
        publish_store=store,
    )

    assert resumed["status"] == "completed"
    assert store.creates == 2
    operation = json.loads((tmp_path / "operations/g03-interrupted/operation.json").read_text())
    publish = next(stage for stage in operation["stages"] if stage["id"] == "publish")
    assert publish["attempts"] == 1
    assert publish["status"] == "completed"


def test_same_operation_id_rejects_changed_input(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _execute(
        tmp_path,
        fixture,
        operation_id="g03-identity",
        local_input=fixture["jsonl"],
        through="validate",
    )
    fixture["jsonl"].write_bytes(fixture["jsonl"].read_bytes() + b"\n")

    with pytest.raises(OperationError, match="entrada ou configuração diferente"):
        _execute(
            tmp_path,
            fixture,
            operation_id="g03-identity",
            local_input=fixture["jsonl"],
            through="validate",
        )


def test_parquet_cli_defaults_to_local_validation_and_requires_explicit_gcs_targets() -> None:
    args = build_parser().parse_args(
        [
            "parquet-pilot",
            "--operation-id",
            "g03-cli",
            "--implementation-revision",
            "abc123",
        ]
    )

    assert args.backend == "local"
    assert args.through == "validate"
    assert args.confirm_project_id is None
    assert args.confirm_region is None
    assert args.confirm_bucket is None
    assert args.confirm_authoritative_raw is None


def test_metadata_token_provider_requires_google_header_and_caches_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["metadata-flavor"] == "Google"
        return httpx.Response(200, json={"access_token": "short-lived", "expires_in": 3600})

    provider = MetadataServerTokenProvider(http_transport=httpx.MockTransport(handler))

    assert provider() == "short-lived"
    assert provider() == "short-lived"
    assert len(requests) == 1
