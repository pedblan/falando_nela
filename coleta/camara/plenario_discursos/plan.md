# Plano: discursos da Camara por deputado

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Deputados: `GET /api/v2/deputados`.
- Discursos: `GET /api/v2/deputados/{id}/discursos`.
- Referencia de cobertura: o Banco de Discursos da Camara documenta
  pronunciamentos de Plenario desde 1946.

## Recorte Historico

- O backfill oficial de `camara/plenario_discursos` deve iniciar em
  `1946-01-01`.
- A data `1900-01-01` nao deve ser usada como default operacional desta base,
  porque pode acionar muitas consultas vazias ou registros anomalos sem data
  real.
- Se houver interesse em investigar registros anteriores a 1946, isso deve ser
  feito como diagnostico separado de `1900-01-01` a `1945-12-31`, com limite
  explicito e saida/auditoria em `metadata/`, sem preencher corpus mensal por
  padrao.
- Para analises substantivas comparaveis entre bases, o recorte recomendado do
  projeto continua sendo `2010-01-01` em diante.

O inicio oficial acima continua sendo o contrato de um backfill historico
dedicado; ele nao deve ser confundido com uma atualizacao temporal. No ciclo
`20260713`, as ultimas coletas uteis ja haviam ocorrido em maio e o caderno 05
coleta somente a sobreposicao `2026-05-01` a `2026-07-13`.

O run incompleto `prod-historico-camara-plenario` e seus artefatos permanecem
no Drive, fora dos gates desse ciclo. Uma retomada desde 1946 exige tarefa e
runtime proprios e nao pode bloquear a incorporacao da nova janela.

### Recuperacao Prioritaria De 2010

- A lacuna `camara/2010` deve ser recuperada em um run anual proprio, com
  `data_inicio=2010-01-01`, `data_fim=2010-12-31` e `run_id` novo. Ela nao
  deve reutilizar nem apagar o run historico incompleto.
- A populacao deve ser formada por `parlamentares_periodos` oficial, quando
  disponivel, usando `parlamentar_id`; o fallback permitido e
  `GET /api/v2/deputados` no mesmo periodo, que tambem retorna o `id` oficial.
  Nome nao e chave de descoberta, de deduplicacao ou de validacao.
- O caderno `09_recuperacao_discursos_plenario_2010_colab.ipynb` registra a
  quantidade de deputados por id, paginas, discursos e transcricoes. O run so
  pode seguir aos derivados com `status=completed`, `errors=0`, zero anos
  falhos e ao menos uma transcricao de 2010.
- Um snapshot de recuperacao pode exigir explicitamente os anos 2010, 2015 e
  2016 por arena. Essa exigencia pontual nao declara cobertura dos anos entre
  eles nem altera a faixa de elegibilidade inferencial completa.

## Fluxo

1. Particionar o periodo por ano.
2. Antes de abrir requisicoes por deputado, tentar carregar
   `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet` ou,
   como fallback local, `processed/parlamentares/v1/parlamentares_periodos.jsonl`.
   No Colab, o caderno operacional pode copiar o Parquet para o disco efemero
   do runtime e passa-lo por `--parlamentares-periodos-path`; raw, checkpoint,
   log e manifest continuam no Drive.
3. Quando `parlamentares_periodos` existir, montar o plano anual apenas com
   deputados cujos mandatos oficiais interceptam o ano e clipar a janela de
   cada deputado ao intervalo efetivo do mandato naquele ano.
4. Quando `parlamentares_periodos` nao existir, usar o comportamento antigo:
   coletar a lista de deputados ativos no intervalo daquele ano pela API da
   Camara como metadado auxiliar.
5. Para cada deputado ativo no ano, consultar
   `/api/v2/deputados/{id}/discursos` com `itens=1` como preflight anual.
   Se o endpoint devolver erro de servidor/limite no probe ordenado por
   `dataHoraInicio`, repetir o probe sem parametros de ordenacao antes de
   considerar a janela falha.
   Para `500 Internal Server Error`, cair no fallback apos uma tentativa, sem
   esperar a sequencia completa de retries.
6. Se o preflight anual vier sem `dados`, gravar o probe em `metadata/` e nao
   abrir trimestres nem meses para aquele deputado/ano.
7. Se o ano for positivo, consultar trimestres com `itens=1`.
8. Trimestres vazios param no probe; trimestres positivos abrem as janelas
   mensais daquele trimestre.
9. Apenas requisicoes mensais completas sao paginadas e gravadas em
   `ano=YYYY/mes=MM/{run_id}.jsonl`.
