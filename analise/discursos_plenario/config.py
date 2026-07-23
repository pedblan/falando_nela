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
        "interjection_segmentation",
        "interjection_episode_linking_v2",
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
    coverage_years = config.get("coverage_required_years")
    if coverage_years is not None:
        if not isinstance(coverage_years, Mapping) or set(coverage_years) != set(config["arenas"]):
            raise ValueError(
                "coverage_required_years deve mapear exatamente camara, senado e congresso"
            )
        for arena, years in coverage_years.items():
            if not isinstance(years, list) or not years:
                raise ValueError(f"coverage_required_years[{arena}] deve ser uma lista não vazia")
            if any(isinstance(year, bool) or not isinstance(year, int) for year in years):
                raise ValueError(f"coverage_required_years[{arena}] deve conter apenas anos inteiros")
            if len(set(years)) != len(years):
                raise ValueError(f"coverage_required_years[{arena}] não pode repetir anos")
    if len(config["rhetorical_figures"]) != 14:
        raise ValueError("A ontologia deve conter exatamente 14 figuras")
    if len(config["interjection_speech_acts"]) != 10:
        raise ValueError("A ontologia de atos de aparte deve conter exatamente 10 categorias")
    if len(config["response_speech_acts"]) != 9:
        raise ValueError("A ontologia de respostas deve conter exatamente 9 categorias")
    segmentation = config["interjection_segmentation"]
    segmentation_required = {
        "method",
        "prompt_version",
        "block_max_chars",
        "review_sample_size",
        "min_reviewed",
        "min_precision",
    }
    if missing_segmentation := segmentation_required.difference(segmentation):
        raise ValueError(f"Configuracao de segmentacao incompleta: {sorted(missing_segmentation)}")
    if segmentation["method"] != "ia_blocos_offsets_v1":
        raise ValueError("Metodo de segmentacao nao suportado")
    if int(segmentation["block_max_chars"]) < 80:
        raise ValueError("block_max_chars deve ser pelo menos 80")
    if int(segmentation["review_sample_size"]) < int(segmentation["min_reviewed"]):
        raise ValueError("review_sample_size deve ser maior ou igual a min_reviewed")
    if not 0 < float(segmentation["min_precision"]) <= 1:
        raise ValueError("min_precision deve estar em (0, 1]")
    if not str(config["openai"].get("interjection_segmentation_model") or "").strip():
        raise ValueError("interjection_segmentation_model deve ser informado")
    episodes = config["interjection_episode_linking_v2"]
    episode_required = {
        "method",
        "prompt_version",
        "subturn_max_chars",
        "review_sample_size",
        "min_reviewed",
        "min_precision",
        "required_diagnostic_cases",
    }
    if missing_episodes := episode_required.difference(episodes):
        raise ValueError(
            f"Configuracao de episodios v2 incompleta: {sorted(missing_episodes)}"
        )
    if episodes["method"] != "ia_turnos_subturnos_v2":
        raise ValueError("Metodo de episodios v2 nao suportado")
    if int(episodes["subturn_max_chars"]) < 80:
        raise ValueError("subturn_max_chars deve ser pelo menos 80")
    if int(episodes["review_sample_size"]) < int(episodes["min_reviewed"]):
        raise ValueError(
            "review_sample_size v2 deve ser maior ou igual a min_reviewed"
        )
    if not 0 < float(episodes["min_precision"]) <= 1:
        raise ValueError("min_precision v2 deve estar em (0, 1]")
    diagnostics = episodes["required_diagnostic_cases"]
    if not isinstance(diagnostics, list) or len(diagnostics) != 3:
        raise ValueError(
            "required_diagnostic_cases deve listar os tres casos v2"
        )
    if len(set(map(str, diagnostics))) != len(diagnostics):
        raise ValueError("required_diagnostic_cases nao pode repetir casos")


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
