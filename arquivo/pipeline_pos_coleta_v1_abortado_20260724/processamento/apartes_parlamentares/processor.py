from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import urljoin

import pyarrow as pa
import pyarrow.parquet as pq

from coleta.common.config import DEFAULT_DEV_DATA_DIR, PROD_DATA_ROOT_ENV, utc_now_iso
from coleta.common.io import listify

DATASET_NAME = "apartes_parlamentares"
DATASET_VERSION = "v1"
RAW_DATASET = "plenario_apartes"

SENADO_SOURCE = "senado"
CAMARA_SOURCE = "camara"
SENADO_APARTES_RECORD_TYPE = "senador_apartes_metadata"
CAMARA_APARTES_RECORD_TYPE = "sitaq_apartes_search_page"
PROBE_RECORD_TYPES = {
    "senador_apartes_year_probe",
    "senador_apartes_quarter_probe",
    "sitaq_apartes_year_probe",
    "sitaq_apartes_quarter_probe",
}
DISCOVERY_RECORD_TYPES = {
    "senadores_legislatura_metadata",
    "senadores_atual_metadata",
    "deputados_apartes_metadata",
    "deputados_apartes_atual_metadata",
}

APARTES_FIELDS = [
    "aparte_id",
    "dataset_version",
    "source",
    "casa",
    "data",
    "ano",
    "mes",
    "pronunciamento_id",
    "discurso_chave",
    "sessao_id",
    "tipo_sessao",
    "fase_sessao",
    "orador_id",
    "orador_nome",
    "orador_genero",
    "orador_partido",
    "orador_uf",
    "aparteante_id",
    "aparteante_nome",
    "aparteante_genero",
    "aparteante_partido",
    "aparteante_uf",
    "url_texto",
    "url_diario",
    "url_origem",
    "match_status",
    "raw_run_id",
    "raw_record_type",
    "raw_source_id",
    "raw_partition",
    "raw_collected_at",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]

INT_FIELDS = {"ano", "mes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normaliza raw/*/plenario_apartes em processed/apartes_parlamentares/v1."
    )
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--raw-run-id", action="append", default=None)
    parser.add_argument("--source", choices=["camara", "senado", "all"], default="all")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit-records", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_root = resolve_data_root(mode=args.mode, data_root=args.data_root, cwd=Path.cwd(), env=os.environ)
    manifest = process_apartes_data_root(
        data_root,
        run_id=args.run_id,
        raw_run_ids=args.raw_run_id,
        source=args.source,
        overwrite=args.overwrite,
        limit_records=args.limit_records,
    )
    print(manifest["manifest_path"])


def resolve_data_root(
    *,
    mode: str,
    data_root: str | None,
    cwd: Path,
    env: os._Environ[str] | dict[str, str],
) -> Path:
    raw_data_root = data_root or env.get(PROD_DATA_ROOT_ENV)
    if raw_data_root is None:
        if mode == "dev":
            return DEFAULT_DEV_DATA_DIR
        raise ValueError(f"--mode prod exige --data-root ou {PROD_DATA_ROOT_ENV}")

    resolved = Path(raw_data_root).expanduser()
    if mode == "prod" and _is_inside_repo(resolved, cwd):
        raise ValueError(
            "Em --mode prod, use um diretorio externo ao repositorio "
            f"(por exemplo, /content/drive/MyDrive/falando_nela/data via {PROD_DATA_ROOT_ENV})."
        )
    return resolved


