# Plano — schema normalizado v3

## Estado

Specs aprovadas e ferramenta de evidências implementada em 2026-07-24. G01 foi
revalidado no runtime do pesquisador, e dois pilotos exploratórios de 150 e
300 caminhos foram executados para orientar a ampliação. Eles não substituem
a avaliação A/B formal. O catálogo global `schema_core` foi executado; a
requisição final foi recontada em 692.031 tokens, incluindo o JSON Schema. A proposta
`gpt56-global-schema-proposal-v1` foi recebida, revisada por famílias e
aprovada conceitualmente pelo pesquisador em 2026-07-25. O Batch controlado
dos 23.786 `field_id` e dois reparos disjuntos
foram reconciliados em cobertura exata, com todas as propostas ainda não
avaliadas humanamente e não aplicadas. A auditoria integral do raw terminou
em modo somente leitura, e seus artefatos técnicos, inclusive as 14 rejeições,
foram reconciliados. O gate humano final de G02 permanece pendente.
Adaptadores, aplicação das propostas e materialização de registros
normalizados continuam bloqueados.

A síntese dos resultados técnicos e das decisões ainda necessárias está em
`g02_gate_humano_operacional_20260726.md`.

## Regra de avanço

Este submódulo desenha o schema com evidências; não materializa a camada
normalizada. A implementação autorizada limita-se à ferramenta deste contrato.
A aprovação de 2026-07-25 fecha o subgate humano do vocabulário conceitual,
mas não substitui a cobertura e as validações do gate G02. Adaptadores e
normalização continuam bloqueados até a aprovação operacional de G02 e de
seus contratos próprios.

## Sequência

- [x] Registrar G01 aprovado para `raw-metadata-full-20260724t184418z`.
- [x] Fixar nas specs os totais de 14 rejeições, 543 conflitos e 20.523 caminhos de `senado/ccj_notas`.
- [x] Separar normalização determinística de interpretação da estrutura textual.
- [x] Especificar auditoria de aliases recorde a recorde sem fusão automática.
- [x] Especificar uso restrito do GPT-5.6 para propor categorias de metadados.
- [x] Admitir categorias oficiais das APIs somente como evidência semântica secundária.
- [x] Especificar samples estruturais e previews textuais `context_only`.
- [x] Especificar avaliação A/B do benefício dos previews.
- [x] Revisar e aprovar `requirements.md`.
- [x] Revisar e aprovar `validation.md`.
- [x] Revisar e aprovar `tech-stack.md`.
- [x] Revisar e aprovar este plano.
- [x] Localizar os sete artefatos de G01 e conferir seus hashes.
- [x] Confirmar que o fingerprint do raw permanece igual ao de G01.
- [x] Implementar somente a ferramenta de evidências autorizada pelas specs.
- [x] Executar pilotos exploratórios de 150 e 300 caminhos para avaliar o formato de proposta.
- [x] Concluir que lotes independentes não fornecem visão semântica global ao modelo.
- [x] Especificar uma chamada global com arquivo seguida de mapeamento por vocabulário congelado.
- [x] Implementar catálogo TXT reversível e crosswalk dos caminhos originais.
- [x] Implementar amostragem segura `context_only` e reforçada para `senado/ccj_notas`.
- [x] Implementar perfil `schema_core` com estatísticas compactas e crosswalk integral.
- [x] Integrar ao caderno o upload `user_data` e a contagem exata de tokens.
- [x] Gerar e contar uma primeira versão integral do catálogo no runtime atual.
- [x] Confirmar 23.786 caminhos, 543 conflitos e 20.523 caminhos de `senado/ccj_notas`.
- [x] Reduzir as amostras `context_only` para 150 sem alterar os caminhos.
- [x] Gerar o catálogo integral com o perfil `schema_core`.
- [x] Fazer upload do TXT e contar arquivo + prompt do payload global.
- [x] Registrar a medição preliminar de 691.302 tokens para arquivo + prompt.
- [x] Autorizar humanamente uma chamada global com teto estimado de US$ 10,10.
- [x] Implementar submissão única em background e retomada pelo `response_id`.
- [x] Implementar continuação por CLI para o runtime Colab já aberto.
- [x] Recontar 692.031 tokens na requisição exata com o JSON Schema de saída.
- [x] Executar uma única chamada para propor o vocabulário global.
- [x] Revisar e congelar humanamente o vocabulário global.
- [x] Revisar individualmente os 40 candidatos canônicos da proposta global.
- [x] Acrescentar e aprovar as famílias temáticas omitidas de indexação de fala e assuntos de proposição.
- [x] Decidir as oito hipóteses de alias da proposta global.
- [x] Aprovar o modelo conceitual polimórfico de `senado/ccj_notas` em dez blocos.
- [x] Aprovar as coordenadas técnicas de registro e valor e a política de indexação.
- [x] Registrar que a disposição física, inclusive eventual Parquet, pertence a G03/G05.
- [x] Preparar Batch somente para mapear `field_id` com o vocabulário congelado.
- [x] Contar a entrada Batch exata e confirmar o limite conservador antes da submissão.
- [x] Preservar a tentativa rejeitada com o alias `gpt-5.6`.
- [x] Submeter a tentativa válida com o identificador explícito `gpt-5.6-sol`.
- [x] Detectar 4.007 IDs sem disposição válida na primeira saída concluída.
- [x] Preparar e submeter reparo disjunto em blocos de até 100 IDs.
- [x] Preservar e validar a saída final da tentativa Batch válida.
- [x] Reconciliar uma proposta de disposição para todos os 23.786 `field_id`.
- [ ] Cobrir os 23.786 caminhos no livro de decisões.
- [ ] Catalogar categorias e definições relevantes das APIs oficiais.
- [ ] Montar pacotes GPT apenas com evidências de metadados permitidas.
- [x] Implementar a seleção determinística de amostras estruturais.
- [x] Implementar a seleção limitada de previews `context_only`.
- [ ] Revisar humanamente os previews antes de qualquer envio.
- [ ] Aprovar o prompt e o JSON Schema fechado das propostas GPT.
- [ ] Executar a condição A do piloto sem previews textuais.
- [ ] Executar a condição B do piloto com previews `context_only`.
- [ ] Comparar as condições A e B com métricas pareadas.
- [ ] Revisar validade, utilidade, tokens e custo do piloto GPT.
- [ ] Decidir se os previews permanecerão após o piloto.
- [ ] Autorizar ou rejeitar a ampliação das propostas GPT.
- [x] Registrar individualmente as 14 linhas rejeitadas.
- [x] Produzir o relatório dos 543 conflitos de tipo.
- [x] Produzir a trilha estrutural dos 20.523 caminhos de `senado/ccj_notas`.
- [x] Gerar pares candidatos a duplicidade ou alias por sinais exatos.
- [x] Executar a comparação recorde a recorde dos metadados preenchidos.
- [x] Calcular contagens e taxas de coincidência para cada par candidato.
- [ ] Revisar humanamente pares concordantes, divergentes e sem evidência.
- [x] Propor categorias somente a partir dos caminhos observados.
- [x] Propor o tratamento explícito de ausência, nulo, vazio e conflito.
- [ ] Propor o vocabulário fechado de regras determinísticas.
- [x] Implementar o gerador de `schema_normalizado.schema.json` com o contrato conceitual aprovado.
- [x] Gerar `schema_normalizado.schema.json` na execução integral de G02.
- [x] Gerar os demais artefatos previstos para G02.
- [ ] Executar todas as validações de `validation.md`.
- [ ] Revisar o relatório integral e a proveniência por valor.
- [ ] Registrar aprovação ou rejeição de G02.

