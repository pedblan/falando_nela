from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from coleta.common.config import utc_now_iso


SOURCE = "senado"
DATASET = "plenario_discursos"
RECORD_TYPE = "pronunciamento_texto"
PROMOTION_METHOD = "legacy_parquet_transcricao_audiovisual_v1"
PROMOTION_SCHEMA_VERSION = 1
STRONG_MATCH_METHODS = {
    "exact_speech_id",
    "exact_audio_url",
    "exact_video_url",
}


def build_promotion_records(
    rows: Iterable[dict[str, Any]],
    *,
    run_id: str,
    recovery_id: str,
    audit_id: str,
    visual_review_fraction: float,
    visual_review_decision: str,
    visual_review_note: str,
    collected_at: str | None = None,
) -> list[dict[str, Any]]:
    if not run_id.strip() or not recovery_id.strip() or not audit_id.strip():
        raise ValueError("run_id, recovery_id e audit_id são obrigatórios")
    if not 0 < visual_review_fraction <= 1:
        raise ValueError("visual_review_fraction deve estar entre 0 e 1")
    if visual_review_decision != "approved":
        raise ValueError("A promoção exige visual_review_decision='approved'")
    if not visual_review_note.strip():
        raise ValueError("A promoção exige nota da revisão visual")

    timestamp = collected_at or utc_now_iso()
    records = [
        build_promotion_record(
            row,
            run_id=run_id,
            recovery_id=recovery_id,
            audit_id=audit_id,
            visual_review_fraction=visual_review_fraction,
            visual_review_decision=visual_review_decision,
            visual_review_note=visual_review_note,
            collected_at=timestamp,
        )
        for row in rows
    ]
    source_ids = [record["source_id"] for record in records]
    codes = [record["payload"]["codigo_pronunciamento"] for record in records]
    if len(source_ids) != len(set(source_ids)) or len(codes) != len(set(codes)):
        raise ValueError("A população promovida contém identificadores duplicados")
    return sorted(records, key=lambda record: (record["partition"], record["source_id"]))


