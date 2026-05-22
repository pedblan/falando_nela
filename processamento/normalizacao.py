from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from coleta.common.config import DEFAULT_DEV_DATA_DIR, PROD_DATA_ROOT_ENV, utc_now_iso

DATASET_NAME = "textos_parlamentares"
DATASET_VERSION = "v1"

PROCESSED_FIELDS = [
    "texto_id",
    "dataset_version",
    "source",
    "dataset",
    "casa",
    "ambito",
    "orgao_sigla",
    "orgao_nome",
    "documento_tipo",
    "unidade_analitica",
    "data",
    "data_hora",
    "ano",
    "mes",
    "titulo",
    "resumo",
    "indexacao",
    "tipo_discurso",
    "tipo_uso_palavra",
    "fase_evento",
    "parlamentar_id",
    "parlamentar_nome",
    "parlamentar_partido",
    "parlamentar_uf",
    "parlamentar_cargo",
    "pronunciamento_id",
    "sessao_id",
    "reuniao_id",
    "evento_id",
    "proposicao_id",
    "materia_id",
    "documento_id",
    "proposicao_sigla",
    "proposicao_numero",
    "proposicao_ano",
    "proposicao_identificacao",
    "documento_classe",
    "status_deliberativo",
    "vencido",
    "texto",
    "texto_tamanho",
    "texto_status",
    "forma",
    "metodo_obtencao",
    "url_texto",
    "url_audio",
    "url_video",
    "url_origem",
    "fontes",
    "raw_run_id",
    "raw_record_type",
    "raw_source_id",
    "raw_partition",
    "raw_collected_at",
    "raw_checksum",
    "raw_path",
    "raw_response_url",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normaliza a camada raw em processed/textos_parlamentares/v1."
    )
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--raw-run-id",
        action="append",
        default=None,
        help="Inclui apenas registros brutos destes run_id. Pode ser repetido. Por default, le todos.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit-records", type=int, default=None)
    parser.add_argument(
        "--dataset",
        action="append",
        default=None,
        help="Filtra por dataset no formato fonte/dataset. Pode ser repetido.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_root = resolve_data_root(mode=args.mode, data_root=args.data_root, cwd=Path.cwd(), env=os.environ)
    manifest = normalize_data_root(
        data_root,
        run_id=args.run_id,
        overwrite=args.overwrite,
        limit_records=args.limit_records,
        datasets=args.dataset,
        raw_run_ids=args.raw_run_id,
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


def normalize_data_root(
    data_root: Path,
    *,
    run_id: str | None = None,
    overwrite: bool = False,
    limit_records: int | None = None,
    datasets: Iterable[str] | None = None,
    raw_run_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    data_root = data_root.expanduser()
    run_id = run_id or f"processed-{DATASET_NAME}-{DATASET_VERSION}-{_run_timestamp()}"
    dataset_filter = set(datasets or [])
    raw_run_id_filter = set(raw_run_ids or [])
    output_root = data_root / "processed" / DATASET_NAME / DATASET_VERSION
    manifest_path = data_root / "processed" / "manifests" / f"{run_id}.json"

    existing_outputs = list(output_root.rglob(f"{run_id}.jsonl")) if output_root.exists() else []
    if manifest_path.exists():
        existing_outputs.append(manifest_path)
    if existing_outputs and not overwrite:
        raise FileExistsError(f"Saidas ja existem para run_id={run_id}; use --overwrite para substituir.")
    for path in existing_outputs:
        path.unlink()

    raw_paths = list(iter_raw_jsonl_paths(data_root, dataset_filter=dataset_filter))
    deputados_index = build_camara_deputados_index(data_root)
    writer = PartitionedJsonlWriter(output_root=output_root, run_id=run_id)
    seen_text_ids: set[str] = set()
    observed_raw_run_ids: set[str] = set()
    input_files: set[str] = set()
    input_record_counts: Counter[str] = Counter()
    output_record_counts: Counter[str] = Counter()
    skipped_counts: Counter[str] = Counter()
    written = 0

    try:
        for raw_path in raw_paths:
            if limit_records is not None and written >= limit_records:
                break
            relative_raw_path = _relative_path(raw_path, data_root)
            for raw_record in iter_jsonl(raw_path):
                if limit_records is not None and written >= limit_records:
                    break

                source = str(raw_record.get("source") or "")
                dataset = str(raw_record.get("dataset") or "")
                record_type = str(raw_record.get("record_type") or "")
                input_files.add(relative_raw_path)
                input_record_counts[f"{source}/{dataset}/{record_type}"] += 1
                raw_run_id = raw_record.get("run_id")
                if isinstance(raw_run_id, str):
                    observed_raw_run_ids.add(raw_run_id)
                if raw_run_id_filter and raw_run_id not in raw_run_id_filter:
                    skipped_counts["raw_run_id_filtered"] += 1
                    continue

                normalized_records = normalize_raw_record(
                    raw_record,
                    raw_path=raw_path,
                    data_root=data_root,
                    deputados_index=deputados_index,
                )
                if not normalized_records:
                    skipped_counts["record_type_not_textual"] += 1
                    continue

                for record in normalized_records:
                    text_id = record["texto_id"]
                    if text_id in seen_text_ids:
                        skipped_counts["duplicate_texto_id"] += 1
                        continue
                    if not record.get("texto"):
                        skipped_counts["empty_text"] += 1
                        continue

                    writer.write(record)
                    seen_text_ids.add(text_id)
                    output_record_counts[f"{record['source']}/{record['dataset']}"] += 1
                    written += 1
    finally:
        output_files = writer.close()

    manifest = {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "created_at": utc_now_iso(),
        "data_root": str(data_root),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "output_records": written,
        "output_files": output_files,
        "input_files": sorted(input_files),
        "input_file_count": len(input_files),
        "input_record_counts": dict(sorted(input_record_counts.items())),
        "output_record_counts": dict(sorted(output_record_counts.items())),
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "raw_run_ids": sorted(observed_raw_run_ids),
        "raw_run_id_filter": sorted(raw_run_id_filter),
        "dataset_filter": sorted(dataset_filter),
        "schema": f"data/schemas/processed_{DATASET_NAME}_{DATASET_VERSION}.schema.json",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def normalize_raw_record(
    record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
    deputados_index: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    source = record.get("source")
    dataset = record.get("dataset")
    record_type = record.get("record_type")

    if source == "senado" and dataset in {"plenario_discursos", "congresso_discursos"}:
        if record_type == "pronunciamento_texto":
            return [_normalize_senado_pronunciamento(record, raw_path=raw_path, data_root=data_root)]
        return []
    if source == "senado" and dataset == "ccj_notas":
        if record_type == "notas_taquigraficas":
            return [_normalize_senado_ccj_notas(record, raw_path=raw_path, data_root=data_root)]
        return []
    if source == "camara" and dataset == "plenario_discursos":
        if record_type == "discursos_page":
            return _normalize_camara_discursos_page(
                record,
                raw_path=raw_path,
                data_root=data_root,
                deputados_index=deputados_index or {},
            )
        return []
    if source == "camara" and dataset == "ccjc_eventos":
        if record_type == "notas_taquigraficas":
            return [_normalize_camara_ccjc_notas(record, raw_path=raw_path, data_root=data_root)]
        return []
    if dataset == "pareceres_pec" and record_type == "parecer_pec_texto":
        return [_normalize_parecer_pec(record, raw_path=raw_path, data_root=data_root)]
    return []


def build_camara_deputados_index(data_root: Path) -> dict[str, dict[str, Any]]:
    metadata_root = data_root / "raw" / "camara" / "plenario_discursos" / "metadata"
    index: dict[str, dict[str, Any]] = {}
    if not metadata_root.exists():
        return index

    for path in _sort_newest_first(metadata_root.rglob("*.jsonl")):
        for record in iter_jsonl(path):
            if record.get("record_type") != "deputados_page":
                continue
            payload = _dict(record.get("payload"))
            for item in _list(payload.get("dados")):
                if not isinstance(item, dict):
                    continue
                deputado_id = _string(item.get("id"))
                if deputado_id and deputado_id not in index:
                    index[deputado_id] = item
    return index


def iter_raw_jsonl_paths(data_root: Path, *, dataset_filter: set[str]) -> Iterator[Path]:
    raw_root = data_root / "raw"
    if not raw_root.exists():
        return
    paths = _sort_newest_first(raw_root.rglob("*.jsonl"))
    for path in paths:
        if not dataset_filter:
            yield path
            continue
        parts = path.relative_to(raw_root).parts
        if len(parts) >= 2 and f"{parts[0]}/{parts[1]}" in dataset_filter:
            yield path


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


class PartitionedJsonlWriter:
    def __init__(self, *, output_root: Path, run_id: str) -> None:
        self.output_root = output_root
        self.run_id = run_id
        self._handles: dict[Path, Any] = {}
        self._output_files: set[str] = set()

    def write(self, record: dict[str, Any]) -> None:
        year = record["ano"]
        month = record["mes"]
        path = self.output_root / f"ano={year}" / f"mes={month}" / f"{self.run_id}.jsonl"
        handle = self._handles.get(path)
        if handle is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a", encoding="utf-8")
            self._handles[path] = handle
            self._output_files.add(str(path))
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False, default=str) + "\n")

    def close(self) -> list[str]:
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()
        return sorted(self._output_files)


def _normalize_senado_pronunciamento(record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    payload = _dict(record.get("payload"))
    metadata = _dict(payload.get("metadata"))
    pronunciamento = _dict(metadata.get("pronunciamento"))
    sessao = _dict(metadata.get("sessao"))
    fontes = _dict(payload.get("fontes"))
    dataset = str(record.get("dataset"))
    codigo = _string(payload.get("codigo_pronunciamento") or payload.get("CodigoPronunciamento") or record.get("source_id"))
    data = _date_part(_first(pronunciamento, "Data", "data")) or _date_part(_first(sessao, "DataSessao", "dataSessao"))
    casa = "Congresso Nacional" if dataset == "congresso_discursos" else "Senado Federal"
    ambito = "congresso" if dataset == "congresso_discursos" else "plenario"
    orgao_sigla = "CN" if dataset == "congresso_discursos" else "SF"
    orgao_nome = "Plenario do Congresso Nacional" if dataset == "congresso_discursos" else "Plenario do Senado Federal"

    return _finalize_record(
        record,
        raw_path=raw_path,
        data_root=data_root,
        texto_id=f"senado:{dataset}:pronunciamento:{codigo}",
        casa=casa,
        ambito=ambito,
        orgao_sigla=orgao_sigla,
        orgao_nome=orgao_nome,
        documento_tipo="discurso",
        unidade_analitica="pronunciamento",
        data=data,
        titulo=_string(_first(pronunciamento, "TipoUsoPalavra", "Descricao")),
        resumo=_string(_first(pronunciamento, "Resumo", "resumo")),
        indexacao=_string(_first(pronunciamento, "Indexacao", "indexacao")),
        tipo_uso_palavra=_tipo_uso_palavra(pronunciamento),
        parlamentar_id=_string(_first(pronunciamento, "CodigoParlamentar", "codigoParlamentar")),
        parlamentar_nome=_string(_first(pronunciamento, "NomeAutor", "nomeAutor")),
        parlamentar_partido=_string(_first(pronunciamento, "Partido", "partido")),
        parlamentar_uf=_string(_first(pronunciamento, "UF", "uf")),
        parlamentar_cargo=_string(_first(pronunciamento, "FuncaoAutor", "TipoAutor", "tipoAutor")),
        pronunciamento_id=codigo,
        sessao_id=_string(_first(sessao, "CodigoSessao", "codigoSessao")),
        texto=_clean_text(payload.get("texto") or payload.get("TextoIntegral")),
        texto_status=_string(payload.get("texto_status")),
        forma=_string(payload.get("forma")),
        metodo_obtencao=_string(payload.get("metodo_obtencao")),
        url_texto=_string(payload.get("TextoIntegralUrl") or fontes.get("texto_integral_txt") or fontes.get("texto_integral_html")),
        url_video=_string(fontes.get("video") or fontes.get("videos_sessao_api")),
        url_origem=_string(fontes.get("texto_integral_html") or fontes.get("texto_integral_txt")),
        fontes=fontes,
    )


def _normalize_senado_ccj_notas(record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    payload = _dict(record.get("payload"))
    metadata = _dict(payload.get("metadata"))
    agenda = _dict(metadata.get("agenda"))
    detalhe = _dict(metadata.get("detalhe"))
    fontes = _dict(payload.get("fontes"))
    colegiado = _colegiado_senado(detalhe) or _colegiado_senado(agenda)
    codigo = _string(payload.get("codigo_reuniao") or payload.get("CodigoReuniao") or record.get("source_id"))
    data_hora = _string(_first(detalhe, "dataInicio", "DataInicio") or _first(agenda, "dataInicio", "DataInicio"))

    return _finalize_record(
        record,
        raw_path=raw_path,
        data_root=data_root,
        texto_id=f"senado:ccj_notas:reuniao:{codigo}",
        casa="Senado Federal",
        ambito="ccj",
        orgao_sigla=_string(colegiado.get("sigla")) or "CCJ",
        orgao_nome=_string(colegiado.get("nome")) or "Comissao de Constituicao, Justica e Cidadania",
        documento_tipo="notas_taquigraficas",
        unidade_analitica="reuniao",
        data_hora=data_hora,
        titulo=_string(_first(detalhe, "titulo", "Titulo") or _first(agenda, "titulo", "Titulo")),
        resumo=_string(_first(detalhe, "descricao", "Descricao") or _first(agenda, "descricao", "Descricao")),
        reuniao_id=codigo,
        texto=_clean_text(payload.get("texto") or payload.get("TextoIntegral")),
        texto_status=_string(payload.get("texto_status")),
        forma=_string(payload.get("forma")),
        metodo_obtencao=_string(payload.get("metodo_obtencao")),
        url_texto=_string(fontes.get("notas_reuniao_html") or fontes.get("notas_reuniao_api")),
        url_audio=_first_list_item(fontes.get("audios")),
        url_video=_senado_video_url(detalhe) or _senado_video_url(agenda),
        url_origem=_string(fontes.get("reuniao_detalhe_api") or fontes.get("notas_reuniao_html")),
        fontes=fontes,
    )


def _normalize_camara_discursos_page(
    record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
    deputados_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    payload = _dict(record.get("payload"))
    source_id = _string(record.get("source_id")) or ""
    deputado_id = _extract_deputado_id(source_id)
    deputado = deputados_index.get(deputado_id or "", {})
    records: list[dict[str, Any]] = []

    for index, item in enumerate(_list(payload.get("dados")), start=1):
        if not isinstance(item, dict):
            continue
        texto = _clean_text(item.get("transcricao"))
        if not texto:
            continue
        data_hora = _string(item.get("dataHoraInicio"))
        texto_hash = sha1(texto.encode("utf-8")).hexdigest()[:16]
        fase_evento = _dict(item.get("faseEvento"))
        evento_id = _id_from_uri(_string(item.get("uriEvento")))
        discurso_id = _camara_discurso_id(
            deputado_id=deputado_id,
            evento_id=evento_id,
            data_hora=data_hora,
            tipo_discurso=_string(item.get("tipoDiscurso")),
            index=index,
            texto_hash=texto_hash,
        )
        fontes = {
            "urlAudio": item.get("urlAudio"),
            "urlTexto": item.get("urlTexto"),
            "urlVideo": item.get("urlVideo"),
            "uriEvento": item.get("uriEvento"),
        }
        records.append(
            _finalize_record(
                record,
                raw_path=raw_path,
                data_root=data_root,
                texto_id=discurso_id,
                casa="Camara dos Deputados",
                ambito="plenario",
                orgao_sigla="PLEN",
                orgao_nome="Plenario da Camara dos Deputados",
                documento_tipo="discurso",
                unidade_analitica="discurso",
                data_hora=data_hora,
                resumo=_string(item.get("sumario")),
                indexacao=_string(item.get("keywords")),
                tipo_discurso=_string(item.get("tipoDiscurso")),
                fase_evento=_string(fase_evento.get("titulo")),
                parlamentar_id=deputado_id,
                parlamentar_nome=_string(deputado.get("nome")),
                parlamentar_partido=_string(deputado.get("siglaPartido")),
                parlamentar_uf=_string(deputado.get("siglaUf")),
                parlamentar_cargo="Deputado(a)",
                evento_id=evento_id,
                texto=texto,
                texto_status="disponivel",
                forma="texto",
                metodo_obtencao="api_transcricao_discursos",
                url_texto=_string(item.get("urlTexto")),
                url_audio=_string(item.get("urlAudio")),
                url_video=_string(item.get("urlVideo")),
                url_origem=_string(item.get("uriEvento")),
                fontes=fontes,
            )
        )
    return records


def _normalize_camara_ccjc_notas(record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    payload = _dict(record.get("payload"))
    metadata = _dict(payload.get("metadata"))
    event = _dict(metadata.get("evento"))
    orgao = _first_orgao_camara(event)
    fontes = _dict(payload.get("fontes"))
    evento_id = _string(payload.get("evento_id") or payload.get("CodigoEvento") or event.get("id"))
    data_hora = _string(_first(event, "dataHoraInicio", "dataInicio"))

    return _finalize_record(
        record,
        raw_path=raw_path,
        data_root=data_root,
        texto_id=f"camara:ccjc_eventos:evento:{evento_id}",
        casa="Camara dos Deputados",
        ambito="ccjc",
        orgao_sigla=_string(orgao.get("sigla")) or "CCJC",
        orgao_nome=_string(orgao.get("nome")) or "Comissao de Constituicao e Justica e de Cidadania",
        documento_tipo="notas_taquigraficas",
        unidade_analitica="evento",
        data_hora=data_hora,
        titulo=_string(event.get("descricao")),
        tipo_discurso=_string(event.get("descricaoTipo")),
        evento_id=evento_id,
        texto=_clean_text(payload.get("texto") or payload.get("TextoIntegral")),
        texto_status=_string(payload.get("texto_status")),
        forma=_string(payload.get("forma")),
        metodo_obtencao=_string(payload.get("metodo_obtencao")),
        url_texto=_string(fontes.get("escriba_html")),
        url_audio=_first_list_item(fontes.get("audios")),
        url_video=_string(event.get("urlRegistro")) or _first_list_item(fontes.get("videos")),
        url_origem=_string(event.get("uri") or fontes.get("evento_api")),
        fontes=fontes,
    )


def _normalize_parecer_pec(record: dict[str, Any], *, raw_path: Path, data_root: Path) -> dict[str, Any]:
    payload = _dict(record.get("payload"))
    source = str(record.get("source") or "")
    metadata = _dict(payload.get("metadata"))
    fontes = _dict(payload.get("fontes"))
    colegiado = _dict(payload.get("colegiado"))
    texto = _clean_text(payload.get("texto") or payload.get("TextoIntegral"))

    if source == "senado":
        processo = _dict(metadata.get("processo"))
        documento = _dict(metadata.get("documento"))
        data_hora = _string(
            _first(documento, "dataDocumento", "dataRecebimento")
            or _first(processo, "dataApresentacao", "dataDeliberacao")
        )
        proposicao_sigla, proposicao_numero, proposicao_ano = _split_identificacao_pec(
            _string(payload.get("IdentificacaoPec") or processo.get("identificacao"))
        )
        proposicao_id = _string(payload.get("IdProcesso") or processo.get("id"))
        materia_id = _string(payload.get("CodigoMateria") or processo.get("codigoMateria"))
        documento_id = _string(payload.get("IdDocumento") or documento.get("id"))
        identificacao = _string(payload.get("IdentificacaoPec") or processo.get("identificacao"))
        resumo = _string(processo.get("ementa"))
        url_origem = _string(fontes.get("processo") or processo.get("urlDocumento"))
    else:
        proposicao = _dict(metadata.get("proposicao"))
        detalhe = _dict(metadata.get("detalhe"))
        tramitacao = _dict(metadata.get("tramitacao"))
        data_hora = _string(tramitacao.get("dataHora") or proposicao.get("dataApresentacao") or detalhe.get("dataApresentacao"))
        proposicao_sigla = _string(payload.get("SiglaTipo") or proposicao.get("siglaTipo") or detalhe.get("siglaTipo"))
        proposicao_numero = _string(payload.get("Numero") or proposicao.get("numero") or detalhe.get("numero"))
        proposicao_ano = _string(payload.get("Ano") or proposicao.get("ano") or detalhe.get("ano"))
        proposicao_id = _string(payload.get("IdProposicao") or proposicao.get("id") or detalhe.get("id"))
        materia_id = None
        documento_id = _string(tramitacao.get("sequencia") or tramitacao.get("url") or record.get("source_id"))
        identificacao = _format_identificacao(proposicao_sigla, proposicao_numero, proposicao_ano)
        resumo = _string(detalhe.get("ementa") or proposicao.get("ementa"))
        url_origem = _string(fontes.get("proposicao_detalhe") or fontes.get("proposicao"))

    return _finalize_record(
        record,
        raw_path=raw_path,
        data_root=data_root,
        texto_id=f"{source}:pareceres_pec:parecer:{record.get('source_id')}",
        casa="Senado Federal" if source == "senado" else "Camara dos Deputados",
        ambito=_string(colegiado.get("ambito")) or "indeterminado",
        orgao_sigla=_string(colegiado.get("sigla")),
        orgao_nome=_string(colegiado.get("nome")),
        documento_tipo="parecer_pec",
        unidade_analitica="parecer",
        data_hora=data_hora,
        titulo=identificacao,
        resumo=resumo,
        proposicao_id=proposicao_id,
        materia_id=materia_id,
        documento_id=documento_id,
        proposicao_sigla=proposicao_sigla,
        proposicao_numero=proposicao_numero,
        proposicao_ano=proposicao_ano,
        proposicao_identificacao=identificacao,
        documento_classe=_string(payload.get("documento_classe")),
        status_deliberativo=_string(payload.get("status_deliberativo")),
        vencido=payload.get("vencido"),
        texto=texto,
        texto_status=_string(payload.get("texto_status")),
        forma=_string(payload.get("forma")),
        metodo_obtencao=_string(payload.get("metodo_obtencao")),
        url_texto=_string(payload.get("TextoIntegralUrl") or fontes.get("documento")),
        url_origem=url_origem,
        fontes=fontes,
    )


def _finalize_record(
    raw_record: dict[str, Any],
    *,
    raw_path: Path,
    data_root: Path,
    texto_id: str,
    casa: str,
    ambito: str,
    orgao_sigla: str | None,
    orgao_nome: str | None,
    documento_tipo: str,
    unidade_analitica: str,
    texto: str | None,
    data: str | None = None,
    data_hora: str | None = None,
    fontes: dict[str, Any] | None = None,
    **values: Any,
) -> dict[str, Any]:
    normalized_text = _clean_text(texto)
    normalized_date = _date_part(data_hora) or _date_part(data) or _date_from_partition(_string(raw_record.get("partition")))
    year, month = _year_month(normalized_date)
    response = _dict(raw_record.get("response"))
    record = {field: None for field in PROCESSED_FIELDS}
    record.update(
        {
            "texto_id": texto_id,
            "dataset_version": DATASET_VERSION,
            "source": raw_record.get("source"),
            "dataset": raw_record.get("dataset"),
            "casa": casa,
            "ambito": ambito,
            "orgao_sigla": orgao_sigla,
            "orgao_nome": orgao_nome,
            "documento_tipo": documento_tipo,
            "unidade_analitica": unidade_analitica,
            "data": normalized_date,
            "data_hora": data_hora,
            "ano": year,
            "mes": month,
            "texto": normalized_text,
            "texto_tamanho": len(normalized_text or ""),
            "fontes": fontes or {},
            "raw_run_id": raw_record.get("run_id"),
            "raw_record_type": raw_record.get("record_type"),
            "raw_source_id": raw_record.get("source_id"),
            "raw_partition": raw_record.get("partition"),
            "raw_collected_at": raw_record.get("collected_at"),
            "raw_checksum": raw_record.get("checksum"),
            "raw_path": _relative_path(raw_path, data_root),
            "raw_response_url": response.get("url"),
        }
    )
    for key, value in values.items():
        if key in record:
            record[key] = value
    return record


def _colegiado_senado(value: dict[str, Any]) -> dict[str, Any]:
    for key in ("colegiadoCriador", "colegiados", "ColegiadoCriador", "Colegiados"):
        item = value.get(key)
        if isinstance(item, dict):
            return item
    return {}


def _senado_video_url(value: dict[str, Any]) -> str | None:
    videos = value.get("videos") or value.get("Videos")
    if isinstance(videos, dict):
        return _string(videos.get("url") or videos.get("Url"))
    if isinstance(videos, list):
        for item in videos:
            if isinstance(item, dict):
                url = _string(item.get("url") or item.get("Url"))
                if url:
                    return url
    return None


def _first_orgao_camara(event: dict[str, Any]) -> dict[str, Any]:
    orgaos = event.get("orgaos")
    if isinstance(orgaos, list):
        for orgao in orgaos:
            if isinstance(orgao, dict):
                return orgao
    if isinstance(orgaos, dict):
        return orgaos
    return {}


def _tipo_uso_palavra(pronunciamento: dict[str, Any]) -> str | None:
    value = pronunciamento.get("TipoUsoPalavra") or pronunciamento.get("tipoUsoPalavra")
    if isinstance(value, dict):
        return _string(value.get("Descricao") or value.get("descricao") or value.get("Sigla") or value.get("sigla"))
    return _string(value)


def _extract_deputado_id(source_id: str) -> str | None:
    match = re.search(r"deputado:(\d+):", source_id)
    return match.group(1) if match else None


def _id_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    match = re.search(r"/(\d+)(?:\D*)?$", uri)
    return match.group(1) if match else None


def _camara_discurso_id(
    *,
    deputado_id: str | None,
    evento_id: str | None,
    data_hora: str | None,
    tipo_discurso: str | None,
    index: int,
    texto_hash: str,
) -> str:
    if deputado_id and (evento_id or data_hora):
        return (
            "camara:plenario_discursos:"
            f"deputado:{deputado_id}:"
            f"evento:{evento_id or 'sem-evento'}:"
            f"inicio:{data_hora or 'sem-data'}:"
            f"tipo:{_slug(tipo_discurso) or 'sem-tipo'}:"
            f"ordem:{index}"
        )
    return f"camara:plenario_discursos:discurso:sha1:{texto_hash}"


def _split_identificacao_pec(value: str | None) -> tuple[str | None, str | None, str | None]:
    if not value:
        return None, None, None
    match = re.search(r"\b([A-Z]+)\s+(\d+)\s*/\s*(\d{4})\b", value.upper())
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None


def _format_identificacao(sigla: str | None, numero: str | None, ano: str | None) -> str | None:
    if sigla and numero and ano:
        return f"{sigla} {numero}/{ano}"
    return None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text or None


def _date_part(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def _date_from_partition(value: str | None) -> str:
    if value and re.fullmatch(r"\d{4}-\d{2}", value):
        return f"{value}-01"
    return "0000-00-00"


def _year_month(value: str | None) -> tuple[str, str]:
    if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value[:4], value[5:7]
    return "0000", "00"


def _first_list_item(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            text = _string(item)
            if text:
                return text
        return None
    return _string(value)


def _slug(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _sort_newest_first(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (_mtime(path), path.as_posix()), reverse=True)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


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


if __name__ == "__main__":
    main()
