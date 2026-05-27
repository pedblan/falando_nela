from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from coleta.common.config import DEFAULT_DEV_DATA_DIR, PROD_DATA_ROOT_ENV, parse_iso_date, utc_now_iso
from coleta.common.io import listify

DATASET_NAME = "parlamentares"
DATASET_VERSION = "v1"

PARLAMENTARES_FIELDS = [
    "parlamentar_key",
    "dataset_version",
    "source",
    "casa",
    "parlamentar_id",
    "codigo_publico",
    "nome_parlamentar",
    "nome_civil",
    "sexo_original",
    "genero",
    "genero_fonte",
    "data_nascimento",
    "data_falecimento",
    "uf_nascimento",
    "municipio_nascimento",
    "url_foto",
    "url_pagina",
    "email_publico",
    "raw_run_id",
    "raw_source_id",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]

MANDATOS_FIELDS = [
    "parlamentar_key",
    "dataset_version",
    "source",
    "casa",
    "parlamentar_id",
    "mandato_id",
    "legislatura",
    "data_inicio",
    "data_fim",
    "uf",
    "partido_sigla",
    "situacao",
    "condicao",
    "participacao",
    "cargo",
    "titular_key",
    "raw_run_id",
    "raw_source_id",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]

FILIACOES_FIELDS = [
    "parlamentar_key",
    "dataset_version",
    "source",
    "casa",
    "parlamentar_id",
    "partido_sigla",
    "partido_nome",
    "data_inicio",
    "data_fim",
    "raw_run_id",
    "raw_source_id",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]

PERIODOS_FIELDS = [
    "parlamentar_key",
    "dataset_version",
    "source",
    "casa",
    "parlamentar_id",
    "nome_parlamentar",
    "nome_civil",
    "genero",
    "sexo_original",
    "partido_sigla",
    "uf",
    "cargo",
    "legislatura",
    "mandato_id",
    "vigencia_inicio",
    "vigencia_fim",
    "vigencia_fim_exclusivo",
    "intervalo_fonte",
    "match_priority",
    "intervalo_inferido",
    "observacao_qualidade",
    "raw_run_id",
    "raw_source_id",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]

TABLE_FIELDS = {
    "parlamentares": PARLAMENTARES_FIELDS,
    "mandatos": MANDATOS_FIELDS,
    "filiacoes": FILIACOES_FIELDS,
    "parlamentares_periodos": PERIODOS_FIELDS,
}

