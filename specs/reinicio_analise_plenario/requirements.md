# Requirements: reinício controlado da análise de plenário

Status: **contrato aprovado em 2026-07-23**.

## Objetivo

Reiniciar integralmente a camada analítica de discursos de plenário, mantendo
os dados e resultados anteriores como arquivo auditável e separando:

1. preparação e inventário de dados;
2. snapshots imutáveis;
3. análise científica;
4. relatórios humanos;
5. manifests técnicos;
6. logs de diagnóstico.

## Escopo preservado

- A execução `analise-plenario-20260717-v1` deve permanecer íntegra e ser
  classificada como abortada para resultados científicos.
- Notebooks, revisões humanas, JSONLs, resultados de Batch, manifests e logs
  antigos devem permanecer disponíveis para auditoria.
- O snapshot v1 deve permanecer legível e com seus hashes preservados, mesmo
  se um snapshot v2 for criado.
- Casos revisados na segmentação de apartes podem ser reutilizados como
  exemplos diagnósticos, nunca como verdade automática da nova análise.

## Separação de identidades

- `snapshot_id` identifica um produto de dados imutável.
- `analysis_run_id` identifica uma execução científica que referencia um
  `snapshot_id`.
- `operation_id` identifica inventários, migrações e auditorias operacionais.
- Nenhum desses IDs pode ser usado como sinônimo dos demais.

## Governança por specs

- Nenhuma etapa científica será implementada antes de sua spec própria.
- Cada spec de etapa deve declarar pergunta, unidade, universo, denominador,
  inclusões, exclusões, saídas, validação e condição de parada.
- Decisões científicas não podem ser preenchidas por defaults escolhidos pelo
  agente.
- Mudanças aprovadas devem atualizar specs, notebooks, código e testes no
  mesmo ciclo.
- Execuções pagas exigem autorização explícita e separada da aprovação do
  código.

## Organização dos notebooks

- A análise abortada deve ser arquivada em diretório explicitamente nomeado.
- `notebooks/dados/` conterá inventário, snapshot e eventual migração.
- `notebooks/analise/` conterá apenas etapas científicas aprovadas.
- Não haverá geração antecipada de uma suíte completa de cadernos vazios.
- Cada notebook deve declarar, antes de qualquer célula executável cara:
  objetivo, entradas, saídas, custo possível e próximo checkpoint humano.

## Artefatos e comunicação

- Toda saída deve aparecer em um catálogo com nome, finalidade, unidade,
  formato, caminho e etapa produtora.
- Contagens sem universo explícito são inválidas.
- Relatórios humanos não devem imprimir configurações ou manifests completos.
- Logs completos devem ser persistidos, mas exibidos apenas por resumo ou
  cauda quando houver erro.
- Manifests devem ser pequenos, estáveis e destinados à reprodutibilidade.
- Um relatório Markdown deve explicar em linguagem direta o que ocorreu, o
  que foi produzido, as limitações e a próxima decisão.

## Segurança dos dados

- Inventários são somente leitura.
- Planos de migração não executam movimentações.
- Migrações exigem aprovação do plano, cópia antes de qualquer remoção,
  verificação por hash e registro de rollback.
- Nenhuma exclusão automática é permitida.
- Entradas `raw` e `processed` permanecem somente leitura para a análise.

## Novo snapshot

- A criação do snapshot v2 depende de spec aprovada e baseline exploratório
  concluído; o saneamento dos manifests legados não é pré-condição.
- O snapshot deve partir somente de bases processadas canônicas aprovadas.
- Filtros, deduplicações e cortes temporais devem aparecer como regras
  explícitas e produzir contagens antes/depois.
- O snapshot não deve embutir elegibilidade de NLP, GPT ou hipóteses
  científicas sem colunas e justificativas explícitas.
- O snapshot deve produzir relatório humano de cobertura por fonte, arena,
  dataset, ano e estado de qualidade.

## Fora de escopo deste pacote

- Definir as perguntas substantivas da nova análise.
- Implementar episódios, atos de fala, NLP, tópicos ou inferência.
- Executar novamente a segmentação de apartes.
- Enviar chamadas à OpenAI.
- Mover ou apagar dados no Drive.
