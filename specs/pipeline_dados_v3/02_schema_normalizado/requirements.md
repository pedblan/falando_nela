# Requisitos — schema normalizado v3

## Estado

Specs aprovadas e implementação da ferramenta de evidências autorizada pelo
pesquisador responsável em 2026-07-24. A proposta global
`gpt56-global-schema-proposal-v1` foi recebida e seu vocabulário conceitual foi
revisado coluna a coluna e aprovado pelo pesquisador em 2026-07-25. Essa
aprovação autoriza incorporar às quatro specs o contrato humano consolidado.
Ela não equivale à conclusão operacional de G02. Em autorização específica
posterior, o pesquisador liberou o Batch de disposição dos `field_id` e a
auditoria integral somente leitura. O Batch e dois reparos incrementais foram
reconciliados em 2026-07-25 com 23.786 propostas únicas e zero pendências;
e a auditoria raw terminou em 2026-07-26 com fingerprint estável e seus
artefatos técnicos reconciliados. As propostas e os artefatos ainda aguardam
revisão humana. Continuam não autorizados adaptadores, aplicação do schema,
geração de dados normalizados, alteração do `raw/` ou início dos submódulos
seguintes.

O único inventário aceito como evidência estrutural é
`raw-metadata-full-20260724t184418z`, aprovado em G01 em 2026-07-24.
Seu `manifest.json` deverá corresponder ao SHA-256 aprovado
`b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9`.

## Objetivo

Definir o contrato lógico do schema normalizado v3 e o método auditável para
propor suas categorias a partir exclusivamente dos metadados estruturados
observados no inventário aprovado.

O submódulo deverá produzir uma proposta de schema e suas evidências. Ele não
aplicará o schema ao corpus.

## Contrato humano aprovado do vocabulário global

A revisão humana vinculante está registrada em
`docs/revisoes/g02_schema_global_revisao_humana.md`. O diário conserva
finalidade, riscos, exemplos, recomendações e decisões individuais; esta
seção incorpora às specs suas consequências normativas.

A aprovação abrange:

- os 40 candidatos canônicos da proposta global;
- as famílias omitidas `speech_indexing_source_raw` e
  `proposition_subject_source`;
- as oito hipóteses de alias;
- as entidades, relações e cardinalidades da família polimórfica de
  `senado/ccj_notas`;
- as coordenadas técnicas de registro e de valor;
- a separação entre indexação temática, índice temporário de candidatos a
  alias e índice físico de consulta.

Uma decisão histórica “revisar” significa aprovação com a reformulação
descrita abaixo; não significa pendência. O número 40 descreve os candidatos
recebidos do modelo, não uma obrigação de produzir uma tabela única com
exatamente 40 colunas. Separações por entidade e papel poderão ampliar o
vocabulário lógico expresso em `schema_normalizado.schema.json`.

### Destino normativo dos candidatos e das lacunas