10. Se uma requisicao mensal falhar com `500`, `502`, `503`, `504` ou `429`,
    tentar a mesma janela sem ordenacao. Se ainda falhar, paginar
    explicitamente com `itens=1`, gravando paginas recuperadas no corpus
    mensal e paginas persistentes quebradas como erro auditavel em `metadata/`.
    O erro `500` aciona esse fallback rapidamente, porque nos anos historicos
    ele costuma ser persistente e ligado a registros/paginas especificos.
11. Depois de concluir um deputado sem erro de página, gravar no checkpoint do
    mesmo `run_id` uma fronteira por deputado e intervalo de mandato. Uma
    retomada deve pular essa fronteira sem reconsultar a API; itens com erro de
    página permanecem pendentes.
12. Para recuperar uma interrupção produzida por versões anteriores que ainda
    não gravavam essa fronteira, aceitar apenas o prefixo determinístico do
    plano de mandatos declarado no manifest, se cada deputado do prefixo tiver
    evidência raw de probe. A inferência registra sua proveniência no
    checkpoint; nunca é feita por nome.
13. Limitar a espera indicada por `Retry-After` da API a 60 segundos por
    tentativa. Depois dos retries e fallbacks normais, registrar a falha
    recuperável em vez de deixar o Colab sem progresso indefinidamente.
14. Preservar `transcricao` como texto oficial quando entregue pela API.
15. Quando houver endpoint oficial mais granular para texto integral do discurso
   ou sessao, esse texto deve ter prioridade sobre metadados, `sumario` e
   palavras-chave.

## Record Types

- `deputados_page`: lista de deputados ativos no intervalo anual, em
  `metadata/`, usada somente quando `parlamentares_periodos` nao estiver
  disponivel.
- `discursos_year_probe`: primeira pagina anual com `itens=1`, em
  `metadata/`.
- `discursos_quarter_probe`: primeira pagina trimestral com `itens=1`, em
  `metadata/`.
- `discursos_page`: pagina mensal de discursos, em `ano=YYYY/mes=MM/`.
- `discursos_page_error`: erro persistente de pagina mensal apos fallback,
  em `metadata/`, com status HTTP, periodo e estrategia de fallback.

## Saidas

- `data/raw/camara/plenario_discursos/metadata/{run_id}.jsonl`.
- `data/raw/camara/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`.
- `data/checkpoints/camara/plenario_discursos.json`, com retomada por
  `run_id`, partição e fronteiras concluídas por deputado.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Contrato De Corpus

- Requisicoes anuais ou trimestrais nunca devem ser gravadas no corpus
  `ano=YYYY/mes=MM/`; elas sao somente descoberta em `metadata/`, porque podem
  misturar meses diferentes.
- So paginas de requisicoes mensais podem ser gravadas em
  `ano=YYYY/mes=MM/{run_id}.jsonl`.
- O caderno de backfill deve auditar esse contrato antes do processamento.
- O caderno de backfill historico deve coletar e processar `parlamentares/v1`
  antes de `camara/plenario_discursos` sempre que possivel, para reduzir anos
  vazios por deputado.

## Dev E Producao

- `dev`: primeira particao anual e amostra de deputados por default, gravada em
  `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google
  Drive via `FALANDO_NELA_DATA_ROOT`.
- No caderno de backfill historico, esta base deve ter `data_inicio`
  especifica `1946-01-01`, mesmo quando outras bases usarem `1900-01-01`.

## Resiliencia Operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a
  execucao.
- Capturar falhas de deputado/particao com `try/except`, registrar log
  estruturado e continuar quando possivel.
- Para erros 500 historicos da API de discursos, reduzir a granularidade da
  pagina antes de desistir da janela: uma tentativa ordenada, mensal sem
  ordenacao, pagina mensal `itens=1`.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular
  particoes/registros existentes desse `run_id`.
- Durante a varredura dos JSONLs existentes, imprimir inicio, progresso por
  arquivo/50 mil registros e conclusao, para que a indexacao do Drive nao
  pareca uma execucao travada.
- Se checkpoint e log concordarem sobre as particoes concluidas e identificarem
  anos abertos ou com falha, reconstruir o indice somente para esses anos,
  incluindo o arquivo compartilhado de `metadata`; diante de divergencia,
  voltar automaticamente ao scan integral.
- Dentro de cada ano, registrar `deputy_progress` no primeiro deputado, a cada
  25 e no ultimo, atualizando tambem o autosave com a particao ativa.
- `--skip-existing-record-scan` so pode ser usado com `--resume` quando
  checkpoint e log comprovarem que, dentro da janela pedida, toda particao
  iniciada foi concluida e nao houver falha nao resolvida. Se houver particao
  parcial, manter a varredura completa para evitar duplicatas.
- Pode rodar em paralelo com os coletores `senado/ccj_notas` e
  `camara/ccjc_eventos` se cada execucao tiver `run_id` distinto.
