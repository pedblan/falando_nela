from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, format_senado_date, month_windows
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun

SOURCE = "senado"
DATASET = "congresso_discursos"
SIGLA_CASA = "CN"
BASE_URL = "https://legis.senado.leg.br/"


def collect() -> None:
    parser = build_parser("Coleta discursos do Plenario do Congresso Nacional.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)

    with OpenDataClient(BASE_URL) as client:
        for partition, start, end in windows:
            if run.should_skip_partition(partition):
                run.log("partition_skipped", partition=partition)
                continue

            endpoint = (
                "dadosabertos/plenario/lista/discursos/"
                f"{format_senado_date(start)}/{format_senado_date(end)}.json"
            )
            params = {"siglaCasa": SIGLA_CASA, "v": 4}
            periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}

            run.log("partition_started", partition=partition, periodo=periodo)
            result = client.get_json(endpoint, params=params)
            run.write_record(
                partition="metadata",
                source_id=f"{SIGLA_CASA}:{format_senado_date(start)}:{format_senado_date(end)}",
                request={"method": "GET", "path": endpoint, "params": params},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="discursos_periodo_metadata",
            )
            run.mark_partition_complete(partition, periodo=periodo)
            run.log("partition_completed", partition=partition)

    run.write_manifest(
        data_inicio=runtime.data_inicio.isoformat(),
        data_fim=runtime.data_fim.isoformat(),
        mode=runtime.mode,
        sample=runtime.sample,
    )
    print(run.manifest_path)


if __name__ == "__main__":
    collect()
