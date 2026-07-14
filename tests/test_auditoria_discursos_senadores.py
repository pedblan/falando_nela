from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from coleta.common.http import HttpResult
from coleta.senado import auditoria_discursos_historicos as audit


def _source_item(code: str, *, house: str = "SF", year: int = 2010) -> dict[str, Any]:
    return {
        "codigo_pronunciamento": code,
        "parlamentar_id": "123",
        "data": f"{year}-03-10",
        "house": house,
        "pronunciamento": {
            "CodigoPronunciamento": code,
            "DataPronunciamento": f"{year}-03-10",
            "SiglaCasaPronunciamento": house,
        },
        "probe_key": f"{house}:{year}:123",
        "discovering_parlamentar_ids": ["123"],
    }


def test_extract_pronunciamentos_senador_uses_codes_and_preserves_diacritics() -> None:
    payload = {
        "DiscursosParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "CodigoParlamentar": "123",
                    "NomeParlamentar": "JOÃO DA CONCEIÇÃO",
                },
                "Pronunciamentos": {
                    "Pronunciamento": {
                        "CodigoPronunciamento": "456",
                        "DataPronunciamento": "2010-03-10",
                        "SiglaCasaPronunciamento": "SF",
                        "TextoResumo": "Discussão sobre educação e saúde.",
                    }
                },
            }
        }
    }

    items = audit.extract_pronunciamentos_senador(
        payload,
        parlamentar_id="123",
        requested_house="SF",
    )

    assert items == [
        {
            "codigo_pronunciamento": "456",
            "parlamentar_id": "123",
            "data": "2010-03-10",
            "house": "SF",
            "pronunciamento": payload["DiscursosParlamentar"]["Parlamentar"]["Pronunciamentos"][
                "Pronunciamento"
            ],
        }
    ]
    assert audit.extract_pronunciamento_codes(payload) == ["456"]


