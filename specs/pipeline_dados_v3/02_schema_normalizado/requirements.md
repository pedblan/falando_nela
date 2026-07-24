# Requisitos — schema normalizado v3

## Estado

Specs aprovadas e implementação da ferramenta de evidências autorizada pelo
pesquisador responsável em 2026-07-24. A autorização não inclui aplicar o
schema, gerar dados normalizados, alterar o `raw/`, ampliar chamadas GPT após
o piloto ou iniciar os submódulos seguintes.

O único inventário aceito como evidência estrutural é
`raw-metadata-full-20260724t184418z`, aprovado em G01 em 2026-07-24.

## Objetivo

Definir o contrato lógico do schema normalizado v3 e o método auditável para
propor suas categorias a partir exclusivamente dos metadados estruturados
observados no inventário aprovado.

O submódulo deverá produzir uma proposta de schema e suas evidências. Ele não
aplicará o schema ao corpus.

## Universo vinculante

O contrato deverá reconciliar estes números do inventário integral:

| Unidade | Quantidade |
|---|---:|
| registros observados | 1.148.754 |
| registros legíveis | 1.148.740 |
| linhas rejeitadas | 14 |
| grupos `fonte × dataset × record_type` | 50 |
| caminhos de campo | 23.786 |
| conflitos de tipo | 543 |
| caminhos em `senado/ccj_notas` | 20.523 |

Os 543 conflitos de tipo se distribuem em:

- 540 em `senado/ccj_notas`;
- 1 em `senado/parlamentares`;
- 2 em `senado/plenario_discursos`.

As 14 linhas rejeitadas pertencem a seis arquivos de metadata. Elas não
fornecem campos legíveis para o desenho do schema, mas continuam pertencendo
ao universo de entrada e deverão permanecer localizadas e reconciliadas.

## Fontes de evidência permitidas

- Os sete artefatos da operação aprovada: seis saídas com hashes conferidos
  contra o `manifest.json` e o próprio manifest conferido contra seu SHA-256
  aprovado, fornecido separadamente.
- Os 1.148.740 registros legíveis do `raw/`, somente para confirmar presença,
  tipo, igualdade e proveniência recorde a recorde.
- A nomenclatura, as categorias e as definições publicadas pelas APIs oficiais
  da Câmara e do Senado, sempre com URL, versão ou data de consulta.
- Decisões humanas explicitamente registradas durante G02.

A documentação oficial das APIs será fonte semântica secundária. Ela poderá
explicar ou nomear um caminho realmente observado, mas não poderá criar coluna
ausente do inventário, preencher valor ausente nem prevalecer sobre o payload
raw divergente. Campo documentado e não observado será registrado como
`nao_observado`, fora do schema proposto.

Código de coletores, schemas arquivados v1/v2, derivados antigos, nomes
esperados por análises futuras e conteúdo parlamentar não poderão servir de
evidência para criar categorias de domínio.

Campos técnicos de controle, como versão do schema, coordenadas do registro e
identificador da regra, poderão ser definidos pelo contrato. Eles deverão ser
marcados como controle de proveniência, e não como categoria observada no raw.

## Identidade e estados

Um campo de origem será identificado, no mínimo, por:

```text
fonte + dataset + record_type + caminho_de_campo_original
```

O tipo técnico observado e o contexto estrutural serão atributos dessa
identidade; um conflito de tipo não criará silenciosamente outro campo.

Cada ocorrência deverá preservar a coordenada do registro:

```text
caminho relativo do arquivo + número do registro
```

Para JSONL/NDJSON, o número do registro deverá continuar localizando a linha
física observada. Para outro formato, a convenção exata deverá ser declarada.

Os estados serão distintos:

- ausente;
- presente nulo;
- presente vazio;
- presente preenchido;
- rejeitado antes do parse.

String vazia, objeto vazio e coleção vazia poderão compartilhar o estado
`presente vazio`, mas o tipo técnico original deverá continuar preservado.

## Contrato de evidências e decisões

Deverá existir um livro de decisões com uma linha para cada um dos 23.786
caminhos inventariados. Nenhum caminho poderá desaparecer por não ter sido
selecionado para o schema.

Estados mínimos de decisão:

- `nao_avaliado`;
- `candidato`;
- `mapeado`;
- `preservado_sem_normalizacao`;
- `adiado_para_estrutura_textual`;
- `conflito_aberto`;
- `fora_do_schema_proposto`.

`fora_do_schema_proposto` não significa descarte: exige justificativa humana e
continua preservando caminho original, métricas do inventário e proveniência.

Cada categoria de domínio proposta deverá apontar para ao menos um caminho
preenchido do inventário aprovado. A evidência registrará:

- nome e versão da categoria;
- tipo lógico e cardinalidade;
- fonte, dataset e `record_type`;
- caminho original;
- tipos técnicos observados;
- cobertura e estados de presença;
- regra proposta;
- decisão humana e sua data.

## Limites da normalização determinística

Python poderá, em implementação futura e somente após aprovação:

- transportar metadados preenchidos;
- renomear um campo por mapeamento explícito;
- converter tipos por regra determinística, total e testada;
- padronizar valores por tabela fechada e versionada;
- calcular campos técnicos de proveniência;
- validar invariantes e registrar falhas.

Cada regra deverá ter identificador, versão, domínio de entrada, saída,
condições de erro e exemplos observados.

Python não poderá:

- preencher uma categoria quando o metadado de origem estiver ausente, nulo ou
  vazio;
- escolher entre campos por interpretação do texto;
- extrair informação de conteúdo parlamentar, cabeçalho, nota editorial ou
  transcrição;
- descobrir marcadores, separadores, oradores, papéis, seções ou turnos;
- usar regex, busca aproximada, vocabulário ou heurística para interpretar
  estrutura textual;
- transformar silenciosamente um tipo conflitante;
- reutilizar uma regra v1/v2 sem nova evidência e aprovação.

Uma regra poderá comparar ou transformar uma string de metadado somente quando
o campo e a operação forem aprovados explicitamente. Isso não autoriza ler
texto livre para inferir informação.

## Proveniência por valor

Todo valor normalizado futuro deverá conservar:

- valor original e tipo técnico original;
- valor normalizado e tipo lógico;
- fonte, dataset e `record_type`;
- caminho de campo original;
- caminho relativo do arquivo e número do registro;
- método `python_regra_aprovada`;
- identificador e versão da regra;
- estado de validação;
- decisão sobre revisão humana.

Valores não mapeados e falhas de regra continuarão auditáveis. Nenhum campo
será descartado, fundido, sobrescrito ou escolhido como prioridade
automaticamente.

## Auditoria de duplicidades e aliases

A auditoria procurará campos potencialmente duplicados ou aliases sem
pressupor que nomes parecidos tenham o mesmo significado.

### Geração de candidatos

Python poderá gerar pares candidatos por sinais estruturais e exatos:

- mesma chave terminal no caminho;
- mesmo escopo `fonte × dataset × record_type` e tipos comparáveis;
- ocorrência de valores tipados exatamente iguais;
- par incluído explicitamente para revisão humana.

Busca aproximada, embeddings, NLP, leitura semântica dos valores e inferência
por conteúdo textual são proibidos.

### Confirmação recorde a recorde

Para cada par `A, B`, a unidade padrão será o mesmo registro raw legível. Serão
contados:

```text
U  = registros em que A ou B está preenchido
AB = registros em que A e B estão preenchidos
E  = registros de AB em que os valores tipados são exatamente iguais
D  = registros de AB em que os valores diferem
SA = registros em que somente A está preenchido
SB = registros em que somente B está preenchido
```

As taxas mínimas serão:

```text
taxa_coincidencia = E / AB
taxa_sobreposicao = AB / U
taxa_so_a         = SA / U
taxa_so_b         = SB / U
```

Divisão por zero produzirá `nao_aplicavel`, nunca zero implícito. Nulos,
vazios e ausentes serão contabilizados separadamente e não contarão como
coincidência de metadados preenchidos.

A comparação basal será igualdade JSON tipada e exata. Uma taxa adicional
após transformação determinística só poderá ser calculada com `rule_id`
aprovado e deverá permanecer separada da taxa exata.

Campos de registros diferentes só poderão ser comparados depois de um vínculo
determinístico, explícito e um-para-um construído com metadados preenchidos.
Registros sem vínculo e chaves ambíguas serão quantificados. Sem vínculo
aprovado, o par permanecerá com evidência insuficiente.

As taxas são evidência, não decisão. Python nunca marcará um par como alias,
nunca escolherá o campo prioritário e nunca fundirá campos. Somente revisão
humana poderá mudar o par para `confirmado` ou `rejeitado`.

## Propostas de categorias com GPT-5.6

GPT-5.6 poderá ser usado em G02 para propor categorias, nomes de colunas,
mapeamentos e possíveis aliases de metadados. A proposta do modelo será uma
evidência para revisão, nunca uma regra aprovada automaticamente.

### Entrada permitida

Cada chamada receberá pacotes de evidência delimitados contendo somente:

- fonte, dataset e `record_type`;
- caminho original observado;
- tipos e estados de presença;
- cobertura, cardinalidade e tamanhos;
- valores de baixa cardinalidade e amostras curtas já classificadas como
  metadados;
- métricas estruturais e de coocorrência;
- categoria e definição da API oficial, quando disponíveis;
- identificadores das linhas de evidência, sem dados inventados.

Os pacotes poderão conter dois canais de amostra, com funções distintas.

