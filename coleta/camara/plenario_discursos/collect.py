from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary

SOURCE = "camara"
DATASET = "plenario_discursos"
BASE_URL = "https://dadosabertos.camara.leg.br/"


def collect() -> None:
    parser = build_parser("Coleta discursos de deputados pela API de Dados Abertos da Camara.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_deputados = 0
    processed_discourse_pages = 0
    processed_discourses = 0
    processed_transcricoes = 0
    status = "completed"
    errors = 0

    try:
        with OpenDataClient(BASE_URL) as client:
            deputados = _collect_deputados(
                client,
                run,
                data_inicio=runtime.data_inicio.isoformat(),
                data_fim=runtime.data_fim.isoformat(),
                sample=runtime.sample,
            )
            run.log("deputies_loaded", total=len(deputados), sample=runtime.sample)

            for partition, start, end in windows:
                if runtime.sample_limit is not None and not runtime.sample and processed_deputados >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    run.log("partition_started", partition=partition, periodo=periodo, deputados=len(deputados))

                    for deputado in deputados:
                        if (
                            runtime.sample_limit is not None
                            and not runtime.sample
                            and processed_deputados >= runtime.sample_limit
                        ):
                            run.log(
                                "sample_limit_reached",
                                sample_limit=runtime.sample_limit,
                                processed_deputados=processed_deputados,
                            )
                            break

                        deputado_id = deputado.get("id")
                        if deputado_id is None:
                            continue
                        try:
                            stats = _collect_discursos_deputado(client, run, partition, periodo, int(deputado_id))
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("deputy_discourses_failed", deputado_id=deputado_id, error=error_summary(exc))
                            continue
                        processed_deputados += 1
                        processed_discourse_pages += stats["pages"]
                        processed_discourses += stats["discursos"]
                        processed_transcricoes += stats["transcricoes"]

                    run.mark_partition_complete(
                        partition,
                        periodo=periodo,
                        deputados=len(deputados),
                        deputados_processados=processed_deputados,
                        paginas_discursos=processed_discourse_pages,
                        discursos=processed_discourses,
                        discursos_com_transcricao=processed_transcricoes,
                    )
                    run.log(
                        "partition_completed",
                        partition=partition,
                        deputados=len(deputados),
                        deputados_processados=processed_deputados,
                        paginas_discursos=processed_discourse_pages,
                        discursos=processed_discourses,
                        discursos_com_transcricao=processed_transcricoes,
                    )
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
            sample_limit=runtime.sample_limit,
            deputados_processados=processed_deputados,
            paginas_discursos=processed_discourse_pages,
            discursos=processed_discourses,
            discursos_com_transcricao=processed_transcricoes,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_deputados(
    client: OpenDataClient,
    run: CollectionRun,
    *,
    data_inicio: str,
    data_fim: str,
    sample: bool,
) -> list[dict[str, Any]]:
    params = {
        "dataInicio": data_inicio,
        "dataFim": data_fim,
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "nome",
    }
    deputados: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for page_index, page in enumerate(iter_camara_pages(client, "api/v2/deputados", params=params), start=1):
        source_id = f"deputados:pagina:{page_index}"
        run.write_record(
            partition="metadata",
            source_id=source_id,
            request={"method": "GET", "path": "api/v2/deputados", "params": params},
            response=page.response_metadata,
            periodo={"data_inicio": "", "data_fim": ""},
            payload=page.data,
            record_type="deputados_page",
        )
        dados = page.data.get("dados", []) if isinstance(page.data, dict) else []
        for item in dados:
            if not isinstance(item, dict):
                continue
            deputado_id = item.get("id")
            if not isinstance(deputado_id, int) or deputado_id in seen_ids:
                continue
            deputados.append(item)
            seen_ids.add(deputado_id)
        if sample and len(deputados) >= 3:
            return deputados[:3]
    return deputados


def _collect_discursos_deputado(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    deputado_id: int,
) -> dict[str, int]:
    path = f"api/v2/deputados/{deputado_id}/discursos"
    params = {
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "dataHoraInicio",
    }
    stats = {"pages": 0, "discursos": 0, "transcricoes": 0}

    for page_index, result in enumerate(iter_camara_pages(client, path, params=params), start=1):
        source_id = f"deputado:{deputado_id}:discursos:{partition}:pagina:{page_index}"
        discursos = _dados(result.data)
        stats["pages"] += 1
        stats["discursos"] += len(discursos)
        stats["transcricoes"] += sum(1 for discurso in discursos if _has_text(discurso.get("transcricao")))
        run.write_record(
            partition=partition,
            source_id=source_id,
            request={"method": "GET", "path": path, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type="discursos_page",
        )
    return stats


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


if __name__ == "__main__":
    collect()
