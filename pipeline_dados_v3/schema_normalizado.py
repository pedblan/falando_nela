from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import os
import platform
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from pipeline_dados_v3.inventario_metadados_raw import (
    DEFAULT_MAX_JSON_BYTES,
    canonical_json_value,
    declared_record_type,
    escape_path_key,
    flatten_fields,
    is_relative_to,
    mounted_drive_root,
    structural_fingerprint,
    technical_type,
    value_state,
)


APPROVED_INVENTORY_OPERATION_ID = "raw-metadata-full-20260724t184418z"
APPROVED_INVENTORY_MANIFEST_SHA256 = (
    "b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9"
)
DEFAULT_RAW_ROOT = Path("/content/drive/MyDrive/falando_nela/data/raw")
DEFAULT_OUTPUT_BASE = Path("/content/falando_nela_v3_schema")
DEFAULT_GLOBAL_RUNTIME_DIR = Path("/content/falando_nela_g02_global_core")
DEFAULT_GLOBAL_DRIVE_DIR = Path(
    "/content/drive/MyDrive/falando_nela/auditoria/"
    "pipeline_dados_v3/g02/schema-global-gpt56-20260724"
)
DEFAULT_BATCH_RUNTIME_DIR = Path("/content/falando_nela_g02_batch_mapping")
DEFAULT_BATCH_DRIVE_DIR = Path(
    "/content/drive/MyDrive/falando_nela/auditoria/"
    "pipeline_dados_v3/g02/schema-field-mapping-batch-gpt56-20260725"
)
SCHEMA_VERSION = "normalized-schema-evidence-v3.1"
SPEC_REF = "specs/pipeline_dados_v3/02_schema_normalizado/requirements.md"
PROMPT_VERSION = "schema-proposal-gpt56-v1"
PROPOSAL_SCHEMA_VERSION = "schema-proposal-response-v1"
REQUESTED_MODEL = "gpt-5.6"
BATCH_REQUESTED_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_METADATA_VALUE_LIMIT = 200
DEFAULT_PREVIEW_LIMIT = 500
GLOBAL_CATALOG_VERSION = "gpt56-global-field-catalog-v2"
GLOBAL_CATALOG_PROMPT_VERSION = "gpt56-global-schema-prompt-v1"
GLOBAL_PROPOSAL_SCHEMA_VERSION = "gpt56-global-schema-proposal-v1"
GLOBAL_PROPOSAL_OPERATION_ID = "schema-global-gpt56-20260724"
BATCH_MAPPING_OPERATION_ID = "schema-field-mapping-batch-gpt56-20260725"
BATCH_MAPPING_PROMPT_VERSION = "gpt56-field-mapping-batch-v1"
BATCH_MAPPING_SCHEMA_VERSION = "gpt56-field-mapping-response-v1"
BATCH_MAPPING_VOCABULARY_VERSION = "normalized-schema-evidence-v3.1-batch-v1"
BATCH_MAPPING_CHUNK_SIZE = 400
BATCH_REPAIR_CHUNK_SIZE = 100
BATCH_MAPPING_MAX_OUTPUT_TOKENS = 32_000
REJECTED_LINE_FIELDS = [
    "severity",
    "issue_type",
    "relative_path",
    "record_number",
    "field_path",
    "detail",
    "raw_line_sha256",
    "treatment",
]
BATCH_CONSERVATIVE_QUEUED_INPUT_TOKENS = 1_500_000
GLOBAL_CATALOG_STANDARD_SAMPLE_FIELDS = 16
GLOBAL_CATALOG_CCJ_SAMPLE_FIELDS = 96
GLOBAL_CATALOG_SAMPLES_PER_FIELD = 2
GPT56_MAX_INPUT_TOKENS = 922_000
GPT56_GLOBAL_MAX_OUTPUT_TOKENS = 32_000
GPT56_LONG_INPUT_PER_MILLION = Decimal("10")
GPT56_LONG_CACHED_INPUT_PER_MILLION = Decimal("1")
GPT56_LONG_CACHE_WRITE_PER_MILLION = Decimal("12.5")
GPT56_LONG_OUTPUT_PER_MILLION = Decimal("45")
GPT56_BATCH_INPUT_PER_MILLION = Decimal("2.5")
GPT56_BATCH_CACHED_INPUT_PER_MILLION = Decimal("0.25")
GPT56_BATCH_OUTPUT_PER_MILLION = Decimal("15")
GLOBAL_ARCHIVE_ARTIFACTS = (
    "catalogo_global_gpt56.txt",
    "catalogo_global_crosswalk.csv",
    "catalogo_global_amostras.csv",
    "catalogo_global_manifest.json",
    "upload_token_count.json",
)

APPROVED_COUNTS = {
    "records_observed": 1_148_754,
    "records_read": 1_148_740,
    "records_rejected": 14,
    "record_groups": 50,
    "field_paths": 23_786,
}
APPROVED_TYPE_CONFLICTS = {
    ("senado", "ccj_notas"): 540,
    ("senado", "parlamentares"): 1,
    ("senado", "plenario_discursos"): 2,
}
APPROVED_CCJ_PATHS = 20_523

APPROVED_LOGICAL_FIELDS = (
    "source",
    "dataset",
    "record_type",
    "source_record_id",
    "collected_at",
    "coverage_start_date",
    "coverage_end_date",
    "event_official_id",
    "committee_meeting_id",
    "plenary_session_id",
    "legislative_session_id",
    "pronouncement_official_id",
    "taquigraphic_segment_id",
    "event_start_datetime",
    "event_end_datetime",
    "committee_meeting_start_datetime",
    "committee_meeting_end_datetime",
    "plenary_session_start_datetime",
    "plenary_session_end_datetime",
    "pronouncement_datetime",
    "arena_identifier_namespace",
    "arena_identifier_value",
    "arena_role",
    "arena_name_source",
    "arena_acronym_source",
    "event_title_source",
    "committee_meeting_title_source",
    "plenary_session_title_source",
    "event_status_code_source",
    "event_status_label_source",
    "speech_type_code_source",
    "speech_type_acronym_source",
    "speech_type_description_source",
    "speech_type_active_indicator_source",
    "proposition_official_id",
    "legislative_matter_official_id",
    "legislative_process_official_id",
    "proposition_type_acronym_source",
    "legislative_matter_type_acronym_source",
    "proposition_identification_source",
    "proposition_number",
    "proposition_year",
    "proposition_abstract_source",
    "document_identifier_namespace",
    "document_identifier_role",
    "document_official_id",
    "document_type_code_source",
    "document_type_acronym_source",
    "document_type_label_source",
    "document_type_collector_derived",
    "document_url_source",
    "document_url_role",
    "document_declared_media_type_source",
    "retrieval_response_content_type",
    "detected_file_media_type",
    "opinion_deliberative_status_collector_derived",
    "opinion_deliberative_status_code_source",
    "opinion_deliberative_status_label_source",
    "opinion_defeated_indicator_collector_derived",
    "opinion_defeated_indicator_source",
    "person_identifier_namespace",
    "person_identifier_role",
    "person_official_id",
    "person_civil_name_source",
    "person_parliamentary_name_source",
    "person_electoral_name_source",
    "speaker_display_name_source",
    "author_actor_type_source",
    "author_actor_name_source",
    "speaking_role_source",
    "author_office_source",
    "author_function_source",
    "form_of_address_source",
    "party_identifier_namespace",
    "party_official_id",
    "party_acronym_source",
    "party_name_source",
    "affiliation_role",
    "affiliation_start_date",
    "affiliation_end_date",
    "federative_unit_source",
    "federative_unit_role",
    "sex_label_recorded_by_source",
    "text_artifact_role",
    "text_production_method",
    "text_content_source",
    "text_retrieval_status_collector_derived",
    "request_metadata",
    "response_metadata",
    "speech_indexing_source_raw",
    "proposition_subject_source",
)

BATCH_FIELD_FAMILIES = (
    {
        "family": "provenance_and_coverage",
        "fields": (
            "source",
            "dataset",
            "record_type",
            "source_record_id",
            "collected_at",
            "coverage_start_date",
            "coverage_end_date",
        ),
        "rule": (
            "Envelope técnico e período explícito de coleta/consulta; não usar "
            "como substituto de entidade legislativa ou data de ocorrência."
        ),
        "examples": (
            "$.source -> source",
            "$.source_id -> source_record_id",
            "$.periodo.data_inicio -> coverage_start_date",
        ),
    },
    {
        "family": "events_meetings_sessions_and_time",
        "fields": (
            "event_official_id",
            "committee_meeting_id",
            "plenary_session_id",
            "legislative_session_id",
            "pronouncement_official_id",
            "taquigraphic_segment_id",
            "event_start_datetime",
            "event_end_datetime",
            "committee_meeting_start_datetime",
            "committee_meeting_end_datetime",
            "plenary_session_start_datetime",
            "plenary_session_end_datetime",
            "pronouncement_datetime",
            "event_title_source",
            "committee_meeting_title_source",
            "plenary_session_title_source",
            "event_status_code_source",
            "event_status_label_source",
            "speech_type_code_source",
            "speech_type_acronym_source",
            "speech_type_description_source",
            "speech_type_active_indicator_source",
        ),
        "rule": (
            "Evento, reunião de comissão/colegiado, sessão plenária, sessão "
            "legislativa, pronunciamento e segmento taquigráfico são domínios "
            "distintos. Data sem hora não vira meia-noite; código, sigla, "
            "descrição e indicador oficial permanecem separados."
        ),
        "examples": (
            "CodigoReuniao de CCJ -> committee_meeting_id",
            "CodigoSessao plenária -> plenary_session_id",
            "CodigoPronunciamento -> pronouncement_official_id",
        ),
    },
    {
        "family": "arenas_and_institutions",
        "fields": (
            "arena_identifier_namespace",
            "arena_identifier_value",
            "arena_role",
            "arena_name_source",
            "arena_acronym_source",
        ),
        "rule": (
            "Casa, órgão, comissão e colegiado são ocorrências institucionais "
            "qualificadas por namespace e papel; CCJ e CCJC não são aliases."
        ),
        "examples": (
            "órgão organizador CCJC -> arena_role + arena_acronym_source",
            "colegiado receptor CCJ -> ocorrência institucional distinta",
        ),
    },
    {
        "family": "propositions_matters_and_processes",
        "fields": (
            "proposition_official_id",
            "legislative_matter_official_id",
            "legislative_process_official_id",
            "proposition_type_acronym_source",
            "legislative_matter_type_acronym_source",
            "proposition_identification_source",
            "proposition_number",
            "proposition_year",
            "proposition_abstract_source",
            "proposition_subject_source",
        ),
        "rule": (
            "Proposição, matéria e processo são entidades distintas. A forma "
            "tipo/número/ano é identificação pública preservada como unidade, "
            "sem decomposição inferida nem leitura do texto parlamentar."
        ),
        "examples": (
            "PEC 45/2019 -> proposition_identification_source",
            "número explícito 45 -> proposition_number",
            "assunto estruturado da API -> proposition_subject_source",
        ),
    },
    {
        "family": "documents_and_opinions",
        "fields": (
            "document_identifier_namespace",
            "document_identifier_role",
            "document_official_id",
            "document_type_code_source",
            "document_type_acronym_source",
            "document_type_label_source",
            "document_type_collector_derived",
            "document_url_source",
            "document_url_role",
            "document_declared_media_type_source",
            "retrieval_response_content_type",
            "detected_file_media_type",
            "opinion_deliberative_status_collector_derived",
            "opinion_deliberative_status_code_source",
            "opinion_deliberative_status_label_source",
            "opinion_defeated_indicator_collector_derived",
            "opinion_defeated_indicator_source",
        ),
        "rule": (
            "Preservar namespace e função de cada ID/URL. Tipo declarado, "
            "Content-Type HTTP e detecção técnica são distintos. Situação "
            "oficial não se confunde com derivação do coletor; vencido não "
            "significa automaticamente substituído."
        ),
        "examples": (
            "ID de inteiro teor -> document_official_id + document_identifier_role",
            "Content-Type da resposta -> retrieval_response_content_type",
            "flag oficial vencido -> opinion_defeated_indicator_source",
        ),
    },
    {
        "family": "persons_roles_and_affiliations",
        "fields": (
            "person_identifier_namespace",
            "person_identifier_role",
            "person_official_id",
            "person_civil_name_source",
            "person_parliamentary_name_source",
            "person_electoral_name_source",
            "speaker_display_name_source",
            "author_actor_type_source",
            "author_actor_name_source",
            "speaking_role_source",
            "author_office_source",
            "author_function_source",
            "form_of_address_source",
            "party_identifier_namespace",
            "party_official_id",
            "party_acronym_source",
            "party_name_source",
            "affiliation_role",
            "affiliation_start_date",
            "affiliation_end_date",
            "federative_unit_source",
            "federative_unit_role",
            "sex_label_recorded_by_source",
        ),
        "rule": (
            "IDs e nomes são qualificados por fonte, papel e ocorrência; nome "
            "não resolve identidade. Partido e UF preservam papel e tempo. "
            "Sexo é somente o rótulo registrado pela API, não identidade de gênero."
        ),
        "examples": (
            "nome parlamentar -> person_parliamentary_name_source",
            "papel de fala Relator -> speaking_role_source",
            "sexo M/F da API -> sex_label_recorded_by_source",
        ),
    },
    {
        "family": "text_transport_and_thematic_metadata",
        "fields": (
            "text_artifact_role",
            "text_production_method",
            "text_content_source",
            "text_retrieval_status_collector_derived",
            "speech_indexing_source_raw",
        ),
        "rule": (
            "Transportar texto e indexação literal sem inferência semântica. "
            "Artefatos, ordem, origem e método permanecem distintos; status "
            "de obtenção é controle derivado por tentativa."
        ),
        "examples": (
            "TextoIntegral -> text_content_source",
            "Indexacao/keywords da fala -> speech_indexing_source_raw",
            "resultado de download -> text_retrieval_status_collector_derived",
        ),
    },
    {
        "family": "technical_transport",
        "fields": (
            "request_metadata",
            "response_metadata",
        ),
        "rule": (
            "Objetos técnicos de requisição e resposta; nunca preenchem "
            "automaticamente campos substantivos."
        ),
        "examples": (
            "$.request -> request_metadata",
            "$.response -> response_metadata",
        ),
    },
)

APPROVED_ENTITY_COLLECTIONS = (
    ("committee_meetings", "committee_meeting"),
    ("committee_meeting_observations", "committee_meeting_observation"),
    ("meeting_parts", "meeting_part"),
    ("agenda_items", "agenda_item"),
    ("events", "event"),
    ("committee_embedded_events", "committee_embedded_event"),
    ("plenary_sessions", "plenary_session"),
    ("legislative_sessions", "legislative_session"),
    ("pronouncements", "pronouncement"),
    ("propositions", "proposition"),
    ("legislative_matters", "legislative_matter"),
    ("legislative_processes", "legislative_process"),
    ("documents", "document"),
    ("opinions", "opinion"),
    ("persons", "person"),
    ("participations", "participation"),
    ("authorship_assignments", "authorship_assignment"),
    ("rapporteur_assignments", "rapporteur_assignment"),
    ("agenda_item_outcomes", "agenda_item_outcome"),
    ("meeting_states", "meeting_state_observation"),
    ("meeting_arenas", "meeting_arena_assignment"),
    ("meeting_videos", "meeting_video"),
    ("text_artifacts", "text_artifact"),
    ("taquigraphic_quarters", "taquigraphic_quarter"),
    ("taquigraphic_markers", "taquigraphic_marker"),
)

APPROVED_CARDINALITIES = (
    {
        "source_entity": "legible_raw_record",
        "relationship": "has_source_value_occurrence",
        "target_entity": "source_value_occurrence",
        "cardinality": "1:N",
    },
    {
        "source_entity": "committee_meeting",
        "relationship": "has_source_observation",
        "target_entity": "committee_meeting_observation",
        "cardinality": "1:N",
    },
    {
        "source_entity": "committee_meeting",
        "relationship": "has_part",
        "target_entity": "meeting_part",
        "cardinality": "0:N",
    },
    {
        "source_entity": "meeting_part",
        "relationship": "has_agenda_item",
        "target_entity": "agenda_item",
        "cardinality": "0:N",
    },
    {
        "source_entity": "meeting_part",
        "relationship": "has_embedded_event",
        "target_entity": "committee_embedded_event",
        "cardinality": "0:N",
    },
    {
        "source_entity": "agenda_item",
        "relationship": "has_outcome_matter_document_or_authorship",
        "target_entity": "contextual_entity",
        "cardinality": "0:N",
    },
    {
        "source_entity": "legislative_matter_or_process",
        "relationship": "has_rapporteur_or_authorship",
        "target_entity": "assignment",
        "cardinality": "0:N",
    },
    {
        "source_entity": "document",
        "relationship": "has_context_link",
        "target_entity": "document_context",
        "cardinality": "0:N",
    },
    {
        "source_entity": "committee_embedded_event",
        "relationship": "has_related_matter_or_involvement",
        "target_entity": "contextual_entity",
        "cardinality": "0:N",
    },
    {
        "source_entity": "participation",
        "relationship": "has_presentation_document",
        "target_entity": "document",
        "cardinality": "0:N",
    },
    {
        "source_entity": "committee_meeting",
        "relationship": "has_state_video_quarter_or_arena",
        "target_entity": "meeting_context",
        "cardinality": "0:N",
    },
    {
        "source_entity": "committee_meeting_observation",
        "relationship": "has_presidency",
        "target_entity": "participation",
        "cardinality": "0..1",
    },
    {
        "source_entity": "committee_meeting_observation",
        "relationship": "has_legislative_session_context",
        "target_entity": "legislative_session",
        "cardinality": "0..1",
    },
    {
        "source_entity": "taquigraphic_quarter",
        "relationship": "has_marker",
        "target_entity": "taquigraphic_marker",
        "cardinality": "0:N",
    },
    {
        "source_entity": "pronouncement",
        "relationship": "has_thematic_metadata",
        "target_entity": "speech_indexing_source_raw",
        "cardinality": "0:N",
    },
)

APPROVED_TECHNICAL_DUPLICATIONS = (
    {
        "rule_id": "alias-camara-event-id",
        "decision": "technical_duplication",
        "field_ids": ["F00282", "F00284"],
        "scope": {
            "source": "camara",
            "dataset": "ccjc_eventos",
            "record_types": ["notas_taquigraficas"],
        },
        "source_paths": [
            "$.payload.CodigoEvento",
            "$.payload.evento_id",
        ],
        "canonical_target": "event_official_id",
    },
    {
        "rule_id": "alias-camara-notas-text",
        "decision": "technical_duplication",
        "field_ids": ["F00283", "F00371"],
        "scope": {
            "source": "camara",
            "dataset": "ccjc_eventos",
            "record_types": ["notas_taquigraficas"],
        },
        "source_paths": [
            "$.payload.TextoIntegral",
            "$.payload.texto",
        ],
        "canonical_target": "text_content_source",
    },
    {
        "rule_id": "alias-camara-parecer-text",
        "decision": "technical_duplication",
        "field_ids": ["F00400", "F00504"],
        "scope": {
            "source": "camara",
            "dataset": "pareceres_pec",
            "record_types": ["parecer_pec_texto"],
        },
        "source_paths": [
            "$.payload.TextoIntegral",
            "$.payload.texto",
        ],
        "canonical_target": "text_content_source",
    },
    {
        "rule_id": "alias-senado-meeting-id",
        "decision": "technical_duplication",
        "field_ids": ["F13699", "F13701"],
        "supporting_field_ids": ["F16569", "F16570"],
        "scope": {
            "source": "senado",
            "dataset": "ccj_notas",
            "record_types": [
                "notas_taquigraficas",
                "notas_taquigraficas_status",
            ],
        },
        "source_paths": [
            "$.payload.CodigoReuniao",
            "$.payload.codigo_reuniao",
        ],
        "canonical_target": "committee_meeting_id",
    },
    {
        "rule_id": "alias-senado-notas-text",
        "decision": "technical_duplication",
        "field_ids": ["F13700", "F16508"],
        "scope": {
            "source": "senado",
            "dataset": "ccj_notas",
            "record_types": ["notas_taquigraficas"],
        },
        "source_paths": [
            "$.payload.TextoIntegral",
            "$.payload.texto",
        ],
        "canonical_target": "text_content_source",
    },
    {
        "rule_id": "alias-senado-pronouncement-id-congresso",
        "decision": "technical_duplication",
        "field_ids": ["F22062", "F22065"],
        "scope": {
            "source": "senado",
            "dataset": "congresso_discursos",
            "record_types": ["pronunciamento_texto"],
        },
        "source_paths": [
            "$.payload.CodigoPronunciamento",
            "$.payload.codigo_pronunciamento",
        ],
        "canonical_target": "pronouncement_official_id",
    },
    {
        "rule_id": "alias-senado-pronouncement-id-plenario",
        "decision": "technical_duplication",
        "field_ids": ["F23487", "F23490"],
        "scope": {
            "source": "senado",
            "dataset": "plenario_discursos",
            "record_types": ["pronunciamento_texto"],
        },
        "source_paths": [
            "$.payload.CodigoPronunciamento",
            "$.payload.codigo_pronunciamento",
        ],
        "canonical_target": "pronouncement_official_id",
    },
    {
        "rule_id": "alias-ccj-agenda-detail-subtrees",
        "decision": "not_alias",
        "field_ids": ["F13711", "F16294"],
        "scope": {
            "source": "senado",
            "dataset": "ccj_notas",
            "record_types": [
                "agenda_periodo",
                "reuniao_detalhe",
                "notas_taquigraficas",
            ],
        },
        "source_paths": [
            "$.payload.metadata.agenda",
            "$.payload.metadata.detalhe",
        ],
        "canonical_target": None,
    },
)

INVENTORY_ARTIFACTS = {
    "inventario_arquivos.csv",
    "inventario_campos.csv",
    "valores_observados.csv",
    "amostras_campos.jsonl",
    "inconsistencias.csv",
    "relatorio.md",
}

FIELD_BOOK_FIELDS = [
    "source",
    "dataset",
    "record_type",
    "field_path",
    "technical_types",
    "records_universe",
    "field_absent",
    "present_null",
    "present_empty",
    "present_filled",
    "fill_rate",
    "cardinality",
    "cardinality_method",
    "string_length_min",
    "string_length_median",
    "string_length_max",
    "first_partition",
    "last_partition",
    "type_conflict",
    "semantic_role",
    "decision",
    "proposed_category",
    "proposed_logical_type",
    "rule_id",
    "decision_rationale",
    "decision_by",
    "decision_at",
]

GLOBAL_CATALOG_CROSSWALK_FIELDS = [
    "field_id",
    "group_id",
    *FIELD_BOOK_FIELDS[:19],
]

GLOBAL_CATALOG_SAMPLE_FIELDS = [
    "field_id",
    "channel",
    "source",
    "dataset",
    "record_type",
    "field_path",
    "sample_hash",
    "value_type",
    "value_json",
]

ALIAS_FIELDS = [
    "candidate_id",
    "source",
    "dataset",
    "record_type",
    "field_a",
    "field_b",
    "comparison_scope",
    "candidate_signal",
    "comparator",
    "rule_id",
    "records_universe",
    "u",
    "ab",
    "equal",
    "different",
    "only_a",
    "only_b",
    "coincidence_rate",
    "overlap_rate",
    "only_a_rate",
    "only_b_rate",
    "a_absent",
    "a_null",
    "a_empty",
    "b_absent",
    "b_null",
    "b_empty",
    "agree_coordinates",
    "differ_coordinates",
    "link_matched",
    "link_unmatched_a",
    "link_unmatched_b",
    "link_ambiguous",
    "evidence_status",
    "human_decision",
    "human_rationale",
]

MAPPING_FIELDS = [
    "pair_id",
    "packet_id",
    "proposal_id",
    "condition",
    "canonical_field",
    "logical_type",
    "operation",
    "source",
    "dataset",
    "record_type",
    "source_paths_json",
    "evidence_ids_json",
    "context_refs_json",
    "api_category_refs_json",
    "possible_aliases_json",
    "caveats_json",
    "needs_human_review",
    "human_decision",
    "human_rationale",
]

EXECUTION_FIELDS = [
    "pair_id",
    "packet_id",
    "condition",
    "requested_model",
    "resolved_model",
    "reasoning_effort",
    "prompt_version",
    "prompt_sha256",
    "schema_version",
    "schema_sha256",
    "input_sha256",
    "response_sha256",
    "status",
    "refusal",
    "error",
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "latency_seconds",
    "cost_usd",
    "pricing_ref",
]

AB_FIELDS = [
    "pair_id",
    "packet_id",
    "condition",
    "reviewed_proposals",
    "accepted_proposals",
    "unsupported_categories",
    "incorrect_aliases",
    "insufficient_evidence",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "latency_seconds",
    "cost_usd",
    "human_preview_decision",
]


@dataclass(frozen=True)
class SchemaConfig:
    raw_root: Path
    inventory_root: Path
    output_base: Path
    operation_id: str
    code_commit: str
    expected_inventory_operation_id: str = APPROVED_INVENTORY_OPERATION_ID
    expected_inventory_manifest_sha256: str | None = (
        APPROVED_INVENTORY_MANIFEST_SHA256
    )
    enforce_approved_counts: bool = True
    metadata_value_limit: int = DEFAULT_METADATA_VALUE_LIMIT
    preview_limit: int = DEFAULT_PREVIEW_LIMIT
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES
    max_alias_candidates_per_group: int | None = None
    field_review_path: Path | None = None
    manual_alias_path: Path | None = None
    api_categories_path: Path | None = None
    progress_every_files: int = 100

    @property
    def operation_root(self) -> Path:
        return self.output_base / self.operation_id


@dataclass(frozen=True)
class RawRecord:
    source: str
    dataset: str
    record_type: str
    relative_path: str
    record_number: int
    technical_kind: str
    value: Any

    @property
    def coordinate(self) -> str:
        return f"{self.relative_path}#{self.record_number}"


