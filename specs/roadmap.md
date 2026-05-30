# Roadmap

Este roadmap organiza o projeto em fases pequenas, com specs orientando as decisoes antes da implementacao.

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
- Registrar separadamente cobertura historica maxima e recorte analitico
  recomendado `2010-01-01` em diante.

## Fase 3: normalizacao e armazenamento

- Consolidar dados brutos em camada `raw`.
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

## Fase 5: validacao e publicacao

- Revisar consistencia dos dados e reproducibilidade das analises.
- Documentar limitacoes de cobertura, vieses de fonte e decisoes metodologicas.
- Preparar releases de datasets e resultados analiticos quando apropriado.
- Atualizar specs sempre que escopo, metodo ou stack mudarem de forma relevante.
- Tratar specs desatualizadas como bloqueio metodologico: cadernos, coletores e
  processamento novos devem ser acompanhados pela spec que descreve objetivo,
  entradas, saidas e validacao.
