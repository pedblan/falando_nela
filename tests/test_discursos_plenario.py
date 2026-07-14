from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analise.discursos_plenario.apartes import (
    association_tests,
    benjamini_hochberg,
    bridge_quality,
    build_camara_speech_bridge,
    denominators_authorized,
    observed_expected_dyads,
)
from analise.discursos_plenario.apartes_qualitativos import (
    build_senate_speech_bridge,
    extract_interaction_turns,
    make_qualitative_batch_request,
    manual_coding_template,
    qualitative_codebook_template,
    qualitative_output_schema,
    qualitative_review_sample,
    segment_transcript_turns,
    segmentation_quality,
)
from analise.discursos_plenario.config import load_config
from analise.discursos_plenario.descritivas import clustered_speaker_bootstrap, descriptive_panel
from analise.discursos_plenario.figuras import (
    balanced_figure_pilot,
    binary_kappa,
    calculate_usage_cost,
    count_errors,
    evaluate_multilabel,
    figures_output_schema,
    figure_manual_coding_template,
    jaccard_permutation_test,
    make_batch_request,
    multilabel_jaccard,
    paired_cluster_bootstrap_jaccard,
    parse_batch_output,
)
from analise.discursos_plenario.genero import (
    REVIEW_COLUMNS,
    apply_approved_gender_enrichment,
    candidate_from_research_payload,
    publish_approved_gender_enrichment,
    select_unknown_parliamentarians,
)
from analise.discursos_plenario.inferencia import paired_trajectory_correlations
from analise.discursos_plenario.snapshot import apply_cleaning_rules, build_snapshot, run_snapshot
from analise.discursos_plenario.topicos import balanced_summary_sample


CONFIG = load_config()


def _speech(
    *,
    arena: str,
    text_id: str,
    date: str,
    text: str,
    parliamentarian_id: str = "10",
    name: str = "Maria Silva",
    speech_id: str | None = None,
    session_id: str = "S1",
) -> dict[str, object]:
    specs = CONFIG.raw["arenas"][arena]
    return {
        "texto_id": text_id,
        "source": specs["source"],
        "dataset": specs["dataset"],
        "casa": specs["house"],
        "ambito": specs["scope"],
        "documento_tipo": "discurso",
        "data": date,
        "texto": text,
        "resumo": "Resumo disponível",
        "parlamentar_id": parliamentarian_id,
        "parlamentar_nome": name,
        "pronunciamento_id": speech_id,
        "sessao_id": session_id,
        "documento_id": None,
        "data_hora": f"{date}T12:00:00",
        "tipo_discurso": "Discurso",
    }


def test_snapshot_inclusive_dates_three_arenas_dedup_and_temporal_join() -> None:
    shared = "Texto repetido com conteúdo e sessão concordantes."
    frames = {
        "camara": pd.DataFrame(
            [
                _speech(arena="camara", text_id="c-start", date="2010-02-02", text="Início válido."),
                _speech(arena="camara", text_id="c-before", date="2010-02-01", text="Antes."),
                _speech(arena="camara", text_id="c-end", date="2026-07-13", text="Fim válido."),
                _speech(arena="camara", text_id="c-after", date="2026-07-14", text="Depois."),
            ]
        ),
        "senado": pd.DataFrame(
            [
                _speech(arena="senado", text_id="s-dup", date="2020-05-03", text=shared, speech_id="P1"),
                _speech(arena="senado", text_id="s-unique", date="2021-06-01", text="Fala exclusiva do Senado."),
            ]
        ),
        "congresso": pd.DataFrame(
            [_speech(arena="congresso", text_id="g-dup", date="2020-05-03", text=shared, speech_id="P1")]
        ),
    }
    periods = pd.DataFrame(
        [
            {
                "parlamentar_key": "senado:10",
                "source": "senado",
                "parlamentar_id": "10",
                "vigencia_inicio": "2010-01-01",
                "vigencia_fim": "2026-12-31",
                "genero": "feminino",
                "sexo_original": "F",
                "partido_sigla": "ABC",
                "uf": "SP",
                "cargo": "Senadora",
                "legislatura": "1",
                "mandato_id": "M1",
                "intervalo_fonte": "oficial",
                "match_priority": 1,
                "intervalo_inferido": False,
            },
            {
                "parlamentar_key": "camara:10",
                "source": "camara",
                "parlamentar_id": "10",
                "vigencia_inicio": "2010-02-02",
                "vigencia_fim": "2026-07-13",
                "genero": "feminino",
                "sexo_original": "F",
                "partido_sigla": "XYZ",
                "uf": "RJ",
                "cargo": "Deputada",
                "legislatura": "1",
                "mandato_id": "M2",
                "intervalo_fonte": "oficial",
                "match_priority": 1,
                "intervalo_inferido": False,
            },
        ]
    )
    snapshot, audits = build_snapshot(frames, CONFIG, parliamentarian_periods=periods)

    assert set(snapshot["texto_id"]) == {"c-start", "c-end", "s-unique", "g-dup"}
    assert set(snapshot["arena"]) == {"camara", "senado", "congresso"}
    assert snapshot.loc[snapshot["texto_id"].eq("c-end"), "ano_ytd"].item() is np.True_
    assert not snapshot.loc[snapshot["ano"].eq(2026), "elegivel_inferencia_anual"].any()
    assert snapshot["texto_original"].equals(snapshot["texto_analitico"])
    assert set(snapshot["genero_oficial"]) == {"feminino"}
    assert audits["duplicate_audit"]["status"].tolist() == ["auto_remove_senado"]


