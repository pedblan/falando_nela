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
    filter_interjections_by_date,
    observed_expected_dyads,
)
from analise.discursos_plenario.apartes_qualitativos import (
    build_segmentation_candidates,
    build_segmentation_sources,
    build_senate_speech_bridge,
    ensure_qualitative_codebook,
    extract_interaction_turns,
    make_qualitative_batch_request,
    make_segmentation_batch_request,
    manual_coding_template,
    parse_qualitative_batch_output,
    parse_segmentation_batch_output,
    qualitative_codebook_template,
    qualitative_output_schema,
    qualitative_review_sample,
    segment_text_blocks,
    segment_transcript_turns,
    segmentation_output_schema,
    segmentation_quality,
    write_qualitative_batch_jsonl,
    write_segmentation_batch_jsonl,
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
from analise.discursos_plenario.snapshot import (
    apply_cleaning_rules,
    build_snapshot,
    coverage_required_years,
    run_snapshot,
)
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


def test_snapshot_can_gate_only_explicit_non_contiguous_recovery_years(tmp_path: Path) -> None:
    config_payload = json.loads(json.dumps(CONFIG.raw))
    config_payload.update(
        {
            "date_start": "2010-01-01",
            "date_end": "2016-12-31",
            "complete_year_start": 2015,
            "complete_year_end": 2016,
            "ytd_year": 2017,
            "coverage_required_years": {
                "camara": [2010, 2015, 2016],
                "senado": [2010, 2015, 2016],
                "congresso": [2010, 2015, 2016],
            },
        }
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    config = load_config(config_path)
    assert coverage_required_years(config)["camara"] == [2010, 2015, 2016]

    for arena in config_payload["arenas"]:
        path = tmp_path / config_payload["arenas"][arena]["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            _speech(arena=arena, text_id=f"{arena}-{year}", date=f"{year}-02-02", text="texto")
            for year in [2010, 2015, 2016]
        ]
        pd.DataFrame(rows).to_parquet(path, index=False)

    result = run_snapshot(data_root=tmp_path, run_id="non-contiguous", config_path=config_path)
    assert result["coverage_gate"]["passed"] is True
    assert result["coverage_gate"]["required_years_by_arena"] == config_payload["coverage_required_years"]

    missing_path = tmp_path / config_payload["arenas"]["camara"]["path"]
    missing = pd.read_parquet(missing_path)
    missing = missing.loc[~missing["data"].eq("2010-02-02")]
    missing.to_parquet(missing_path, index=False)
    with pytest.raises(ValueError, match="camara/2010"):
        run_snapshot(
            data_root=tmp_path,
            run_id="non-contiguous-missing",
            config_path=config_path,
        )


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


def test_interjection_date_cut_is_inclusive_and_precedes_analysis() -> None:
    frame = pd.DataFrame(
        {
            "aparte_id": ["before", "start", "end", "after", "missing"],
            "source": ["camara", "camara", "senado", "senado", "camara"],
            "data": ["2010-02-01", "2010-02-02T23:59:59", "2026-07-13T12:00:00", "2026-07-14", None],
            "ano": [1900] * 5,
        }
    )
    filtered, audit = filter_interjections_by_date(
        frame,
        date_start="2010-02-02",
        date_end="2026-07-13",
    )
    assert filtered["aparte_id"].tolist() == ["start", "end"]
    assert filtered["ano"].astype(int).tolist() == [2010, 2026]
    total = audit.loc[audit["source"].eq("total")].iloc[0]
    assert total[["entrada", "no_recorte", "data_ausente", "antes_do_recorte", "depois_do_recorte"]].tolist() == [5, 2, 1, 1, 1]


def test_interjection_date_cut_uses_brazilian_calendar_for_aware_timestamps() -> None:
    frame = pd.DataFrame(
        {
            "aparte_id": ["previous_local_day", "first_local_instant"],
            "source": ["camara", "camara"],
            "data": ["2010-02-02T01:30:00Z", "2010-02-02T03:00:00Z"],
        }
    )
    filtered, audit = filter_interjections_by_date(
        frame,
        date_start="2010-02-02",
        date_end="2010-02-02",
    )
    assert filtered["aparte_id"].tolist() == ["first_local_instant"]
    total = audit.loc[audit["source"].eq("total")].iloc[0]
    assert total["antes_do_recorte"] == 1


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

    conflicting_session = speeches.assign(sessao_id="S2")
    conflict_bridge = build_camara_speech_bridge(
        interjections,
        conflicting_session,
    )
    assert conflict_bridge.loc[0, "ponte_status"] == "ausente"


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


def test_ai_segmentation_blocks_reconstruct_exact_local_offsets() -> None:
    transcript = (
        "O SR. JOÃO SOUZA – Abertura do discurso.\\n"
        "O SR. CARLOS LIMA – Este é o aparte solicitado.\\n"
        "O SR. JOÃO SOUZA – Esta é a resposta explícita.\\n"
    )
    blocks = segment_text_blocks(transcript, max_chars=80)
    assert "".join(block["text"] for block in blocks) == transcript
    apart_block = next(block for block in blocks if "CARLOS LIMA" in block["text"])
    response_block = next(block for block in blocks if "resposta explícita" in block["text"])
    interjections = pd.DataFrame(
        [
            {
                "aparte_id": "a1",
                "source": "senado",
                "data": "2020-01-10",
                "ano": 2020,
                "orador_id": "1",
                "orador_nome": "João Souza",
                "orador_genero": "masculino",
                "aparteante_id": "2",
                "aparteante_nome": "Carlos Lima",
                "aparteante_genero": "masculino",
            },
            {
                "aparte_id": "a2",
                "source": "senado",
                "data": "2020-01-10",
                "ano": 2020,
                "orador_nome": "João Souza",
                "aparteante_nome": "Pessoa Ausente",
            },
            {
                "aparte_id": "a3",
                "source": "senado",
                "data": "2020-01-10",
                "ano": 2020,
                "orador_nome": "João Souza",
                "aparteante_nome": "Outra Pessoa",
            },
        ]
    )
    bridge = pd.DataFrame(
        [
            {"aparte_id": "a1", "texto_id": "t1", "ponte_status": "exato", "ponte_score": 6.0},
            {"aparte_id": "a2", "texto_id": None, "ponte_status": "ausente", "ponte_score": 0.0},
            {"aparte_id": "a3", "texto_id": "t1", "ponte_status": "exato", "ponte_score": 6.0},
        ]
    )
    candidates = build_segmentation_candidates(interjections, bridge)
    speeches = pd.DataFrame([{"texto_id": "t1", "texto_analitico": transcript}])
    sources = build_segmentation_sources(candidates, speeches, block_max_chars=80)
    assert sources[["texto_id", "candidatos"]].to_dict("records") == [{"texto_id": "t1", "candidatos": 2}]
    request = make_segmentation_batch_request(sources.iloc[0], config=CONFIG)
    assert request["url"] == "/v1/responses"
    assert request["body"]["model"] == "gpt-5.6-sol"
    assert "nunca devolva a transcrição" in request["body"]["input"]
    assert segmentation_output_schema()["additionalProperties"] is False
    payload = {
        "texto_id": "t1",
        "segmentos": [
            {
                "aparte_id": "a1",
                "status": "segmentado_com_resposta",
                "aparte_bloco_inicio": apart_block["block_id"],
                "aparte_bloco_fim": apart_block["block_id"],
                "resposta_bloco_inicio": response_block["block_id"],
                "resposta_bloco_fim": response_block["block_id"],
            },
            {
                "aparte_id": "a3",
                "status": "aparte_nao_localizado",
                "aparte_bloco_inicio": None,
                "aparte_bloco_fim": None,
                "resposta_bloco_inicio": None,
                "resposta_bloco_fim": None,
            },
        ],
    }
    output_line = json.dumps(
        {
            "custom_id": request["custom_id"],
            "response": {"status_code": 200, "body": {"output_text": json.dumps(payload)}},
        }
    )
    interactions, errors = parse_segmentation_batch_output(
        [output_line],
        request_index={request["custom_id"]: "t1"},
        sources=sources,
        candidates=candidates,
        model="gpt-5.6-sol",
    )
    assert errors.empty
    result = interactions.set_index("aparte_id")
    assert result.loc["a1", "texto_aparte"] == transcript[apart_block["char_start"] : apart_block["char_end"]]
    assert result.loc["a1", "aparte_char_start"] == apart_block["char_start"]
    assert result.loc["a1", "resposta_char_end"] == response_block["char_end"]
    assert result.loc["a2", "segmentacao_status"] == "sem_texto_validado"
    assert result.loc["a3", "segmentacao_status"] == "aparte_nao_localizado"

    missing_interactions, missing_errors = parse_segmentation_batch_output(
        [],
        request_index={request["custom_id"]: "t1"},
        sources=sources,
        candidates=candidates,
        model="gpt-5.6-sol",
    )
    assert missing_errors["error"].tolist() == ["request sem linha correspondente na saida do Batch"]
    assert (
        missing_interactions.set_index("aparte_id")
        .loc[["a1", "a3"], "segmentacao_status"]
        .eq("ia_sem_resultado")
        .all()
    )

    invalid_payload = json.loads(json.dumps(payload))
    invalid_payload["segmentos"][0]["aparte_bloco_inicio"] = "B999999"
    invalid_line = json.dumps(
        {
            "custom_id": request["custom_id"],
            "response": {"status_code": 200, "body": {"output_text": json.dumps(invalid_payload)}},
        }
    )
    invalid_interactions, invalid_errors = parse_segmentation_batch_output(
        [invalid_line],
        request_index={request["custom_id"]: "t1"},
        sources=sources,
        candidates=candidates,
        model="gpt-5.6-sol",
    )
    assert len(invalid_errors) == 1
    assert "bloco inexistente" in invalid_errors.loc[0, "error"]
    assert invalid_interactions["segmentacao_status"].isin(["ia_sem_resultado", "sem_texto_validado"]).all()


def test_segmentation_review_counts_only_complete_valid_answers_and_fills_sample() -> None:
    interactions = pd.DataFrame(
        [
            {
                "interaction_id": f"a{index:03d}",
                "segmentacao_status": "segmentado_com_resposta",
                "arena": "senado" if index % 2 else "camara",
                "ano": 2020,
                "aparteante_genero": "feminino" if index % 3 else "masculino",
                "orador_genero": "masculino",
                "texto_aparte": f"Aparte {index}",
                "texto_resposta": f"Resposta {index}",
            }
            for index in range(138)
        ]
    )
    assert len(qualitative_review_sample(interactions, size=200, seed=7)) == 138
    larger = pd.concat([interactions, interactions.assign(interaction_id=lambda frame: "x" + frame["interaction_id"])], ignore_index=True)
    assert len(qualitative_review_sample(larger, size=200, seed=7)) == 200
    gold = pd.DataFrame(
        [
            {"interaction_id": "a000", "segmentacao_aparte_correta": "", "segmentacao_resposta_correta": ""},
            {"interaction_id": "a001", "segmentacao_aparte_correta": False, "segmentacao_resposta_correta": True},
            {"interaction_id": "a002", "segmentacao_aparte_correta": "talvez", "segmentacao_resposta_correta": True},
        ]
    )
    quality = segmentation_quality(interactions, gold, min_reviewed=1)
    assert quality["review_rows_total"] == 3
    assert quality["reviewed"] == 1
    assert quality["review_rows_invalid"] == 1
    assert quality["precision_aparte"] == 0.0
    assert quality["precision_resposta"] == 1.0
    assert quality["classification_authorized"] is False

    whitespace = interactions.iloc[[0]].copy()
    whitespace["texto_aparte"] = "   "
    whitespace["texto_resposta"] = "\n"
    assert segmentation_quality(whitespace)["segmented"] == 0
    assert qualitative_review_sample(whitespace).empty


def test_batch_jsonl_writers_split_limits_and_keep_unique_ids(
    tmp_path: Path,
) -> None:
    sources = pd.DataFrame(
        [
                {
                    "texto_id": f"t{index}",
                    "texto_fonte": "Discurso",
                    "texto_fonte_sha256": f"hash-{index}",
                "blocos_json": json.dumps(
                    [
                        {
                            "block_id": "B000001",
                            "char_start": 0,
                            "char_end": 8,
                            "text": "Discurso",
                        }
                    ]
                ),
                "candidatos_json": json.dumps(
                    [{"aparte_id": f"a{index}"}]
                ),
            }
            for index in range(3)
        ]
    )
    segmentation_parts = write_segmentation_batch_jsonl(
        sources,
        tmp_path / "segmentacao.jsonl",
        config=CONFIG,
        max_requests=1,
    )
    assert len(segmentation_parts) == 3
    segmentation_requests = [
        json.loads(line)
        for path in segmentation_parts
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len({record["custom_id"] for record in segmentation_requests}) == 3
    assert all(path.stat().st_size > 0 for path in segmentation_parts)

    interactions = pd.DataFrame(
        [
            {
                "interaction_id": f"a{index}",
                "segmentacao_status": "segmentado_com_resposta",
                "texto_aparte": f"Aparte {index}",
                "texto_resposta": f"Resposta {index}",
            }
            for index in range(3)
        ]
    )
    qualitative_parts = write_qualitative_batch_jsonl(
        interactions,
        tmp_path / "qualitativo.jsonl",
        codebook="codebook preenchido",
        config=CONFIG,
        max_requests=1,
    )
    assert len(qualitative_parts) == 3
    qualitative_requests = [
        json.loads(line)
        for path in qualitative_parts
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len({record["custom_id"] for record in qualitative_requests}) == 3
    largest_line = max(
        len(
            (
                json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )
        for record in qualitative_requests
    )
    byte_limited_parts = write_qualitative_batch_jsonl(
        interactions,
        tmp_path / "qualitativo_por_bytes.jsonl",
        codebook="codebook preenchido",
        config=CONFIG,
        max_bytes=largest_line + 1,
    )
    assert len(byte_limited_parts) == 3
    assert all(
        path.stat().st_size <= largest_line + 1
        for path in byte_limited_parts
    )


def test_qualitative_batch_parser_reconciles_ids_and_missing_rows() -> None:
    payload = {
        "interaction_id": "i1",
        "atos_aparte": [
            {"categoria": category, "presente": False, "evidencia": None}
            for category in CONFIG.raw["interjection_speech_acts"]
        ],
        "atos_resposta": [
            {"categoria": category, "presente": False, "evidencia": None}
            for category in CONFIG.raw["response_speech_acts"]
        ],
        "possivel_descortesia": False,
        "evidencia_descortesia": None,
        "observacao": None,
    }
    valid = json.dumps(
        {
            "custom_id": "k1",
            "response": {
                "status_code": 200,
                "body": {"output_text": json.dumps(payload)},
            },
        }
    )
    unknown = json.dumps(
        {
            "custom_id": "unknown",
            "response": {"status_code": 500},
        }
    )
    results, errors = parse_qualitative_batch_output(
        [valid, unknown, valid, "{json inválido"],
        request_index={"k1": "i1", "k2": "i2"},
        model="gpt-test",
        config=CONFIG,
    )
    assert len(results) == 20
    assert results["interaction_id"].eq("i1").all()
    messages = errors["error"].tolist()
    assert "custom_id desconhecido" in messages
    assert "custom_id duplicado na saída" in messages
    assert "request sem linha correspondente na saída do Batch" in messages
    assert any("Expecting property name" in message for message in messages)


def test_existing_qualitative_codebook_is_never_overwritten(
    tmp_path: Path,
) -> None:
    path = tmp_path / "codebook.csv"
    created = ensure_qualitative_codebook(path, CONFIG)
    edited = created.copy()
    edited.loc[0, "definicao_operacional"] = "Definição humana"
    edited.to_csv(path, index=False)
    preserved = ensure_qualitative_codebook(path, CONFIG)
    assert preserved.loc[0, "definicao_operacional"] == "Definição humana"


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