| Candidato ou família | Destino aprovado | Exemplo |
|---|---|---|
| `source`, `dataset`, `record_type` | cópia literal e escopo estrutural conjunto | `senado + ccj_notas + reuniao_detalhe` |
| `source_record_id` | identificador técnico do envelope, nunca ID oficial da entidade | `senado:senador:3:detalhe` |
| `collected_at` | tempo técnico de coleta; cast somente válido e sem perda | `2026-05-28T01:19:42+00:00` |
| `original_field_path` | linhagem por ocorrência, acompanhada de pointer concreto | `$.payload.reuniao.partes[].itens[]` e `/payload/reuniao/partes/1/itens/0` |
| `coverage_start_date`, `coverage_end_date` | período técnico explícito | `2025-01-01` a `2025-01-31` |
| `event_start_datetime`, `event_end_datetime` | separar tempos por evento, reunião, sessão e pronunciamento e preservar precisão | data de reunião não preenche data de sessão |
| `arena_name`, `arena_acronym` | ocorrências institucionais qualificadas por papel, ID e namespace | `CCJ` como colegiado da reunião; `CCJC` como órgão da Câmara |
| `event_id` | ID oficial de evento no namespace da fonte | evento da Câmara `81996` |
| `meeting_id` | `committee_meeting_id`, restrito a reunião de comissão ou colegiado | reunião da CCJ `14657` |
| `session_id` | separar `plenary_session_id` de `legislative_session_id` | sessão plenária `526727` e sessão legislativa `873` |
| `speech_id` | preferir `pronouncement_official_id`; segmento taquigráfico permanece distinto | pronunciamento `519407` |
| `event_title` | títulos separados por entidade e papel | título de audiência não substitui descrição de sessão |
| `event_status_source` | código e descrição separados por entidade e fonte | código `5`, rótulo `Cancelada` |
| `speech_type_source` | preservar código, sigla, descrição e indicador oficial | `4819`, `DIS`, `Discurso`, `S` |
| `proposition_id` | separar proposição, matéria e processo legislativo | proposição Câmara `2252029`, matéria e processo do Senado |
| `proposition_type_acronym` | preservar tipo por entidade e identificação composta | `PEC` e `PEC 45/2019` |
| `proposition_number`, `proposition_year` | componentes analíticos explícitos no formato conhecido tipo número/ano | `PEC 45/2019` |
| `proposition_abstract_source` | somente ementa explícita, literal e vinculada à entidade ou versão | campo `ementa`, nunca texto integral |
| `document_id` | IDs documentais separados por função e namespace | `IdDocumento` e `idEcmSenado` não são o mesmo domínio |
| `document_type_source` | separar categoria oficial, sigla, descrição e classificação derivada | `siglaTipo=OFS` e descrição própria |
| `document_url` | preservar cada URL por papel e contexto | `linkDownload`, `urlDocumento` e URL final |
| `document_media_type` | separar MIME declarado, cabeçalho HTTP e detecção técnica | `application/pdf` declarado não sobrescreve resposta divergente |
| `opinion_deliberative_status_source` | usar `opinion_deliberative_status_collector_derived` para a derivação; reservar código e rótulo `_source` ao campo oficial | `_status_deliberativo` não vira status oficial sem evidência |
| `opinion_superseded_source` | substituir por indicadores de parecer vencido, distinguindo fonte oficial de derivação do coletor | `opinion_defeated_indicator_collector_derived=true` não significa “substituído” |
| `person_official_id` | ID por fonte, namespace, papel e ocorrência | ID Senado `5523` não é comparado globalmente a ID Câmara |
| `person_name_source` | nomes separados por papel; identidade nunca resolvida apenas por nome | nome parlamentar e nome civil |
| `speaker_role_source` | separar papel da fala, cargo, função e tratamento | `Presidente`, `Orador`, `CargoAutor` |
| `party_acronym_source` | partido por papel, tempo e namespace | partido no mandato ou na data do pronunciamento |
| `federative_unit_source` | UF por papel geográfico e contexto temporal | UF de exercício não substitui UF de nascimento |
| `sex_or_gender_source_reported` | substituir por `sex_label_recorded_by_source`, restrito ao rótulo de sexo literalmente registrado | `F`, `M` ou `Masculino`; não representa necessariamente identidade de gênero |
| `text_content_raw` | representar como ocorrências de `text_artifacts`, por origem, entidade, papel, ordem e método | notas agregadas, texto de parecer e marcação taquigráfica separados |
| `text_status_source` | usar `text_retrieval_status_collector_derived` por tentativa, não status substantivo da fonte | `ausente` na API e `disponivel` em tentativa posterior |
| `request_metadata`, `response_metadata` | objetos técnicos pareados, sem preencher categorias substantivas | método e parâmetros da requisição; URL e status da resposta |
| `speech_indexing_source_raw` | indexação temática literal de fala, qualificada por fonte | `Indexacao` do Senado ou `keywords` da Câmara |
| `proposition_subject_source` | assunto oficial estruturado da proposição | Câmara: `codTema=43`, `Direito Penal e Processual Penal`, `relevancia=0` |