def test_cleaning_applies_only_approved_hard_cut() -> None:
    text = "Fala principal.\nARTIGO A QUE SE REFERE O ORADOR\nAnexo."
    cleaned, rule = apply_cleaning_rules(
        text,
        [
            {"rule_id": "ignored", "action": "review", "approved": True, "pattern": "Fala"},
            {"rule_id": "article", "action": "hard_cut", "approved": True, "pattern": r"^ARTIGO A QUE"},
        ],
    )
    assert cleaned == "Fala principal."
    assert rule == "article"
    unchanged, no_rule = apply_cleaning_rules(text, [{"action": "hard_cut", "approved": False, "pattern": "ARTIGO"}])
    assert unchanged == text
    assert no_rule is None


def test_run_snapshot_persists_coverage_diagnostics_before_gate_failure(tmp_path: Path) -> None:
    config_payload = json.loads(json.dumps(CONFIG.raw))
    config_payload.update(
        {
            "date_start": "2015-01-01",
            "date_end": "2016-12-31",
            "complete_year_start": 2015,
            "complete_year_end": 2016,
            "ytd_year": 2017,
        }
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    rows = {
        "camara": [
            _speech(arena="camara", text_id="c15", date="2015-01-02", text="Câmara 2015"),
            _speech(arena="camara", text_id="c16", date="2016-01-02", text="Câmara 2016"),
        ],
        "senado": [
            _speech(arena="senado", text_id="s16", date="2016-02-02", text="Senado 2016"),
        ],
        "congresso": [
            _speech(arena="congresso", text_id="g15", date="2015-03-02", text="Congresso 2015"),
            _speech(arena="congresso", text_id="g16", date="2016-03-02", text="Congresso 2016"),
        ],
    }
    for arena, arena_rows in rows.items():
        path = tmp_path / config_payload["arenas"][arena]["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(arena_rows).to_parquet(path, index=False)

    with pytest.raises(ValueError, match="senado/2015"):
        run_snapshot(data_root=tmp_path, run_id="coverage-failure", config_path=config_path)

    output = tmp_path / "analises" / "discursos_plenario" / "v1" / "coverage-failure" / "00_snapshot"
    assert (output / "annual_coverage.csv").exists()
    missing = pd.read_csv(output / "missing_complete_years.csv")
    assert missing.to_dict("records") == [{"arena": "senado", "ano": 2015, "discursos": 0}]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["coverage_gate"]["passed"] is False


def test_gender_candidates_require_evidence_and_human_approval() -> None:
    periods = pd.DataFrame(
        [
            {"parlamentar_key": "x:1", "genero": "nao_informado", "source": "x", "parlamentar_id": "1"},
            {"parlamentar_key": "x:2", "genero": "feminino", "source": "x", "parlamentar_id": "2"},
        ]
    )
    unknowns = select_unknown_parliamentarians(periods)
    assert unknowns["parlamentar_key"].tolist() == ["x:1"]
    with pytest.raises(ValueError, match="evidencia"):
        candidate_from_research_payload(
            unknowns.iloc[0],
            {
                "genero_enriquecido": "feminino",
                "evidencia_url": None,
                "evidencia_titulo": None,
                "evidencia_trecho": None,
                "fontes_consultadas": [],
            },
            model="gpt-5.6-sol",
            prompt_version="v1",
        )
    candidate = candidate_from_research_payload(
        unknowns.iloc[0],
        {
            "genero_enriquecido": "feminino",
            "evidencia_url": "https://example.test/source",
            "evidencia_titulo": "Biografia oficial",
            "evidencia_trecho": "Trecho textual suficiente.",
            "fontes_consultadas": [{"url": "https://example.test/source", "titulo": "Biografia"}],
        },
        model="gpt-5.6-sol",
        prompt_version="v1",
    )
    pending = pd.DataFrame([candidate])[REVIEW_COLUMNS]
    assert publish_approved_gender_enrichment(pending).empty
    approved_input = pending.copy()
    approved_input.loc[0, ["revisao_status", "revisor", "revisado_em"]] = ["aprovado", "Pesquisadora", "2026-07-14"]
    approved = publish_approved_gender_enrichment(approved_input)
    assert approved.loc[0, "genero_presumido"]
    assert approved.loc[0, "genero_analitico"] == "feminino"
    snapshot = pd.DataFrame([{"parlamentar_key": "x:1", "genero_analitico": "nao_informado", "genero_presumido": False}])
    enriched = apply_approved_gender_enrichment(snapshot, approved)
    assert enriched.loc[0, "genero_analitico"] == "feminino"


def test_descriptives_and_cluster_bootstrap_are_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "arena": ["senado"] * 4,
            "data_analise": pd.to_datetime(["2020-01-01", "2020-02-01", "2021-01-01", "2021-02-01"]),
            "texto_id": ["1", "2", "3", "4"],
            "parlamentar_id": ["a", "b", "a", "b"],
            "n_palavras": [10, 20, 30, 40],
            "elegivel_descritivas": True,
        }
    )
    annual = descriptive_panel(frame)
    assert annual["discursos"].tolist() == [2, 2]
    assert annual["palavras_mediana"].tolist() == [15.0, 35.0]
    with pytest.raises(ValueError, match="generalizacao"):
        clustered_speaker_bootstrap(frame, lambda data: data["n_palavras"].mean(), estimand="")
    first = clustered_speaker_bootstrap(
        frame,
        lambda data: data["n_palavras"].mean(),
        estimand="média entre oradores comparáveis",
        repetitions=30,
        seed=20260713,
    )
    second = clustered_speaker_bootstrap(
        frame,
        lambda data: data["n_palavras"].mean(),
        estimand="média entre oradores comparáveis",
        repetitions=30,
        seed=20260713,
    )
    assert first == second


