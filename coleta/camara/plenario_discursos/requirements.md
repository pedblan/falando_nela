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
  registros ja existentes desse `run_id`. Dentro de partição aberta, pula
  deputados já confirmados no checkpoint pelo mesmo ID e intervalo oficial de
  mandato.
- `--skip-existing-record-scan`: evita a varredura integral do raw somente em
  uma retomada situada entre particoes; exige `--resume`, checkpoint/log
  coerentes, nenhuma particao aberta na janela e zero falhas nao resolvidas.
- `--parlamentares-periodos-path`: caminho explicito para uma copia local de
  `parlamentares_periodos.parquet` ou `.jsonl`; nao altera o `output-dir`.
- `--run-id`: identificador da execucao.

## Recorte

- O backfill oficial deve usar `--data-inicio 1946-01-01`.
- O caderno operacional 05 do ciclo `20260713` nao e um backfill: deve usar
  `--data-inicio 2026-05-01 --data-fim 2026-07-13` e o `run_id`
  `prod-atualizacao-20260713-camara-plenario`.
- Esse caderno nao deve chamar `prod-historico-camara-plenario`; raw,
  checkpoint, log, autosave e eventual manifest desse run sao somente
  preservados. O coletor e seus defaults historicos permanecem inalterados.
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
- Um `Retry-After` enviado pela API pode atrasar no máximo 60 segundos cada
  tentativa. O coletor não pode permanecer sem evento por horas devido a uma
  espera controlada pelo servidor.
- O coletor deve respeitar intervalo mínimo de 0,2 segundo entre requisições à
  API da Câmara, inclusive nos caminhos de fallback rápido.
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
- A paginação mensal deve persistir cada resposta antes de solicitar a próxima;
  não pode acumular uma lista ilimitada de páginas em memória.
- Um `rel=next` posterior ao `rel=last` deve ser ignorado e registrado como
  anomalia. A URL de `rel=next` não pode alterar `dataInicio`, `dataFim`,
  ordenação ou tamanho de página da consulta mensal original; apenas seu número
  de página pode ser usado. Mais de 1.000 páginas no mesmo deputado/mês deve
  falhar a janela de modo auditável.
- `transcricao` deve ser preservada como texto prioritario quando estiver
  disponivel.
- Nomes e transcrições devem preservar Unicode/UTF-8, inclusive diacríticos
  como `ç`, `ã`, `ô` e `í`; o caractere de substituição `�` indica corrupção e
  deve reprovar a validação.
- URL final, status HTTP, payload e checksum.
- O manifest deve registrar `deputados_periodos_carregados` quando o plano por
  mandato for usado.
- O manifest deve terminar como `completed_with_errors` quando houver paginas
  mensais persistentes registradas como `discursos_page_error`.
- Interrupção explícita do runtime deve terminar o manifest com
  `status=interrupted`, nunca como `completed`.

## Limites

- O endpoint de discursos e por deputado; a coleta completa faz muitas
  requisicoes mesmo com preflight.
- O endpoint pode incluir discursos em eventos diversos; filtros analiticos de
  Plenario ficam para normalizacao posterior.
- `sumario` e `keywords` nao substituem a transcricao/texto integral.

## Recuperação De Texto Legado

- Itens sem `transcricao` e com mídia oficial podem ser inventariados fora do
  coletor; se outra ocorrência raw da mesma unidade já tiver texto, ela deve
  sair da fila.
- O Parquet legado contém somente Senado e não pode fornecer texto da Câmara.
- A saída da Câmara preserva id do deputado, data, evento, tipo, URL, origem raw,
  prioridade e estados pendentes de download/transcrição.
- A fila fica em `operations/` e não autoriza mutação do raw ou dos derivados.

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
- Uma falha de deputado ou pagina dentro de um ano impede que aquela particao
  seja marcada como concluida. O checkpoint deve registrá-la como falha para
  que o mesmo `run_id --resume` volte a tentar somente essa particao; uma
  cobertura parcial não pode parecer completa.
- Com `--resume`, o coletor deve pular particoes concluidas pelo mesmo
  `run_id` e registros ja presentes no JSONL do mesmo `run_id`.
- Para probe ou página mensal já presentes no raw do mesmo `run_id`, a retomada
  deve reconstruir a resposta a partir do payload gravado e não pode abrir nova
  conexão HTTP para esse `source_id`. Raw ilegível ou payload incompatível pode
  ser consultado novamente e deve ficar auditável no log.
- Após concluir um deputado sem erro de página, o checkpoint deve persistir a
  unidade `deputado + intervalo de mandato`; a retomada deve pular essa unidade
  sem nova consulta. Itens com erro ficam fora da fronteira e são tentados de
  novo.
- Para compatibilidade com interrupções de versões anteriores, um prefixo só
  pode ser migrado do manifest se o plano por mandato tiver o mesmo tamanho e
  houver probe raw para cada deputado do prefixo. A ordem é a dos IDs oficiais,
  não nomes.
- A varredura de registros existentes deve emitir progresso no stdout no
  inicio, a cada 50 mil linhas ou 25 arquivos e no fim.
- Quando checkpoint e log forem coerentes e houver particao anual parcial, o
  indice de duplicatas deve ler somente os anos abertos ou com falha e os
  respectivos registros de `metadata`. Se esse escopo nao puder ser provado,
  deve usar todo o raw do `run_id`.
- O processamento anual deve emitir `deputy_progress` no primeiro deputado, a
  cada 25 deputados e no ultimo; cada evento deve atualizar o autosave com
  `active_partition`, visitados, total, paginas, discursos e erros.
- Antes de cada deputado, registrar `deputy_started`; ao pular fronteira
  concluída, registrar `deputy_resume_skipped`. Isso identifica exatamente o
  item em curso quando um endpoint deixa de responder.
- Antes de uma página mensal sem cache raw, registrar
  `discursos_page_request_started`; uso de payload já gravado registra
  `record_resume_reused`.
- Quando a API entregar `next` além da última página declarada, registrar
  `discursos_pagination_next_ignored` com a URL descartada.
- Se o log contiver `partition_started` sem conclusao posterior para uma
  particao da janela, `--skip-existing-record-scan` deve ser recusado. A
  retomada normal continua permitida e deve reconstruir o indice a partir do
  raw cumulativo.
