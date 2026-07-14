from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .apartes import run_interjection_analysis
from .clusterizacao import run_clustering
from .descritivas import run_descriptives
from .figuras import prepare_figures_stage
from .genero import run_gender_enrichment_setup
from .inferencia import run_temporal_inference
from .nlp import run_nlp_analysis
from .sintese import run_synthesis
from .snapshot import run_snapshot
from .topicos import run_topic_modeling


STAGES = {
    "snapshot": run_snapshot,
    "genero": run_gender_enrichment_setup,
    "descritivas": run_descriptives,
    "apartes": run_interjection_analysis,
    "nlp": run_nlp_analysis,
    "inferencia": run_temporal_inference,
    "clusterizacao": run_clustering,
    "topicos": run_topic_modeling,
    "figuras-setup": prepare_figures_stage,
    "sintese": run_synthesis,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa uma etapa da suite analitica de discursos em plenario.")
    parser.add_argument("stage", choices=sorted(STAGES))
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", dest="config_path", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    kwargs = {"data_root": Path(args.data_root), "run_id": args.run_id, "config_path": args.config_path}
    if args.stage in {"snapshot", "genero"}:
        kwargs["overwrite"] = args.overwrite
    if args.stage == "nlp" and args.limit is not None:
        kwargs["limit"] = args.limit
    if args.stage == "figuras-setup" and args.limit is not None:
        kwargs["sample_limit"] = args.limit
    result = STAGES[args.stage](**kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