def test_observed_expected_association_and_bh_known_values() -> None:
    interactions = pd.DataFrame(
        {
            "aparteante_genero": ["F"] * 8 + ["F"] * 2 + ["M"] * 2 + ["M"] * 8,
            "orador_genero": ["F"] * 8 + ["M"] * 2 + ["F"] * 2 + ["M"] * 8,
        }
    )
    dyads = observed_expected_dyads(interactions)
    assert set(dyads["esperado"]) == {5.0}
    table = pd.DataFrame([[8, 2], [2, 8]])
    tests = association_tests(table)
    assert tests["chi2"] == pytest.approx(7.2)
    assert tests["cramer_v"] == pytest.approx(0.6)
    assert tests["fisher_applied"] is False
    sparse = association_tests(pd.DataFrame([[1, 0], [0, 2]]))
    assert sparse["fisher_applied"] is True
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, np.nan])
    assert adjusted.iloc[:3].tolist() == pytest.approx([0.03, 0.04, 0.04])
    assert np.isnan(adjusted.iloc[3])


def test_camara_bridge_and_denominator_gate() -> None:
    interjections = pd.DataFrame(
        [
            {
                "aparte_id": "a1",
                "data": "2020-01-10",
                "discurso_chave": "D1",
                "sessao_id": "S1",
                "orador_id": "10",
                "orador_nome": "Maria Silva",
                "data_hora": "2020-01-10T12:00:00",
            }
        ]
    )
    speeches = pd.DataFrame(
        [
            {
                "texto_id": "t1",
                "data": "2020-01-10",
                "documento_id": "D1",
                "sessao_id": "S1",
                "parlamentar_id": "10",
                "parlamentar_nome": "Maria Silva",
                "data_hora": "2020-01-10T12:02:00",
            }
        ]
    )
    bridge = build_camara_speech_bridge(interjections, speeches)
    assert bridge.loc[0, "ponte_status"] == "exato"
    quality_without_gold = bridge_quality(bridge)
    assert not denominators_authorized(quality_without_gold)
    gold = pd.DataFrame([{"aparte_id": "a1", "texto_id_gold": "t1"}])
    quality = bridge_quality(bridge, gold)
    assert denominators_authorized(quality, min_precision=0.95, min_coverage=0.80)

    empty_bridge = build_camara_speech_bridge(interjections.head(0), speeches)
    assert "ponte_status" in empty_bridge
    assert bridge_quality(empty_bridge)["n"] == 0


