from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from falando_nela.sampling import (
    PILOT_STRATUM,
    RecordContractError,
    exact_sample_size,
    record_identity,
    selection_key,
    substantive_year,
    validate_stratum,
)


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "source": "senado",
        "dataset": "plenario_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "123",
        "periodo": {"data_inicio": "2010-08-03"},
        "payload": {"texto": "não entra na identidade"},
    }
    record.update(overrides)
    return record


def test_pilot_stratum_uses_literal_raw_record_type() -> None:
    assert PILOT_STRATUM.record_type == "pronunciamento_texto"
    assert validate_stratum(_record(), PILOT_STRATUM) == record_identity(_record())


def test_identity_is_canonical_and_does_not_include_payload() -> None:
    first = _record(payload={"texto": "primeiro"})
    second = _record(payload={"texto": "segundo"})

    assert record_identity(first) == record_identity(second)
    assert record_identity(first) == (
        '{"dataset":"plenario_discursos","record_type":"pronunciamento_texto",'
        '"source":"senado","source_id":"123","substantive_year":2010}'
    )


def test_substantive_year_comes_from_period_start() -> None:
    assert substantive_year(_record(periodo={"data_inicio": "2010-12-31T23:59:59Z"})) == 2010


@pytest.mark.parametrize(
    "record",
    [
        _record(source_id=""),
        _record(periodo={}),
        _record(periodo={"data_inicio": "2010-99-99"}),
        _record(record_type="discurso"),
        _record(periodo={"data_inicio": "2011-01-01"}),
    ],
)
def test_invalid_identity_date_or_stratum_is_rejected(record: dict[str, object]) -> None:
    with pytest.raises(RecordContractError):
        validate_stratum(record, PILOT_STRATUM)


def test_selection_key_is_deterministic_and_seeded() -> None:
    identity = record_identity(_record())

    assert selection_key(identity, "seed-a") == selection_key(identity, "seed-a")
    assert selection_key(identity, "seed-a") != selection_key(identity, "seed-b")
    assert (
        selection_key(identity, "seed-a")
        == hashlib.sha256(b"seed-a\0" + identity.encode("utf-8")).hexdigest()
    )
    assert len(selection_key(identity, "seed-a")) == 64


@pytest.mark.parametrize(
    ("population", "expected"),
    [(0, 0), (1, 1), (99, 1), (100, 1), (101, 2), (2_996, 30)],
)
def test_exact_one_percent_uses_ceiling(population: int, expected: int) -> None:
    assert exact_sample_size(population) == expected


def test_sample_size_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        exact_sample_size(-1)
    with pytest.raises(ValueError):
        exact_sample_size(10, Decimal("0"))
    with pytest.raises(ValueError):
        exact_sample_size(10, Decimal("1.01"))
