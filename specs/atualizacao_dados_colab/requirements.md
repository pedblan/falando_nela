# Requirements: atualizacao completa das bases pelo Colab

## Ciclo inicial

- `cycle_id`: `20260713`.
- Inicio com sobreposicao: `2026-05-01`.
- Fim inclusivo: `2026-07-13`.
- Raiz de producao:
  `/content/drive/MyDrive/falando_nela/data`.
- Somente um ciclo pode estar ativo por vez.

## Contrato de configuracao

O caderno 00 deve gravar:

```text
operations/atualizacao/active.json
operations/atualizacao/ciclos/20260713/config.json
```

Os dois arquivos devem ter o mesmo conteudo e incluir:

- `schema_version = 1`;
- `cycle_id`, `data_inicio`, `data_fim`, `data_root` e `created_at`;
- `historical_recoveries`, com modulo, janela e `run_id` de cada retomada;
- `run_ids`, com todos os identificadores de coleta e processamento;
- `expected_text_datasets`, `expected_apartes_sources` e
  `expected_processed_outputs`.

Os demais cadernos devem ler `active.json`, recusar outro `cycle_id` e nunca
derivar datas do relogio durante a execucao.

## Run IDs

Retomadas existentes:

- `prod-historico-senado-ccj`;
- `prod-historico-camara-ccjc`;
- `prod-historico-camara-plenario`.

Backfill textual novo:

- `prod-historico-senado-congresso-textos-v1`, de `1996-05-01` a
  `2026-07-13`.

Atualizacoes incrementais:

- `prod-atualizacao-20260713-parlamentares`;
- `prod-atualizacao-20260713-senado-plenario`;
- `prod-atualizacao-20260713-senado-ccj`;
- `prod-atualizacao-20260713-senado-pareceres-pec`;
- `prod-atualizacao-20260713-senado-plenario-apartes`;
- `prod-atualizacao-20260713-camara-ccjc`;
- `prod-atualizacao-20260713-camara-pareceres-pec`;
- `prod-atualizacao-20260713-camara-plenario-apartes`;
- `prod-atualizacao-20260713-camara-plenario`.

Processamento:

- `processed-parlamentares-v1-current`;
- `processed-textos-v1-current`;
- `parquet-textos-v1-current`;
- `processed-apartes-parlamentares-v1-current`;
- `parlamentares-join-20260713`;
- `samples-textos-v1-20260713`.

## Regras dos cadernos

- A primeira celula executavel monta o Google Drive.
- Clone/pull, instalacao e imports do projeto ocorrem somente depois do mount.
- Toda coleta usa `--mode prod --resume --no-sample`, datas explicitas e um
  `run_id` da configuracao.
- Na retomada `prod-historico-senado-ccj`, erro de transporte após os retries
  da agenda mensal deve acionar subdivisao recursiva da janela; o mesmo
  `run_id`, o raw cumulativo e o checkpoint existente devem ser preservados.
- Celulas de producao ficam protegidas por flags `RODAR_* = False` por default.
- Processos longos transmitem stdout, usam `check=False` e preservam a etapa de
  inspecao mesmo quando retornam codigo diferente de zero.
- O caderno 01 deve terminar antes das faixas 02 a 05.
- O caderno 01 deve bloquear as faixas seguintes se algum mandato tiver
  `data_fim < data_inicio` ou algum periodo tiver
  `vigencia_fim < vigencia_inicio`.
- Faixas 02 a 05 podem rodar simultaneamente, pois nao compartilham datasets.
- Duas instancias do mesmo dataset nunca podem rodar ao mesmo tempo.

## Congresso textual

- O endpoint mensal continua sendo
  `/dadosabertos/plenario/lista/discursos/{inicio}/{fim}.json` com
  `siglaCasa=CN` e `v=4`.
- A lista mensal permanece em `metadata/`.
- Cada `CodigoPronunciamento` deve usar o pipeline compartilhado do Senado:
  texto integral, notas da sessao como fallback e fila de transcricao.
- Registros com texto ou ausencia auditavel usam `record_type` igual a
  `pronunciamento_texto` na particao mensal.
- Casos sem texto e com fonte audiovisual usam tambem `transcription_queue`.
- Falha inesperada de um pronunciamento deixa a particao como falha; a retomada
  pula itens ja gravados e tenta novamente apenas os faltantes.

## Gates de processamento

O caderno 06 deve recusar a execucao se:

- faltar `manifests/{run_id}.json` de qualquer coleta obrigatoria;
- algum manifest tiver status diferente de `completed`;
- a janela do manifest divergir da configuracao;
- houver particao em `failed_partitions` que nao apareca posteriormente em
  `completed_partitions` para o mesmo `run_id`;
- `parlamentares/v1` do ciclo nao existir.

## Fotografia current

- A normalizacao textual le todo o raw e grava uma fotografia completa com
  `processed-textos-v1-current --overwrite`.
- O processamento de parlamentares e apartes substitui suas tabelas canonicas
  com `--overwrite`.
- Os sete Parquets esperados sao Senado Plenario, Congresso, CCJ e pareceres de
  PEC; Camara Plenario, CCJC e pareceres de PEC.
- Depois de cada etapa `current`, seu manifest deve ser copiado para o
  diretorio do ciclo antes que uma atualizacao futura possa sobrescreve-lo.
- Samples sao geradas a partir da base completa do Drive, nunca de samples
  locais.
