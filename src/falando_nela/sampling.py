from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Any

from falando_nela.raw import canonical_json_bytes


class RecordContractError(ValueError):
    """Registro raw não pertence ao contrato amostral informado."""


@dataclass(frozen=True)
class Stratum:
    source: str
    dataset: str
    record_type: str
    substantive_year: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "source": self.source,
            "dataset": self.dataset,
            "record_type": self.record_type,
            "substantive_year": self.substantive_year,
        }


PILOT_STRATUM = Stratum(
    source="senado",
    dataset="plenario_discursos",
    record_type="pronunciamento_texto",
    substantive_year=2010,
)


def record_identity(record: dict[str, Any]) -> str:
    identity: dict[str, str | int] = {}
    for field in ("source", "dataset", "record_type", "source_id"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RecordContractError(f"campo de identidade ausente ou inválido: {field}")
        identity[field] = value
    identity["substantive_year"] = substantive_year(record)
    return canonical_json_bytes(identity).decode("utf-8")


def substantive_year(record: dict[str, Any]) -> int:
    period = record.get("periodo")
    if not isinstance(period, dict):
        raise RecordContractError("periodo ausente ou inválido")
    value = period.get("data_inicio")
    if not isinstance(value, str) or len(value) < 10:
        raise RecordContractError("periodo.data_inicio ausente ou inválido")
    try:
        return date.fromisoformat(value[:10]).year
    except ValueError as exc:
        raise RecordContractError("periodo.data_inicio não é uma data ISO válida") from exc


def validate_stratum(record: dict[str, Any], stratum: Stratum) -> str:
    identity = record_identity(record)
    observed_year = substantive_year(record)
    expected = stratum.as_dict()
    observed = {
        "source": record["source"],
        "dataset": record["dataset"],
        "record_type": record["record_type"],
        "substantive_year": observed_year,
    }
    if observed != expected:
        raise RecordContractError(f"registro fora do estrato: {observed!r}")
    return identity


def selection_key(identity: str, seed: str) -> str:
    if not seed.strip():
        raise ValueError("sample_seed não pode ser vazio")
    payload = seed.encode("utf-8") + b"\0" + identity.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def exact_sample_size(population: int, rate: Decimal = Decimal("0.01")) -> int:
    if population < 0:
        raise ValueError("population não pode ser negativa")
    if not Decimal("0") < rate <= Decimal("1"):
        raise ValueError("sample_rate deve estar no intervalo (0, 1]")
    if population == 0:
        return 0
    return max(1, int((Decimal(population) * rate).to_integral_value(rounding=ROUND_CEILING)))
