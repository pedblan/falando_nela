from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any


INVENTORY_CODE_VERSION = 3


OLD_PARQUET_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "house": (
        "casa",
        "house",
        "arena",
        "origem",
        "source",
        "fonte",
    ),
    "date": (
        "data_hora",
        "dataHoraInicio",
        "data_pronunciamento",
        "DataPronunciamento",
        "data_discurso",
        "data",
        "date",
    ),
    "text": (
        "texto",
        "TextoIntegral",
        "transcricao",
        "discurso",
        "speech",
    ),
    "speech_id": (
        "pronunciamento_id",
        "codigo_pronunciamento",
        "CodigoPronunciamento",
        "discurso_id",
        "id_discurso",
        "texto_id",
        "id",
    ),
    "speaker_name": (
        "parlamentar_nome",
        "nome_parlamentar",
        "NomeAutor",
        "orador",
        "autor",
        "nome",
    ),
    "speaker_id": (
        "parlamentar_id",
        "id_parlamentar",
        "CodigoParlamentar",
        "codigo_parlamentar",
        "deputado_id",
        "id_deputado",
    ),
    "event_id": (
        "evento_id",
        "id_evento",
        "CodigoSessao",
        "codigo_sessao",
        "sessao_id",
    ),
    "speech_type": (
        "tipo_discurso",
        "tipoDiscurso",
        "TipoPronunciamento",
        "tipo_pronunciamento",
        "fase_evento",
    ),
    "video_url": (
        "url_video",
        "urlVideo",
        "video_url",
        "video",
    ),
    "audio_url": (
        "url_audio",
        "urlAudio",
        "audio_url",
    ),
    "text_method": (
        "metodo_obtencao",
        "metodo_transcricao",
        "origem_texto",
        "forma",
    ),
}


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Lê um JSONL bruto e falha com indicação precisa da linha inválida."""

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


def scan_senado_transcription_queue(
    data_root: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Inventaria a fila raw do Senado sem transformar mídia em texto analítico."""

    queue_root = (
        Path(data_root)
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "transcription_queue"
    )
    if not queue_root.is_dir():
        return []

    candidates: dict[str, dict[str, Any]] = {}
    paths = sorted(queue_root.rglob("*.jsonl"))
    for file_index, path in enumerate(paths, start=1):
        for record in iter_jsonl(path):
            if record.get("record_type") != "transcription_queue":
                continue
            payload = _mapping(record.get("payload"))
            if _has_text(payload.get("texto") or payload.get("TextoIntegral")):
                continue
            code = _string(
                payload.get("codigo_pronunciamento")
                or payload.get("CodigoPronunciamento")
                or _speech_code_from_source_id(record.get("source_id"))
            )
            if not code:
                continue

            fontes = _mapping(payload.get("fontes"))
            media_url, media_source, granularity = _senado_preferred_media(fontes)
            if not media_url:
                continue
            metadata = _mapping(payload.get("metadata"))
            pronunciamento = _mapping(metadata.get("pronunciamento"))
            sessao = _mapping(metadata.get("sessao"))
            periodo = _mapping(record.get("periodo"))
            date_value = _first_string(
                pronunciamento,
                "DataPronunciamento",
                "Data",
                "DataHoraInicio",
            ) or _first_string(sessao, "DataSessao", "Data") or _string(
                periodo.get("data_inicio")
            )
            candidate_id = f"senado:plenario_discursos:pronunciamento:{code}"
            row = {
                "candidate_id": candidate_id,
                "house": "senado",
                "dataset": "plenario_discursos",
                "speech_id": code,
                "date": date_value,
                "year": _year(date_value),
                "speaker_id": _first_string(
                    pronunciamento,
                    "CodigoParlamentar",
                    "CodigoAutor",
                    "codigoParlamentar",
                ),
                "speaker_name": _first_string(
                    pronunciamento,
                    "NomeAutor",
                    "NomeParlamentar",
                    "nomeAutor",
                ),
                "event_id": _first_string(sessao, "CodigoSessao", "codigoSessao"),
                "media_url": media_url,
                "media_source": media_source,
                "media_granularity": granularity,
                "needs_alignment": granularity != "speech",
                "eligible_for_asr": granularity == "speech",
                "texto_status": _string(payload.get("texto_status")),
                "metodo_obtencao": _string(payload.get("metodo_obtencao")),
                "raw_run_id": _string(record.get("run_id")),
                "raw_source_id": _string(record.get("source_id")),
                "raw_path": _relative_path(path, Path(data_root)),
                "raw_occurrences": 1,
                "fontes": fontes,
            }
            previous = candidates.get(candidate_id)
            if previous is None:
                candidates[candidate_id] = row
            else:
                row["raw_occurrences"] = int(previous["raw_occurrences"]) + 1
                if _media_priority(row) >= _media_priority(previous):
                    candidates[candidate_id] = row
                else:
                    previous["raw_occurrences"] = row["raw_occurrences"]

        if progress and (file_index == 1 or file_index % 25 == 0 or file_index == len(paths)):
            progress(f"Senado: {file_index}/{len(paths)} arquivos; {len(candidates)} candidatos")

    return sorted(candidates.values(), key=_candidate_sort_key)


