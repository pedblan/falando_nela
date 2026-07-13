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

Excecoes posteriores ao inicio do ciclo devem ser aditivas e registradas em
`operations/atualizacao/ciclos/20260713/deferred_collections.json`; nao devem
reescrever um manifest `completed_with_errors` como `completed`.

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
- Na retomada `prod-historico-senado-ccj`, erro de transporte ou HTTP
  `500`, `502`, `503` ou `504` apos os retries da agenda JSON deve acionar
  subdivisao recursiva da janela.
- Se a falha persistir no JSON de um dia, a retomada deve usar a agenda XML
  diaria, higienizar somente controles invalidos para XML 1.0 e preservar no
  raw e no log a proveniencia do fallback. O mesmo `run_id`, o raw cumulativo
  e o checkpoint existente devem ser preservados.
- Celulas de producao ficam protegidas por flags `RODAR_* = False` por default.
- Processos longos transmitem stdout, usam `check=False` e preservam a etapa de
  inspecao mesmo quando retornam codigo diferente de zero.
- O caderno 01 deve terminar antes das faixas 02 a 05.
- O caderno 01 deve bloquear as faixas seguintes se algum mandato tiver
  `data_fim < data_inicio` ou algum periodo tiver
  `vigencia_fim < vigencia_inicio`.
- Faixas 02 a 05 podem rodar simultaneamente, pois nao compartilham datasets.
- Duas instancias do mesmo dataset nunca podem rodar ao mesmo tempo.
- O caderno 05 deve copiar somente
  `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet` para o
  disco local efemero do runtime e passa-lo explicitamente ao coletor; todas
  as saidas permanecem na raiz ativa do Drive.
- Antes da recuperacao historica do Plenario da Camara, o caderno deve cruzar
  checkpoint e log. Se houver particao iniciada sem conclusao, deve manter o
  scan de registros do `run_id`, restrito aos anos parciais quando o escopo
  puder ser provado; somente fronteira limpa pode usar
  `--skip-existing-record-scan`. Divergencia deve provocar scan integral.
- A retomada do Plenario da Camara deve imprimir progresso durante o scan do
  raw e durante a particao, com heartbeat a cada 25 deputados no autosave.
- O caderno 02 pode adiar somente `senado_ccj_historico`, somente quando o
  manifest mantiver `completed_with_errors` e a lista exata de falhas nao
  resolvidas for `["2015-05"]`. A excecao exige confirmacao do `cycle_id`,
  `analysis_excluded=true`, motivo e `follow_up`.
- Depois do registro, o caderno 02 nao deve executar novamente a recuperacao
  historica adiada e deve prosseguir com Plenario, CCJ incremental, pareceres
  de PEC e apartes do Senado. Falhas dessas outras coletas continuam
  bloqueantes.

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

Excecao: uma coleta pode ser aceita como `deferred`, sem ser considerada
completa, quando houver entrada correspondente em `deferred_collections.json`
e `run_id`, status e conjunto de particoes nao resolvidas coincidirem
exatamente. O caderno deve expor separadamente `COLLECTION_GATE_OK=true` e
`STRICT_COLLECTION_GATE_OK=false`, arquivando as chaves adiadas. Qualquer
divergencia continua bloqueante.

## Fotografia current

- A normalizacao textual le todo o raw e grava uma fotografia completa com
  `processed-textos-v1-current --overwrite`.
- O processamento de parlamentares e apartes substitui suas tabelas canonicas
  com `--overwrite`.
- Os sete Parquets esperados sao Senado Plenario, Congresso, CCJ e pareceres de
  PEC; Camara Plenario, CCJC e pareceres de PEC.
- Neste ciclo, o Parquet da CCJ pode ser regenerado com a cobertura raw
  disponivel, mas deve ser excluido do artigo corrente e nao pode ser descrito
  como historicamente completo enquanto `2015-05` estiver adiado.
- Depois de cada etapa `current`, seu manifest deve ser copiado para o
  diretorio do ciclo antes que uma atualizacao futura possa sobrescreve-lo.
- Samples sao geradas a partir da base completa do Drive, nunca de samples
  locais.
