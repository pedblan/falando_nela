from __future__ import annotations

import json
from pathlib import Path

import pytest

from coleta.transcricoes_audiovisuais import (
    infer_old_parquet_columns,
    scan_camara_media_candidates,
    scan_senado_transcription_queue,
    select_probe_sample,
    validate_parquet_magic,
)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_senado_inventory_prefers_direct_speech_video_and_deduplicates(tmp_path: Path) -> None:
    queue = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "transcription_queue"
        / "run.jsonl"
    )
    base = {
        "record_type": "transcription_queue",
        "run_id": "run",
        "source_id": "SF:pronunciamento:389577",
        "periodo": {"data_inicio": "2011-05-01"},
        "payload": {
            "codigo_pronunciamento": "389577",
            "texto": None,
            "texto_status": "ausente",
            "metodo_obtencao": "pendente_transcricao_video",
            "metadata": {
                "sessao": {"CodigoSessao": "21014", "DataSessao": "2011-05-31"},
                "pronunciamento": {"NomeAutor": "Autora"},
            },
            "fontes": {"videos_sessao_api": "https://example.test/session/21014"},
        },
    }
    direct = json.loads(json.dumps(base))
    direct["payload"]["fontes"]["video"] = "https://example.test/speech.mp4"  # type: ignore[index]
    _write_jsonl(queue, [base, direct])

    rows = scan_senado_transcription_queue(tmp_path)

    assert len(rows) == 1
    assert rows[0]["candidate_id"].endswith(":389577")
    assert rows[0]["media_url"] == "https://example.test/speech.mp4"
    assert rows[0]["media_granularity"] == "speech"
    assert rows[0]["eligible_for_asr"] is True
    assert rows[0]["raw_occurrences"] == 2


def test_senado_session_video_requires_alignment(tmp_path: Path) -> None:
    queue = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "transcription_queue"
        / "run.jsonl"
    )
    _write_jsonl(
        queue,
        [
            {
                "record_type": "transcription_queue",
                "source_id": "SF:pronunciamento:10",
                "payload": {
                    "codigo_pronunciamento": "10",
                    "texto": None,
                    "fontes": {"videos_sessao_api": "https://example.test/session/20"},
                },
            }
        ],
    )

    row = scan_senado_transcription_queue(tmp_path)[0]

    assert row["media_granularity"] == "session"
    assert row["needs_alignment"] is True
    assert row["eligible_for_asr"] is False


def test_camara_inventory_excludes_item_resolved_in_later_raw_occurrence(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "raw"
        / "camara"
        / "plenario_discursos"
        / "ano=2024"
        / "mes=05"
        / "run.jsonl"
    )
    item = {
        "dataHoraInicio": "2024-05-02T10:00:00",
        "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/99",
        "tipoDiscurso": "Pequeno Expediente",
        "sumario": "Tema",
        "urlAudio": "https://example.test/99.mp3",
        "urlVideo": "https://example.test/99.mp4",
        "transcricao": None,
    }
    resolved = {**item, "transcricao": "Texto oficial"}
    _write_jsonl(
        path,
        [
            {
                "record_type": "discursos_page",
                "source_id": "deputado:123:discursos:2024-05:pagina:1",
                "payload": {"dados": [item]},
            },
            {
                "record_type": "discursos_page",
                "source_id": "deputado:123:discursos:2024-05:pagina:2",
                "payload": {"dados": [resolved]},
            },
        ],
    )

    assert scan_camara_media_candidates(tmp_path) == []


def test_camara_inventory_uses_audio_and_stable_candidate_id(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "raw"
        / "camara"
        / "plenario_discursos"
        / "ano=2024"
        / "mes=05"
        / "run.jsonl"
    )
    item = {
        "dataHoraInicio": "2024-05-02T10:00:00",
        "uriEvento": "https://dadosabertos.camara.leg.br/api/v2/eventos/99",
        "tipoDiscurso": "Pequeno Expediente",
        "sumario": "Tema",
        "urlAudio": "https://example.test/99.mp3",
        "urlVideo": "https://example.test/99.mp4",
        "transcricao": " ",
    }
    _write_jsonl(
        path,
        [
            {
                "record_type": "discursos_page",
                "run_id": "run",
                "source_id": "deputado:123:discursos:2024-05:pagina:1",
                "payload": {"dados": [item, item]},
            }
        ],
    )

    rows = scan_camara_media_candidates(tmp_path)

    assert len(rows) == 1
    assert rows[0]["candidate_id"].startswith("camara:plenario_discursos:discurso:")
    assert rows[0]["speaker_id"] == "123"
    assert rows[0]["event_id"] == "99"
    assert rows[0]["media_source"] == "audio"
    assert rows[0]["media_url"].endswith("99.mp3")
    assert rows[0]["raw_occurrences"] == 2


def test_probe_sample_is_reproducible_and_prioritizes_asr_eligible() -> None:
    candidates = [
        {
            "candidate_id": "senado:session",
            "house": "senado",
            "eligible_for_asr": False,
            "media_source": "session_video_api",
        },
        {
            "candidate_id": "senado:direct",
            "house": "senado",
            "eligible_for_asr": True,
            "media_source": "video",
        },
        {
            "candidate_id": "camara:audio",
            "house": "camara",
            "eligible_for_asr": True,
            "media_source": "audio",
        },
    ]

    first = select_probe_sample(candidates, max_per_house=1, seed=20260716)
    second = select_probe_sample(candidates, max_per_house=1, seed=20260716)

    assert first == second
    assert {row["candidate_id"] for row in first} == {"senado:direct", "camara:audio"}


def test_old_parquet_schema_inference_and_magic_validation(tmp_path: Path) -> None:
    inferred = infer_old_parquet_columns(
        [
            "Casa",
            "DataPronunciamento",
            "TextoIntegral",
            "CodigoPronunciamento",
            "CodigoParlamentar",
            "urlVideo",
        ]
    )
    assert inferred == {
        "house": "Casa",
        "date": "DataPronunciamento",
        "text": "TextoIntegral",
        "speech_id": "CodigoPronunciamento",
        "speaker_id": "CodigoParlamentar",
        "video_url": "urlVideo",
    }

    parquet = tmp_path / "old.parquet"
    parquet.write_bytes(b"PAR1payloadPAR1")
    assert validate_parquet_magic(parquet, expected_size=15)["footer"] == "PAR1"

    html = tmp_path / "login.parquet"
    html.write_bytes(b"<html>login</html>")
    with pytest.raises(ValueError, match="não é um Parquet"):
        validate_parquet_magic(html)
