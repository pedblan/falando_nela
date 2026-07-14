"""Analise comparativa dos discursos em plenario da Camara, Senado e Congresso."""

from .config import AnalysisConfig, load_config
from .snapshot import build_snapshot, run_snapshot

__all__ = ["AnalysisConfig", "build_snapshot", "load_config", "run_snapshot"]
