# Decisões do pipeline de dados v3

## D01 — versão

**Estado:** aprovada em 2026-07-24.

A nova linha pós-coleta será identificada como v3. O nome evita colisão com a
normalização v1 arquivada e com a tentativa de snapshot v2.

## D02 — fonte de verdade

**Estado:** aprovada em 2026-07-24.

Somente `raw/` será fonte de entrada. Derivados antigos serão mantidos apenas
como arquivo histórico.

## D03 — inventário antes da ontologia

**Estado:** aprovada em 2026-07-24.

As categorias normalizadas serão propostas somente depois de observar todos os
metadados recebidos na coleta.

## D04 — limite da normalização Python

**Estado:** aprovada em 2026-07-24.

Python normalizará apenas metadados preenchidos por regras explícitas e
aprovadas. Valores ausentes continuarão ausentes.

## D05 — interpretação textual

**Estado:** aprovada em 2026-07-24.

Python não descobrirá marcadores, separadores, oradores ou fronteiras por regex
ou heurística. GPT-5.6 identificará os marcadores de cada texto; Python
validará literalmente a resposta e aplicará a transformação.

## D06 — saída GPT declarativa

**Estado:** aprovada em 2026-07-24.

GPT-5.6 devolverá um plano declarativo em JSON com evidências literais,
posições, tipos e ações de um vocabulário fechado. Não será solicitado nem
executado código Python específico para cada discurso. Um único motor Python,
versionado e testado, aplicará os planos válidos. A decisão reduz tokens de
saída, superfície de erro e dificuldade de auditoria.

## D07 — implementação

**Estado:** aprovada parcialmente em 2026-07-24.

As specs do primeiro submódulo foram aprovadas e sua implementação foi
autorizada. Os submódulos seguintes continuam bloqueados até seus próprios
contratos e gates.
