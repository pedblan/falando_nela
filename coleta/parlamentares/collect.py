from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from coleta.common.cli import build_parser, resolve_output_dir
from coleta.common.config import PROD_DATA_ROOT_ENV, parse_iso_date, utc_now_iso
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary, listify

DATASET = "parlamentares"
CAMARA_SOURCE = "camara"
SENADO_SOURCE = "senado"
CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/"
SENADO_BASE_URL = "https://legis.senado.leg.br/"


@dataclass(frozen=True)
class ParlamentaresRuntime:
    data_inicio: date
    data_fim: date
    mode: str
    output_dir: Path
    sample: bool
    sample_limit: int | None
    resume: bool
    run_id: str
    source: str
    ids_from_textos_only: bool
    skip_existing_id_scan: bool
    textos_root: Path | None


def collect(argv: Sequence[str] | None = None) -> None:
    runtime = parse_args(argv)
    selected_sources = [CAMARA_SOURCE, SENADO_SOURCE] if runtime.source == "all" else [runtime.source]
    runs: dict[str, CollectionRun] = {}
    stats_by_source: dict[str, dict[str, Any]] = {}
    total_errors = 0

    for source in selected_sources:
        run = CollectionRun(
            runtime.output_dir,
            source=source,
            dataset=DATASET,
            run_id=runtime.run_id,
            resume=runtime.resume,
        )
        runs[source] = run
        if run.should_skip_partition("metadata"):
            run.log("partition_skipped", partition="metadata")
            stats_by_source[source] = {"skipped": True}
            continue

        try:
            run.log(
                "source_started",
                partition="metadata",
                source_selected=source,
                periodo=_periodo(runtime),
                sample=runtime.sample,
                sample_limit=runtime.sample_limit,
            )
            if source == CAMARA_SOURCE:
                stats = collect_camara(run, runtime)
            else:
                stats = collect_senado(run, runtime)
            stats_by_source[source] = stats
            total_errors += int(stats.get("errors", 0) or 0)
            run.mark_partition_complete("metadata", periodo=_periodo(runtime), stats=stats)
        except Exception as exc:
            total_errors += 1
            stats_by_source[source] = {"errors": 1, "error": error_summary(exc)}
            run.mark_partition_failed(
                "metadata",
                periodo=_periodo(runtime),
                error=error_summary(exc, include_traceback=True),
            )
            run.log("partition_failed", partition="metadata", error=error_summary(exc))

    status = "completed" if total_errors == 0 else "completed_with_errors"
    manifest = write_combined_manifest(
        output_dir=runtime.output_dir,
        run_id=runtime.run_id,
        runs=runs,
        runtime=runtime,
        status=status,
        errors=total_errors,
        stats_by_source=stats_by_source,
    )
    print(manifest["manifest_path"])


def parse_args(argv: Sequence[str] | None = None) -> ParlamentaresRuntime:
    parser = build_parser("Coleta metadados de parlamentares da Camara e do Senado.")
    parser.add_argument("--source", choices=["camara", "senado", "all"], default="all")
    parser.add_argument(
        "--ids-from-textos-only",
        action="store_true",
        help="Baixa apenas parlamentares com parlamentar_id encontrado nos textos processados informados.",
    )
    parser.add_argument(
        "--skip-existing-id-scan",
        action="store_true",
        help=(
            "Nao varre raw/ e processed/textos_parlamentares/v1 para complementar IDs. "
            "Use quando a lista oficial por periodo for suficiente e a varredura do Drive estiver lenta."
        ),
    )
    parser.add_argument(
        "--textos-root",
        default=None,
        help="Raiz de textos processed/textos_parlamentares/v1 ou de seus Parquets. Default tenta samples locais em dev.",
    )
    args = parser.parse_args(argv)

    data_inicio = parse_iso_date(args.data_inicio)
    data_fim = parse_iso_date(args.data_fim)
    if data_inicio > data_fim:
        parser.error("--data-inicio nao pode ser posterior a --data-fim")

    sample = args.sample if args.sample is not None else args.mode == "dev"
    sample_limit = args.sample_limit
    if sample_limit is None and args.mode == "dev":
        sample_limit = 5
    if sample_limit is not None and sample_limit <= 0:
        parser.error("--sample-limit deve ser positivo")

    output_dir = resolve_output_dir(
        mode=args.mode,
        output_dir=args.output_dir,
        cwd=Path.cwd(),
        env=os.environ,
        parser=parser,
    )
    return ParlamentaresRuntime(
        data_inicio=data_inicio,
        data_fim=data_fim,
        mode=args.mode,
        output_dir=output_dir,
        sample=bool(sample),
        sample_limit=sample_limit,
        resume=bool(args.resume),
        run_id=args.run_id or f"parlamentares-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        source=args.source,
        ids_from_textos_only=bool(args.ids_from_textos_only),
        skip_existing_id_scan=bool(args.skip_existing_id_scan),
        textos_root=Path(args.textos_root).expanduser() if args.textos_root else None,
    )