### Entidades e cardinalidades mínimas

As relações abaixo serão preservadas no contrato lógico. `0:N` significa que
ausência e multiplicidade são válidas; não autoriza criar elementos nem
colapsar repetições.

| Entidade de origem | Relação | Entidade de destino | Exemplo |
|---|---:|---|---|
| registro raw | `1:N` | ocorrências de valor | uma linha JSONL com campos e coleções aninhadas |
| reunião de comissão | `1:N` | observações da fonte | agenda e detalhe da reunião `14657` |
| reunião de comissão | `0:N` | partes | reunião `14685`, partes `18966` e `18967` |
| parte | `0:N` | itens de pauta | parte `18930`, com 11 itens |
| parte | `0:N` | eventos aninhados | parte `19114`, evento `10375` |
| item de pauta | `0:N` | resultados, matérias, documentos e autorias | `OFS 4/2026` com vista em `14657` e aprovação em `14685` |
| matéria ou processo | `0:N` | relatorias e autorias | designação qualificada por pessoa ou instituição, papel e tempo |
| documento | `0:N` | vínculos contextuais | aparições em `doma.textos` e `textosPauta` |
| evento aninhado | `0:N` | matérias relacionadas e envolvimentos | convidados e participantes como ocorrências distintas |
| participante | `0:N` | apresentações | documento ECM associado à participação |
| reunião | `0:N` | estados, vídeos, quartos e arenas | estados oficiais `1`, `3`, `4`, `5` e `6` |
| reunião observada | `0..1` | presidência | reunião `14657`, presidente ID `5523`; reunião `14634`, nulo |
| quarto taquigráfico | `0:N` | marcações | `Palavra`, `Intercorrência`, `Matéria` e `Anotação` |
| reunião observada | `0..1` | contexto de sessão legislativa | período legislativo sem conversão em sessão plenária |
| fala ou pronunciamento | `0:N` | metadados temáticos | `Indexacao` ou `keywords` |

Proposição, matéria, processo, documento, item de pauta, parecer, reunião de
comissão, evento, evento aninhado, sessão plenária, sessão legislativa,
pronunciamento, quarto e marcação taquigráfica são entidades distintas. Senado,
Câmara, Congresso, CCJ, CCJC e os plenários têm namespaces próprios.

### Famílias estruturais aprovadas para `senado/ccj_notas`

| Bloco | Famílias lógicas | Exemplo |
|---:|---|---|
| 1 | `meeting_part_source`, `agenda_item_source` | parte `18930` e seus 11 itens |
| 2 | `legislative_matter_observation`, `rapporteur_assignment_source` | `doma` e uma relatoria contextual |
| 3 | `legislative_document_source`, `document_context_link_source` | documento e sua aparição em matéria ou pauta |
| 4 | `committee_embedded_event_source`, `event_involvement_source` | evento `10375`, convite e participação |
| 5 | `event_related_matter_link_source`, `authorship_assignment_source` | matéria relacionada e autoria pessoal ou institucional |
| 6 | `meeting_state_observation_source`, `agenda_item_outcome_source` | estado `Suspensa` e resultado `Vista` |
| 7 | `taquigraphic_quarter_source`, `taquigraphic_marker_source` | quarto `3765408` e marcação `Palavra` |
| 8 | `meeting_arena_assignment_source`, `meeting_presidency_source` | colegiado criador e presidente ID `5523` |
| 9 | `meeting_video_source`, `participant_presentation_document_source` | vídeo da reunião e apresentação ECM |
| 10 | `committee_meeting_type_source`, `meeting_modality_source`, `legislative_session_context_source` | tipo oficial, modalidade e sessão legislativa |

As formas `object|array`, a ordem, a multiplicidade, os nulos, os vazios e a
ausência permanecerão explícitos. Convites e participações só poderão ser
ligados por `codigoConvidado` exato e preenchido. Nomes, posições de arrays e
similaridade textual não estabelecerão identidade.