@dataclass(frozen=True)
class AliasCandidate:
    source: str
    dataset: str
    record_type: str
    field_a: str
    field_b: str
    comparison_scope: str = "same_record"
    candidate_signal: str = "same_terminal_key"

    @property
    def candidate_id(self) -> str:
        payload = "\0".join(
            [
                self.source,
                self.dataset,
                self.record_type,
                self.field_a,
                self.field_b,
                self.comparison_scope,
            ]
        )
        return "alias_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class LinkRule:
    rule_id: str
    link_path_a: str
    link_path_b: str
    value_path_a: str
    value_path_b: str
    link_field_role_a: str
    link_field_role_b: str
    approved_by: str

    def validate(self) -> None:
        if not self.rule_id.strip() or not self.approved_by.strip():
            raise ValueError("Vínculo entre registros exige regra e aprovação.")
        if (
            self.link_field_role_a != "metadata"
            or self.link_field_role_b != "metadata"
        ):
            raise ValueError(
                "Vínculo entre registros só pode usar metadados aprovados."
            )
        for name in (
            "link_path_a",
            "link_path_b",
            "value_path_a",
            "value_path_b",
        ):
            if not getattr(self, name).startswith("$"):
                raise ValueError(f"Caminho inválido na regra de vínculo: {name}")


@dataclass
class AliasMetrics:
    records_universe: int = 0
    u: int = 0
    ab: int = 0
    equal: int = 0
    different: int = 0
    only_a: int = 0
    only_b: int = 0
    a_absent: int = 0
    a_null: int = 0
    a_empty: int = 0
    b_absent: int = 0
    b_null: int = 0
    b_empty: int = 0
    agree_coordinates: list[str] = field(default_factory=list)
    differ_coordinates: list[str] = field(default_factory=list)
    link_matched: int | str = ""
    link_unmatched_a: int | str = ""
    link_unmatched_b: int | str = ""
    link_ambiguous: int | str = ""
    evidence_status: str = "measured"

    def observe(
        self,
        values_a: Sequence[Any] | None,
        values_b: Sequence[Any] | None,
        coordinate: str,
    ) -> None:
        self.records_universe += 1
        state_a = occurrence_state(values_a)
        state_b = occurrence_state(values_b)
        if state_a == "absent":
            self.a_absent += 1
        elif state_a == "null":
            self.a_null += 1
        elif state_a == "empty":
            self.a_empty += 1
        if state_b == "absent":
            self.b_absent += 1
        elif state_b == "null":
            self.b_null += 1
        elif state_b == "empty":
            self.b_empty += 1

        filled_a = state_a == "filled"
        filled_b = state_b == "filled"
        if not (filled_a or filled_b):
            return
        self.u += 1
        if filled_a and filled_b:
            self.ab += 1
            if typed_occurrence_token(values_a or []) == typed_occurrence_token(
                values_b or []
            ):
                self.equal += 1
                append_coordinate(self.agree_coordinates, coordinate)
            else:
                self.different += 1
                append_coordinate(self.differ_coordinates, coordinate)
        elif filled_a:
            self.only_a += 1
        else:
            self.only_b += 1

    def validate(self) -> None:
        if self.u != self.ab + self.only_a + self.only_b:
            raise AssertionError("U não reconcilia com AB + SA + SB.")
        if self.ab != self.equal + self.different:
            raise AssertionError("AB não reconcilia com E + D.")

    def finalize_universe(self, records_universe: int) -> None:
        if records_universe < self.records_universe:
            raise AssertionError("Universo final menor que registros auditados.")
        unseen = records_universe - self.records_universe
        self.a_absent += unseen
        self.b_absent += unseen
        self.records_universe = records_universe

    def rates(self) -> dict[str, str]:
        self.validate()
        return {
            "coincidence_rate": rate(self.equal, self.ab),
            "overlap_rate": rate(self.ab, self.u),
            "only_a_rate": rate(self.only_a, self.u),
            "only_b_rate": rate(self.only_b, self.u),
        }


@dataclass
class SampleCandidate:
    score: tuple[Any, ...]
    coordinate: str
    record: RawRecord
    sanitized: Any
    structure_hash: str
    filled_paths: int
    max_depth: int
    conflict_paths: int


class StructuralSampleSelector:
    def __init__(
        self,
        field_stats: Mapping[tuple[str, str, str, str], Mapping[str, str]],
        field_roles: Mapping[tuple[str, str, str, str], str],
        *,
        metadata_value_limit: int,
    ) -> None:
        self.field_stats = field_stats
        self.field_roles = field_roles
        self.metadata_value_limit = metadata_value_limit
        self._candidates: dict[
            tuple[str, str, str], dict[str, list[SampleCandidate]]
        ] = defaultdict(lambda: defaultdict(list))

    def observe(self, raw_record: RawRecord) -> None:
        group = (raw_record.source, raw_record.dataset, raw_record.record_type)
        occurrences = occurrences_by_path(raw_record.value)
        filled = {
            path
            for path, values in occurrences.items()
            if occurrence_state(values) == "filled"
        }
        fill_rates = [
            Decimal(
                self.field_stats.get((*group, path), {}).get("fill_rate", "0") or "0"
            )
            for path in filled
        ]
        rarity = sum((Decimal("1") - value for value in fill_rates), Decimal("0"))
        conflict_paths = sum(
            truthy(self.field_stats.get((*group, path), {}).get("type_conflict", ""))
            for path in filled
        )
        depth = max((path_depth(path) for path in occurrences), default=0)
        sanitized = sanitize_record(
            raw_record.value,
            group=group,
            field_roles=self.field_roles,
            metadata_value_limit=self.metadata_value_limit,
        )
        structure_hash = sha256_json(structure_signature(raw_record.value))
        common = {
            "coordinate": raw_record.coordinate,
            "record": raw_record,
            "sanitized": sanitized,
            "structure_hash": structure_hash,
            "filled_paths": len(filled),
            "max_depth": depth,
            "conflict_paths": conflict_paths,
        }
        role_scores = {
            "typical": (
                sum(fill_rates, Decimal("0")),
                len(filled),
                -depth,
            ),
            "sparse": (-len(filled), -depth),
            "rare_or_conflict": (conflict_paths, rarity, depth, len(filled)),
        }
        for role, score in role_scores.items():
            candidate = SampleCandidate(score=score, **common)
            bucket = self._candidates[group][role]
            bucket.append(candidate)
            bucket.sort(key=lambda item: (item.score, item.coordinate), reverse=True)
            del bucket[8:]

    def rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for group in sorted(self._candidates):
            used: set[str] = set()
            for role in ("typical", "sparse", "rare_or_conflict"):
                selected = next(
                    (
                        candidate
                        for candidate in self._candidates[group][role]
                        if candidate.coordinate not in used
                    ),
                    None,
                )
                if selected is None:
                    continue
                used.add(selected.coordinate)
                raw_record = selected.record
                evidence_id = stable_id(
                    "evidence",
                    *group,
                    role,
                    raw_record.coordinate,
                    selected.structure_hash,
                )
                rows.append(
                    {
                        "evidence_id": evidence_id,
                        "channel": "evidence",
                        "source": raw_record.source,
                        "dataset": raw_record.dataset,
                        "record_type": raw_record.record_type,
                        "relative_path": raw_record.relative_path,
                        "record_number": raw_record.record_number,
                        "selection_role": role,
                        "selection_reason": {
                            "filled_paths": selected.filled_paths,
                            "max_depth": selected.max_depth,
                            "conflict_paths": selected.conflict_paths,
                            "criterion": "deterministic_structural_score",
                        },
                        "structure_hash": selected.structure_hash,
                        "record": selected.sanitized,
                    }
                )
        return rows


class PreviewSelector:
    def __init__(
        self,
        field_rows: Mapping[tuple[str, str, str, str], Mapping[str, str]],
        field_roles: Mapping[tuple[str, str, str, str], str],
        *,
        preview_limit: int,
    ) -> None:
        self.field_rows = field_rows
        self.field_roles = field_roles
        self.preview_limit = preview_limit
        self._best: dict[tuple[str, str, str, str], tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def observe(self, raw_record: RawRecord) -> None:
        group = (raw_record.source, raw_record.dataset, raw_record.record_type)
        for path, values in occurrences_by_path(raw_record.value).items():
            key = (*group, path)
            if self.field_roles.get(key) != "text":
                continue
            median = decimal_or_zero(self.field_rows.get(key, {}).get("string_length_median"))
            for occurrence_index, value in enumerate(values):
                if not isinstance(value, str) or value_state(value) != "filled":
                    continue
                digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                score = (abs(Decimal(len(value)) - median), digest)
                context_id = stable_id(
                    "context",
                    *group,
                    path,
                    raw_record.coordinate,
                    str(occurrence_index),
                    digest,
                )
                preview = value[: self.preview_limit]
                row = {
                    "context_id": context_id,
                    "channel": "context_only",
                    "context_only": True,
                    "approved_for_gpt": False,
                    "approval_by": "",
                    "approval_at": "",
                    "approval_rationale": "",
                    "source": raw_record.source,
                    "dataset": raw_record.dataset,
                    "record_type": raw_record.record_type,
                    "field_path": path,
                    "relative_path": raw_record.relative_path,
                    "record_number": raw_record.record_number,
                    "occurrence_index": occurrence_index,
                    "start": 0,
                    "end": len(preview),
                    "full_length": len(value),
                    "full_sha256": digest,
                    "selection_criterion": "closest_to_inventory_median_then_sha256",
                    "preview": preview,
                }
                current = self._best.get(key)
                if current is None or score < current[0]:
                    self._best[key] = (score, row)

    def rows(self) -> list[dict[str, Any]]:
        return [self._best[key][1] for key in sorted(self._best)]


def validate_inventory(
    config: SchemaConfig,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    manifest_path = config.inventory_root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Manifest G01 ausente: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_hash = sha256_file(manifest_path)
    if config.enforce_approved_counts:
        expected_manifest_hash = config.expected_inventory_manifest_sha256
        if (
            expected_manifest_hash is None
            or len(expected_manifest_hash) != 64
            or any(char not in "0123456789abcdef" for char in expected_manifest_hash)
        ):
            raise ValueError(
                "A execução integral exige o SHA-256 aprovado do manifest G01."
            )
        if manifest_hash != expected_manifest_hash:
            raise ValueError("Hash aprovado do manifest G01 não confere.")
    if manifest.get("operation_id") != config.expected_inventory_operation_id:
        raise ValueError(
            "operation_id G01 divergente: "
            f"{manifest.get('operation_id')!r} != "
            f"{config.expected_inventory_operation_id!r}"
        )
    if manifest.get("execution_status") != "succeeded":
        raise ValueError("O inventário G01 não terminou com succeeded.")
    if manifest.get("scope_mode") != "full":
        raise ValueError("G02 exige inventário integral, não smoke.")

    output_refs = manifest.get("outputs")
    if not isinstance(output_refs, list):
        raise ValueError("Manifest G01 sem lista outputs.")
    refs_by_name = {str(item.get("name")): item for item in output_refs}
    if set(refs_by_name) != INVENTORY_ARTIFACTS:
        raise ValueError(
            "Artefatos G01 divergentes: "
            f"esperados={sorted(INVENTORY_ARTIFACTS)}; "
            f"observados={sorted(refs_by_name)}"
        )
    for name in sorted(INVENTORY_ARTIFACTS):
        path = config.inventory_root / name
        if not path.is_file():
            raise ValueError(f"Artefato G01 ausente: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != refs_by_name[name].get("sha256"):
            raise ValueError(f"Hash G01 divergente para {name}.")

    fields = read_csv(config.inventory_root / "inventario_campos.csv")
    issues = read_csv(config.inventory_root / "inconsistencias.csv")
    if config.enforce_approved_counts:
        counts = manifest.get("counts", {})
        for name, expected in APPROVED_COUNTS.items():
            if int(counts.get(name, -1)) != expected:
                raise ValueError(
                    f"Contagem G01 divergente para {name}: "
                    f"{counts.get(name)!r} != {expected}"
                )
        conflicts = Counter(
            (row["source"], row["dataset"])
            for row in fields
            if truthy(row["type_conflict"])
        )
        if sum(conflicts.values()) != 543:
            raise ValueError("O inventário não possui exatamente 543 conflitos.")
        for group, expected in APPROVED_TYPE_CONFLICTS.items():
            if conflicts[group] != expected:
                raise ValueError(
                    f"Conflitos divergentes em {'/'.join(group)}: "
                    f"{conflicts[group]} != {expected}"
                )
        ccj_paths = sum(
            row["source"] == "senado" and row["dataset"] == "ccj_notas"
            for row in fields
        )
        if ccj_paths != APPROVED_CCJ_PATHS:
            raise ValueError(
                f"senado/ccj_notas possui {ccj_paths}, não {APPROVED_CCJ_PATHS} caminhos."
            )
        rejected = int(counts["records_rejected"])
        if int(counts["records_observed"]) != int(counts["records_read"]) + rejected:
            raise ValueError("Registros observados não reconciliam lidos + rejeitados.")
    return manifest, fields, issues


def build_compact_global_catalog(
    *,
    inventory_manifest: Mapping[str, Any],
    inventory_manifest_sha256: str,
    field_rows: Sequence[Mapping[str, Any]],
    issue_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    output_dir: Path,
    expected_operation_id: str = APPROVED_INVENTORY_OPERATION_ID,
    catalog_profile: str = "full",
    standard_sample_fields: int = GLOBAL_CATALOG_STANDARD_SAMPLE_FIELDS,
    ccj_sample_fields: int = GLOBAL_CATALOG_CCJ_SAMPLE_FIELDS,
    samples_per_field: int = GLOBAL_CATALOG_SAMPLES_PER_FIELD,
) -> dict[str, Any]:
    """Build a lossless, line-oriented catalog for one global model request.

    The model-facing text factors repeated provenance and path prefixes, while
    the companion crosswalk preserves every original inventory column. Existing
    identical outputs are reused; divergent files are never overwritten.
    """

    if inventory_manifest.get("operation_id") != expected_operation_id:
        raise ValueError("O catálogo global exige o operation_id G01 esperado.")
    if (
        len(inventory_manifest_sha256) != 64
        or any(char not in "0123456789abcdef" for char in inventory_manifest_sha256)
    ):
        raise ValueError("SHA-256 do manifest G01 inválido.")
    if standard_sample_fields < 0 or ccj_sample_fields < 0:
        raise ValueError("A quantidade de campos amostrados não pode ser negativa.")
    if samples_per_field < 0:
        raise ValueError("samples_per_field não pode ser negativo.")
    if catalog_profile not in {"full", "schema_core"}:
        raise ValueError("catalog_profile deve ser full ou schema_core.")

    ordered_fields = sorted(
        (dict(row) for row in field_rows),
        key=lambda row: (
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            str(row.get("record_type", "")),
            str(row.get("field_path", "")),
        ),
    )
    keys = [
        (
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            str(row.get("record_type", "")),
            str(row.get("field_path", "")),
        )
        for row in ordered_fields
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("O inventário contém chaves de campo duplicadas.")

    counts = dict(inventory_manifest.get("counts") or {})
    if int(counts.get("field_paths", -1)) != len(ordered_fields):
        raise ValueError("A contagem de caminhos diverge do manifest G01.")
    observed_groups = sorted({key[:3] for key in keys})
    if int(counts.get("record_groups", -1)) != len(observed_groups):
        raise ValueError("A contagem de grupos diverge do manifest G01.")
    if int(counts.get("records_observed", -1)) != (
        int(counts.get("records_read", -1))
        + int(counts.get("records_rejected", -1))
    ):
        raise ValueError("Registros observados não reconciliam lidos + rejeitados.")

    group_ids = {
        group: f"G{index:03d}"
        for index, group in enumerate(observed_groups, start=1)
    }
    field_ids = {
        key: f"F{index:05d}"
        for index, key in enumerate(keys, start=1)
    }
    type_codes = _global_catalog_type_codes(ordered_fields)

    fields_by_group: defaultdict[
        tuple[str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for row in ordered_fields:
        fields_by_group[
            (
                str(row.get("source", "")),
                str(row.get("dataset", "")),
                str(row.get("record_type", "")),
            )
        ].append(row)

    lines = [
        f"# {GLOBAL_CATALOG_VERSION}",
        "# CONTRACT",
        f"operation_id={expected_operation_id}",
        f"manifest_sha256={inventory_manifest_sha256}",
        f"records_observed={int(counts['records_observed'])}",
        f"records_read={int(counts['records_read'])}",
        f"records_rejected={int(counts['records_rejected'])}",
        f"record_groups={len(observed_groups)}",
        f"field_paths={len(ordered_fields)}",
        f"catalog_profile={catalog_profile}",
        "identity=source+dataset+record_type+original_field_path",
        "path_rule=inside each G block, original path is P prefix plus F path component",
        "decision_rule=proposal_only;no_automatic_drop_merge_priority_or_fill",
        "text_rule=no_semantic_inference_from_parliamentary_text",
        "# TYPE_CODES",
    ]
    for technical_type_name, code in sorted(
        type_codes.items(), key=lambda item: item[1]
    ):
        lines.append(f"T|{code}|{_catalog_json(technical_type_name)}")
    lines.extend(
        [
            "# FIELD_GRAMMAR",
            "# G|group_id|source|dataset|record_type|fields|conflicts|special",
            "# P|shared_original_path_prefix; empty means F contains full path",
        ]
    )
    if catalog_profile == "schema_core":
        lines.append(
            "# F|field_id|path_component|type_codes|"
            "filled/universe:state_mask|cardinality|string_max|conflict"
        )
        lines.append(
            "# state_mask: a=absent,n=null,e=empty,f=filled; "
            "complete metrics remain in the crosswalk"
        )
    else:
        lines.append(
            "# F|field_id|path_component|type_codes|"
            "universe,absent,null,empty,filled|cardinality|"
            "string_min,median,max|first_partition,last_partition|conflict"
        )
    lines.append("# FIELDS")

    crosswalk_rows: list[dict[str, Any]] = []
    for group in observed_groups:
        group_rows = fields_by_group[group]
        conflict_count = sum(
            truthy(str(row.get("type_conflict", ""))) for row in group_rows
        )
        special = "senado_ccj_notas" if group[:2] == ("senado", "ccj_notas") else "-"
        lines.append(
            "|".join(
                [
                    "G",
                    group_ids[group],
                    *(_catalog_json(value) for value in group),
                    str(len(group_rows)),
                    str(conflict_count),
                    special,
                ]
            )
        )
        for prefix, prefixed_rows in _global_catalog_prefix_blocks(group_rows):
            lines.append(f"P|{_catalog_json(prefix)}")
            for row, path_component in prefixed_rows:
                key = (
                    str(row.get("source", "")),
                    str(row.get("dataset", "")),
                    str(row.get("record_type", "")),
                    str(row.get("field_path", "")),
                )
                technical_types = [
                    value
                    for value in str(row.get("technical_types", "")).split("|")
                    if value
                ]
                encoded_types = ",".join(type_codes[value] for value in technical_types)
                if catalog_profile == "schema_core":
                    model_stats = [
                        _global_catalog_core_presence(row),
                        _global_catalog_cardinality(row),
                        _catalog_cell(row.get("string_length_max", "")),
                    ]
                else:
                    model_stats = [
                        ",".join(
                            _catalog_cell(row.get(name, ""))
                            for name in (
                                "records_universe",
                                "field_absent",
                                "present_null",
                                "present_empty",
                                "present_filled",
                            )
                        ),
                        _global_catalog_cardinality(row),
                        ",".join(
                            _catalog_cell(row.get(name, ""))
                            for name in (
                                "string_length_min",
                                "string_length_median",
                                "string_length_max",
                            )
                        ),
                        ",".join(
                            _catalog_cell(row.get(name, ""))
                            for name in ("first_partition", "last_partition")
                        ),
                    ]
                lines.append(
                    "|".join(
                        [
                            "F",
                            field_ids[key],
                            _catalog_json(path_component),
                            encoded_types,
                            *model_stats,
                            "!" if truthy(str(row.get("type_conflict", ""))) else "-",
                        ]
                    )
                )
                crosswalk_rows.append(
                    {
                        "field_id": field_ids[key],
                        "group_id": group_ids[group],
                        **{
                            name: row.get(name, "")
                            for name in GLOBAL_CATALOG_CROSSWALK_FIELDS[2:]
                        },
                    }
                )

    selected_sample_keys: set[tuple[str, str, str, str]] = set()
    for group in observed_groups:
        limit = (
            ccj_sample_fields
            if group[:2] == ("senado", "ccj_notas")
            else standard_sample_fields
        )
        selected_sample_keys.update(
            _select_global_catalog_sample_keys(fields_by_group[group], limit)
        )

    samples_by_key: defaultdict[
        tuple[str, str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for sample in sample_rows:
        key = (
            str(sample.get("source", "")),
            str(sample.get("dataset", "")),
            str(sample.get("record_type", "")),
            str(sample.get("field_path", "")),
        )
        if key in selected_sample_keys and key in field_ids:
            samples_by_key[key].append(dict(sample))

    lines.extend(
        [
            "# CONTEXT_SAMPLES",
            (
                "# Deterministic context_only samples from G01; they cannot support "
                "a column or alias, and long strings remain length+sha256 descriptors."
            ),
            "# S|field_id|context_only|technical_type_code|safe_value_json",
        ]
    )
    sample_crosswalk_rows: list[dict[str, Any]] = []
    for key in sorted(samples_by_key):
        samples = sorted(
            samples_by_key[key],
            key=lambda row: str(row.get("sample_hash", "")),
        )[:samples_per_field]
        for sample in samples:
            value_type = str(sample.get("value_type", ""))
            safe_value = _global_catalog_safe_value(sample.get("value"))
            lines.append(
                "|".join(
                    [
                        "S",
                        field_ids[key],
                        "context_only",
                        type_codes.get(value_type, _catalog_json(value_type)),
                        _catalog_json(safe_value),
                    ]
                )
            )
            sample_crosswalk_rows.append(
                {
                    "field_id": field_ids[key],
                    "channel": "context_only",
                    "source": key[0],
                    "dataset": key[1],
                    "record_type": key[2],
                    "field_path": key[3],
                    "sample_hash": sample.get("sample_hash", ""),
                    "value_type": value_type,
                    "value_json": _catalog_json(safe_value),
                }
            )

    lines.extend(
        [
            "# INVENTORY_ISSUES",
            "# X|severity|issue_type|relative_path|record_number|field_path|detail",
        ]
    )
    for issue in sorted(
        (dict(row) for row in issue_rows),
        key=lambda row: (
            str(row.get("relative_path", "")),
            str(row.get("record_number", "")),
            str(row.get("issue_type", "")),
            str(row.get("field_path", "")),
        ),
    ):
        lines.append(
            "|".join(
                [
                    "X",
                    *(
                        _catalog_json(issue.get(name, ""))
                        for name in (
                            "severity",
                            "issue_type",
                            "relative_path",
                            "record_number",
                            "field_path",
                            "detail",
                        )
                    ),
                ]
            )
        )

    catalog_text = "\n".join(lines) + "\n"
    crosswalk_text = _csv_text(
        crosswalk_rows,
        GLOBAL_CATALOG_CROSSWALK_FIELDS,
    )
    samples_text = _csv_text(
        sample_crosswalk_rows,
        GLOBAL_CATALOG_SAMPLE_FIELDS,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "catalog": output_dir / "catalogo_global_gpt56.txt",
        "crosswalk": output_dir / "catalogo_global_crosswalk.csv",
        "samples": output_dir / "catalogo_global_amostras.csv",
        "manifest": output_dir / "catalogo_global_manifest.json",
    }
    _write_reusable_text(paths["catalog"], catalog_text)
    _write_reusable_text(paths["crosswalk"], crosswalk_text)
    _write_reusable_text(paths["samples"], samples_text)

    conflict_count = sum(
        truthy(str(row.get("type_conflict", ""))) for row in ordered_fields
    )
    ccj_path_count = sum(
        row.get("source") == "senado" and row.get("dataset") == "ccj_notas"
        for row in ordered_fields
    )
    output_refs = [
        {
            "name": paths[name].name,
            "sha256": sha256_file(paths[name]),
            "bytes": paths[name].stat().st_size,
            "rows": row_count,
        }
        for name, row_count in (
            ("catalog", len(lines)),
            ("crosswalk", len(crosswalk_rows)),
            ("samples", len(sample_crosswalk_rows)),
        )
    ]
    catalog_manifest = {
        "catalog_version": GLOBAL_CATALOG_VERSION,
        "catalog_profile": catalog_profile,
        "prompt_version": GLOBAL_CATALOG_PROMPT_VERSION,
        "inventory_operation_id": expected_operation_id,
        "inventory_manifest_sha256": inventory_manifest_sha256,
        "counts": {
            "records_observed": int(counts["records_observed"]),
            "records_read": int(counts["records_read"]),
            "records_rejected": int(counts["records_rejected"]),
            "record_groups": len(observed_groups),
            "field_paths": len(ordered_fields),
            "type_conflicts": conflict_count,
            "ccj_notas_field_paths": ccj_path_count,
            "inventory_issues": len(issue_rows),
            "safe_sample_rows": len(sample_crosswalk_rows),
        },
        "sample_policy": {
            "selection": (
                "typed_conflicts_and_evenly_spread_field_paths_without_semantic_reading"
            ),
            "channel": "context_only",
            "standard_fields_per_group": standard_sample_fields,
            "ccj_notas_fields_per_group": ccj_sample_fields,
            "samples_per_field": samples_per_field,
            "long_strings": "length_and_sha256_only",
        },
        "invariants": {
            "all_inventory_paths_in_crosswalk": len(crosswalk_rows)
            == len(ordered_fields),
            "automatic_drop_merge_priority_or_fill": 0,
            "raw_records_read": 0,
            "normalized_records_materialized": 0,
        },
        "outputs": output_refs,
        "next_action": (
            "Upload catalogo_global_gpt56.txt as user_data and count the exact "
            "full Responses input before requesting a global schema proposal."
        ),
    }
    manifest_text = json.dumps(
        catalog_manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    _write_reusable_text(paths["manifest"], manifest_text)
    return {
        "paths": paths,
        "manifest": catalog_manifest,
        "field_rows": crosswalk_rows,
        "sample_rows": sample_crosswalk_rows,
    }


def global_schema_prompt() -> str:
    return (
        "Analise integralmente o arquivo de catálogo do Falando Nela v3. "
        "Ele representa todos os caminhos inventariados em G01; reconstrua cada "
        "caminho como o prefixo da linha P corrente mais o componente da linha F, "
        "dentro do grupo G corrente. Proponha um vocabulário global e coerente de "
        "colunas normalizadas para pesquisa comparável de pronunciamentos, debates, "
        "sessões, reuniões, documentos e pareceres sobre conteúdo constitucional "
        "na Câmara e no Senado. Priorize arena, data, evento ou sessão, proposição "
        "ou documento, parlamentar ou orador, partido, UF, sexo ou gênero informado "
        "pela fonte, identificadores oficiais e proveniência. Use somente nomes de "
        "caminhos, tipos, presença, cardinalidade e estrutura. As linhas S são apenas "
        "context_only: não podem sustentar coluna, preenchimento ou alias. Não extraia "
        "nem infira informação de texto parlamentar. Não descarte, funda, priorize "
        "nem preencha campo automaticamente. "
        "Trate aliases apenas como candidatos para auditoria recorde a recorde. "
        "Mantenha os 543 conflitos explícitos, dedique tratamento próprio a "
        "senado/ccj_notas e reconheça as 14 linhas rejeitadas. Nesta resposta, "
        "defina o schema canônico, famílias de campos, critérios de mapeamento e "
        "casos que exigem revisão; não tente emitir uma decisão detalhada para cada "
        "um dos 23.786 campos. Cite somente field_id existentes no catálogo. "
        "Uma hipótese de alias deve permanecer candidate_only e exigir auditoria "
        "record_by_record_exact_typed. Toda proposta permanece sujeita à revisão "
        "humana e não autoriza alteração dos dados ou do schema."
    )


def global_proposal_json_schema() -> dict[str, Any]:
    """Closed response contract for the one-shot global vocabulary proposal."""

    string_array = {"type": "array", "items": {"type": "string"}}
    field_id_array = {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "minLength": 1},
    }
    canonical_column = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "canonical_name",
            "label_pt",
            "definition",
            "research_role",
            "logical_type",
            "cardinality",
            "nullable",
            "representative_field_ids",
            "mapping_operations",
            "api_alignment",
            "caveats",
            "needs_human_review",
        ],
        "properties": {
            "canonical_name": {"type": "string", "minLength": 1},
            "label_pt": {"type": "string", "minLength": 1},
            "definition": {"type": "string", "minLength": 1},
            "research_role": {
                "type": "string",
                "enum": [
                    "provenance",
                    "temporal",
                    "arena",
                    "event",
                    "document",
                    "proposition",
                    "person",
                    "party",
                    "geography",
                    "demographic_source_reported",
                    "text_transport",
                    "technical_control",
                    "other",
                ],
            },
            "logical_type": {
                "type": "string",
                "enum": [
                    "string",
                    "integer",
                    "number",
                    "boolean",
                    "date",
                    "datetime",
                    "object",
                    "array",
                    "typed_union",
                    "unknown",
                ],
            },
            "cardinality": {
                "type": "string",
                "enum": ["scalar", "repeated", "either", "unknown"],
            },
            "nullable": {"type": "boolean"},
            "representative_field_ids": field_id_array,
            "mapping_operations": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "direct_copy",
                        "rename",
                        "lossless_cast",
                        "closed_map",
                        "preserve_unmapped",
                        "needs_human_rule",
                    ],
                },
            },
            "api_alignment": string_array,
            "caveats": string_array,
            "needs_human_review": {"type": "boolean"},
        },
    }
    field_family = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "family_id",
            "description",
            "canonical_candidates",
            "representative_field_ids",
            "scope_groups",
            "selection_criteria",
            "unmapped_policy",
        ],
        "properties": {
            "family_id": {"type": "string", "minLength": 1},
            "description": {"type": "string", "minLength": 1},
            "canonical_candidates": string_array,
            "representative_field_ids": field_id_array,
            "scope_groups": string_array,
            "selection_criteria": string_array,
            "unmapped_policy": {
                "type": "string",
                "enum": [
                    "preserve_unmapped",
                    "defer",
                    "conflict_open",
                ],
            },
        },
    }
    alias_hypothesis = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "hypothesis_id",
            "field_ids",
            "rationale",
            "required_audit",
            "status",
        ],
        "properties": {
            "hypothesis_id": {"type": "string", "minLength": 1},
            "field_ids": {
                "type": "array",
                "minItems": 2,
                "items": {"type": "string", "minLength": 1},
            },
            "rationale": {"type": "string", "minLength": 1},
            "required_audit": {
                "type": "string",
                "enum": ["record_by_record_exact_typed"],
            },
            "status": {"type": "string", "enum": ["candidate_only"]},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "proposal_version",
            "status",
            "summary",
            "canonical_columns",
            "field_families",
            "alias_hypotheses",
            "type_conflict_policy",
            "rejected_records_policy",
            "batch_mapping_contract",
            "unresolved_questions",
            "insufficiency_reasons",
        ],
        "properties": {
            "proposal_version": {
                "type": "string",
                "enum": [GLOBAL_PROPOSAL_SCHEMA_VERSION],
            },
            "status": {
                "type": "string",
                "enum": ["proposal", "insufficient_evidence"],
            },
            "summary": {"type": "string"},
            "canonical_columns": {
                "type": "array",
                "items": canonical_column,
            },
            "field_families": {
                "type": "array",
                "items": field_family,
            },
            "alias_hypotheses": {
                "type": "array",
                "items": alias_hypothesis,
            },
            "type_conflict_policy": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "general_policy",
                    "ccj_notas_policy",
                    "representative_field_ids",
                ],
                "properties": {
                    "general_policy": string_array,
                    "ccj_notas_policy": string_array,
                    "representative_field_ids": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
            "rejected_records_policy": string_array,
            "batch_mapping_contract": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "allowed_decisions",
                    "required_output_per_field",
                    "prohibitions",
                ],
                "properties": {
                    "schema_version": {"type": "string", "minLength": 1},
                    "allowed_decisions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "map",
                                "preserve_unmapped",
                                "type_conflict_open",
                                "alias_candidate",
                                "needs_human_review",
                            ],
                        },
                    },
                    "required_output_per_field": string_array,
                    "prohibitions": string_array,
                },
            },
            "unresolved_questions": string_array,
            "insufficiency_reasons": string_array,
        },
    }


