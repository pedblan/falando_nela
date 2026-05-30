from __future__ import annotations

from coleta.camara.plenario_apartes.collect import classify_sitaq_probe
from coleta.senado.plenario_apartes.collect import count_apartes


def test_count_senado_apartes_accepts_null_single_and_list() -> None:
    assert count_apartes({"ApartesParlamentar": {"Parlamentar": {"Apartes": None}}}) == 0
    assert (
        count_apartes(
            {
                "ApartesParlamentar": {
                    "Parlamentar": {
                        "Apartes": {
                            "Aparte": {
                                "CodigoPronunciamento": "1",
                            }
                        }
                    }
                }
            }
        )
        == 1
    )
    assert (
        count_apartes(
            {
                "ApartesParlamentar": {
                    "Parlamentar": {
                        "Apartes": {
                            "Aparte": [
                                {"CodigoPronunciamento": "1"},
                                {"CodigoPronunciamento": "2"},
                            ]
                        }
                    }
                }
            }
        )
        == 2
    )


def test_classify_sitaq_probe_splits_only_when_period_is_positive_or_unknown() -> None:
    assert (
        classify_sitaq_probe({"result_count_text": "Nenhum discurso encontrado.", "chaves_extraidas": []}, 1)
        == "zero"
    )
    assert (
        classify_sitaq_probe({"result_count_text": "1 a 10 de 23 documentos encontrados", "chaves_extraidas": []}, 1)
        == "positive"
    )
    assert (
        classify_sitaq_probe({"result_count_text": None, "chaves_extraidas": [{"discurso_chave": "x"}]}, 1)
        == "positive"
    )
    assert (
        classify_sitaq_probe({"result_count_text": None, "chaves_extraidas": []}, 3)
        == "positive"
    )
    assert (
        classify_sitaq_probe({"result_count_text": None, "chaves_extraidas": []}, 1)
        == "unknown"
    )