### Decisões sobre as oito hipóteses de alias

Sete pares foram aprovados como duplicações técnicas criadas pelos coletores,
sempre restritas ao `source + dataset + record_type` demonstrado:

1. Câmara/CCJC: `CodigoEvento` ↔ `evento_id`;
2. Câmara/CCJC: `TextoIntegral` ↔ `texto`;
3. Câmara/pareceres de PEC: `TextoIntegral` ↔ `texto`;
4. Senado/CCJ: `CodigoReuniao` ↔ `codigo_reuniao`;
5. Senado/CCJ: `TextoIntegral` ↔ `texto`;
6. Senado/Congresso: `CodigoPronunciamento` ↔
   `codigo_pronunciamento`;
7. Senado/Plenário: `CodigoPronunciamento` ↔
   `codigo_pronunciamento`.

A oitava hipótese foi rejeitada: as subárvores de agenda e detalhe não são
aliases. Elas permanecem observações distintas da mesma reunião, ligadas por
`committee_meeting_id`, mesmo quando os valores coincidem, como na reunião
`14657`.

Essas decisões não reescrevem nem removem as duas grafias no raw. A aplicação
futura de qualquer duplicação técnica deverá conservar ambas as ocorrências de
linhagem e provar o escopo antes de produzir um único valor canônico.

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
  aprovado, fixado externamente no contrato.
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

Cada ocorrência deverá preservar `source_record_coordinate`, composta por:

```text
source + dataset + record_type
+ source_file_path
+ source_record_number
+ record_locator_scheme
```

`source_file_path` será relativo à raiz raw. `source_record_number` será
inteiro positivo. `record_locator_scheme` declarará obrigatoriamente a
convenção:

- `jsonl_physical_line_1_based`, por exemplo a linha física `1842`;
- `csv_data_row_1_based`, por exemplo a 1842ª linha de dados, sem cabeçalho;
- `parquet_row_1_based`, por exemplo a 1842ª linha lógica;
- outro valor fechado e versionado para um formato diferente.

Cada valor aninhado deverá preservar também `source_value_coordinate`:

- `catalog_field_path`, por exemplo
  `$.payload.DetalheReuniao.reuniao.partes[].itens[].doma.idProcesso`;
- `source_value_pointer` em JSON Pointer concreto, por exemplo
  `/payload/DetalheReuniao/reuniao/partes/1/itens/0/doma/idProcesso`;
- `source_container_shape`, por exemplo `partes=array` e `itens=array`;
- `source_occurrence_id`, calculado de forma determinística por SHA-256 sobre
  o escopo, arquivo, número do registro e pointer concreto.

Índices de arrays em `source_value_pointer` serão `zero_based`. Uma ocorrência
em contêiner `object` não receberá índice artificial `[0]`. A posição servirá
para ordem e proveniência, nunca como identidade entre coleções.

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

## Política de indexação

Três categorias permanecerão separadas:

1. **Indexação temática da fonte:** dado de domínio preservado em
   `speech_indexing_source_raw`, por exemplo `Indexacao` do Senado e
   `keywords` da Câmara.
2. **Índice temporário de candidatos a alias:** artefato técnico reproduzível
   e descartável, por exemplo agrupamento por
   `source + dataset + record_type + chave terminal + tipos + hash tipado`.
3. **Índice físico de consulta:** decisão posterior de armazenamento e
   desempenho, por exemplo índice sobre `committee_meeting_id`.

Não existirá coluna canônica genérica `index`. Match em índice temporário não
confirma alias, e índice físico não substitui proveniência.

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

### Catálogo global e ampliação após o piloto

Os pilotos exploratórios mostraram que lotes independentes são úteis para
aplicar uma classificação já definida, mas não dão ao modelo uma visão global
dos 23.786 caminhos. A ampliação adotará, portanto, duas fases distintas:

1. uma única chamada global propôs o vocabulário canônico a partir de um
   arquivo textual que representa todos os caminhos;
