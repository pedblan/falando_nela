from __future__ import annotations

from pathlib import Path

from processamento.limpeza_diario import (
    DIARY_CLEANING_VERSION,
    DIARY_RECOVERY_METHOD,
    clean_diary_editorial_noise,
)
from processamento.normalizacao import normalize_raw_record


def _diary_text() -> str:
    return """Primeiro parágrafo do pronunciamento.
Linha substantiva 2.
Linha substantiva 3.
Linha substantiva 4.
Linha substantiva 5.
Linha substantiva 6.
123
\f
DIÁRIO DO CONGRESSO NACIONAL
Brasília, terça-feira, 2 de março de 2010
Continuação 1.
Continuação 2.
Continuação 3.
Continuação 4.
Continuação 5.
O orador menciona o Diário do Congresso Nacional no corpo do discurso.
Continuação final.
124"""


def test_clean_diary_editorial_noise_only_removes_page_boundary_lines() -> None:
    result = clean_diary_editorial_noise(_diary_text())

    assert result["changed"] is True
    assert result["version"] == DIARY_CLEANING_VERSION
    assert result["page_breaks"] == 1
    assert result["removed_line_count"] == 4
    assert "\f" not in result["text"]
    assert "123" not in result["text"]
    assert "124" not in result["text"]
    assert "DIÁRIO DO CONGRESSO NACIONAL" not in result["text"]
    assert "O orador menciona o Diário do Congresso Nacional" in result["text"]
    assert result["original_sha256"] != result["cleaned_sha256"]


def test_clean_diary_editorial_noise_is_noop_without_recognized_boundary_noise() -> None:
    text = "Texto integral sem cabeçalho ou rodapé."

    result = clean_diary_editorial_noise(text)

    assert result["text"] == text
    assert result["changed"] is False
    assert result["removed_lines"] == []
    assert result["original_sha256"] == result["cleaned_sha256"]


def test_clean_diary_editorial_noise_is_idempotent() -> None:
    first = clean_diary_editorial_noise(_diary_text())
    second = clean_diary_editorial_noise(first["text"])

    assert second["text"] == first["text"]
    assert second["changed"] is False


def test_normalization_cleans_only_exact_diary_recovery_method(tmp_path: Path) -> None:
    raw_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "ano=2010"
        / "mes=03"
        / "recovery.jsonl"
    )
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "recovery",
        "source": "senado",
        "dataset": "congresso_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "CN:pronunciamento:456:diario-congresso",
        "partition": "2010-03",
        "payload": {
            "codigo_pronunciamento": "456",
            "texto": _diary_text(),
            "metodo_obtencao": DIARY_RECOVERY_METHOD,
            "metadata": {
                "sessao": {},
                "pronunciamento": {"DataPronunciamento": "2010-03-10"},
            },
            "fontes": {"documento": "DCN"},
        },
    }

    normalized = normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path)[0]

    assert normalized["texto"] == clean_diary_editorial_noise(_diary_text())["text"]
    audit = normalized["fontes"]["normalizacao_texto_diario"]
    assert audit["version"] == DIARY_CLEANING_VERSION
    assert audit["changed"] is True
    assert audit["removed_line_count"] == 4
    assert "text" not in audit
    assert raw_record["payload"]["texto"] == _diary_text()


def test_normalization_does_not_clean_other_methods(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "senado" / "congresso_discursos" / "ano=2010" / "mes=03" / "api.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "api",
        "source": "senado",
        "dataset": "congresso_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "CN:pronunciamento:789",
        "partition": "2010-03",
        "payload": {
            "codigo_pronunciamento": "789",
            "texto": _diary_text(),
            "metodo_obtencao": "api_texto_integral",
            "metadata": {"pronunciamento": {"Data": "2010-03-11"}},
            "fontes": {},
        },
    }

    normalized = normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path)[0]

    assert normalized["texto"] == _diary_text()
    assert "normalizacao_texto_diario" not in normalized["fontes"]


def test_normalization_does_not_apply_diary_rule_outside_congress(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "senado" / "plenario_discursos" / "ano=2010" / "mes=03" / "raw.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_record = {
        "run_id": "raw",
        "source": "senado",
        "dataset": "plenario_discursos",
        "record_type": "pronunciamento_texto",
        "source_id": "SF:pronunciamento:999",
        "partition": "2010-03",
        "payload": {
            "codigo_pronunciamento": "999",
            "texto": _diary_text(),
            "metodo_obtencao": DIARY_RECOVERY_METHOD,
            "metadata": {"pronunciamento": {"Data": "2010-03-12"}},
            "fontes": {},
        },
    }

    normalized = normalize_raw_record(raw_record, raw_path=raw_path, data_root=tmp_path)[0]

    assert normalized["texto"] == _diary_text()
    assert "normalizacao_texto_diario" not in normalized["fontes"]
