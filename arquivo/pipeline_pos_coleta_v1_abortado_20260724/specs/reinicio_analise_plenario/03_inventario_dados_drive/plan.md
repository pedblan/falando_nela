# Plano — inventário dos dados no Drive

Status: **encerrado como baseline exploratório em 2026-07-23 — saneamento adiado**.

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
- [x] Revisão do código publicada na `main`.
- [x] Operação real `drive-inventory-20260724t020749z` executada no Colab.
- [x] Relatório, mapa e inconsistências revisados conjuntamente.

## Resultado do piloto

- 7.859 itens reconciliados, incluindo 4.987 arquivos e 2.872 diretórios;
- nenhuma escrita na raiz examinada;
- 1.688 referências relativas classificadas incorretamente porque o resolvedor
  não considerou raízes declaradas nos manifests;
- correção dos manifests, duplicidades, órfãos e caminhos legados adiada;
- baseline aceito para orientação arquivística, sem aprovação para migração.

## Checkpoint obrigatório

Nenhuma ação de reorganização ou limpeza começa até que o pesquisador aprove:

- os universos e denominadores;
- as bases candidatas a canônicas;
- as inconsistências;
- cada ação proposta no plano de migração.

Esse checkpoint não bloqueia a fase 4 de identificar e validar diretamente as
bases processadas candidatas ao snapshot v2.