def validate_global_proposal(
    proposal: Mapping[str, Any],
    field_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Validate catalog references without applying any proposed decision."""

    if proposal.get("status") not in {"proposal", "insufficient_evidence"}:
        raise ValueError("status da proposta global inválido.")
    if proposal.get("proposal_version") != GLOBAL_PROPOSAL_SCHEMA_VERSION:
        raise ValueError("proposal_version global inválida.")
    canonical_columns = proposal.get("canonical_columns")
    field_families = proposal.get("field_families")
    alias_hypotheses = proposal.get("alias_hypotheses")
    conflict_policy = proposal.get("type_conflict_policy")
    if not isinstance(canonical_columns, list):
        raise ValueError("canonical_columns deve ser lista.")
    if not isinstance(field_families, list):
        raise ValueError("field_families deve ser lista.")
    if not isinstance(alias_hypotheses, list):
        raise ValueError("alias_hypotheses deve ser lista.")
    if not isinstance(conflict_policy, Mapping):
        raise ValueError("type_conflict_policy deve ser objeto.")
    reasons = proposal.get("insufficiency_reasons")
    if not isinstance(reasons, list):
        raise ValueError("insufficiency_reasons deve ser lista.")
    if proposal["status"] == "proposal" and not canonical_columns:
        raise ValueError("status proposal exige ao menos uma coluna canônica.")
    if proposal["status"] == "insufficient_evidence":
        if canonical_columns or field_families or alias_hypotheses or not reasons:
            raise ValueError(
                "insufficient_evidence exige proposta vazia e justificativa."
            )

    known_ids = {str(row.get("field_id", "")) for row in field_rows}
    if "" in known_ids or len(known_ids) != len(field_rows):
        raise ValueError("Crosswalk contém field_id vazio ou duplicado.")
    cited_ids: list[str] = []
    canonical_names: list[str] = []
    for item in canonical_columns:
        canonical_names.append(str(item.get("canonical_name", "")))
        cited_ids.extend(item.get("representative_field_ids") or [])
    for item in field_families:
        cited_ids.extend(item.get("representative_field_ids") or [])
    for alias in alias_hypotheses:
        alias_ids = list(alias.get("field_ids") or [])
        if len(set(alias_ids)) < 2:
            raise ValueError("Hipótese de alias exige ao menos dois field_id distintos.")
        if alias.get("required_audit") != "record_by_record_exact_typed":
            raise ValueError("Alias exige auditoria exata e tipada recorde a recorde.")
        if alias.get("status") != "candidate_only":
            raise ValueError("Alias global deve permanecer candidate_only.")
        cited_ids.extend(alias_ids)
    cited_ids.extend(conflict_policy.get("representative_field_ids") or [])
    unknown = sorted(set(cited_ids).difference(known_ids))
    if unknown:
        raise ValueError(f"Proposta global cita field_id inexistentes: {unknown[:10]}")
    if any(not name for name in canonical_names):
        raise ValueError("canonical_name vazio.")
    if len(set(canonical_names)) != len(canonical_names):
        raise ValueError("canonical_name duplicado na proposta global.")


def estimate_gpt56_global_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    """Estimate long-context GPT-5.6 standard cost from reported token classes."""

    if min(
        input_tokens,
        output_tokens,
        cached_input_tokens,
        cache_write_tokens,
    ) < 0:
        raise ValueError("Contagens de tokens não podem ser negativas.")
    if cached_input_tokens + cache_write_tokens > input_tokens:
        raise ValueError("Tokens cached + cache_write excedem input_tokens.")
    ordinary_input_tokens = (
        input_tokens - cached_input_tokens - cache_write_tokens
    )
    total = (
        Decimal(ordinary_input_tokens) * GPT56_LONG_INPUT_PER_MILLION
        + Decimal(cached_input_tokens)
        * GPT56_LONG_CACHED_INPUT_PER_MILLION
        + Decimal(cache_write_tokens)
        * GPT56_LONG_CACHE_WRITE_PER_MILLION
        + Decimal(output_tokens) * GPT56_LONG_OUTPUT_PER_MILLION
    )
    return total / Decimal(1_000_000)


def submit_global_proposal(
    runtime_dir: Path = DEFAULT_GLOBAL_RUNTIME_DIR,
    drive_dir: Path = DEFAULT_GLOBAL_DRIVE_DIR,
    *,
    confirm_operation_id: str,
    execute_gpt: bool,
    client: Any | None = None,
) -> dict[str, Any]:
    """Archive the approved catalog and submit at most one global response."""

    if not execute_gpt:
        raise PermissionError("Chamada global bloqueada: use execute_gpt=True.")
    if confirm_operation_id != GLOBAL_PROPOSAL_OPERATION_ID:
        raise PermissionError("Confirmação literal da chamada global não confere.")
    runtime_dir = Path(runtime_dir)
    drive_dir = Path(drive_dir)
    for artifact_name in GLOBAL_ARCHIVE_ARTIFACTS:
        source = runtime_dir / artifact_name
        destination = drive_dir / artifact_name
        if not source.is_file():
            raise FileNotFoundError(f"Artefato global ausente: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(source) != sha256_file(destination):
                raise FileExistsError(
                    f"Destino divergente; nada foi sobrescrito: {destination}"
                )
        else:
            shutil.copy2(source, destination)

    catalog_path = runtime_dir / "catalogo_global_gpt56.txt"
    catalog_manifest = json.loads(
        (runtime_dir / "catalogo_global_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    counts = catalog_manifest.get("counts") or {}
    if catalog_manifest.get("catalog_profile") != "schema_core":
        raise ValueError("A chamada global exige catálogo schema_core.")
    expected_counts = {
        "field_paths": APPROVED_COUNTS["field_paths"],
        "records_rejected": APPROVED_COUNTS["records_rejected"],
        "type_conflicts": sum(APPROVED_TYPE_CONFLICTS.values()),
        "ccj_notas_field_paths": APPROVED_CCJ_PATHS,
    }
    observed_counts = {
        name: int(counts.get(name, -1)) for name in expected_counts
    }
    if observed_counts != expected_counts:
        raise ValueError(
            "Contagens do catálogo global divergem de G01: "
            f"{observed_counts} != {expected_counts}"
        )
    upload_receipt = json.loads(
        (runtime_dir / "upload_token_count.json").read_text(encoding="utf-8")
    )
    if upload_receipt.get("model") != REQUESTED_MODEL:
        raise ValueError("Recibo global exige gpt-5.6.")
    if upload_receipt.get("fits") is not True:
        raise ValueError("O recibo global não confirma que a entrada cabe.")
    if upload_receipt.get("catalog_sha256") != sha256_file(catalog_path):
        raise ValueError("SHA-256 do catálogo diverge do recibo de upload.")
    file_id = str(upload_receipt.get("file_id") or "")
    if not file_id:
        raise ValueError("Recibo global não contém file_id.")

    client = _openai_client(client)
    model_input = [
        {
            "role": "user",
            "content": [
                {"type": "input_file", "file_id": file_id},
                {"type": "input_text", "text": global_schema_prompt()},
            ],
        }
    ]
    response_text_config = {
        "format": {
            "type": "json_schema",
            "name": "falando_nela_global_schema_proposal",
            "strict": True,
            "schema": global_proposal_json_schema(),
        },
        "verbosity": "low",
    }
    exact_count = client.responses.input_tokens.count(
        model=REQUESTED_MODEL,
        input=model_input,
        reasoning={"effort": DEFAULT_REASONING_EFFORT},
        text=response_text_config,
    )
    generation_input_tokens = int(exact_count.input_tokens)
    if generation_input_tokens > GPT56_MAX_INPUT_TOKENS:
        raise ValueError(
            "A geração excede o limite conservador de entrada: "
            f"{generation_input_tokens} > {GPT56_MAX_INPUT_TOKENS}."
        )
    cost_low = estimate_gpt56_global_cost(
        input_tokens=generation_input_tokens,
        output_tokens=GPT56_GLOBAL_MAX_OUTPUT_TOKENS,
    )
    cost_high = estimate_gpt56_global_cost(
        input_tokens=generation_input_tokens,
        output_tokens=GPT56_GLOBAL_MAX_OUTPUT_TOKENS,
        cache_write_tokens=generation_input_tokens,
    )
    request_fingerprint = {
        "operation_id": GLOBAL_PROPOSAL_OPERATION_ID,
        "model": REQUESTED_MODEL,
        "file_id": file_id,
        "catalog_sha256": upload_receipt["catalog_sha256"],
        "prompt_sha256": sha256_text(global_schema_prompt()),
        "schema_version": GLOBAL_PROPOSAL_SCHEMA_VERSION,
        "schema_sha256": sha256_json(global_proposal_json_schema()),
        "input_tokens": generation_input_tokens,
        "reasoning_effort": DEFAULT_REASONING_EFFORT,
        "max_output_tokens": GPT56_GLOBAL_MAX_OUTPUT_TOKENS,
        "truncation": "disabled",
    }
    request_sha256 = sha256_json(request_fingerprint)
    submission_path = drive_dir / "submission_receipt.json"
    if submission_path.exists():
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        if submission.get("request_sha256") != request_sha256:
            raise FileExistsError(
                "Já existe submissão global divergente; "
                "nenhuma nova chamada foi feita."
            )
        submission["reused"] = True
        return submission

    response = client.responses.create(
        model=REQUESTED_MODEL,
        input=model_input,
        reasoning={"effort": DEFAULT_REASONING_EFFORT},
        text=response_text_config,
        max_output_tokens=GPT56_GLOBAL_MAX_OUTPUT_TOKENS,
        truncation="disabled",
        background=True,
        store=True,
        metadata={"operation_id": GLOBAL_PROPOSAL_OPERATION_ID},
    )
    submission = {
        **request_fingerprint,
        "request_sha256": request_sha256,
        "response_id": str(response.id),
        "initial_status": str(response.status),
        "estimated_cost_usd_low": str(cost_low),
        "estimated_cost_usd_high": str(cost_high),
    }
    _write_reusable_text(
        submission_path,
        json.dumps(
            submission,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return {**submission, "reused": False}


def retrieve_global_proposal(
    drive_dir: Path = DEFAULT_GLOBAL_DRIVE_DIR,
    *,
    client: Any | None = None,
    expected_field_paths: int = APPROVED_COUNTS["field_paths"],
) -> dict[str, Any]:
    """Poll once and preserve a completed proposal without applying it."""

    drive_dir = Path(drive_dir)
    submission_path = drive_dir / "submission_receipt.json"
    if not submission_path.is_file():
        raise FileNotFoundError("Submeta a chamada global primeiro.")
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    client = _openai_client(client)
    response = client.responses.retrieve(submission["response_id"])
    response_dict = model_dump(response)
    response_id = str(getattr(response, "id", submission["response_id"]))
    response_status = str(
        getattr(response, "status", response_dict.get("status", ""))
    )
    status_snapshot = {
        "operation_id": GLOBAL_PROPOSAL_OPERATION_ID,
        "response_id": response_id,
        "status": response_status,
        "error": response_dict.get("error"),
        "incomplete_details": response_dict.get("incomplete_details"),
    }
    (drive_dir / "status_latest.json").write_text(
        json.dumps(
            status_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result: dict[str, Any] = dict(status_snapshot)
    if response_status != "completed":
        return result

    raw_text = (
        json.dumps(
            response_dict,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    _write_reusable_text(drive_dir / "response_raw.json", raw_text)
    refusal = extract_refusal(response_dict)
    if refusal:
        raise RuntimeError(f"Resposta global recusada: {refusal}")
    output_text = extract_output_text(response, response_dict)
    proposal = json.loads(output_text)
    with (drive_dir / "catalogo_global_crosswalk.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        crosswalk_rows = list(csv.DictReader(handle))
    if len(crosswalk_rows) != expected_field_paths:
        raise ValueError(
            "Crosswalk global possui quantidade inesperada de caminhos: "
            f"{len(crosswalk_rows)} != {expected_field_paths}."
        )
    validate_global_proposal(proposal, crosswalk_rows)
    _write_reusable_text(
        drive_dir / "proposta_schema_global.json",
        json.dumps(
            proposal,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    usage = flatten_usage(response_dict.get("usage") or {})
    actual_cost = estimate_gpt56_global_cost(
        input_tokens=usage["input_tokens"],
        cached_input_tokens=usage["cached_input_tokens"],
        cache_write_tokens=usage["cache_write_tokens"],
        output_tokens=usage["output_tokens"],
    )
    execution = {
        "operation_id": GLOBAL_PROPOSAL_OPERATION_ID,
        "scientific_gate": "needs_human_review",
        "proposal_applied": False,
        "response_id": response_id,
        "requested_model": REQUESTED_MODEL,
        "resolved_model": response_dict.get("model", ""),
        "response_sha256": sha256_text(output_text),
        **usage,
        "actual_cost_usd": str(actual_cost),
        "pricing_as_of": "2026-07-24",
    }
    _write_reusable_text(
        drive_dir / "execution.json",
        json.dumps(
            execution,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    result.update(
        {
            "proposal_path": str(drive_dir / "proposta_schema_global.json"),
            "scientific_gate": "needs_human_review",
            "proposal_applied": False,
            "usage": usage,
            "actual_cost_usd": str(actual_cost),
        }
    )
    return result


def batch_mapping_output_json_schema() -> dict[str, Any]:
    """Closed response contract for one independent Batch request."""

    mapping = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "field_id",
            "decision",
            "canonical_candidate_or_null",
            "mapping_operation",
            "review_reason",
        ],
        "properties": {
            "field_id": {"type": "string", "pattern": "^F[0-9]{5}$"},
            "decision": {
                "type": "string",
                "enum": [
                    "map",
                    "preserve_unmapped",
                    "type_conflict_open",
                    "alias_candidate",
                    "needs_human_review",
                ],
            },
            "canonical_candidate_or_null": {
                "anyOf": [
                    {"type": "string", "enum": list(APPROVED_LOGICAL_FIELDS)},
                    {"type": "null"},
                ]
            },
            "mapping_operation": {
                "type": "string",
                "enum": [
                    "direct_copy",
                    "rename",
                    "lossless_cast",
                    "closed_map",
                    "preserve_unmapped",
                    "needs_human_rule",
                ],
            },
            "review_reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": 240,
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "frozen_vocabulary_sha256",
            "mappings",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [BATCH_MAPPING_SCHEMA_VERSION],
            },
            "frozen_vocabulary_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "mappings": {
                "type": "array",
                "minItems": 1,
                "maxItems": BATCH_MAPPING_CHUNK_SIZE,
                "items": mapping,
            },
        },
    }


def batch_mapping_prompt() -> str:
    return (
        "Você classifica caminhos estruturais já inventariados usando somente "
        "o vocabulário humano congelado fornecido. Para cada field_id de input, "
        "devolva exatamente uma disposição. Não omita, não duplique e não "
        "invente field_id. Use o caminho completo, source, dataset, record_type, "
        "tipos, estados e conflito; não interprete conteúdo parlamentar. "
        "Mapeie apenas quando a semântica e o escopo forem sustentados pelo "
        "metadado estrutural. Preserve sem mapear contêineres, campos opacos e "
        "evidência insuficiente. Conflito de tipo permanece aberto. Alias só "
        "pode ser candidato, salvo as duplicações técnicas já aprovadas no "
        "vocabulário; mesmo nelas, ambas as linhagens são preservadas. Não "
        "descarte, funda, priorize, preencha, corrija nem aplique o schema. "
        "canonical_candidate_or_null deve usar somente a lista autorizada. "
        "review_reason deve ser curto, concreto e baseado na estrutura."
    )


def batch_frozen_vocabulary(
    global_proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the compact, human-approved vocabulary shared by every request."""

    family_fields = [
        field_name
        for family in BATCH_FIELD_FAMILIES
        for field_name in family["fields"]
    ]
    if len(family_fields) != len(set(family_fields)):
        raise ValueError("Vocabulário Batch contém campo repetido entre famílias.")
    if set(family_fields) != set(APPROVED_LOGICAL_FIELDS):
        missing = sorted(set(APPROVED_LOGICAL_FIELDS).difference(family_fields))
        extra = sorted(set(family_fields).difference(APPROVED_LOGICAL_FIELDS))
        raise ValueError(
            f"Famílias Batch não reconciliam campos aprovados: "
            f"missing={missing}, extra={extra}"
        )
    anchors = []
    for item in global_proposal.get("canonical_columns") or []:
        anchors.append([item["canonical_name"], item["definition"]])
    compact_duplications = []
    for item in APPROVED_TECHNICAL_DUPLICATIONS:
        compact_duplications.append(
            {
                "id": item["rule_id"],
                "decision": item["decision"],
                "field_ids": item["field_ids"],
                "scope": item["scope"],
                "paths": item["source_paths"],
                "target": item["canonical_target"],
            }
        )
    return {
        "vocabulary_version": BATCH_MAPPING_VOCABULARY_VERSION,
        "logical_schema_version": SCHEMA_VERSION,
        "authority": (
            "revisão humana aprovada em 2026-07-25; os campos approved_fields "
            "substituem candidatos agregados da proposta global"
        ),
        "approved_fields": list(APPROVED_LOGICAL_FIELDS),
        "families": [
            {
                "family": family["family"],
                "fields": list(family["fields"]),
                "rule": family["rule"],
                "examples": list(family["examples"]),
            }
            for family in BATCH_FIELD_FAMILIES
        ],
        "historical_semantic_anchors_name_and_definition": anchors,
        "distinct_entity_namespaces": [
            entity_type for _, entity_type in APPROVED_ENTITY_COLLECTIONS
        ],
        "cardinalities_source_relation_target_value": [
            [
                item["source_entity"],
                item["relationship"],
                item["target_entity"],
                item["cardinality"],
            ]
            for item in APPROVED_CARDINALITIES
        ],
        "technical_duplications_and_non_alias": compact_duplications,
        "ccj_notas_rules": [
            "Tratar os 20.523 caminhos e 540 conflitos em trilha própria.",
            "Separar record_type antes de comparar caminhos.",
            "Preservar hierarquia, ordem e multiplicidade de arrays.",
            "[] descreve coleção e não identifica elementos.",
            "Agenda e detalhe são escopos distintos e não aliases.",
            "Não achatar variantes array, object e scalar.",
        ],
        "presence_states": ["absent", "null", "empty", "filled", "rejected"],
        "input_field_key_legend": {
            "id": "field_id",
            "scope.s": "source",
            "scope.d": "dataset",
            "scope.r": "record_type",
            "path_blocks[].p": "shared_original_field_path_prefix",
            "path_blocks[].f[].q": (
                "field_path_suffix; original_field_path = p + q"
            ),
            "t": "observed_type_codes",
            "c": "observed_cardinality_or_null",
            "m": "presence_state_mask",
            "x": "type_conflict",
        },
        "model_output_fields": [
            "field_id",
            "decision",
            "canonical_candidate_or_null",
            "mapping_operation",
            "review_reason",
        ],
        "deterministic_expansion_fields": [
            "source",
            "dataset",
            "record_type",
            "reconstructed_original_field_path",
            "observed_type_codes",
            "observed_cardinality",
            "presence_state_mask",
        ],
        "prohibitions": list(
            (global_proposal.get("batch_mapping_contract") or {}).get(
                "prohibitions"
            )
            or []
        ),
    }


def _batch_presence_state_mask(row: Mapping[str, Any]) -> str:
    states = []
    for column, state in (
        ("field_absent", "absent"),
        ("present_null", "null"),
        ("present_empty", "empty"),
        ("present_filled", "filled"),
    ):
        if int(str(row.get(column) or "0")) > 0:
            states.append(state)
    if not states:
        raise ValueError(f"field_id sem estado de presença: {row.get('field_id')}")
    return "|".join(states)


def _batch_field_input(row: Mapping[str, Any]) -> dict[str, Any]:
    cardinality = str(row.get("cardinality") or "")
    return {
        "id": str(row["field_id"]),
        "s": str(row["source"]),
        "d": str(row["dataset"]),
        "r": str(row["record_type"]),
        "p": str(row["field_path"]),
        "t": [
            item
            for item in str(row.get("technical_types") or "").split("|")
            if item
        ],
        "c": cardinality or None,
        "m": _batch_presence_state_mask(row),
        "x": truthy(str(row.get("type_conflict") or "")),
    }


def _expanded_batch_field_input(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "field_id": str(row["id"]),
        "source": str(row["s"]),
        "dataset": str(row["d"]),
        "record_type": str(row["r"]),
        "original_field_path": str(row["p"]),
        "observed_type_codes": list(row["t"]),
        "observed_cardinality": row["c"],
        "presence_state_mask": str(row["m"]),
        "type_conflict": bool(row["x"]),
    }


def _compact_batch_field_input(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["field_id"]),
        "s": str(row["source"]),
        "d": str(row["dataset"]),
        "r": str(row["record_type"]),
        "p": str(row["original_field_path"]),
        "t": list(row["observed_type_codes"]),
        "c": row["observed_cardinality"],
        "m": str(row["presence_state_mask"]),
        "x": bool(row["type_conflict"]),
    }


