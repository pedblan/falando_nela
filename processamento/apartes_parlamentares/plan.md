# Plano: apartes_parlamentares/v1

## Objetivo

Criar uma tabela relacional processada para contar apartes por ano e cruzar
essas relacoes com metadados oficiais de parlamentares, especialmente genero,
partido e UF.

A unidade analitica inicial e a relacao oficial
`aparteante -> discurso/pronunciamento`, nao cada intervencao oral individual.
Essa tabela e independente de `textos_parlamentares/v1` e nao contem campo
`texto`.

## Entradas

- `raw/senado/plenario_apartes/metadata/*.jsonl`.
- `raw/camara/plenario_apartes/metadata/*.jsonl`.
- `processed/parlamentares/v1/parlamentares_periodos.jsonl` ou Parquet
  equivalente, quando disponivel.

Os raws de apartes podem conter registros de descoberta e preflight:

- Senado:
  - `senador_apartes_year_probe`;
  - `senador_apartes_quarter_probe`;
  - `senador_apartes_metadata`.
- Camara:
  - `sitaq_apartes_year_probe`;
  - `sitaq_apartes_quarter_probe`;
  - `sitaq_apartes_search_page`.

Somente os registros mensais finais (`senador_apartes_metadata` e
`sitaq_apartes_search_page`) viram linhas analiticas. Probes anuais e
trimestrais entram no manifest como `probe_record`, para evitar duplicacao de
relacoes.

## Fluxo

1. Ler os raws em `metadata/` das duas casas, com filtros opcionais por
   `source` e `raw_run_id`.
2. Ignorar registros de descoberta e probes no material analitico, mantendo as
   contagens no manifest.
3. Senado: explodir `Apartes.Aparte` em uma linha por aparte retornado pelo
   endpoint `senador/{codigo}/apartes`.
4. Camara: criar uma linha por item em `chaves_extraidas` das paginas mensais
   do Sitaq associadas ao `txAparteante` consultado.
5. Criar `aparte_id` deterministico por fonte, data, discurso/sessao e
   aparteante.
6. Deduplicar linhas por `aparte_id`, registrando `duplicate_aparte_id`.
7. Enriquecer orador e aparteante com `parlamentares/v1` por `source`,
   `parlamentar_id` e data.
8. Na Camara, quando so houver nome, tentar match unico por nome normalizado e
   data; se nao for unico, preservar nome e marcar `name_only` ou `ambiguous`.
9. Gravar JSONL, Parquet, manifest e auditorias anuais.

## Implementacao

- Modulo: `processamento.apartes_parlamentares`.
- Entrada operacional Colab:
  `notebooks/processamento/geracao_apartes_parlamentares_colab.ipynb`.
- Comando base:

```bash
python -m processamento.apartes_parlamentares \
  --mode prod \
  --data-root /content/drive/MyDrive/falando_nela/data \
  --run-id processed-apartes-parlamentares-v1-YYYYMMDD \
  --overwrite
```

## Saidas

- `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`.
- `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`.
- `processed/manifests/{run_id}-apartes-parlamentares.json`.
- `processed/audits/apartes_parlamentares/{run_id}/contagens_anuais.csv`.
- `processed/audits/apartes_parlamentares/{run_id}/match_status.csv`.
- `processed/audits/apartes_parlamentares/{run_id}/cobertura_parlamentares.csv`.
- `processed/audits/apartes_parlamentares/{run_id}/manifest.json`.

## Campos Principais

- `aparte_id`;
- `dataset_version`;
- `source`;
- `casa`;
- `data`, `ano`, `mes`;
- `pronunciamento_id`;
- `discurso_chave`;
- `sessao_id`;
- `tipo_sessao`;
- `fase_sessao`;
- `orador_id`, `orador_nome`, `orador_genero`, `orador_partido`,
  `orador_uf`;
- `aparteante_id`, `aparteante_nome`, `aparteante_genero`,
  `aparteante_partido`, `aparteante_uf`;
- `url_texto`, `url_diario`, `url_origem`;
- `match_status`;
- `raw_run_id`, `raw_record_type`, `raw_source_id`, `raw_partition`,
  `raw_collected_at`, `raw_checksum`, `raw_path`, `raw_response_url`.

## Regras Analiticas

- `genero` nunca deve ser inferido por nome, foto, tratamento, pronome ou
  texto.
- Partido e UF devem vir de `parlamentares/v1` quando houver match temporal; no
  Senado, campos oficiais do proprio aparte podem servir como fallback para
  partido/UF, nunca para genero.
- A contagem anual default usa uma linha por relacao deduplicada
  `aparteante -> discurso/pronunciamento`.
- O backfill historico de discursos pode melhorar joins textuais no futuro, mas
  nao e requisito para produzir esta tabela.

## Fora Do Escopo Atual

- Nao criar `texto` para apartes.
- Nao segmentar apartes no texto integral de discursos.
- Nao alterar o schema de `textos_parlamentares/v1`.
- Nao usar regex sobre discurso integral para descobrir apartes nesta etapa.