def collect_camara(run: CollectionRun, runtime: ParlamentaresRuntime) -> dict[str, Any]:
    periodo = _periodo(runtime)
    stats: Counter[str] = Counter()
    if runtime.ids_from_textos_only:
        textos_root = resolve_textos_root(runtime)
        run.log("ids_textos_scan_started", textos_root=textos_root.as_posix())
        discovered_ids = discover_text_parlamentar_ids(textos_root, CAMARA_SOURCE)
        stats["ids_from_textos_only"] = 1
        stats["textos_root_exists"] = int(textos_root.exists())
        stats["textos_root"] = textos_root.as_posix()
        run.log("ids_textos_scan_completed", ids_descobertos=len(discovered_ids), textos_root=textos_root.as_posix())
    elif runtime.skip_existing_id_scan:
        discovered_ids = []
        stats["skip_existing_id_scan"] = 1
        run.log("ids_existing_scan_skipped", motivo="skip_existing_id_scan")
    else:
        run.log("ids_existing_scan_started", data_root=runtime.output_dir.as_posix())
        discovered_ids = _ordered_ids(discover_existing_parlamentar_ids(runtime.output_dir, CAMARA_SOURCE, run=run))
        run.log("ids_existing_scan_completed", ids_descobertos=len(discovered_ids))

    with OpenDataClient(CAMARA_BASE_URL) as client:
        if not runtime.ids_from_textos_only:
            params = {
                "dataInicio": runtime.data_inicio.isoformat(),
                "dataFim": runtime.data_fim.isoformat(),
                "itens": 100,
                "ordem": "ASC",
                "ordenarPor": "nome",
            }
            run.log("camara_deputados_list_started", periodo=periodo)
            for page_index, page in enumerate(iter_camara_pages(client, "api/v2/deputados", params=params), start=1):
                source_id = f"camara:deputados:periodo:{runtime.data_inicio.isoformat()}:{runtime.data_fim.isoformat()}:pagina:{page_index}"
                written = run.write_record(
                    partition="metadata",
                    source_id=source_id,
                    request={"method": "GET", "path": "api/v2/deputados", "params": params if page_index == 1 else {}},
                    response=page.response_metadata,
                    periodo=periodo,
                    payload=page.data,
                    record_type="camara_deputados_page",
                )
                stats["paginas_deputados"] += int(written)
                discovered_ids.extend(_extract_camara_ids_from_page(page.data))
                discovered_ids = _ordered_ids(discovered_ids)
                run.log(
                    "camara_deputados_page_loaded",
                    pagina=page_index,
                    written=written,
                    ids_descobertos=len(discovered_ids),
                )
                if runtime.sample and runtime.sample_limit is not None and len(discovered_ids) >= runtime.sample_limit:
                    break

        selected_ids = _limit_ids(discovered_ids, runtime)
        stats["ids_descobertos"] = len(discovered_ids)
        stats["ids_selecionados"] = len(selected_ids)
        run.log("camara_deputados_selected", ids_descobertos=len(discovered_ids), ids_selecionados=len(selected_ids))
        for index, deputado_id in enumerate(selected_ids, start=1):
            stats["deputados_processados"] += 1
            _log_item_progress(
                run,
                event="camara_deputado_progress",
                index=index,
                total=len(selected_ids),
                parlamentar_id=deputado_id,
            )
            _collect_camara_endpoint(
                client,
                run,
                periodo,
                deputado_id,
                path=f"api/v2/deputados/{deputado_id}",
                record_type="camara_deputado_detalhe",
                source_id=f"camara:deputado:{deputado_id}:detalhe",
                stats=stats,
            )
            _collect_camara_endpoint(
                client,
                run,
                periodo,
                deputado_id,
                path=f"api/v2/deputados/{deputado_id}/historico",
                record_type="camara_deputado_historico",
                source_id=f"camara:deputado:{deputado_id}:historico",
                stats=stats,
                optional=True,
            )

    return dict(stats)


