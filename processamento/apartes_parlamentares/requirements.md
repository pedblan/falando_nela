# Requirements: apartes_parlamentares/v1

## Objetivo

Normalizar os raws `senado/plenario_apartes` e `camara/plenario_apartes` em
uma tabela relacional para analises de contagem anual e cruzamento com
`parlamentares/v1`.

## Interface CLI

- `--mode dev|prod`.
- `--data-root CAMINHO`.
- `--run-id ID`.
- `--raw-run-id ID`, repetivel, para restringir raws de entrada.
- `--source camara|senado|all`.
- `--overwrite`.
- `--limit-records N`, para validacoes locais.

## Entradas

- Raws:
  - `raw/senado/plenario_apartes/metadata/{run_id}.jsonl`;
  - `raw/camara/plenario_apartes/metadata/{run_id}.jsonl`.
- Metadados de parlamentares:
  - `processed/parlamentares/v1/parlamentares_periodos.jsonl`; ou
  - `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet`.
- Textos processados sao entrada opcional apenas para preencher
  `pending_text_match` ou `matched_text`.

## Saidas

- JSONL:
  `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`.
- Parquet:
  `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`.
- Manifest:
  `processed/manifests/{run_id}-apartes-parlamentares.json`.
- Auditorias:
  `processed/audits/apartes_parlamentares/{run_id}/`.

## Schema minimo

`apartes_parlamentares/v1` deve conter:

- `aparte_id`;
- `dataset_version`;
- `source`;
- `casa`;
- `data`;
- `ano`;
- `mes`;
- `pronunciamento_id`;
- `discurso_chave`;
- `sessao_id`;
- `tipo_sessao`;
- `fase_sessao`;
- `orador_id`;
- `orador_nome`;
- `orador_genero`;
- `orador_partido`;
- `orador_uf`;
- `aparteante_id`;
- `aparteante_nome`;
- `aparteante_genero`;
- `aparteante_partido`;
- `aparteante_uf`;
- `url_texto`;
- `url_diario`;
- `url_origem`;
- `match_status`;
- `raw_run_id`;
- `raw_record_type`;
- `raw_source_id`;
- `raw_partition`;
- `raw_collected_at`;
- `raw_checksum`;
- `raw_path`;
- `raw_response_url`.

## IDs e deduplicacao

- `aparte_id` deve ser deterministico e estavel.
- Senado: deduplicar por `source`, `pronunciamento_id` e
  `aparteante_id`.
- Camara: deduplicar por `source`, `discurso_chave` e
  `aparteante_id` quando houver ID; quando nao houver ID, usar
  `aparteante_nome` normalizado e manter `match_status=name_only`.
- Duplicatas exatas entre raw runs devem aparecer no manifest como
  `duplicate_aparte_id`.

## Match com parlamentares

- O match oficial usa `source`, `parlamentar_id` e `data` dentro do intervalo
  de `parlamentares_periodos`.
- `genero`, partido e UF devem vir de `parlamentares/v1` quando houver match.
- Para a Camara, se o raw tiver somente nome:
  - match unico por nome e data pode preencher `aparteante_id`;
  - multiplos candidatos geram `match_status=ambiguous`;
  - nenhum candidato gera `match_status=name_only`.
- Nao inferir genero por nome em nenhuma circunstancia.

## Valores de match_status

- `matched`: orador e aparteante com match suficiente para analise por
  parlamentares.
- `name_only`: aparteante ou orador preservado apenas por nome.
- `ambiguous`: mais de um parlamentar possivel.
- `pending_text_match`: relacao de aparte criada, mas discurso textual ainda
  nao encontrado em `textos_parlamentares/v1`.
- `missing_date`: registro sem data suficiente para juncao temporal.

## Relatorios anuais

Gerar pelo menos:

- `contagens_anuais.csv`: contagens por `source`, `ano`,
  `aparteante_genero`, `aparteante_partido`, `aparteante_uf`.
- `match_status.csv`: contagens por `source`, `ano` e `match_status`.
- `cobertura_parlamentares.csv`: cobertura de match para orador e aparteante.

## Manifest

O manifest deve registrar:

- raws lidos;
- raw run IDs observados;
- filtros aplicados;
- contagens de entrada por fonte/record_type;
- linhas processadas por fonte;
- deduplicacoes;
- skipped por motivo;
- caminho dos JSONLs, Parquets e auditorias gerados.
