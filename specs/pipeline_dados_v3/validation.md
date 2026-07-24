# Validação geral do pipeline de dados v3

## Princípio

Sucesso operacional não equivale a aprovação científica. Cada etapa termina em
um gate humano.

## Gates

| Gate | Condição para abertura | Aprovação necessária |
|---|---|---|
| G00 — arquivo | `data/` contém somente `raw/` | confirmar que a linha anterior foi isolada |
| G01 — inventário | todos os itens raw foram reconciliados | aprovar o mapa de campos e valores |
| G02 — categorias | vocabulário proposto a partir do inventário | aprovar categorias, nulos e proveniência |
| G03 — adaptadores | smoke estratificado por fonte e dataset | aprovar regras Python apenas para metadados preenchidos |
| G04 — marcadores | piloto GPT-5.6 com revisão humana | aprovar prompt, schema, custo e precisão |
| G05 — normalização | execução integral reconciliada | aprovar a camada processada v3 |
| G06 — snapshot | unidade, período e exclusões documentados | aprovar o corpus científico |
| G07 — análise | perguntas e métodos especificados | autorizar cada etapa analítica |

## Validações transversais

- O fingerprint estrutural do `raw/` deve permanecer inalterado.
- Toda contagem deve declarar unidade e universo.
- Toda exclusão deve ser quantificada e reproduzível.
- Todo valor normalizado deve apontar para sua origem.
- Nulos não podem ser preenchidos silenciosamente.
- Saídas GPT devem passar por validação literal de trecho e posição.
- Saídas GPT devem obedecer a um schema fechado e a um vocabulário aprovado
  de tipos e ações.
- O resultado por texto deve ser declarativo e não pode conter código
  executável.
- Respostas inválidas, recusas e indeterminações devem permanecer auditáveis.
- Custos observados e projetados devem ser apresentados antes de batches
  amplos.

## Bloqueios

Uma etapa não pode ser aprovada quando:

- houver escrita no raw;
- entradas não estiverem reconciliadas;
- uma regra Python interpretar texto;
- um metadado ausente for inferido;
- um marcador GPT não existir literalmente no texto;
- uma saída GPT contiver função, comando, expressão regular ou outro código a
  ser executado;
- uma ação não puder ser aplicada pelo motor Python comum, versionado e
  testado;
- o schema, prompt, modelo ou versão da regra não estiver registrado;
- o custo integral projetado, o teto de gasto ou a regra de interrupção não
  estiver aprovado em G04;
- a revisão humana ainda não tiver sido realizada.
