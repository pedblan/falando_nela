"""Processamento da base apartes_parlamentares/v1."""

from .processor import APARTES_FIELDS, build_parser, main, process_apartes_data_root

__all__ = [
    "APARTES_FIELDS",
    "build_parser",
    "main",
    "process_apartes_data_root",
]