def test_scan_raw_pronunciamentos_indexes_code_and_official_year(tmp_path: Path) -> None:
    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "ano=2010"
        / "mes=03"
        / "run.jsonl"
    )
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(
        json.dumps(
            {
                "source": "senado",
                "dataset": "plenario_discursos",
                "record_type": "pronunciamento_texto",
                "payload": {
                    "CodigoPronunciamento": "456",
                    "metadata": {
                        "pronunciamento": {"DataPronunciamento": "2010-03-10"}
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metadata_path = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "metadata"
        / "run.jsonl"
    )
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        json.dumps(
            {
                "record_type": "pronunciamento_texto",
                "payload": {"CodigoPronunciamento": "nao-contar"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    inventory = audit.scan_raw_pronunciamentos(
        tmp_path,
        houses=("SF",),
        start=date(2010, 1, 1),
        end=date(2010, 12, 31),
    )

    assert inventory["all_by_house"]["SF"] == {"456"}
    assert inventory["by_house_year"][("SF", 2010)] == {"456"}
    assert inventory["years_by_house_code"]["SF"]["456"] == {2010}
    assert inventory["records_scanned"] == 1
    assert inventory["invalid_lines"] == 0


def test_build_coverage_lists_missing_ids_without_rejecting_raw_non_senators() -> None:
    source_inventory = {
        "by_house_year": {
            ("CN", 2010): {
                "100": _source_item("100", house="CN"),
                "101": _source_item("101", house="CN"),
            }
        },
        "all_by_house": {"CN": {"100", "101"}},
    }
    raw_inventory = {
        "all_by_house": {"CN": {"100", "999"}},
        "by_house_year": {("CN", 2010): {"100", "999"}},
        "years_by_house_code": {"CN": {"100": {2010}, "999": {2010}}},
        "files_scanned": 1,
        "records_scanned": 2,
        "invalid_lines": 0,
    }

    coverage, missing = audit.build_coverage(
        start=date(2010, 1, 1),
        end=date(2010, 12, 31),
        houses=("CN",),
        senator_ids_by_year={2010: ["123"]},
        source_inventory=source_inventory,
        raw_inventory=raw_inventory,
        probe_records=[],
        source_conflicts=[],
        invalid_probe_lines=0,
        compare_raw=True,
    )

    assert coverage[0]["source_ids"] == 2
    assert coverage[0]["source_ids_present_in_raw"] == 1
    assert coverage[0]["missing_ids"] == 1
    assert coverage[0]["raw_ids_not_in_senator_endpoint"] == 1
    assert coverage[0]["status"] == "incomplete"
    assert [record["codigo_pronunciamento"] for record in missing] == ["101"]


def test_build_coverage_marks_year_inconclusive_after_request_error() -> None:
    error_record = audit.probe_record(
        probe_key="SF:2010:20100101:20101231:123",
        probe_scope="speeches",
        request={"method": "GET", "path": "endpoint", "params": {}},
        response={"status": "error"},
        payload=None,
        error={"type": "TimeoutError", "message": "timeout"},
        house="SF",
        year=2010,
        parlamentar_id="123",
    )

    coverage, _ = audit.build_coverage(
        start=date(2010, 1, 1),
        end=date(2010, 12, 31),
        houses=("SF",),
        senator_ids_by_year={2010: ["123"]},
        source_inventory={"by_house_year": {}, "all_by_house": {"SF": set()}},
        raw_inventory=audit.empty_raw_inventory(("SF",)),
        probe_records=[error_record],
        source_conflicts=[],
        invalid_probe_lines=0,
        compare_raw=True,
    )

    assert coverage[0]["request_errors"] == 1
    assert coverage[0]["status"] == "inconclusive"


def test_load_probe_records_keeps_latest_retry_and_counts_invalid_line(tmp_path: Path) -> None:
    path = tmp_path / "probes.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"probe_key": "SF:2010:123", "error": {"type": "Timeout"}}),
                "{linha truncada",
                json.dumps({"probe_key": "SF:2010:123", "payload": {"ok": True}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records, invalid_lines = audit.load_probe_records(path)

    assert invalid_lines == 1
    assert records["SF:2010:123"]["payload"] == {"ok": True}


def test_audit_queries_speeches_by_codigo_parlamentar_not_name(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    requests: list[tuple[str, dict[str, Any] | None]] = []

    class FakeClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> HttpResult:
            requests.append((path, params))
            if "lista/legislatura" in path:
                return HttpResult(
                    "https://example.test/senadores",
                    200,
                    {},
                    {
                        "ListaParlamentarLegislatura": {
                            "Parlamentares": {
                                "Parlamentar": {
                                    "IdentificacaoParlamentar": {
                                        "CodigoParlamentar": "123",
                                        "NomeParlamentar": "JOÃO DA CONCEIÇÃO",
                                    }
                                }
                            }
                        }
                    },
                )
            assert path == "dadosabertos/senador/123/discursos"
            assert params == {
                "casa": "SF",
                "dataInicio": "20100101",
                "dataFim": "20101231",
                "v": 5,
            }
            return HttpResult(
                "https://example.test/discursos",
                200,
                {},
                {
                    "DiscursosParlamentar": {
                        "Pronunciamentos": {
                            "Pronunciamento": {
                                "CodigoPronunciamento": "456",
                                "DataPronunciamento": "2010-03-10",
                                "SiglaCasaPronunciamento": "SF",
                            }
                        }
                    }
                },
            )

    monkeypatch.setattr(audit, "OpenDataClient", FakeClient)
    cycle_dir = tmp_path / "audit"
    data_root = tmp_path / "data"
    summary = audit.audit_senator_endpoint(
        cycle_dir=cycle_dir,
        data_root=data_root,
        start=date(2010, 1, 1),
        end=date(2010, 12, 31),
        houses=("SF",),
        resume=True,
        strict=True,
    )

    with (cycle_dir / "senator_endpoint_coverage.csv").open(encoding="utf-8") as handle:
        coverage = list(csv.DictReader(handle))
    assert summary["missing_ids"] == 1
    assert coverage[0]["status"] == "incomplete"
    assert [path for path, _ in requests if "/discursos" in path] == [
        "dadosabertos/senador/123/discursos"
    ]
    assert all("JOÃO" not in path for path, _ in requests)

