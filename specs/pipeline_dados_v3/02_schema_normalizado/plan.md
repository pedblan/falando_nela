# Plano — schema normalizado v3

## Estado

Specs aprovadas e ferramenta de evidências implementada em 2026-07-24.
Execução integral, piloto GPT real e G02 permanecem pendentes. Adaptadores e
materialização de registros normalizados continuam bloqueados.

## Regra de avanço

Este submódulo desenha o schema com evidências; não materializa a camada
normalizada. A implementação autorizada limita-se à ferramenta deste contrato.
Adaptadores e normalização continuam bloqueados até G02 e seus contratos
próprios.

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
- [ ] Localizar os sete artefatos de G01 e conferir seus hashes.
- [ ] Confirmar que o fingerprint do raw permanece igual ao de G01.
- [x] Implementar somente a ferramenta de evidências autorizada pelas specs.
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
- [ ] Registrar individualmente as 14 linhas rejeitadas.
- [ ] Produzir o relatório dos 543 conflitos de tipo.
- [ ] Produzir a trilha estrutural dos 20.523 caminhos de `senado/ccj_notas`.
- [ ] Gerar pares candidatos a duplicidade ou alias por sinais exatos.
- [ ] Executar a comparação recorde a recorde dos metadados preenchidos.
- [ ] Calcular contagens e taxas de coincidência para cada par candidato.
- [ ] Revisar humanamente pares concordantes, divergentes e sem evidência.
- [ ] Propor categorias somente a partir dos caminhos observados.
- [ ] Propor o tratamento explícito de ausência, nulo, vazio e conflito.
- [ ] Propor o vocabulário fechado de regras determinísticas.
- [ ] Gerar `schema_normalizado.schema.json`.
- [ ] Gerar os demais artefatos previstos para G02.
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

## Entregas desta etapa

Depois de implementada e executada com autorização, a etapa entregará:

- livro de decisões de todos os caminhos observados;
- schema lógico proposto;
- mapeamentos e regras propostos, ainda não aplicados;
- amostras estruturais e previews de contexto separados;
- propostas GPT declarativas com sua trilha de execução;
- avaliação A/B do efeito dos previews;
- auditoria recorde a recorde de duplicidades e aliases;
- relatório completo dos conflitos de tipo;
- trilha especial de `senado/ccj_notas`;
- registro das linhas rejeitadas;
- manifest e relatório para G02.

## Bloqueios mantidos

- Não implementar adaptadores por fonte antes de G02.
- Não materializar registros normalizados antes dos contratos seguintes.
- Não aplicar automaticamente propostas do GPT-5.6.
- Não enviar conteúdo parlamentar além dos previews `context_only` aprovados.
- Não usar preview como evidência de categoria, coluna ou alias.
- Não interpretar marcadores ou estruturas textuais com Python.
- Não alterar, corrigir ou regravar o raw.
- Não descartar nem fundir campos automaticamente.