def scan_camara_media_candidates(
    data_root: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Encontra discursos da Câmara com mídia, mas sem transcrição na fotografia raw.

    O mesmo item pode reaparecer em runs diferentes. Se alguma ocorrência já
    trouxer ``transcricao``, a unidade é tratada como resolvida e sai da fila.
    """

    corpus_root = Path(data_root) / "raw" / "camara" / "plenario_discursos"
    if not corpus_root.is_dir():
        return []

    candidates: dict[str, dict[str, Any]] = {}
    text_available_keys: set[str] = set()
    items_seen = 0
    text_occurrences = 0
    empty_text_occurrences = 0
    empty_text_with_media_occurrences = 0
    paths = sorted(
        path
        for path in corpus_root.glob("ano=*/mes=*/*.jsonl")
        if path.is_file()
    )
    for file_index, path in enumerate(paths, start=1):
        for record in iter_jsonl(path):
            if record.get("record_type") != "discursos_page":
                continue
            payload = _mapping(record.get("payload"))
            data = payload.get("dados")
            if not isinstance(data, list):
                continue
            deputy_id = _deputy_id_from_source_id(record.get("source_id"))
            for item in data:
                if not isinstance(item, dict):
                    continue
                items_seen += 1
                unit_key = _camara_unit_key(item, deputy_id=deputy_id)
                if _has_text(item.get("transcricao")):
                    text_occurrences += 1
                    text_available_keys.add(unit_key)
                    continue
                empty_text_occurrences += 1
                media_url, media_source = _camara_preferred_media(item)
                if not media_url:
                    continue
                empty_text_with_media_occurrences += 1

                date_value = _string(item.get("dataHoraInicio"))
                event_uri = _string(item.get("uriEvento"))
                candidate_id = f"camara:plenario_discursos:discurso:{unit_key}"
                fase_evento = _mapping(item.get("faseEvento"))
                row = {
                    "candidate_id": candidate_id,
                    "house": "camara",
                    "dataset": "plenario_discursos",
                    "speech_id": unit_key,
                    "date": date_value,
                    "year": _year(date_value),
                    "speaker_id": deputy_id,
                    "speaker_name": None,
                    "event_id": _trailing_id(event_uri),
                    "media_url": media_url,
                    "media_source": media_source,
                    "media_granularity": "speech",
                    "needs_alignment": False,
                    "eligible_for_asr": True,
                    "texto_status": "ausente",
                    "metodo_obtencao": "pendente_transcricao_audio_video",
                    "raw_run_id": _string(record.get("run_id")),
                    "raw_source_id": _string(record.get("source_id")),
                    "raw_path": _relative_path(path, Path(data_root)),
                    "raw_occurrences": 1,
                    "tipo_discurso": _string(item.get("tipoDiscurso")),
                    "fase_evento": _string(fase_evento.get("titulo")),
                    "sumario": _string(item.get("sumario")),
                    "fontes": {
                        "urlAudio": item.get("urlAudio"),
                        "urlTexto": item.get("urlTexto"),
                        "urlVideo": item.get("urlVideo"),
                        "uriEvento": item.get("uriEvento"),
                    },
                }
                previous = candidates.get(candidate_id)
                if previous is None:
                    candidates[candidate_id] = row
                else:
                    row["raw_occurrences"] = int(previous["raw_occurrences"]) + 1
                    if _media_priority(row) >= _media_priority(previous):
                        candidates[candidate_id] = row
                    else:
                        previous["raw_occurrences"] = row["raw_occurrences"]

        if progress and (file_index == 1 or file_index % 25 == 0 or file_index == len(paths)):
            pending_unique = sum(
                row["speech_id"] not in text_available_keys for row in candidates.values()
            )
            progress(
                f"Câmara: {file_index}/{len(paths)} arquivos; itens={items_seen}; "
                f"com_texto={text_occurrences}; sem_texto={empty_text_occurrences}; "
                f"sem_texto_com_midia={empty_text_with_media_occurrences}; "
                f"pendentes_unicos={pending_unique}"
            )

    rows = [
        row
        for candidate_id, row in candidates.items()
        if candidate_id.rsplit(":", 1)[-1] not in text_available_keys
    ]
    return sorted(rows, key=_candidate_sort_key)


def audit_camara_transcription_coverage(
    data_root: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Mede, por ano, a cobertura textual das unidades audiovisuais da Câmara.

    A auditoria distingue ocorrências raw de unidades únicas. Uma unidade com
    mídia só permanece pendente quando nenhuma de suas ocorrências contém
    ``transcricao``. Arquivos de ``metadata/`` não fazem parte do corpus e não
    são lidos.
    """

    corpus_root = Path(data_root) / "raw" / "camara" / "plenario_discursos"
    if not corpus_root.is_dir():
        return []

    paths = sorted(
        path
        for path in corpus_root.glob("ano=*/mes=*/*.jsonl")
        if path.is_file()
    )
    buckets: dict[int | None, dict[str, Any]] = {}
    items_seen = 0
    text_occurrences = 0
    media_occurrences = 0

    for file_index, path in enumerate(paths, start=1):
        partition_year = _partition_year(path)
        for record in iter_jsonl(path):
            if record.get("record_type") != "discursos_page":
                continue
            payload = _mapping(record.get("payload"))
            data = payload.get("dados")
            if not isinstance(data, list):
                continue
            deputy_id = _deputy_id_from_source_id(record.get("source_id"))
            for item in data:
                if not isinstance(item, dict):
                    continue
                items_seen += 1
                year = _year(_string(item.get("dataHoraInicio"))) or partition_year
                bucket = buckets.setdefault(year, _new_camara_coverage_bucket())
                unit_key = _camara_unit_key(item, deputy_id=deputy_id)
                has_text = _has_text(item.get("transcricao"))
                media_url, _ = _camara_preferred_media(item)
                has_media = bool(media_url)

                bucket["item_occurrences"] += 1
                bucket["unique_units"].add(unit_key)
                if has_text:
                    text_occurrences += 1
                    bucket["text_occurrences"] += 1
                    bucket["unique_units_with_text"].add(unit_key)
                else:
                    bucket["empty_text_occurrences"] += 1

                if has_media:
                    media_occurrences += 1
                    bucket["media_occurrences"] += 1
                    bucket["unique_units_with_media"].add(unit_key)
                    if has_text:
                        bucket["media_with_text_occurrences"] += 1
                    else:
                        bucket["media_without_text_occurrences"] += 1
                        bucket["unique_blank_units_with_media"].add(unit_key)

        if progress and (file_index == 1 or file_index % 25 == 0 or file_index == len(paths)):
            progress(
                f"Cobertura Câmara: {file_index}/{len(paths)} arquivos; "
                f"itens={items_seen}; com_texto={text_occurrences}; "
                f"com_midia={media_occurrences}"
            )

    rows: list[dict[str, Any]] = []
    for year in sorted(buckets, key=lambda value: (value is None, value or 0)):
        bucket = buckets[year]
        unique_units = bucket["unique_units"]
        unique_with_text = bucket["unique_units_with_text"]
        unique_with_media = bucket["unique_units_with_media"]
        unique_media_and_text = unique_with_media & unique_with_text
        unique_pending = bucket["unique_blank_units_with_media"] - unique_with_text
        rows.append(
            {
                "year": year,
                "files_total": len(paths),
                "item_occurrences": bucket["item_occurrences"],
                "text_occurrences": bucket["text_occurrences"],
                "empty_text_occurrences": bucket["empty_text_occurrences"],
                "media_occurrences": bucket["media_occurrences"],
                "media_with_text_occurrences": bucket["media_with_text_occurrences"],
                "media_without_text_occurrences": bucket["media_without_text_occurrences"],
                "unique_units": len(unique_units),
                "unique_units_with_text": len(unique_with_text),
                "unique_units_with_media": len(unique_with_media),
                "unique_units_with_media_and_text": len(unique_media_and_text),
                "unique_pending_media_transcription": len(unique_pending),
                "text_coverage_rate": (
                    len(unique_with_text) / len(unique_units) if unique_units else None
                ),
                "media_text_coverage_rate": (
                    len(unique_media_and_text) / len(unique_with_media)
                    if unique_with_media
                    else None
                ),
            }
        )
    return rows


def select_probe_sample(
    candidates: Sequence[dict[str, Any]],
    *,
    max_per_house: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Seleciona amostra reproduzível, priorizando mídia do pronunciamento."""

    if max_per_house < 1:
        raise ValueError("max_per_house deve ser positivo")
    selected: list[dict[str, Any]] = []
    houses = sorted({_string(row.get("house")) for row in candidates if row.get("house")})
    for house in houses:
        pool = [row for row in candidates if _string(row.get("house")) == house]
        ranked = sorted(
            pool,
            key=lambda row: (
                0 if row.get("eligible_for_asr") else 1,
                0 if row.get("media_source") == "audio" else 1,
                sha256(f"{seed}:{row.get('candidate_id')}".encode("utf-8")).hexdigest(),
            ),
        )
        selected.extend(dict(row) for row in ranked[:max_per_house])
    return selected


def infer_old_parquet_columns(columns: Iterable[str]) -> dict[str, str]:
    """Infere campos canônicos sem assumir o schema do Parquet legado."""

    available = list(columns)
    normalized = {_normalized_name(column): column for column in available}
    inferred: dict[str, str] = {}
    for canonical, aliases in OLD_PARQUET_COLUMN_ALIASES.items():
        for alias in aliases:
            match = normalized.get(_normalized_name(alias))
            if match is not None:
                inferred[canonical] = match
                break
    return inferred


def validate_parquet_magic(
    path: Path,
    *,
    expected_size: int | None = None,
) -> dict[str, Any]:
    """Recusa páginas HTML ou downloads truncados antes de abrir o Parquet."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if expected_size is not None and size != expected_size:
        raise ValueError(f"Tamanho inesperado: {size}; esperado: {expected_size}")
    if size < 8:
        raise ValueError(f"Arquivo pequeno demais para Parquet: {size} bytes")
    with path.open("rb") as handle:
        header = handle.read(4)
        handle.seek(-4, 2)
        footer = handle.read(4)
    if header != b"PAR1" or footer != b"PAR1":
        raise ValueError(
            f"Arquivo não é um Parquet íntegro: header={header!r}, footer={footer!r}"
        )
    return {"path": str(path), "size_bytes": size, "header": "PAR1", "footer": "PAR1"}


def _senado_preferred_media(fontes: dict[str, Any]) -> tuple[str | None, str | None, str]:
    direct_video = _string(fontes.get("video"))
    if direct_video:
        return direct_video, "video", "speech"
    session_api = _string(fontes.get("videos_sessao_api"))
    if session_api:
        return session_api, "session_video_api", "session"
    binary = _string(fontes.get("texto_binario"))
    if binary:
        return binary, "official_binary", "unknown"
    return None, None, "unknown"


def _camara_preferred_media(item: dict[str, Any]) -> tuple[str | None, str | None]:
    audio = _string(item.get("urlAudio"))
    if audio:
        return audio, "audio"
    video = _string(item.get("urlVideo"))
    if video:
        return video, "video"
    return None, None


def _camara_unit_key(item: dict[str, Any], *, deputy_id: str | None) -> str:
    fase = _mapping(item.get("faseEvento"))
    stable_values = [
        deputy_id,
        _string(item.get("uriEvento")),
        _string(item.get("dataHoraInicio")),
        _string(item.get("tipoDiscurso")),
        _string(fase.get("titulo")),
        _string(item.get("sumario")),
    ]
    material = "\x1f".join(value or "" for value in stable_values)
    return sha256(material.encode("utf-8")).hexdigest()[:24]


def _new_camara_coverage_bucket() -> dict[str, Any]:
    return {
        "item_occurrences": 0,
        "text_occurrences": 0,
        "empty_text_occurrences": 0,
        "media_occurrences": 0,
        "media_with_text_occurrences": 0,
        "media_without_text_occurrences": 0,
        "unique_units": set(),
        "unique_units_with_text": set(),
        "unique_units_with_media": set(),
        "unique_blank_units_with_media": set(),
    }


def _partition_year(path: Path) -> int | None:
    for part in path.parts:
        match = re.fullmatch(r"ano=(\d{4})", part)
        if match:
            return int(match.group(1))
    return None


def _media_priority(row: dict[str, Any]) -> tuple[int, int]:
    granularity = 2 if row.get("media_granularity") == "speech" else 1
    source = 2 if row.get("media_source") == "audio" else 1
    return granularity, source


def _candidate_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _string(row.get("house")) or "",
        _string(row.get("date")) or "",
        _string(row.get("candidate_id")) or "",
    )


def _deputy_id_from_source_id(value: Any) -> str | None:
    match = re.search(r"deputado:(\d+):discursos", _string(value) or "")
    return match.group(1) if match else None


def _speech_code_from_source_id(value: Any) -> str | None:
    match = re.search(r"pronunciamento:([^:]+)$", _string(value) or "")
    return match.group(1) if match else None


def _trailing_id(value: str | None) -> str | None:
    match = re.search(r"/(\d+)/?$", value or "")
    return match.group(1) if match else None


def _year(value: str | None) -> int | None:
    match = re.match(r"(\d{4})", value or "")
    return int(match.group(1)) if match else None


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", ascii_value.casefold())


def _relative_path(path: Path, data_root: Path) -> str:
    try:
        return str(path.relative_to(data_root))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _first_string(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _string(mapping.get(key))
        if value:
            return value
    return None
