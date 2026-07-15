from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from coleta.common.http import HttpResult
from coleta.senado import recuperar_textos_diario as recovery


def _population_record() -> dict[str, Any]:
    return {
        "codigo_pronunciamento": "384832",
        "data": "2010-03-03",
        "house": "CN",
        "dataset": "congresso_discursos",
        "pronunciamento": {
            "CodigoPronunciamento": "384832",
            "NomeAutor": "Antônio Carlos Valadares",
            "Publicacoes": {
                "Publicacao": {
                    "SiglaFonte": "DCN",
                    "DataPublicacao": "2010-03-04",
                    "PaginaInicial": "769",
                    "UrlDiario": "http://legis.senado.leg.br/diarios/BuscaDiario?tipDiario=1",
                }
            },
        },
    }


def test_load_population_requires_dcn_publication_and_keeps_code_identity(tmp_path: Path) -> None:
    path = tmp_path / "population.jsonl"
    path.write_text(json.dumps(_population_record()) + "\n", encoding="utf-8")

    rows = recovery.load_population(
        path,
        start=recovery.date(2010, 1, 1),
        end=recovery.date(2010, 12, 31),
    )

    assert rows == [
        {
            "codigo_pronunciamento": "384832",
            "data": "2010-03-03",
            "house": "CN",
            "dataset": "congresso_discursos",
            "pronunciamento": _population_record()["pronunciamento"],
            "publication": {
                "sigla_fonte": "DCN",
                "data_publicacao": "2010-03-04",
                "pagina_inicial": 769,
                "url_diario_original": "http://legis.senado.leg.br/diarios/BuscaDiario?tipDiario=1",
            },
            "speaker": "Antônio Carlos Valadares",
        }
    ]


def test_extract_speaker_text_is_accent_insensitive_and_stops_at_next_speaker() -> None:
    document = """
O SR. ANTONIO CARLOS VALADARES (PSB – SE) – Primeiro parágrafo com conteúdo suficiente
para superar a validação de tamanho e preservar a transcrição oficial no registro recuperado.
O SR. PRESIDENTE (Mão Santa) – Próximo orador.
"""

    text = recovery.extract_speaker_text(document, "Antônio Carlos Valadares")

    assert text is not None
    assert text.startswith("O SR. ANTONIO CARLOS VALADARES")
    assert "Próximo orador" not in text


def test_lookup_congress_diary_forces_dcn_even_when_legacy_url_points_to_senado() -> None:
    class FakeClient:
        def get_text(self, path: str, *, params: dict[str, Any]) -> HttpResult:
            assert path == recovery.DIARY_LOOKUP_PATH
            assert params["tipDiario"] == 2
            assert params["paginaDireta"] == 769
            return HttpResult(
                "https://legis.senado.leg.br/diarios/ver/2088?pagina=769",
                200,
                {},
                'var diario = {"tituloCurto":"DCN 5/2010","caderno":{"codigo":2088,"sglVeiculo":"DCN","paginaFinal":799}};',
            )

    diary = recovery.lookup_congress_diary(
        FakeClient(),  # type: ignore[arg-type]
        {"data_publicacao": "2010-03-04", "pagina_inicial": 769},
    )

    assert diary["codigo_diario"] == "2088"
    assert diary["titulo"] == "DCN 5/2010"


def test_recover_pronunciamento_writes_a_code_bound_text_payload(monkeypatch: Any) -> None:
    record = _population_record()
    prepared = {
        **record,
        "publication": recovery.select_congress_publication(record["pronunciamento"]),
        "speaker": "Antônio Carlos Valadares",
    }
    monkeypatch.setattr(
        recovery,
        "lookup_congress_diary",
        lambda *_: {"codigo_diario": "2088", "pagina_final": 799, "url": "https://example.test/dcn"},
    )
    monkeypatch.setattr(
        recovery,
        "download_diary_pages",
        lambda *_args, **_kwargs: (
            [
                """
O SR. ANTÔNIO CARLOS VALADARES (PSB – SE) – Texto oficial longo o suficiente para
validar que o recorte vem do Diário do Congresso e não de uma correspondência por nome.
O SR. PRESIDENTE (Mão Santa) – Próximo orador.
"""
            ],
            {"url": "https://example.test/dcn.pdf", "status_code": 200},
        ),
    )

    payload, request, response = recovery.recover_pronunciamento_texto(None, prepared)  # type: ignore[arg-type]

    assert payload["codigo_pronunciamento"] == "384832"
    assert payload["texto_status"] == "disponivel"
    assert payload["metodo_obtencao"] == recovery.RECOVERY_STRATEGY
    assert "Próximo orador" not in payload["texto"]
    assert payload["metadata"]["diario_congresso_recovery"]["codigo_pronunciamento"] == "384832"
    assert request["params"]["codDiario"] == "2088"
    assert response["status_code"] == 200


def test_collect_writes_text_for_every_fixed_population_code(
    tmp_path: Path, monkeypatch: Any
) -> None:
    population_path = tmp_path / "population.jsonl"
    population_path.write_text(json.dumps(_population_record()) + "\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def fake_recover(_client: Any, record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        return (
            {
                "codigo_pronunciamento": record["codigo_pronunciamento"],
                "CodigoPronunciamento": record["codigo_pronunciamento"],
                "texto": "Texto oficial do Diário do Congresso.",
                "TextoIntegral": "Texto oficial do Diário do Congresso.",
                "texto_status": "disponivel",
                "metodo_obtencao": recovery.RECOVERY_STRATEGY,
                "metadata": {"pronunciamento": record["pronunciamento"], "sessao": {}},
                "fontes": {},
            },
            {"method": "GET", "path": "diarios/BuscaPaginasDiario", "params": {}},
            {"url": "https://example.test/dcn.pdf", "status_code": 200},
        )

    monkeypatch.setattr(recovery, "OpenDataClient", FakeClient)
    monkeypatch.setattr(recovery, "recover_pronunciamento_texto", fake_recover)

    manifest_path = recovery.collect(
        [
            "--mode",
            "dev",
            "--no-sample",
            "--output-dir",
            str(tmp_path),
            "--data-inicio",
            "2010-01-01",
            "--data-fim",
            "2010-12-31",
            "--run-id",
            "diario-cn-test",
            "--population-path",
            str(population_path),
        ]
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_path = (
        tmp_path
        / "raw"
        / "senado"
        / "congresso_discursos"
        / "ano=2010"
        / "mes=03"
        / "diario-cn-test.jsonl"
    )
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    text_record = next(record for record in records if record["record_type"] == "pronunciamento_texto")

    assert manifest["status"] == "completed"
    assert manifest["errors"] == 0
    assert manifest["texto_disponivel"] == 1
    assert text_record["source_id"] == "CN:pronunciamento:384832:diario-congresso"
    assert text_record["payload"]["texto"] == "Texto oficial do Diário do Congresso."