def test_turn_segmentation_qualitative_gate_and_taxonomy() -> None:
    transcript = """O SR. JOÃO SOUZA (ABC - SP) – Inicio minha fala.

O SR. CARLOS LIMA (XYZ - RJ) – Concordo com V. Exa. e peço esclarecimento.

O SR. JOÃO SOUZA (ABC - SP) – Muito obrigado, Senador. Responderei ao ponto.
"""
    turns = segment_transcript_turns(transcript)
    assert turns["speaker_name"].tolist() == ["JOÃO SOUZA", "CARLOS LIMA", "JOÃO SOUZA"]
    speeches = pd.DataFrame([{"texto_id": "t1", "pronunciamento_id": "p1", "texto_analitico": transcript}])
    apartes = pd.DataFrame(
        [
            {
                "aparte_id": "a1",
                "source": "senado",
                "pronunciamento_id": "p1",
                "data": "2020-01-10",
                "ano": 2020,
                "orador_id": "1",
                "orador_nome": "João Souza",
                "orador_genero": "masculino",
                "aparteante_id": "2",
                "aparteante_nome": "Carlos Lima",
                "aparteante_genero": "masculino",
                "url_texto": "https://example.test",
            }
        ]
    )
    bridge = build_senate_speech_bridge(apartes, speeches)
    interactions = extract_interaction_turns(apartes, speeches, bridge)
    assert interactions.loc[0, "segmentacao_status"] == "segmentado_com_resposta"
    assert interactions.loc[0, "texto_aparte"].startswith("Concordo")
    assert interactions.loc[0, "texto_resposta"].startswith("Muito obrigado")
    assert segmentation_quality(interactions)["classification_authorized"] is False
    gold = pd.DataFrame(
        [
            {
                "interaction_id": "a1",
                "segmentacao_aparte_correta": True,
                "segmentacao_resposta_correta": True,
            }
        ]
    )
    quality = segmentation_quality(interactions, gold, min_reviewed=1)
    assert quality["classification_authorized"] is True
    codebook = qualitative_codebook_template(CONFIG)
    assert len(codebook) == 20
    sample = qualitative_review_sample(interactions, size=1)
    manual = manual_coding_template(sample, CONFIG)
    assert len(manual) == 20
    schema = qualitative_output_schema(CONFIG)
    assert schema["properties"]["atos_aparte"]["minItems"] == 10
    request = make_qualitative_batch_request(
        interactions.iloc[0],
        codebook="codebook preenchido",
        config=CONFIG,
    )
    assert request["url"] == "/v1/responses"
    assert request["body"]["model"] == "gpt-5.6-sol"
    assert "Muito obrigado" in request["body"]["input"]


def test_correlations_levels_and_differences_report_number_of_years() -> None:
    annual = pd.DataFrame(
        {
            "arena": ["camara"] * 4 + ["senado"] * 4,
            "ano": [2018, 2019, 2020, 2021] * 2,
            "metric": [1, 2, 4, 7, 2, 4, 8, 14],
        }
    )
    levels = paired_trajectory_correlations(annual, ["metric"])
    differences = paired_trajectory_correlations(annual, ["metric"], first_differences=True)
    assert levels.loc[0, "pearson_r"] == pytest.approx(1.0)
    assert levels.loc[0, "n_years"] == 4
    assert differences.loc[0, "n_years"] == 3
    assert differences.loc[0, "scale"] == "first_difference"


