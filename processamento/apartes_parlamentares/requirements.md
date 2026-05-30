# Requirements: apartes_parlamentares/v1

## Objetivo

Normalizar os raws `senado/plenario_apartes` e `camara/plenario_apartes` em uma
tabela relacional para analises de contagem anual e cruzamento com
`parlamentares/v1`.

## Interface CLI

O modulo deve rodar com:

```bash
python -m processamento.apartes_parlamentares
```

Argumentos obrigatorios/aceitos:

- `--mode dev|prod`.
- `--data-root CAMINHO`.
- `--run-id ID`.
- `--raw-run-id ID`, repetivel, para restringir raws de entrada.
- `--source camara|senado|all`.
- `--overwrite`.
- `--limit-records N`, para validacoes locais.

Em `--mode prod`, `--data-root` ou `FALANDO_NELA_DATA_ROOT` deve apontar para
diretorio externo ao repositorio.

## Notebook Operacional

Deve existir um caderno Colab em:

```text
notebooks/processamento/geracao_apartes_parlamentares_colab.ipynb
```

O caderno deve:

- montar o Google Drive na primeira celula executavel;
- definir `FALANDO_NELA_DATA_ROOT`;
- clonar/atualizar o repositorio e instalar `requirements.txt`;
- conferir raws de Senado e Camara em `metadata/`;
- conferir a existencia de `parlamentares/v1`, sem bloquear quando ausente;
- chamar `processamento.apartes_parlamentares.process_apartes_data_root`;
- validar schema, unicidade de `aparte_id`, ausencia de `texto`, Parquet e
  auditorias.

## Entradas

- Raws:
  - `raw/senado/plenario_apartes/metadata/{run_id}.jsonl`;
  - `raw/camara/plenario_apartes/metadata/{run_id}.jsonl`.
- Metadados de parlamentares:
  - `processed/parlamentares/v1/parlamentares_periodos.jsonl`; ou
  - `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet`.

## Record Types

Geram linhas:

- `senador_apartes_metadata`;
- `sitaq_apartes_search_page`.

Nao geram linhas, mas entram no manifest:

- `senador_apartes_year_probe`;
- `senador_apartes_quarter_probe`;
- `sitaq_apartes_year_probe`;
- `sitaq_apartes_quarter_probe`;
- registros de descoberta de parlamentares usados pelos coletores.

## Saidas

- JSONL:
  `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`.
- Parquet:
  `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`.
- Manifest:
  `processed/manifests/{run_id}-apartes-parlamentares.json`.
- Auditorias:
  `processed/audits/apartes_parlamentares/{run_id}/`.

## Schema Minimo

`apartes_parlamentares/v1` deve conter exatamente os campos minimos:

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

## IDs E Deduplicacao

- `aparte_id` deve ser deterministico e estavel.
- Senado: deduplicar por relacao equivalente a `source`, data,
  `pronunciamento_id`, `sessao_id` e `aparteante_id`.
- Camara: deduplicar por relacao equivalente a `source`, data,
  `discurso_chave`, `sessao_id` e `aparteante_id`; quando nao houver ID, usar
  `aparteante_nome` normalizado.
- Duplicatas exatas entre raw runs ou paginas devem aparecer no manifest como
  `duplicate_aparte_id`.

## Match Com Parlamentares

- O match oficial usa `source`, `parlamentar_id` e `data` dentro do intervalo
  de `parlamentares_periodos`.
- `genero` deve vir somente de `parlamentares/v1`.
- Partido e UF devem vir de `parlamentares/v1` quando houver match; fallback de
  partido/UF pode usar campos oficiais do raw do Senado.
- Para a Camara, se o raw tiver somente nome:
  - match unico por nome e data pode preencher `aparteante_id`;
  - multiplos candidatos geram `match_status=ambiguous`;
  - nenhum candidato gera `match_status=name_only`.
- Nao inferir genero por nome em nenhuma circunstancia.

## Valores De match_status

- `matched`: relacao com identificador suficiente para a analise relacional.
- `name_only`: parlamentar preservado apenas por nome.
- `ambiguous`: mais de um parlamentar possivel no match por nome.
- `missing_date`: registro sem data suficiente para juncao temporal.
- `pending_text_match`: reservado para etapa futura em que a tabela for cruzada
  com `textos_parlamentares/v1`; nao e exigido pela geracao inicial.

## Relatorios Anuais

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
- skipped por motivo, incluindo `probe_record`;
- caminhos dos JSONLs, Parquets e auditorias gerados;
- resumo do indice de `parlamentares/v1`.
