# Roadmap

Este roadmap organiza o projeto em fases pequenas, com specs orientando as decisoes antes da implementacao.

## Atualizacao temporal via Colab

- O ciclo `20260713` regulariza runs historicos pendentes e atualiza todas as
  bases ate `2026-07-13`, com sobreposicao desde `2026-05-01`, conforme
  `specs/atualizacao_dados_colab/`.
- Coletas historicas longas rodam exclusivamente no Colab/Drive. O repositorio
  local executa testes, validacao estrutural dos cadernos e smokes pequenos.
- `senado/congresso_discursos` passa a integrar o corpus
  `textos_parlamentares/v1` com texto integral, fallback de sessao e fila de
  transcricao.
- Processamento usa fotografia canonica `current`; configuracoes, manifests,
  auditorias e amostras sao arquivados por ciclo.
- A faixa do Plenario da Camara nesse ciclo e estritamente incremental,
  `2026-05-01` a `2026-07-13`. O backfill iniciado em 1946 foi retirado dos
  gates da atualizacao e preservado para trabalho historico separado.

## Fase 0: fundacao

- Criar as specs primarias: missao, stack tecnica e roadmap.
- Renomear a branch principal local para `main`.
- Manter o repositorio sem codigo ate a definicao da primeira spec operacional.
- Preservar higiene inicial do repositorio, evitando arquivos desnecessarios de dados, notebooks ou dependencias antes da hora.

## Fase 1: prototipo local de coleta

- Criar uma spec para o modulo de coleta.
- Implementar prototipos locais com uma parcela estratificada e pequena de cada fonte-alvo.
- Validar acesso, paginacao, campos essenciais, limites dos portais e comportamento de erro.
- Definir o contrato minimo dos registros coletados.

## Fase 2: coleta completa no Colab

- Criar notebook preparado para Google Colab Pro.
- Executar coletas longas com retries, checkpoints e logs.
- Permitir retomada segura de execucoes interrompidas.
- Evitar duplicacao de registros entre execucoes.
- Descarregar metadados oficiais de apartes em Plenario como base raw
  separada, antes mesmo do backfill historico completo de discursos, porque
  esses registros nao dependem de texto integral para a primeira analise
  relacional.
- Orquestrar backfill historico de todas as bases existentes com `run_id`s
  fixos, `--resume`, validacao curta e inspecao de manifests antes do
  processamento.
- Reduzir consultas vazias no backfill longo com janelas anuais de preflight:
  apartes preservam anos e trimestres vazios em `metadata/` e expandem apenas
  trimestres positivos para meses; `camara/plenario_discursos` usa o mesmo
  principio com inicio oficial em `1946-01-01`, probes em `metadata/` e somente
  requisicoes mensais no corpus textual. Para `senado/plenario_discursos` e
  `senado/congresso_discursos`, o endpoint rejeita janelas acima de um mes; o
  backfill operacional usa os primeiros meses com retorno observado,
  respectivamente `1995-02-01` e `1996-05-01`.
- Antes dos coletores historicos lentos da Camara, gerar `parlamentares/v1` e
  usar `parlamentares_periodos` como plano de mandato para
  `camara/plenario_discursos` e `camara/plenario_apartes`, evitando consultas de
  deputados em anos fora do exercicio oficial. A descoberta via API permanece
  como fallback quando a tabela ainda nao existir.
- Em tarefas historicas extensas do Plenario da Camara, tornar a inicializacao
  observavel e proporcional: copiar o pequeno plano de mandatos para o runtime
  Colab, imprimir o scan do raw e heartbeats por deputado. Pular o scan apenas
  quando checkpoint e log comprovarem uma fronteira entre particoes; particao
  parcial usa indice restrito aos anos afetados quando o escopo for comprovado,
  sem duplicar raw nem reler particoes concluidas.
- Registrar separadamente cobertura historica maxima e recorte analitico
  recomendado `2010-01-01` em diante.
