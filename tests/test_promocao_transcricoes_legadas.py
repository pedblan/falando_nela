from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from coleta.senado.promocao_transcricoes_legadas import (
    PROMOTION_METHOD,
    build_promotion_records,
    find_existing_nonempty_texts,
    write_promotion_records,
)
from processamento.normalizacao import normalize_raw_record


def _accepted_row(**updates: object) -> dict[str, object]:
    text = str(updates.get("legacy_text", "Transcrição audiovisual integral revisada."))
    row: dict[str, object] = {
        "candidate_id": "senado:123",
        "house": "senado",
        "speech_id": "123",
        "speaker_id": "456",
        "speaker_name": "Senadora Teste",
        "event_id": "789",
        "date": "2010-03-10",
        "tipo_discurso": "Discurso",
        "media_url": "https://example.test/video/123",
        "media_source": "video",
        "legacy_text": text,
        "legacy_text_sha256": hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
        "legacy_text_length": len(text.strip()),
        "legacy_row_fingerprint": "fingerprint-123",
        "legacy_file_id": "drive-file-id",
        "match_method": "exact_speech_id",
        "match_score": 100,
        "recovery_id": "recovery-v1",
        "recovery_source": "legacy_parquet",
        "review_status": "accepted_by_strong_key_pending_text_review",
        "publication_status": "operations_only",
    }
    row.update(updates)
    return row


def _records(rows: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    return build_promotion_records(
        rows or [_accepted_row()],
        run_id="promotion-v1",
        recovery_id="recovery-v1",
        audit_id="audit-v1",
        visual_review_fraction=0.30,
        visual_review_decision="approved",
        visual_review_note="Amostra aleatória de 30% aprovada em inspeção visual.",
        collected_at="2026-07-16T16:00:00+00:00",
    )


def test_build_promotion_records_emits_canonical_auditable_raw_record(tmp_path: Path) -> None:
    record = _records()[0]
    payload = record["payload"]

    assert record["source_id"] == "SF:pronunciamento:123:legacy-transcription-promotion:v1"
    assert record["partition"] == "2010-03"
    assert payload["metodo_obtencao"] == PROMOTION_METHOD
    assert payload["texto"] == "Transcrição audiovisual integral revisada."
    assert payload["metadata"]["legacy_recovery"]["visual_review_fraction"] == 0.30
    expected_checksum = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert record["checksum"] == expected_checksum

    raw_path = tmp_path / "raw" / "senado" / "plenario_discursos" / "ano=2010" / "mes=03" / "promotion-v1.jsonl"
    normalized = normalize_raw_record(record, raw_path=raw_path, data_root=tmp_path)[0]
    assert normalized["texto_id"] == "senado:plenario_discursos:pronunciamento:123"
    assert normalized["texto"] == payload["texto"]
    assert normalized["metodo_obtencao"] == PROMOTION_METHOD
    assert normalized["raw_run_id"] == "promotion-v1"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"house": "camara"}, "Casa não permitida"),
        ({"match_score": 80}, "Vínculo fraco"),
        ({"match_method": "senate_speaker_date_event_review"}, "chave forte"),
        ({"review_status": "manual_review"}, "Estado de revisão"),
        ({"publication_status": "published"}, "Estado de publicação"),
        ({"legacy_text_sha256": "bad"}, "SHA-256 divergente"),
        ({"legacy_text_length": 1}, "Comprimento textual divergente"),
        ({"recovery_id": "other"}, "recovery_id divergente"),
        ({"recovery_source": "other"}, "Fonte de recuperação inesperada"),
    ],
)
def test_build_promotion_records_rejects_nonaccepted_population(
    updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _records([_accepted_row(**updates)])


def test_build_promotion_records_rejects_duplicate_speech_ids() -> None:
    duplicate = _accepted_row(candidate_id="senado:duplicate")

    with pytest.raises(ValueError, match="identificadores duplicados"):
        _records([_accepted_row(), duplicate])


def test_find_existing_nonempty_texts_scans_only_monthly_raw(tmp_path: Path) -> None:
    monthly = tmp_path / "raw" / "senado" / "plenario_discursos" / "ano=2010" / "mes=03" / "official.jsonl"
    metadata = tmp_path / "raw" / "senado" / "plenario_discursos" / "metadata" / "broken.jsonl"
    monthly.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    monthly.write_text(
        json.dumps(
            {
                "run_id": "official",
                "record_type": "pronunciamento_texto",
                "source_id": "SF:pronunciamento:123",
                "payload": {"codigo_pronunciamento": "123", "texto": "Texto oficial"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metadata.write_text("isto não é JSONL\n", encoding="utf-8")

    found = find_existing_nonempty_texts(tmp_path, ["123", "999"])

    assert set(found) == {"123"}
    assert found["123"][0]["run_id"] == "official"
    assert found["123"][0]["raw_path"].startswith("raw/senado/plenario_discursos/ano=2010")


def test_write_promotion_records_publishes_partitioned_raw_and_manifest(tmp_path: Path) -> None:
    rows = [
        _accepted_row(),
        _accepted_row(
            candidate_id="senado:999",
            speech_id="999",
            date="2015-04-20",
            legacy_text="Outra transcrição revisada.",
            legacy_text_sha256=hashlib.sha256("Outra transcrição revisada.".encode()).hexdigest(),
            legacy_row_fingerprint="fingerprint-999",
        ),
    ]
    records = _records(rows)

    manifest = write_promotion_records(
        tmp_path,
        records,
        run_id="promotion-v1",
        recovery_id="recovery-v1",
        audit_id="audit-v1",
        repository_commit="abc123",
    )

    assert manifest["status"] == "completed"
    assert manifest["records"] == 2
    assert manifest["partitions"] == {"2010-03": 1, "2015-04": 1}
    assert len(manifest["output_files"]) == 2
    for output in manifest["output_files"]:
        path = Path(output["path"])
        assert path.exists()
        assert not path.with_name(f"{path.name}.partial").exists()
    manifest_path = tmp_path / "manifests" / "promotion-v1.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["records"] == 2

    with pytest.raises(FileExistsError, match="Saídas da promoção já existem"):
        write_promotion_records(
            tmp_path,
            records,
            run_id="promotion-v1",
            recovery_id="recovery-v1",
            audit_id="audit-v1",
            repository_commit="abc123",
        )


def test_write_promotion_records_rolls_back_raw_if_manifest_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = _records()
    original_write_text = Path.write_text

    def fail_manifest(self: Path, *args: object, **kwargs: object) -> int:
        if self.name == "promotion-v1.json.partial":
            raise OSError("falha simulada no manifest")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_manifest)

    with pytest.raises(OSError, match="falha simulada"):
        write_promotion_records(
            tmp_path,
            records,
            run_id="promotion-v1",
            recovery_id="recovery-v1",
            audit_id="audit-v1",
            repository_commit="abc123",
        )

    assert not list(
        (tmp_path / "raw" / "senado" / "plenario_discursos").rglob("promotion-v1.jsonl")
    )
    assert not (tmp_path / "manifests" / "promotion-v1.json").exists()
    assert not list(tmp_path.rglob("*.partial"))


def test_write_promotion_records_rejects_tampered_payload(tmp_path: Path) -> None:
    records = _records()
    records[0]["payload"]["texto"] = "Texto alterado depois do aceite"

    with pytest.raises(ValueError, match="Contrato de promoção inválido"):
        write_promotion_records(
            tmp_path,
            records,
            run_id="promotion-v1",
            recovery_id="recovery-v1",
            audit_id="audit-v1",
            repository_commit="abc123",
        )
