# Batch de mapeamento e auditoria raw de G02 — 2026-07-25

## Autorizações e limites

Depois da aprovação integral do contrato humano de G02, o pesquisador
autorizou explicitamente:

- preparar e executar uma operação Batch para propor a disposição dos 23.786
  `field_id` no vocabulário canônico já congelado;
- executar a auditoria integral do `raw/` em modo somente leitura;
- reutilizar a `OPENAI_API_KEY` já presente no ambiente local, sem exibi-la ou
  incorporá-la aos artefatos.

Essas autorizações não incluem aplicar a proposta, normalizar registros,
implementar adaptadores, materializar Parquets nem alterar o `raw/`.

## Contrato Batch congelado

| Item | Valor |
|---|---|
| operação | `schema-field-mapping-batch-gpt56-20260725` |
| endpoint | `/v1/responses` |
| modelo | `gpt-5.6-sol` |
| raciocínio | `low` |
| janela | `24h` |
| caminhos | 23.786 |
| grupos de registros | 50 |
| requisições independentes | 99 |
| conflitos preservados | 543 |
| caminhos `senado/ccj_notas` | 20.523 |
| tokens de entrada contados | 1.353.952 |
| custo estimado apenas da entrada, sem cache | US$ 3,38488 |
| teto matemático com 32.000 tokens em cada saída | US$ 50,90488 |

Cada requisição recebeu:

- a mesma versão do vocabulário de 91 campos lógicos;
- o mesmo JSON Schema fechado;
- `field_id` existentes e o contexto estrutural do crosswalk;
- proibição explícita de inventar campo, aplicar mapeamento, fundir entidade,
  preencher valor ou modificar dados.

O modelo devolve somente uma disposição proposta por `field_id`. A expansão
de proveniência vem deterministicamente do crosswalk, e a ordem das respostas
não é usada: a reconciliação é feita por `custom_id`.

Hashes principais:

| Artefato/contrato | SHA-256 |
|---|---|
| crosswalk | `42413168597c1baa7b8a280c2c50968c7fe8acf0f702184b13cef947fb5f8dff` |
| proposta global aprovada | `e4e38d5ca9bee0c1e493ee95b990a2d113aeb00d8a0fe8a6db8200d877df92fe` |
| entrada Batch | `8324f63c588480014e152bed1a6458f83362fff8e700e52db56d56582a8c62af` |
| vocabulário congelado | `5862d87c7dd75ae037e21d399c31bce0546f965ce8aeb53acad89700cfa47745` |
| schema de resposta | `a3ea1bd129637204303b64054393f1c2ff63e514182160730acbb5567b5be086` |
| prompt | `5cd754b555e3e642b5ad59e5fdade7cc9bf6da17f0c5fa812dfb8c30176a04b1` |

## Tentativa rejeitada e correção

A primeira submissão, `batch_6a655fe188488190a729c50a19a3ef6c`,
foi rejeitada integralmente na validação, antes de processar qualquer
requisição. A API informou que o alias `gpt-5.6` não era aceito pelo Batch.
Foram zero requisições processadas e não houve mapeamento gerado.

O contrato foi corrigido para o identificador explícito `gpt-5.6-sol`, que a
documentação oficial declara compatível com Batch. A nova entrada foi
regerada, recontada e submetida sem reutilizar a tentativa inválida.

## Submissão válida

- Batch: `batch_6a6560b67d108190b7be8423e6e55906`
- arquivo de entrada: `file-9gZ9vR8Qucg3GGH2a8sERb`
- estado inicial: `validating`
- estado final da API: `completed`, com 99 respostas HTTP concluídas e zero
  falhas de transporte;
- proposta aplicada: `false`

Pasta preservada no Drive:
`falando_nela/auditoria/pipeline_dados_v3/g02/schema-field-mapping-batch-gpt56-20260725/attempt_002_gpt-5.6-sol`.

O validador local não confundiu conclusão HTTP com cobertura científica:

- 19.779 disposições passaram integralmente;
- 3.984 `field_id` foram omitidos por 10 respostas que devolveram somente
  uma ou sete disposições em vez do conjunto solicitado;
- 23 disposições adicionais violaram combinações do contrato: 15
  `alias_candidate` usaram operação direta ou `rename`, e 8
  `type_conflict_open` usaram `preserve_unmapped`;