def test_topic_sample_is_balanced_deterministic_and_never_fills_missing_summary() -> None:
    rows = []
    for arena in ["camara", "senado", "congresso"]:
        for index in range(5):
            rows.append({"arena": arena, "ano": 2020, "texto_id": f"{arena}-{index}", "resumo": "" if index == 0 else f"Resumo {index}"})
    frame = pd.DataFrame(rows)
    first = balanced_summary_sample(frame, max_per_arena_year=2, seed=7)
    second = balanced_summary_sample(frame, max_per_arena_year=2, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert first.groupby(["arena", "ano"]).size().eq(2).all()
    assert first["resumo"].str.strip().ne("").all()


def test_jaccard_metrics_bootstrap_permutation_and_batch_reconciliation() -> None:
    assert np.isnan(multilabel_jaccard([], [])["jaccard"])
    assert multilabel_jaccard([], [])["both_empty"] is True
    truth = [{"a"}, set(), {"a", "b"}, {"b"}]
    prediction_a = [{"a"}, set(), {"a", "b"}, {"b"}]
    prediction_b = [set(), set(), {"a"}, {"a"}]
    summary, labels = evaluate_multilabel(truth, prediction_b, ["a", "b"])
    assert summary["both_empty"] == 1
    assert set(labels["categoria"]) == {"a", "b"}
    bootstrap = paired_cluster_bootstrap_jaccard(
        truth,
        prediction_a,
        prediction_b,
        ["s1", "s1", "s2", "s2"],
        repetitions=50,
        seed=3,
    )
    assert bootstrap["difference_a_minus_b"] > 0
    permutation = jaccard_permutation_test(truth, prediction_a, strata=["x"] * 4, repetitions=30, seed=4)
    assert 0 <= permutation["p_greater"] <= 1
    assert binary_kappa([True, False], [True, False]) == pytest.approx(1.0)
    assert count_errors([1, 2], [2, 2]) == {"mean_absolute_error": 0.5, "mean_bias_prediction_minus_truth": 0.5}

    request = make_batch_request(text_id="t1", text="Um texto.", codebook="codebook", config=CONFIG)
    assert request["url"] == "/v1/responses"
    assert request["body"]["model"] == "gpt-5.6-sol"
    schema = figures_output_schema(CONFIG.raw["rhetorical_figures"])
    figures = [
        {"categoria": category, "presente": False, "contagem": 0, "evidencias": [], "confianca": 0.8}
        for category in CONFIG.raw["rhetorical_figures"]
    ]
    response_line = json.dumps(
        {
            "custom_id": request["custom_id"],
            "response": {
                "status_code": 200,
                "body": {
                    "id": "resp_1",
                    "output": [{"content": [{"type": "output_text", "text": json.dumps({"texto_id": "t1", "figuras": figures, "observacao": None})}]}],
                    "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
                },
            },
        }
    )
    parsed, errors = parse_batch_output([response_line], request_index={request["custom_id"]: "t1"})
    assert errors.empty
    assert len(parsed) == 14
    assert parsed["texto_id"].eq("t1").all()
    assert schema["properties"]["figuras"]["minItems"] == 14


def test_figure_pilot_and_versioned_cost_table() -> None:
    eligible = pd.DataFrame(
        [
            {
                "texto_id": f"{arena}-{year}-{index}",
                "arena": arena,
                "ano": year,
                "parlamentar_id": f"p{index}",
                "n_palavras": 200 + index * 50,
            }
            for arena in ["camara", "senado", "congresso"]
            for year in [2012, 2018, 2024]
            for index in range(4)
        ]
    )
    pilot = balanced_figure_pilot(eligible, size=18, seed=9)
    assert len(pilot) == 18
    manual = figure_manual_coding_template(pilot, CONFIG.raw["rhetorical_figures"])
    assert len(manual) == 18 * 14
    usage = pd.DataFrame([{"model": "gpt-5.6-sol", "input_tokens": 1_000_000, "output_tokens": 500_000}])
    incomplete = pd.DataFrame(
        [
            {
                "model": "gpt-5.6-sol",
                "input_per_million": 1.0,
                "output_per_million": 2.0,
                "batch_discount": 0.5,
                "source_url": "",
                "as_of": "",
            }
        ]
    )
    with pytest.raises(ValueError, match="fonte oficial"):
        calculate_usage_cost(usage, incomplete)
    complete = incomplete.assign(source_url="https://example.test/pricing", as_of="2026-07-14")
    cost = calculate_usage_cost(usage, complete)
    assert cost.loc[0, "estimated_cost"] == pytest.approx(1.0)