def build_promotion_record(
    row: dict[str, Any],
    *,
    run_id: str,
    recovery_id: str,
    audit_id: str,
    visual_review_fraction: float,
    visual_review_decision: str,
    visual_review_note: str,
    collected_at: str,
) -> dict[str, Any]:
    house = _string(row.get("house"))
    code = _string(row.get("speech_id"))
    text = _string(row.get("legacy_text"))
    date_value = _iso_date(row.get("date"))
    match_score = _integer(row.get("match_score"))
    expected_hash = _string(row.get("legacy_text_sha256"))
    expected_length = _integer(row.get("legacy_text_length"))
    actual_hash = _sha256(text or "")
    candidate_id = _string(row.get("candidate_id"))
    legacy_file_id = _string(row.get("legacy_file_id"))
    legacy_row_fingerprint = _string(row.get("legacy_row_fingerprint"))

    if house != "senado":
        raise ValueError(f"Casa não permitida para promoção: {house!r}")
    if not code or not text or not date_value:
        raise ValueError(f"Registro sem código, texto ou data: {row.get('candidate_id')}")
    if match_score < 90:
        raise ValueError(f"Vínculo fraco não pode ser promovido: {row.get('candidate_id')}")
    if _string(row.get("match_method")) not in STRONG_MATCH_METHODS:
        raise ValueError(f"Método de vínculo não é chave forte: {row.get('match_method')!r}")
    if expected_hash != actual_hash:
        raise ValueError(f"SHA-256 divergente: {row.get('candidate_id')}")
    if expected_length != len(text):
        raise ValueError(f"Comprimento textual divergente: {row.get('candidate_id')}")
    if _string(row.get("recovery_id")) != recovery_id:
        raise ValueError(f"recovery_id divergente: {row.get('candidate_id')}")
    if not candidate_id or not legacy_file_id or not legacy_row_fingerprint:
        raise ValueError("Proveniência legada incompleta")
    if _string(row.get("recovery_source")) != "legacy_parquet":
        raise ValueError(f"Fonte de recuperação inesperada: {row.get('recovery_source')!r}")
    if _string(row.get("review_status")) != "accepted_by_strong_key_pending_text_review":
        raise ValueError(f"Estado de revisão inesperado: {row.get('review_status')!r}")
    if _string(row.get("publication_status")) != "operations_only":
        raise ValueError(f"Estado de publicação inesperado: {row.get('publication_status')!r}")

    speaker_id = _string(row.get("speaker_id") or row.get("old_speaker_id"))
    speaker_name = _string(row.get("speaker_name"))
    event_id = _string(row.get("event_id") or row.get("old_event_id"))
    speech_type = _string(row.get("tipo_discurso") or row.get("old_speech_type"))
    media_url = _string(row.get("media_url"))
    media_source = _string(row.get("media_source"))
    partition = date_value[:7]

    pronunciamento = {
        "CodigoPronunciamento": code,
        "CodigoParlamentar": speaker_id,
        "NomeAutor": speaker_name,
        "Data": date_value,
        "DataPronunciamento": date_value,
        "TipoUsoPalavra": speech_type,
    }
    sessao = {
        "CodigoSessao": event_id,
        "DataSessao": date_value,
    }
    legacy_recovery = {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "promotion_method": PROMOTION_METHOD,
        "candidate_id": candidate_id,
        "recovery_id": recovery_id,
        "recovery_source": _string(row.get("recovery_source")),
        "legacy_file_id": legacy_file_id,
        "legacy_row_fingerprint": legacy_row_fingerprint,
        "legacy_text_sha256": expected_hash,
        "legacy_text_length": len(text),
        "match_method": _string(row.get("match_method")),
        "match_score": match_score,
        "audit_id": audit_id,
        "visual_review_fraction": visual_review_fraction,
        "visual_review_decision": visual_review_decision,
        "visual_review_note": visual_review_note,
    }
    fontes = {
        "legacy_file_id": legacy_recovery["legacy_file_id"],
        "legacy_media_url": media_url,
        "legacy_media_source": media_source,
        "video": media_url if media_source != "audio" else None,
        "audio": media_url if media_source == "audio" else None,
    }
    payload = {
        "CodigoPronunciamento": code,
        "TextoIntegral": text,
        "TextoIntegralUrl": None,
        "codigo_pronunciamento": code,
        "metadata": {
            "sessao": sessao,
            "pronunciamento": pronunciamento,
            "legacy_recovery": legacy_recovery,
        },
        "texto": text,
        "forma": "texto",
        "metodo_obtencao": PROMOTION_METHOD,
        "texto_status": "disponivel",
        "fontes": fontes,
    }
    return {
        "run_id": run_id,
        "collected_at": collected_at,
        "source": SOURCE,
        "dataset": DATASET,
        "record_type": RECORD_TYPE,
        "source_id": f"SF:pronunciamento:{code}:legacy-transcription-promotion:v1",
        "partition": partition,
        "periodo": {"data_inicio": date_value, "data_fim": date_value},
        "request": {
            "method": "READ_PARQUET",
            "source": "legacy_recovery_operation",
            "legacy_file_id": legacy_recovery["legacy_file_id"],
            "legacy_row_fingerprint": legacy_recovery["legacy_row_fingerprint"],
        },
        "response": {
            "status_code": 200,
            "source": "reviewed_legacy_transcription",
            "content_type": "text/plain",
        },
        "checksum": _payload_checksum(payload),
        "payload": payload,
    }