- 4.007 IDs permaneceram, portanto, fora da cobertura validada;
- 13 das 99 requisições tiveram pelo menos uma pendência;
- nenhum `field_id` desconhecido ou duplicado foi aceito;
- o custo efetivo da primeira tentativa válida foi US$ 16,066915 para
  1.353.952 tokens de entrada e 845.469 tokens de saída, incluindo 62.242
  tokens de raciocínio.

A saída bruta e as 19.779 propostas válidas foram preservadas. As 23
combinações inválidas também foram arquivadas separadamente, sem correção
silenciosa. O gate ficou em `repair_required`; nada foi aplicado.

## Reparo incremental

O pesquisador autorizou reenviar até obter cobertura exata. Para não repetir
os 19.779 resultados válidos, foi criada a operação
`schema-field-mapping-batch-gpt56-20260725-repair-001` somente com os 4.007
IDs pendentes:

| Item | Valor |
|---|---|
| Batch | `batch_6a6565aebe008190a562302473110088` |
| arquivo de entrada | `file-94B7kYr5stWcxpGdjKZX7o` |
| requisições | 43 |
| tamanho máximo por requisição | 100 campos |
| tokens de entrada contados | 361.313 |
| custo da entrada sem cache | US$ 0,9032825 |
| teto matemático de entrada e saída | US$ 21,5432825 |
| SHA-256 da entrada | `4b449e33f52908331040fd1748e7eaa13465a3cbca50af602c1770049d86b978` |
| estado final | `completed_incomplete_coverage` |
| disposições válidas | 4.005 |
| custo efetivo | US$ 3,6864725 |

O reparo usa os mesmos hashes de vocabulário e JSON Schema da submissão
principal. Ele deixou dois IDs pendentes: uma disposição semanticamente
inválida para `F01575` e a omissão de `F05877`. A saída original foi
preservada, e nenhum dos dois resultados foi corrigido silenciosamente.

O segundo reparo,
`schema-field-mapping-batch-gpt56-20260725-repair-002`, enviou somente esses
dois IDs, em duas requisições de um campo:

| Item | Valor |
|---|---|
| Batch | `batch_6a656c92f3dc81908c4e008f436cb241` |
| arquivo de entrada | `file-XDJZN2PGUEUCnwzAYcBgtc` |
| tokens de entrada contados | 9.713 |
| custo da entrada sem cache | US$ 0,0242825 |
| teto matemático de entrada e saída | US$ 0,9842825 |
| SHA-256 da entrada | `45bfd9f7d327e2a80d8257ee5941998bd0a3a4b3f02df3935f8b3506f65dbb82` |
| estado final | `completed_validated` |
| disposições válidas | 2 |
| custo efetivo | US$ 0,0180515 |

## Reconciliação final do Batch

A união disjunta da tentativa principal e dos dois reparos provou:

- 23.786 `field_id` esperados;
- 23.786 `field_id` reconciliados e únicos;
- zero ausentes, desconhecidos ou duplicados;
- 99 + 43 + 2 requisições preservadas em suas tentativas;
- custo efetivo total de US$ 19,7714390;
- `proposal_applied=false`, `raw_mutated=false` e
  `normalization_materialized=false`;
- gate científico `needs_human_review`.

A distribuição das propostas reconciliadas é:

| Decisão proposta | Linhas |
|---|---:|
| `preserve_unmapped` | 11.777 |
| `map` | 10.948 |
| `type_conflict_open` | 536 |
| `needs_human_review` | 366 |
| `alias_candidate` | 159 |

As combinações entre decisão e operação passaram no contrato fechado. Todos
os 23.786 registros ainda têm `human_decision=nao_avaliado`; cobertura
completa significa apenas que existe uma proposta validada para cada
`field_id`, não que ela foi aceita. O conjunto reconciliado usa 82 dos 91
campos lógicos aprovados. Os nove campos sem candidato nesta rodada foram
preservados no vocabulário e não removidos:

- `committee_meeting_end_datetime`;
- `document_identifier_namespace`;
- `document_url_role`;
- `federative_unit_role`;
- `party_identifier_namespace`;
- `person_identifier_namespace`;
- `person_identifier_role`;
- `plenary_session_end_datetime`;
- `plenary_session_start_datetime`.

Em `senado/ccj_notas`, os 20.523 caminhos permanecem individualmente
visíveis: 9.751 receberam `map`, 9.750 `preserve_unmapped`, 533
`type_conflict_open`, 350 `needs_human_review` e 139 `alias_candidate`.
Nenhuma dessas propostas foi aplicada ou convertida em dado normalizado.

Artefatos finais:

