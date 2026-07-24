from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analise.discursos_plenario.apartes_episodios import (
    DIAGNOSTIC_CASES,
    build_episode_sources_v2,
    episode_output_schema_v2,
    episode_quality_v2,
    episode_review_sample_v2,
    make_episode_batch_request_v2,
    parse_episode_batch_output_v2,
    segment_raw_turns_v2,
    write_episode_batch_jsonl_v2,
)
from analise.discursos_plenario.config import load_config


CONFIG = load_config()


def _candidate(
    *,
    apart_id: str,
    text_id: str,
    participant_id: str,
    participant_name: str,
    speaker_name: str = "Oradora",
) -> dict[str, object]:
    return {
        "aparte_id": apart_id,
        "texto_id": text_id,
        "ponte_status": "exato",
        "arena": "camara",
        "source": "camara",
        "data": "2020-05-20",
        "ano": 2020,
        "aparteante_id": participant_id,
        "aparteante_nome": participant_name,
        "orador_id": "orador-1",
        "orador_nome": speaker_name,
    }


def _prepared(
    transcript: str,
    candidates: list[dict[str, object]],
) -> tuple[pd.DataFrame, ...]:
    text_id = str(candidates[0]["texto_id"])
    speeches = pd.DataFrame(
        [
            {
                "texto_id": text_id,
                "arena": "camara",
                "texto_analitico": transcript,
            }
        ]
    )
    return build_episode_sources_v2(
        pd.DataFrame(candidates),
        speeches,
        subturn_max_chars=120,
    )


def _candidate_payloads(source: pd.Series) -> dict[str, dict[str, object]]:
    return {
        str(candidate["aparte_id"]): candidate
        for candidate in json.loads(source["candidatos_json"])
    }


def _parse_payload(
    prepared: tuple[pd.DataFrame, ...],
    payload: dict[str, object],
) -> tuple[pd.DataFrame, ...]:
    candidates, participants, turns, units, sources, _, _ = prepared
    request = make_episode_batch_request_v2(sources.iloc[0], config=CONFIG)
    line = json.dumps(
        {
            "custom_id": request["custom_id"],
            "response": {
                "status_code": 200,
                "body": {"output_text": json.dumps(payload)},
            },
        }
    )
    return parse_episode_batch_output_v2(
        [line],
        request_index={request["custom_id"]: str(sources.iloc[0]["texto_id"])},
        sources=sources,
        candidates=candidates,
        participants=participants,
        raw_turns=turns,
        units=units,
        model="modelo-teste",
    )


def test_raw_turns_v2_are_deterministic_and_preserve_exact_offsets() -> None:
    transcript = (
        "Preâmbulo com Unicode: ação.\n"
        "O SR. ÁLVARO — Primeira fala.\n"
        "A SRA. BIA – Segunda fala.\n"
        "O SR. CÉSAR — Terceira fala."
    )

    first = segment_raw_turns_v2(transcript, texto_id="texto-1")
    second = segment_raw_turns_v2(transcript, texto_id="texto-1")

    pd.testing.assert_frame_equal(first, second)
    assert first["turno_id"].tolist() == [
        "T000001",
        "T000002",
        "T000003",
        "T000004",
    ]
    assert "".join(first["texto_turno"]) == transcript
    assert first["char_start"].tolist() == sorted(first["char_start"])
    for row in first.to_dict("records"):
        assert transcript[row["char_start"] : row["char_end"]] == row["texto_turno"]


