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
do raw. O manifest aprovado está ancorado externamente pelo SHA-256
`b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9`.

## D09 — piloto de categorias e samples em G02

**Estado:** aprovada em 2026-07-24.

GPT-5.6 poderá propor categorias, colunas e possíveis aliases a partir de
evidências estruturais dos metadados observados e categorias oficiais das
APIs. Samples estruturais poderão mostrar o banco na prática com strings não
classificadas redigidas. Previews textuais limitados a 500 caracteres serão
`context_only`, dependerão de aprovação humana individual e serão avaliados em
condições A/B pareadas. Nenhuma proposta do modelo será aplicada
automaticamente e G02 continuará dependente de revisão humana.

## D10 — aprovação do vocabulário conceitual de G02

**Estado:** aprovada em 2026-07-25.

A proposta `gpt56-global-schema-proposal-v1` foi revisada por famílias, coluna
a coluna, e aprovada com as reformulações registradas em
`docs/revisoes/g02_schema_global_revisao_humana.md`. A decisão inclui
proveniência por ocorrência, entidades e cardinalidades distintas, categorias
oficiais literais, duas famílias temáticas omitidas, oito decisões de alias e
a trilha polimórfica de `senado/ccj_notas`.

A aprovação congela o vocabulário conceitual antes de qualquer Batch, mas não
aprova operacionalmente G02. Permanecem pendentes o livro dos 23.786 caminhos,
os 543 conflitos, as 14 rejeições, a execução integral do schema lógico, as
regras e o relatório integral. Não foram autorizados Batch, adaptadores,
normalização, Parquets ou alterações no raw naquela decisão. A autorização
posterior e restrita de Batch e auditoria raw está registrada em D12.

## D11 — reconciliação global e contrato lógico de G02

**Estado:** concluída em 2026-07-25; G02 permanece pendente.

Os hashes do catálogo, do crosswalk, das amostras e dos sete artefatos JSON da
chamada global foram recalculados. A entrada final incluiu o JSON Schema
fechado e teve 692.031 tokens; a resposta terminou sem truncamento, foi
validada e permaneceu não aplicada. A trilha está registrada em
`02_schema_normalizado/g02_reconciliacao_global_20260725.md`.

O gerador de `schema_normalizado.schema.json` passou a expressar as
coordenadas por registro e valor, os namespaces de entidades, as
cardinalidades, as famílias de `senado/ccj_notas`, os metadados temáticos e as
oito decisões de alias aprovadas. O contrato continua declarativo e registra
explicitamente materialização zero, ausência de layout Parquet e preservação
do raw.

Essa implementação não substitui o mapeamento individual dos 23.786
`field_id`, a auditoria integral por registro nem a decisão humana do gate
G02. Pela regra de avanço, as specs de `03_adaptadores_fontes` continuam
bloqueadas enquanto G02 não for aprovado operacionalmente.

## D12 — Batch de disposição e auditoria raw integral de G02

**Estado:** Batch e auditoria raw reconciliados em 2026-07-26; G02 permanece
pendente.

Depois da aprovação do vocabulário, o pesquisador autorizou especificamente
o Batch de disposição dos 23.786 `field_id`, a auditoria integral do raw em
modo somente leitura e a reutilização segura da `OPENAI_API_KEY` local. A
autorização não abrange aplicação, adaptadores, normalização, Parquets ou
alteração do raw.

A tentativa Batch com o alias `gpt-5.6` foi rejeitada antes do processamento
e preservada. A tentativa válida usa `gpt-5.6-sol`, 99 requisições
independentes, 1.353.952 tokens de entrada e o mesmo vocabulário fechado em
todas as linhas. A primeira saída deixou 4.007 IDs pendentes; dois reparos
disjuntos reduziram esse número a zero. A união final contém exatamente
23.786 propostas únicas, custou US$ 19,7714390 e permanece integralmente não
aplicada e não avaliada humanamente. O registro operacional e a auditoria
estão documentados em
`02_schema_normalizado/g02_batch_e_auditoria_20260725.md`.

A auditoria raw releu 1.148.740 registros e preservou o fingerprint de G01,
as 23.786 chaves, os 543 conflitos e os 20.523 caminhos de
`senado/ccj_notas`. Uma deduplicação herdada da lista de inconsistências de
G01 localizou inicialmente 9 das 14 rejeições; um suplemento imutável releu
os seis arquivos afetados e reconciliou as 14 coordenadas e hashes sem
alterar o raw ou o artefato original.