## Gates internos

| Gate | Pergunta |
|---|---|
| S01 | Os artefatos e totais correspondem exatamente ao inventário aprovado? |
| S02 | Todo caminho observado possui decisão explícita e proveniência? |
| S03 | Toda categoria de domínio possui evidência preenchida no raw? |
| S04 | A auditoria de aliases é recorde a recorde e não decide fusões? |
| S05 | Os 543 conflitos permanecem visíveis e tratados individualmente? |
| S06 | `senado/ccj_notas` preserva hierarquia, tipos e multiplicidade? |
| S07 | As 14 rejeições continuam localizadas e reconciliadas? |
| S08 | Python não inferiu informação lendo texto? |
| S09 | Toda proposta GPT cita evidências observadas e permanece não aplicada? |
| S10 | Todo preview está limitado, aprovado e rotulado `context_only`? |
| S11 | A avaliação A/B mostra se os previews agregam qualidade proporcional ao custo? |
| S12 | Marcadores e estruturas textuais foram integralmente adiados? |
| S13 | O pesquisador aprovou categorias, nulos, regras e proveniência em G02? |
| S14 | O catálogo global reconstrói exatamente os 23.786 caminhos? |
| S15 | O arquivo e o prompt cabem numa única chamada sem truncamento? |
| S16 | Batch apenas aplica um vocabulário global já revisado e congelado? |
| S17 | A revisão humana de 2026-07-25 está incorporada nas quatro specs sem fechar indevidamente G02? |

## Entregas desta etapa

Depois de implementada e executada com autorização, a etapa entregará:

- livro de decisões de todos os caminhos observados;
- schema lógico proposto;
- mapeamentos e regras propostos, ainda não aplicados;
- amostras estruturais e previews de contexto separados;
- propostas GPT declarativas com sua trilha de execução;
- avaliação A/B do efeito dos previews;
- catálogo global TXT, crosswalk, amostras e recibo de contagem;
- proposta de vocabulário global e decisão humana de 2026-07-25 preservadas;
- auditoria recorde a recorde de duplicidades e aliases;
- relatório completo dos conflitos de tipo;
- trilha especial de `senado/ccj_notas`;
- registro das linhas rejeitadas;
- manifest e relatório para G02.

## Bloqueios mantidos

- Não implementar adaptadores por fonte antes da aprovação operacional de G02.
- Não materializar registros normalizados antes dos contratos seguintes.
- Não aplicar automaticamente propostas do GPT-5.6.
- Não enviar conteúdo parlamentar além dos previews `context_only` aprovados.
- Não usar preview como evidência de categoria, coluna ou alias.
- Não interpretar marcadores ou estruturas textuais com Python.
- Não alterar, corrigir ou regravar o raw.
- Não descartar nem fundir campos automaticamente.