def test_geovania_rogerio_supports_overlapping_episodes() -> None:
    transcript = (
        "A SRA. ORADORA — Início.\n"
        "A SRA. GEOVANIA — Minha questão.\n"
        "O SR. ROGÉRIO — Acrescento outra questão.\n"
        "A SRA. ORADORA — Geovania, sua resposta.\n"
        "A SRA. ORADORA — Rogério, outra resposta."
    )
    prepared = _prepared(
        transcript,
        [
            _candidate(
                apart_id="camara:2dbfcb9db21b05d4e50792d0",
                text_id="texto-geovania-rogerio",
                participant_id="geovania",
                participant_name="Geovania",
            ),
            _candidate(
                apart_id="camara:56b37524858b1b11e3eba216",
                text_id="texto-geovania-rogerio",
                participant_id="rogerio",
                participant_name="Rogério",
            ),
        ],
    )
    source = prepared[4].iloc[0]
    candidates = _candidate_payloads(source)
    geovania_id = candidates["camara:2dbfcb9db21b05d4e50792d0"][
        "participante_id"
    ]
    rogerio_id = candidates["camara:56b37524858b1b11e3eba216"][
        "participante_id"
    ]
    payload = {
        "texto_id": source["texto_id"],
        "atribuicoes_falante": [],
        "candidatos": [
            {
                "aparte_id": "camara:2dbfcb9db21b05d4e50792d0",
                "participante_id": geovania_id,
                "status": "localizado",
                "episodios": [
                    {
                        "falas_participante_ids": ["T000002"],
                        "backchannels_ids": [],
                        "respostas_orador_ids": ["T000004"],
                        "contexto_interveniente_ids": ["T000003"],
                    }
                ],
            },
            {
                "aparte_id": "camara:56b37524858b1b11e3eba216",
                "participante_id": rogerio_id,
                "status": "localizado",
                "episodios": [
                    {
                        "falas_participante_ids": ["T000003"],
                        "backchannels_ids": [],
                        "respostas_orador_ids": ["T000005"],
                        "contexto_interveniente_ids": ["T000004"],
                    }
                ],
            },
        ],
    }

    episodes, links, _, candidate_results, errors = _parse_payload(
        prepared,
        payload,
    )

    assert errors.empty
    assert len(episodes) == 2
    assert candidate_results["status_resultado"].eq("localizado").all()
    first, second = episodes.sort_values("char_start").to_dict("records")
    assert first["char_end"] > second["char_start"]
    assert set(links["papel_no_episodio"]) == {
        "fala_participante",
        "resposta_orador",
        "contexto_interveniente",
    }


def test_julio_campos_keeps_multiturn_aparte_and_all_backchannels() -> None:
    transcript = (
        "O SR. ORADOR — Abertura.\n"
        "O SR. JÚLIO CAMPOS — Primeiro ponto.\n"
        "O SR. ORADOR — Perfeito.\n"
        "O SR. JÚLIO CAMPOS — Segundo ponto.\n"
        "O SR. ORADOR — Perfeito.\n"
        "O SR. JÚLIO CAMPOS — Terceiro ponto.\n"
        "O SR. ORADOR — Respondo ao conjunto."
    )
    apart_id = "camara:4832ef40cc933090157a075b"
    prepared = _prepared(
        transcript,
        [
            _candidate(
                apart_id=apart_id,
                text_id="texto-julio",
                participant_id="julio",
                participant_name="Júlio Campos",
                speaker_name="Orador",
            )
        ],
    )
    source = prepared[4].iloc[0]
    participant_id = _candidate_payloads(source)[apart_id]["participante_id"]
    payload = {
        "texto_id": source["texto_id"],
        "atribuicoes_falante": [],
        "candidatos": [
            {
                "aparte_id": apart_id,
                "participante_id": participant_id,
                "status": "localizado",
                "episodios": [
                    {
                        "falas_participante_ids": [
                            "T000002",
                            "T000004",
                            "T000006",
                        ],
                        "backchannels_ids": ["T000003", "T000005"],
                        "respostas_orador_ids": ["T000007"],
                        "contexto_interveniente_ids": [],
                    }
                ],
            }
        ],
    }

    episodes, links, _, _, errors = _parse_payload(prepared, payload)

    assert errors.empty
    episode = episodes.iloc[0]
    assert episode["n_falas_participante"] == 3
    assert episode["n_backchannels"] == 2
    assert episode["texto_backchannels"].count("Perfeito") == 2
    assert links["ordem_cronologica"].tolist() == list(range(1, 7))


def test_izalci_keeps_request_and_permission_outside_participant_speech() -> None:
    transcript = (
        "O SR. ORADOR — Abertura.\n"
        "O SR. IZALCI — V.Exa. me concede um aparte?\n"
        "O SR. ORADOR — Pois não, Deputado Izalci.\n"
        "O SR. IZALCI — A questão substantiva é esta.\n"
        "O SR. ORADOR — Sobre a questão, respondo."
    )
    apart_id = "camara:3876d2f8cca7b70cf8a3b987"
    prepared = _prepared(
        transcript,
        [
            _candidate(
                apart_id=apart_id,
                text_id="texto-izalci",
                participant_id="izalci",
                participant_name="Izalci",
                speaker_name="Orador",
            )
        ],
    )
    source = prepared[4].iloc[0]
    participant_id = _candidate_payloads(source)[apart_id]["participante_id"]
    payload = {
        "texto_id": source["texto_id"],
        "atribuicoes_falante": [],
        "candidatos": [
            {
                "aparte_id": apart_id,
                "participante_id": participant_id,
                "status": "localizado",
                "episodios": [
                    {
                        "falas_participante_ids": ["T000004"],
                        "backchannels_ids": [],
                        "respostas_orador_ids": ["T000005"],
                        "contexto_interveniente_ids": ["T000002", "T000003"],
                    }
                ],
            }
        ],
    }

    episodes, links, _, _, errors = _parse_payload(prepared, payload)

    assert errors.empty
    episode = episodes.iloc[0]
    assert "concede" not in episode["texto_participante"]
    assert "concede" in episode["texto_contexto"]
    assert "Pois não" in episode["texto_contexto"]
    roles_by_turn = links.set_index("turno_id")["papel_no_episodio"].to_dict()
    assert roles_by_turn["T000002"] == "contexto_interveniente"
    assert roles_by_turn["T000003"] == "contexto_interveniente"