2. somente depois de revisão e congelamento desse vocabulário, chamadas Batch
   independentes poderão propor o mapeamento de cada caminho.

O catálogo global será produzido apenas dos artefatos aprovados de G01, sem
reler o raw. Ele deverá:

- conter exatamente uma identidade para cada caminho do inventário;
- preservar em crosswalk separado a fonte, o dataset, o `record_type`, o
  caminho original integral e todas as métricas do inventário;
- fatorar apenas repetições de proveniência e prefixos de caminho de maneira
  reversível;
- manter no TXT os tipos, a razão exata `preenchidos/universo`, a máscara de
  estados observados, a cardinalidade, o comprimento máximo de string e o
  indicador de conflito;
- manter no crosswalk os cinco contadores de presença, `fill_rate`, os três
  comprimentos, as partições e as demais métricas integrais;
- reconciliar explicitamente 14 rejeições, 543 conflitos e os 20.523 caminhos
  de `senado/ccj_notas`;
- incluir amostras seguras de G01 em canal `context_only`, selecionadas por
  regra determinística sem leitura semântica e incapazes de sustentar coluna
  ou alias;
- representar strings longas somente por tipo, tamanho e SHA-256;
- produzir hashes e manifest próprios;
- ser idempotente: saída existente idêntica será reutilizada e saída
  divergente não será sobrescrita.

O pesquisador autorizou em 2026-07-24 a seleção determinística dessas amostras
`context_only` para dar ao modelo noção prática do banco sem exigir a edição
manual de 23.786 linhas. Essa autorização não converte amostra em evidência,
não libera conteúdo longo e não altera as regras dos previews textuais.

O arquivo enviado ao modelo será `.txt`, não `.csv` ou planilha, para que os
23.786 caminhos integrem o contexto em vez de serem submetidos ao fluxo
reduzido de leitura de planilhas. `File Search` não será usado para esta
decisão global, pois recuperação seletiva não comprova leitura integral.

O perfil `schema_core` reduzirá somente redundâncias estatísticas do TXT:
`ausente`, `nulo`, `vazio` e `preenchido` serão representados por uma máscara,
e a cobertura será a fração exata `preenchidos/universo`. Mínimo, mediana,
partições e contadores completos continuarão no crosswalk. Essa redução não
retirará caminhos, tipos, conflitos ou proveniência do conjunto de evidências.

Antes da chamada de geração, o arquivo será enviado com `purpose=user_data` e
o payload completo, incluindo o prompt versionado, será submetido ao endpoint
de contagem exata de tokens. A geração permanecerá bloqueada se exceder o
máximo de entrada do modelo ou se qualquer reconciliação falhar. Truncamento
automático será proibido.

Em 2026-07-24, a execução integral do perfil `schema_core` produziu 23.786
caminhos, 543 conflitos, 20.523 caminhos de `senado/ccj_notas` e 65 amostras
`context_only`. A medição preliminar do caderno foi 691.302 tokens para
arquivo + prompt; o recibo preservado registrou 691.339 tokens nesse estágio.
O pesquisador autorizou uma única chamada global depois de revisar a
estimativa de custo. A proposta resultante foi recebida e aprovada
conceitualmente em 2026-07-25.

A reconciliação registrada em
`g02_reconciliacao_global_20260725.md` demonstrou que a submissão:

- recontou 692.031 tokens com o JSON Schema exato da geração;
- usou `gpt-5.6`, raciocínio `medium`, no máximo 32.000 tokens de saída,
  truncamento desabilitado e execução em background;
- preservou no Drive os artefatos do catálogo e o `response_id`;
- mantém recibo idempotente compatível com a chamada única;
- registrou 13.712 tokens de saída, 1.182 tokens de raciocínio e custo efetivo
  de US$ 7,53735.

Como `git pull` não altera as células exibidas por um caderno que já está
aberto no Colab, a mesma submissão e consulta deverão estar disponíveis por
CLI. Esse caminho de continuação reutilizará o runtime e os artefatos correntes,
sem exigir abertura ou reexecução integral do caderno.

