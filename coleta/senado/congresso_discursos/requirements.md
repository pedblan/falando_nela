# Requirements: discursos do Plenario do Congresso

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador da execucao.
- `--discovery-strategy period-session|historical-official`: default
  `period-session`; o modo histórico é opt-in e percorre a busca oficial
  paginada por autor, filtrando exclusivamente `Congresso Nacional`/`CN`.

## Recuperação 2015–2016

- `Sessoes=null` no endpoint mensal é `source_anomaly` quando a busca oficial
  encontra pronunciamentos.
- HTML bruto fica em `metadata/` como `discursos_portal_page`; IDs e auditoria
  consolidada ficam em `discursos_historical_discovery`.
- Todos os IDs do endpoint mensal em meses-controle devem reaparecer na fonte
  histórica; ausência bloqueia a partição.
- Autores sem código de senador não podem ser descartados, razão pela qual o
  índice oficial por autor é a descoberta autoritativa do Congresso.

## Auditoria de senadores

- A auditoria desde 2010 consulta o endpoint por CodigoParlamentar com casa CN
  e compara apenas CodigoPronunciamento de senadores com o raw.
- raw_ids_not_in_senator_endpoint não bloqueia a auditoria de CN, pois pode
  representar deputados ou autoridades.
- A auditoria não substitui a descoberta por sessões ou índice oficial para
  completar autores não senadores.

## Separacao de dados

- Listas mensais da API ficam em `data/raw/senado/congresso_discursos/metadata/{run_id}.jsonl`.
- O corpus textual mensal fica reservado a registros consolidados com texto integral.
- A lista mensal nao deve ser tratada como substituta do texto integral.

## Recorte E Granularidade

- Backfill operacional do endpoint: `1996-05-01` em diante.
- Probes mensais encontraram o primeiro pronunciamento de `siglaCasa=CN` em
  `1996-05-21`.
- Janelas acima de um mes no endpoint de lista retornam HTTP 400; por isso, o
  coletor deve continuar mensal e nao usar preflight anual/trimestral.
- Periodos anteriores a `1996-05-01` ficam fora do backfill normal deste
  endpoint e devem ser tratados como diagnostico separado.

## Campos obrigatorios

- Fonte, dataset, periodo e endpoint consultado.
- `siglaCasa=CN`.
- `CodigoPronunciamento` e texto integral quando a fonte oficial disponibilizar.
- URL final, status HTTP e payload/texto retornado.
- Checksum do payload.

## Pipeline textual compartilhado

- Reutilizar o mesmo extrator e a mesma cadeia de obtencao de texto de
  `senado/plenario_discursos`, variando somente `dataset` e `siglaCasa`.
- Gravar `pronunciamento_texto` na particao mensal com o contrato canonico
  `CodigoPronunciamento`, `TextoIntegral`, `TextoIntegralUrl`, `texto`,
  `forma`, `metodo_obtencao`, `texto_status`, `metadata` e `fontes`.
- Tentar, nesta ordem, o endpoint oficial de texto integral e as notas da
  sessao. Preservar as tentativas no payload quando houver fallback.
- Quando nao houver texto e existir video, texto binario ou endpoint de videos
  da sessao, gravar tambem em `transcription_queue`.
- Uma excecao inesperada ao baixar um pronunciamento deve marcar a particao
  mensal como falha. Em `--resume`, registros ja gravados sao pulados e os
  faltantes sao tentados novamente.

## Limites

- A API do Senado limita rotinas com mais de 10 requisicoes por segundo.
- Falhas `429`, `500`, `502`, `503` e `504` devem entrar na politica de retry.
- A lista mensal nao basta para analise textual; ela e metadado para localizar o texto integral do discurso ou da sessao.

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