def test_v2_request_is_one_per_transcript_ids_only_and_sharded(
    tmp_path: Path,
) -> None:
    transcript = (
        "O SR. ORADOR — Abertura.\n"
        "O SR. PARTICIPANTE — Questão.\n"
        "O SR. ORADOR — Resposta."
    )
    prepared = _prepared(
        transcript,
        [
            _candidate(
                apart_id="a1",
                text_id="texto-1",
                participant_id="p1",
                participant_name="Participante",
                speaker_name="Orador",
            )
        ],
    )
    source = prepared[4].iloc[0]
    request = make_episode_batch_request_v2(source, config=CONFIG)
    repeated = make_episode_batch_request_v2(source, config=CONFIG)
    schema = episode_output_schema_v2()
    episode_properties = schema["properties"]["candidatos"]["items"][
        "properties"
    ]["episodios"]["items"]["properties"]

    assert request["custom_id"] == repeated["custom_id"]
    assert set(episode_properties) == {
        "falas_participante_ids",
        "backchannels_ids",
        "respostas_orador_ids",
        "contexto_interveniente_ids",
    }
    assert all(
        token not in field
        for field in episode_properties
        for token in ["conteudo", "trecho", "transcricao"]
    )
    assert request["body"]["metadata"]["pipeline_version"] == (
        "episodios_interacao_v2"
    )

    second = source.copy()
    second["texto_id"] = "texto-2"
    second["texto_fonte_sha256"] = "f" * 64
    sources = pd.DataFrame([source, second])
    parts = write_episode_batch_jsonl_v2(
        sources,
        tmp_path / "episodios.jsonl",
        config=CONFIG,
        max_requests=1,
    )
    assert len(parts) == 2
    assert sum(len(path.read_text(encoding="utf-8").splitlines()) for path in parts) == 2


def test_review_gate_requires_all_four_dimensions_and_diagnostic_cases() -> None:
    rows = []
    required_cases = list(DIAGNOSTIC_CASES)
    for index in range(30):
        rows.append(
            {
                "episodio_id": f"ep-{index:02d}",
                "episodio_fingerprint_v2": f"fp-{index:02d}",
                "caso_diagnostico": (
                    required_cases[index] if index < len(required_cases) else ""
                ),
                "status_episodio": "localizado",
                "texto_id": f"t-{index:02d}",
                "arena": "camara",
                "ano": 2020,
                "char_start": index * 10,
                "char_end": index * 10 + 5,
                "ordem_inicio": index,
                "revisao_v1_disponivel": False,
            }
        )
    episodes = pd.DataFrame(rows)
    links = pd.DataFrame(
        [
            {
                "episodio_id": row["episodio_id"],
                "papel_no_episodio": "fala_participante",
                "unidade_id": f"T{index:06d}.S001",
                "ordem_cronologica": 1,
            }
            for index, row in enumerate(rows, start=1)
        ]
    )
    review = episode_review_sample_v2(episodes, links, size=30, seed=7)
    for column in [
        "atribuicao_participantes_correta",
        "episodio_completo",
        "atribuicao_respostas_correta",
        "contexto_suficiente",
    ]:
        review[column] = True

    passed = episode_quality_v2(
        episodes,
        review,
        min_reviewed=30,
        min_precision=0.95,
        required_diagnostic_cases=required_cases,
    )
    assert passed["qualitative_authorized_v2"] is True
    assert passed["diagnostic_gate_passed"] is True

    review.loc[
        review["caso_diagnostico"].eq(required_cases[0]),
        "contexto_suficiente",
    ] = False
    failed = episode_quality_v2(
        episodes,
        review,
        min_reviewed=30,
        min_precision=0.95,
        required_diagnostic_cases=required_cases,
    )
    assert failed["qualitative_authorized_v2"] is False
    assert failed["diagnostic_gate_passed"] is False