def process_apartes_data_root(
    data_root: Path,
    *,
    run_id: str | None = None,
    raw_run_ids: Sequence[str] | None = None,
    source: str = "all",
    overwrite: bool = False,
    limit_records: int | None = None,
) -> dict[str, Any]:
    data_root = data_root.expanduser()
    run_id = run_id or f"processed-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
    output_root = data_root / "processed" / DATASET_NAME / DATASET_VERSION
    parquet_root = output_root / "parquet"
    jsonl_path = output_root / f"{DATASET_NAME}.jsonl"
    parquet_path = parquet_root / f"{DATASET_NAME}.parquet"
    manifest_path = data_root / "processed" / "manifests" / f"{run_id}-apartes-parlamentares.json"
    audit_root = data_root / "processed" / "audits" / DATASET_NAME / run_id

    if not overwrite:
        existing = [path for path in (jsonl_path, parquet_path, manifest_path) if path.exists()]
        if existing:
            raise FileExistsError(f"Saidas ja existem: {existing[0]}; use --overwrite para substituir.")
        if audit_root.exists() and any(audit_root.iterdir()):
            raise FileExistsError(f"Auditoria ja existe: {audit_root}; use --overwrite para substituir.")
    else:
        for path in (jsonl_path, parquet_path, manifest_path):
            if path.exists():
                path.unlink()
        if audit_root.exists():
            shutil.rmtree(audit_root)

    raw_run_id_filter = set(raw_run_ids or [])
    parlamentares_index = ParlamentaresIndex.load(data_root)
    raw_records = list(
        iter_apartes_raw_records(
            data_root,
            raw_run_ids=raw_run_id_filter or None,
            source=source,
            limit_records=limit_records,
        )
    )
    table, build_stats = build_apartes_table(raw_records, data_root=data_root, parlamentares=parlamentares_index)

    write_jsonl_table(jsonl_path, table, APARTES_FIELDS)
    write_parquet_table(parquet_path, table, APARTES_FIELDS)
    audit_files = write_audits(audit_root, table)
    audit_manifest_path = audit_root / "manifest.json"
    audit_files["manifest"] = str(audit_manifest_path)

    manifest = {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "created_at": utc_now_iso(),
        "data_root": str(data_root),
        "output_root": str(output_root),
        "parquet_root": str(parquet_root),
        "manifest_path": str(manifest_path),
        "audit_root": str(audit_root),
        "source_filter": source,
        "raw_run_id_filter": sorted(raw_run_id_filter),
        "input_records": len(raw_records),
        "input_record_counts": dict(sorted(build_stats["input_record_counts"].items())),
        "raw_run_ids_observed": sorted(build_stats["raw_run_ids_observed"]),
        "output_records": len(table),
        "output_record_counts": dict(sorted(build_stats["output_record_counts"].items())),
        "skipped_counts": dict(sorted(build_stats["skipped_counts"].items())),
        "output_files": {"apartes_parlamentares": str(jsonl_path)},
        "parquet_files": {"apartes_parlamentares": str(parquet_path)},
        "audit_files": audit_files,
        "parlamentares_index": parlamentares_index.summary(),
        "table_fields": APARTES_FIELDS,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def iter_apartes_raw_records(
    data_root: Path,
    *,
    raw_run_ids: set[str] | None = None,
    source: str = "all",
    limit_records: int | None = None,
) -> Iterator[tuple[dict[str, Any], Path]]:
    raw_root = data_root / "raw"
    if not raw_root.exists():
        return

    sources = [SENADO_SOURCE, CAMARA_SOURCE] if source == "all" else [source]
    paths: list[Path] = []
    for raw_source in sources:
        paths.extend(raw_root.glob(f"{raw_source}/{RAW_DATASET}/metadata/*.jsonl"))

    count = 0
    for path in _sort_newest_first(paths):
        for record in iter_jsonl(path):
            if record.get("dataset") != RAW_DATASET:
                continue
            if raw_run_ids and record.get("run_id") not in raw_run_ids:
                continue
            if source != "all" and record.get("source") != source:
                continue
            yield record, path
            count += 1
            if limit_records is not None and count >= limit_records:
                return


def build_apartes_table(
    raw_records: Iterable[tuple[dict[str, Any], Path]],
    *,
    data_root: Path,
    parlamentares: "ParlamentaresIndex",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    input_record_counts: Counter[str] = Counter()
    output_record_counts: Counter[str] = Counter()
    skipped_counts: Counter[str] = Counter()
    raw_run_ids_observed: set[str] = set()

    for raw_record, raw_path in raw_records:
        source = _string(raw_record.get("source")) or "unknown"
        record_type = _string(raw_record.get("record_type")) or "unknown"
        input_record_counts[f"{source}/{record_type}"] += 1
        if raw_record.get("run_id"):
            raw_run_ids_observed.add(str(raw_record["run_id"]))

        if record_type in PROBE_RECORD_TYPES:
            skipped_counts["probe_record"] += 1
            continue
        if record_type in DISCOVERY_RECORD_TYPES:
            skipped_counts["discovery_record"] += 1
            continue

        if source == SENADO_SOURCE and record_type == SENADO_APARTES_RECORD_TYPE:
            candidate_rows = normalize_senado_record(raw_record, raw_path=raw_path, data_root=data_root, parlamentares=parlamentares)
        elif source == CAMARA_SOURCE and record_type == CAMARA_APARTES_RECORD_TYPE:
            candidate_rows = normalize_camara_record(raw_record, raw_path=raw_path, data_root=data_root, parlamentares=parlamentares)
        else:
            skipped_counts[f"unsupported_record_type:{record_type}"] += 1
            continue

        if not candidate_rows:
            skipped_counts["empty_apartes_payload"] += 1
            continue

        for row in candidate_rows:
            aparte_id = row.get("aparte_id")
            if not aparte_id:
                skipped_counts["missing_aparte_id"] += 1
                continue
            if aparte_id in seen_ids:
                skipped_counts["duplicate_aparte_id"] += 1
                continue
            seen_ids.add(aparte_id)
            rows.append(row)
            output_record_counts[source] += 1

    rows.sort(
        key=lambda row: (
            str(row.get("data") or ""),
            str(row.get("source") or ""),
            str(row.get("pronunciamento_id") or row.get("discurso_chave") or ""),
            str(row.get("aparteante_id") or row.get("aparteante_nome") or ""),
        )
    )
    return rows, {
        "input_record_counts": input_record_counts,
        "output_record_counts": output_record_counts,
        "skipped_counts": skipped_counts,
        "raw_run_ids_observed": raw_run_ids_observed,
    }


def normalize_senado_record(
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
    parlamentares: "ParlamentaresIndex",
) -> list[dict[str, Any]]:
    payload = _dict(raw_record.get("payload"))
    parlamentar = _dict(_dict(payload.get("ApartesParlamentar")).get("Parlamentar"))
    identificacao = _dict(parlamentar.get("IdentificacaoParlamentar"))
    aparteante_id = _string(identificacao.get("CodigoParlamentar")) or _senador_id_from_source_id(
        _string(raw_record.get("source_id"))
    )
    aparteante_nome = _string(
        identificacao.get("NomeParlamentar")
        or identificacao.get("NomeCompletoParlamentar")
        or identificacao.get("NomeParlamentarCompleto")
    )
    apartes = _list(_dict(parlamentar.get("Apartes")).get("Aparte"))
    rows = []
    for aparte in [item for item in apartes if isinstance(item, dict)]:
        sessao = _dict(aparte.get("SessaoPlenaria"))
        orador = _dict(aparte.get("Orador"))
        tipo_uso = _dict(aparte.get("TipoUsoPalavra"))
        data = _parse_date_any(aparte.get("DataPronunciamento") or sessao.get("DataSessao"))
        ano, mes = _year_month(data)

        orador_id = _string(orador.get("CodigoParlamentar"))
        orador_nome = _string(orador.get("NomeParlamentar"))
        orador_raw_partido = _string(
            orador.get("SiglaPartidoParlamentarNaData")
            or aparte.get("SiglaPartidoParlamentarNaData")
            or orador.get("SiglaPartidoParlamentar")
        )
        orador_raw_uf = _string(
            orador.get("UfParlamentarNaData")
            or aparte.get("UfParlamentarNaData")
            or orador.get("UfParlamentar")
        )
        aparteante_raw_partido = _string(identificacao.get("SiglaPartidoParlamentar"))
        aparteante_raw_uf = _string(identificacao.get("UfParlamentar"))

        orador_periodo = parlamentares.match_by_id(SENADO_SOURCE, orador_id, data)
        aparteante_periodo = parlamentares.match_by_id(SENADO_SOURCE, aparteante_id, data)
        pronunciamento_id = _string(aparte.get("CodigoPronunciamento"))
        row = _empty_row()
        row.update(
            {
                "aparte_id": make_aparte_id(
                    SENADO_SOURCE,
                    data=data,
                    speech_key=pronunciamento_id,
                    session_key=_string(sessao.get("CodigoSessao")),
                    aparteante_key=aparteante_id or aparteante_nome,
                ),
                "dataset_version": DATASET_VERSION,
                "source": SENADO_SOURCE,
                "casa": _string(aparte.get("SiglaCasaPronunciamento") or sessao.get("SiglaCasaSessao")) or "SF",
                "data": data,
                "ano": ano,
                "mes": mes,
                "pronunciamento_id": pronunciamento_id,
                "sessao_id": _string(sessao.get("CodigoSessao")),
                "tipo_sessao": _string(sessao.get("SiglaTipoSessao") or sessao.get("TipoSessao")),
                "fase_sessao": _string(tipo_uso.get("Sigla") or tipo_uso.get("Descricao")),
                "orador_id": orador_id,
                "orador_nome": orador_nome,
                "orador_genero": _periodo_value(orador_periodo, "genero"),
                "orador_partido": _periodo_value(orador_periodo, "partido_sigla") or orador_raw_partido,
                "orador_uf": _periodo_value(orador_periodo, "uf") or orador_raw_uf,
                "aparteante_id": aparteante_id,
                "aparteante_nome": aparteante_nome,
                "aparteante_genero": _periodo_value(aparteante_periodo, "genero"),
                "aparteante_partido": _periodo_value(aparteante_periodo, "partido_sigla") or aparteante_raw_partido,
                "aparteante_uf": _periodo_value(aparteante_periodo, "uf") or aparteante_raw_uf,
                "url_texto": _string(aparte.get("UrlTexto") or aparte.get("UrlTextoBinario")),
                "url_diario": _first_url_diario(aparte.get("Publicacoes")),
                "url_origem": _response_url(raw_record),
                "match_status": _senado_match_status(data, aparteante_id, aparteante_nome),
                **_raw_provenance(raw_record, raw_path=raw_path, data_root=data_root),
            }
        )
        rows.append(row)
    return rows


def normalize_camara_record(
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
    parlamentares: "ParlamentaresIndex",
) -> list[dict[str, Any]]:
    payload = _dict(raw_record.get("payload"))
    chaves = [item for item in _list(payload.get("chaves_extraidas")) if isinstance(item, dict)]
    aparteante_nome_raw = _string(payload.get("aparteante_consultado"))
    aparteante_id_raw = _string(payload.get("aparteante_id_consultado"))
    rows = []
    for chave in chaves:
        data = _parse_date_any(chave.get("Data") or chave.get("dtHoraQuarto"))
        if not data:
            periodo = _dict(raw_record.get("periodo"))
            data = _parse_date_any(periodo.get("data_inicio"))
        ano, mes = _year_month(data)

        aparteante_id = aparteante_id_raw
        aparteante_nome = aparteante_nome_raw
        aparteante_periodo = parlamentares.match_by_id(CAMARA_SOURCE, aparteante_id, data)
        name_status = None
        if not aparteante_periodo and not aparteante_id and aparteante_nome:
            name_status, aparteante_periodo = parlamentares.match_by_name(CAMARA_SOURCE, aparteante_nome, data)
            if aparteante_periodo:
                aparteante_id = _string(aparteante_periodo.get("parlamentar_id"))
                aparteante_nome = _string(aparteante_periodo.get("nome_parlamentar")) or aparteante_nome

        orador_nome = _string(chave.get("txApelido"))
        orador_status = None
        orador_periodo = None
        if orador_nome:
            orador_status, orador_periodo = parlamentares.match_by_name(CAMARA_SOURCE, orador_nome, data)
        orador_id = _string(_periodo_value(orador_periodo, "parlamentar_id") or chave.get("nuOrador"))

        discurso_chave = _string(chave.get("discurso_chave")) or _discurso_chave_from_item(chave)
        href = _string(chave.get("href"))
        url_texto = urljoin("https://www.camara.leg.br/internet/SitaqWeb/", href) if href else None
        row = _empty_row()
        row.update(
            {
                "aparte_id": make_aparte_id(
                    CAMARA_SOURCE,
                    data=data,
                    speech_key=discurso_chave,
                    session_key=_string(chave.get("nuSessao")),
                    aparteante_key=aparteante_id or aparteante_nome,
                ),
                "dataset_version": DATASET_VERSION,
                "source": CAMARA_SOURCE,
                "casa": "CD",
                "data": data,
                "ano": ano,
                "mes": mes,
                "discurso_chave": discurso_chave,
                "sessao_id": _string(chave.get("nuSessao")),
                "tipo_sessao": _string(chave.get("txTipoSessao")),
                "fase_sessao": _string(chave.get("sgFaseSessao") or chave.get("txFaseSessao")),
                "orador_id": orador_id,
                "orador_nome": _string(_periodo_value(orador_periodo, "nome_parlamentar") or orador_nome),
                "orador_genero": _periodo_value(orador_periodo, "genero"),
                "orador_partido": _periodo_value(orador_periodo, "partido_sigla"),
                "orador_uf": _periodo_value(orador_periodo, "uf"),
                "aparteante_id": aparteante_id,
                "aparteante_nome": aparteante_nome,
                "aparteante_genero": _periodo_value(aparteante_periodo, "genero"),
                "aparteante_partido": _periodo_value(aparteante_periodo, "partido_sigla"),
                "aparteante_uf": _periodo_value(aparteante_periodo, "uf"),
                "url_texto": url_texto,
                "url_origem": _response_url(raw_record),
                "match_status": _camara_match_status(
                    data=data,
                    aparteante_id=aparteante_id,
                    aparteante_nome=aparteante_nome,
                    name_status=name_status,
                    orador_status=orador_status,
                ),
                **_raw_provenance(raw_record, raw_path=raw_path, data_root=data_root),
            }
        )
        rows.append(row)
    return rows


class ParlamentaresIndex:
    def __init__(self, rows: list[dict[str, Any]], *, source_path: Path | None) -> None:
        self.rows = rows
        self.source_path = source_path
        self.by_id: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.by_name: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            source = _string(row.get("source"))
            parlamentar_id = _string(row.get("parlamentar_id"))
            nome = _string(row.get("nome_parlamentar") or row.get("nome_civil"))
            if source and parlamentar_id:
                self.by_id.setdefault((source, parlamentar_id), []).append(row)
            if source and nome:
                self.by_name.setdefault((source, normalize_name(nome)), []).append(row)

        for values in self.by_id.values():
            values.sort(key=lambda item: str(item.get("vigencia_inicio") or ""))
        for values in self.by_name.values():
            values.sort(key=lambda item: str(item.get("vigencia_inicio") or ""))

    @classmethod
    def load(cls, data_root: Path) -> "ParlamentaresIndex":
        jsonl_path = data_root / "processed" / "parlamentares" / "v1" / "parlamentares_periodos.jsonl"
        parquet_path = data_root / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
        if jsonl_path.exists():
            return cls(list(iter_jsonl(jsonl_path)), source_path=jsonl_path)
        if parquet_path.exists():
            table = pq.read_table(parquet_path)
            return cls(table.to_pylist(), source_path=parquet_path)
        return cls([], source_path=None)

    def match_by_id(self, source: str, parlamentar_id: str | None, data: str | None) -> dict[str, Any] | None:
        if not source or not parlamentar_id:
            return None
        candidates = self.by_id.get((source, parlamentar_id), [])
        return self._select_candidate(candidates, data)

    def match_by_name(self, source: str, nome: str | None, data: str | None) -> tuple[str, dict[str, Any] | None]:
        if not source or not nome:
            return "name_only", None
        candidates = self.by_name.get((source, normalize_name(nome)), [])
        candidates = self._filter_by_date(candidates, data)
        distinct_ids = {_string(item.get("parlamentar_id")) for item in candidates if _string(item.get("parlamentar_id"))}
        if len(distinct_ids) == 1 and candidates:
            return "matched", candidates[0]
        if len(distinct_ids) > 1:
            return "ambiguous", None
        return "name_only", None

    def summary(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path) if self.source_path else None,
            "rows": len(self.rows),
            "ids_indexed": len(self.by_id),
            "names_indexed": len(self.by_name),
        }

    def _select_candidate(self, candidates: list[dict[str, Any]], data: str | None) -> dict[str, Any] | None:
        filtered = self._filter_by_date(candidates, data)
        if filtered:
            return filtered[0]
        return None

    def _filter_by_date(self, candidates: list[dict[str, Any]], data: str | None) -> list[dict[str, Any]]:
        if not data:
            return []
        return [candidate for candidate in candidates if _period_contains(candidate, data)]


def write_jsonl_table(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(_order_record(record, fields), ensure_ascii=False, sort_keys=False) + "\n")


def write_parquet_table(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema([pa.field(field, _arrow_type(field)) for field in fields])
    rows = [_coerce_record(record, fields) for record in records]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression="zstd")


def write_audits(audit_root: Path, records: list[dict[str, Any]]) -> dict[str, str]:
    audit_root.mkdir(parents=True, exist_ok=True)
    files = {
        "contagens_anuais": audit_root / "contagens_anuais.csv",
        "match_status": audit_root / "match_status.csv",
        "cobertura_parlamentares": audit_root / "cobertura_parlamentares.csv",
    }
    _write_grouped_csv(
        files["contagens_anuais"],
        records,
        group_fields=["source", "ano", "aparteante_genero", "aparteante_partido", "aparteante_uf"],
        count_field="apartes",
    )
    _write_grouped_csv(
        files["match_status"],
        records,
        group_fields=["source", "ano", "match_status"],
        count_field="apartes",
    )
    _write_coverage_csv(files["cobertura_parlamentares"], records)
    return {key: str(path) for key, path in files.items()}


def _write_grouped_csv(
    path: Path,
    records: list[dict[str, Any]],
    *,
    group_fields: list[str],
    count_field: str,
) -> None:
    counts: Counter[tuple[str, ...]] = Counter()
    for record in records:
        counts[tuple(_csv_value(record.get(field)) for field in group_fields)] += 1
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([*group_fields, count_field])
        for key, count in sorted(counts.items()):
            writer.writerow([*key, count])


def _write_coverage_csv(path: Path, records: list[dict[str, Any]]) -> None:
    counts: Counter[tuple[str, str, str, str, str]] = Counter()
    for record in records:
        for papel in ("orador", "aparteante"):
            key = (
                _csv_value(record.get("source")),
                _csv_value(record.get("ano")),
                papel,
                "sim" if record.get(f"{papel}_id") else "nao",
                "sim" if record.get(f"{papel}_genero") else "nao",
            )
            counts[key] += 1
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "ano", "papel", "tem_id", "tem_genero", "linhas"])
        for key, count in sorted(counts.items()):
            writer.writerow([*key, count])


