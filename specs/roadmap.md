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

## Fase 3: normalizacao e armazenamento

- Consolidar dados brutos em camada `raw`.
- Criar camada `processed` com campos normalizados entre Senado, Congresso e Camara.
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
