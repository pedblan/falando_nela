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
- Status final e `completed`, salvo excecao exata registrada para uma base
  excluida da analise corrente.
- `unresolved_failed_partitions`, calculado como falhas menos conclusoes
  posteriores do mesmo run, e vazio, salvo a lista exata da excecao auditada.
- Logs e autosave continuam acessiveis e as ultimas linhas sao exibidas.
- JSONLs tocados pela faixa sao parseaveis.
- A conclusao estrita de `prod-historico-senado-ccj` continua exigindo que as
  particoes `2013-10` e `2015-05` aparecam em `completed_partitions`; suas
  entradas historicas em `failed_partitions` podem permanecer quando o mesmo
  run registrar conclusao posterior.
- O log da recuperacao pode conter `agenda_range_split`; cada evento deve
  descrever metades contiguas e sem sobreposicao da janela que falhou.
- Para os dias problematicos alcancados pela subdivisao, o log pode conter
  `agenda_xml_fallback`; o `agenda_periodo` correspondente deve preservar o
  endpoint `.xml`, `Content-Type`, periodo de um dia e payload convertido.
- Os casos observados em `2013-10-18` e `2015-05-25` devem ser resolvidos pelo
  XML diario mesmo quando ele nao contiver reuniao da CCJ; ausencia de CCJ e
  resultado valido, nao falha de particao.
- Se JSON e XML falharem para o mesmo dia, a particao deve continuar em
  `unresolved_failed_partitions` e, por default, bloquear o processamento
  final; a unica flexibilizacao e a excecao auditada descrita abaixo.
- Estado auditado em `2026-07-13`: `2013-10` esta concluida e apenas
  `2015-05` permanece nao resolvida; o manifest tem
  `status=completed_with_errors` e `errors=1`.
- Se a analise corrente excluir a CCJ, o caderno 02 pode gravar a excecao
  somente para `senado_ccj_historico` e `["2015-05"]`. A validacao deve falhar
  se aparecer outra particao, outro status, outro `run_id` ou manifest ausente.
- Com a excecao registrada, a validacao da faixa deve imprimir
  `deferred=True` para a recuperacao historica e continuar exigindo
  `completed` para as quatro coletas seguintes do Senado.
- Para `prod-historico-camara-plenario`, o preflight deve detectar a particao
  parcial `1999` observada no log e registrar
  `existing_record_scan=filtered`, `existing_record_scan_years=["1999"]` na
  primeira retomada. O stdout deve progredir durante a indexacao e depois
  emitir `deputy_progress`.
- Depois que nenhuma particao da janela estiver aberta, uma nova retomada pode
  usar o atalho; checkpoint e log divergentes devem faze-lo falhar antes de
  qualquer escrita raw.
- O caminho registrado em `parlamentares_periodos_path` deve apontar para
  `/content/falando_nela_runtime/parlamentares_periodos.parquet`, enquanto
  `output_dir` permanece `/content/drive/MyDrive/falando_nela/data`.

## Gate de parlamentares

- Mudancas da Camara no mesmo dia sao consolidadas pelo ultimo `dataHora`;
  timestamps identicos respeitam a ultima ocorrencia da resposta oficial.
- `mandatos` nao contem `data_fim < data_inicio` e
  `parlamentares_periodos` nao contem `vigencia_fim < vigencia_inicio`.
- JSONL e Parquet preservam o schema `parlamentares/v1` e a proveniencia do
  estado diario escolhido.
- Os cadernos 02 a 05 permanecem bloqueados ate aparecer
  `Gate aprovado: ... periodos de mandato` no caderno 01.

## Congresso

- O smoke de `2000-03-01` a `2000-03-31` produz pelo menos um
  `pronunciamento_texto` com `source=senado`,
  `dataset=congresso_discursos`, `CodigoPronunciamento` e `texto` nao vazio.
- O request mensal preserva `siglaCasa=CN`.
- O backfill usa somente particoes mensais a partir de `1996-05-01`.
- A segunda execucao com o mesmo `run_id --resume` nao duplica linhas.

## Processamento final

- O gate aceito deve mostrar `COLLECTION_GATE_OK=True`,
  `STRICT_COLLECTION_GATE_OK=False` e
  `DEFERRED_GATE_KEYS=["senado_ccj_historico"]`. O resumo do ciclo deve copiar
  o conteudo de `deferred_collections.json` e a justificativa da cobertura
  degradada.
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
- Nenhum resultado do artigo corrente deve ler `senado/ccj_notas`; antes de
  uma analise futura da CCJ, `2015-05` deve ser retomada e o gate estrito deve
  voltar a ser verdadeiro.

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