A resposta global recebida limitou-se a:

- schema canônico e definições de colunas;
- famílias estruturais de campos;
- critérios declarativos de mapeamento;
- candidatos a aliases ainda sujeitos à auditoria recorde a recorde;
- conflitos e casos que exigem decisão humana.

Ela não emitiu 23.786 decisões verbosas, não aplicou mapeamentos, não confirmou
aliases nem autorizou descarte, fusão, prioridade ou preenchimento.

O pesquisador autorizou posteriormente, em 2026-07-25, uma operação Batch
integral para propor o mapeamento dos 23.786 `field_id`. Essa operação:

- usa o identificador explícito `gpt-5.6-sol`, compatível com Batch;
- divide os 50 grupos em 99 requisições independentes de até 400 campos;
- entrega a todas as requisições o mesmo vocabulário congelado de 91 campos
  lógicos e o mesmo JSON Schema fechado;
- reconcilia por `custom_id`, sem depender da ordem das respostas;
- permite apenas `map`, `defer`, `technical` e `unmapped`;
- valida candidatos contra o vocabulário fechado;
- recompõe a proveniência deterministicamente do crosswalk;
- mantém `proposal_applied=false`, `raw_mutated=false` e
  `normalization_materialized=false`.

A entrada válida contém 1.353.952 tokens e cabe no limite conservador de
1.500.000 tokens enfileirados adotado para a operação. A primeira tentativa,
com o alias `gpt-5.6`, foi rejeitada pela API antes de processar requisições;
ela foi preservada, e uma nova tentativa foi submetida com
`gpt-5.6-sol`. O registro operacional completo está em
`g02_batch_e_auditoria_20260725.md`.

Conclusão HTTP não será tratada como cobertura científica. Se uma resposta
omitir IDs ou devolver uma combinação incompatível entre decisão, candidato
e operação, a saída bruta será preservada, a disposição inválida não entrará
no conjunto aceito e o gate ficará em `repair_required`. Reparos usarão
somente os IDs ainda pendentes, em requisições menores, com os mesmos hashes
de vocabulário e schema. A união entre tentativas deverá ser disjunta e
reconciliar exatamente os 23.786 IDs antes da revisão humana.

Esse requisito foi satisfeito operacionalmente por uma tentativa principal e
dois reparos disjuntos: `19.779 + 4.005 + 2 = 23.786` IDs válidos. O custo
efetivo total foi US$ 19,7714390. A reconciliação final tem zero IDs ausentes,
desconhecidos ou duplicados e mantém todas as decisões humanas como
`nao_avaliado`; portanto, ela abre a revisão humana e não aplica o schema.

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

## Limite entre schema lógico e materialização física

G02 definirá o vocabulário, as entidades, os tipos, as cardinalidades, os
estados e a proveniência. Não definirá um Parquet único, um Parquet por coluna
nem os nomes, partições e índices físicos da camada processada.

G03 especificará adaptadores por fonte. G04 tratará marcadores textuais em
contrato separado. Somente G05 poderá materializar a camada processada v3.
Caso Parquet seja escolhido, relações como reunião → partes → itens ou quarto
→ marcações deverão ser representadas sem duplicação destrutiva nem perda de
cardinalidade. Por exemplo, reuniões, observações de agenda/detalhe, itens de
pauta e marcações taquigráficas poderão ocupar tabelas derivadas distintas.
Essa ilustração não fixa a disposição física.

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
| `catalogo_global_gpt56.txt` | representação integral compacta enviada ao modelo |
| `catalogo_global_crosswalk.csv` | correspondência lossless entre IDs e caminhos originais |
| `catalogo_global_amostras.csv` | trilha das amostras `context_only` efetivamente incluídas |
| `catalogo_global_manifest.json` | hashes, contagens e política do catálogo global |
| `upload_token_count.json` | `file_id`, hash e contagem exata do payload global |
| `submission_receipt.json` | fingerprint da requisição e `response_id` reutilizável |
| `status_latest.json` | último estado observado da chamada em background |
| `response_raw.json` | resposta integral preservada sem aplicação |
| `proposta_schema_global.json` | proposta global validada para revisão humana |
| `execution.json` | uso, custo, modelo resolvido e gate científico |
| `propostas_gpt.jsonl` | propostas declarativas, evidências e estados |
| `execucao_gpt.jsonl` | modelo, prompt, tokens, custo, erros e recusas |
| `avaliacao_contexto_ab.csv` | comparação pareada com e sem previews |
| `conflitos_tipos.csv` | tratamento explícito dos 543 conflitos |
| `senado_ccj_notas.md` | revisão estrutural especial do dataset |
| `linhas_rejeitadas.csv` | preservação das 14 rejeições |
| `relatorio.md` | síntese para decisão G02 |
| `docs/revisoes/g02_schema_global_revisao_humana.md` | registro da aprovação conceitual de 2026-07-25 |