def find_existing_nonempty_texts(
    data_root: Path,
    speech_ids: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    wanted = {str(value) for value in speech_ids}
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    corpus_root = Path(data_root) / "raw" / SOURCE / DATASET
    paths = sorted(path for path in corpus_root.glob("ano=*/mes=*/*.jsonl") if path.is_file())
    for path in paths:
        for record in _iter_jsonl_strict(path):
            if record.get("record_type") != RECORD_TYPE:
                continue
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            code = _string(
                payload.get("codigo_pronunciamento")
                or payload.get("CodigoPronunciamento")
            )
            text = _string(payload.get("texto") or payload.get("TextoIntegral"))
            if code in wanted and text:
                found[code].append(
                    {
                        "run_id": record.get("run_id"),
                        "source_id": record.get("source_id"),
                        "metodo_obtencao": payload.get("metodo_obtencao"),
                        "text_sha256": _sha256(text),
                        "raw_path": _relative(path, Path(data_root)),
                    }
                )
    return dict(found)


def write_promotion_records(
    data_root: Path,
    records: list[dict[str, Any]],
    *,
    run_id: str,
    recovery_id: str,
    audit_id: str,
    repository_commit: str,
) -> dict[str, Any]:
    if not records:
        raise ValueError("Nenhum registro para promoção")
    if any(record.get("run_id") != run_id for record in records):
        raise ValueError("run_id divergente nos registros promovidos")
    for record in records:
        payload = record.get("payload")
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        legacy = metadata.get("legacy_recovery") if isinstance(metadata, dict) else None
        if (
            record.get("source") != SOURCE
            or record.get("dataset") != DATASET
            or record.get("record_type") != RECORD_TYPE
            or not isinstance(payload, dict)
            or payload.get("metodo_obtencao") != PROMOTION_METHOD
            or not isinstance(legacy, dict)
            or legacy.get("recovery_id") != recovery_id
            or legacy.get("audit_id") != audit_id
            or record.get("checksum") != _payload_checksum(payload)
        ):
            raise ValueError(f"Contrato de promoção inválido: {record.get('source_id')}")

    data_root = Path(data_root)
    by_partition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        partition = _string(record.get("partition"))
        if not partition or not re.fullmatch(r"\d{4}-\d{2}", partition):
            raise ValueError(f"Partição inválida: {partition!r}")
        by_partition[partition].append(record)

    target_paths = {
        partition: (
            data_root
            / "raw"
            / SOURCE
            / DATASET
            / f"ano={partition[:4]}"
            / f"mes={partition[5:7]}"
            / f"{run_id}.jsonl"
        )
        for partition in by_partition
    }
    manifest_path = data_root / "manifests" / f"{run_id}.json"
    collisions = [
        str(path)
        for path in [manifest_path, *target_paths.values()]
        if path.exists() or path.with_name(f"{path.name}.partial").exists()
    ]
    if collisions:
        raise FileExistsError(f"Saídas da promoção já existem: {collisions}")

    partial_paths: list[Path] = []
    published_paths: list[Path] = []
    manifest_partial = manifest_path.with_name(f"{manifest_path.name}.partial")
    try:
        for partition, target in sorted(target_paths.items()):
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(f"{target.name}.partial")
            partial_paths.append(partial)
            with partial.open("x", encoding="utf-8") as handle:
                for record in by_partition[partition]:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if _count_jsonl(partial) != len(by_partition[partition]):
                raise ValueError(f"Contagem divergente em {partial}")

        for partition, target in sorted(target_paths.items()):
            partial = target.with_name(f"{target.name}.partial")
            os.replace(partial, target)
            published_paths.append(target)

        manifest = {
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "run_id": run_id,
            "source": SOURCE,
            "dataset": DATASET,
            "status": "completed",
            "created_at": utc_now_iso(),
            "recovery_id": recovery_id,
            "audit_id": audit_id,
            "repository_commit": repository_commit,
            "promotion_method": PROMOTION_METHOD,
            "records": len(records),
            "unique_speech_ids": len(
                {record["payload"]["codigo_pronunciamento"] for record in records}
            ),
            "partitions": {
                partition: len(by_partition[partition]) for partition in sorted(by_partition)
            },
            "output_files": [
                {
                    "path": str(target),
                    "rows": len(by_partition[partition]),
                    "size_bytes": target.stat().st_size,
                    "sha256": _sha256_file(target),
                }
                for partition, target in sorted(target_paths.items())
            ],
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_partial.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(manifest_partial, manifest_path)
        return {**manifest, "manifest_path": str(manifest_path)}
    except Exception:
        if not manifest_path.exists():
            for path in published_paths:
                path.unlink(missing_ok=True)
        raise
    finally:
        for partial in partial_paths:
            partial.unlink(missing_ok=True)
        manifest_partial.unlink(missing_ok=True)


def _iter_jsonl_strict(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido em {path}, linha {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Registro não é objeto em {path}, linha {line_number}")
            yield value


def _count_jsonl(path: Path) -> int:
    return sum(1 for _ in _iter_jsonl_strict(path))


def _payload_checksum(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(serialized).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _integer(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return None if text in {"", "<NA>", "NaT", "nan", "None"} else text


def _iso_date(value: Any) -> str | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", _string(value) or "")
    return match.group(0) if match else None


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
