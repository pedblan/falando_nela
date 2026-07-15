from __future__ import annotations

import argparse
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Sequence

from pypdf import PdfReader

from coleta.common.cli import build_parser, runtime_config_from_namespace
from coleta.common.http import OpenDataClient
from coleta.common.io import CollectionRun, error_summary, listify


SOURCE = "senado"
DATASET = "congresso_discursos"
HOUSE = "CN"
DIARIOS_BASE_URL = "https://legis.senado.leg.br/"
DIARY_LOOKUP_PATH = "diarios/BuscaDiario"
DIARY_PAGES_PATH = "diarios/BuscaPaginasDiario"
DIARY_TYPE_CONGRESSO = 2
PAGES_PER_REQUEST = 20
MAX_PAGES_PER_SPEECH = 100
RECOVERY_STRATEGY = "diario-congresso-oficial-por-codigo-v1"


def build_recovery_parser() -> argparse.ArgumentParser:
    parser = build_parser(
        "Recupera textos de pronunciamentos CN a partir do Diario do Congresso Nacional."
    )
    parser.add_argument(
        "--population-path",
        required=True,
        help="JSONL de CodigoPronunciamento sem texto, produzido pelo caderno de recuperacao.",
    )
    return parser


def collect(argv: Sequence[str] | None = None) -> Path:
    parser = build_recovery_parser()
    args = parser.parse_args(argv)
    runtime = runtime_config_from_namespace(parser, args)
    population_path = Path(args.population_path).expanduser()
    if not population_path.is_file():
        parser.error(f"--population-path ausente: {population_path}")

    population = load_population(
        population_path,
        start=runtime.data_inicio,
        end=runtime.data_fim,
    )
    if runtime.sample:
        population = population[: runtime.sample_limit or 5]
    years = {record["data"][:4] for record in population}
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
        existing_record_years=years,
    )
    by_partition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in population:
        by_partition[record["data"][:7]].append(record)

    status = "completed"
    errors = 0
    stats: Counter[str] = Counter()
    run.write_record(
        partition="metadata",
        source_id=(
            f"CN:diario-congresso-recovery-population:{len(population)}:"
            f"{runtime.data_inicio.isoformat()}:{runtime.data_fim.isoformat()}"
        ),
        request={"method": "READ_JSONL", "path": str(population_path), "params": {}},
        response={"status_code": 200, "source": "fixed_missing_text_population"},
        periodo={
            "data_inicio": runtime.data_inicio.isoformat(),
            "data_fim": runtime.data_fim.isoformat(),
        },
        payload={
            "strategy": RECOVERY_STRATEGY,
            "house": HOUSE,
            "dataset": DATASET,
            "population_path": str(population_path),
            "population": len(population),
            "codes": [record["codigo_pronunciamento"] for record in population],
        },
        record_type="diario_congresso_recovery_population",
    )

    try:
        with OpenDataClient(DIARIOS_BASE_URL, min_interval_seconds=0.11) as client:
            for partition, records in sorted(by_partition.items()):
                if run.should_skip_partition(partition):
                    stats["partitions_skipped"] += 1
                    run.log("partition_skipped", partition=partition)
                    continue
                partition_errors = 0
                run.log("partition_started", partition=partition, population=len(records))
                for index, record in enumerate(records, start=1):
                    code = record["codigo_pronunciamento"]
                    source_id = f"CN:pronunciamento:{code}:diario-congresso"
                    if run.has_record(source_id=source_id, record_type="pronunciamento_texto"):
                        stats["resume_skipped"] += 1
                        continue
                    try:
                        payload, request, response = recover_pronunciamento_texto(client, record)
                    except Exception as exc:
                        partition_errors += 1
                        errors += 1
                        run.log(
                            "pronunciamento_failed",
                            partition=partition,
                            codigo_pronunciamento=code,
                            error=error_summary(exc),
                        )
                        continue
                    written = run.write_record(
                        partition=partition,
                        source_id=source_id,
                        request=request,
                        response=response,
                        periodo={"data_inicio": record["data"], "data_fim": record["data"]},
                        payload=payload,
                        record_type="pronunciamento_texto",
                    )
                    stats["pronunciamentos_written"] += int(written)
                    if written:
                        stats["texto_disponivel"] += 1
                    if index == 1 or index % 10 == 0 or index == len(records):
                        run.log(
                            "recovery_progress",
                            partition=partition,
                            processed=index,
                            total=len(records),
                            written=stats["pronunciamentos_written"],
                            errors=errors,
                        )
                        run.write_autosave(
                            status="running",
                            population=len(population),
                            **dict(stats),
                            errors=errors,
                        )
                if partition_errors:
                    status = "completed_with_errors"
                    run.mark_partition_failed(
                        partition,
                        population=len(records),
                        errors=partition_errors,
                    )
                else:
                    run.mark_partition_complete(partition, population=len(records))
    except Exception as exc:
        status = "failed"
        errors += 1
        run.log("run_failed", error=error_summary(exc, include_traceback=True))
    finally:
        run.write_manifest(
            data_inicio=runtime.data_inicio.isoformat(),
            data_fim=runtime.data_fim.isoformat(),
            mode=runtime.mode,
            sample=runtime.sample,
            sample_limit=runtime.sample_limit,
            house=HOUSE,
            dataset=DATASET,
            strategy=RECOVERY_STRATEGY,
            population_path=str(population_path),
            population=len(population),
            **dict(stats),
            status=status,
            errors=errors,
        )
        print(run.manifest_path)
    return run.manifest_path


