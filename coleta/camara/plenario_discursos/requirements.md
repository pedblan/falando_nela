# Requirements: discursos da Camara por deputado

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa
  coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre
  `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit N`: limita deputados em validacoes/amostras.
- `--resume`: pula particoes concluidas no checkpoint para o mesmo `run_id` e
  registros ja existentes desse `run_id`.
- `--run-id`: identificador da execucao.

## Recorte

- O backfill oficial deve usar `--data-inicio 1946-01-01`.
- O intervalo `1900-01-01` a `1945-12-31` so pode ser usado em diagnostico
  separado, com limite explicito, para investigar anomalias como discursos sem
  data real. Ele nao deve ser default do caderno de backfill.

## Separacao De Dados

- Listas de deputados e probes ficam em
  `data/raw/camara/plenario_discursos/metadata/{run_id}.jsonl`.
- Paginas mensais de discursos ficam em
  `data/raw/camara/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`, porque
  podem conter `transcricao`.
- Nenhuma resposta anual ou trimestral pode ser gravada em `ano=YYYY/mes=MM/`.

## Preflight

- O coletor deve particionar por ano.
- Quando `processed/parlamentares/v1` existir no `data_root`, o coletor deve
  carregar `parlamentares_periodos` e consultar apenas deputados cujos mandatos
  oficiais interceptem o ano corrente.
- Em coleta completa (`--no-sample`), um `parlamentares_periodos` muito pequeno
  deve ser tratado como amostra/insuficiente e nao pode substituir a descoberta
  oficial de deputados.
- A janela enviada ao endpoint de discursos deve ser clipada ao intervalo de
  mandato do deputado dentro daquele ano, quando esse plano estiver disponivel.
- Quando `parlamentares_periodos` nao existir, a lista de deputados deve ser
  coletada por ano pela API, para evitar consultar parlamentares que nao
  estavam ativos naquele intervalo.
- Para cada deputado/ano, o coletor deve fazer probe anual com `itens=1`.
- Se a API devolver `500`, `502`, `503`, `504` ou `429` no probe ordenado
  por `dataHoraInicio`, o coletor deve tentar novamente sem `ordem` e sem
  `ordenarPor`, registrando a estrategia em `request.fallback_strategy`.
- Para `500 Internal Server Error` nos pontos com fallback conhecido, o
  coletor deve fazer apenas uma tentativa antes de trocar de estrategia. Isso
  evita gastar a politica completa de retry em erros historicos persistentes.
  `429`, `502`, `503` e `504` continuam podendo usar retries normais quando
  nao houver fallback imediato seguro.
- Ano vazio nao abre trimestre nem mes.
- Ano positivo abre probes trimestrais com `itens=1`.
- Trimestre vazio nao abre mes.
- Trimestre positivo abre os meses correspondentes; em caso de falha do
  preflight trimestral, o coletor pode abrir meses como fallback conservador.
- Falha do preflight anual deve ser registrada em log e pode cair para o fluxo
  trimestral como fallback.

## Campos Obrigatorios

- Id do deputado no `source_id`.
- Periodo consultado.
- `record_type` coerente com a granularidade:
  `deputados_page`, `discursos_year_probe`, `discursos_quarter_probe` ou
  `discursos_page`; falhas persistentes de pagina mensal usam
  `discursos_page_error` em `metadata/`.
- Pagina de discursos retornada pela API nos registros mensais.
- Quando uma pagina mensal ordenada falhar com erro temporario/servidor, o
  coletor deve tentar a mesma janela sem ordenacao. Se continuar falhando, deve
  cair para paginacao explicita com `itens=1`, gravando as paginas recuperadas
  no corpus mensal e registrando paginas ainda quebradas como
  `discursos_page_error` em `metadata/`.
- A primeira tentativa mensal ordenada que receber `500` deve acionar fallback
  rapido sem aguardar todos os retries do cliente HTTP padrao.
- `transcricao` deve ser preservada como texto prioritario quando estiver
  disponivel.
- URL final, status HTTP, payload e checksum.
- O manifest deve registrar `deputados_periodos_carregados` quando o plano por
  mandato for usado.
- O manifest deve terminar como `completed_with_errors` quando houver paginas
  mensais persistentes registradas como `discursos_page_error`.

## Limites

- O endpoint de discursos e por deputado; a coleta completa faz muitas
  requisicoes mesmo com preflight.
- O endpoint pode incluir discursos em eventos diversos; filtros analiticos de
  Plenario ficam para normalizacao posterior.
- `sumario` e `keywords` nao substituem a transcricao/texto integral.

## Concorrencia Operacional

- Pode rodar em paralelo com `senado/ccj_notas` e `camara/ccjc_eventos`, pois
  usa `raw/camara/plenario_discursos/` e checkpoint proprio.
- O `run_id` deve ser distinto dos outros notebooks ativos, porque logs e
  manifests sao indexados por `run_id`.
- Nao rode duas instancias de `camara/plenario_discursos` com o mesmo `run_id`
  ao mesmo tempo.

## Progresso, Autosave E Retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e
  conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e
  `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de deputado ou particao sem derrubar o fluxo
  inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas pelo mesmo
  `run_id` e registros ja presentes no JSONL do mesmo `run_id`.
