from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.senado.discursos import collect_discursos

DATASET = "congresso_discursos"
SIGLA_CASA = "CN"


def collect(argv: Sequence[str] | None = None) -> Path:
    return collect_discursos(
        dataset=DATASET,
        sigla_casa=SIGLA_CASA,
        description="Coleta discursos do Plenario do Congresso Nacional.",
        argv=argv,
    )


if __name__ == "__main__":
    collect()