def load_population(path: Path, *, start: date, end: date) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for line_number, record in enumerate(iter_jsonl(path), start=1):
        if record.get("house") != HOUSE or record.get("dataset") != DATASET:
            continue
        code = _string(record.get("codigo_pronunciamento"))
        value_date = _parse_date(record.get("data"))
        pronunciamento = record.get("pronunciamento")
        if not code or value_date is None or not isinstance(pronunciamento, dict):
            raise ValueError(f"Registro de população inválido na linha {line_number}: {record!r}")
        if not start <= value_date <= end:
            continue
        publication = select_congress_publication(pronunciamento)
        speaker = _string(_first(pronunciamento, "NomeAutor", "NomeParlamentar", "Autor"))
        if not speaker:
            raise ValueError(f"Nome do orador ausente para CodigoPronunciamento={code}")
        normalized = {
            "codigo_pronunciamento": code,
            "data": value_date.isoformat(),
            "house": HOUSE,
            "dataset": DATASET,
            "pronunciamento": pronunciamento,
            "publication": publication,
            "speaker": speaker,
        }
        previous = by_code.get(code)
        if previous and previous != normalized:
            raise ValueError(f"CodigoPronunciamento duplicado com divergência: {code}")
        by_code[code] = normalized
    if not by_code:
        raise ValueError(
            f"Nenhum item CN para recuperar em {start.isoformat()}..{end.isoformat()}"
        )
    return sorted(by_code.values(), key=lambda row: (row["data"], _code_sort_key(row["codigo_pronunciamento"])))


def select_congress_publication(pronunciamento: dict[str, Any]) -> dict[str, Any]:
    publications = _get(pronunciamento, "Publicacoes", "Publicacao")
    candidates: list[dict[str, Any]] = []
    for publication in listify(publications):
        if not isinstance(publication, dict):
            continue
        source = _string(_first(publication, "SiglaFonte", "DescricaoVeiculoPublicacao"))
        if source and _normalize(source) == "DCN":
            candidates.append(publication)
    if len(candidates) != 1:
        raise ValueError(
            "Esperada exatamente uma publicação DCN para "
            f"CodigoPronunciamento={_first(pronunciamento, 'CodigoPronunciamento')}: {candidates!r}"
        )
    publication = candidates[0]
    published_on = _parse_date(_first(publication, "DataPublicacao"))
    page = _parse_page(_first(publication, "PaginaInicial", "NumeroPagInicioPublicacao"))
    if published_on is None or page is None:
        raise ValueError(f"Publicação DCN sem data/página: {publication!r}")
    return {
        "sigla_fonte": "DCN",
        "data_publicacao": published_on.isoformat(),
        "pagina_inicial": page,
        "url_diario_original": _string(_first(publication, "UrlDiario")),
    }