INT_FIELDS = {"match_priority"}
BOOL_FIELDS = {"intervalo_inferido"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normaliza raw/*/parlamentares em processed/parlamentares/v1.")
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit-records", type=int, default=None)
    parser.add_argument("--data-inicio", default=None, help="Data minima para intervalos inferidos.")
    parser.add_argument("--data-fim", default=None, help="Data maxima para intervalos inferidos.")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_root = resolve_data_root(mode=args.mode, data_root=args.data_root, cwd=Path.cwd(), env=os.environ)
    manifest = process_parlamentares_data_root(
        data_root,
        run_id=args.run_id,
        overwrite=args.overwrite,
        limit_records=args.limit_records,
        data_inicio=parse_iso_date(args.data_inicio) if args.data_inicio else None,
        data_fim=parse_iso_date(args.data_fim) if args.data_fim else None,
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


def process_parlamentares_data_root(
    data_root: Path,
    *,
    run_id: str | None = None,
    overwrite: bool = False,
    limit_records: int | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:
    data_root = data_root.expanduser()
    run_id = run_id or f"processed-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
    output_root = data_root / "processed" / DATASET_NAME / DATASET_VERSION
    parquet_root = output_root / "parquet"
    manifest_path = data_root / "processed" / "manifests" / f"{run_id}-parlamentares.json"

    if output_root.exists() and not overwrite and any(output_root.glob("*.jsonl")):
        raise FileExistsError(f"Saidas ja existem em {output_root}; use --overwrite para substituir.")
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(f"Manifest ja existe: {manifest_path}; use --overwrite para substituir.")
    if overwrite:
        for path in output_root.glob("*.jsonl"):
            path.unlink()
        if parquet_root.exists():
            for path in parquet_root.glob("*.parquet"):
                path.unlink()
        if manifest_path.exists():
            manifest_path.unlink()

    raw_records = list(iter_parlamentares_raw_records(data_root, limit_records=limit_records))
    tables = build_processed_tables(raw_records, data_root=data_root, data_inicio=data_inicio, data_fim=data_fim)

    output_files = {}
    parquet_files = {}
    for table_name, fields in TABLE_FIELDS.items():
        records = tables[table_name]
        jsonl_path = output_root / f"{table_name}.jsonl"
        write_jsonl_table(jsonl_path, records, fields)
        output_files[table_name] = str(jsonl_path)
        parquet_path = parquet_root / f"{table_name}.parquet"
        write_parquet_table(parquet_path, records, fields)
        parquet_files[table_name] = str(parquet_path)

    input_counts = Counter(f"{record.get('source')}/{record.get('record_type')}" for record, _ in raw_records)
    output_counts = {table_name: len(records) for table_name, records in tables.items()}
    manifest = {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "created_at": utc_now_iso(),
        "data_root": str(data_root),
        "output_root": str(output_root),
        "parquet_root": str(parquet_root),
        "manifest_path": str(manifest_path),
        "input_records": len(raw_records),
        "input_record_counts": dict(sorted(input_counts.items())),
        "output_record_counts": output_counts,
        "output_records": sum(output_counts.values()),
        "output_files": output_files,
        "parquet_files": parquet_files,
        "table_fields": TABLE_FIELDS,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def iter_parlamentares_raw_records(
    data_root: Path,
    *,
    limit_records: int | None = None,
) -> Iterator[tuple[dict[str, Any], Path]]:
    raw_root = data_root / "raw"
    if not raw_root.exists():
        return
    count = 0
    paths = _sort_newest_first(raw_root.glob("*/parlamentares/metadata/*.jsonl"))
    for path in paths:
        for record in iter_jsonl(path):
            if record.get("dataset") != DATASET_NAME:
                continue
            yield record, path
            count += 1
            if limit_records is not None and count >= limit_records:
                return


def build_processed_tables(
    raw_records: Iterable[tuple[dict[str, Any], Path]],
    *,
    data_root: Path,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, list[dict[str, Any]]]:
    parlamentares: dict[str, dict[str, Any]] = {}
    mandatos: list[dict[str, Any]] = []
    filiacoes: list[dict[str, Any]] = []
    seen_mandatos: set[tuple[Any, ...]] = set()
    seen_filiacoes: set[tuple[Any, ...]] = set()
    camara_history: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    camara_detail_records: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    senado_mandate_records: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    senado_filiation_records: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    senado_list_records: list[tuple[dict[str, Any], Path]] = []

    for raw_record, raw_path in raw_records:
        source = raw_record.get("source")
        record_type = raw_record.get("record_type")
        payload = _dict(raw_record.get("payload"))
        if source == "camara" and record_type == "camara_deputado_detalhe":
            row = normalize_camara_parlamentar(raw_record, raw_path=raw_path, data_root=data_root)
            if row:
                parlamentares.setdefault(row["parlamentar_key"], row)
                camara_detail_records[row["parlamentar_id"]] = (payload, raw_record, raw_path)
        elif source == "camara" and record_type == "camara_deputado_historico":
            deputado_id = _camara_id_from_source_id(_string(raw_record.get("source_id")))
            if deputado_id and deputado_id not in camara_history:
                camara_history[deputado_id] = (payload, raw_record, raw_path)
        elif source == "camara" and record_type == "camara_deputados_page":
            for item in _list(payload.get("dados")):
                if not isinstance(item, dict):
                    continue
                row = normalize_camara_list_item(item, raw_record, raw_path=raw_path, data_root=data_root)
                if row:
                    parlamentares.setdefault(row["parlamentar_key"], row)
        elif source == "senado" and record_type == "senado_senador_detalhe":
            row = normalize_senado_parlamentar(raw_record, raw_path=raw_path, data_root=data_root)
            if row:
                parlamentares.setdefault(row["parlamentar_key"], row)
        elif source == "senado" and record_type in {"senado_parlamentares_legislatura", "senado_parlamentares_atual"}:
            senado_list_records.append((raw_record, raw_path))
        elif source == "senado" and record_type == "senado_senador_mandatos":
            senador_id = _senado_id_from_source_id(_string(raw_record.get("source_id")))
            if senador_id and senador_id not in senado_mandate_records:
                senado_mandate_records[senador_id] = (payload, raw_record, raw_path)
        elif source == "senado" and record_type == "senado_senador_filiacoes":
            senador_id = _senado_id_from_source_id(_string(raw_record.get("source_id")))
            if senador_id and senador_id not in senado_filiation_records:
                senado_filiation_records[senador_id] = (payload, raw_record, raw_path)

    for raw_record, raw_path in senado_list_records:
        for item in extract_senado_parlamentares(raw_record.get("payload")):
            row = normalize_senado_list_item(item, raw_record, raw_path=raw_path, data_root=data_root)
            if row:
                parlamentares.setdefault(row["parlamentar_key"], row)
            for mandato in normalize_senado_list_mandatos(item, raw_record, raw_path=raw_path, data_root=data_root):
                key = _mandato_key(mandato)
                if key not in seen_mandatos:
                    mandatos.append(mandato)
                    seen_mandatos.add(key)

    for deputado_id, (payload, raw_record, raw_path) in camara_history.items():
        rows = normalize_camara_historico(payload, raw_record, raw_path=raw_path, data_root=data_root)
        for row in rows:
            key = _mandato_key(row)
            if key not in seen_mandatos:
                mandatos.append(row)
                seen_mandatos.add(key)
            filiacao = filiacao_from_mandato(row)
            fkey = _filiacao_key(filiacao)
            if fkey not in seen_filiacoes:
                filiacoes.append(filiacao)
                seen_filiacoes.add(fkey)

    for deputado_id, (payload, raw_record, raw_path) in camara_detail_records.items():
        if any(row["source"] == "camara" and row["parlamentar_id"] == deputado_id for row in mandatos):
            continue
        row = normalize_camara_ultimo_status(payload, raw_record, raw_path=raw_path, data_root=data_root)
        if row:
            key = _mandato_key(row)
            if key not in seen_mandatos:
                mandatos.append(row)
                seen_mandatos.add(key)

    for senador_id, (payload, raw_record, raw_path) in senado_mandate_records.items():
        for row in normalize_senado_mandatos(payload, raw_record, raw_path=raw_path, data_root=data_root):
            key = _mandato_key(row)
            if key not in seen_mandatos:
                mandatos.append(row)
                seen_mandatos.add(key)

    for senador_id, (payload, raw_record, raw_path) in senado_filiation_records.items():
        for row in normalize_senado_filiacoes(payload, raw_record, raw_path=raw_path, data_root=data_root):
            key = _filiacao_key(row)
            if key not in seen_filiacoes:
                filiacoes.append(row)
                seen_filiacoes.add(key)

    periodos = build_periodos(
        parlamentares=parlamentares,
        mandatos=mandatos,
        filiacoes=filiacoes,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    return {
        "parlamentares": [_order_record(row, PARLAMENTARES_FIELDS) for row in sorted(parlamentares.values(), key=lambda row: row["parlamentar_key"])],
        "mandatos": [_order_record(row, MANDATOS_FIELDS) for row in sorted(mandatos, key=lambda row: _sort_tuple(row, ["source", "parlamentar_id", "data_inicio", "mandato_id"]))],
        "filiacoes": [_order_record(row, FILIACOES_FIELDS) for row in sorted(filiacoes, key=lambda row: _sort_tuple(row, ["source", "parlamentar_id", "data_inicio", "partido_sigla"]))],
        "parlamentares_periodos": [_order_record(row, PERIODOS_FIELDS) for row in sorted(periodos, key=lambda row: _sort_tuple(row, ["source", "parlamentar_id", "vigencia_inicio", "mandato_id"]))],
    }


def normalize_camara_parlamentar(
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    payload = _dict(raw_record.get("payload"))
    dados = _dict(payload.get("dados"))
    status = _dict(dados.get("ultimoStatus"))
    parlamentar_id = _string(dados.get("id") or status.get("id"))
    if not parlamentar_id:
        return None
    sexo_original = _string(dados.get("sexo"))
    return _base_parlamentar_row(
        source="camara",
        casa="Camara dos Deputados",
        parlamentar_id=parlamentar_id,
        codigo_publico=None,
        nome_parlamentar=_string(status.get("nome") or status.get("nomeEleitoral") or dados.get("nomeCivil")),
        nome_civil=_string(dados.get("nomeCivil")),
        sexo_original=sexo_original,
        genero_fonte="camara:/api/v2/deputados/{id}.dados.sexo" if sexo_original else None,
        data_nascimento=_date_part(dados.get("dataNascimento")),
        data_falecimento=_date_part(dados.get("dataFalecimento")),
        uf_nascimento=_string(dados.get("ufNascimento")),
        municipio_nascimento=_string(dados.get("municipioNascimento")),
        url_foto=_string(status.get("urlFoto")),
        url_pagina=_string(dados.get("uri")),
        email_publico=_string(status.get("email")),
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def normalize_camara_list_item(
    item: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    parlamentar_id = _string(item.get("id"))
    if not parlamentar_id:
        return None
    return _base_parlamentar_row(
        source="camara",
        casa="Camara dos Deputados",
        parlamentar_id=parlamentar_id,
        codigo_publico=None,
        nome_parlamentar=_string(item.get("nome")),
        nome_civil=None,
        sexo_original=None,
        genero_fonte=None,
        data_nascimento=None,
        data_falecimento=None,
        uf_nascimento=None,
        municipio_nascimento=None,
        url_foto=_string(item.get("urlFoto")),
        url_pagina=_string(item.get("uri")),
        email_publico=_string(item.get("email")),
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def normalize_senado_parlamentar(
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    payload = _dict(raw_record.get("payload"))
    root = _dict(payload.get("DetalheParlamentar") or payload)
    parlamentar = _dict(root.get("Parlamentar"))
    identificacao = _dict(parlamentar.get("IdentificacaoParlamentar"))
    dados_basicos = _dict(parlamentar.get("DadosBasicosParlamentar"))
    return _normalize_senado_identity(
        identificacao,
        dados_basicos,
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def normalize_senado_list_item(
    item: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    identificacao = _dict(item.get("IdentificacaoParlamentar"))
    return _normalize_senado_identity(
        identificacao,
        {},
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def _normalize_senado_identity(
    identificacao: dict[str, Any],
    dados_basicos: dict[str, Any],
    *,
    raw_record: dict[str, Any],
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    parlamentar_id = _string(identificacao.get("CodigoParlamentar"))
    if not parlamentar_id:
        return None
    sexo_original = _string(identificacao.get("SexoParlamentar"))
    return _base_parlamentar_row(
        source="senado",
        casa="Senado Federal",
        parlamentar_id=parlamentar_id,
        codigo_publico=_string(identificacao.get("CodigoPublicoNaLegAtual")),
        nome_parlamentar=_string(identificacao.get("NomeParlamentar")),
        nome_civil=_string(identificacao.get("NomeCompletoParlamentar")),
        sexo_original=sexo_original,
        genero_fonte="senado:IdentificacaoParlamentar.SexoParlamentar" if sexo_original else None,
        data_nascimento=_date_part(dados_basicos.get("DataNascimento")),
        data_falecimento=None,
        uf_nascimento=_string(dados_basicos.get("UfNaturalidade")),
        municipio_nascimento=_string(dados_basicos.get("Naturalidade")),
        url_foto=_string(identificacao.get("UrlFotoParlamentar")),
        url_pagina=_string(identificacao.get("UrlPaginaParlamentar")),
        email_publico=_string(identificacao.get("EmailParlamentar")),
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def normalize_camara_historico(
    payload: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> list[dict[str, Any]]:
    deputado_id = _camara_id_from_source_id(_string(raw_record.get("source_id")))
    if not deputado_id:
        return []
    items = [item for item in _list(payload.get("dados")) if isinstance(item, dict)]
    items.sort(key=lambda item: _date_part(item.get("dataHora") or item.get("data")) or "")
    rows = []
    for index, item in enumerate(items):
        start = _date_part(item.get("dataHora") or item.get("data"))
        next_start = _date_part(items[index + 1].get("dataHora") or items[index + 1].get("data")) if index + 1 < len(items) else None
        end = _previous_day(next_start) if next_start else None
        row = _base_mandato_row(
            source="camara",
            casa="Camara dos Deputados",
            parlamentar_id=deputado_id,
            mandato_id=f"{deputado_id}:historico:{index + 1}",
            legislatura=_string(item.get("idLegislatura")),
            data_inicio=start,
            data_fim=end,
            uf=_string(item.get("siglaUf")),
            partido_sigla=_string(item.get("siglaPartido")),
            situacao=_string(item.get("situacao")),
            condicao=_string(item.get("condicaoEleitoral")),
            participacao=None,
            cargo="Deputado(a)",
            titular_key=None,
            raw_record=raw_record,
            raw_path=raw_path,
            data_root=data_root,
        )
        rows.append(row)
    return rows


def normalize_camara_ultimo_status(
    payload: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any] | None:
    dados = _dict(payload.get("dados"))
    status = _dict(dados.get("ultimoStatus"))
    deputado_id = _string(dados.get("id") or status.get("id"))
    if not deputado_id:
        return None
    return _base_mandato_row(
        source="camara",
        casa="Camara dos Deputados",
        parlamentar_id=deputado_id,
        mandato_id=f"{deputado_id}:ultimo_status:{_string(status.get('idLegislatura')) or 'sem-legislatura'}",
        legislatura=_string(status.get("idLegislatura")),
        data_inicio=_date_part(status.get("data")),
        data_fim=None,
        uf=_string(status.get("siglaUf")),
        partido_sigla=_string(status.get("siglaPartido")),
        situacao=_string(status.get("situacao")),
        condicao=_string(status.get("condicaoEleitoral")),
        participacao=None,
        cargo="Deputado(a)",
        titular_key=None,
        raw_record=raw_record,
        raw_path=raw_path,
        data_root=data_root,
    )


def normalize_senado_mandatos(
    payload: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> list[dict[str, Any]]:
    senador_id = _senado_id_from_source_id(_string(raw_record.get("source_id")))
    rows = []
    for mandato in extract_mandatos(payload):
        parlamentar_id = senador_id or _string(_first(mandato, "CodigoParlamentar", "codigoParlamentar"))
        if not parlamentar_id:
            continue
        legislaturas = _senado_legislatura_periods(mandato)
        if not legislaturas:
            legislaturas = [
                {
                    "legislatura": _string(_first(mandato, "NumeroLegislatura", "Legislatura")),
                    "data_inicio": _date_part(_first(mandato, "DataInicio", "dataInicio")),
                    "data_fim": _date_part(_first(mandato, "DataFim", "dataFim")),
                }
            ]
        for item in legislaturas:
            mandato_id = _string(mandato.get("CodigoMandato")) or f"{parlamentar_id}:{item.get('legislatura') or 'sem-legislatura'}"
            row = _base_mandato_row(
                source="senado",
                casa="Senado Federal",
                parlamentar_id=parlamentar_id,
                mandato_id=mandato_id,
                legislatura=item.get("legislatura"),
                data_inicio=item.get("data_inicio"),
                data_fim=item.get("data_fim"),
                uf=_string(mandato.get("UfParlamentar")),
                partido_sigla=None,
                situacao=None,
                condicao=None,
                participacao=_string(mandato.get("DescricaoParticipacao")),
                cargo="Senador(a)",
                titular_key=_senado_titular_key(mandato),
                raw_record=raw_record,
                raw_path=raw_path,
                data_root=data_root,
            )
            rows.append(row)
    return rows


def normalize_senado_list_mandatos(
    item: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> list[dict[str, Any]]:
    identificacao = _dict(item.get("IdentificacaoParlamentar"))
    parlamentar_id = _string(identificacao.get("CodigoParlamentar"))
    if not parlamentar_id:
        return []
    rows = []
    for mandato in extract_mandatos(item):
        legislaturas = _senado_legislatura_periods(mandato)
        if not legislaturas:
            legislaturas = [
                {
                    "legislatura": _string(_first(mandato, "NumeroLegislatura", "Legislatura")),
                    "data_inicio": _date_part(_first(mandato, "DataInicio", "dataInicio")),
                    "data_fim": _date_part(_first(mandato, "DataFim", "dataFim")),
                }
            ]
        for leg in legislaturas:
            mandato_id = _string(mandato.get("CodigoMandato")) or f"{parlamentar_id}:{leg.get('legislatura') or 'sem-legislatura'}"
            rows.append(
                _base_mandato_row(
                    source="senado",
                    casa="Senado Federal",
                    parlamentar_id=parlamentar_id,
                    mandato_id=mandato_id,
                    legislatura=leg.get("legislatura"),
                    data_inicio=leg.get("data_inicio"),
                    data_fim=leg.get("data_fim"),
                    uf=_string(mandato.get("UfParlamentar")),
                    partido_sigla=_string(identificacao.get("SiglaPartidoParlamentar")),
                    situacao=None,
                    condicao=None,
                    participacao=_string(mandato.get("DescricaoParticipacao")),
                    cargo="Senador(a)",
                    titular_key=_senado_titular_key(mandato),
                    raw_record=raw_record,
                    raw_path=raw_path,
                    data_root=data_root,
                )
            )
    return rows


def normalize_senado_filiacoes(
    payload: dict[str, Any],
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
) -> list[dict[str, Any]]:
    senador_id = _senado_id_from_source_id(_string(raw_record.get("source_id")))
    rows = []
    for filiacao in extract_filiacoes(payload):
        parlamentar_id = senador_id or _string(_first(filiacao, "CodigoParlamentar", "codigoParlamentar"))
        if not parlamentar_id:
            continue
        row = _base_filiacao_row(
            source="senado",
            casa="Senado Federal",
            parlamentar_id=parlamentar_id,
            partido_sigla=_string(_first(filiacao, "SiglaPartido", "SiglaPartidoParlamentar", "Partido", "partido")),
            partido_nome=_string(_first(filiacao, "NomePartido", "Nome", "nomePartido")),
            data_inicio=_date_part(_first(filiacao, "DataFiliacao", "DataInicio", "dataInicio")),
            data_fim=_date_part(_first(filiacao, "DataDesfiliacao", "DataFim", "dataFim")),
            raw_record=raw_record,
            raw_path=raw_path,
            data_root=data_root,
        )
        rows.append(row)
    return rows


def build_periodos(
    *,
    parlamentares: dict[str, dict[str, Any]],
    mandatos: list[dict[str, Any]],
    filiacoes: list[dict[str, Any]],
    data_inicio: date | None,
    data_fim: date | None,
) -> list[dict[str, Any]]:
    periods = []
    mandates_by_key: dict[str, list[dict[str, Any]]] = {}
    filiacoes_by_key: dict[str, list[dict[str, Any]]] = {}
    for mandato in mandatos:
        mandates_by_key.setdefault(mandato["parlamentar_key"], []).append(mandato)
    for filiacao in filiacoes:
        filiacoes_by_key.setdefault(filiacao["parlamentar_key"], []).append(filiacao)

    inferred_start = data_inicio.isoformat() if data_inicio else "0001-01-01"
    inferred_end = data_fim.isoformat() if data_fim else "9999-12-31"
    for parlamentar_key, parlamentar in parlamentares.items():
        key_mandatos = mandates_by_key.get(parlamentar_key, [])
        if not key_mandatos:
            periods.append(
                _periodo_from_parts(
                    parlamentar,
                    mandato={},
                    partido_sigla=None,
                    vigencia_inicio=inferred_start,
                    vigencia_fim=inferred_end,
                    intervalo_fonte="identidade",
                    match_priority=99,
                    intervalo_inferido=True,
                    observacao_qualidade="intervalo amplo inferido por ausencia de mandato normalizado",
                )
            )
            continue

        for mandato in key_mandatos:
            start = mandato.get("data_inicio") or inferred_start
            end = mandato.get("data_fim") or inferred_end
            partido_sigla = mandato.get("partido_sigla") or _partido_for_date(filiacoes_by_key.get(parlamentar_key, []), start)
            periods.append(
                _periodo_from_parts(
                    parlamentar,
                    mandato=mandato,
                    partido_sigla=partido_sigla,
                    vigencia_inicio=start,
                    vigencia_fim=end,
                    intervalo_fonte="mandato",
                    match_priority=1 if mandato.get("data_inicio") else 50,
                    intervalo_inferido=not bool(mandato.get("data_inicio")),
                    observacao_qualidade=None if mandato.get("data_inicio") else "inicio de vigencia inferido",
                )
            )
    return periods


def _periodo_from_parts(
    parlamentar: dict[str, Any],
    *,
    mandato: dict[str, Any],
    partido_sigla: str | None,
    vigencia_inicio: str,
    vigencia_fim: str,
    intervalo_fonte: str,
    match_priority: int,
    intervalo_inferido: bool,
    observacao_qualidade: str | None,
) -> dict[str, Any]:
    row = {field: None for field in PERIODOS_FIELDS}
    row.update(
        {
            "parlamentar_key": parlamentar["parlamentar_key"],
            "dataset_version": DATASET_VERSION,
            "source": parlamentar["source"],
            "casa": parlamentar["casa"],
            "parlamentar_id": parlamentar["parlamentar_id"],
            "nome_parlamentar": parlamentar.get("nome_parlamentar"),
            "nome_civil": parlamentar.get("nome_civil"),
            "genero": parlamentar.get("genero"),
            "sexo_original": parlamentar.get("sexo_original"),
            "partido_sigla": partido_sigla,
            "uf": mandato.get("uf"),
            "cargo": mandato.get("cargo"),
            "legislatura": mandato.get("legislatura"),
            "mandato_id": mandato.get("mandato_id"),
            "vigencia_inicio": vigencia_inicio,
            "vigencia_fim": vigencia_fim,
            "vigencia_fim_exclusivo": _next_day(vigencia_fim) if vigencia_fim != "9999-12-31" else "9999-12-31",
            "intervalo_fonte": intervalo_fonte,
            "match_priority": match_priority,
            "intervalo_inferido": intervalo_inferido,
            "observacao_qualidade": observacao_qualidade,
            "raw_run_id": mandato.get("raw_run_id") or parlamentar.get("raw_run_id"),
            "raw_source_id": mandato.get("raw_source_id") or parlamentar.get("raw_source_id"),
            "raw_checksum": mandato.get("raw_checksum") or parlamentar.get("raw_checksum"),
            "raw_path": mandato.get("raw_path") or parlamentar.get("raw_path"),
            "raw_response_url": mandato.get("raw_response_url") or parlamentar.get("raw_response_url"),
        }
    )
    return row


def extract_senado_parlamentares(payload: Any) -> list[dict[str, Any]]:
    roots = []
    if isinstance(payload, dict):
        for key in ("ListaParlamentarLegislatura", "ListaParlamentarEmExercicio"):
            if isinstance(payload.get(key), dict):
                roots.append(payload[key])
        roots.append(payload)
    items = []
    for root in roots:
        parlamentares = _dict(root.get("Parlamentares")).get("Parlamentar")
        for item in _list(parlamentares):
            if isinstance(item, dict):
                items.append(item)
    return items


def extract_mandatos(payload: Any) -> list[dict[str, Any]]:
    return [item for item in _objects_under_key(payload, "Mandato") if isinstance(item, dict)]


def extract_filiacoes(payload: Any) -> list[dict[str, Any]]:
    items = []
    for key in ("Filiacao", "FiliacaoPartidaria"):
        items.extend(item for item in _objects_under_key(payload, key) if isinstance(item, dict))
    return items


def filiacao_from_mandato(mandato: dict[str, Any]) -> dict[str, Any]:
    return _base_filiacao_row(
        source=mandato["source"],
        casa=mandato["casa"],
        parlamentar_id=mandato["parlamentar_id"],
        partido_sigla=mandato.get("partido_sigla"),
        partido_nome=None,
        data_inicio=mandato.get("data_inicio"),
        data_fim=mandato.get("data_fim"),
        raw_record={
            "run_id": mandato.get("raw_run_id"),
            "source_id": mandato.get("raw_source_id"),
            "checksum": mandato.get("raw_checksum"),
            "response": {"url": mandato.get("raw_response_url")},
        },
        raw_path=Path(str(mandato.get("raw_path") or "")),
        data_root=Path("."),
        raw_path_is_relative=True,
    )


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


def _base_parlamentar_row(
    *,
    source: str,
    casa: str,
    parlamentar_id: str,
    codigo_publico: str | None,
    nome_parlamentar: str | None,
    nome_civil: str | None,
    sexo_original: str | None,
    genero_fonte: str | None,
    data_nascimento: str | None,
    data_falecimento: str | None,
    uf_nascimento: str | None,
    municipio_nascimento: str | None,
    url_foto: str | None,
    url_pagina: str | None,
    email_publico: str | None,
    raw_record: dict[str, Any],
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    row = {field: None for field in PARLAMENTARES_FIELDS}
    row.update(
        {
            "parlamentar_key": f"{source}:{parlamentar_id}",
            "dataset_version": DATASET_VERSION,
            "source": source,
            "casa": casa,
            "parlamentar_id": parlamentar_id,
            "codigo_publico": codigo_publico,
            "nome_parlamentar": nome_parlamentar,
            "nome_civil": nome_civil,
            "sexo_original": sexo_original,
            "genero": normalize_genero(sexo_original),
            "genero_fonte": genero_fonte,
            "data_nascimento": data_nascimento,
            "data_falecimento": data_falecimento,
            "uf_nascimento": uf_nascimento,
            "municipio_nascimento": municipio_nascimento,
            "url_foto": url_foto,
            "url_pagina": url_pagina,
            "email_publico": email_publico,
            **_raw_provenance(raw_record, raw_path=raw_path, data_root=data_root),
        }
    )
    return row


def _base_mandato_row(
    *,
    source: str,
    casa: str,
    parlamentar_id: str,
    mandato_id: str | None,
    legislatura: str | None,
    data_inicio: str | None,
    data_fim: str | None,
    uf: str | None,
    partido_sigla: str | None,
    situacao: str | None,
    condicao: str | None,
    participacao: str | None,
    cargo: str | None,
    titular_key: str | None,
    raw_record: dict[str, Any],
    raw_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    row = {field: None for field in MANDATOS_FIELDS}
    row.update(
        {
            "parlamentar_key": f"{source}:{parlamentar_id}",
            "dataset_version": DATASET_VERSION,
            "source": source,
            "casa": casa,
            "parlamentar_id": parlamentar_id,
            "mandato_id": mandato_id,
            "legislatura": legislatura,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "uf": uf,
            "partido_sigla": partido_sigla,
            "situacao": situacao,
            "condicao": condicao,
            "participacao": participacao,
            "cargo": cargo,
            "titular_key": titular_key,
            **_raw_provenance(raw_record, raw_path=raw_path, data_root=data_root),
        }
    )
    return row


def _base_filiacao_row(
    *,
    source: str,
    casa: str,
    parlamentar_id: str,
    partido_sigla: str | None,
    partido_nome: str | None,
    data_inicio: str | None,
    data_fim: str | None,
    raw_record: dict[str, Any],
    raw_path: Path,
    data_root: Path,
    raw_path_is_relative: bool = False,
) -> dict[str, Any]:
    row = {field: None for field in FILIACOES_FIELDS}
    provenance = _raw_provenance(raw_record, raw_path=raw_path, data_root=data_root)
    if raw_path_is_relative:
        provenance["raw_path"] = str(raw_path)
    row.update(
        {
            "parlamentar_key": f"{source}:{parlamentar_id}",
            "dataset_version": DATASET_VERSION,
            "source": source,
            "casa": casa,
            "parlamentar_id": parlamentar_id,
            "partido_sigla": partido_sigla,
            "partido_nome": partido_nome,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            **provenance,
        }
    )
    return row


def normalize_genero(value: Any) -> str:
    normalized = (_string(value) or "").strip().lower()
    if normalized in {"m", "masculino", "male", "homem"}:
        return "masculino"
    if normalized in {"f", "feminino", "female", "mulher"}:
        return "feminino"
    return "nao_informado"


def _raw_provenance(raw_record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    response = _dict(raw_record.get("response"))
    return {
        "raw_run_id": raw_record.get("run_id"),
        "raw_source_id": raw_record.get("source_id"),
        "raw_checksum": raw_record.get("checksum"),
        "raw_path": _relative_path(raw_path, data_root),
        "raw_response_url": response.get("url"),
    }


def _senado_legislatura_periods(mandato: dict[str, Any]) -> list[dict[str, str | None]]:
    periods = []
    for key in ("PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato", "Legislatura"):
        value = mandato.get(key)
        for item in _list(value):
            if not isinstance(item, dict):
                continue
            periods.append(
                {
                    "legislatura": _string(item.get("NumeroLegislatura") or item.get("numeroLegislatura")),
                    "data_inicio": _date_part(item.get("DataInicio") or item.get("dataInicio")),
                    "data_fim": _date_part(item.get("DataFim") or item.get("dataFim")),
                }
            )
    return periods


def _senado_titular_key(mandato: dict[str, Any]) -> str | None:
    titular = _dict(mandato.get("Titular"))
    titular_id = _string(titular.get("CodigoParlamentar"))
    return f"senado:{titular_id}" if titular_id else None


def _partido_for_date(filiacoes: list[dict[str, Any]], value: str | None) -> str | None:
    if not value:
        return None
    for filiacao in sorted(filiacoes, key=lambda row: row.get("data_inicio") or ""):
        if not filiacao.get("partido_sigla"):
            continue
        start = filiacao.get("data_inicio") or "0001-01-01"
        end = filiacao.get("data_fim") or "9999-12-31"
        if start <= value <= end:
            return filiacao.get("partido_sigla")
    return None


def _objects_under_key(value: Any, key: str) -> list[Any]:
    found = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if child_key == key:
                found.extend(listify(child_value))
            found.extend(_objects_under_key(child_value, key))
    elif isinstance(value, list):
        for item in value:
            found.extend(_objects_under_key(item, key))
    return found


def _mandato_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("source"),
        row.get("parlamentar_id"),
        row.get("mandato_id"),
        row.get("legislatura"),
        row.get("data_inicio"),
        row.get("data_fim"),
    )


def _filiacao_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("source"),
        row.get("parlamentar_id"),
        row.get("partido_sigla"),
        row.get("data_inicio"),
        row.get("data_fim"),
    )


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
    if field in BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "1", "sim", "yes"}
        return bool(value)
    return str(value)


def _arrow_type(field: str) -> pa.DataType:
    if field in INT_FIELDS:
        return pa.int64()
    if field in BOOL_FIELDS:
        return pa.bool_()
    return pa.string()


def _order_record(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _sort_tuple(row: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in fields)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return listify(value)


def _first(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


def _date_part(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def _previous_day(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return (date.fromisoformat(value) - timedelta(days=1)).isoformat()
    except ValueError:
        return None


def _next_day(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return (date.fromisoformat(value) + timedelta(days=1)).isoformat()
    except ValueError:
        return None


def _camara_id_from_source_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"deputado:(\d+)", value)
    return match.group(1) if match else None


def _senado_id_from_source_id(value: str | None) -> str | None:
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


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    main()
