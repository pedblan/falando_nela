from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary

SOURCE = "camara"
DATASET = "ccjc_eventos"
CCJC_ORGAO_ID = 2003
BASE_URL = "https://dadosabertos.camara.leg.br/"


def collect() -> None:
    parser = build_parser("Coleta eventos, participantes e metadados da CCJC da Camara.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    status = "completed"
    errors = 0

    try:
        with OpenDataClient(BASE_URL) as client:
            for partition, start, end in windows:
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    run.log("partition_started", partition=partition, periodo=periodo)
                    event_ids = _collect_event_pages(client, run, partition, periodo, sample=runtime.sample)
                    for event_id in event_ids:
                        try:
                            _collect_event_detail(client, run, partition, periodo, event_id)
                            _collect_event_deputados(client, run, partition, periodo, event_id)
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("event_failed", event_id=event_id, error=error_summary(exc))
                            continue

                    run.mark_partition_complete(partition, periodo=periodo, eventos=len(event_ids))
                    run.log("partition_completed", partition=partition, eventos=len(event_ids))
                except Exception as exc:
                    errors += 1
                    status = "completed_with_errors"
                    run.mark_partition_failed(partition, periodo=periodo, error=error_summary(exc, include_traceback=True))
                    run.log("partition_failed", partition=partition, error=error_summary(exc))
                    continue
    except Exception as exc:
        errors += 1
        status = "failed"
        run.log("run_failed", error=error_summary(exc, include_traceback=True))
    finally:
        run.write_manifest(
            data_inicio=runtime.data_inicio.isoformat(),
            data_fim=runtime.data_fim.isoformat(),
            mode=runtime.mode,
            sample=runtime.sample,
            ccjc_orgao_id=CCJC_ORGAO_ID,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_event_pages(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    *,
    sample: bool,
) -> list[int]:
    path = f"api/v2/orgaos/{CCJC_ORGAO_ID}/eventos"
    params = {
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "dataHoraInicio",
    }
    event_ids: list[int] = []

    for page_index, result in enumerate(iter_camara_pages(client, path, params=params), start=1):
        run.write_record(
            partition="metadata",
            source_id=f"ccjc:eventos:{partition}:pagina:{page_index}",
            request={"method": "GET", "path": path, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type="eventos_page",
        )
        for event in _dados(result.data):
            event_id = event.get("id")
            if isinstance(event_id, int) and event_id not in event_ids:
                event_ids.append(event_id)
        if sample and len(event_ids) >= 3:
            return event_ids[:3]
    return event_ids


def _collect_event_detail(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    event_id: int,
    ) -> None:
    path = f"api/v2/eventos/{event_id}"
    source_id = f"ccjc:evento:{event_id}:detalhe"
    if run.has_record(source_id=source_id, record_type="evento_detalhe"):
        run.log("record_resume_skipped", source_id=source_id, record_type="evento_detalhe")
        return
    try:
        result = client.get_json(path)
    except httpx.HTTPStatusError as exc:
        run.log("event_detail_failed", event_id=event_id, status_code=exc.response.status_code)
        return

    run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": path, "params": {}},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type="evento_detalhe",
    )


def _collect_event_deputados(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    event_id: int,
) -> None:
    path = f"api/v2/eventos/{event_id}/deputados"
    try:
        pages = iter_camara_pages(client, path)
        for page_index, result in enumerate(pages, start=1):
            source_id = f"ccjc:evento:{event_id}:deputados:pagina:{page_index}"
            run.write_record(
                partition="metadata",
                source_id=source_id,
                request={"method": "GET", "path": path, "params": {}},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="evento_deputados_page",
            )
    except httpx.HTTPStatusError as exc:
        run.log("event_deputies_failed", event_id=event_id, status_code=exc.response.status_code)
        return


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


if __name__ == "__main__":
    collect()
