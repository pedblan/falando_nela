# Plano: apartes_parlamentares/v1

## Objetivo

Criar uma tabela relacional processada para contar apartes por ano e cruzar
essas contagens com metadados oficiais de parlamentares, especialmente genero,
partido e UF.

A unidade analitica inicial e a relacao oficial
`aparteante -> discurso/pronunciamento`, nao cada fala individual de aparte.
Essa tabela e independente de `textos_parlamentares/v1`.

## Entradas

- `raw/senado/plenario_apartes/metadata/*.jsonl`.
- `raw/camara/plenario_apartes/metadata/*.jsonl`.
- `processed/parlamentares/v1/parlamentares_periodos.jsonl` ou Parquet
  equivalente, quando disponivel.
- Opcionalmente, `processed/textos_parlamentares/v1` para marcar se o discurso
  ou pronunciamento ja possui texto processado.

## Fluxo

1. Ler os registros raw de apartes das duas casas.
2. Senado: explodir `Apartes.Aparte` em uma linha por aparte retornado pelo
   endpoint `senador/{codigo}/apartes`.
3. Camara: parsear paginas do Sitaq e criar uma linha por resultado de busca
   associado ao `txAparteante` consultado.
4. Criar IDs deterministico para cada relacao.
5. Deduplicar por fonte, data/sessao/discurso e aparteante.
6. Enriquecer orador e aparteante com `parlamentares/v1` por `source`,
   `parlamentar_id` e data.
7. Quando a Camara nao tiver match unico para o aparteante consultado, manter o
   nome e marcar `match_status`.
8. Gerar Parquet unificado e relatorios anuais de contagem.

## Saidas

- `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`.
- `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`.
- `processed/audits/apartes_parlamentares/{run_id}/contagens_anuais.csv`.
- `processed/audits/apartes_parlamentares/{run_id}/match_status.csv`.
- `processed/audits/apartes_parlamentares/{run_id}/manifest.json`.

## Campos principais

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

## Regras analiticas

- `genero` nunca deve ser inferido por nome, foto, tratamento, pronome ou
  texto.
- Partido e UF devem vir da fonte do proprio aparte quando presentes, ou de
  `parlamentares/v1` por data.
- A contagem anual default usa uma linha por relacao deduplicada
  `aparteante -> discurso/pronunciamento`.
- `pending_text_match` nao bloqueia a contagem anual de apartes; indica apenas
  que o corpus textual correspondente ainda nao foi encontrado.
- O backfill historico de discursos pode melhorar joins, mas nao e requisito
  para produzir esta tabela.

## Fora do escopo atual

- Nao criar `texto` para apartes.
- Nao segmentar apartes no texto integral de discursos.
- Nao alterar o schema de `textos_parlamentares/v1`.