def _compact_batch_field_blocks(
    fields: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    scopes = {
        (field_row["s"], field_row["d"], field_row["r"])
        for field_row in fields
    }
    if len(scopes) != 1:
        raise ValueError("Cada request Batch deve conter um único escopo.")
    source, dataset, record_type = next(iter(scopes))
    by_parent: defaultdict[str, list[tuple[Mapping[str, Any], str]]] = defaultdict(
        list
    )
    for field_row in fields:
        parent, suffix = _global_catalog_parent_suffix(str(field_row["p"]))
        by_parent[parent].append((field_row, suffix))
    blocks = []
    direct_fields = []
    for parent, members in sorted(by_parent.items()):
        full_size = sum(len(str(field_row["p"])) for field_row, _ in members)
        factored_size = len(parent) + sum(len(suffix) for _, suffix in members)
        if parent and len(members) >= 2 and full_size - factored_size >= 8:
            block_prefix = parent
            block_members = members
        else:
            for field_row, _ in members:
                direct_fields.append((field_row, str(field_row["p"])))
            continue
        blocks.append(
            {
                "p": block_prefix,
                "f": [
                    {
                        "id": field_row["id"],
                        "q": suffix,
                        "t": field_row["t"],
                        "c": field_row["c"],
                        "m": field_row["m"],
                        "x": field_row["x"],
                    }
                    for field_row, suffix in sorted(
                        block_members,
                        key=lambda item: str(item[0]["id"]),
                    )
                ],
            }
        )
    if direct_fields:
        blocks.insert(
            0,
            {
                "p": "",
                "f": [
                    {
                        "id": field_row["id"],
                        "q": path,
                        "t": field_row["t"],
                        "c": field_row["c"],
                        "m": field_row["m"],
                        "x": field_row["x"],
                    }
                    for field_row, path in sorted(
                        direct_fields,
                        key=lambda item: str(item[0]["id"]),
                    )
                ],
            },
        )
    return {
        "scope": {"s": source, "d": dataset, "r": record_type},
        "path_blocks": blocks,
    }


def _expanded_batch_request_fields(
    request_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scope = request_payload["scope"]
    rows = []
    for block in request_payload["path_blocks"]:
        prefix = str(block["p"])
        for field_row in block["f"]:
            rows.append(
                {
                    "field_id": str(field_row["id"]),
                    "source": str(scope["s"]),
                    "dataset": str(scope["d"]),
                    "record_type": str(scope["r"]),
                    "original_field_path": prefix + str(field_row["q"]),
                    "observed_type_codes": list(field_row["t"]),
                    "observed_cardinality": field_row["c"],
                    "presence_state_mask": str(field_row["m"]),
                    "type_conflict": bool(field_row["x"]),
                }
            )
    return rows


def _batch_request_body(
    *,
    vocabulary: Mapping[str, Any],
    vocabulary_sha256: str,
    fields: Sequence[Mapping[str, Any]],
    model: str = BATCH_REQUESTED_MODEL,
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    request_payload = {
        "frozen_vocabulary": vocabulary,
        "frozen_vocabulary_sha256": vocabulary_sha256,
        **_compact_batch_field_blocks(fields),
    }
    return {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": [
                    {"type": "input_text", "text": batch_mapping_prompt()}
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json_compact(request_payload),
                    }
                ],
            },
        ],
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "falando_nela_field_mapping_batch",
                "strict": True,
                "schema": batch_mapping_output_json_schema(),
            },
        },
        "max_output_tokens": BATCH_MAPPING_MAX_OUTPUT_TOKENS,
        "store": False,
    }


