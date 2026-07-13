# Validation: atualizacao completa das bases pelo Colab

## Validacao local

- Rodar a suite de testes sem requisicoes historicas reais.
- Cobrir o pipeline compartilhado de discursos com `siglaCasa=SF` e
  `siglaCasa=CN`.
- Confirmar texto integral, fallback de notas, `transcription_queue`, falha de
  item retomavel e idempotencia de `--resume`.
- Validar todos os notebooks com `nbformat`.
- Fazer parse AST do codigo concatenado de cada celula.
- Confirmar que a primeira celula de codigo de cada caderno monta o Drive.

## Auditoria inicial

O caderno 00 deve confirmar e registrar:

- raiz ativa `/content/drive/MyDrive/falando_nela/data`;
- corte historico textual `2026-05-28` e corte dos apartes `2026-05-18`;
- autosave incompleto de `prod-historico-camara-plenario`;
- manifests com erro de `prod-historico-senado-ccj` e
  `prod-historico-camara-ccjc`;
- fotografia anterior com 407.084 textos e seis Parquets.

Ausencia ou divergencia deve gerar aviso visivel antes da gravacao da
configuracao, sem apagar dados.

## Validacao de cada faixa

- O manifest final existe, usa `mode=prod`, `sample=false` e o `run_id` certo.
- `data_inicio` e `data_fim` correspondem a configuracao ou a retomada
  historica declarada.
- Status final e `completed`.
- `unresolved_failed_partitions`, calculado como falhas menos conclusoes
  posteriores do mesmo run, e vazio.
- Logs e autosave continuam acessiveis e as ultimas linhas sao exibidas.
- JSONLs tocados pela faixa sao parseaveis.

## Congresso

- O smoke de `2000-03-01` a `2000-03-31` produz pelo menos um
  `pronunciamento_texto` com `source=senado`,
  `dataset=congresso_discursos`, `CodigoPronunciamento` e `texto` nao vazio.
- O request mensal preserva `siglaCasa=CN`.
- O backfill usa somente particoes mensais a partir de `1996-05-01`.
- A segunda execucao com o mesmo `run_id --resume` nao duplica linhas.

## Processamento final

- O manifest textual registra os nove `run_id`s incrementais/recuperados e o
  backfill textual do Congresso entre suas entradas observadas.
- `dataset_version` e sempre `v1`, `texto` e nao vazio e `texto_id` e unico.
- Existem sete Parquets, cada um contendo somente o `source/dataset` indicado
  no nome.
- A soma de linhas dos Parquets coincide com os `texto_id`s distintos.
- Contagens anteriores nao diminuem sem justificativa registrada no resumo do
  ciclo.
- `parlamentares/v1` e `apartes_parlamentares/v1` possuem JSONL, Parquet e
  manifest; as auditorias de join nao inferem genero por nome.
- O manifest de samples contem as sete bases textuais e os ZIPs preservam o
  schema v1.

## Inspecao no Gradio

- O app lista os sete Parquets atualizados.
- Filtros encontram registros entre `2026-05-01` e `2026-07-13` quando a fonte
  possuir atividade no periodo.
- A tabela compacta omite `texto`.
- Um `texto_id` novo abre texto integral e metadados.

## Fechamento

O caderno 06 deve gravar
`operations/atualizacao/ciclos/20260713/summary.json`, com:

- configuracao efetiva;
- status e contagens de cada coleta;
- caminhos dos manifests processados arquivados;
- comparacao com a fotografia anterior;
- resultado dos gates e checklist manual do Gradio.