#### Amostras estruturais de evidência

As amostras `evidence` mostrarão registros na prática sem interpretar conteúdo:

- estrutura completa de objetos e coleções;
- nomes de campos e tipos técnicos;
- valores reais curtos já classificados como metadados;
- coordenada raw e motivo de seleção;
- campos textuais longos substituídos por caminho, tipo, tamanho e hash.

A seleção será determinística e estratificada por
`fonte × dataset × record_type`. O piloto procurará incluir até três registros
distintos por grupo:

- um caso estrutural típico;
- um caso esparso;
- um caso com variante rara, conflito de tipo ou maior complexidade estrutural.

Grupos com menos de três registros fornecerão todos os registros distintos.
Critérios, desempates e hashes da seleção deverão ser registrados. A trilha de
`senado/ccj_notas` poderá acrescentar amostras para representar envelopes,
profundidades e variantes `array|object` que os três casos não cubram.

#### Previews textuais de contexto

Um conjunto separado `context_only` poderá mostrar pequenos trechos de
conteúdo parlamentar apenas para dar ao modelo noção prática do banco:

- no máximo um preview por grupo textual no piloto;
- segundo preview somente para variante estrutural distinta e justificada;
- no máximo 500 caracteres Unicode por preview;
- caminho do campo, posição inicial e final, tamanho integral, hash e
  coordenada raw;
- seleção determinística por critérios de comprimento e estrutura, nunca por
  interpretação semântica.

Cada preview será marcado com `context_only=true`. O prompt informará que ele
não é evidência para criar ou preencher coluna, confirmar alias, interpretar
marcador ou inferir metadado.

### Saída declarativa

A resposta obedecerá a JSON Schema fechado e deverá permitir:

- propor uma categoria ou declarar evidência insuficiente;
- propor nome e tipo lógico de coluna;
- citar todos os caminhos de origem usados;
- citar identificadores de evidência estrutural separadamente de referências
  opcionais de contexto;
- citar categorias oficiais da API usadas;
- propor operação determinística para futura revisão;
- marcar possível duplicidade ou alias;
- registrar ressalvas, conflitos e necessidade de revisão humana.

O modelo não poderá:

- criar caminho de origem que não exista no inventário;
- confirmar alias ou ordenar prioridade entre campos;
- autorizar descarte, fusão ou preenchimento;
- decidir tratamento dos 543 conflitos sem revisão;
- transformar sua proposta em regra executável;
- analisar marcadores ou estrutura interna de texto.

Python validará o JSON, as referências ao inventário e o vocabulário fechado.
Uma proposta sem evidência estrutural será inválida, mesmo que cite um preview
`context_only`.
Saídas inválidas, recusas e referências inexistentes serão preservadas e não
serão aplicadas.

### Rastreabilidade e piloto

Cada chamada registrará:

- modelo solicitado e identificador efetivamente resolvido;
- versão do prompt e do JSON Schema;
- hashes dos pacotes de entrada;
- resposta bruta e resposta validada;
- tokens, latência, custo calculado e estado;
- recusa, erro ou necessidade de revisão.

Um piloto estratificado deverá ser revisado antes de ampliar as propostas ao
universo de campos. `senado/ccj_notas` terá estrato e avaliação próprios.

O piloto comparará duas condições pareadas, com o mesmo modelo, prompt, schema
e pacote de evidências:

- condição A: sem previews `context_only`;
- condição B: com os previews `context_only` aprovados.

A revisão comparará propostas aceitas, categorias sem evidência, aliases
incorretos, respostas com evidência insuficiente, tokens, latência e custo. Os
previews só permanecerão no desenho se demonstrarem benefício revisado pelo
pesquisador responsável.

## Conflitos de tipo

Cada um dos 543 conflitos deverá receber uma linha própria com tipos,
cobertura, partições e exemplos estruturais seguros.

Nenhuma coerção automática será adotada. As alternativas permitidas para
proposta humana incluem:

- manter uma união tipada explícita;
- separar variantes por escopo observado;
- preservar a estrutura original e adiar o mapeamento;
- declarar conflito aberto.

Converter objetos ou coleções para string, escolher o tipo majoritário ou
descartar a variante minoritária é proibido.

## Tratamento especial de `senado/ccj_notas`

Os 20.523 caminhos e 540 conflitos de `senado/ccj_notas` serão tratados em
uma trilha própria, sem reduzir a cobertura exigida para os demais datasets.

O desenho deverá:

- separar envelopes e `record_type` antes de comparar caminhos;
- preservar hierarquia, multiplicidade e ordem de arrays;
- distinguir objeto, array, escalar, nulo e vazio;
- impedir que o curinga `[]` seja interpretado como identidade de elementos;
- comparar aliases apenas em escopos estruturalmente compatíveis;
- registrar variantes `array|object` sem achatamento destrutivo;
- produzir métricas e relatório específicos para revisão humana.