def prepare_batch_mapping(
    crosswalk_path: Path,
    global_proposal_path: Path,
    operation_root: Path = DEFAULT_BATCH_RUNTIME_DIR,
    *,
    operation_id: str = BATCH_MAPPING_OPERATION_ID,
    chunk_size: int = BATCH_MAPPING_CHUNK_SIZE,
    expected_field_paths: int = APPROVED_COUNTS["field_paths"],
) -> dict[str, Any]:
    """Prepare a deterministic Batch JSONL without calling or applying GPT."""

    if operation_id != BATCH_MAPPING_OPERATION_ID:
        raise ValueError(
            f"A operação Batch aprovada exige {BATCH_MAPPING_OPERATION_ID}."
        )
    if not (1 <= chunk_size <= BATCH_MAPPING_CHUNK_SIZE):
        raise ValueError(
            f"chunk_size deve estar entre 1 e {BATCH_MAPPING_CHUNK_SIZE}."
        )
    crosswalk_path = Path(crosswalk_path).resolve()
    global_proposal_path = Path(global_proposal_path).resolve()
    operation_root = Path(operation_root).resolve()
    field_rows = read_csv(crosswalk_path)
    proposal = json.loads(global_proposal_path.read_text(encoding="utf-8"))
    validate_global_proposal(proposal, field_rows)
    if len(field_rows) != expected_field_paths:
        raise ValueError(
            "Batch integral exige exatamente "
            f"{expected_field_paths} field_id."
        )
    field_ids = [str(row.get("field_id") or "") for row in field_rows]
    if len(field_ids) != len(set(field_ids)):
        raise ValueError("Crosswalk Batch contém field_id duplicado.")

    vocabulary = batch_frozen_vocabulary(proposal)
    vocabulary_sha256 = sha256_json(vocabulary)
    request_schema = batch_mapping_output_json_schema()
    request_schema_sha256 = sha256_json(request_schema)
    prompt_sha256 = sha256_text(batch_mapping_prompt())
    grouped: defaultdict[
        tuple[str, str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for row in field_rows:
        grouped[
            (
                str(row["group_id"]),
                str(row["source"]),
                str(row["dataset"]),
                str(row["record_type"]),
            )
        ].append(row)

    requests: list[dict[str, Any]] = []
    request_index: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        group_id, source, dataset, record_type = group_key
        rows = sorted(
            grouped[group_key],
            key=lambda row: str(row["field_id"]),
        )
        for chunk_number, start in enumerate(range(0, len(rows), chunk_size), 1):
            chunk = rows[start : start + chunk_size]
            fields = [_batch_field_input(row) for row in chunk]
            custom_id = (
                f"g02-{group_id.lower()}-{chunk_number:03d}"
            )
            body = _batch_request_body(
                vocabulary=vocabulary,
                vocabulary_sha256=vocabulary_sha256,
                fields=fields,
            )
            requests.append(
                {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": body,
                }
            )
            request_index.append(
                {
                    "custom_id": custom_id,
                    "group_id": group_id,
                    "source": source,
                    "dataset": dataset,
                    "record_type": record_type,
                    "field_count": len(fields),
                    "first_field_id": fields[0]["id"],
                    "last_field_id": fields[-1]["id"],
                    "field_ids_sha256": sha256_json(
                        [field["id"] for field in fields]
                    ),
                }
            )

    batch_input_text = "".join(
        json_compact(request) + "\n" for request in requests
    )
    request_index_text = "".join(
        json_compact(row) + "\n" for row in request_index
    )
    vocabulary_text = (
        json.dumps(
            vocabulary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    schema_text = (
        json.dumps(
            request_schema,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    operation_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "batch_input": operation_root / "batch_input.jsonl",
        "request_index": operation_root / "batch_request_index.jsonl",
        "vocabulary": operation_root / "frozen_vocabulary.json",
        "response_schema": operation_root / "batch_response.schema.json",
        "manifest": operation_root / "batch_manifest.json",
    }
    reused = all(path.exists() for path in paths.values())
    _write_reusable_text(paths["batch_input"], batch_input_text)
    _write_reusable_text(paths["request_index"], request_index_text)
    _write_reusable_text(paths["vocabulary"], vocabulary_text)
    _write_reusable_text(paths["response_schema"], schema_text)
    manifest = {
        "operation_id": operation_id,
        "status": "prepared",
        "scientific_gate": "batch_not_submitted",
        "requested_model": BATCH_REQUESTED_MODEL,
        "reasoning_effort": "low",
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "prompt_version": BATCH_MAPPING_PROMPT_VERSION,
        "prompt_sha256": prompt_sha256,
        "response_schema_version": BATCH_MAPPING_SCHEMA_VERSION,
        "response_schema_sha256": request_schema_sha256,
        "vocabulary_version": BATCH_MAPPING_VOCABULARY_VERSION,
        "vocabulary_sha256": vocabulary_sha256,
        "global_proposal_sha256": sha256_file(global_proposal_path),
        "crosswalk_sha256": sha256_file(crosswalk_path),
        "batch_input_sha256": sha256_text(batch_input_text),
        "request_index_sha256": sha256_text(request_index_text),
        "counts": {
            "field_ids": len(field_rows),
            "requests": len(requests),
            "record_groups": len(grouped),
            "type_conflicts": sum(
                truthy(str(row.get("type_conflict") or ""))
                for row in field_rows
            ),
            "ccj_notas_field_ids": sum(
                str(row.get("source")) == "senado"
                and str(row.get("dataset")) == "ccj_notas"
                for row in field_rows
            ),
        },
        "chunk_size": chunk_size,
        "batch_input_size_bytes": len(batch_input_text.encode("utf-8")),
        "proposal_applied": False,
        "raw_mutated": False,
        "normalization_materialized": False,
    }
    manifest_text = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    _write_reusable_text(paths["manifest"], manifest_text)
    return {
        "paths": paths,
        "manifest": manifest,
        "requests": requests,
        "request_index": request_index,
        "reused": reused,
    }


def estimate_gpt56_batch_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> Decimal:
    if min(input_tokens, output_tokens, cached_input_tokens) < 0:
        raise ValueError("Contagens de tokens não podem ser negativas.")
    if cached_input_tokens > input_tokens:
        raise ValueError("cached_input_tokens excede input_tokens.")
    uncached = input_tokens - cached_input_tokens
    total = (
        Decimal(uncached) * GPT56_BATCH_INPUT_PER_MILLION
        + Decimal(cached_input_tokens)
        * GPT56_BATCH_CACHED_INPUT_PER_MILLION
        + Decimal(output_tokens) * GPT56_BATCH_OUTPUT_PER_MILLION
    )
    return total / Decimal(1_000_000)


def count_batch_mapping_input_tokens(
    operation_root: Path = DEFAULT_BATCH_RUNTIME_DIR,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Count every prepared request with the official input-token endpoint."""

    operation_root = Path(operation_root).resolve()
    manifest_path = operation_root / "batch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    requests = read_jsonl(operation_root / "batch_input.jsonl")
    if manifest.get("batch_input_sha256") != sha256_file(
        operation_root / "batch_input.jsonl"
    ):
        raise ValueError("batch_input.jsonl diverge do manifest preparado.")
    client = _openai_client(client)
    rows = []
    total = 0
    for request in requests:
        body = request["body"]
        count = client.responses.input_tokens.count(
            model=body["model"],
            input=body["input"],
            reasoning=body["reasoning"],
            text=body["text"],
        )
        input_tokens = int(count.input_tokens)
        total += input_tokens
        rows.append(
            {
                "custom_id": request["custom_id"],
                "input_tokens": input_tokens,
            }
        )
    count_text = "".join(json_compact(row) + "\n" for row in rows)
    count_path = operation_root / "batch_input_token_counts.jsonl"
    _write_reusable_text(count_path, count_text)
    output_ceiling = len(requests) * BATCH_MAPPING_MAX_OUTPUT_TOKENS
    operation_id = str(manifest["operation_id"])
    result = {
        "operation_id": operation_id,
        "requested_model": BATCH_REQUESTED_MODEL,
        "requests": len(requests),
        "input_tokens": total,
        "conservative_queue_limit": BATCH_CONSERVATIVE_QUEUED_INPUT_TOKENS,
        "fits_conservative_queue_limit": (
            total <= BATCH_CONSERVATIVE_QUEUED_INPUT_TOKENS
        ),
        "max_output_tokens_per_request": BATCH_MAPPING_MAX_OUTPUT_TOKENS,
        "max_output_tokens_all_requests": output_ceiling,
        "estimated_cost_usd_input_uncached": str(
            estimate_gpt56_batch_cost(
                input_tokens=total,
                output_tokens=0,
            )
        ),
        "estimated_cost_usd_ceiling_uncached": str(
            estimate_gpt56_batch_cost(
                input_tokens=total,
                output_tokens=output_ceiling,
            )
        ),
        "pricing": {
            "as_of": "2026-07-25",
            "pricing_ref": "https://openai.com/api/pricing/",
            "input_per_million": str(GPT56_BATCH_INPUT_PER_MILLION),
            "cached_input_per_million": str(
                GPT56_BATCH_CACHED_INPUT_PER_MILLION
            ),
            "output_per_million": str(GPT56_BATCH_OUTPUT_PER_MILLION),
        },
        "token_counts_sha256": sha256_text(count_text),
    }
    _write_reusable_text(
        operation_root / "batch_cost_estimate.json",
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return result


def submit_batch_mapping(
    operation_root: Path = DEFAULT_BATCH_RUNTIME_DIR,
    *,
    confirm_operation_id: str,
    execute_batch: bool,
    client: Any | None = None,
) -> dict[str, Any]:
    """Upload and create at most one idempotent Batch mapping operation."""

    if not execute_batch:
        raise PermissionError("Batch bloqueado: use execute_batch=True.")
    operation_root = Path(operation_root).resolve()
    estimate_path = operation_root / "batch_cost_estimate.json"
    if not estimate_path.is_file():
        raise FileNotFoundError("Conte tokens e preserve a estimativa antes do Batch.")
    estimate = json.loads(estimate_path.read_text(encoding="utf-8"))
    if estimate.get("fits_conservative_queue_limit") is not True:
        raise ValueError(
            "Entrada excede o limite conservador de tokens enfileirados; "
            "não submeter sem revisar o limite do projeto."
        )
    input_path = operation_root / "batch_input.jsonl"
    manifest = json.loads(
        (operation_root / "batch_manifest.json").read_text(encoding="utf-8")
    )
    operation_id = str(manifest["operation_id"])
    if confirm_operation_id != operation_id:
        raise PermissionError("Confirmação literal da operação Batch não confere.")
    request_fingerprint = {
        "operation_id": operation_id,
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "requested_model": BATCH_REQUESTED_MODEL,
        "batch_input_sha256": sha256_file(input_path),
        "input_tokens": estimate["input_tokens"],
        "vocabulary_sha256": manifest["vocabulary_sha256"],
        "response_schema_sha256": manifest["response_schema_sha256"],
    }
    request_sha256 = sha256_json(request_fingerprint)
    receipt_path = operation_root / "batch_submission_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("request_sha256") != request_sha256:
            raise FileExistsError(
                "Já existe submissão Batch divergente; nenhuma nova foi criada."
            )
        return {**receipt, "reused": True}

    client = _openai_client(client)
    for batch in client.batches.list(limit=100):
        metadata = model_dump(batch).get("metadata") or {}
        if (
            metadata.get("operation_id") == operation_id
            and metadata.get("request_sha256") == request_sha256
        ):
            receipt = {
                **request_fingerprint,
                "request_sha256": request_sha256,
                "input_file_id": str(batch.input_file_id),
                "batch_id": str(batch.id),
                "initial_status": str(batch.status),
                "recovered_from_batch_list": True,
                "proposal_applied": False,
            }
            _write_reusable_text(
                receipt_path,
                json.dumps(
                    receipt,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
            )
            return {**receipt, "reused": True}

    with input_path.open("rb") as handle:
        input_file = client.files.create(file=handle, purpose="batch")
    batch = client.batches.create(
        input_file_id=input_file.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={
            "operation_id": operation_id,
            "request_sha256": request_sha256,
        },
    )
    receipt = {
        **request_fingerprint,
        "request_sha256": request_sha256,
        "input_file_id": str(input_file.id),
        "batch_id": str(batch.id),
        "initial_status": str(batch.status),
        "recovered_from_batch_list": False,
        "proposal_applied": False,
    }
    _write_reusable_text(
        receipt_path,
        json.dumps(
            receipt,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return {**receipt, "reused": False}


def _validate_batch_mapping_item(
    item: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    if item.get("field_id") != expected["field_id"]:
        raise ValueError("Resposta Batch cita field_id divergente.")
    decision = item.get("decision")
    candidate = item.get("canonical_candidate_or_null")
    operation = item.get("mapping_operation")
    if candidate is not None and candidate not in APPROVED_LOGICAL_FIELDS:
        raise ValueError("Resposta Batch inventou campo canônico.")
    if decision == "map":
        if candidate is None or operation == "preserve_unmapped":
            raise ValueError("Mapeamento exige candidato e operação compatível.")
    elif decision == "preserve_unmapped":
        if candidate is not None or operation != "preserve_unmapped":
            raise ValueError(
                "preserve_unmapped exige candidato nulo e operação homônima."
            )
    elif decision in {
        "type_conflict_open",
        "alias_candidate",
        "needs_human_review",
    }:
        if operation != "needs_human_rule":
            raise ValueError(f"{decision} exige needs_human_rule.")
    else:
        raise ValueError("Decisão Batch fora do vocabulário fechado.")
    reason = str(item.get("review_reason") or "")
    if not (1 <= len(reason) <= 240):
        raise ValueError("review_reason ausente ou longo demais.")


def _expanded_batch_mapping_row(
    item: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    custom_id: str,
    batch_id: str,
    resolved_model: str,
) -> dict[str, Any]:
    return {
        "field_id": expected["field_id"],
        "source": expected["source"],
        "dataset": expected["dataset"],
        "record_type": expected["record_type"],
        "reconstructed_original_field_path": expected["original_field_path"],
        "observed_type_codes": "|".join(expected["observed_type_codes"]),
        "observed_cardinality": expected["observed_cardinality"] or "",
        "presence_state_mask": expected["presence_state_mask"],
        "decision": item["decision"],
        "canonical_candidate_or_null": (
            item["canonical_candidate_or_null"]
            if item["canonical_candidate_or_null"] is not None
            else ""
        ),
        "mapping_operation": item["mapping_operation"],
        "review_reason": item["review_reason"],
        "custom_id": custom_id,
        "batch_id": batch_id,
        "requested_model": BATCH_REQUESTED_MODEL,
        "resolved_model": resolved_model,
        "human_decision": "nao_avaliado",
        "proposal_applied": False,
    }


def retrieve_batch_mapping(
    operation_root: Path = DEFAULT_BATCH_RUNTIME_DIR,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Poll once; on completion, validate and expand proposals without applying."""

    operation_root = Path(operation_root).resolve()
    receipt = json.loads(
        (operation_root / "batch_submission_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    requests = read_jsonl(operation_root / "batch_input.jsonl")
    request_by_id = {request["custom_id"]: request for request in requests}
    client = _openai_client(client)
    batch = client.batches.retrieve(receipt["batch_id"])
    batch_dict = model_dump(batch)
    status = str(batch_dict.get("status") or getattr(batch, "status", ""))
    operation_id = str(receipt["operation_id"])
    snapshot = {
        "operation_id": operation_id,
        "batch_id": receipt["batch_id"],
        "status": status,
        "request_counts": batch_dict.get("request_counts"),
        "errors": batch_dict.get("errors"),
        "output_file_id": batch_dict.get("output_file_id"),
        "error_file_id": batch_dict.get("error_file_id"),
        "proposal_applied": False,
    }
    (operation_root / "batch_status_latest.json").write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if status != "completed":
        return snapshot

    output_file_id = str(batch_dict.get("output_file_id") or "")
    if not output_file_id:
        raise RuntimeError("Batch concluído sem output_file_id.")
    output_text = client.files.content(output_file_id).text
    _write_reusable_text(operation_root / "batch_output_raw.jsonl", output_text)
    error_file_id = str(batch_dict.get("error_file_id") or "")
    error_text = ""
    if error_file_id:
        error_text = client.files.content(error_file_id).text
        _write_reusable_text(operation_root / "batch_errors_raw.jsonl", error_text)

    manifest = json.loads(
        (operation_root / "batch_manifest.json").read_text(encoding="utf-8")
    )
    vocabulary_sha256 = manifest["vocabulary_sha256"]
    expanded_rows = []
    execution_rows = []
    seen_custom_ids: set[str] = set()
    seen_field_ids: set[str] = set()
    incomplete_custom_ids: set[str] = set()
    invalid_mapping_rows = []
    usage_total = Counter()
    for line_number, line in enumerate(output_text.splitlines(), 1):
        if not line.strip():
            continue
        envelope = json.loads(line)
        custom_id = str(envelope.get("custom_id") or "")
        if custom_id not in request_by_id:
            raise ValueError(f"Output Batch cita custom_id desconhecido: {custom_id}")
        if custom_id in seen_custom_ids:
            raise ValueError(f"Output Batch duplica custom_id: {custom_id}")
        seen_custom_ids.add(custom_id)
        response = envelope.get("response") or {}
        if int(response.get("status_code") or 0) != 200:
            raise RuntimeError(
                f"Resposta Batch sem HTTP 200 em {custom_id}: "
                f"{response.get('status_code')}"
            )
        body = response.get("body") or {}
        response_text = extract_output_text(
            type("BatchResponse", (), {"output_text": ""})(),
            body,
        )
        payload = json.loads(response_text)
        if payload.get("schema_version") != BATCH_MAPPING_SCHEMA_VERSION:
            raise ValueError("Resposta Batch usa schema_version divergente.")
        if payload.get("frozen_vocabulary_sha256") != vocabulary_sha256:
            raise ValueError("Resposta Batch não confirma o vocabulário congelado.")
        request_payload = json.loads(
            request_by_id[custom_id]["body"]["input"][1]["content"][0]["text"]
        )
        expected_fields = _expanded_batch_request_fields(request_payload)
        expected_by_id = {field["field_id"]: field for field in expected_fields}
        items = payload.get("mappings")
        if not isinstance(items, list):
            raise ValueError("Resposta Batch sem mappings.")
        returned_ids = [str(item.get("field_id") or "") for item in items]
        if len(returned_ids) != len(set(returned_ids)):
            raise ValueError(
                f"Resposta Batch duplica field_id em {custom_id}."
            )
        unknown_ids = sorted(set(returned_ids).difference(expected_by_id))
        if unknown_ids:
            raise ValueError(
                f"Resposta Batch inventa field_id em {custom_id}: "
                f"{unknown_ids[:10]}"
            )
        omitted_request_ids = sorted(
            set(expected_by_id).difference(returned_ids)
        )
        resolved_model = str(body.get("model") or "")
        usage = flatten_usage(body.get("usage") or {})
        usage_total.update(usage)
        invalid_request_ids = []
        for item in items:
            field_id = str(item["field_id"])
            if field_id in seen_field_ids:
                raise ValueError(f"field_id duplicado entre requests: {field_id}")
            expected = expected_by_id[field_id]
            try:
                _validate_batch_mapping_item(item, expected)
            except ValueError as exc:
                invalid_request_ids.append(field_id)
                invalid_mapping_rows.append(
                    {
                        "custom_id": custom_id,
                        "field_id": field_id,
                        "validation_error": str(exc),
                        "mapping": dict(item),
                    }
                )
                continue
            seen_field_ids.add(field_id)
            expanded_rows.append(
                _expanded_batch_mapping_row(
                    item,
                    expected,
                    custom_id=custom_id,
                    batch_id=receipt["batch_id"],
                    resolved_model=resolved_model,
                )
            )
        unresolved_request_ids = sorted(
            set(omitted_request_ids).union(invalid_request_ids)
        )
        if unresolved_request_ids:
            incomplete_custom_ids.add(custom_id)
        execution_rows.append(
            {
                "custom_id": custom_id,
                "status": (
                    "incomplete_coverage"
                    if unresolved_request_ids
                    else "valid"
                ),
                "field_ids_expected": len(expected_by_id),
                "field_ids_returned": len(returned_ids),
                "field_ids_valid": (
                    len(returned_ids) - len(invalid_request_ids)
                ),
                "field_ids_invalid": len(invalid_request_ids),
                "field_ids_missing": len(unresolved_request_ids),
                "missing_field_ids_sha256": (
                    sha256_json(unresolved_request_ids)
                    if unresolved_request_ids
                    else ""
                ),
                "resolved_model": resolved_model,
                **usage,
                "response_sha256": sha256_text(response_text),
                "line_number": line_number,
            }
        )

    error_rows = [
        json.loads(line)
        for line in error_text.splitlines()
        if line.strip()
    ]
    if error_rows:
        raise RuntimeError(
            f"Batch concluiu com {len(error_rows)} erros; "
            "artefato bruto preservado e nenhuma proposta aplicada."
        )
    expected_all_by_id = {
        field["field_id"]: field
        for request in requests
        for field in _expanded_batch_request_fields(
            json.loads(request["body"]["input"][1]["content"][0]["text"])
        )
    }
    expected_all_ids = set(expected_all_by_id)
    if seen_custom_ids != set(request_by_id):
        missing = sorted(set(request_by_id).difference(seen_custom_ids))
        raise ValueError(f"Batch sem output para requests: {missing[:10]}")
    missing_field_ids = sorted(expected_all_ids.difference(seen_field_ids))
    expanded_rows.sort(key=lambda row: row["field_id"])
    execution_rows.sort(key=lambda row: row["custom_id"])
    mapping_fields = [
        "field_id",
        "source",
        "dataset",
        "record_type",
        "reconstructed_original_field_path",
        "observed_type_codes",
        "observed_cardinality",
        "presence_state_mask",
        "decision",
        "canonical_candidate_or_null",
        "mapping_operation",
        "review_reason",
        "custom_id",
        "batch_id",
        "requested_model",
        "resolved_model",
        "human_decision",
        "proposal_applied",
    ]
    write_csv(
        operation_root / "mapeamentos_batch_propostos.csv",
        expanded_rows,
        mapping_fields,
    )
    write_jsonl(
        operation_root / "batch_execution.jsonl",
        execution_rows,
    )
    if invalid_mapping_rows:
        write_jsonl(
            operation_root / "batch_invalid_mappings.jsonl",
            invalid_mapping_rows,
        )
    if missing_field_ids:
        write_jsonl(
            operation_root / "batch_missing_fields.jsonl",
            [expected_all_by_id[field_id] for field_id in missing_field_ids],
        )
    actual_cost = estimate_gpt56_batch_cost(
        input_tokens=usage_total["input_tokens"],
        cached_input_tokens=usage_total["cached_input_tokens"],
        output_tokens=usage_total["output_tokens"],
    )
    completed_coverage = not missing_field_ids
    reconciliation = {
        **snapshot,
        "status": (
            "completed_validated"
            if completed_coverage
            else "completed_incomplete_coverage"
        ),
        "scientific_gate": (
            "needs_human_review"
            if completed_coverage
            else "repair_required"
        ),
        "field_ids_expected": len(expected_all_ids),
        "field_ids_reconciled": len(seen_field_ids),
        "missing_field_ids": len(missing_field_ids),
        "missing_field_ids_sha256": (
            sha256_json(missing_field_ids) if missing_field_ids else None
        ),
        "duplicate_field_ids": 0,
        "requests_expected": len(requests),
        "requests_reconciled": len(seen_custom_ids),
        "requests_incomplete": len(incomplete_custom_ids),
        "invalid_mappings": len(invalid_mapping_rows),
        "usage": dict(usage_total),
        "actual_cost_usd": str(actual_cost),
        "proposal_applied": False,
        "raw_mutated": False,
        "normalization_materialized": False,
    }
    _write_reusable_text(
        operation_root / "batch_reconciliation.json",
        json.dumps(
            reconciliation,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return reconciliation


def prepare_batch_repair(
    source_operation_root: Path,
    repair_operation_root: Path,
    *,
    operation_id: str,
    chunk_size: int = BATCH_REPAIR_CHUNK_SIZE,
) -> dict[str, Any]:
    """Prepare a smaller Batch containing only unreconciled field IDs."""

    source_operation_root = Path(source_operation_root).resolve()
    repair_operation_root = Path(repair_operation_root).resolve()
    if source_operation_root == repair_operation_root:
        raise ValueError("A correção Batch exige diretório de operação próprio.")
    if not operation_id.startswith(
        f"{BATCH_MAPPING_OPERATION_ID}-repair-"
    ):
        raise ValueError("operation_id de correção Batch fora do prefixo aprovado.")
    if not (1 <= chunk_size <= BATCH_REPAIR_CHUNK_SIZE):
        raise ValueError(
            f"chunk_size de correção deve estar entre 1 e "
            f"{BATCH_REPAIR_CHUNK_SIZE}."
        )
    reconciliation = json.loads(
        (source_operation_root / "batch_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )
    if reconciliation.get("status") != "completed_incomplete_coverage":
        raise ValueError("A operação de origem não registra cobertura incompleta.")
    missing_path = source_operation_root / "batch_missing_fields.jsonl"
    missing_fields = read_jsonl(missing_path)
    if len(missing_fields) != int(reconciliation["missing_field_ids"]):
        raise ValueError("Lista de campos ausentes diverge da reconciliação.")
    missing_ids = [str(field_row["field_id"]) for field_row in missing_fields]
    if len(missing_ids) != len(set(missing_ids)):
        raise ValueError("Lista de correção contém field_id duplicado.")

    vocabulary_path = source_operation_root / "frozen_vocabulary.json"
    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
    vocabulary_sha256 = sha256_json(vocabulary)
    source_manifest = json.loads(
        (source_operation_root / "batch_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    if vocabulary_sha256 != source_manifest["vocabulary_sha256"]:
        raise ValueError("Vocabulário da correção diverge da operação de origem.")
    request_schema = batch_mapping_output_json_schema()
    request_schema_sha256 = sha256_json(request_schema)
    if request_schema_sha256 != source_manifest["response_schema_sha256"]:
        raise ValueError("JSON Schema da correção diverge da operação de origem.")

    grouped: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for field_row in missing_fields:
        grouped[
            (
                str(field_row["source"]),
                str(field_row["dataset"]),
                str(field_row["record_type"]),
            )
        ].append(field_row)

    requests = []
    request_index = []
    request_number = 0
    for group_key in sorted(grouped):
        source, dataset, record_type = group_key
        rows = sorted(grouped[group_key], key=lambda row: str(row["field_id"]))
        for start in range(0, len(rows), chunk_size):
            request_number += 1
            chunk = rows[start : start + chunk_size]
            fields = [_compact_batch_field_input(row) for row in chunk]
            custom_id = f"g02-repair-{request_number:03d}"
            requests.append(
                {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": _batch_request_body(
                        vocabulary=vocabulary,
                        vocabulary_sha256=vocabulary_sha256,
                        fields=fields,
                    ),
                }
            )
            request_index.append(
                {
                    "custom_id": custom_id,
                    "source": source,
                    "dataset": dataset,
                    "record_type": record_type,
                    "field_count": len(fields),
                    "first_field_id": fields[0]["id"],
                    "last_field_id": fields[-1]["id"],
                    "field_ids_sha256": sha256_json(
                        [field["id"] for field in fields]
                    ),
                }
            )

    batch_input_text = "".join(
        json_compact(request) + "\n" for request in requests
    )
    request_index_text = "".join(
        json_compact(row) + "\n" for row in request_index
    )
    vocabulary_text = (
        json.dumps(
            vocabulary,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    schema_text = (
        json.dumps(
            request_schema,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    repair_operation_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "batch_input": repair_operation_root / "batch_input.jsonl",
        "request_index": repair_operation_root / "batch_request_index.jsonl",
        "vocabulary": repair_operation_root / "frozen_vocabulary.json",
        "response_schema": (
            repair_operation_root / "batch_response.schema.json"
        ),
        "manifest": repair_operation_root / "batch_manifest.json",
    }
    reused = all(path.exists() for path in paths.values())
    _write_reusable_text(paths["batch_input"], batch_input_text)
    _write_reusable_text(paths["request_index"], request_index_text)
    _write_reusable_text(paths["vocabulary"], vocabulary_text)
    _write_reusable_text(paths["response_schema"], schema_text)
    manifest = {
        "operation_id": operation_id,
        "status": "prepared",
        "scientific_gate": "batch_repair_not_submitted",
        "parent_operation_id": reconciliation["operation_id"],
        "parent_batch_id": reconciliation["batch_id"],
        "parent_reconciliation_sha256": sha256_file(
            source_operation_root / "batch_reconciliation.json"
        ),
        "missing_fields_sha256": sha256_file(missing_path),
        "requested_model": BATCH_REQUESTED_MODEL,
        "reasoning_effort": "low",
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "prompt_version": BATCH_MAPPING_PROMPT_VERSION,
        "prompt_sha256": sha256_text(batch_mapping_prompt()),
        "response_schema_version": BATCH_MAPPING_SCHEMA_VERSION,
        "response_schema_sha256": request_schema_sha256,
        "vocabulary_version": BATCH_MAPPING_VOCABULARY_VERSION,
        "vocabulary_sha256": vocabulary_sha256,
        "global_proposal_sha256": source_manifest["global_proposal_sha256"],
        "crosswalk_sha256": source_manifest["crosswalk_sha256"],
        "batch_input_sha256": sha256_text(batch_input_text),
        "request_index_sha256": sha256_text(request_index_text),
        "counts": {
            "field_ids": len(missing_fields),
            "requests": len(requests),
            "record_groups": len(grouped),
            "type_conflicts": sum(
                bool(field_row["type_conflict"])
                for field_row in missing_fields
            ),
            "ccj_notas_field_ids": sum(
                field_row["source"] == "senado"
                and field_row["dataset"] == "ccj_notas"
                for field_row in missing_fields
            ),
        },
        "chunk_size": chunk_size,
        "batch_input_size_bytes": len(batch_input_text.encode("utf-8")),
        "proposal_applied": False,
        "raw_mutated": False,
        "normalization_materialized": False,
    }
    _write_reusable_text(
        paths["manifest"],
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return {
        "paths": paths,
        "manifest": manifest,
        "requests": requests,
        "request_index": request_index,
        "reused": reused,
    }


def merge_batch_mapping_attempts(
    primary_operation_root: Path,
    repair_operation_roots: Sequence[Path],
) -> dict[str, Any]:
    """Merge disjoint validated proposals and prove complete field coverage."""

    primary_operation_root = Path(primary_operation_root).resolve()
    operation_roots = [
        primary_operation_root,
        *(Path(path).resolve() for path in repair_operation_roots),
    ]
    primary_requests = read_jsonl(primary_operation_root / "batch_input.jsonl")
    expected_ids = {
        field_row["field_id"]
        for request in primary_requests
        for field_row in _expanded_batch_request_fields(
            json.loads(request["body"]["input"][1]["content"][0]["text"])
        )
    }
    merged_by_id: dict[str, dict[str, Any]] = {}
    reconciliations = []
    total_cost = Decimal("0")
    for operation_root in operation_roots:
        reconciliation = json.loads(
            (operation_root / "batch_reconciliation.json").read_text(
                encoding="utf-8"
            )
        )
        if reconciliation.get("status") not in {
            "completed_validated",
            "completed_incomplete_coverage",
        }:
            raise ValueError(f"Operação Batch não validada: {operation_root}")
        reconciliations.append(reconciliation)
        total_cost += Decimal(str(reconciliation["actual_cost_usd"]))
        for row in read_csv(
            operation_root / "mapeamentos_batch_propostos.csv"
        ):
            field_id = str(row["field_id"])
            if field_id in merged_by_id:
                raise ValueError(
                    f"field_id repetido entre tentativas Batch: {field_id}"
                )
            merged_by_id[field_id] = row

    unknown_ids = sorted(set(merged_by_id).difference(expected_ids))
    missing_ids = sorted(expected_ids.difference(merged_by_id))
    if unknown_ids:
        raise ValueError(f"Tentativas Batch inventam IDs: {unknown_ids[:10]}")
    mapping_fields = [
        "field_id",
        "source",
        "dataset",
        "record_type",
        "reconstructed_original_field_path",
        "observed_type_codes",
        "observed_cardinality",
        "presence_state_mask",
        "decision",
        "canonical_candidate_or_null",
        "mapping_operation",
        "review_reason",
        "custom_id",
        "batch_id",
        "requested_model",
        "resolved_model",
        "human_decision",
        "proposal_applied",
    ]
    rows = [merged_by_id[field_id] for field_id in sorted(merged_by_id)]
    write_csv(
        primary_operation_root
        / "mapeamentos_batch_propostos_reconciliados.csv",
        rows,
        mapping_fields,
    )
    result = {
        "operation_id": BATCH_MAPPING_OPERATION_ID,
        "status": (
            "completed_validated"
            if not missing_ids
            else "completed_incomplete_coverage"
        ),
        "scientific_gate": (
            "needs_human_review" if not missing_ids else "repair_required"
        ),
        "field_ids_expected": len(expected_ids),
        "field_ids_reconciled": len(merged_by_id),
        "missing_field_ids": len(missing_ids),
        "missing_field_ids_sha256": (
            sha256_json(missing_ids) if missing_ids else None
        ),
        "attempts": [
            {
                "operation_id": reconciliation["operation_id"],
                "batch_id": reconciliation["batch_id"],
                "status": reconciliation["status"],
                "field_ids_reconciled": reconciliation[
                    "field_ids_reconciled"
                ],
                "actual_cost_usd": reconciliation["actual_cost_usd"],
            }
            for reconciliation in reconciliations
        ],
        "actual_cost_usd_total": str(total_cost),
        "proposal_applied": False,
        "raw_mutated": False,
        "normalization_materialized": False,
    }
    _write_reusable_text(
        primary_operation_root / "batch_reconciliation_final.json",
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return result


def _openai_client(client: Any | None) -> Any:
    if client is not None:
        return client
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY não está disponível no ambiente.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Instale o SDK oficial openai.") from exc
    return OpenAI()


def _global_catalog_type_codes(
    field_rows: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    observed = sorted(
        {
            technical_type_name
            for row in field_rows
            for technical_type_name in str(
                row.get("technical_types", "")
            ).split("|")
            if technical_type_name
        }
    )
    preferred = {
        "array": "a",
        "boolean": "b",
        "bytes": "y",
        "date": "d",
        "datetime": "dt",
        "decimal": "dc",
        "integer": "i",
        "null": "n",
        "number": "r",
        "object": "o",
        "string": "s",
        "time": "t",
    }
    result: dict[str, str] = {}
    used: set[str] = set()
    extra_index = 1
    for name in observed:
        code = preferred.get(name)
        if code is None or code in used:
            while f"x{extra_index}" in used:
                extra_index += 1
            code = f"x{extra_index}"
            extra_index += 1
        result[name] = code
        used.add(code)
    return result


def _global_catalog_prefix_blocks(
    group_rows: Sequence[Mapping[str, Any]],
) -> list[tuple[str, list[tuple[Mapping[str, Any], str]]]]:
    by_parent: defaultdict[str, list[tuple[Mapping[str, Any], str]]] = defaultdict(list)
    direct: list[tuple[Mapping[str, Any], str]] = []
    for row in group_rows:
        path = str(row.get("field_path", ""))
        parent, suffix = _global_catalog_parent_suffix(path)
        by_parent[parent].append((row, suffix))
    factored: dict[str, list[tuple[Mapping[str, Any], str]]] = {}
    for parent, rows in by_parent.items():
        full_size = sum(len(str(row.get("field_path", ""))) for row, _ in rows)
        factored_size = len(parent) + sum(len(suffix) for _, suffix in rows)
        if parent and len(rows) >= 2 and full_size - factored_size >= 8:
            factored[parent] = rows
        else:
            direct.extend(
                (row, str(row.get("field_path", ""))) for row, _ in rows
            )
    blocks: list[tuple[str, list[tuple[Mapping[str, Any], str]]]] = []
    if direct:
        blocks.append(
            (
                "",
                sorted(
                    direct,
                    key=lambda item: str(item[0].get("field_path", "")),
                ),
            )
        )
    blocks.extend(
        (
            parent,
            sorted(rows, key=lambda item: str(item[0].get("field_path", ""))),
        )
        for parent, rows in sorted(factored.items())
    )
    return blocks


def _global_catalog_parent_suffix(path: str) -> tuple[str, str]:
    if path == "$" or not path:
        return "", path
    if path.endswith("[]"):
        return path[:-2], "[]"
    for index in range(len(path) - 1, 0, -1):
        if path[index] != ".":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and path[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return path[:index], path[index:]
    return "", path


def _select_global_catalog_sample_keys(
    group_rows: Sequence[Mapping[str, Any]],
    limit: int,
) -> set[tuple[str, str, str, str]]:
    if limit <= 0 or not group_rows:
        return set()
    ordered = sorted(
        group_rows,
        key=lambda row: str(row.get("field_path", "")),
    )
    conflicts = [
        row for row in ordered if truthy(str(row.get("type_conflict", "")))
    ]
    conflict_limit = min(len(conflicts), max(1, limit // 2))
    selected = _spread_sequence(conflicts, conflict_limit)
    selected_keys = {
        (
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            str(row.get("record_type", "")),
            str(row.get("field_path", "")),
        )
        for row in selected
    }
    remaining = [
        row
        for row in ordered
        if (
            str(row.get("source", "")),
            str(row.get("dataset", "")),
            str(row.get("record_type", "")),
            str(row.get("field_path", "")),
        )
        not in selected_keys
    ]
    for row in _spread_sequence(remaining, limit - len(selected_keys)):
        selected_keys.add(
            (
                str(row.get("source", "")),
                str(row.get("dataset", "")),
                str(row.get("record_type", "")),
                str(row.get("field_path", "")),
            )
        )
    return selected_keys


def _spread_sequence(
    rows: Sequence[Mapping[str, Any]],
    limit: int,
) -> list[Mapping[str, Any]]:
    if limit <= 0 or not rows:
        return []
    if limit >= len(rows):
        return list(rows)
    if limit == 1:
        return [rows[0]]
    indexes = {
        round(position * (len(rows) - 1) / (limit - 1))
        for position in range(limit)
    }
    return [rows[index] for index in sorted(indexes)]


def _global_catalog_cardinality(row: Mapping[str, Any]) -> str:
    value = _catalog_cell(row.get("cardinality", ""))
    method = str(row.get("cardinality_method", ""))
    if value == "-":
        return "-"
    if method == "exact_scalar_values":
        return f"={value}"
    if method == "kmv_scalar_estimate":
        return f"~{value}"
    return value


def _global_catalog_core_presence(row: Mapping[str, Any]) -> str:
    states = "".join(
        code
        for name, code in (
            ("field_absent", "a"),
            ("present_null", "n"),
            ("present_empty", "e"),
            ("present_filled", "f"),
        )
        if int(row.get(name, 0) or 0) > 0
    )
    return (
        f"{_catalog_cell(row.get('present_filled', ''))}/"
        f"{_catalog_cell(row.get('records_universe', ''))}:"
        f"{states or '-'}"
    )


def _global_catalog_safe_value(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= DEFAULT_METADATA_VALUE_LIMIT:
            return value
        return {
            "kind": "redacted_long_string",
            "length": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        }
    if isinstance(value, Mapping):
        return {
            str(key): _global_catalog_safe_value(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_global_catalog_safe_value(child) for child in value]
    return canonical_json_value(value)


def _catalog_json(value: Any) -> str:
    encoded = json.dumps(
        canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return encoded.replace("|", "\\u007c")


def _catalog_cell(value: Any) -> str:
    text = str(value)
    return text if text else "-"


def _csv_text(
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> str:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def _write_reusable_text(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise FileExistsError(
                f"Artefato existente diverge e não será sobrescrito: {path}"
            )
        return
    path.write_bytes(encoded)


def validated_config(config: SchemaConfig) -> SchemaConfig:
    raw_root = config.raw_root.expanduser().resolve()
    inventory_root = config.inventory_root.expanduser().resolve()
    output_base = config.output_base.expanduser().resolve()
    normalized = SchemaConfig(
        raw_root=raw_root,
        inventory_root=inventory_root,
        output_base=output_base,
        operation_id=config.operation_id,
        code_commit=config.code_commit,
        expected_inventory_operation_id=config.expected_inventory_operation_id,
        expected_inventory_manifest_sha256=(
            config.expected_inventory_manifest_sha256
        ),
        enforce_approved_counts=config.enforce_approved_counts,
        metadata_value_limit=config.metadata_value_limit,
        preview_limit=config.preview_limit,
        max_json_bytes=config.max_json_bytes,
        max_alias_candidates_per_group=config.max_alias_candidates_per_group,
        field_review_path=resolve_optional(config.field_review_path),
        manual_alias_path=resolve_optional(config.manual_alias_path),
        api_categories_path=resolve_optional(config.api_categories_path),
        progress_every_files=config.progress_every_files,
    )
    if not raw_root.is_dir() or raw_root.name != "raw":
        raise ValueError(f"Raiz raw inválida: {raw_root}")
    if not inventory_root.is_dir():
        raise ValueError(f"Diretório G01 inválido: {inventory_root}")
    if not config.operation_id or "/" in config.operation_id:
        raise ValueError("operation_id de G02 é obrigatório e não pode conter '/'.")
    if not config.code_commit.strip():
        raise ValueError("code_commit é obrigatório.")
    if normalized.metadata_value_limit < 1:
        raise ValueError("metadata_value_limit deve ser positivo.")
    if not 1 <= normalized.preview_limit <= DEFAULT_PREVIEW_LIMIT:
        raise ValueError("preview_limit deve estar entre 1 e 500.")
    if normalized.max_alias_candidates_per_group is not None:
        if normalized.max_alias_candidates_per_group < 1:
            raise ValueError("max_alias_candidates_per_group deve ser positivo.")
        if normalized.enforce_approved_counts:
            raise ValueError(
                "Limite de candidatos não é permitido na execução integral aprovada."
            )
    operation_root = normalized.operation_root
    if is_relative_to(operation_root, raw_root):
        raise ValueError("A saída não pode ficar dentro do raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(operation_root, drive_root):
        raise ValueError("A saída temporária não pode ficar dentro do Drive.")
    if operation_root.exists():
        raise FileExistsError(
            f"A saída já existe e não será sobrescrita: {operation_root}"
        )
    return normalized


def prepare_schema_evidence(config: SchemaConfig) -> dict[str, Any]:
    config = validated_config(config)
    started_at = utc_now()
    manifest_g01, field_rows, issues = validate_inventory(config)
    value_rows = read_csv(config.inventory_root / "valores_observados.csv")
    inventory_sample_rows = read_jsonl(
        config.inventory_root / "amostras_campos.jsonl"
    )
    fingerprint_before = structural_fingerprint(config.raw_root)
    approved_fingerprint = (
        manifest_g01.get("input", {}).get("structural_fingerprint")
    )
    if approved_fingerprint and fingerprint_before != approved_fingerprint:
        raise RuntimeError("O fingerprint atual do raw diverge do inventário G01.")

    field_by_key = {
        field_key(row): row
        for row in field_rows
    }
    roles, review_rows = build_field_book(
        field_rows,
        review_path=config.field_review_path,
    )
    candidates = generate_alias_candidates(
        field_rows,
        field_roles=roles,
        manual_alias_path=config.manual_alias_path,
        max_per_group=config.max_alias_candidates_per_group,
    )
    candidates_by_group: defaultdict[
        tuple[str, str, str], list[AliasCandidate]
    ] = defaultdict(list)
    candidate_ids_by_path: defaultdict[
        tuple[str, str, str, str], set[str]
    ] = defaultdict(set)
    candidate_by_id = {
        candidate.candidate_id: candidate for candidate in candidates
    }
    metrics = {candidate.candidate_id: AliasMetrics() for candidate in candidates}
    for candidate in candidates:
        candidate_group = (
            candidate.source,
            candidate.dataset,
            candidate.record_type,
        )
        candidates_by_group[candidate_group].append(candidate)
        candidate_ids_by_path[(*candidate_group, candidate.field_a)].add(
            candidate.candidate_id
        )
        candidate_ids_by_path[(*candidate_group, candidate.field_b)].add(
            candidate.candidate_id
        )

    sample_selector = StructuralSampleSelector(
        field_by_key,
        roles,
        metadata_value_limit=config.metadata_value_limit,
    )
    preview_selector = PreviewSelector(
        field_by_key,
        roles,
        preview_limit=config.preview_limit,
    )
    files = selected_inventory_files(config.inventory_root)
    records_seen = 0
    for file_index, file_row in enumerate(files, start=1):
        for raw_record in iter_raw_file(
            config.raw_root,
            file_row,
            max_json_bytes=config.max_json_bytes,
        ):
            records_seen += 1
            sample_selector.observe(raw_record)
            preview_selector.observe(raw_record)
            group = (
                raw_record.source,
                raw_record.dataset,
                raw_record.record_type,
            )
            group_candidates = candidates_by_group.get(group)
            if group_candidates:
                occurrences = occurrences_by_path(raw_record.value)
                relevant_ids: set[str] = set()
                for path in occurrences:
                    relevant_ids.update(candidate_ids_by_path.get((*group, path), ()))
                for candidate_id in sorted(relevant_ids):
                    candidate = candidate_by_id[candidate_id]
                    metrics[candidate.candidate_id].observe(
                        occurrences.get(candidate.field_a),
                        occurrences.get(candidate.field_b),
                        raw_record.coordinate,
                    )
        if config.progress_every_files > 0 and (
            file_index == 1
            or file_index == len(files)
            or file_index % config.progress_every_files == 0
        ):
            print(
                f"[schema-v3] arquivos lidos: {file_index}/{len(files)}",
                flush=True,
            )
    expected_records = int(manifest_g01["counts"]["records_read"])
    if records_seen != expected_records:
        raise RuntimeError(
            f"Leitura G02 observou {records_seen} registros; G01 registra "
            f"{expected_records}."
        )
    fingerprint_after = structural_fingerprint(config.raw_root)
    if fingerprint_after != fingerprint_before:
        raise RuntimeError("A árvore raw mudou durante a auditoria G02.")

    group_universe = {
        (row["source"], row["dataset"], row["record_type"]): int(
            row["records_universe"]
        )
        for row in field_rows
    }
    for candidate in candidates:
        metrics[candidate.candidate_id].finalize_universe(
            group_universe[
                (candidate.source, candidate.dataset, candidate.record_type)
            ]
        )

    sample_rows = sample_selector.rows()
    preview_rows = preview_selector.rows()
    alias_rows = build_alias_rows(candidates, metrics)
    conflict_rows = build_conflict_rows(field_rows, inventory_sample_rows)
    rejected_rows = build_rejected_rows(
        issues,
        config.raw_root,
        inventory_file_rows=files,
    )
    ccj_report = render_ccj_report(field_rows, conflict_rows)
    api_categories = load_api_categories(config.api_categories_path)
    packets = build_gpt_packets(
        field_rows=field_rows,
        value_rows=value_rows,
        field_roles=roles,
        sample_rows=sample_rows,
        alias_rows=alias_rows,
        api_categories=api_categories,
    )
    operation_root = config.operation_root
    operation_root.mkdir(parents=True)
    paths = write_preparation_outputs(
        operation_root=operation_root,
        field_book_rows=review_rows,
        alias_rows=alias_rows,
        sample_rows=sample_rows,
        preview_rows=preview_rows,
        conflict_rows=conflict_rows,
        rejected_rows=rejected_rows,
        ccj_report=ccj_report,
        packets=packets,
    )
    manifest = build_manifest(
        config=config,
        manifest_g01=manifest_g01,
        fingerprint=fingerprint_before,
        started_at=started_at,
        records_seen=records_seen,
        paths=paths,
        counts={
            "field_book_rows": len(review_rows),
            "alias_candidates": len(alias_rows),
            "structural_samples": len(sample_rows),
            "context_previews": len(preview_rows),
            "type_conflicts": len(conflict_rows),
            "rejected_lines": len(rejected_rows),
            "gpt_packets": len(packets),
        },
    )
    write_json(operation_root / "manifest.json", manifest)
    return {
        "manifest": manifest,
        "paths": {**paths, "manifest": operation_root / "manifest.json"},
        "field_book_rows": review_rows,
        "alias_rows": alias_rows,
        "sample_rows": sample_rows,
        "preview_rows": preview_rows,
        "packets": packets,
    }


def initialize_field_review(
    config: SchemaConfig,
    output_path: Path,
) -> Path:
    normalized_output = output_path.expanduser().resolve()
    if normalized_output.exists():
        raise FileExistsError(
            f"A revisão já existe e não será sobrescrita: {normalized_output}"
        )
    raw_root = config.raw_root.expanduser().resolve()
    if is_relative_to(normalized_output, raw_root):
        raise ValueError("A revisão de campos não pode ser escrita dentro do raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(normalized_output, drive_root):
        raise ValueError("A revisão temporária não pode ser escrita no Drive.")
    _manifest, field_rows, _issues = validate_inventory(config)
    _roles, review_rows = build_field_book(field_rows, review_path=None)
    normalized_output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(normalized_output, review_rows, FIELD_BOOK_FIELDS)
    return normalized_output


def build_field_book(
    field_rows: Sequence[Mapping[str, str]],
    *,
    review_path: Path | None,
) -> tuple[
    dict[tuple[str, str, str, str], str],
    list[dict[str, Any]],
]:
    existing: dict[tuple[str, str, str, str], Mapping[str, str]] = {}
    if review_path is not None:
        for row in read_csv(review_path):
            key = field_key(row)
            if key in existing:
                raise ValueError(f"Chave duplicada na revisão de campos: {key}")
            existing[key] = row
    inventory_keys = {field_key(row) for row in field_rows}
    invented = set(existing).difference(inventory_keys)
    if invented:
        raise ValueError(
            f"A revisão de campos inventou {len(invented)} caminhos; exemplo: "
            f"{sorted(invented)[0]}"
        )

    allowed_roles = {"unknown", "metadata", "text", "technical_control"}
    allowed_decisions = {
        "nao_avaliado",
        "candidato",
        "mapeado",
        "preservado_sem_normalizacao",
        "adiado_para_estrutura_textual",
        "conflito_aberto",
        "fora_do_schema_proposto",
    }
    roles: dict[tuple[str, str, str, str], str] = {}
    result: list[dict[str, Any]] = []
    for row in sorted(field_rows, key=field_sort_key):
        key = field_key(row)
        decision_row = existing.get(key, {})
        role = str(decision_row.get("semantic_role") or "unknown")
        decision = str(decision_row.get("decision") or "nao_avaliado")
        if role not in allowed_roles:
            raise ValueError(f"semantic_role inválido para {key}: {role}")
        if decision not in allowed_decisions:
            raise ValueError(f"decision inválida para {key}: {decision}")
        rationale = str(decision_row.get("decision_rationale") or "")
        if decision == "fora_do_schema_proposto" and not rationale.strip():
            raise ValueError(
                f"fora_do_schema_proposto exige justificativa humana: {key}"
            )
        roles[key] = role
        result.append(
            {
                **{name: row.get(name, "") for name in FIELD_BOOK_FIELDS},
                "semantic_role": role,
                "decision": decision,
                "proposed_category": decision_row.get("proposed_category", ""),
                "proposed_logical_type": decision_row.get(
                    "proposed_logical_type", ""
                ),
                "rule_id": decision_row.get("rule_id", ""),
                "decision_rationale": rationale,
                "decision_by": decision_row.get("decision_by", ""),
                "decision_at": decision_row.get("decision_at", ""),
            }
        )
    if len(result) != len(inventory_keys):
        raise AssertionError("O livro de campos não cobre exatamente o inventário.")
    return roles, result


def generate_alias_candidates(
    field_rows: Sequence[Mapping[str, str]],
    *,
    field_roles: Mapping[tuple[str, str, str, str], str],
    manual_alias_path: Path | None,
    max_per_group: int | None,
) -> list[AliasCandidate]:
    known_keys = {field_key(row) for row in field_rows}
    groups: defaultdict[
        tuple[str, str, str, str, str], list[str]
    ] = defaultdict(list)
    for row in field_rows:
        if field_roles.get(field_key(row)) != "metadata":
            continue
        path = row["field_path"]
        if path == "$":
            continue
        terminal = terminal_key(path)
        non_null_types = "|".join(
            value
            for value in str(row["technical_types"]).split("|")
            if value and value != "null"
        )
        groups[
            (
                row["source"],
                row["dataset"],
                row["record_type"],
                terminal,
                non_null_types,
            )
        ].append(path)

    candidates: dict[str, AliasCandidate] = {}
    per_record_group: Counter[tuple[str, str, str]] = Counter()
    for key in sorted(groups):
        source, dataset, record_type, _terminal, _types = key
        paths = sorted(set(groups[key]))
        for field_a, field_b in itertools.combinations(paths, 2):
            group = (source, dataset, record_type)
            if max_per_group is not None and per_record_group[group] >= max_per_group:
                break
            candidate = AliasCandidate(
                source=source,
                dataset=dataset,
                record_type=record_type,
                field_a=field_a,
                field_b=field_b,
            )
            candidates[candidate.candidate_id] = candidate
            per_record_group[group] += 1

    if manual_alias_path is not None:
        for row in read_csv(manual_alias_path):
            scope = row.get("comparison_scope") or "same_record"
            if scope not in {"same_record", "linked_records"}:
                raise ValueError(f"comparison_scope inválido: {scope}")
            candidate_signal = (
                row.get("candidate_signal") or "human_declared"
            )
            approved_structural_audit = candidate_signal.startswith(
                "human_approved_structural_audit:"
            )
            field_a, field_b = sorted([row["field_a"], row["field_b"]])
            for path in (field_a, field_b):
                key = (
                    row["source"],
                    row["dataset"],
                    row["record_type"],
                    path,
                )
                if key not in known_keys:
                    raise ValueError(f"Par manual cita caminho inexistente: {key}")
                allowed_roles = (
                    {"metadata", "text", "technical_control"}
                    if approved_structural_audit
                    else {"metadata"}
                )
                if field_roles.get(key) not in allowed_roles:
                    raise ValueError(
                        "Par manual exige papel estrutural permitido "
                        f"{sorted(allowed_roles)}: {key}"
                    )
            candidate = AliasCandidate(
                source=row["source"],
                dataset=row["dataset"],
                record_type=row["record_type"],
                field_a=field_a,
                field_b=field_b,
                comparison_scope=scope,
                candidate_signal=candidate_signal,
            )
            candidates[candidate.candidate_id] = candidate
    return [candidates[key] for key in sorted(candidates)]


def build_alias_rows(
    candidates: Sequence[AliasCandidate],
    metrics: Mapping[str, AliasMetrics],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        metric = metrics[candidate.candidate_id]
        if candidate.comparison_scope != "same_record":
            metric.evidence_status = "insufficient_without_approved_link"
        metric.validate()
        rates = metric.rates()
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "source": candidate.source,
                "dataset": candidate.dataset,
                "record_type": candidate.record_type,
                "field_a": candidate.field_a,
                "field_b": candidate.field_b,
                "comparison_scope": candidate.comparison_scope,
                "candidate_signal": candidate.candidate_signal,
                "comparator": "typed_exact_json_occurrence_sequence_v1",
                "rule_id": "",
                "records_universe": metric.records_universe,
                "u": metric.u,
                "ab": metric.ab,
                "equal": metric.equal,
                "different": metric.different,
                "only_a": metric.only_a,
                "only_b": metric.only_b,
                **rates,
                "a_absent": metric.a_absent,
                "a_null": metric.a_null,
                "a_empty": metric.a_empty,
                "b_absent": metric.b_absent,
                "b_null": metric.b_null,
                "b_empty": metric.b_empty,
                "agree_coordinates": json_compact(metric.agree_coordinates),
                "differ_coordinates": json_compact(metric.differ_coordinates),
                "link_matched": metric.link_matched,
                "link_unmatched_a": metric.link_unmatched_a,
                "link_unmatched_b": metric.link_unmatched_b,
                "link_ambiguous": metric.link_ambiguous,
                "evidence_status": metric.evidence_status,
                "human_decision": "nao_avaliado",
                "human_rationale": "",
            }
        )
    return rows


def audit_linked_records(
    records_a: Sequence[RawRecord],
    records_b: Sequence[RawRecord],
    *,
    rule: LinkRule,
) -> AliasMetrics:
    rule.validate()
    index_a, ambiguous_a, _unkeyed_a = build_unique_link_index(
        records_a, rule.link_path_a
    )
    index_b, ambiguous_b, _unkeyed_b = build_unique_link_index(
        records_b, rule.link_path_b
    )
    ambiguous_keys = ambiguous_a | ambiguous_b
    common = sorted(set(index_a) & set(index_b) - ambiguous_keys)
    metrics = AliasMetrics()
    for token in common:
        record_a = index_a[token]
        record_b = index_b[token]
        metrics.observe(
            occurrences_by_path(record_a.value).get(rule.value_path_a),
            occurrences_by_path(record_b.value).get(rule.value_path_b),
            f"{record_a.coordinate}<->{record_b.coordinate}",
        )
    metrics.link_matched = len(common)
    metrics.link_ambiguous = len(ambiguous_keys)
    metrics.link_unmatched_a = len(records_a) - len(common)
    metrics.link_unmatched_b = len(records_b) - len(common)
    metrics.evidence_status = (
        "measured_with_approved_one_to_one_link"
        if not ambiguous_keys
        else "measured_with_ambiguous_keys_excluded"
    )
    metrics.validate()
    return metrics


def build_unique_link_index(
    records: Sequence[RawRecord],
    link_path: str,
) -> tuple[dict[str, RawRecord], set[str], int]:
    buckets: defaultdict[str, list[RawRecord]] = defaultdict(list)
    unkeyed = 0
    for record in records:
        values = occurrences_by_path(record.value).get(link_path)
        if occurrence_state(values) != "filled":
            unkeyed += 1
            continue
        buckets[typed_occurrence_token(values or [])].append(record)
    ambiguous = {key for key, values in buckets.items() if len(values) != 1}
    unique = {
        key: values[0]
        for key, values in buckets.items()
        if key not in ambiguous
    }
    return unique, ambiguous, unkeyed


def selected_inventory_files(inventory_root: Path) -> list[dict[str, str]]:
    rows = read_csv(inventory_root / "inventario_arquivos.csv")
    selected = [
        row
        for row in rows
        if row.get("item_type") == "file"
        and truthy(row.get("selected_for_read", ""))
        and row.get("read_status") in {"read", "read_with_rejections"}
    ]
    return sorted(selected, key=lambda row: row["relative_path"])


def iter_raw_file(
    raw_root: Path,
    file_row: Mapping[str, str],
    *,
    max_json_bytes: int,
) -> Iterator[RawRecord]:
    relative_path = file_row["relative_path"]
    path = raw_root / relative_path
    suffix = path.suffix.lower()
    source = file_row["source"]
    dataset = file_row["dataset"]
    if suffix in {".jsonl", ".ndjson"}:
        technical_kind = "jsonl_record"
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    line_number,
                    technical_kind,
                    value,
                )
        return
    if suffix == ".json":
        if path.stat().st_size > max_json_bytes:
            raise RuntimeError(f"JSON excede max_json_bytes em G02: {relative_path}")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            for index, item in enumerate(value, start=1):
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    index,
                    "json_array_item",
                    item,
                )
        else:
            yield make_raw_record(
                source,
                dataset,
                relative_path,
                1,
                "json_document",
                value,
            )
        return
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return
            for index, value in enumerate(reader, start=1):
                if None in value:
                    continue
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    index,
                    "csv_row",
                    dict(value),
                )
        return
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pyarrow é necessário para ler Parquet.") from exc
        parquet = pq.ParquetFile(path)
        record_number = 0
        for batch in parquet.iter_batches(batch_size=4_096):
            for value in batch.to_pylist():
                record_number += 1
                yield make_raw_record(
                    source,
                    dataset,
                    relative_path,
                    record_number,
                    "parquet_row",
                    value,
                )
        return
    raise ValueError(f"Formato não suportado listado em G01: {relative_path}")


def make_raw_record(
    source: str,
    dataset: str,
    relative_path: str,
    record_number: int,
    technical_kind: str,
    value: Any,
) -> RawRecord:
    return RawRecord(
        source=source,
        dataset=dataset,
        record_type=declared_record_type(value, technical_kind),
        relative_path=relative_path,
        record_number=record_number,
        technical_kind=technical_kind,
        value=value,
    )


def occurrences_by_path(value: Any) -> dict[str, list[Any]]:
    result: defaultdict[str, list[Any]] = defaultdict(list)
    for path, occurrence in flatten_fields(value):
        result[path].append(occurrence)
    return dict(result)


def occurrence_state(values: Sequence[Any] | None) -> str:
    if values is None:
        return "absent"
    states = {value_state(value) for value in values}
    if "filled" in states:
        return "filled"
    if "empty" in states:
        return "empty"
    return "null"


def typed_occurrence_token(values: Sequence[Any]) -> str:
    typed = [
        {
            "technical_type": technical_type(value),
            "value": canonical_json_value(value),
        }
        for value in values
    ]
    return json_compact(typed)


def sanitize_record(
    value: Any,
    *,
    group: tuple[str, str, str],
    field_roles: Mapping[tuple[str, str, str, str], str],
    metadata_value_limit: int,
    path: str = "$",
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_record(
                child,
                group=group,
                field_roles=field_roles,
                metadata_value_limit=metadata_value_limit,
                path=f"{path}.{escape_path_key(str(key))}",
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            sanitize_record(
                child,
                group=group,
                field_roles=field_roles,
                metadata_value_limit=metadata_value_limit,
                path=f"{path}[]",
            )
            for child in value
        ]
    if isinstance(value, str):
        role = field_roles.get((*group, path), "unknown")
        if role == "metadata" and len(value) <= metadata_value_limit:
            return value
        return {
            "__redacted_string__": True,
            "length": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "semantic_role": role,
        }
    if isinstance(value, bytes):
        return {
            "__redacted_bytes__": True,
            "length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    return canonical_json_value(value)


def structure_signature(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): structure_signature(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [structure_signature(child) for child in value]
    return {"technical_type": technical_type(value), "state": value_state(value)}


def build_conflict_rows(
    field_rows: Sequence[Mapping[str, str]],
    sample_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    samples_by_field: defaultdict[
        tuple[str, str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for sample in sample_rows:
        samples_by_field[field_key(sample)].append(sample)
    rows = []
    for row in sorted(field_rows, key=field_sort_key):
        if not truthy(row["type_conflict"]):
            continue
        rows.append(
            {
                **dict(row),
                "safe_examples_json": json_compact(
                    sorted(
                        samples_by_field.get(field_key(row), []),
                        key=lambda item: str(item.get("sample_hash", "")),
                    )
                ),
                "decision": "conflito_aberto",
                "proposed_treatment": "",
                "human_rationale": "",
            }
        )
    return rows


def build_rejected_rows(
    issues: Sequence[Mapping[str, str]],
    raw_root: Path,
    *,
    inventory_file_rows: Sequence[Mapping[str, str]] | None = None,
) -> list[dict[str, Any]]:
    if inventory_file_rows is not None:
        rows = []
        expected = 0
        for file_row in inventory_file_rows:
            rejected = int(file_row.get("records_rejected") or 0)
            if not rejected:
                continue
            expected += rejected
            rows.extend(
                scan_rejected_file(
                    raw_root / file_row["relative_path"],
                    relative_path=file_row["relative_path"],
                )
            )
        if len(rows) != expected:
            raise RuntimeError(
                "Reconciliação de linhas rejeitadas diverge do inventário: "
                f"{len(rows)} localizadas para {expected} registradas."
            )
        return sorted(
            rows,
            key=lambda row: (row["relative_path"], row["record_number"]),
        )

    rows = []
    for issue in issues:
        if issue.get("issue_type") not in {"invalid_json_line", "invalid_csv_row"}:
            continue
        relative_path = issue["relative_path"]
        record_number = int(issue["record_number"])
        raw_hash = rejected_physical_line_hash(
            raw_root / relative_path,
            (
                record_number + 1
                if Path(relative_path).suffix.lower() == ".csv"
                else record_number
            ),
        )
        rows.append(
            {
                "severity": issue["severity"],
                "issue_type": issue["issue_type"],
                "relative_path": relative_path,
                "record_number": record_number,
                "field_path": issue.get("field_path", ""),
                "detail": issue["detail"],
                "raw_line_sha256": raw_hash,
                "treatment": "preserved_rejected_no_repair",
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["relative_path"], row["record_number"]),
    )


def scan_rejected_file(
    path: Path,
    *,
    relative_path: str,
) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    rows = []
    if suffix in {".jsonl", ".ndjson"}:
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                try:
                    encoding = "utf-8-sig" if line_number == 1 else "utf-8"
                    json.loads(raw_line.decode(encoding))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    if isinstance(exc, json.JSONDecodeError):
                        detail = f"{exc.msg} (coluna {exc.colno})"
                    else:
                        detail = f"{type(exc).__name__}: {exc}"
                    rows.append(
                        {
                            "severity": "warning",
                            "issue_type": "invalid_json_line",
                            "relative_path": relative_path,
                            "record_number": line_number,
                            "field_path": "",
                            "detail": detail,
                            "raw_line_sha256": hashlib.sha256(
                                raw_line
                            ).hexdigest(),
                            "treatment": "preserved_rejected_no_repair",
                        }
                    )
        return rows
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return rows
            for record_number, record in enumerate(reader, start=1):
                if None not in record:
                    continue
                rows.append(
                    {
                        "severity": "warning",
                        "issue_type": "invalid_csv_row",
                        "relative_path": relative_path,
                        "record_number": record_number,
                        "field_path": "",
                        "detail": "Linha possui mais valores que o cabeçalho.",
                        "raw_line_sha256": rejected_physical_line_hash(
                            path,
                            record_number + 1,
                        ),
                        "treatment": "preserved_rejected_no_repair",
                    }
                )
        return rows
    raise ValueError(
        "Inventário registra rejeições em formato não reconciliável: "
        f"{relative_path}"
    )


def rejected_physical_line_hash(path: Path, line_number: int) -> str:
    if path.suffix.lower() not in {".jsonl", ".ndjson", ".csv"}:
        return ""
    with path.open("rb") as handle:
        for index, line in enumerate(handle, start=1):
            if index == line_number:
                return hashlib.sha256(line).hexdigest()
    raise ValueError(f"Linha rejeitada não localizável: {path}#{line_number}")


def reconcile_rejected_lines(
    *,
    raw_root: Path,
    inventory_root: Path,
    source_audit_root: Path,
    output_base: Path,
    operation_id: str,
    code_commit: str,
    expected_inventory_operation_id: str = APPROVED_INVENTORY_OPERATION_ID,
    expected_inventory_manifest_sha256: str = (
        APPROVED_INVENTORY_MANIFEST_SHA256
    ),
) -> dict[str, Any]:
    """Rebuild every rejected record without mutating the source audit."""

    raw_root = Path(raw_root).expanduser().resolve()
    inventory_root = Path(inventory_root).expanduser().resolve()
    source_audit_root = Path(source_audit_root).expanduser().resolve()
    output_base = Path(output_base).expanduser().resolve()
    operation_root = output_base / operation_id
    if not raw_root.is_dir() or raw_root.name != "raw":
        raise ValueError(f"Raiz raw inválida: {raw_root}")
    if not inventory_root.is_dir():
        raise ValueError(f"Diretório G01 inválido: {inventory_root}")
    if not source_audit_root.is_dir():
        raise ValueError(f"Auditoria G02 de origem inválida: {source_audit_root}")
    if not operation_id or "/" in operation_id:
        raise ValueError("operation_id de reconciliação inválido.")
    if not code_commit.strip():
        raise ValueError("code_commit é obrigatório.")
    if operation_root.exists():
        raise FileExistsError(
            f"A saída já existe e não será sobrescrita: {operation_root}"
        )
    if is_relative_to(operation_root, raw_root):
        raise ValueError("A saída não pode ficar dentro do raw.")
    drive_root = mounted_drive_root(raw_root)
    if drive_root is not None and is_relative_to(operation_root, drive_root):
        raise ValueError("A saída temporária não pode ficar dentro do Drive.")

    inventory_manifest_path = inventory_root / "manifest.json"
    if sha256_file(inventory_manifest_path) != (
        expected_inventory_manifest_sha256
    ):
        raise RuntimeError("Manifest G01 diverge do hash aprovado.")
    inventory_manifest = json.loads(
        inventory_manifest_path.read_text(encoding="utf-8")
    )
    if inventory_manifest.get("operation_id") != (
        expected_inventory_operation_id
    ):
        raise RuntimeError("operation_id G01 divergente.")
    source_manifest_path = source_audit_root / "manifest.json"
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    if source_manifest.get("execution_status") != "succeeded":
        raise RuntimeError("Auditoria G02 de origem não foi concluída.")

    started_at = utc_now()
    fingerprint_before = structural_fingerprint(raw_root)
    approved_fingerprint = inventory_manifest["input"][
        "structural_fingerprint"
    ]
    if fingerprint_before != approved_fingerprint:
        raise RuntimeError("Fingerprint raw diverge do inventário G01.")
    inventory_files = selected_inventory_files(inventory_root)
    rows = build_rejected_rows(
        [],
        raw_root,
        inventory_file_rows=inventory_files,
    )
    expected = int(inventory_manifest["counts"]["records_rejected"])
    if len(rows) != expected:
        raise RuntimeError(
            f"Rejeições reconciliadas divergem de G01: {len(rows)} != {expected}"
        )
    fingerprint_after = structural_fingerprint(raw_root)
    if fingerprint_after != fingerprint_before:
        raise RuntimeError("A árvore raw mudou durante a reconciliação.")

    operation_root.mkdir(parents=True)
    rejected_path = operation_root / "linhas_rejeitadas_reconciliadas.csv"
    write_csv(rejected_path, rows, REJECTED_LINE_FIELDS)
    result = {
        "schema_version": SCHEMA_VERSION,
        "module": "normalized_schema_rejected_lines_reconciliation_v3",
        "operation_id": operation_id,
        "execution_status": "succeeded",
        "scientific_gate": "needs_review",
        "started_at": started_at,
        "finished_at": utc_now(),
        "spec_ref": SPEC_REF,
        "code_commit": code_commit,
        "input": {
            "raw_root": str(raw_root),
            "write_policy": "read_only",
            "structural_fingerprint_before": fingerprint_before,
            "structural_fingerprint_after": fingerprint_after,
            "inventory_operation_id": inventory_manifest["operation_id"],
            "inventory_manifest_sha256": sha256_file(
                inventory_manifest_path
            ),
            "source_audit_operation_id": source_manifest["operation_id"],
            "source_audit_manifest_sha256": sha256_file(
                source_manifest_path
            ),
            "source_audit_rejected_lines": int(
                source_manifest["counts"]["rejected_lines"]
            ),
        },
        "counts": {
            "records_rejected_expected": expected,
            "records_rejected_reconciled": len(rows),
            "source_issue_rows_deduplicated": int(
                source_manifest["counts"]["rejected_lines"]
            ),
            "deduplication_gap_recovered": (
                expected
                - int(source_manifest["counts"]["rejected_lines"])
            ),
        },
        "outputs": [
            artifact_ref(rejected_path, operation_root=operation_root)
        ],
        "invariants": {
            "raw_writes": 0,
            "source_audit_mutated": False,
            "normalized_records_materialized": 0,
        },
        "next_action": (
            "Revisar as 14 coordenadas; preservar a auditoria original e usar "
            "este suplemento como reconciliação da deduplicação de avisos G01."
        ),
    }
    manifest_path = operation_root / "manifest.json"
    write_json(manifest_path, result)
    return {
        "manifest": result,
        "paths": {
            "rejected": rejected_path,
            "manifest": manifest_path,
        },
        "rows": rows,
    }


def render_ccj_report(
    field_rows: Sequence[Mapping[str, str]],
    conflict_rows: Sequence[Mapping[str, Any]],
) -> str:
    ccj = [
        row
        for row in field_rows
        if row["source"] == "senado" and row["dataset"] == "ccj_notas"
    ]
    groups = Counter(row["record_type"] for row in ccj)
    type_variants = Counter(row["technical_types"] for row in ccj)
    arrays = sum("[]" in row["field_path"] for row in ccj)
    conflicts = [
        row
        for row in conflict_rows
        if row["source"] == "senado" and row["dataset"] == "ccj_notas"
    ]
    lines = [
        "# Trilha estrutural — senado/ccj_notas",
        "",
        "Estado: evidência técnica; revisão humana pendente.",
        "",
        f"- caminhos preservados: {len(ccj)}",
        f"- conflitos de tipo preservados: {len(conflicts)}",
        f"- caminhos sob coleções (`[]`): {arrays}",
        "- identidade implícita de `[]`: nenhuma",
        "- coerções ou achatamentos aplicados: nenhum",
        "",
        "## Caminhos por record_type",
        "",
        "| record_type | caminhos |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {groups[key]} |" for key in sorted(groups))
    lines.extend(
        [
            "",
            "## Combinações de tipos observadas",
            "",
            "| tipos técnicos | caminhos |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| `{key}` | {type_variants[key]} |" for key in sorted(type_variants)
    )
    lines.extend(
        [
            "",
            "Objetos, arrays, escalares, nulos, vazios, ordem e multiplicidade "
            "permanecem representados pelo caminho e pelos tipos originais. "
            "Nenhum elemento de coleção é vinculado sem chave declarativa "
            "preenchida e aprovada.",
            "",
        ]
    )
    return "\n".join(lines)


def load_api_categories(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Categorias de API devem formar uma lista JSON.")
    result = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("Cada categoria de API deve ser um objeto.")
        required = {"api_category_id", "source", "name", "definition", "url", "as_of"}
        missing = required.difference(item)
        if missing:
            raise ValueError(f"Categoria de API sem campos: {sorted(missing)}")
        if not str(item["url"]).startswith("https://"):
            raise ValueError("Referência de API exige URL HTTPS oficial.")
        result.append({name: item[name] for name in sorted(item)})
    return sorted(result, key=lambda item: str(item["api_category_id"]))


def build_gpt_packets(
    *,
    field_rows: Sequence[Mapping[str, str]],
    value_rows: Sequence[Mapping[str, str]],
    field_roles: Mapping[tuple[str, str, str, str], str],
    sample_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    api_categories: Sequence[Mapping[str, Any]],
    max_fields_per_packet: int = 100,
) -> list[dict[str, Any]]:
    fields_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, str]]
    ] = defaultdict(list)
    samples_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    aliases_by_group: defaultdict[
        tuple[str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    api_by_source: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    values_by_field: defaultdict[
        tuple[str, str, str, str], list[Mapping[str, str]]
    ] = defaultdict(list)
    for row in field_rows:
        if field_roles.get(field_key(row)) != "metadata":
            continue
        fields_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in sample_rows:
        samples_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in alias_rows:
        aliases_by_group[
            (row["source"], row["dataset"], row["record_type"])
        ].append(row)
    for row in api_categories:
        api_by_source[str(row["source"])].append(row)
    for row in value_rows:
        values_by_field[field_key(row)].append(row)

    packets: list[dict[str, Any]] = []
    for group in sorted(fields_by_group):
        ordered_fields = sorted(fields_by_group[group], key=field_sort_key)
        for chunk_index, start in enumerate(
            range(0, len(ordered_fields), max_fields_per_packet),
            start=1,
        ):
            chunk = ordered_fields[start : start + max_fields_per_packet]
            structural_fields = []
            for row in chunk:
                key = field_key(row)
                evidence_id = stable_id(
                    "field",
                    row["source"],
                    row["dataset"],
                    row["record_type"],
                    row["field_path"],
                )
                structural_fields.append(
                    {
                        "evidence_id": evidence_id,
                        "source": row["source"],
                        "dataset": row["dataset"],
                        "record_type": row["record_type"],
                        "field_path": row["field_path"],
                        "semantic_role": "metadata",
                        "technical_types": row["technical_types"].split("|"),
                        "records_universe": int(row["records_universe"]),
                        "field_absent": int(row["field_absent"]),
                        "present_null": int(row["present_null"]),
                        "present_empty": int(row["present_empty"]),
                        "present_filled": int(row["present_filled"]),
                        "fill_rate": row["fill_rate"],
                        "cardinality": integer_or_text(row["cardinality"]),
                        "cardinality_method": row["cardinality_method"],
                        "string_length": {
                            "min": integer_or_text(row["string_length_min"]),
                            "median": number_or_text(row["string_length_median"]),
                            "max": integer_or_text(row["string_length_max"]),
                        },
                        "type_conflict": truthy(row["type_conflict"]),
                        "observed_low_cardinality_values": (
                            [
                                {
                                    "value_type": value_row["value_type"],
                                    "value": json.loads(value_row["value_json"]),
                                    "frequency": int(value_row["frequency"]),
                                    "rank": int(value_row["rank"]),
                                }
                                for value_row in sorted(
                                    values_by_field.get(key, []),
                                    key=lambda item: int(item["rank"]),
                                )
                            ]
                            if field_roles.get(key) == "metadata"
                            else []
                        ),
                    }
                )
            chunk_paths = {row["field_path"] for row in chunk}
            relevant_aliases = [
                {
                    "candidate_id": row["candidate_id"],
                    "field_a": row["field_a"],
                    "field_b": row["field_b"],
                    "u": int(row["u"]),
                    "ab": int(row["ab"]),
                    "equal": int(row["equal"]),
                    "different": int(row["different"]),
                    "coincidence_rate": row["coincidence_rate"],
                    "overlap_rate": row["overlap_rate"],
                    "evidence_status": row["evidence_status"],
                }
                for row in aliases_by_group[group]
                if row["field_a"] in chunk_paths or row["field_b"] in chunk_paths
            ]
            packet_id = stable_id(
                "packet",
                *group,
                str(chunk_index),
                sha256_json(structural_fields),
            )
            packets.append(
                {
                    "packet_id": packet_id,
                    "packet_version": "g02-structural-evidence-v1",
                    "source": group[0],
                    "dataset": group[1],
                    "record_type": group[2],
                    "chunk_index": chunk_index,
                    "structural_evidence": structural_fields,
                    "record_samples": list(samples_by_group[group]),
                    "alias_metrics": relevant_aliases,
                    "official_api_categories": list(api_by_source[group[0]]),
                    "context_previews": [],
                }
            )
    return packets


def proposal_json_schema() -> dict[str, Any]:
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "proposal_id",
            "canonical_field",
            "logical_type",
            "source_paths",
            "evidence_ids",
            "context_refs",
            "api_category_refs",
            "operation",
            "possible_aliases",
            "caveats",
            "needs_human_review",
        ],
        "properties": {
            "proposal_id": {"type": "string", "minLength": 1},
            "canonical_field": {"type": "string", "minLength": 1},
            "logical_type": {
                "type": "string",
                "enum": [
                    "string",
                    "integer",
                    "number",
                    "boolean",
                    "date",
                    "datetime",
                    "object",
                    "array",
                    "typed_union",
                    "unknown",
                ],
            },
            "source_paths": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
            },
            "evidence_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "context_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "api_category_refs": {
                "type": "array",
                "items": {"type": "string"},
            },
            "operation": {
                "type": "string",
                "enum": [
                    "direct_copy",
                    "rename",
                    "lossless_cast",
                    "closed_map",
                    "preserve_unmapped",
                    "needs_human_rule",
                ],
            },
            "possible_aliases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "candidate_id",
                        "field_a",
                        "field_b",
                        "evidence_ids",
                        "status",
                    ],
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "field_a": {"type": "string"},
                        "field_b": {"type": "string"},
                        "evidence_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                        "status": {
                            "type": "string",
                            "enum": ["possible", "insufficient_evidence"],
                        },
                    },
                },
            },
            "caveats": {"type": "array", "items": {"type": "string"}},
            "needs_human_review": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["packet_id", "status", "proposals", "insufficiency_reasons"],
        "properties": {
            "packet_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["proposal", "insufficient_evidence"],
            },
            "proposals": {"type": "array", "items": proposal},
            "insufficiency_reasons": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


def proposal_prompt() -> str:
    return (
        "Você propõe somente um schema de metadados para revisão humana. "
        "Use exclusivamente structural_evidence e record_samples marcadas como "
        "evidence. Toda proposta e todo possível alias deve citar evidence_ids "
        "estruturais existentes; possível alias também deve citar um candidate_id "
        "presente em alias_metrics. context_previews são apenas context_only: não "
        "podem sustentar coluna, preenchimento, alias, marcador, orador, turno "
        "ou interpretação textual. Categorias oficiais apenas nomeiam campos "
        "observados; não criam campos ausentes. Não confirme aliases, não "
        "escolha prioridade, não descarte, não funda e não aplique regras. "
        "Quando a evidência não bastar, declare insufficient_evidence. "
        "Conflitos de tipo permanecem explícitos e exigem revisão humana."
    )


def validate_proposal(
    proposal: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    allowed_context_ids: set[str],
) -> None:
    if proposal.get("packet_id") != packet["packet_id"]:
        raise ValueError("Resposta cita packet_id diferente da entrada.")
    structural_ids = {
        item["evidence_id"] for item in packet["structural_evidence"]
    } | {
        item["evidence_id"] for item in packet["record_samples"]
    }
    known_paths = {
        item["field_path"] for item in packet["structural_evidence"]
    }
    api_ids = {
        item["api_category_id"] for item in packet["official_api_categories"]
    }
    alias_by_id = {
        item["candidate_id"]: item for item in packet.get("alias_metrics", [])
    }
    if proposal.get("status") not in {"proposal", "insufficient_evidence"}:
        raise ValueError("status da proposta inválido.")
    proposals = proposal.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("proposals deve ser lista.")
    insufficiency_reasons = proposal.get("insufficiency_reasons")
    if not isinstance(insufficiency_reasons, list):
        raise ValueError("insufficiency_reasons deve ser lista.")
    if proposal["status"] == "proposal" and not proposals:
        raise ValueError("status proposal exige ao menos uma proposta.")
    if proposal["status"] == "insufficient_evidence":
        if proposals or not insufficiency_reasons:
            raise ValueError(
                "insufficient_evidence exige propostas vazias e justificativa."
            )
    allowed_operations = {
        "direct_copy",
        "rename",
        "lossless_cast",
        "closed_map",
        "preserve_unmapped",
        "needs_human_rule",
    }
    for item in proposals:
        if not isinstance(item, Mapping):
            raise ValueError("Item de proposta deve ser objeto.")
        evidence_ids = set(item.get("evidence_ids") or [])
        if not evidence_ids or not evidence_ids.issubset(structural_ids):
            raise ValueError(
                "Proposta exige evidence_ids estruturais existentes; "
                "context_refs não os substituem."
            )
        source_paths = set(item.get("source_paths") or [])
        if not source_paths or not source_paths.issubset(known_paths):
            raise ValueError("Proposta cita caminho ausente do inventário.")
        context_refs = set(item.get("context_refs") or [])
        if not context_refs.issubset(allowed_context_ids):
            raise ValueError("Proposta cita context_id inexistente ou não aprovado.")
        if not set(item.get("api_category_refs") or []).issubset(api_ids):
            raise ValueError("Proposta cita categoria oficial inexistente.")
        if item.get("operation") not in allowed_operations:
            raise ValueError("Operação proposta fora do vocabulário fechado.")
        for alias in item.get("possible_aliases") or []:
            candidate = alias_by_id.get(alias.get("candidate_id"))
            if candidate is None:
                raise ValueError(
                    "Possível alias cita candidate_id sem auditoria recorde a recorde."
                )
            alias_evidence = set(alias.get("evidence_ids") or [])
            if not alias_evidence or not alias_evidence.issubset(structural_ids):
                raise ValueError(
                    "Possível alias exige evidence_ids estruturais válidos."
                )
            if alias.get("field_a") not in known_paths:
                raise ValueError("Alias cita field_a ausente.")
            if alias.get("field_b") not in known_paths:
                raise ValueError("Alias cita field_b ausente.")
            if {
                alias.get("field_a"),
                alias.get("field_b"),
            } != {candidate["field_a"], candidate["field_b"]}:
                raise ValueError("Possível alias diverge do par candidato auditado.")


def run_gpt_pilot(
    operation_root: Path,
    *,
    confirm_operation_id: str,
    execute_gpt: bool,
    pricing_path: Path,
    pilot_packet_ids: set[str],
    client: Any | None = None,
    model: str = REQUESTED_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict[str, Any]:
    operation_root = operation_root.resolve()
    manifest_path = operation_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    operation_id = manifest["operation_id"]
    if not execute_gpt:
        raise PermissionError("Piloto GPT bloqueado: use execute_gpt=True.")
    if confirm_operation_id != operation_id:
        raise PermissionError("Confirmação literal do operation_id não confere.")
    if model != REQUESTED_MODEL:
        raise ValueError(f"O piloto aprovado exige o alias {REQUESTED_MODEL}.")
    pricing = load_pricing(pricing_path, model)
    all_packets = read_jsonl(operation_root / "pacotes_gpt.jsonl")
    if not pilot_packet_ids:
        raise PermissionError("Selecione explicitamente packet_ids para o piloto.")
    known_packet_ids = {row["packet_id"] for row in all_packets}
    unknown_packet_ids = pilot_packet_ids.difference(known_packet_ids)
    if unknown_packet_ids:
        raise ValueError(
            f"packet_ids inexistentes: {sorted(unknown_packet_ids)}"
        )
    packets = [
        row for row in all_packets if row["packet_id"] in pilot_packet_ids
    ]
    previews = read_jsonl(operation_root / "previews_contexto.jsonl")
    approved_previews = {
        row["context_id"]: row
        for row in previews
        if truthy(row.get("approved_for_gpt", False))
    }
    if not approved_previews:
        raise PermissionError(
            "Condição B exige ao menos um preview context_only aprovado humanamente."
        )
    for row in approved_previews.values():
        validate_approved_preview(row)
    preview_groups = {
        (row["source"], row["dataset"], row["record_type"])
        for row in approved_previews.values()
    }
    groups_without_preview = {
        (row["source"], row["dataset"], row["record_type"])
        for row in packets
    }.difference(preview_groups)
    if groups_without_preview:
        raise PermissionError(
            "Todo grupo selecionado para o piloto A/B exige preview aprovado: "
            f"{sorted(groups_without_preview)}"
        )
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY não está disponível no ambiente.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Instale o SDK oficial openai.") from exc
        client = OpenAI()

    prompt = proposal_prompt()
    schema = proposal_json_schema()
    prompt_hash = sha256_text(prompt)
    schema_hash = sha256_json(schema)
    proposal_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for packet in packets:
        group = (packet["source"], packet["dataset"], packet["record_type"])
        contexts = [
            row
            for row in approved_previews.values()
            if (row["source"], row["dataset"], row["record_type"]) == group
        ]
        pair_id = stable_id("ab", packet["packet_id"], model, prompt_hash, schema_hash)
        for condition in ("A", "B"):
            effective = dict(packet)
            effective["context_previews"] = [] if condition == "A" else contexts
            allowed_context_ids = {
                row["context_id"] for row in effective["context_previews"]
            }
            request_input = {
                "instructions": prompt,
                "evidence_packet": effective,
            }
            input_hash = sha256_json(request_input)
            started = time.monotonic()
            status = "error"
            refusal = ""
            error = ""
            response_payload: dict[str, Any] | None = None
            response_text = ""
            usage: Mapping[str, Any] = {}
            resolved_model = ""
            try:
                response = client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": "developer",
                            "content": [
                                {"type": "input_text", "text": prompt},
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": json.dumps(
                                        effective,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                        separators=(",", ":"),
                                    ),
                                }
                            ],
                        },
                    ],
                    reasoning={"effort": reasoning_effort},
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "schema_normalizado_proposal",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                    store=False,
                )
                response_dict = model_dump(response)
                resolved_model = str(response_dict.get("model", ""))
                usage = response_dict.get("usage") or {}
                refusal = extract_refusal(response_dict)
                response_text = extract_output_text(response, response_dict)
                if refusal:
                    status = "refused"
                else:
                    response_payload = json.loads(response_text)
                    validate_proposal(
                        response_payload,
                        effective,
                        allowed_context_ids=allowed_context_ids,
                    )
                    status = "valid"
            except Exception as exc:  # preserve the failure; never fallback
                error = safe_error_message(exc)
            latency = time.monotonic() - started
            usage_flat = flatten_usage(usage)
            cost = calculate_cost(usage_flat, pricing)
            response_hash = sha256_text(response_text) if response_text else ""
            execution_rows.append(
                {
                    "pair_id": pair_id,
                    "packet_id": packet["packet_id"],
                    "condition": condition,
                    "requested_model": model,
                    "resolved_model": resolved_model,
                    "reasoning_effort": reasoning_effort,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": prompt_hash,
                    "schema_version": PROPOSAL_SCHEMA_VERSION,
                    "schema_sha256": schema_hash,
                    "input_sha256": input_hash,
                    "response_sha256": response_hash,
                    "status": status,
                    "refusal": refusal,
                    "error": error,
                    **usage_flat,
                    "latency_seconds": format(latency, ".6f"),
                    "cost_usd": format(cost, ".8f"),
                    "pricing_ref": pricing["pricing_ref"],
                }
            )
            proposal_row = {
                "pair_id": pair_id,
                "packet_id": packet["packet_id"],
                "condition": condition,
                "status": status,
                "raw_response": response_text,
                "validated_response": response_payload,
                "error": error,
                "refusal": refusal,
            }
            proposal_rows.append(proposal_row)
            if response_payload is not None:
                mapping_rows.extend(
                    proposal_to_mapping_rows(
                        response_payload,
                        condition,
                        pair_id=pair_id,
                        packet_id=packet["packet_id"],
                        source=packet["source"],
                        dataset=packet["dataset"],
                        record_type=packet["record_type"],
                    )
                )

    write_jsonl(operation_root / "propostas_gpt.jsonl", proposal_rows)
    write_jsonl(operation_root / "execucao_gpt.jsonl", execution_rows)
    write_csv(
        operation_root / "mapeamentos_propostos.csv",
        mapping_rows,
        MAPPING_FIELDS,
    )
    manifest["gpt_pilot"] = {
        "status": "needs_human_review",
        "requested_model": model,
        "reasoning_effort": reasoning_effort,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "proposal_schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_schema_sha256": schema_hash,
        "calls": len(execution_rows),
        "pilot_packet_ids": sorted(pilot_packet_ids),
        "valid_responses": sum(row["status"] == "valid" for row in execution_rows),
        "refusals": sum(row["status"] == "refused" for row in execution_rows),
        "errors": sum(row["status"] == "error" for row in execution_rows),
    }
    refresh_manifest_outputs(operation_root, manifest)
    write_json(manifest_path, manifest)
    return {
        "manifest": manifest,
        "execution_rows": execution_rows,
        "proposal_rows": proposal_rows,
        "mapping_rows": mapping_rows,
    }


def validate_approved_preview(row: Mapping[str, Any]) -> None:
    if row.get("channel") != "context_only" or row.get("context_only") is not True:
        raise ValueError("Preview aprovado perdeu o rótulo context_only.")
    start = int(row["start"])
    end = int(row["end"])
    full_length = int(row["full_length"])
    preview = str(row["preview"])
    if not (0 <= start < end <= full_length):
        raise ValueError("Posições inválidas em preview aprovado.")
    if end - start > DEFAULT_PREVIEW_LIMIT or len(preview) != end - start:
        raise ValueError("Preview aprovado excede 500 caracteres ou não reconcilia.")
    for name in ("approval_by", "approval_at", "approval_rationale"):
        if not str(row.get(name, "")).strip():
            raise ValueError(f"Preview aprovado sem {name}.")


def evaluate_context_ab(
    operation_root: Path,
    *,
    review_path: Path,
    human_preview_decision: str = "",
) -> list[dict[str, Any]]:
    operation_root = operation_root.resolve()
    executions = read_jsonl(operation_root / "execucao_gpt.jsonl")
    proposals = read_jsonl(operation_root / "propostas_gpt.jsonl")
    mappings = read_csv(operation_root / "mapeamentos_propostos.csv")
    reviews = read_csv(review_path)
    review_by_key: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in reviews:
        key = (row["pair_id"], row["condition"], row["proposal_id"])
        if key in review_by_key:
            raise ValueError(f"Revisão GPT duplicada: {key}")
        review_by_key[key] = row
    expected_review_keys = {
        (row["pair_id"], row["condition"], row["proposal_id"])
        for row in mappings
    }
    unknown_reviews = set(review_by_key).difference(expected_review_keys)
    missing_reviews = expected_review_keys.difference(review_by_key)
    if unknown_reviews:
        raise ValueError(f"Revisões citam propostas inexistentes: {unknown_reviews}")
    if missing_reviews:
        raise ValueError(f"Propostas sem revisão humana: {missing_reviews}")
    response_by_call = {
        (row["pair_id"], row["condition"]): row for row in proposals
    }
    rows: list[dict[str, Any]] = []
    for execution in executions:
        pair_id = str(execution["pair_id"])
        condition = str(execution["condition"])
        call_mappings = [
            row
            for row in mappings
            if row["condition"] == condition
            and row["pair_id"] == pair_id
        ]
        call_reviews = [
            review_by_key[(pair_id, condition, row["proposal_id"])]
            for row in call_mappings
        ]
        rows.append(
            {
                "pair_id": pair_id,
                "packet_id": execution["packet_id"],
                "condition": condition,
                "reviewed_proposals": len(call_reviews),
                "accepted_proposals": sum(
                    truthy(row.get("accepted", "")) for row in call_reviews
                ),
                "unsupported_categories": sum(
                    truthy(row.get("unsupported_category", ""))
                    for row in call_reviews
                ),
                "incorrect_aliases": sum(
                    truthy(row.get("incorrect_alias", "")) for row in call_reviews
                ),
                "insufficient_evidence": sum(
                    truthy(row.get("insufficient_evidence", ""))
                    for row in call_reviews
                )
                + int(
                    (
                        response_by_call.get((pair_id, condition), {}).get(
                            "validated_response"
                        )
                        or {}
                    ).get("status")
                    == "insufficient_evidence"
                ),
                "input_tokens": execution.get("input_tokens", 0),
                "cached_input_tokens": execution.get("cached_input_tokens", 0),
                "output_tokens": execution.get("output_tokens", 0),
                "reasoning_tokens": execution.get("reasoning_tokens", 0),
                "latency_seconds": execution.get("latency_seconds", ""),
                "cost_usd": execution.get("cost_usd", ""),
                "human_preview_decision": human_preview_decision,
            }
        )
    rows.sort(key=lambda row: (row["pair_id"], row["condition"]))
    write_csv(operation_root / "avaliacao_contexto_ab.csv", rows, AB_FIELDS)
    return rows


def proposal_to_mapping_rows(
    response: Mapping[str, Any],
    condition: str,
    *,
    pair_id: str,
    packet_id: str,
    source: str,
    dataset: str,
    record_type: str,
) -> list[dict[str, Any]]:
    rows = []
    for proposal in response.get("proposals", []):
        rows.append(
            {
                "pair_id": pair_id,
                "packet_id": packet_id,
                "proposal_id": proposal["proposal_id"],
                "condition": condition,
                "canonical_field": proposal["canonical_field"],
                "logical_type": proposal["logical_type"],
                "operation": proposal["operation"],
                "source": source,
                "dataset": dataset,
                "record_type": record_type,
                "source_paths_json": json_compact(proposal["source_paths"]),
                "evidence_ids_json": json_compact(proposal["evidence_ids"]),
                "context_refs_json": json_compact(proposal["context_refs"]),
                "api_category_refs_json": json_compact(
                    proposal["api_category_refs"]
                ),
                "possible_aliases_json": json_compact(
                    proposal["possible_aliases"]
                ),
                "caveats_json": json_compact(proposal["caveats"]),
                "needs_human_review": proposal["needs_human_review"],
                "human_decision": "nao_avaliado",
                "human_rationale": "",
            }
        )
    return rows


def write_preparation_outputs(
    *,
    operation_root: Path,
    field_book_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    preview_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
    rejected_rows: Sequence[Mapping[str, Any]],
    ccj_report: str,
    packets: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    paths = {
        "field_book": operation_root / "livro_campos.csv",
        "logical_schema": operation_root / "schema_normalizado.schema.json",
        "mappings": operation_root / "mapeamentos_propostos.csv",
        "aliases": operation_root / "auditoria_aliases.csv",
        "samples": operation_root / "amostras_estruturais.jsonl",
        "previews": operation_root / "previews_contexto.jsonl",
        "gpt_packets": operation_root / "pacotes_gpt.jsonl",
        "gpt_proposals": operation_root / "propostas_gpt.jsonl",
        "gpt_execution": operation_root / "execucao_gpt.jsonl",
        "ab_evaluation": operation_root / "avaliacao_contexto_ab.csv",
        "conflicts": operation_root / "conflitos_tipos.csv",
        "ccj_report": operation_root / "senado_ccj_notas.md",
        "rejected": operation_root / "linhas_rejeitadas.csv",
        "report": operation_root / "relatorio.md",
        "proposal_schema": operation_root / "proposta_gpt.schema.json",
        "prompt": operation_root / "prompt_gpt.md",
    }
    write_csv(paths["field_book"], field_book_rows, FIELD_BOOK_FIELDS)
    write_json(paths["logical_schema"], draft_logical_schema())
    write_csv(paths["mappings"], [], MAPPING_FIELDS)
    write_csv(paths["aliases"], alias_rows, ALIAS_FIELDS)
    write_jsonl(paths["samples"], sample_rows)
    write_jsonl(paths["previews"], preview_rows)
    write_jsonl(paths["gpt_packets"], packets)
    write_jsonl(paths["gpt_proposals"], [])
    write_jsonl(paths["gpt_execution"], [])
    write_csv(paths["ab_evaluation"], [], AB_FIELDS)
    conflict_fields = [
        *[
            "source",
            "dataset",
            "record_type",
            "field_path",
            "technical_types",
            "records_universe",
            "field_absent",
            "present_null",
            "present_empty",
            "present_filled",
            "fill_rate",
            "cardinality",
            "cardinality_method",
            "string_length_min",
            "string_length_median",
            "string_length_max",
            "first_partition",
            "last_partition",
        "type_conflict",
        "safe_examples_json",
        ],
        "decision",
        "proposed_treatment",
        "human_rationale",
    ]
    write_csv(paths["conflicts"], conflict_rows, conflict_fields)
    write_csv(paths["rejected"], rejected_rows, REJECTED_LINE_FIELDS)
    paths["ccj_report"].write_text(ccj_report, encoding="utf-8")
    paths["proposal_schema"].write_text(
        json.dumps(
            proposal_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["prompt"].write_text(
        f"# Prompt GPT-5.6 — {PROMPT_VERSION}\n\n{proposal_prompt()}\n",
        encoding="utf-8",
    )
    paths["report"].write_text(
        render_report(
            field_book_rows=field_book_rows,
            alias_rows=alias_rows,
            sample_rows=sample_rows,
            preview_rows=preview_rows,
            conflict_rows=conflict_rows,
            rejected_rows=rejected_rows,
            packets=packets,
        ),
        encoding="utf-8",
    )
    return paths


def draft_logical_schema() -> dict[str, Any]:
    source_record_coordinate = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "source",
            "dataset",
            "record_type",
            "source_file_path",
            "source_record_number",
            "record_locator_scheme",
        ],
        "properties": {
            "source": {"type": "string", "minLength": 1},
            "dataset": {"type": "string", "minLength": 1},
            "record_type": {"type": "string", "minLength": 1},
            "source_file_path": {
                "type": "string",
                "minLength": 1,
                "description": "Caminho POSIX relativo à raiz raw.",
            },
            "source_record_number": {"type": "integer", "minimum": 1},
            "record_locator_scheme": {
                "type": "string",
                "enum": [
                    "jsonl_physical_line_1_based",
                    "csv_data_row_1_based",
                    "parquet_row_1_based",
                ],
            },
        },
    }
    source_value_coordinate = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "catalog_field_path",
            "source_value_pointer",
            "source_container_shape",
            "source_occurrence_id",
            "array_index_base",
        ],
        "properties": {
            "catalog_field_path": {"type": "string", "minLength": 1},
            "source_value_pointer": {
                "type": "string",
                "description": (
                    "JSON Pointer concreto; posições de arrays começam em zero."
                ),
            },
            "source_container_shape": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["container_path", "shape"],
                    "properties": {
                        "container_path": {"type": "string"},
                        "shape": {
                            "type": "string",
                            "enum": ["object", "array"],
                        },
                    },
                },
            },
            "source_occurrence_id": {
                "type": "string",
                "pattern": "^sha256:[0-9a-f]{64}$",
            },
            "array_index_base": {"const": "zero_based"},
        },
    }
    source_field_state = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "catalog_field_path",
            "presence_state",
            "technical_types",
            "source_occurrence_ids",
        ],
        "properties": {
            "catalog_field_path": {"type": "string", "minLength": 1},
            "presence_state": {
                "type": "string",
                "enum": ["absent", "null", "empty", "filled", "rejected"],
            },
            "technical_types": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "source_occurrence_ids": {
                "type": "array",
                "items": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
                "uniqueItems": True,
            },
        },
    }
    source_value_occurrence = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "coordinate",
            "technical_type",
            "presence_state",
            "original_value",
        ],
        "properties": {
            "coordinate": {"$ref": "#/$defs/source_value_coordinate"},
            "technical_type": {"type": "string", "minLength": 1},
            "presence_state": {
                "type": "string",
                "enum": ["null", "empty", "filled"],
            },
            "original_value": {},
        },
    }
    mapping_rule = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "method",
            "rule_id",
            "rule_version",
            "validation_state",
            "human_decision",
        ],
        "properties": {
            "method": {"const": "python_regra_aprovada"},
            "rule_id": {"type": "string", "minLength": 1},
            "rule_version": {"type": "string", "minLength": 1},
            "validation_state": {
                "type": "string",
                "enum": ["valid", "invalid_preserved", "needs_human_review"],
            },
            "human_decision": {
                "type": "string",
                "enum": ["approved", "revised", "deferred"],
            },
        },
    }
    lineaged_value = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "canonical_field",
            "logical_type",
            "normalized_value",
            "source_occurrence_ids",
            "mapping_rule",
        ],
        "properties": {
            "canonical_field": {
                "type": "string",
                "enum": list(APPROVED_LOGICAL_FIELDS),
            },
            "logical_type": {"type": "string", "minLength": 1},
            "normalized_value": {},
            "source_occurrence_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {
                    "type": "string",
                    "pattern": "^sha256:[0-9a-f]{64}$",
                },
            },
            "mapping_rule": {"$ref": "#/$defs/mapping_rule"},
        },
    }

    def scoped_value(canonical_field: str) -> dict[str, Any]:
        return {
            "allOf": [
                {"$ref": "#/$defs/lineaged_value"},
                {
                    "type": "object",
                    "properties": {
                        "canonical_field": {"const": canonical_field},
                    },
                },
            ]
        }

    def entity_schema(entity_type: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "entity_occurrence_id",
                "entity_type",
                "identifier_namespace",
                "values",
                "source_occurrence_ids",
            ],
            "properties": {
                "entity_occurrence_id": {
                    "type": "string",
                    "minLength": 1,
                },
                "entity_type": {"const": entity_type},
                "identifier_namespace": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "Namespace da fonte e do recurso; IDs não são globais."
                    ),
                },
                "values": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/lineaged_value"},
                },
                "source_occurrence_ids": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {
                        "type": "string",
                        "pattern": "^sha256:[0-9a-f]{64}$",
                    },
                },
            },
        }

    relationship_types = sorted(
        {item["relationship"] for item in APPROVED_CARDINALITIES}
    )
    entities = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            collection: {
                "type": "array",
                "items": entity_schema(entity_type),
            }
            for collection, entity_type in APPROVED_ENTITY_COLLECTIONS
        },
    }
    relationship = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "from_entity_occurrence_id",
            "relationship_type",
            "to_entity_occurrence_id",
            "source_occurrence_ids",
        ],
        "properties": {
            "from_entity_occurrence_id": {"type": "string", "minLength": 1},
            "relationship_type": {
                "type": "string",
                "enum": relationship_types,
            },
            "to_entity_occurrence_id": {"type": "string", "minLength": 1},
            "source_occurrence_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {
                    "type": "string",
                    "pattern": "^sha256:[0-9a-f]{64}$",
                },
            },
        },
    }
    technical_duplications = []
    for decision in APPROVED_TECHNICAL_DUPLICATIONS:
        technical_duplications.append(
            {
                **decision,
                "required_audit": "record_by_record_exact_typed",
                "preserve_all_source_lineages": True,
                "raw_mutation_allowed": False,
                "automatic_priority_allowed": False,
            }
        )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://falandonela.local/schema/normalizado-v3-draft",
        "title": "Contrato lógico do schema normalizado v3",
        "description": (
            "Vocabulário conceitual aprovado em 2026-07-25. Contrato ainda não "
            "operacional: não autoriza por si só Batch, adaptadores ou "
            "materialização."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "source_record_coordinate",
            "source_field_states",
            "source_value_occurrences",
            "normalized",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "source_record_coordinate": {
                "$ref": "#/$defs/source_record_coordinate"
            },
            "source_field_states": {
                "type": "array",
                "items": {"$ref": "#/$defs/source_field_state"},
            },
            "source_value_occurrences": {
                "type": "array",
                "items": {"$ref": "#/$defs/source_value_occurrence"},
            },
            "normalized": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "record_scope",
                    "record_metadata",
                    "entities",
                    "relationships",
                ],
                "properties": {
                    "record_scope": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source", "dataset", "record_type"],
                        "properties": {
                            "source": scoped_value("source"),
                            "dataset": scoped_value("dataset"),
                            "record_type": scoped_value("record_type"),
                        },
                    },
                    "record_metadata": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/lineaged_value"},
                    },
                    "entities": entities,
                    "relationships": {
                        "type": "array",
                        "items": relationship,
                    },
                },
            },
        },
        "$defs": {
            "source_record_coordinate": source_record_coordinate,
            "source_value_coordinate": source_value_coordinate,
            "source_field_state": source_field_state,
            "source_value_occurrence": source_value_occurrence,
            "mapping_rule": mapping_rule,
            "lineaged_value": lineaged_value,
        },
        "x-scientific-gate": (
            "conceptual_vocabulary_approved_operational_g02_pending"
        ),
        "x-distinct-entity-namespaces": [
            "committee_meeting",
            "event",
            "committee_embedded_event",
            "plenary_session",
            "legislative_session",
            "pronouncement",
            "proposition",
            "legislative_matter",
            "legislative_process",
            "document",
            "agenda_item",
            "opinion",
            "taquigraphic_quarter",
            "taquigraphic_marker",
        ],
        "x-cardinalities": list(APPROVED_CARDINALITIES),
        "x-ccj-notas-field-families": [
            ["meeting_part_source", "agenda_item_source"],
            [
                "legislative_matter_observation",
                "rapporteur_assignment_source",
            ],
            [
                "legislative_document_source",
                "document_context_link_source",
            ],
            [
                "committee_embedded_event_source",
                "event_involvement_source",
            ],
            [
                "event_related_matter_link_source",
                "authorship_assignment_source",
            ],
            [
                "meeting_state_observation_source",
                "agenda_item_outcome_source",
            ],
            [
                "taquigraphic_quarter_source",
                "taquigraphic_marker_source",
            ],
            [
                "meeting_arena_assignment_source",
                "meeting_presidency_source",
            ],
            [
                "meeting_video_source",
                "participant_presentation_document_source",
            ],
            [
                "committee_meeting_type_source",
                "meeting_modality_source",
                "legislative_session_context_source",
            ],
        ],
        "x-approved-technical-duplications": technical_duplications,
        "x-index-policy": {
            "source_thematic_metadata": [
                "speech_indexing_source_raw",
                "proposition_subject_source",
            ],
            "temporary_alias_candidate_index": (
                "technical_reproducible_non_semantic"
            ),
            "physical_query_indexes": "deferred",
            "generic_index_field_allowed": False,
        },
        "x-physical-layout": "deferred_to_g03_g05",
        "x-parquet-layout-assumed": False,
        "x-source-policy": "observed_g01_metadata_only",
        "x-automatic-merge": False,
        "x-normalized-record-materialization": False,
    }


