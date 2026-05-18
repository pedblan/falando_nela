from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, format_senado_date, month_windows
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary, listify

SOURCE = "senado"
DATASET = "ccj_notas"
CCJ_SIGLA = "CCJ"
CCJ_CODIGO = "34"
BASE_URL = "https://legis.senado.leg.br/"


def collect() -> None:
    parser = build_parser("Coleta agenda, detalhes e notas taquigraficas da CCJ do Senado.")
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
                    endpoint = (
                        "dadosabertos/comissao/agenda/"
                        f"{format_senado_date(start)}/{format_senado_date(end)}.json"
                    )
                    params = {"v": 2}

                    run.log("partition_started", partition=partition, periodo=periodo)
                    agenda = client.get_json(endpoint, params=params)
                    run.write_record(
                        partition="metadata",
                        source_id=f"agenda:{format_senado_date(start)}:{format_senado_date(end)}",
                        request={"method": "GET", "path": endpoint, "params": params},
                        response=agenda.response_metadata,
                        periodo=periodo,
                        payload=agenda.data,
                        record_type="agenda_periodo",
                    )

                    ccj_reunioes = _ccj_reunioes(agenda.data)
                    for reuniao in ccj_reunioes:
                        codigo = _codigo_reuniao(reuniao)
                        if not codigo:
                            run.log("meeting_without_code", partition=partition, reuniao=reuniao)
                            continue
                        try:
                            _collect_reuniao(client, run, partition, periodo, codigo)
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("meeting_failed", partition=partition, codigo_reuniao=codigo, error=error_summary(exc))
                            continue

                    run.mark_partition_complete(partition, periodo=periodo, reunioes_ccj=len(ccj_reunioes))
                    run.log("partition_completed", partition=partition, reunioes_ccj=len(ccj_reunioes))
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
            ccj_codigo=CCJ_CODIGO,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_reuniao(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    codigo: str,
) -> None:
    detail_endpoint = f"dadosabertos/comissao/reuniao/{codigo}.json"
    notes_endpoint = f"dadosabertos/taquigrafia/notas/reuniao/{codigo}.json"

    for record_type, endpoint, params in [
        ("reuniao_detalhe", detail_endpoint, {"v": 2}),
        ("notas_taquigraficas", notes_endpoint, {"v": 1}),
    ]:
        source_id = f"reuniao:{codigo}:{record_type}"
        if run.has_record(source_id=source_id, record_type=record_type):
            run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
            continue
        try:
            result = client.get_json(endpoint, params=params)
        except httpx.HTTPStatusError as exc:
            run.log(
                "meeting_request_failed",
                codigo_reuniao=codigo,
                record_type=record_type,
                status_code=exc.response.status_code,
                url=str(exc.request.url),
            )
            continue

        run.write_record(
            partition=partition if record_type == "notas_taquigraficas" else "metadata",
            source_id=source_id,
            request={"method": "GET", "path": endpoint, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type=record_type,
        )


def _ccj_reunioes(payload: Any) -> list[dict[str, Any]]:
    agenda = _get(payload, "AgendaReuniao") or {}
    reunioes = _get(agenda, "reunioes", "Reunioes") or {}
    items = listify(_get(reunioes, "reuniao", "Reuniao"))
    return [item for item in items if isinstance(item, dict) and _is_ccj(item)]


def _is_ccj(reuniao: dict[str, Any]) -> bool:
    colegiado = _get(reuniao, "colegiadoCriador", "Colegiado", "colegiado") or {}
    sigla = _get(colegiado, "sigla", "Sigla")
    codigo = _get(colegiado, "codigo", "Codigo")
    return sigla == CCJ_SIGLA or str(codigo) == CCJ_CODIGO


def _codigo_reuniao(reuniao: dict[str, Any]) -> str | None:
    codigo = _get(reuniao, "codigo", "Codigo", "codigoReuniao", "CodigoReuniao")
    return str(codigo) if codigo is not None else None


def _get(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


if __name__ == "__main__":
    collect()