def _collect_camara_endpoint(
    client: OpenDataClient,
    run: CollectionRun,
    periodo: dict[str, str],
    deputado_id: str,
    *,
    path: str,
    record_type: str,
    source_id: str,
    stats: Counter[str],
    optional: bool = False,
) -> None:
    if run.has_record(source_id=source_id, record_type=record_type):
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        stats[f"{record_type}_skipped"] += 1
        return
    try:
        result = client.get_json(path)
    except Exception as exc:
        stats["errors"] += 0 if optional else 1
        stats[f"{record_type}_errors"] += 1
        run.log(
            "parlamentar_endpoint_failed",
            parlamentar_id=deputado_id,
            record_type=record_type,
            optional=optional,
            error=error_summary(exc),
        )
        return
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": path, "params": {}},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type=record_type,
    )
    stats[record_type] += int(written)


def collect_senado(run: CollectionRun, runtime: ParlamentaresRuntime) -> dict[str, Any]:
    periodo = _periodo(runtime)
    stats: Counter[str] = Counter()
    if runtime.ids_from_textos_only:
        textos_root = resolve_textos_root(runtime)
        run.log("ids_textos_scan_started", textos_root=textos_root.as_posix())
        discovered_ids = discover_text_parlamentar_ids(textos_root, SENADO_SOURCE)
        stats["ids_from_textos_only"] = 1
        stats["textos_root_exists"] = int(textos_root.exists())
        stats["textos_root"] = textos_root.as_posix()
        run.log("ids_textos_scan_completed", ids_descobertos=len(discovered_ids), textos_root=textos_root.as_posix())
    elif runtime.skip_existing_id_scan:
        discovered_ids = []
        stats["skip_existing_id_scan"] = 1
        run.log("ids_existing_scan_skipped", motivo="skip_existing_id_scan")
    else:
        run.log("ids_existing_scan_started", data_root=runtime.output_dir.as_posix())
        discovered_ids = _ordered_ids(discover_existing_parlamentar_ids(runtime.output_dir, SENADO_SOURCE, run=run))
        run.log("ids_existing_scan_completed", ids_descobertos=len(discovered_ids))
    legislaturas = legislaturas_for_period(runtime.data_inicio, runtime.data_fim)

    with OpenDataClient(SENADO_BASE_URL) as client:
        if legislaturas and not runtime.ids_from_textos_only:
            inicio, fim = min(legislaturas), max(legislaturas)
            path = f"dadosabertos/senador/lista/legislatura/{inicio}/{fim}.json"
            source_id = f"senado:senadores:legislatura:{inicio}:{fim}"
            run.log("senado_legislatura_list_started", legislatura_inicio=inicio, legislatura_fim=fim)
            result = client.get_json(path)
            written = run.write_record(
                partition="metadata",
                source_id=source_id,
                request={"method": "GET", "path": path, "params": {}},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="senado_parlamentares_legislatura",
            )
            stats["listas_legislatura"] += int(written)
            discovered_ids.extend(extract_senado_parlamentar_ids(result.data))
            run.log(
                "senado_legislatura_list_loaded",
                legislatura_inicio=inicio,
                legislatura_fim=fim,
                written=written,
                ids_descobertos=len(_ordered_ids(discovered_ids)),
            )

        if not runtime.ids_from_textos_only:
            current_path = "dadosabertos/senador/lista/atual.json"
            run.log("senado_atual_list_started")
            current_result = client.get_json(current_path)
            written = run.write_record(
                partition="metadata",
                source_id="senado:senadores:atual",
                request={"method": "GET", "path": current_path, "params": {}},
                response=current_result.response_metadata,
                periodo=periodo,
                payload=current_result.data,
                record_type="senado_parlamentares_atual",
            )
            stats["listas_atual"] += int(written)
            discovered_ids.extend(extract_senado_parlamentar_ids(current_result.data))
            run.log("senado_atual_list_loaded", written=written, ids_descobertos=len(_ordered_ids(discovered_ids)))

        discovered_ids = _ordered_ids(discovered_ids)
        selected_ids = _limit_ids(discovered_ids, runtime)
        stats["ids_descobertos"] = len(discovered_ids)
        stats["ids_selecionados"] = len(selected_ids)
        run.log("senado_senadores_selected", ids_descobertos=len(discovered_ids), ids_selecionados=len(selected_ids))

        for index, senador_id in enumerate(selected_ids, start=1):
            stats["senadores_processados"] += 1
            _log_item_progress(
                run,
                event="senado_senador_progress",
                index=index,
                total=len(selected_ids),
                parlamentar_id=senador_id,
            )
            for suffix, record_type in [
                ("", "senado_senador_detalhe"),
                ("/mandatos", "senado_senador_mandatos"),
                ("/filiacoes", "senado_senador_filiacoes"),
            ]:
                path = f"dadosabertos/senador/{senador_id}{suffix}.json"
                source_id = f"senado:senador:{senador_id}:{record_type.replace('senado_senador_', '')}"
                _collect_senado_endpoint(
                    client,
                    run,
                    periodo,
                    senador_id,
                    path=path,
                    record_type=record_type,
                    source_id=source_id,
                    stats=stats,
                    optional=suffix != "",
                )

    return dict(stats)