def render_report(
    *,
    field_book_rows: Sequence[Mapping[str, Any]],
    alias_rows: Sequence[Mapping[str, Any]],
    sample_rows: Sequence[Mapping[str, Any]],
    preview_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
    rejected_rows: Sequence[Mapping[str, Any]],
    packets: Sequence[Mapping[str, Any]],
) -> str:
    unknown = sum(row["semantic_role"] == "unknown" for row in field_book_rows)
    return f"""# Evidências para o schema normalizado v3

## Estado

Execução técnica concluída; gate científico **needs_review**.

Nenhum registro normalizado foi materializado. Nenhum campo foi descartado,
fundido ou priorizado. Nenhuma proposta GPT foi aplicada.

## Cobertura

| Unidade | Quantidade |
|---|---:|
| caminhos no livro de campos | {len(field_book_rows)} |
| campos com papel semântico ainda não avaliado | {unknown} |
| pares candidatos a alias | {len(alias_rows)} |
| amostras estruturais `evidence` | {len(sample_rows)} |
| previews `context_only` não aprovados por padrão | {len(preview_rows)} |
| conflitos de tipo preservados | {len(conflict_rows)} |
| linhas rejeitadas preservadas | {len(rejected_rows)} |
| pacotes estruturais para piloto | {len(packets)} |

## Limites

- Strings não classificadas humanamente como metadados foram substituídas por
  tipo, comprimento e SHA-256 nas amostras estruturais.
- Os previews literais estão separados e nascem com
  `approved_for_gpt=false`.
- O piloto GPT exige confirmação literal da operação, preço versionado e
  aprovação de previews; a preparação não o executa.
- O schema lógico contém o vocabulário conceitual aprovado em 2026-07-25,
  com entidades, cardinalidades e proveniência por ocorrência.
- A autorização posterior de Batch não autoriza aplicar o schema,
  implementar adaptadores ou materializar registros normalizados.
- Marcadores, oradores, turnos e estruturas internas de texto continuam
  integralmente adiados.
"""


