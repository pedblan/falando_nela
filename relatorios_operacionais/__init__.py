"""Relatórios, manifests e logs operacionais do Falando Nela."""

from .core import (
    ArtifactRef,
    CountRow,
    ReportArtifact,
    append_log_event,
    build_manifest,
    render_report,
    validate_manifest,
    write_minimal_failure_record,
    write_operation_bundle,
)

__all__ = [
    "ArtifactRef",
    "CountRow",
    "ReportArtifact",
    "append_log_event",
    "build_manifest",
    "render_report",
    "validate_manifest",
    "write_minimal_failure_record",
    "write_operation_bundle",
]