Se a identidade de elementos de uma coleção não puder ser estabelecida por
metadado preenchido e regra determinística, a estrutura permanecerá
preservada e não mapeada.

## Separação da estrutura textual

O schema poderá transportar texto, sua coordenada, tamanho e hash, mas não
interpretará sua estrutura.

Marcadores, cabeçalhos, separadores, oradores, turnos, papéis e fronteiras
serão tratados posteriormente por planos JSON declarativos do GPT-5.6. As
chamadas de G02 se limitarão à proposta de schema para metadados e não
anteciparão o vocabulário dos planos textuais. Previews `context_only` não
autorizam análise ou transformação do conteúdo.

## Artefatos de G02

A ferramenta implementada prepara ou reserva ao menos:

| Artefato | Finalidade |
|---|---|
| `manifest.json` | entrada, hashes, configuração, versão e contagens |
| `livro_campos.csv` | decisão explícita para os 23.786 caminhos |
| `schema_normalizado.schema.json` | contrato lógico proposto |
| `mapeamentos_propostos.csv` | origem, destino, regra e proveniência |
| `auditoria_aliases.csv` | pares, contagens, taxas e decisão humana |
| `amostras_estruturais.jsonl` | registros `evidence` selecionados |
| `previews_contexto.jsonl` | trechos `context_only` aprovados |
| `propostas_gpt.jsonl` | propostas declarativas, evidências e estados |
| `execucao_gpt.jsonl` | modelo, prompt, tokens, custo, erros e recusas |
| `avaliacao_contexto_ab.csv` | comparação pareada com e sem previews |
| `conflitos_tipos.csv` | tratamento explícito dos 543 conflitos |
| `senado_ccj_notas.md` | revisão estrutural especial do dataset |
| `linhas_rejeitadas.csv` | preservação das 14 rejeições |
| `relatorio.md` | síntese para decisão G02 |

Os nomes poderão ser refinados antes da implementação, mas nenhuma dessas
responsabilidades poderá ser eliminada.

## Checklist contratual

- [ ] R02-01 — Confirmar os hashes dos sete artefatos da operação G01.
- [ ] R02-02 — Cobrir os 23.786 caminhos no livro de decisões.
- [ ] R02-03 — Vincular toda categoria de domínio a metadado observado e preenchido.
- [ ] R02-04 — Preservar caminho original e proveniência em todo mapeamento.
- [ ] R02-05 — Manter ausente, nulo, vazio, preenchido e rejeitado como estados distintos.
- [x] R02-06 — Impedir descarte ou fusão automática de campos.
- [x] R02-07 — Auditar aliases recorde a recorde com contagens e taxas reproduzíveis.
- [x] R02-08 — Submeter toda confirmação de alias à revisão humana.
- [ ] R02-09 — Tratar individualmente os 543 conflitos de tipo.
- [ ] R02-10 — Reconciliar separadamente os 20.523 caminhos de `senado/ccj_notas`.
- [ ] R02-11 — Preservar e localizar as 14 linhas rejeitadas.
- [x] R02-12 — Impedir inferência a partir de texto em qualquer regra Python.
- [x] R02-13 — Adiar marcadores e estruturas textuais para planos JSON do GPT-5.6.
- [ ] R02-14 — Obter aprovação humana de G02 antes de implementar adaptadores ou normalização.
- [x] R02-15 — Validar toda proposta GPT contra caminhos e evidências do inventário.
- [x] R02-16 — Registrar modelo, prompt, schema, entrada, resposta, uso e custo.
- [x] R02-17 — Impedir aplicação automática de categorias ou aliases propostos pelo GPT.
- [x] R02-18 — Vincular categorias oficiais das APIs somente a campos observados.
- [x] R02-19 — Selecionar deterministicamente amostras estruturais por grupo.
- [x] R02-20 — Limitar e rotular todo preview textual como `context_only`.
- [x] R02-21 — Impedir que preview de contexto seja evidência de coluna ou alias.
- [x] R02-22 — Comparar condições pareadas com e sem previews textuais.
- [ ] R02-23 — Manter previews somente após benefício aprovado na avaliação A/B.

## Não objetivos

- Implementar o normalizador.
- Materializar registros normalizados.
- Definir adaptadores por fonte.
- Corrigir ou reescrever o raw.
- Resolver marcadores ou estruturas textuais.
- Enviar conteúdo parlamentar fora dos previews `context_only` aprovados.
- Usar preview de contexto como evidência de categoria, coluna ou alias.
- Aplicar automaticamente propostas do GPT-5.6.
- Reutilizar automaticamente o schema arquivado.
- Aprovar G02 sem revisão humana dos artefatos.
