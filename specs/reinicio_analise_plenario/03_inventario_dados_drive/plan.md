# Plano — inventário dos dados no Drive

Status: **piloto implementado e testado localmente — execução real não iniciada**.

1. Revisar e aprovar
   [`proposta_gate_inicial.md`](proposta_gate_inicial.md), com a raiz do Drive
   a examinar e a política de leitura.
2. Aprovar a taxonomia inicial de classe, camada, fonte e origem da
   classificação.
3. Listar metadados em modo somente leitura.
4. Identificar artefatos estruturados e extrair apenas os campos necessários.
5. Reconstruir relações entre entradas, execuções e saídas.
6. Medir e reconciliar todos os universos por fonte, camada, classe e unidade.
7. Sinalizar inconsistências, duplicidades potenciais e incertezas.
8. Gerar o catálogo tabular e o mapa humano.
9. Fazer a revisão de compreensão com o pesquisador.
10. Redigir, sem executar, o plano de migração.

## Progresso

- [x] Raiz e política de leitura aprovadas em 2026-07-23.
- [x] Taxonomia inicial aprovada em 2026-07-23.
- [x] Módulo de inventário implementado.
- [x] Notebook Colab protegido implementado.
- [x] Fixture local somente leitura e saídas D06 validadas.
- [ ] Publicar a revisão do código que contém o piloto.
- [ ] Executar a célula real no Colab com novo `operation_id`.
- [ ] Revisar conjuntamente relatório, mapa, universos e inconsistências.

## Checkpoint obrigatório

Após o passo 8, nenhuma ação de reorganização começa até que o pesquisador
aprove:

- os universos e denominadores;
- as bases candidatas a canônicas;
- as inconsistências;
- cada ação proposta no plano de migração.
