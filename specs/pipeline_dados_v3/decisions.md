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

**Estado:** aprovada parcialmente e ampliada em 2026-07-24.

As specs e a implementação do primeiro submódulo foram aprovadas. A ferramenta
de evidências de `02_schema_normalizado` também foi autorizada depois da
aprovação de suas quatro specs. A autorização não inclui aplicar o schema,
materializar dados normalizados ou iniciar adaptadores.

## D08 — aprovação de G01

**Estado:** aprovada em 2026-07-24.

O inventário integral
`raw-metadata-full-20260724t184418z` foi aceito como mapa estrutural do raw. As
rejeições, arquivos vazios, itens acidentais e conflitos de tipos permanecem
documentados e serão tratados como entradas do próximo contrato, sem correção
do raw.

## D09 — piloto de categorias e samples em G02

**Estado:** aprovada em 2026-07-24.

GPT-5.6 poderá propor categorias, colunas e possíveis aliases a partir de
evidências estruturais dos metadados observados e categorias oficiais das
APIs. Samples estruturais poderão mostrar o banco na prática com strings não
classificadas redigidas. Previews textuais limitados a 500 caracteres serão
`context_only`, dependerão de aprovação humana individual e serão avaliados em
condições A/B pareadas. Nenhuma proposta do modelo será aplicada
automaticamente e G02 continuará dependente de revisão humana.