def _collect_senado_endpoint(
    client: OpenDataClient,
    run: CollectionRun,
    periodo: dict[str, str],
    senador_id: str,
    *,
    path: str,
    record_type: str,
    source_id: str,
    stats: Counter[str],
    optional: bool = False,
) -> None:
    if run.has_record(source_id=source_id, record_type=record_type):
        run.log("record_resume_skipped", source_id=source_id, record_type=record_type)
        stats[f"{record_type}_skipped"] += 1
        return
    try:
        result = client.get_json(path)
    except Exception as exc:
        stats["errors"] += 0 if optional else 1
        stats[f"{record_type}_errors"] += 1
        run.log(
            "parlamentar_endpoint_failed",
            parlamentar_id=senador_id,
            record_type=record_type,
            optional=optional,
            error=error_summary(exc),
        )
        return
    written = run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": path, "params": {}},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type=record_type,
    )
    stats[record_type] += int(written)


def discover_existing_parlamentar_ids(data_root: Path, source: str, *, run: CollectionRun | None = None) -> list[str]:
    ids: list[str] = []
    raw_root = data_root / "raw"
    if raw_root.exists():
        for file_index, path in enumerate(raw_root.rglob("*.jsonl"), start=1):
            for record in _iter_jsonl(path):
                if record.get("source") != source:
                    continue
                ids.extend(_ids_from_raw_record(record, source))
            if run is not None and file_index % 250 == 0:
                run.log("ids_existing_scan_progress", area="raw", arquivos_lidos=file_index, ids_encontrados=len(ids))

    processed_root = data_root / "processed" / "textos_parlamentares" / "v1"
    if processed_root.exists():
        for file_index, path in enumerate(processed_root.rglob("*.jsonl"), start=1):
            if "parquet" in path.parts:
                continue
            for record in _iter_jsonl(path):
                if record.get("source") != source:
                    continue
                parlamentar_id = _string(record.get("parlamentar_id"))
                if parlamentar_id:
                    ids.append(parlamentar_id)
            if run is not None and file_index % 250 == 0:
                run.log(
                    "ids_existing_scan_progress",
                    area="processed_textos",
                    arquivos_lidos=file_index,
                    ids_encontrados=len(ids),
                )
    return _ordered_ids(ids)


def resolve_textos_root(runtime: ParlamentaresRuntime) -> Path:
    if runtime.textos_root is not None:
        return runtime.textos_root
    samples_root = Path("data/samples/textos_parlamentares/v1")
    if runtime.mode == "dev" and samples_root.exists():
        return samples_root
    return runtime.output_dir / "processed" / "textos_parlamentares" / "v1"


def discover_text_parlamentar_ids(textos_root: Path, source: str) -> list[str]:
    ids: list[str] = []
    if not textos_root.exists():
        return ids

    jsonl_paths = sorted(textos_root.rglob("*.jsonl"))
    for path in jsonl_paths:
        if "audits" in path.parts:
            continue
        for record in _iter_jsonl(path):
            if record.get("source") != source:
                continue
            parlamentar_id = _string(record.get("parlamentar_id"))
            if parlamentar_id:
                ids.append(parlamentar_id)

    for path in sorted(textos_root.rglob("*.parquet")):
        ids.extend(_parquet_parlamentar_ids(path, source))
    return _ordered_ids(ids)


def _parquet_parlamentar_ids(path: Path, source: str) -> list[str]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return []

    try:
        schema_names = set(pq.read_schema(path).names)
    except Exception:
        return []
    if "source" not in schema_names or "parlamentar_id" not in schema_names:
        return []

    try:
        table = pq.read_table(path, columns=["source", "parlamentar_id"])
    except Exception:
        return []

    ids: list[str] = []
    for row in table.to_pylist():
        if row.get("source") != source:
            continue
        parlamentar_id = _string(row.get("parlamentar_id"))
        if parlamentar_id:
            ids.append(parlamentar_id)
    return ids