- Permitir adiamentos operacionais apenas para bases explicitamente excluidas
  da analise corrente, com `run_id`, status e particoes exatas, motivo e
  acompanhamento arquivados. O gate aceito nunca deve ser confundido com a
  conclusao estrita do ciclo.

## Fase 3: normalizacao e armazenamento

- Consolidar dados brutos em camada `raw`.
- Recuperar, antes de qualquer novo ASR, as transcrições audiovisuais já
  existentes para o Senado em `DiscursosTodos.parquet`. Para a Câmara, que não
  está no legado, produzir primeiro uma fila auditável de mídia e dimensionar
  download/transcrição em etapa própria. Manter tudo em `operations/` até
  revisão e promoção raw versionada.
- Criar camada `processed` com campos normalizados entre Senado, Congresso e Camara.
- Criar `apartes_parlamentares/v1` como tabela relacional independente de
  `textos_parlamentares/v1`, voltada a contagens anuais de relacoes
  `aparteante -> discurso/pronunciamento` e cruzamento com
  `parlamentares/v1`, com JSONL, Parquet, manifest e auditorias gerados por
  `processamento.apartes_parlamentares`.
- Inventariar separadores no corpus completo antes de cortar texto integral,
  usando os Parquets completos do Drive como fonte principal de auditoria.
- Diagnosticar separadores especificamente nos discursos historicos anteriores a
  2010, comparando por fonte, dataset e ano antes de promover qualquer regra de
  corte automatico.
- Criar modulo de processamento do texto integral para separar, de forma
  auditavel, o corpo analitico de discursos e notas de anexos, artigos citados,
  expedientes e outros blocos editoriais agregados pela fonte oficial.
- Produzir dicionario de dados.
- Definir estrategia de versionamento dos datasets gerados.

## Fase 4: cadernos analiticos por artigo constitucional

- Criar notebooks especificos para artigos ou temas constitucionais.
- Documentar criterios de selecao, filtros, palavras-chave e metodos.
- Produzir tabelas e visualizacoes com Altair.
- Separar hipoteses substantivas, metodos e resultados em cada caderno.

## Fase 4.1: suite comparativa dos discursos em plenario

- Construir snapshot imutavel de Camara, Senado e Congresso entre
  `2010-02-02` e `2026-07-13`, mantendo arena e Casa de origem separadas.
- Tratar 2010–2025 como series anuais completas e 2026 apenas como YTD.
- Auditar duplicacoes Senado × Congresso, aplicar exclusivamente regras de
  limpeza aprovadas e fazer juncao temporal com `parlamentares_periodos`.
- Criar camada derivada e humanamente revisada para genero oficial desconhecido,
  sem alterar `parlamentares/v1`.
- Produzir descritivas, apartes relacionais, segmentacao de turnos, atos de
  fala, possivel descortesia, NLP, inferencia temporal, clusterizacao, BERTopic,
  figuras de linguagem com GPT-5.6 e sintese comparativa.
- Exigir piloto humano e evidencias textuais nas classificacoes; usar Batch API
  e Structured Outputs somente por celula de comando explicita.
- Manter cadernos Jupyter/Colab em portugues como primeira entrega, com logica
  reutilizavel em `analise.discursos_plenario`.
- Suportar futuramente conversao revisada para Marimo e variantes inglesas que
  substituem apenas Markdown e preservam codigo, manifests e resultados.

## Fase 5: validacao e publicacao

- Revisar consistencia dos dados e reproducibilidade das analises.
- Documentar limitacoes de cobertura, vieses de fonte e decisoes metodologicas.
- Preparar releases de datasets e resultados analiticos quando apropriado.
- Atualizar specs sempre que escopo, metodo ou stack mudarem de forma relevante.
- Tratar specs desatualizadas como bloqueio metodologico: cadernos, coletores e
  processamento novos devem ser acompanhados pela spec que descreve objetivo,
  entradas, saidas e validacao.
