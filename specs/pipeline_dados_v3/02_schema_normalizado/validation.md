# Validação — schema normalizado v3

## Estado

Contrato aprovado. Os testes sintéticos da implementação estão concluídos;
validações que dependem da execução integral aprovada, do piloto real ou de
revisão humana permanecem pendentes.

## Pré-condições

- G01 está aprovado para `raw-metadata-full-20260724t184418z`.
- O diretório dos artefatos aprovados é fornecido explicitamente.
- Os hashes das seis saídas conferem com o `manifest.json`; o hash do próprio
  manifest confere com o SHA-256 aprovado fixado em G01 e na implementação.
- O fingerprint estrutural do `raw/` continua igual ao registrado em G01.
- Nenhum coletor está escrevendo na raiz durante a auditoria recorde a recorde.
- Estas quatro specs foram aprovadas pelo pesquisador responsável.

## Validação da entrada

- [ ] V02-01 — Verificar `operation_id`, versão do inventário e commit registrados no manifest.
- [ ] V02-02 — Recalcular e conferir os hashes dos sete artefatos de G01.
- [ ] V02-03 — Confirmar `1.148.754 = 1.148.740 + 14`.
- [ ] V02-04 — Confirmar 50 grupos `fonte × dataset × record_type`.
- [ ] V02-05 — Confirmar 23.786 caminhos no inventário de campos.
- [ ] V02-06 — Confirmar 543 conflitos de tipo.
- [ ] V02-07 — Confirmar a distribuição `540 + 1 + 2` dos conflitos.
- [ ] V02-08 — Confirmar 20.523 caminhos em `senado/ccj_notas`.

Qualquer divergência bloqueia a etapa. A implementação não poderá
escolher silenciosamente outro inventário nem reconstruir números a partir de
artefatos v1/v2.

## Cobertura do livro de decisões

Para a chave:

```text
fonte + dataset + record_type + caminho_de_campo_original
```

deverão valer:

```text
linhas únicas no livro de decisões = 23.786
chaves ausentes do inventário = 0
chaves inventadas = 0
chaves do inventário sem decisão = 0
```

- [ ] V02-09 — Validar unicidade das 23.786 chaves.
- [ ] V02-10 — Validar cobertura bidirecional entre inventário e livro de decisões.
- [ ] V02-11 — Exigir justificativa humana para todo `fora_do_schema_proposto`.
- [ ] V02-12 — Confirmar que nenhuma decisão remove caminho ou proveniência.

## Rastreabilidade do schema

Toda categoria de domínio deverá possuir ao menos uma evidência observada.
Campos técnicos de controle deverão estar rotulados separadamente.

- [ ] V02-13 — Rejeitar categoria de domínio sem caminho no inventário aprovado.
- [ ] V02-14 — Rejeitar mapeamento sem fonte, dataset, `record_type` e caminho original.
- [ ] V02-15 — Rejeitar mapeamento sem estado de presença e tipos observados.
- [ ] V02-16 — Rejeitar regra sem identificador, versão e domínio de entrada.
- [ ] V02-17 — Rejeitar prioridade, descarte ou fusão sem decisão humana explícita.
- [ ] V02-18 — Confirmar que schemas v1/v2 não aparecem como fonte de evidência.

## Presença, nulos e falhas

Em cada universo de registros comparável:

```text
registros
= campo ausente
+ presente nulo
+ presente vazio
+ presente preenchido
```

As 14 rejeições permanecem fora dessa equação de presença porque não foram
interpretadas como registros, mas entram na reconciliação global da leitura.

- [ ] V02-19 — Reconciliar presença para todo campo selecionado.
- [ ] V02-20 — Demonstrar que metadado não preenchido nunca gera valor normalizado.
- [ ] V02-21 — Manter tipo original de strings, objetos e coleções vazias.
- [ ] V02-22 — Preservar as 14 rejeições por arquivo, linha e hash.
- [ ] V02-23 — Confirmar que nenhuma rejeição foi reparada ou descartada.

## Auditoria recorde a recorde de aliases

### Mesma unidade raw

Cada linha de `auditoria_aliases.csv` deverá declarar:

- escopo do par;
- caminhos `A` e `B`;
- tipos observados;
- `U`, `AB`, `E`, `D`, `SA` e `SB`;
- quatro taxas ou `nao_aplicavel`;
- comparador e eventual `rule_id`;
- quantidade de nulos, vazios e ausentes;
- decisão humana.

As identidades deverão satisfazer:

```text
U  = AB + SA + SB
AB = E + D
0 <= taxa <= 1
```

Quando `AB > 0`:

```text
taxa_coincidencia = E / AB
```

Quando `U > 0`:

```text
taxa_sobreposicao = AB / U
taxa_so_a = SA / U
taxa_so_b = SB / U
```