def build_manifest(
    *,
    config: SchemaConfig,
    manifest_g01: Mapping[str, Any],
    fingerprint: str,
    started_at: str,
    records_seen: int,
    paths: Mapping[str, Path],
    counts: Mapping[str, int],
) -> dict[str, Any]:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": "normalized_schema_evidence_v3",
        "operation_id": config.operation_id,
        "execution_status": "succeeded",
        "scientific_gate": "needs_review",
        "started_at": started_at,
        "finished_at": utc_now(),
        "spec_ref": SPEC_REF,
        "code_commit": config.code_commit,
        "runtime": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "openai_sdk": package_version("openai"),
            "pyarrow": package_version("pyarrow"),
        },
        "input": {
            "raw_root": str(config.raw_root),
            "write_policy": "read_only",
            "structural_fingerprint_before": fingerprint,
            "structural_fingerprint_after": fingerprint,
            "inventory_root": str(config.inventory_root),
            "inventory_operation_id": manifest_g01["operation_id"],
            "inventory_manifest_sha256": sha256_file(
                config.inventory_root / "manifest.json"
            ),
            "inventory_outputs": manifest_g01["outputs"],
            "records_read_again": records_seen,
        },
        "config": {
            "metadata_value_limit": config.metadata_value_limit,
            "preview_limit": config.preview_limit,
            "max_json_bytes": config.max_json_bytes,
            "max_alias_candidates_per_group": (
                config.max_alias_candidates_per_group
            ),
            "field_review_path": optional_text(config.field_review_path),
            "manual_alias_path": optional_text(config.manual_alias_path),
            "api_categories_path": optional_text(config.api_categories_path),
            "requested_model": REQUESTED_MODEL,
            "reasoning_effort": DEFAULT_REASONING_EFFORT,
            "prompt_version": PROMPT_VERSION,
            "proposal_schema_version": PROPOSAL_SCHEMA_VERSION,
            "coordinate_conventions": {
                "jsonl_ndjson": "physical_line_number_1_based",
                "json_array": "array_item_ordinal_1_based",
                "json_document": "constant_1",
                "csv": "data_row_ordinal_after_header_1_based",
                "parquet": "row_ordinal_1_based",
            },
        },
        "counts": dict(counts),
        "outputs": [
            artifact_ref(path, operation_root=config.operation_root)
            for path in sorted(paths.values(), key=lambda item: item.name)
        ],
        "invariants": {
            "raw_writes": 0,
            "normalized_records_materialized": 0,
            "automatic_field_merges": 0,
            "automatic_field_drops": 0,
            "gpt_proposals_applied": 0,
            "textual_structure_extractions": 0,
        },
        "next_action": (
            "Revisar papéis de campos, previews, aliases e pacotes; "
            "não abrir G02 ainda."
        ),
    }
    return manifest


