from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.senado.discursos import (
    build_fontes,
    build_pronunciamento_payload,
    collect_discursos,
    extract_pronunciamentos,
    extract_text_from_nested_payload,
    fetch_pronunciamento_texto,
    fetch_sessao_texto,
    payload_response,
    should_enqueue_transcription,
)

DATASET = "plenario_discursos"
SIGLA_CASA = "SF"


def collect(argv: Sequence[str] | None = None) -> Path:
    return collect_discursos(
        dataset=DATASET,
        sigla_casa=SIGLA_CASA,
        description="Coleta discursos do Plenario do Senado Federal.",
        argv=argv,
    )


if __name__ == "__main__":
    collect()