- [ ] V02-24 — Recalcular as contagens diretamente dos registros legíveis.
- [x] V02-25 — Recalcular as taxas sem tratar ausente, nulo ou vazio como igualdade.
- [x] V02-26 — Confirmar igualdade basal por valor JSON tipado e exato.
- [ ] V02-27 — Separar qualquer taxa transformada da taxa exata.
- [x] V02-28 — Registrar `nao_aplicavel` em toda divisão por zero.
- [x] V02-29 — Amostrar coordenadas de registros concordantes e divergentes.
- [x] V02-30 — Confirmar que Python não atribuiu o estado humano `confirmado`.

As amostras de coordenadas não deverão reproduzir texto longo. Elas poderão
guardar hashes dos valores e referência ao registro para revisão controlada.

### Registros distintos

Para comparações entre tipos de registro, a validação deverá provar:

- chave de vínculo composta apenas por metadados preenchidos;
- regra de vínculo explícita e determinística;
- unicidade em cada lado;
- contagem de pares vinculados;
- contagem de registros sem par;
- contagem de chaves duplicadas ou ambíguas.

- [x] V02-31 — Rejeitar taxa entre registros sem vínculo aprovado.
- [x] V02-32 — Rejeitar vínculo que dependa de conteúdo textual.
- [x] V02-33 — Marcar chaves não únicas como ambíguas, sem escolher um registro.

### Testes mínimos da implementação

- par sempre igual e sempre preenchido;
- par sempre divergente;
- preenchimento complementar sem sobreposição;
- ausência, nulo, string vazia, objeto vazio e array vazio;
- tipos técnicos diferentes;
- chave de vínculo um-para-um;
- chave de vínculo duplicada;
- par sem registros com ambos preenchidos;
- comparação repetida com resultado idêntico;
- texto longo representado somente por coordenada e hash.

- [x] V02-34 — Executar os testes sintéticos de métricas e vínculos.
- [x] V02-35 — Executar duas vezes a mesma auditoria e comparar hashes das saídas.

## Conflitos de tipo

O relatório deverá ter exatamente 543 chaves conflitantes provenientes do
inventário aprovado.

- [ ] V02-36 — Reconciliar 540 conflitos em `senado/ccj_notas`.
- [ ] V02-37 — Reconciliar 1 conflito em `senado/parlamentares`.
- [ ] V02-38 — Reconciliar 2 conflitos em `senado/plenario_discursos`.
- [ ] V02-39 — Exigir uma decisão ou o estado `conflito_aberto` para cada chave.
- [x] V02-40 — Bloquear coerção pelo tipo majoritário.
- [x] V02-41 — Bloquear serialização automática de objeto ou array como string.

## Trilha especial de `senado/ccj_notas`

- [ ] V02-42 — Cobrir os 20.523 caminhos no relatório específico.
- [ ] V02-43 — Segmentar as métricas por `record_type` e contexto estrutural.
- [x] V02-44 — Preservar multiplicidade e ordem das coleções.
- [x] V02-45 — Demonstrar que `[]` não foi usado como identidade de elemento.
- [ ] V02-46 — Manter variantes `array|object` separadas ou explicitamente unidas.
- [ ] V02-47 — Quantificar estruturas sem identidade determinística de elemento.
- [ ] V02-48 — Impedir que limites operacionais reduzam silenciosamente a cobertura.

## Validação das propostas GPT-5.6

As chamadas ao modelo serão válidas somente quando:

- o pacote separar evidências estruturais e previews `context_only`;
- todo caminho citado existir no inventário aprovado;
- toda referência à API oficial registrar URL e data ou versão;
- a resposta obedecer ao JSON Schema fechado;
- o modelo solicitado e o identificador resolvido estiverem registrados;
- prompt, schema e entrada tiverem versão ou hash;
- uso, latência, custo, erro e recusa permanecerem auditáveis;
- nenhuma proposta for aplicada automaticamente.

- [x] V02-49 — Validar o JSON Schema fechado das propostas GPT.
- [x] V02-50 — Rejeitar toda referência a caminho ausente do inventário.
- [x] V02-51 — Registrar modelo, prompt, schema, entrada, resposta, uso e custo.
- [x] V02-52 — Preservar respostas inválidas, recusas e erros sem aplicar fallback.
- [x] V02-53 — Confirmar que nenhuma proposta GPT alterou o livro de decisões automaticamente.

## Validação das amostras

Para cada grupo `fonte × dataset × record_type`, a seleção estrutural deverá
ser reproduzível a partir do raw e de sua configuração.

- [x] V02-54 — Reexecutar a seleção e reproduzir as mesmas coordenadas e hashes.
- [x] V02-55 — Confirmar até três papéis distintos por grupo quando disponíveis.
- [ ] V02-56 — Confirmar justificativa para amostras adicionais de `senado/ccj_notas`.
- [x] V02-57 — Preservar estrutura, tipos, coordenada e motivo de seleção.
- [x] V02-58 — Substituir todo texto longo nas amostras `evidence` por tamanho e hash.

Cada preview textual deverá satisfazer:

```text
context_only = true
0 <= inicio < fim <= tamanho_integral
fim - inicio <= 500 caracteres Unicode
```

