# Gate humano operacional de G02 — 2026-07-26

## Estado

As execuções técnicas autorizadas estão concluídas e reconciliadas. G02
permanece pendente de decisão humana. Nenhum mapeamento foi aplicado, nenhum
registro normalizado foi materializado, nenhum Parquet foi criado e o raw não
foi alterado.

## Evidências prontas para revisão

### Cobertura e proveniência

- 23.786 chaves no inventário;
- 23.786 chaves únicas no livro de campos;
- cobertura bidirecional exata: zero ausentes e zero inventadas;
- 23.786 propostas Batch únicas, todas com
  `human_decision=nao_avaliado`;
- fonte, dataset, `record_type`, caminho original, tipos e estados observados
  preservados em cada proposta;
- 23.768 linhas do livro ainda com papel semântico `unknown`, porque a
  auditoria não converteu proposta do modelo em decisão humana.

### Batch

| Decisão proposta | Linhas |
|---|---:|
| `map` | 10.948 |
| `preserve_unmapped` | 11.777 |
| `type_conflict_open` | 536 |
| `needs_human_review` | 366 |
| `alias_candidate` | 159 |

A tentativa principal e dois reparos disjuntos custaram US$ 19,7714390. O
conjunto usa 82 dos 91 campos lógicos aprovados. Os nove campos sem candidato
permanecem no vocabulário; ausência de candidato não os remove.

### Aliases e duplicações técnicas

Oito comparações de duplicação técnica tiveram sobreposição e igualdade JSON
tipada de 100% nos escopos preenchidos:

- Câmara, pareceres de PEC, texto: 8.100 de 8.100;
- Câmara, CCJC, ID do evento: 961 de 961;
- Câmara, CCJC, texto: 961 de 961;
- Senado, CCJ, texto: 983 de 983;
- Senado, CCJ, ID da reunião em notas: 983 de 983;
- Senado, CCJ, ID da reunião em status: 467 de 467;
- Senado, Congresso, ID de pronunciamento: 3.984 de 3.984;
- Senado, Plenário, ID de pronunciamento: 156.626 de 156.626.

Agenda e detalhe da CCJ coocorreram em 983 registros e divergiram em todos:
igualdade 0%. Isso sustenta a decisão conceitual de tratá-los como
observações distintas da mesma reunião, não como aliases.

Os nove registros de auditoria continuam com
`human_decision=nao_avaliado`. A recomendação operacional é confirmar as
oito duplicações técnicas somente nos escopos medidos e confirmar
agenda/detalhe como não alias, sempre preservando ambas as linhagens.

### Conflitos e `senado/ccj_notas`

- 543 conflitos preservados individualmente;
- 540 em `senado/ccj_notas`, 1 em `senado/parlamentares` e 2 em
  `senado/plenario_discursos`;
- 535 combinações `array|object` e 8 `array|string`;
- 20.523 caminhos de `senado/ccj_notas`;
- 18.868 caminhos sob coleções;
- nenhum achatamento, coerção por tipo majoritário ou uso de `[]` como
  identidade.

A recomendação operacional é manter os 543 conflitos como abertos para
regras humanas posteriores e aprovar a trilha especial de
`senado/ccj_notas` como evidência estrutural, sem convertê-la ainda em layout
físico.

### Rejeições e imutabilidade

A auditoria original localizou 9 das 14 rejeições porque a lista de
inconsistências de G01 deduplicava mensagens iguais no mesmo arquivo sem usar
o número da linha. A contagem por arquivo continuava correta.

O suplemento imutável reconciliou:

- 14 registros rejeitados esperados;
- 14 coordenadas únicas;
- 14 hashes de linha únicos;
- 5 coordenadas recuperadas da deduplicação;
- fingerprint antes e depois igual a
  `7cd7fa0d9f7cec648187e8d2da857c8bdac8861ac6f476662ce6bb97d9730da2`.

A implementação foi corrigida para incluir número de registro e caminho do
campo na chave de inconsistência. O raw e a auditoria original permanecem
inalterados.

## Limites preservados

- `proposal_applied=false`;
- `raw_mutated=false`;
- `normalization_materialized=false`;
- previews `context_only` não aprovados e não enviados;
- zero chamada GPT na auditoria raw;
- nenhuma inferência de marcador, orador, turno ou estrutura textual;
- nenhuma definição de Parquet, partição ou índice físico;
- G03 não iniciado.

## Decisão solicitada

Para fechar G02 operacionalmente, o pesquisador deverá:

1. aprovar ou pedir revisão das evidências de cobertura e proveniência;
2. confirmar ou pedir revisão das nove decisões de alias;
3. aprovar ou pedir revisão da preservação dos 543 conflitos;
4. aprovar ou pedir revisão da trilha de `senado/ccj_notas`;
5. aprovar ou pedir revisão da reconciliação das 14 rejeições;
6. decidir o destino das propostas `map`, `preserve_unmapped`,
   `type_conflict_open`, `needs_human_review` e `alias_candidate`.

Até essa decisão, G02 permanece aberto e os submódulos seguintes continuam
bloqueados.
