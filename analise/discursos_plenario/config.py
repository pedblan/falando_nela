from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.v1.json")


@dataclass(frozen=True)
class AnalysisConfig:
    """Validated, serializable configuration for the plenary analysis suite."""

    raw: dict[str, Any]
    path: Path

    @property
    def date_start(self) -> str:
        return str(self.raw["date_start"])

    @property
    def date_end(self) -> str:
        return str(self.raw["date_end"])

    @property
    def seed(self) -> int:
        return int(self.raw["random_seed"])

    @property
    def output_relative_path(self) -> Path:
        return Path(self.raw["paths"]["output_root"])

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.raw))


def load_config(path: str | Path | None = None) -> AnalysisConfig:
    resolved = Path(path).expanduser().resolve() if path else DEFAULT_CONFIG_PATH.resolve()
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    validate_config(raw)
    return AnalysisConfig(raw=raw, path=resolved)


def validate_config(config: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "analysis_version",
        "date_start",
        "date_end",
        "complete_year_start",
        "complete_year_end",
        "ytd_year",
        "random_seed",
        "bootstrap_repetitions",
        "paths",
        "arenas",
        "eligibility",
        "clustering",
        "openai",
        "rhetorical_figures",
        "interjection_speech_acts",
        "response_speech_acts",
    }
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Configuracao incompleta: {sorted(missing)}")
    if config["date_start"] > config["date_end"]:
        raise ValueError("date_start deve ser anterior ou igual a date_end")
    if int(config["complete_year_end"]) >= int(config["ytd_year"]):
        raise ValueError("O ano YTD nao pode integrar a faixa de anos completos")
    if int(config["bootstrap_repetitions"]) <= 0:
        raise ValueError("bootstrap_repetitions deve ser positivo")
    if set(config["arenas"]) != {"camara", "senado", "congresso"}:
        raise ValueError("As arenas devem ser camara, senado e congresso")
    if len(config["rhetorical_figures"]) != 14:
        raise ValueError("A ontologia deve conter exatamente 14 figuras")
    if len(config["interjection_speech_acts"]) != 10:
        raise ValueError("A ontologia de atos de aparte deve conter exatamente 10 categorias")
    if len(config["response_speech_acts"]) != 9:
        raise ValueError("A ontologia de respostas deve conter exatamente 9 categorias")


def resolve_input_paths(config: AnalysisConfig, data_root: str | Path) -> dict[str, Path]:
    root = Path(data_root).expanduser()
    paths = {arena: root / spec["path"] for arena, spec in config.raw["arenas"].items()}
    paths["parliamentarian_periods"] = root / config.raw["paths"]["parliamentarian_periods"]
    paths["interjections"] = root / config.raw["paths"]["interjections"]
    return paths


def resolve_output_root(config: AnalysisConfig, data_root: str | Path, run_id: str) -> Path:
    if not run_id or "/" in run_id or "\\" in run_id:
        raise ValueError("run_id deve ser um identificador simples e nao vazio")
    return Path(data_root).expanduser() / config.output_relative_path / run_id