Os nomes poderão ser refinados antes da implementação, mas nenhuma dessas
responsabilidades poderá ser eliminada.

## Checklist contratual

- [x] R02-01 — Confirmar os hashes dos sete artefatos da operação G01.
- [ ] R02-02 — Cobrir os 23.786 caminhos no livro de decisões.
- [ ] R02-03 — Vincular toda categoria de domínio a metadado observado e preenchido.
- [x] R02-04 — Preservar caminho original e proveniência em todo mapeamento.
- [x] R02-05 — Manter ausente, nulo, vazio, preenchido e rejeitado como estados distintos.
- [x] R02-06 — Impedir descarte ou fusão automática de campos.
- [x] R02-07 — Auditar aliases recorde a recorde com contagens e taxas reproduzíveis.
- [x] R02-08 — Submeter toda confirmação de alias à revisão humana.
- [x] R02-09 — Tratar individualmente os 543 conflitos de tipo.
- [x] R02-10 — Reconciliar separadamente os 20.523 caminhos de `senado/ccj_notas`.
- [x] R02-11 — Preservar e localizar as 14 linhas rejeitadas.
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
- [x] R02-24 — Implementar representação global reversível dos 23.786 caminhos.
- [x] R02-25 — Preservar o caminho integral e as métricas no crosswalk do catálogo.
- [x] R02-26 — Implementar amostragem segura `context_only` sem inferência semântica.
- [x] R02-27 — Executar o catálogo global sobre o inventário integral aprovado.
- [x] R02-28 — Contar exatamente arquivo e prompt do catálogo global antes da geração.
- [x] R02-29 — Obter e revisar a proposta global de vocabulário canônico.
- [x] R02-30 — Congelar humanamente o vocabulário antes de qualquer Batch integral.
- [x] R02-31 — Reconciliar a saída Batch dos 23.786 IDs sem descarte ou fusão automática.
- [x] R02-32 — Compactar estatísticas no TXT sem removê-las do crosswalk.
- [x] R02-33 — Implementar submissão global idempotente e retomável por `response_id`.
- [x] R02-34 — Registrar a contagem exata incluindo o JSON Schema da geração.
- [x] R02-35 — Permitir submissão e consulta por célula curta em um Colab já aberto.
- [x] R02-36 — Registrar nas quatro specs a aprovação conceitual de 2026-07-25.
- [x] R02-37 — Validar o schema lógico gerado contra o vocabulário conceitual aprovado.
- [x] R02-38 — Preparar e submeter de forma idempotente o Batch autorizado com `gpt-5.6-sol`.
- [x] R02-39 — Contar 1.353.952 tokens da entrada exata antes da submissão válida.
- [x] R02-40 — Preservar e reconciliar saída, uso e custo efetivos do Batch concluído.
- [x] R02-41 — Bloquear cobertura parcial e combinações Batch incompatíveis com o contrato.
- [x] R02-42 — Implementar reparos somente dos IDs pendentes e união disjunta das tentativas.

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