def make_aparte_id(
    source: str,
    *,
    data: str | None,
    speech_key: str | None,
    session_key: str | None,
    aparteante_key: str | None,
) -> str | None:
    if not speech_key and not session_key:
        return None
    if not aparteante_key:
        return None
    canonical = "|".join(
        [
            source,
            data or "",
            speech_key or "",
            session_key or "",
            normalize_name(aparteante_key),
        ]
    )
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{source}:{digest}"


def normalize_name(value: Any) -> str:
    text = _string(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).strip().upper()
    return re.sub(r"\s+", " ", text)


def _empty_row() -> dict[str, Any]:
    return {field: None for field in APARTES_FIELDS}


def _raw_provenance(raw_record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    return {
        "raw_run_id": raw_record.get("run_id"),
        "raw_record_type": raw_record.get("record_type"),
        "raw_source_id": raw_record.get("source_id"),
        "raw_partition": raw_record.get("partition"),
        "raw_collected_at": raw_record.get("collected_at"),
        "raw_checksum": raw_record.get("checksum"),
        "raw_path": _relative_path(raw_path, data_root),
        "raw_response_url": _response_url(raw_record),
    }


def _response_url(raw_record: dict[str, Any]) -> str | None:
    return _string(_dict(raw_record.get("response")).get("url"))


def _senado_match_status(data: str | None, aparteante_id: str | None, aparteante_nome: str | None) -> str:
    if not data:
        return "missing_date"
    if aparteante_id:
        return "matched"
    if aparteante_nome:
        return "name_only"
    return "missing_date"


def _camara_match_status(
    *,
    data: str | None,
    aparteante_id: str | None,
    aparteante_nome: str | None,
    name_status: str | None,
    orador_status: str | None,
) -> str:
    if not data:
        return "missing_date"
    if name_status == "ambiguous" or (not aparteante_id and orador_status == "ambiguous"):
        return "ambiguous"
    if aparteante_id:
        return "matched"
    if aparteante_nome:
        return name_status or "name_only"
    return "name_only"


def _period_contains(row: dict[str, Any], data: str) -> bool:
    start = _string(row.get("vigencia_inicio")) or "0001-01-01"
    end_exclusive = _string(row.get("vigencia_fim_exclusivo"))
    if end_exclusive:
        return start <= data < end_exclusive
    end = _string(row.get("vigencia_fim")) or "9999-12-31"
    return start <= data <= end


def _periodo_value(row: dict[str, Any] | None, field: str) -> str | None:
    if not row:
        return None
    return _string(row.get(field))


def _first_url_diario(publicacoes: Any) -> str | None:
    publication = _dict(publicacoes).get("Publicacao")
    for item in _list(publication):
        if isinstance(item, dict):
            url = _string(item.get("UrlDiario"))
            if url:
                return url
    return None


def _discurso_chave_from_item(item: dict[str, Any]) -> str | None:
    parts = [
        _string(item.get("Data")),
        _string(item.get("nuSessao")),
        _string(item.get("nuQuarto")),
        _string(item.get("nuOrador")),
        _string(item.get("nuInsercao")),
        _string(item.get("sgFaseSessao")),
    ]
    if not any(parts):
        return None
    return "|".join(part or "" for part in parts)


def _parse_date_any(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        return iso_match.group(0)
    br_match = re.search(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})", text)
    if br_match:
        try:
            return date(
                int(br_match.group("year")),
                int(br_match.group("month")),
                int(br_match.group("day")),
            ).isoformat()
        except ValueError:
            return None
    compact_match = re.search(r"\b(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})\b", text)
    if compact_match:
        try:
            return date(
                int(compact_match.group("year")),
                int(compact_match.group("month")),
                int(compact_match.group("day")),
            ).isoformat()
        except ValueError:
            return None
    return None


def _year_month(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, None
    return parsed.year, parsed.month


def _coerce_record(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: _coerce_value(field, record.get(field)) for field in fields}


def _coerce_value(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return str(value)


def _arrow_type(field: str) -> pa.DataType:
    if field in INT_FIELDS:
        return pa.int64()
    return pa.string()


def _order_record(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return listify(value)


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _csv_value(value: Any) -> str:
    return "" if value is None else str(value)


def _senador_id_from_source_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"senador:(\d+)", value)
    return match.group(1) if match else None


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
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


def _sort_newest_first(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (_mtime(path), path.as_posix()), reverse=True)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_inside_repo(path: Path, cwd: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_cwd = cwd.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_cwd)
    except ValueError:
        return False
    return True


def _run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