def _ids_from_raw_record(record: dict[str, Any], source: str) -> list[str]:
    ids: list[str] = []
    if source == CAMARA_SOURCE:
        source_id = _string(record.get("source_id")) or ""
        ids.extend(re.findall(r"deputado:(\d+)", source_id))
        payload = record.get("payload")
        if record.get("record_type") == "camara_deputados_page" and isinstance(payload, dict):
            ids.extend(_extract_camara_ids_from_page(payload))
        for key in ("idDeputado", "id_deputado"):
            for value in _find_values(payload, key):
                if _string(value):
                    ids.append(str(value))
    else:
        payload = record.get("payload")
        for key in ("CodigoParlamentar", "codigoParlamentar", "codigo_parlamentar"):
            for value in _find_values(payload, key):
                if _string(value):
                    ids.append(str(value))
    return ids


def _extract_camara_ids_from_page(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    ids = []
    for item in listify(payload.get("dados")):
        if isinstance(item, dict):
            deputado_id = _string(item.get("id"))
            if deputado_id:
                ids.append(deputado_id)
    return ids


def extract_senado_parlamentar_ids(payload: Any) -> list[str]:
    ids = []
    for value in _find_values(payload, "CodigoParlamentar"):
        senador_id = _string(value)
        if senador_id:
            ids.append(senador_id)
    return _ordered_ids(ids)


def legislaturas_for_period(data_inicio: date, data_fim: date) -> list[int]:
    legislaturas = []
    for numero in range(1, 100):
        start_year = 2011 + (numero - 54) * 4
        start = date(start_year, 2, 1)
        end = date(start_year + 4, 1, 31)
        if start <= data_fim and end >= data_inicio:
            legislaturas.append(numero)
    return legislaturas


def write_combined_manifest(
    *,
    output_dir: Path,
    run_id: str,
    runs: dict[str, CollectionRun],
    runtime: ParlamentaresRuntime,
    status: str,
    errors: int,
    stats_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest_path = output_dir / "manifests" / f"{run_id}.json"
    autosave_path = output_dir / "manifests" / f"{run_id}.autosave.json"
    record_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    checkpoint_paths = {}
    for source, run in runs.items():
        record_counts.update({f"{source}/{key}": value for key, value in run.record_counts.items()})
        partition_counts.update({f"{source}/{key}": value for key, value in run.partition_counts.items()})
        checkpoint_paths[source] = str(run.checkpoint_path)

    manifest = {
        "run_id": run_id,
        "source": runtime.source,
        "sources": sorted(runs),
        "dataset": DATASET,
        "status": status,
        "errors": errors,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "data_inicio": runtime.data_inicio.isoformat(),
        "data_fim": runtime.data_fim.isoformat(),
        "mode": runtime.mode,
        "sample": runtime.sample,
        "sample_limit": runtime.sample_limit,
        "skip_existing_id_scan": runtime.skip_existing_id_scan,
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "autosave_path": str(autosave_path),
        "log_path": str(output_dir / "logs" / f"{run_id}.jsonl"),
        "checkpoint_paths": checkpoint_paths,
        "record_counts": dict(sorted(record_counts.items())),
        "partition_counts": dict(sorted(partition_counts.items())),
        "stats_by_source": stats_by_source,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    autosave_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _periodo(runtime: ParlamentaresRuntime) -> dict[str, str]:
    return {
        "data_inicio": runtime.data_inicio.isoformat(),
        "data_fim": runtime.data_fim.isoformat(),
    }


def _limit_ids(ids: Iterable[str], runtime: ParlamentaresRuntime) -> list[str]:
    ordered = _ordered_ids(ids)
    if runtime.sample and runtime.sample_limit is not None:
        return ordered[: runtime.sample_limit]
    return ordered


def _log_item_progress(
    run: CollectionRun,
    *,
    event: str,
    index: int,
    total: int,
    parlamentar_id: str,
) -> None:
    if index == 1 or index == total or index % 25 == 0:
        run.log(event, processados=index, total=total, parlamentar_id=parlamentar_id)


def _ordered_ids(ids: Iterable[str]) -> list[str]:
    seen = set()
    ordered = []
    for item in ids:
        value = _string(item)
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return sorted(ordered, key=_id_sort_key)


def _id_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**12, value)


def _find_values(value: Any, key: str) -> list[Any]:
    found = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                found.append(child_value)
            found.extend(_find_values(child_value, key))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_values(item, key))
    return found


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


if __name__ == "__main__":
    collect()