- `mapeamentos_batch_propostos_reconciliados.csv`, 7.766.912 bytes,
  SHA-256
  `fa0386e6d47d7ec8964914b724ef716c4d409568d87d068683a71c04dbfe3852`;
- `batch_reconciliation_final.json`, 1.219 bytes, SHA-256
  `827ceeee3940e635e79d044d2b09c2029957b65f816e92fc4d0e98642523f1ef`;
- saídas brutas, erros semânticos, pendências, uso e custo de cada tentativa
  em pastas separadas no Drive.

## Auditoria integral do raw

A auditoria `schema-evidence-full-20260725` foi concluída no Colab, com o
Drive montado, usando:

- `data/raw` como entrada somente leitura;
- o inventário aprovado
  `raw-metadata-full-20260724t184418z`;
- 18 caminhos selecionados para auditoria estrutural;
- 9 comparações recorde a recorde, incluindo as sete famílias de duplicação
  técnica aprovadas, estado/notas de reunião e a rejeição do alias entre
  agenda e detalhe;
- saída temporária sob `/content`;
- cópia final para pasta de auditoria separada no Drive.

A execução começou em `2026-07-26T01:30:37+00:00`, terminou em
`2026-07-26T03:07:11+00:00` e registrou:

- `execution_status=succeeded` e `scientific_gate=needs_review`;
- fingerprint antes e depois idêntico:
  `7cd7fa0d9f7cec648187e8d2da857c8bdac8861ac6f476662ce6bb97d9730da2`;
- 1.148.740 registros legíveis relidos;
- 23.786 chaves únicas no livro, com cobertura bidirecional exata do
  inventário: zero ausentes e zero inventadas;
- 543 conflitos preservados: 540 em `senado/ccj_notas`, 1 em
  `senado/parlamentares` e 2 em `senado/plenario_discursos`;
- 20.523 caminhos de `senado/ccj_notas`, incluindo 18.868 sob coleções,
  sem coerção, achatamento ou identidade implícita de `[]`;
- 143 amostras estruturais, 6 previews `context_only` ainda não aprovados e
  5 pacotes estruturais não enviados;
- 9 comparações de alias, todas com decisão humana operacional ainda
  `nao_avaliado`;
- zero chamadas GPT nesta execução, zero propostas aplicadas, zero registros
  normalizados e zero escrita no raw.

Oito comparações de duplicação técnica tiveram sobreposição e igualdade
tipada de 100% em todos os registros preenchidos dos respectivos escopos. As
subárvores `agenda` e `detalhe`, corretamente tratadas como não alias,
coocorreram em 983 registros e divergiram em todos eles: igualdade de 0%.

### Reconciliação das rejeições

O primeiro artefato `linhas_rejeitadas.csv` localizou 9 coordenadas, embora
G01 registrasse 14 registros rejeitados. A causa foi rastreada: o inventário
contou todas as rejeições por arquivo, mas a lista de inconsistências
deduplicou avisos com a mesma severidade, tipo, arquivo e mensagem sem incluir
o número da linha. Cinco coordenadas do mesmo arquivo ficaram ausentes da
lista de avisos, embora continuassem contadas no inventário.

O raw não foi alterado e o artefato original não foi sobrescrito. A operação
suplementar
`schema-evidence-full-20260725-rejected-lines-reconciliation` releu somente
os seis arquivos marcados com rejeições, recalculou o fingerprint e produziu:

- 14 coordenadas únicas e 14 hashes de linha únicos;
- 14 rejeições esperadas e 14 reconciliadas;
- 5 coordenadas recuperadas da deduplicação de avisos;
- `linhas_rejeitadas_reconciliadas.csv`, 3.258 bytes, SHA-256
  `a1d06c5d011d1bdbefef9f0dbe4f2365b9b08715cb8d399b43e4f5fd22052c10`;
- `raw_writes=0`, `source_audit_mutated=false` e
  `normalized_records_materialized=0`.

A implementação passou a incluir número do registro e caminho do campo na
chave de inconsistência de G01 e a reconstruir as rejeições de G02 a partir
das contagens por arquivo. Testes cobrem múltiplas linhas inválidas com a
mesma mensagem no mesmo arquivo.

Pasta da auditoria:
`falando_nela/auditoria/pipeline_dados_v3/g02/schema-evidence-full-20260725`.

Os artefatos técnicos estão reconciliados e prontos para o gate humano. G02
continua pendente até a revisão e aprovação operacional do pesquisador. Nada
desta etapa altera arquivos raw. A síntese para decisão está em
`g02_gate_humano_operacional_20260726.md`.