def refresh_manifest_outputs(
    operation_root: Path,
    manifest: dict[str, Any],
) -> None:
    output_paths = [
        path
        for path in operation_root.iterdir()
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest["outputs"] = [
        artifact_ref(path, operation_root=operation_root)
        for path in sorted(output_paths, key=lambda item: item.name)
    ]
    manifest["finished_at"] = utc_now()


def load_pricing(path: Path, model: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model") != model:
        raise ValueError("Tabela de preços não corresponde ao modelo solicitado.")
    required = {
        "pricing_ref",
        "as_of",
        "input_per_million",
        "cached_input_per_million",
        "output_per_million",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Tabela de preços incompleta: {sorted(missing)}")
    if not str(payload["pricing_ref"]).strip():
        raise ValueError("pricing_ref é obrigatório.")
    for name in required.difference({"pricing_ref", "as_of"}):
        if Decimal(str(payload[name])) < 0:
            raise ValueError(f"Preço negativo em {name}.")
    return dict(payload)


def flatten_usage(usage: Mapping[str, Any]) -> dict[str, int]:
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(input_details.get("cached_tokens") or 0),
        "cache_write_tokens": int(input_details.get("cache_write_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
    }


def calculate_cost(
    usage: Mapping[str, int],
    pricing: Mapping[str, Any],
) -> Decimal:
    cached = int(usage["cached_input_tokens"])
    input_tokens = int(usage["input_tokens"])
    uncached = max(0, input_tokens - cached)
    output = int(usage["output_tokens"])
    total = (
        Decimal(uncached) * Decimal(str(pricing["input_per_million"]))
        + Decimal(cached) * Decimal(str(pricing["cached_input_per_million"]))
        + Decimal(output) * Decimal(str(pricing["output_per_million"]))
    )
    cache_write_price = pricing.get("cache_write_per_million")
    if cache_write_price is not None:
        total += Decimal(int(usage["cache_write_tokens"])) * Decimal(
            str(cache_write_price)
        )
    return total / Decimal(1_000_000)


def model_dump(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError("Resposta do SDK não oferece model_dump().")


def extract_output_text(response: Any, response_dict: Mapping[str, Any]) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct:
        return direct
    chunks = []
    for item in response_dict.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "".join(chunks)


def extract_refusal(response_dict: Mapping[str, Any]) -> str:
    refusals = []
    for item in response_dict.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "refusal":
                refusals.append(str(content.get("refusal") or ""))
    return "\n".join(value for value in refusals if value)


def safe_error_message(error: Exception) -> str:
    message = f"{type(error).__name__}: {error}"
    secret = os.environ.get("OPENAI_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED_API_KEY]")
    return message


def append_coordinate(values: list[str], coordinate: str, limit: int = 5) -> None:
    if len(values) < limit:
        values.append(coordinate)


def rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "nao_aplicavel"
    return format(Decimal(numerator) / Decimal(denominator), ".8f")


def field_key(
    row: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    return (
        str(row["source"]),
        str(row["dataset"]),
        str(row["record_type"]),
        str(row["field_path"]),
    )


def field_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return field_key(row)


def terminal_key(path: str) -> str:
    escaped = False
    last_dot = -1
    for index, char in enumerate(path):
        if char == "." and not escaped:
            last_dot = index
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return path[last_dot + 1 :].removesuffix("[]")


def path_depth(path: str) -> int:
    return path.count(".") + path.count("[]")


def stable_id(namespace: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{namespace}_{digest}"


def json_compact(value: Any) -> str:
    return json.dumps(
        canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return sha256_text(json_compact(value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim"}


def decimal_or_zero(value: Any) -> Decimal:
    if value in {None, ""}:
        return Decimal("0")
    return Decimal(str(value))


def integer_or_text(value: Any) -> int | str:
    if value in {None, ""}:
        return ""
    return int(value)


def number_or_text(value: Any) -> int | float | str:
    if value in {None, ""}:
        return ""
    parsed = Decimal(str(value))
    if parsed == parsed.to_integral():
        return int(parsed)
    return float(parsed)


def resolve_optional(path: Path | None) -> Path | None:
    return path.expanduser().resolve() if path is not None else None


def optional_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not_installed"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Linha JSONL não é objeto: {path}")
                rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json_compact(row) + "\n")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def artifact_ref(path: Path, *, operation_root: Path) -> dict[str, Any]:
    rows: int | None = None
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = max(0, sum(1 for _ in csv.reader(handle)) - 1)
    elif path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            rows = sum(bool(line.strip()) for line in handle)
    return {
        "name": path.name,
        "relative_path": path.relative_to(operation_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara evidências auditáveis para propor o schema v3; "
            "não materializa dados normalizados."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    prepare.add_argument("--inventory-root", type=Path, required=True)
    prepare.add_argument("--output-base", type=Path, default=DEFAULT_OUTPUT_BASE)
    prepare.add_argument("--operation-id", required=True)
    prepare.add_argument("--code-commit", required=True)
    prepare.add_argument(
        "--expected-inventory-operation-id",
        default=APPROVED_INVENTORY_OPERATION_ID,
    )
    prepare.add_argument(
        "--expected-inventory-manifest-sha256",
        default=APPROVED_INVENTORY_MANIFEST_SHA256,
    )
    prepare.add_argument("--field-review", type=Path)
    prepare.add_argument("--manual-aliases", type=Path)
    prepare.add_argument("--api-categories", type=Path)
    prepare.add_argument(
        "--metadata-value-limit",
        type=int,
        default=DEFAULT_METADATA_VALUE_LIMIT,
    )
    prepare.add_argument("--preview-limit", type=int, default=DEFAULT_PREVIEW_LIMIT)
    prepare.add_argument("--max-json-bytes", type=int, default=DEFAULT_MAX_JSON_BYTES)
    prepare.add_argument("--progress-every-files", type=int, default=100)

    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--operation-root", type=Path, required=True)
    pilot.add_argument("--confirm-operation-id", required=True)
    pilot.add_argument("--pricing-json", type=Path, required=True)
    pilot.add_argument("--packet-id", action="append", required=True)
    pilot.add_argument("--execute-gpt", action="store_true")
    pilot.add_argument("--model", default=REQUESTED_MODEL)
    pilot.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)

    evaluate = subparsers.add_parser("evaluate-ab")
    evaluate.add_argument("--operation-root", type=Path, required=True)
    evaluate.add_argument("--review-csv", type=Path, required=True)
    evaluate.add_argument("--human-preview-decision", default="")

    global_submit = subparsers.add_parser("global-submit")
    global_submit.add_argument(
        "--runtime-dir",
        type=Path,
        default=DEFAULT_GLOBAL_RUNTIME_DIR,
    )
    global_submit.add_argument(
        "--drive-dir",
        type=Path,
        default=DEFAULT_GLOBAL_DRIVE_DIR,
    )
    global_submit.add_argument("--confirm-operation-id", required=True)
    global_submit.add_argument("--execute-gpt", action="store_true")

    global_status = subparsers.add_parser("global-status")
    global_status.add_argument(
        "--drive-dir",
        type=Path,
        default=DEFAULT_GLOBAL_DRIVE_DIR,
    )
    batch_prepare = subparsers.add_parser("batch-prepare")
    batch_prepare.add_argument("--crosswalk-csv", type=Path, required=True)
    batch_prepare.add_argument("--global-proposal-json", type=Path, required=True)
    batch_prepare.add_argument(
        "--operation-root",
        type=Path,
        default=DEFAULT_BATCH_RUNTIME_DIR,
    )
    batch_prepare.add_argument(
        "--operation-id",
        default=BATCH_MAPPING_OPERATION_ID,
    )
    batch_prepare.add_argument(
        "--chunk-size",
        type=int,
        default=BATCH_MAPPING_CHUNK_SIZE,
    )

    batch_count = subparsers.add_parser("batch-count")
    batch_count.add_argument(
        "--operation-root",
        type=Path,
        default=DEFAULT_BATCH_RUNTIME_DIR,
    )

    batch_submit = subparsers.add_parser("batch-submit")
    batch_submit.add_argument(
        "--operation-root",
        type=Path,
        default=DEFAULT_BATCH_RUNTIME_DIR,
    )
    batch_submit.add_argument("--confirm-operation-id", required=True)
    batch_submit.add_argument("--execute-batch", action="store_true")

    batch_status = subparsers.add_parser("batch-status")
    batch_status.add_argument(
        "--operation-root",
        type=Path,
        default=DEFAULT_BATCH_RUNTIME_DIR,
    )

    batch_repair = subparsers.add_parser("batch-repair-prepare")
    batch_repair.add_argument(
        "--source-operation-root",
        type=Path,
        required=True,
    )
    batch_repair.add_argument(
        "--repair-operation-root",
        type=Path,
        required=True,
    )
    batch_repair.add_argument("--operation-id", required=True)
    batch_repair.add_argument(
        "--chunk-size",
        type=int,
        default=BATCH_REPAIR_CHUNK_SIZE,
    )

    batch_merge = subparsers.add_parser("batch-merge")
    batch_merge.add_argument(
        "--operation-root",
        type=Path,
        required=True,
    )
    batch_merge.add_argument(
        "--repair-operation-root",
        type=Path,
        action="append",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        result = prepare_schema_evidence(
            SchemaConfig(
                raw_root=args.raw_root,
                inventory_root=args.inventory_root,
                output_base=args.output_base,
                operation_id=args.operation_id,
                code_commit=args.code_commit,
                expected_inventory_operation_id=(
                    args.expected_inventory_operation_id
                ),
                expected_inventory_manifest_sha256=(
                    args.expected_inventory_manifest_sha256
                ),
                field_review_path=args.field_review,
                manual_alias_path=args.manual_aliases,
                api_categories_path=args.api_categories,
                metadata_value_limit=args.metadata_value_limit,
                preview_limit=args.preview_limit,
                max_json_bytes=args.max_json_bytes,
                progress_every_files=args.progress_every_files,
            )
        )
        print(result["paths"]["report"])
        print("scientific_gate:", result["manifest"]["scientific_gate"])
        return 0
    if args.command == "pilot":
        result = run_gpt_pilot(
            args.operation_root,
            confirm_operation_id=args.confirm_operation_id,
            execute_gpt=args.execute_gpt,
            pricing_path=args.pricing_json,
            pilot_packet_ids=set(args.packet_id),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        print(
            args.operation_root / "execucao_gpt.jsonl",
            "| calls:",
            len(result["execution_rows"]),
        )
        return 0
    if args.command == "evaluate-ab":
        rows = evaluate_context_ab(
            args.operation_root,
            review_path=args.review_csv,
            human_preview_decision=args.human_preview_decision,
        )
        print(
            args.operation_root / "avaliacao_contexto_ab.csv",
            "| rows:",
            len(rows),
        )
        return 0
    if args.command == "global-submit":
        submission = submit_global_proposal(
            args.runtime_dir,
            args.drive_dir,
            confirm_operation_id=args.confirm_operation_id,
            execute_gpt=args.execute_gpt,
        )
        print("response_id:", submission["response_id"])
        print("status inicial:", submission["initial_status"])
        print("tokens exatos:", submission["input_tokens"])
        print(
            "teto estimado (US$):",
            submission["estimated_cost_usd_high"],
        )
        print("reutilizada:", submission["reused"])
        print("recibo:", args.drive_dir / "submission_receipt.json")
        return 0
    if args.command == "global-status":
        status = retrieve_global_proposal(args.drive_dir)
        print("response_id:", status["response_id"])
        print("status:", status["status"])
        if status["status"] in {"queued", "in_progress"}:
            print("Ainda processando; execute global-status mais tarde.")
        elif status["status"] == "completed":
            print("proposta:", status["proposal_path"])
            print("custo estimado real (US$):", status["actual_cost_usd"])
            print("gate científico:", status["scientific_gate"])
        else:
            print("Veja:", args.drive_dir / "status_latest.json")
        return 0
    if args.command == "batch-prepare":
        prepared = prepare_batch_mapping(
            args.crosswalk_csv,
            args.global_proposal_json,
            args.operation_root,
            operation_id=args.operation_id,
            chunk_size=args.chunk_size,
        )
        print("batch_input:", prepared["paths"]["batch_input"])
        print("field_ids:", prepared["manifest"]["counts"]["field_ids"])
        print("requests:", prepared["manifest"]["counts"]["requests"])
        return 0
    if args.command == "batch-count":
        estimate = count_batch_mapping_input_tokens(args.operation_root)
        print("input_tokens:", estimate["input_tokens"])
        print(
            "fits_conservative_queue_limit:",
            estimate["fits_conservative_queue_limit"],
        )
        print(
            "estimated_cost_usd_ceiling_uncached:",
            estimate["estimated_cost_usd_ceiling_uncached"],
        )
        return 0
    if args.command == "batch-submit":
        submission = submit_batch_mapping(
            args.operation_root,
            confirm_operation_id=args.confirm_operation_id,
            execute_batch=args.execute_batch,
        )
        print("batch_id:", submission["batch_id"])
        print("status inicial:", submission["initial_status"])
        print("reutilizada:", submission["reused"])
        return 0
    if args.command == "batch-repair-prepare":
        prepared = prepare_batch_repair(
            args.source_operation_root,
            args.repair_operation_root,
            operation_id=args.operation_id,
            chunk_size=args.chunk_size,
        )
        print("batch_input:", prepared["paths"]["batch_input"])
        print("field_ids:", prepared["manifest"]["counts"]["field_ids"])
        print("requests:", prepared["manifest"]["counts"]["requests"])
        return 0
    if args.command == "batch-merge":
        reconciliation = merge_batch_mapping_attempts(
            args.operation_root,
            args.repair_operation_root,
        )
        print("status:", reconciliation["status"])
        print("field_ids:", reconciliation["field_ids_reconciled"])
        print("missing_field_ids:", reconciliation["missing_field_ids"])
        print(
            "custo total (US$):",
            reconciliation["actual_cost_usd_total"],
        )
        return 0
    status = retrieve_batch_mapping(args.operation_root)
    print("batch_id:", status["batch_id"])
    print("status:", status["status"])
    if status["status"] == "completed_validated":
        print("field_ids:", status["field_ids_reconciled"])
        print("custo real (US$):", status["actual_cost_usd"])
        print("gate científico:", status["scientific_gate"])
    elif status["status"] == "completed_incomplete_coverage":
        print("field_ids:", status["field_ids_reconciled"])
        print("missing_field_ids:", status["missing_field_ids"])
        print("custo real (US$):", status["actual_cost_usd"])
        print("gate científico:", status["scientific_gate"])
    else:
        print("Veja:", args.operation_root / "batch_status_latest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