- [x] V02-59 — Confirmar no máximo um preview por grupo textual por padrão.
- [ ] V02-60 — Exigir justificativa para todo segundo preview do mesmo grupo.
- [x] V02-61 — Confirmar seleção por comprimento e estrutura, sem leitura semântica.
- [x] V02-62 — Conferir trecho, posições, tamanho, hash e coordenada raw.
- [ ] V02-63 — Submeter o conjunto de previews à aprovação humana antes do envio.

O validador das propostas deverá exigir ao menos um `evidence_id` estrutural
válido para cada categoria, coluna ou possível alias. `context_ref` será
opcional e nunca satisfará essa exigência.

- [x] V02-64 — Rejeitar proposta sustentada apenas por `context_ref`.
- [x] V02-65 — Rejeitar preview citado como origem de valor normalizado.

O piloto deverá incluir os grupos de registro previstos, campos com alta e
baixa cobertura, aliases candidatos, conflitos de tipo e um estrato próprio de
`senado/ccj_notas`. A ampliação dependerá de revisão humana da validade,
utilidade, custo e taxa de evidência insuficiente.

- [ ] V02-66 — Revisar humanamente o piloto antes de ampliar as chamadas.

## Avaliação A/B dos previews

As condições A e B deverão compartilhar modelo resolvido, parâmetros, prompt,
JSON Schema, ordem e evidências. A única diferença permitida será a presença
dos previews `context_only` na condição B.

A comparação registrará:

- propostas aceitas após revisão;
- categorias propostas sem evidência válida;
- aliases propostos incorretamente;
- respostas com evidência insuficiente;
- tokens de entrada, cache, saída e raciocínio quando informados;
- latência e custo calculado.

- [x] V02-67 — Confirmar equivalência pareada das condições exceto pelos previews.
- [ ] V02-68 — Revisar as propostas sem revelar ao avaliador a condição quando viável.
- [x] V02-69 — Calcular métricas de qualidade, tokens, latência e custo por condição.
- [ ] V02-70 — Registrar decisão humana sobre manter ou remover os previews.

## Separação textual

Inspeções estáticas, validação dos pacotes e testes instrumentados deverão
demonstrar:

- conteúdo parlamentar fora dos previews `context_only` aprovados: zero;
- previews usados como evidência de coluna, preenchimento ou alias: zero;
- extrações semânticas por regex: zero;
- busca aproximada, embeddings ou NLP: zero;
- preenchimentos de metadado a partir de texto: zero;
- marcadores, oradores, turnos e fronteiras produzidos: zero.

- [x] V02-71 — Auditar conteúdo parlamentar fora dos previews aprovados.
- [x] V02-72 — Auditar regras Python para impedir leitura semântica de texto.
- [x] V02-73 — Confirmar que os previews não geraram marcadores ou metadados.
- [x] V02-74 — Confirmar adiamento de marcadores aos planos JSON textuais do GPT-5.6.

## Proveniência e reversibilidade

Para cada mapeamento proposto, uma amostra estratificada deverá:

1. localizar o arquivo e o registro raw;
2. resolver o caminho original;
3. recuperar o valor e o tipo originais;
4. reaplicar a regra declarada;
5. reproduzir exatamente o valor normalizado proposto.

- [ ] V02-75 — Validar o percurso completo para todos os grupos de registro.
- [ ] V02-76 — Incluir conflitos, nulos, vazios e falhas na amostra.
- [ ] V02-77 — Registrar toda falha de percurso sem fallback.

## Invariantes operacionais

- Escritas sob `data/raw/`: zero.
- Alterações no fingerprint do raw: zero.
- Registros normalizados materializados: zero.
- Campos fundidos automaticamente: zero.
- Campos descartados automaticamente: zero.
- Categorias de domínio sem evidência: zero.
- Regras Python que inferem por texto: zero.
- Propostas GPT aplicadas sem decisão humana: zero.
- Chamadas GPT sem trilha completa: zero.
- Previews sem `context_only=true`: zero.
- Propostas sustentadas somente por preview: zero.

- [ ] V02-78 — Verificar os invariantes antes de abrir G02.

## Gate G02

Sucesso técnico não aprova o schema. G02 só poderá ser aprovado quando o
pesquisador responsável revisar:

- o schema lógico proposto;
- a cobertura dos 23.786 caminhos;
- as decisões sobre nulos e vazios;
- a auditoria de aliases e suas divergências;
- o piloto GPT, suas propostas, falhas, utilidade, tokens e custo;
- a avaliação A/B dos previews `context_only`;
- todos os 543 conflitos;
- o relatório especial de `senado/ccj_notas`;
- o registro das 14 linhas rejeitadas;
- a proveniência e as regras determinísticas propostas.

- [ ] V02-79 — Registrar aprovação ou rejeição humana de G02.

Sem G02 aprovado, permanecem bloqueados os adaptadores por fonte e qualquer
implementação de normalização.