def recover_pronunciamento_texto(
    client: OpenDataClient,
    record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    publication = record["publication"]
    diary = lookup_congress_diary(client, publication)
    page_start = int(publication["pagina_inicial"])
    page_end = page_start + PAGES_PER_REQUEST - 1
    max_page = int(diary["pagina_final"])
    extracted_pages: list[str] = []
    response_metadata: dict[str, Any] | None = None
    while page_start <= max_page and page_start < int(publication["pagina_inicial"]) + MAX_PAGES_PER_SPEECH:
        current_end = min(page_end, max_page)
        pages, response_metadata = download_diary_pages(
            client,
            codigo_diario=diary["codigo_diario"],
            page_start=page_start,
            page_end=current_end,
        )
        extracted_pages.extend(pages)
        text = extract_speaker_text("\n\f\n".join(extracted_pages), record["speaker"])
        if text is not None:
            return build_payload(
                record,
                diary=diary,
                text=text,
                pages_downloaded=[int(publication["pagina_inicial"]), current_end],
            ), {
                "method": "GET",
                "path": DIARY_PAGES_PATH,
                "params": {
                    "codDiario": diary["codigo_diario"],
                    "paginaInicial": int(publication["pagina_inicial"]),
                    "paginaFinal": current_end,
                },
            }, response_metadata
        page_start = current_end + 1
        page_end = page_start + PAGES_PER_REQUEST - 1
    raise ValueError(
        f"Não foi possível delimitar o texto de {record['speaker']!r} para "
        f"CodigoPronunciamento={record['codigo_pronunciamento']} no DCN {diary['codigo_diario']}"
    )


def lookup_congress_diary(client: OpenDataClient, publication: dict[str, Any]) -> dict[str, Any]:
    published_on = _parse_date(publication["data_publicacao"])
    assert published_on is not None
    params = {
        "tipDiario": DIARY_TYPE_CONGRESSO,
        "datDiario": published_on.strftime("%d/%m/%Y"),
        "paginaDireta": publication["pagina_inicial"],
    }
    result = client.get_text(DIARY_LOOKUP_PATH, params=params)
    match = re.search(r"var\s+diario\s*=\s*(\{.*?\});", str(result.data), flags=re.DOTALL)
    if not match:
        raise ValueError(f"Metadados do diário não encontrados em {result.url}")
    payload = json.loads(match.group(1))
    caderno = payload.get("caderno") if isinstance(payload, dict) else None
    if not isinstance(caderno, dict):
        raise ValueError(f"Caderno inválido em {result.url}")
    vehicle = _string(caderno.get("sglVeiculo"))
    code = _string(caderno.get("codigo"))
    page_final = _parse_page(caderno.get("paginaFinal"))
    if vehicle != "DCN" or not code or page_final is None:
        raise ValueError(f"Busca DCN retornou diário incompatível: {caderno!r}")
    return {
        "codigo_diario": code,
        "titulo": _string(payload.get("tituloCurto")) or f"DCN/{code}",
        "pagina_final": page_final,
        "url": result.url,
        "data_publicacao": publication["data_publicacao"],
    }


def download_diary_pages(
    client: OpenDataClient,
    *,
    codigo_diario: str,
    page_start: int,
    page_end: int,
) -> tuple[list[str], dict[str, Any]]:
    result = client.get_bytes(
        DIARY_PAGES_PATH,
        params={
            "codDiario": codigo_diario,
            "paginaInicial": page_start,
            "paginaFinal": page_end,
        },
    )
    try:
        reader = PdfReader(io.BytesIO(result.data))
    except Exception as exc:
        raise ValueError(f"PDF oficial inválido para diário {codigo_diario}") from exc
    pages = [page.extract_text() or "" for page in reader.pages]
    if not any(page.strip() for page in pages):
        raise ValueError(f"PDF oficial sem camada textual para diário {codigo_diario}")
    return pages, result.response_metadata


def extract_speaker_text(document_text: str, speaker: str) -> str | None:
    normalized_document = _normalize(document_text)
    normalized_speaker = _normalize(speaker)
    start_pattern = re.compile(
        rf"(?:^|\n)\s*(?:O|A)\s+S(?:R|RA)\.\s+{re.escape(normalized_speaker)}\s*(?=\(|[-–])",
        flags=re.MULTILINE,
    )
    start = start_pattern.search(normalized_document)
    if not start:
        return None
    next_speaker = re.compile(
        r"(?:^|\n)\s*(?:O|A)\s+S(?:R|RA)\.\s+[^\n]{1,180}?\s*(?=\(|[-–])",
        flags=re.MULTILINE,
    ).search(normalized_document, start.end())
    end = next_speaker.start() if next_speaker else len(normalized_document)
    text = document_text[start.start() : end].strip()
    if len(text) < 80:
        raise ValueError(f"Trecho recuperado muito curto para orador {speaker!r}")
    return text


def build_payload(
    record: dict[str, Any],
    *,
    diary: dict[str, Any],
    text: str,
    pages_downloaded: list[int],
) -> dict[str, Any]:
    code = record["codigo_pronunciamento"]
    publication = record["publication"]
    diary_pdf_url = (
        DIARIOS_BASE_URL
        + DIARY_PAGES_PATH
        + f"?codDiario={diary['codigo_diario']}&paginaInicial={pages_downloaded[0]}"
        + f"&paginaFinal={pages_downloaded[1]}"
    )
    return {
        "CodigoPronunciamento": code,
        "TextoIntegral": text,
        "TextoIntegralUrl": diary_pdf_url,
        "codigo_pronunciamento": code,
        "metadata": {
            "sessao": {},
            "pronunciamento": record["pronunciamento"],
            "diario_congresso_recovery": {
                "strategy": RECOVERY_STRATEGY,
                "codigo_pronunciamento": code,
                "speaker_for_segment_boundary": record["speaker"],
                "publication": publication,
                "diary": diary,
                "pages_downloaded": pages_downloaded,
            },
        },
        "texto": text,
        "forma": "texto",
        "metodo_obtencao": RECOVERY_STRATEGY,
        "texto_status": "disponivel",
        "fontes": {
            "texto_integral_txt": diary_pdf_url,
            "diario_congresso": diary_pdf_url,
            "url_diario_original": publication.get("url_diario_original"),
        },
    }


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido em {path}, linha {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Registro não é objeto em {path}, linha {line_number}")
            yield record


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return without_diacritics.upper()


def _get(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> date | None:
    text = _string(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            day, month, year = text.split("/")
            return date(int(year), int(month), int(day))
        except ValueError:
            return None


def _parse_page(value: Any) -> int | None:
    text = _string(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _code_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**18, value)


if __name__ == "__main__":
    collect()
