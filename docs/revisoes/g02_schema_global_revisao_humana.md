# Diário da revisão humana de G02 — schema global

## Estado e autoridade

- Estado: `aprovada_em_2026-07-25`.
- Natureza: registro de trabalho não normativo.
- Início do registro: 2026-07-25.
- Proposta sob revisão: `gpt56-global-schema-proposal-v1`.
- Responsável pelas decisões: pesquisador responsável pelo Falando Nela.
- Efeito das decisões: incorporadas às quatro specs de
  `02_schema_normalizado` em 2026-07-25.

Este diário não altera nem substitui `requirements.md`, `plan.md`,
`validation.md` ou `tech-stack.md` de `02_schema_normalizado`. Depois da
aprovação final do pesquisador, as decisões abaixo foram consolidadas nessas
specs; em caso de implementação futura, as specs são o contrato normativo.

## Materiais lidos

- `specs/pipeline_dados_v3/02_schema_normalizado/requirements.md`
- `specs/pipeline_dados_v3/02_schema_normalizado/plan.md`
- `specs/pipeline_dados_v3/02_schema_normalizado/validation.md`
- `specs/pipeline_dados_v3/02_schema_normalizado/tech-stack.md`
- proposta global anexada, versão `gpt56-global-schema-proposal-v1`

## Restrições mantidas durante a revisão

- Não executar Batch.
- Não aplicar o schema proposto.
- Não implementar normalização ou adaptadores.
- Não alterar o `raw/`.
- Não alterar as specs antes da aprovação final.
- Não confirmar aliases sem auditoria exata recorde a recorde.
- Não inferir metadados a partir de conteúdo parlamentar.
- Não usar exemplos ou documentação oficial para criar campos ausentes do
  inventário aprovado.
- Manter `senado/ccj_notas`, seus 20.523 caminhos e seus 540 conflitos em
  trilha própria.

## Método acordado

- Revisão amigável por famílias e em blocos pequenos.
- Para cada coluna: finalidade, exemplos, riscos e recomendação.
- Decisão humana por coluna: `aprovar`, `revisar` ou `adiar`.
- A partir da solicitação do pesquisador, toda categoria apresentada deverá
  trazer exemplos.
- Categorias oficiais das APIs são evidência semântica secundária, sempre
  qualificadas por fonte e data de consulta.

## Princípios transversais já aceitos

1. `source + dataset + record_type` é o escopo estrutural mínimo do registro.
2. `source_record_id` é técnico e não substitui IDs oficiais de entidades.
3. Identificadores oficiais permanecem em namespaces próprios.
4. Proposição, matéria, processo, documento, evento, reunião, sessão,
   pronunciamento e segmento taquigráfico são entidades distintas.
5. Um atributo pode ser escalar por ocorrência de entidade e múltiplo em
   relação ao registro raw que contém uma lista dessas entidades.
6. `original_field_path` pertence à linhagem de cada valor, não é um único
   valor escalar capaz de representar toda uma linha normalizada.
7. Códigos, siglas, descrições e indicadores de atividade de vocabulários
   oficiais não devem ser colapsados.
8. Valores originais, tipos técnicos, ausências, nulos e vazios devem
   permanecer auditáveis.
9. Documentação oficial pode validar o sentido de um campo observado, mas não
   pode preencher valores nem criar categorias sem evidência no inventário.
10. Reuniões da CCJ do Senado, reuniões da CCJC da Câmara e sessões plenárias
    são entidades distintas. Siglas, IDs, tempos, participantes, documentos e
    notas permanecem qualificados pela Casa, pelo colegiado e pelo tipo de
    ocorrência.

## Distinção obrigatória entre comissão e plenário

O desenho em revisão deverá manter, no mínimo, estas distinções:

| Contexto | Fonte e arena | Entidade | Identificador e tempo |
|---|---|---|---|
| reunião da CCJ | Senado, `CCJ` | reunião de colegiado | `meeting_id`, `meeting_start_datetime`, `meeting_end_datetime` |
| reunião da CCJC | Câmara, `CCJC` | evento/reunião de comissão conforme a categoria oficial observada | `event_id` da Câmara e tipo oficial do evento; nenhuma conversão automática para ID do Senado |
| sessão plenária do Senado | Senado, Plenário | sessão plenária | `plenary_session_id` e tempos próprios da sessão |
| sessão plenária da Câmara | Câmara, Plenário | evento ou sessão conforme a categoria oficial observada | ID e tipo da Câmara, sem alias automático com sessão do Senado |

Consequências:

- `CCJ` e `CCJC` não são aliases automáticos;
- `meeting_id`, `event_id` e `plenary_session_id` permanecem em domínios
  distintos;
- horário da reunião não preenche horário da sessão plenária;
- participante de comissão não recebe automaticamente papel no plenário;
- pauta, documentos, pronunciamentos e notas ficam ligados à ocorrência e à
  arena corretas;
- notas de reunião de comissão e notas de sessão plenária não compartilham uma
  linha ou identidade textual apenas porque ambas são taquigráficas;
- em `senado/ccj_notas`, arrays, ordem, multiplicidade, `record_type` e caminho
  completo permanecem preservados; `[]` não identifica elementos.

## Quadro de decisões

| Família | Coluna proposta | Decisão | Direção aprovada para a revisão |
|---|---|---|---|
| proveniência | `source` | aprovar | cópia literal; fonte técnica, não casa derivada |
| proveniência | `dataset` | aprovar | cópia literal; coleção técnica |
| proveniência | `record_type` | aprovar | tipo estrutural, sempre qualificado por fonte e dataset |
| proveniência | `source_record_id` | aprovar | ID técnico; não é alias de ID oficial |
| proveniência | `collected_at` | aprovar | tempo técnico de coleta; cast somente válido e sem perda |
| proveniência | `original_field_path` | revisar | escalar por ocorrência de linhagem e potencialmente múltiplo por registro |
| temporal | `coverage_start_date` | aprovar | início explícito do período técnico |
| temporal | `coverage_end_date` | aprovar | fim explícito do período técnico |
| temporal | `event_start_datetime` | revisar | separar evento, reunião, sessão e pronunciamento; preservar precisão |
| temporal | `event_end_datetime` | revisar | separar ao menos evento e reunião; não inferir término |
| instituição | `arena_name` | revisar | ocorrência institucional com tipo, papel, ID, nome e linhagem |
| instituição | `arena_acronym` | revisar | sigla por ocorrência institucional; nunca chave isolada |
| evento | `event_id` | aprovar | escalar por ocorrência; namespace da fonte |
| evento | `meeting_id` | revisar | qualificar como `committee_meeting_id` para reunião de comissão/colegiado; nunca sessão plenária |
| evento | `session_id` | revisar | separar sessão plenária e sessão legislativa |
| evento | `speech_id` | revisar | preferir ID oficial de pronunciamento; segmento permanece distinto |
| evento | `event_title` | revisar | separar título de evento, reunião, sessão e fase |
| evento | `event_status_source` | revisar | separar código e descrição por entidade e fonte |
| evento | `speech_type_source` | revisar | preservar estrutura oficial de tipo de uso da palavra |
| proposição | `proposition_id` | revisar | separar proposição, matéria e processo legislativo |
| proposição | `proposition_type_acronym` | revisar | separar tipos por entidade e preservar identificação composta |
| proposição | `proposition_number` | aprovar | número comum para identificação analítica, sempre com ano e contexto |
| proposição | `proposition_year` | aprovar | ano comum para identificação analítica, somente quando explícito |
| proposição | `proposition_abstract_source` | aprovar | somente ementa explícita, literal e vinculada à entidade ou versão |
| documento | `document_id` | revisar | preservar múltiplos IDs com função e namespace próprios |
| documento | `document_type_source` | revisar | separar taxonomia oficial de classificação derivada |
| documento | `document_url` | revisar | preservar todas as URLs com função e contexto de requisição |
| documento | `document_media_type` | revisar | separar tipo declarado, cabeçalho HTTP e detecção técnica |
| parecer | `opinion_deliberative_status_source` | revisar | preservar como derivação do coletor; `_source` só para campo oficial |
| parecer | `opinion_superseded_source` | revisar | distinguir vencido de substituído e separar derivado de oficial |
| pessoa | `person_official_id` | revisar | preservar IDs por namespace, papel institucional e ocorrência |
| pessoa | `person_name_source` | revisar | separar nomes por papel e impedir identidade somente por nome |
| pessoa | `speaker_role_source` | revisar | separar papel da fala, cargo, função e forma de tratamento |
| contexto parlamentar | `party_acronym_source` | revisar | preservar partido por papel, tempo e namespace |
| geografia | `federative_unit_source` | revisar | preservar UF com papel geográfico e contexto temporal |
| demografia | `sex_or_gender_source_reported` | revisar | representar somente o rótulo de sexo registrado pela fonte e documentar sua insuficiência para identidade de gênero |
| texto | `text_content_raw` | revisar | separar artefatos textuais por origem, papel, entidade, ordem e método |
| texto | `text_status_source` | revisar | reclassificar status como controle derivado por tentativa do coletor |
| controle técnico | `request_metadata` | aprovar | preservar objeto da requisição sem preencher categorias substantivas |
| controle técnico | `response_metadata` | aprovar | preservar objeto da resposta associado à requisição correspondente |
| classificação temática | `speech_indexing_source_raw` | aprovar | preservar literalmente `Indexacao` e `keywords`, qualificados por fonte, entidade e caminho |
| classificação temática | `proposition_subject_source` | aprovar | preservar temas estruturados com código, rótulo, relevância, namespace, ordem e entidade-alvo |

## Detalhamento das decisões

### Proveniência

#### `source` — aprovar

Finalidade: identificar o sistema de origem declarado no envelope raw.

Exemplo:

```json
{"source": "senado"}
```

Limites aceitos: não derivar automaticamente a casa legislativa e não
harmonizar o valor com categorias da API.

#### `dataset` — aprovar

Finalidade: identificar a coleção temática ou operacional.

Exemplo:

```json
{"dataset": "ccj_notas"}
```

Limites aceitos: não confundir dataset com entidade legislativa e não fundir
nomes semelhantes entre fontes.

#### `record_type` — aprovar

Finalidade: identificar a forma estrutural do registro dentro do dataset.

Exemplos:

```text
senado + ccj_notas + agenda_periodo
senado + ccj_notas + reuniao_detalhe
senado + ccj_notas + notas_taquigraficas
camara + ccjc_eventos + notas_taquigraficas
```

Mesmo `record_type` em fontes ou datasets diferentes não implica o mesmo
schema.

#### `source_record_id` — aprovar

Finalidade: preservar o `source_id` técnico do registro coletado.

Exemplo:

```json
{"source_id": "senado:senador:3:detalhe"}
```

Limites aceitos: não substituir IDs de evento, reunião, sessão, documento ou
pessoa; não decompor para preencher categorias.

#### `collected_at` — aprovar

Finalidade: registrar quando ocorreu a coleta.

Exemplo:

```json
{"collected_at": "2026-05-28T01:19:42+00:00"}
```

Limites aceitos: não confundir com ocorrência, publicação ou sessão; preservar
valor lexical, tipo e fuso originais; falha de cast é preservada e reportada.

#### `original_field_path` — revisar

Finalidade: apontar a origem raw de cada valor.

Exemplo da representação desejada:

```json
{
  "canonical_field": "meeting_id",
  "normalized_value": "1234",
  "lineage": [
    {
      "original_field_path": "$.reuniao.codigo",
      "original_value": "1234"
    },
    {
      "original_field_path": "$.agenda.reuniao.codigo",
      "original_value": "1234"
    }
  ]
}
```

Direção: um caminho é escalar por ocorrência de linhagem, mas uma entidade ou
registro pode possuir várias ocorrências. `[]` não fornece identidade de
elemento.

### Temporal

#### `coverage_start_date` e `coverage_end_date` — aprovar

Finalidade: representar somente o período técnico explícito da consulta,
coleta ou partição.

Exemplo:

```json
{
  "coverage_start_date": "2025-01-01",
  "coverage_end_date": "2025-01-31"
}
```

Limites aceitos: não afirmar que houve dados em todos os dias, não confundir
com datas de eventos e não inferir a ponta ausente do intervalo.

#### `event_start_datetime` e `event_end_datetime` — revisar

Problema: a proposta agrega tempos de evento, reunião, sessão e fala.

Exemplos que precisam permanecer distintos:

```json
{"event_start_datetime": "2025-03-12T10:00:00-03:00"}
```

```json
{"meeting_start_datetime": "2025-03-12T10:00:00-03:00"}
```

```json
{"session_start_date": "2025-03-12"}
```

Direção: criar categorias por entidade e pela precisão observada. Data sem
hora não será promovida para meia-noite. Listas mantêm uma ocorrência temporal
por entidade.

### Instituições

#### `arena_name` e `arena_acronym` — revisar

Problema: casa, órgão, comissão e colegiado, além dos papéis de criador,
organizador, recebedor e participante, não são intercambiáveis.

Exemplo da representação desejada:

```json
{
  "institution_role": "organizador",
  "institution_official_id": "id-observado",
  "institution_name_source": "Comissão de Constituição e Justiça e de Cidadania",
  "institution_acronym_source": "CCJC"
}
```

Exemplo de outra fonte:

```json
{
  "institution_role": "colegiado_da_reuniao",
  "institution_name_source": "Comissão de Constituição, Justiça e Cidadania",
  "institution_acronym_source": "CCJ"
}
```

Direção: `CCJ` e `CCJC` não são aliases automáticos. Nome e sigla não
substituem ID e namespace. Eventos com vários órgãos mantêm todas as
ocorrências.

### Eventos, reuniões, sessões e pronunciamentos

#### `event_id` — aprovar

Finalidade: ID oficial de evento no namespace da fonte.

Exemplo:

```json
{"source": "camara", "event_id": 60995}
```

Limites aceitos: não substituir `source_record_id`, não presumir unicidade
entre fontes e não equiparar automaticamente a reunião ou sessão.

#### `meeting_id` — aprovar

Finalidade: ID oficial de uma reunião de comissão ou colegiado.

Exemplo:

```json
{"source": "senado", "meeting_id": "1234"}
```

Direção: escalar por ocorrência de reunião. O candidato
`F13699 ↔ F13701` foi posteriormente aprovado como duplicação técnica criada
pelo coletor no escopo de `senado/ccj_notas`. Qualquer aplicação futura ainda
deverá comprovar o escopo e conservar ambas as linhagens.

#### `session_id` — revisar

Problema: sessão plenária e sessão legislativa são entidades diferentes.

Exemplo observado localmente:

```json
{
  "CodigoSessao": "526727",
  "CodigoSessaoLegislativa": "873"
}
```

Direção:

```text
plenary_session_id
legislative_session_id
```

A segunda categoria só permanecerá se houver caminho preenchido correspondente
no inventário aprovado.

#### `speech_id` — revisar

Problema: o Senado identifica oficialmente o pronunciamento; isso não é o ID
de um segmento taquigráfico.

Exemplo observado localmente:

```json
{
  "CodigoPronunciamento": "519407",
  "UrlTexto": "https://www25.senado.leg.br/web/atividade/pronunciamentos/-/p/texto/519407"
}
```

Direção:

```text
pronouncement_official_id
```

As duas hipóteses globais de alias entre variantes de caixa e estilo do
pronunciamento (`F22062 ↔ F22065` e `F23487 ↔ F23490`) foram aprovadas como
duplicações técnicas produzidas pelo construtor compartilhado dos coletores,
com escopos separados para `CN` e `SF`. As ocorrências oficiais aninhadas
`CodigoPronunciamento` e `id` mantêm linhagem própria.

#### `event_title` — revisar

Problema: título de evento, título de reunião, descrição de sessão e título de
fase possuem papéis diferentes.

Exemplos:

```json
{"event_title_source": "Audiência Pública sobre determinado tema"}
```

```json
{"session_description_source": "190ª Sessão Deliberativa Ordinária"}
```

```json
{"event_phase_title_source": "Abertura dos trabalhos"}
```

Direção: manter categorias separadas e não gerar títulos a partir de texto,
ementa ou descrição de outra entidade.

#### `event_status_source` — revisar

Problema: código, rótulo e entidade do status foram colapsados.

Exemplo oficial da Câmara:

```json
{
  "event_status_code_source": "5",
  "event_status_label_source": "Cancelada"
}
```

Direção: separar código e descrição; distinguir status de evento, reunião,
sessão e obtenção técnica. Tabelas oficiais precisam ser fechadas,
datadas/versionadas e não substituem o raw.

#### `speech_type_source` — revisar

Problema: `tipoDiscurso` e o objeto oficial `TipoUsoPalavra` não podem ser
reduzidos a uma string nem presumidos equivalentes entre fontes.

Exemplos oficiais do Senado:

```json
{
  "Codigo": "4819",
  "Sigla": "DIS",
  "Descricao": "Discurso",
  "IndicadorAtivo": "S"
}
```

```json
{
  "Codigo": "4835",
  "Sigla": "BCO",
  "Descricao": "Breve comunicação",
  "IndicadorAtivo": "N"
}
```

Direção:

```text
speech_use_type_code_source
speech_use_type_acronym_source
speech_use_type_description_source
speech_use_type_active_indicator_source
```

Categoria inativa continua válida para registros históricos. Nenhuma
classificação será inferida pelo conteúdo.

### Proposições, matérias e processos

#### `proposition_id` — revisar

Problema: a proposta reúne `IdProposicao`, `dados.id`, `processo.id` e
`codigoMateria`.

Exemplos das entidades distintas:

```json
{"source": "camara", "proposition_official_id": 2252029}
```

```json
{"source": "senado", "legislative_matter_official_id": "123456"}
```

```json
{"source": "senado", "legislative_process_official_id": "987654"}
```

Direção: separar proposição, matéria legada e processo legislativo. Uma
relação entre matéria e processo exige crosswalk oficial ou vínculo
determinístico aprovado.

#### `proposition_type_acronym` — revisar

Problema: siglas de tipos de proposição, processo e documento possuem
vocabulários e namespaces próprios; `IdentificacaoPec` pode ser composta.

Exemplos:

```json
{
  "cod": "136",
  "sigla": "PEC",
  "nome": "Proposta de Emenda à Constituição"
}
```

```json
{
  "IdentificacaoPec": "PEC 45/2019"
}
```

Direção:

```text
proposition_type_acronym_source
legislative_process_type_acronym_source
document_type_acronym_source
proposition_identification_source
```

Identificação composta não será decomposta automaticamente. Metadados das
tabelas de referência não preencherão campos ausentes no raw.

#### `proposition_number` e `proposition_year` — aprovar

Decisão do pesquisador: manter as duas colunas comuns porque proposições são
conhecidas e utilizadas analiticamente pelo formato número/ano. A separação
por fonte ou por entidade prejudicaria esse uso cotidiano sem ser necessária
para preservar os IDs oficiais.

Exemplo:

```json
{
  "proposition_number": 2506,
  "proposition_year": 2020
}
```

Representação humana:

```text
2506/2020
```

Quando mais de um tipo de proposição estiver no mesmo universo, a sigla do
tipo continua necessária para desambiguação:

```text
PL 2506/2020
PEC 2506/2020
```

Condições da aprovação:

- `proposition_number` e `proposition_year` são atributos analíticos comuns;
- compartilhar esses atributos não funde os IDs oficiais de proposição,
  matéria ou processo;
- ambos mantêm fonte, entidade, caminho original e demais elementos de
  proveniência;
- o ano deve estar explicitamente estruturado;
- não extrair número ou ano de texto livre, URL, nome de arquivo ou
  identificação composta sem regra humana posterior;
- o número não substitui `proposition_official_id`,
  `legislative_matter_official_id` ou `legislative_process_official_id`;
- tipos e valores originais continuam preservados, mesmo se uma representação
  analítica comum vier a ser aprovada posteriormente.

#### `proposition_abstract_source` — aprovar

Finalidade: preservar a ementa explicitamente fornecida pela fonte para a
proposição, matéria ou versão correspondente.

Exemplo:

```json
{
  "proposition_number": 2506,
  "proposition_year": 2020,
  "proposition_abstract_source": "Altera o artigo 273 do Decreto-Lei nº 2.848..."
}
```

Condições da aprovação:

- restringir a categoria à ementa estruturada da fonte;
- preservar o texto literalmente;
- manter ID da entidade, fonte, caminho e contexto documental;
- manter ocorrências distintas quando houver versões ou entidades diferentes;
- não fundir `ementa`, `ementaDetalhada`, resumo e texto integral;
- não gerar, completar ou selecionar a ementa por interpretação textual.

### Documentos, pareceres e publicações

#### `document_id` — revisar

Problema: `IdDocumento`, `documento.id` e `idEcmSenado` podem identificar o
documento em sistemas ou repositórios diferentes. Um documento também pode
possuir mais de um desses IDs simultaneamente.

Exemplo da representação desejada:

```json
{
  "document_identifiers": [
    {
      "identifier_role": "legislative_process_document",
      "identifier_namespace": "senado_processo",
      "identifier_value": "98765"
    },
    {
      "identifier_role": "document_repository",
      "identifier_namespace": "senado_ecm",
      "identifier_value": "ECM-123456"
    }
  ]
}
```

Direção: preservar todos os identificadores, cada qual escalar por ocorrência,
com função, namespace, valor e caminho original. Uma equivalência exige
crosswalk oficial ou auditoria recorde a recorde.

#### `document_type_source` — revisar

Problema: a proposta reúne campos oficiais como `siglaTipo` e
`descricaoTipo` com `documento_classe`, que a documentação atual dos
coletores descreve como classificação derivada pelo Falando Nela.

Exemplo da taxonomia oficial do Senado:

```json
{
  "id": 174,
  "sigla": "PARECER_REDACAO",
  "descricao": "Parecer de redação",
  "idTipoSuperior": 173,
  "dataInicio": "2016-08-30"
}
```

Direção:

```text
document_type_id_source
document_type_acronym_source
document_type_description_source
document_type_parent_id_source
document_type_valid_from_source
document_type_valid_to_source
document_class_collector_derived
```

Os campos de vigência pertencem à referência oficial quando observados e não
preenchem automaticamente cada documento. A classificação derivada permanece
auditável, mas não será representada como informada pela API nem reutilizada
automaticamente na v3. A Câmara não receberá uma categoria equivalente à do
Senado por interpretação de despacho ou texto.

#### `document_url` — revisar

Problema: `TextoIntegralUrl`, `url_final`, `linkDownload` e `urlDocumento`
podem representar página pública, endpoint, download, URL solicitada ou URL
final depois de redirecionamentos. Um documento pode possuir várias delas.

Exemplo da representação desejada:

```json
{
  "document_urls": [
    {
      "url_role": "official_document",
      "url": "https://fonte.gov.br/documento/123"
    },
    {
      "url_role": "download",
      "url": "https://fonte.gov.br/documento/123/download"
    },
    {
      "url_role": "final_response",
      "url": "https://cdn.fonte.gov.br/arquivos/123.pdf"
    }
  ]
}
```

Direção: uma URL é escalar por ocorrência, mas um documento pode ter várias.
Cada ocorrência preservará função, fonte, requisição e caminho original.
Nenhuma URL recebe prioridade automática nem serve isoladamente como
identidade documental.

#### `document_media_type` — revisar

Problema: `mimeType` informado nos metadados do documento e `content_type`
observado na resposta HTTP podem divergir e cumprem papéis distintos.

Exemplo:

```json
{
  "document_declared_media_type_source": "application/pdf",
  "retrieval_response_content_type": "text/html; charset=UTF-8"
}
```

Direção:

```text
document_declared_media_type_source
retrieval_response_content_type
detected_file_media_type
```

O tipo detectado, se futuramente produzido, será controle técnico derivado,
com método versionado. Cada cabeçalho de resposta permanecerá associado à
requisição e à URL corretas. Extensão de arquivo não será usada como prova
silenciosa do conteúdo.

#### `opinion_deliberative_status_source` — revisar

Problema: a documentação dos coletores descreve `status_deliberativo` como
classificação derivada de descrição, tramitação, despacho e, em alguns casos,
texto extraído. O campo está observado no raw, mas não pode ser atribuído à
API nem reutilizado como regra v3.

Exemplo:

```json
{"status_deliberativo": "vencido"}
```

Direção:

```text
opinion_deliberative_status_collector_derived
```

O valor permanece como `preservado_sem_normalizacao`, com proveniência e
versão do coletor quando recuperáveis. Somente campos estruturados diretamente
fornecidos pela API poderão originar:

```text
opinion_deliberative_status_code_source
opinion_deliberative_status_label_source
```

#### `opinion_superseded_source` — revisar

Problema: o booleano `vencido` pode ser apenas uma recodificação do status
derivado e “vencido” não equivale necessariamente a “substituído”
(`superseded`).

Exemplo:

```json
{
  "status_deliberativo": "vencido",
  "vencido": true
}
```

Direção:

```text
opinion_defeated_indicator_collector_derived
opinion_defeated_indicator_source
```

O segundo campo somente existirá para indicador oficial explícito. Documentos
vencidos continuam analiticamente válidos e não serão descartados. Nenhum
booleano será inferido de texto, despacho ou tramitação em G02.

### Pessoas e participantes

#### `person_official_id` — revisar

Problema: `id`, `id_deputado` e `CodigoParlamentar` pertencem a namespaces e
papéis institucionais diferentes. Eles identificam recursos parlamentares das
Casas, não necessariamente uma identidade civil universal.

Exemplos:

```json
{"source": "camara", "id": 204379, "nome": "Acácio Favacho"}
```

```json
{
  "source": "senado",
  "CodigoParlamentar": "3",
  "NomeParlamentar": "Antonio Carlos Valadares"
}
```

Direção: usar ocorrências de identificador com `identifier_namespace`,
`identifier_role`, `identifier_value`, fonte e caminho original. Vínculos
entre Casas exigirão crosswalk determinístico e aprovação humana. Nome não
substitui ID.

#### `person_name_source` — revisar

Problema: nome civil, eleitoral, parlamentar, autoral e de exibição possuem
papéis diferentes. `NomeAutor` também pode nomear instituição, não pessoa.

Exemplo:

```json
{
  "person_names": [
    {
      "name_role": "civil",
      "name_value_source": "ACÁCIO DA SILVA FAVACHO NETO"
    },
    {
      "name_role": "parliamentary_or_electoral",
      "name_value_source": "Acácio Favacho"
    }
  ]
}
```

Direção:

```text
person_civil_name_source
person_parliamentary_name_source
person_electoral_name_source
speaker_display_name_source
author_actor_type_source
author_actor_name_source
```

O nome original será preservado com capitalização, acentos, papel, tempo e
proveniência. Variantes não são aliases automáticos e não resolvem identidade
sozinhas.

#### `speaker_role_source` — revisar

Problema: `papelPalavra`, `CargoAutor`, `FuncaoAutor` e `FormaTratamento`
representam conceitos diferentes e são contextuais, não atributos permanentes
da pessoa.

Exemplo:

```json
{
  "papelPalavra": "Orador",
  "CargoAutor": "Senador",
  "FuncaoAutor": "Relator",
  "FormaTratamento": "Senador"
}
```

Direção:

```text
speaking_role_source
author_office_source
author_function_source
form_of_address_source
```

Cada valor será ligado à ocorrência de participação e à entidade correta:
fala, reunião, sessão, documento ou processo. Uma pessoa pode exercer vários
papéis simultaneamente. `FormaTratamento` não infere cargo, e nenhum papel
será extraído do conteúdo textual. `TipoUsoPalavra` permanece modalidade da
fala, não papel da pessoa.

### Partido, geografia e demografia

#### `party_acronym_source` — revisar

Problema: `siglaPartido`, `Partido` e `SiglaPartidoParlamentar` podem
representar sigla, objeto, nome, partido atual, histórico, de mandato ou da
data da fala.

Exemplos:

```json
{
  "source": "camara",
  "id": 36899,
  "sigla": "MDB",
  "nome": "Movimento Democrático Brasileiro"
}
```

```json
{
  "SiglaPartidoParlamentar": "MDB",
  "SiglaPartidoParlamentarNaData": "PSDB"
}
```

Direção: manter `party_acronym_source` apenas para campo explicitamente
definido como sigla e representá-lo numa ocorrência de filiação ou contexto
com ID, nome, papel, datas e namespace quando observados. Partido atual não
sobrescreve partido na data da fala. Sigla isolada não resolve identidade.

#### `federative_unit_source` — revisar

Problema: `siglaUf`, `UF` e `UfParlamentar` podem indicar representação
parlamentar, representação na data da fala, nascimento ou outro contexto.

Exemplos:

```json
{"UfParlamentar": "SE"}
```

```json
{"UfNaturalidade": "MG"}
```

```json
{"UfParlamentarNaData": "AM"}
```

Direção: preservar a UF como valor comparável dentro de uma ocorrência com
`federative_unit_role`, fonte, tempo e caminho. UF não será inferida de
partido, endereço, nome da Casa ou texto.

#### `sex_or_gender_source_reported` — revisar

Decisão do pesquisador: seguir estritamente os dados disponíveis nas APIs,
reconhecendo que elas não representam adequadamente identidade de gênero e
que essa limitação é substantiva, inclusive para parlamentares trans.

Exemplos observados:

```json
{"source": "camara", "sexo": "M"}
```

```json
{"source": "senado", "SexoParlamentar": "Masculino"}
```

Direção:

```text
sex_label_recorded_by_source
```

Condições:

- transportar literalmente apenas os campos observados `sexo` e
  `SexoParlamentar`, ou outros caminhos explicitamente definidos como sexo;
- não chamar esses valores de identidade de gênero;
- não sugerir que foram autodeclarados pela pessoa;
- não criar `gender_*` sem campo de gênero observado e documentado;
- não inferir identidade trans, sexo ou gênero por nome, pronome, fotografia,
  tratamento, biografia ou conteúdo parlamentar;
- não substituir o valor de uma API pelo de outra fonte;
- preservar divergências históricas e entre sistemas;
- eventual harmonização de rótulos como `M` e `Masculino` será separada do
  original, fechada, versionada e sujeita a aprovação;
- declarar nos produtos analíticos que o campo é insuficiente, sozinho, para
  medir identidade de gênero ou representação trans.

Uma futura base de identidade de gênero, se autorizada e sustentada por fonte
adequada, deverá ter proveniência e coluna próprias; ela não corrigirá nem
sobrescreverá retroativamente o rótulo registrado pelas APIs.

### Transporte de texto

#### `text_content_raw` — revisar

Problema: `TextoIntegral`, `texto` e `transcricao` podem representar texto
oficial, cópia, extração de documento, transcrição ou segmento. O sufixo
`raw` não descreve corretamente todas essas origens.

Exemplo da representação desejada:

```json
{
  "text_artifacts": [
    {
      "text_role": "official_integral_text",
      "production_method": "source_api",
      "text_content": "Texto...",
      "original_field_path": "$.TextoIntegral"
    },
    {
      "text_role": "document_text_extraction",
      "production_method": "collector_pdf_extraction",
      "text_content": "Texto...",
      "original_field_path": "$.texto"
    }
  ]
}
```

Direção: preservar valor, tamanho, hash, caminho, método, entidade, ordem e
multiplicidade por artefato. Notas de reunião e notas de sessão plenária
permanecem distintas. Estruturas de `senado/ccj_notas` não serão concatenadas
ou achatadas. As três hipóteses de alias `TextoIntegral ↔ texto` foram
reclassificadas a partir do código dos coletores: as duas da Câmara foram
aprovadas como duplicações técnicas restritas aos respectivos `record_type`, e
a do Senado também foi aprovada no escopo demonstrado de `senado/ccj_notas`.
Mesmo nos pares criados com a mesma variável, as versões históricas exigem
auditoria exata antes de deduplicação; todos os caminhos de proveniência serão
conservados.

#### `text_status_source` — revisar

Problema: a documentação e o código operacionais indicam que `texto_status` é
produzido pelo coletor, com valores como `disponivel`, `ausente`, `erro`,
`fora_escopo` e `baixado`. Ele não é status informado pela API.

Exemplo:

```json
{
  "text_retrieval_attempts": [
    {
      "method": "api_texto_integral",
      "status": "ausente"
    },
    {
      "method": "api_notas_sessao",
      "status": "disponivel"
    }
  ]
}
```

Direção:

```text
text_retrieval_status_collector_derived
```

O status pertence à tentativa e mantém método, ordem, request/response, erro e
versão do coletor. Estado de presença do texto permanece separado. Contradição
entre status e conteúdo gera falha de validação, nunca preenchimento ou
correção silenciosa.

### Controles técnicos

#### `request_metadata` — aprovar

Finalidade: preservar método, caminho e parâmetros da requisição como objeto
técnico.

Exemplo:

```json
{
  "method": "GET",
  "path": "dadosabertos/senador/3.json",
  "params": {}
}
```

Condições: preservar estrutura, valores e tipos; não preencher categorias de
domínio a partir de caminho ou parâmetros; manter cada tentativa separada;
detectar e bloquear materialização futura se houver segredo, sem remoção
silenciosa.

#### `response_metadata` — aprovar

Finalidade: preservar URL efetiva, código HTTP e cabeçalhos da resposta.

Exemplo:

```json
{
  "status_code": 200,
  "url": "https://legis.senado.leg.br/dadosabertos/senador/3.json",
  "headers": {
    "content-type": "application/json",
    "content-length": "977"
  }
}
```

Condições: associar a resposta à requisição correta; não usar URL, status HTTP
ou cabeçalhos para preencher URL documental, status de domínio ou MIME
declarado do documento; preservar tentativas e divergências; validar possíveis
segredos antes de publicação futura.

## Questão transversal — coordenadas técnicas e índices de execução

Estado: **aprovada**.

A palavra “indexação” não é usada nesta seção no sentido temático empregado
pelas APIs legislativas. Esta seção trata somente de posições em arrays,
coordenadas raw, estruturas temporárias de busca e índices físicos.

A proposta das 40 colunas não inclui uma coluna canônica específica para
índice de array. As specs, porém, exigem preservar ordem e multiplicidade e
determinam que o curinga `[]` não seja tratado como identidade do elemento.

### `source_record_coordinate` — aprovado

**Finalidade:** localizar de forma reproduzível o registro raw que contém a
ocorrência.

Componentes propostos e exemplos:

1. **`source_file_path`.** Caminho relativo à raiz raw. Exemplo:
   `senado/ccj_notas/metadata/run-id.jsonl`.
2. **`source_record_number`.** Número inteiro positivo. Exemplo: `1842`.
3. **`record_locator_scheme`.** Declara como interpretar o número:
   - `jsonl_physical_line_1_based`: linha física 1842 do JSONL;
   - `csv_data_row_1_based`: 1842ª linha de dados, sem contar o cabeçalho;
   - `parquet_row_1_based`: 1842ª linha lógica do arquivo;
   - formatos diferentes exigirão esquema explícito próprio.
4. **Escopo do registro.** `source=senado`, `dataset=ccj_notas` e
   `record_type=reuniao_detalhe`, por exemplo.

Riscos:

- um número sem `record_locator_scheme` é ambíguo;
- confundir linha física com contagem de linhas não vazias pode impedir a
  localização do raw;
- caminho absoluto tornaria o artefato dependente da máquina;
- `source_record_id` do envelope não substitui arquivo e número do registro;
- a coordenada técnica não é identidade da reunião, documento ou pessoa.

Recomendação: tornar `source_record_coordinate` obrigatório para toda
ocorrência normalizada futura, usando caminho relativo e convenção declarada.
Para JSONL/NDJSON, adotar linha física começando em `1`, coerente com leitura
humana e com o contrato já aprovado.

### `source_value_coordinate` — aprovado

**Finalidade:** localizar o valor exato dentro do registro, inclusive quando
ele está em coleções aninhadas.

Componentes propostos e exemplos:

1. **`catalog_field_path`.** Caminho de tipo usado no inventário:
   `$.payload.DetalheReuniao.reuniao.partes[].itens[].doma.idProcesso`.
   Ele informa a família do campo, não a ocorrência.
2. **`source_value_pointer`.** JSON Pointer concreto:
   `/payload/DetalheReuniao/reuniao/partes/1/itens/0/doma/idProcesso`.
   Nesse exemplo, a segunda parte e o primeiro item são localizados com
   índices `zero_based`.
3. **`source_container_shape`.** Tipos efetivos dos contêineres no caminho.
   Exemplo: `partes=array`, `itens=array`. Em outro registro, `partes=object`
   será preservado e seu pointer não inventará um índice `[0]`.
4. **`source_occurrence_id`.** Hash técnico determinístico do escopo do
   registro mais o pointer concreto. Exemplo conceitual:
   `sha256(source + dataset + record_type + file + record + pointer)`.

Riscos:

- somente `catalog_field_path` com `[]` não distingue ocorrências;
- valores repetidos poderiam ser colapsados;
- arrays paralelos poderiam ser associados falsamente pela posição;
- posição em array muda se o raw mudar, motivo adicional para a imutabilidade
  já aprovada;
- posição não substitui `document_official_id`,
  `person_official_id` ou qualquer outra identidade oficial;
- hash sem a composição explícita seria opaco e não auditável.

Recomendação: preservar conjuntamente caminho catalogado e pointer concreto,
com índices de array começando em `0`, forma original dos contêineres e hash
reproduzível. Relações entre elementos usarão ID oficial preenchido quando
existir; posição servirá para ordem e proveniência, nunca para presumir
identidade entre coleções.

### `technical_index_policy` — aprovado

**Finalidade:** impedir que estruturas usadas para acelerar buscas sejam
confundidas com dados científicos ou classificação temática.

Categorias de índice e exemplos:

1. **Índice temático da fonte.** `Indexacao` do Senado e `keywords` da Câmara,
   já aprovados em `speech_indexing_source_raw`; são metadados de domínio.
2. **Índice temporário de candidatos a alias.** Exemplo: agrupamento por
   `source + dataset + record_type + chave terminal + tipos + hash tipado`.
   Produz candidatos, não equivalência.
3. **Índice físico de consulta.** Exemplo futuro:
   `(source, dataset, record_type, source_record_id)` ou
   `(committee_meeting_id)`. É decisão de armazenamento e desempenho.

Riscos:

- chamar tudo apenas de `index` mistura tema, auditoria e desempenho;
- um match no índice de candidatos poderia ser tratado incorretamente como
  alias confirmado;
- índices físicos prematuros podem cristalizar um desenho ainda não aprovado;
- nenhum desses índices substitui coordenada ou proveniência.

Recomendação: manter `Indexacao` e `keywords` somente na família temática;
manter índices de candidatos a alias como artefatos técnicos temporários,
reprodutíveis e descartáveis; adiar índices físicos até a escolha da
materialização e dos padrões de consulta. Não criar uma coluna canônica
genérica chamada `index`.

As três recomendações foram aprovadas. A aprovação não autoriza normalização,
Batch ou alteração das specs antes da aprovação final da consolidação.

## Família omitida — indexação temática e assuntos oficiais

Estado: **aprovada**.

A proposta global não incluiu uma coluna ou família canônica para a indexação
temática fornecida pelas APIs. A ausência é material porque esses campos
transportam classificação temática oficial da fonte, embora não substituam o
texto integral.

Categorias observadas:

1. **Indexação de pronunciamento do Senado.** O campo `Indexacao` é uma string
   associada ao pronunciamento. Exemplo oficial, no pronunciamento `507276`:
   `RELATOR, PROJETO DE LEI DA CAMARA (PLC), CRIAÇÃO, LEI FEDERAL, POLITICA
   NACIONAL, AGRICULTURA, ZONA URBANA.`
2. **Palavras-chave de discurso da Câmara.** O schema oficial
   `DeputadoDiscurso` declara `keywords` como string. Exemplo observado:
   `Discussão,Mensagem do Poder Executivo,favorável`.
3. **Classificação temática estruturada de proposição da Câmara.** O endpoint
   de temas retorna ocorrências com código, nome e relevância. Exemplo para a
   proposição `2252029`: `codTema=43`, `tema=Direito Penal e Processual Penal`,
   `relevancia=0`. Essa classificação pertence à proposição, não ao discurso.

Riscos:

- descartar `Indexacao` e `keywords` por não estarem entre as 40 colunas;
- misturá-los com `text_content_raw`, ementa ou resumo;
- dividir automaticamente por vírgula ou quebra de linha e perder termos
  compostos ou agrupamentos da fonte;
- tratar os vocabulários da Câmara e do Senado como aliases;
- fundir palavras-chave de discursos com temas de proposições, processos,
  documentos ou normas.

Direção aprovada: acrescentar uma família canônica de classificação
temática vinculada explicitamente à entidade indexada. Para strings como
`Indexacao` e `keywords`, preservar o valor integral em
`speech_indexing_source_raw`, com fonte, campo original e ordem. Uma lista
derivada de termos somente poderá ser produzida por regra de separação
específica da fonte, aprovada e reversível. Quando a API já fornecer estrutura,
como os temas de proposição da Câmara, preservar cada ocorrência em
`proposition_subject_source`, com código, rótulo, relevância, namespace, ordem
e entidade-alvo. Similaridade funcional não autoriza alias exato entre Casas
ou entre entidades.

## Hipóteses de alias — primeiro bloco

### `alias-senado-meeting-id` — revisão de escopo aprovada

Observação humana: `CodigoReuniao` provavelmente diz respeito somente a
comissões.

A inspeção confirma a observação para `senado/ccj_notas` e mostra que o par
precisa ser reclassificado:

- o dataset seleciona somente reuniões cujo colegiado é a `CCJ` ou possui o
  código `34`;
- o detalhe oficial da reunião `14657` identifica o colegiado criador como
  `Comissão de Constituição, Justiça e Cidadania`, do tipo
  `Comissão Permanente`;
- o payload oficial de detalhe usa `DetalheReuniao.reuniao.codigo`;
- as notas taquigráficas usam também `codigoReuniaoComiss`;
- na raiz dos registros `notas_taquigraficas` e
  `notas_taquigraficas_status`, o coletor atribui deliberadamente o mesmo valor
  local `codigo` a `CodigoReuniao` e `codigo_reuniao`.

Exemplo produzido pelo coletor:

```json
{
  "CodigoReuniao": "14657",
  "codigo_reuniao": "14657"
}
```

Assim, `F13699 ↔ F13701` não representa dois campos oficiais independentes
cuja equivalência tenha sido apenas sugerida pela grafia. No escopo atual, são
duas cópias de compatibilidade criadas pelo coletor a partir do identificador
da mesma reunião da CCJ.

Direção aprovada: substituir o alias genérico por uma regra estritamente
limitada a `source=senado`, `dataset=ccj_notas` e aos `record_type` em que o
coletor produz as duas cópias. O destino conceitual deve ser um identificador
`committee_meeting_id` de reunião de comissão/colegiado, com namespace do
Senado; nunca um identificador de sessão plenária. Ocorrências oficiais
aninhadas mantêm sua linhagem própria. Dados de versões antigas ainda deverão
ser auditados antes de qualquer deduplicação na camada normalizada.

Garantia aprovada: nenhum registro ou campo raw será alterado, removido,
renomeado ou regravado por esta decisão. `CodigoReuniao` e `codigo_reuniao`
permanecem exatamente como coletados. Uma implementação futura, se aprovada,
somente poderá ler o raw e produzir um artefato normalizado separado, com
linhagem para todas as ocorrências originais e relatório explícito de qualquer
divergência.

### `alias-camara-event-id` — revisão de escopo aprovada

A API v2 da Câmara identifica seu recurso oficial de evento com o campo
inteiro `id`. Em `camara/ccjc_eventos`, os eventos são descobertos pelo recurso
do órgão `2003`, correspondente à CCJC. O evento oficial `81996`, por exemplo,
possui `id=81996`, `descricaoTipo=Reunião Deliberativa` e órgão
`CCJC`, do tipo `Comissão Permanente`.

No registro de notas taquigráficas, o coletor recebe esse `id` como
`event_id` e cria deliberadamente duas cópias na raiz:

```json
{
  "CodigoEvento": 81996,
  "evento_id": 81996
}
```

Outros `record_type`, como `escriba_html` e `escriba_status`, podem conter
somente `evento_id`. O evento oficial completo permanece aninhado em
`metadata.evento`, com seu campo `id`.

Foi investigada a hipótese de `CodigoEvento` ou `evento_id` representarem o
tipo de evento, em vez da ocorrência:

- o contrato OpenAPI define `GET /eventos/{id}` como consulta a “um evento
  específico” e descreve `id` como “identificador numérico do evento”;
- o coletor lê literalmente `event.get("id")` e repassa esse valor para
  `CodigoEvento` e `evento_id`;
- o vocabulário de tipos é separado e usa `codTipoEvento`; por exemplo,
  `112 = Reunião Deliberativa`;
- em maio de 2026, eventos da CCJC classificados como
  `Reunião Deliberativa` possuíam IDs distintos, entre eles `81867`, `81868`,
  `81990`, `81996`, `82014`, `82145`, `82163` e `82281`.

Conclusão: nos campos avaliados, o número identifica a ocorrência oficial do
evento, não sua categoria. O ID numérico deve ser tratado como opaco: a
aparente progressão não autoriza inferir ordem, quantidade, data ou ausência de
eventos. Tipo e ocorrência permanecem em domínios separados.

Assim, `F00282 ↔ F00284` não representa dois campos oficiais independentes da
API v2. Representa duplicação de compatibilidade criada pelo coletor nos
registros de notas.

Direção aprovada: reclassificar a hipótese como regra restrita a
`source=camara`, `dataset=ccjc_eventos` e `record_type=notas_taquigraficas`.
O destino conceitual permanece `event_id`, com namespace `camara.eventos`,
porque esse é o recurso oficial da API. A classificação observada — por
exemplo, reunião deliberativa da CCJC — e a arena devem acompanhar o evento,
sem convertê-lo automaticamente em sessão plenária nem inventar um ID oficial
de reunião que a API não forneceu. Versões antigas ainda exigem auditoria antes
de deduplicação na camada normalizada. O raw permanece imutável.

### `alias-camara-notas-text` — revisão de escopo aprovada

No `record_type=notas_taquigraficas` de `camara/ccjc_eventos`, o coletor
extrai os segmentos do HTML do Escriba, une seus textos com duas quebras de
linha e atribui o mesmo valor agregado a `TextoIntegral` e `texto`.

Exemplo:

```json
{
  "TextoIntegral": "O SR. PRESIDENTE — Declaro aberta a reunião.",
  "texto": "O SR. PRESIDENTE — Declaro aberta a reunião."
}
```

Os dois campos da raiz são cópias do coletor, não dois campos oficiais
independentes. O texto agregado também não é alias de cada
`segmentos[].texto`: o segmento é uma unidade ordenada com orador, horário,
tipo e `id_segmento`, enquanto a raiz representa a concatenação do conjunto.

Direção aprovada: reclassificar `F00283 ↔ F00371` como duplicação técnica
restrita a `source=camara`, `dataset=ccjc_eventos` e
`record_type=notas_taquigraficas`. O destino futuro deve ser um artefato
textual agregado de notas, qualificado por método
`scraping_escriba_html`, evento, arena, ordem e linhagem para os segmentos.
Não classificá-lo como conteúdo raw da API: o HTML original é raw; a string
foi extraída e montada pelo coletor.

### `alias-camara-parecer-text` — revisão de escopo aprovada

No `record_type=parecer_pec_texto` de `camara/pareceres_pec`, o coletor
extrai texto do documento oficial, remove espaços externos e atribui o mesmo
valor — ou o mesmo `null` — a `TextoIntegral` e `texto`.

Exemplo:

```json
{
  "TextoIntegral": "Texto extraído do parecer.",
  "texto": "Texto extraído do parecer.",
  "metodo_obtencao": "pdf_text_extraction"
}
```

Os dois campos são cópias do coletor. O nome `TextoIntegral` não garante que a
extração seja materialmente completa: PDFs digitalizados podem produzir
ausência ou extração parcial, e cada parecer, relatório, voto em separado ou
versão documental continua sendo artefato distinto.

Direção aprovada: reclassificar `F00400 ↔ F00504` como duplicação técnica
restrita a `source=camara`, `dataset=pareceres_pec` e
`record_type=parecer_pec_texto`. O destino futuro deve ser um artefato de texto
extraído de documento, associado ao documento, URL, hash, método, classe,
status e linhagem. Não fundir textos de documentos ou versões diferentes da
mesma proposição.

Regra comum proposta aos dois pares: o raw permanece imutável; versões antigas
serão auditadas antes de qualquer deduplicação na camada normalizada; uma
divergência entre as cópias será preservada e reportada, nunca resolvida por
prioridade silenciosa.

### `alias-senado-notas-text` — revisão de escopo aprovada

No `record_type=notas_taquigraficas` de `senado/ccj_notas`, o coletor
seleciona uma fonte textual, constrói a variável local `texto` e atribui o
mesmo valor a `TextoIntegral` e `texto`.

As categorias de obtenção permanecem distintas:

1. **API taquigráfica normal.**
   `metodo_obtencao=api_taquigrafia_notas_reuniao`. Exemplo agregado a partir
   dos quartos: `Primeiro trecho.\n\nSegundo trecho.`
2. **API taquigráfica forçada.**
   `metodo_obtencao=api_taquigrafia_notas_reuniao_forcado`, usada até
   2024-12-31 quando o metadado indicava ausência. Exemplo:
   `Texto recuperado apesar do indicador N.`
3. **Página pública HTML.**
   `metodo_obtencao=pagina_notas_reuniao_html`, fallback quando a API falha ou
   não entrega texto. Exemplo:
   `10:35\nR\nO SR. PRESIDENTE - Declaro aberta a reunião.`

Exemplo do par na raiz:

```json
{
  "TextoIntegral": "Primeiro trecho.\n\nSegundo trecho.",
  "texto": "Primeiro trecho.\n\nSegundo trecho.",
  "metodo_obtencao": "api_taquigrafia_notas_reuniao"
}
```

O texto da raiz é uma cópia de compatibilidade criada pelo coletor. Ele não é
alias das ocorrências aninhadas de `notas_taquigraficas.quartos[].texto`:
estas preservam os quartos, sua ordem e outros metadados; a raiz contém uma
concatenação com espaços externos removidos. No fallback HTML, a raiz deriva
de outra fonte e método.

Direção aprovada: reclassificar `F13700 ↔ F16508` como duplicação técnica
restrita a `source=senado`, `dataset=ccj_notas` e
`record_type=notas_taquigraficas`. O destino futuro será um artefato textual
agregado de notas da reunião de comissão, mantendo método, tentativas, ordem,
URL, resposta, `committee_meeting_id`, arena e linhagem para os quartos ou
para o HTML. As três categorias de obtenção não serão fundidas nem tratadas
como fontes equivalentes. O raw permanece imutável e divergências históricas
entre `TextoIntegral` e `texto` serão preservadas e reportadas.

### `alias-senado-pronouncement-id-congresso` — revisão de escopo aprovada

O coletor de `senado/congresso_discursos` consulta o serviço do Senado com
`siglaCasa=CN`. Na resposta oficial, um pronunciamento pode trazer `id` e
`CodigoPronunciamento` com o mesmo valor. O extrator prefere
`CodigoPronunciamento`, usa `id` como fallback, converte o resultado para
string e o construtor grava duas cópias na raiz do
`record_type=pronunciamento_texto`.

Exemplo oficial e cópias do coletor:

```json
{
  "house_scope": "CN",
  "metadata": {
    "pronunciamento": {
      "id": "507611",
      "CodigoPronunciamento": "507611",
      "TipoUsoPalavra": {
        "Codigo": "4823",
        "Sigla": "POR",
        "Descricao": "Pela ordem"
      }
    }
  },
  "CodigoPronunciamento": "507611",
  "codigo_pronunciamento": "507611"
}
```

O código `507611` identifica a ocorrência do pronunciamento. O código `4823`
identifica seu tipo de uso da palavra e não é alias do pronunciamento.

Direção aprovada: reclassificar `F22062 ↔ F22065` como duplicação técnica
restrita a `source=senado`, `dataset=congresso_discursos` e
`record_type=pronunciamento_texto`. O destino futuro será
`pronouncement_official_id`, preservando `house_scope=CN`, sessão plenária,
tipo de uso da palavra e linhagem dos campos oficiais aninhados. Não usar nome,
sessão ou segmento taquigráfico como substituto do ID.

### `alias-senado-pronouncement-id-plenario` — revisão de escopo aprovada

O coletor de `senado/plenario_discursos` usa o mesmo extrator e construtor,
mas consulta `siglaCasa=SF`.

Exemplo oficial e cópias do coletor:

```json
{
  "house_scope": "SF",
  "metadata": {
    "pronunciamento": {
      "id": "507283",
      "CodigoPronunciamento": "507283",
      "TipoUsoPalavra": {
        "Codigo": "4819",
        "Sigla": "DIS",
        "Descricao": "Discurso"
      }
    }
  },
  "CodigoPronunciamento": "507283",
  "codigo_pronunciamento": "507283"
}
```

O código `507283` identifica o pronunciamento; `4819` identifica a categoria
oficial `Discurso`.

Direção aprovada: reclassificar `F23487 ↔ F23490` como duplicação técnica
restrita a `source=senado`, `dataset=plenario_discursos` e
`record_type=pronunciamento_texto`. O destino futuro será
`pronouncement_official_id`, preservando `house_scope=SF`, sessão, tipo,
orador e linhagem dos campos oficiais aninhados.

Regra comum aprovada: não presumir que o namespace seja global entre `CN` e
`SF` somente porque o serviço e o construtor são compartilhados; o escopo da
Casa será preservado até prova específica. O ID será tratado como opaco, sem
inferir ordem ou quantidade. O raw permanecerá imutável, e versões históricas
serão auditadas antes de qualquer deduplicação normalizada.

### `alias-ccj-agenda-detail-subtrees` — rejeição como alias aprovada

**Finalidade das três categorias observadas.**

1. **Ocorrência da reunião na agenda.** O endpoint
   `/dadosabertos/comissao/agenda/{inicio}/{fim}.json` serve para descobrir as
   reuniões existentes numa janela. Cada resposta bem-sucedida é preservada
   pelo coletor como `record_type=agenda_periodo` e pode conter zero, uma ou
   muitas reuniões.
2. **Observação detalhada da reunião.** Depois de obter o código na agenda, o
   coletor consulta
   `/dadosabertos/comissao/reuniao/{codigo}.json` e preserva a resposta
   separadamente como `record_type=reuniao_detalhe`.
3. **Cópias contextuais nas notas.** O `record_type=notas_taquigraficas`
   incorpora a ocorrência descoberta como `metadata.agenda` e, quando a
   requisição de detalhe funciona, uma cópia de
   `DetalheReuniao.reuniao` como `metadata.detalhe`. Nessa cópia contextual,
   o coletor exclui `partes`; a resposta completa de detalhe continua
   preservada no raw de `reuniao_detalhe`.

Exemplo oficial consultado em 2026-07-25:

```json
{
  "agenda_meeting_observation": {
    "codigo": "14657",
    "titulo": "7ª Reunião Extraordinária Semipresencial",
    "dataInicio": "2026-05-13T09:00:00.000",
    "codigoSituacao": "6",
    "situacao": "Realizada",
    "tipo": {
      "codigo": "2",
      "sigla": "EXT",
      "descricao": "Extraordinária"
    },
    "colegiadoCriador": {
      "codigo": "34",
      "sigla": "CCJ"
    }
  }
}
```

```json
{
  "meeting_detail_observation": {
    "codigo": "14657",
    "titulo": "7ª Reunião Extraordinária Semipresencial",
    "dataInicio": "2026-05-13T09:00:00.000",
    "partes": {
      "codigo": "18930",
      "descricaoTipo": "Deliberativa",
      "itens": [
        {
          "codigo": "110415",
          "nome": "OFS 4/2026",
          "ordem": "1"
        }
      ]
    }
  }
}
```

Para esse exemplo, a ocorrência da agenda diária e a resposta do detalhe eram
exatamente iguais no momento da consulta: 37 campos de topo e a mesma pauta
com 11 itens. Essa igualdade é evidência de conteúdo repetido naquele
instante, mas não demonstra que os dois endpoints sejam semanticamente
intercambiáveis em todos os registros e épocas.

**Cardinalidades que precisam sobreviver.**

1. **Agenda para reuniões: `1:N`.** Uma resposta de período pode listar muitas
   reuniões. Exemplo: a agenda de 13 de maio pode conter a reunião CCJ
   `14657` e outras reuniões de outros colegiados.
2. **Reunião para ocorrências de agenda: `1:N`.** A mesma reunião pode reaparecer
   em respostas de janelas sobrepostas, subdivididas após erro ou em runs
   diferentes. Exemplo: `14657` pode aparecer tanto na agenda diária de
   `2026-05-13` quanto na agenda mensal de maio. O coletor evita processá-la
   duas vezes no mesmo fluxo, mas não apaga as respostas raw.
3. **Ocorrência de agenda para detalhe obtido: `1:0..1` por tentativa.**
   Exemplo com sucesso: `14657` liga-se ao detalhe de código `14657`. Exemplo
   sem sucesso: a agenda contém a reunião, mas o endpoint de detalhe responde
   `404` ou `500`; a ocorrência continua válida e o detalhe não deve ser
   inventado.
4. **Reunião para partes e itens: `1:N`.** Exemplo: a reunião `14657` possui
   uma parte deliberativa e, nela, 11 itens de pauta. Arrays como `partes`,
   `itens`, `textos`, `relatorias` e `dataReuniao` mantêm ordem, repetição e
   caminho completo.

**Riscos de aceitar o par como alias de subárvores.**

- apagar que agenda e detalhe vieram de endpoints, requests e instantes de
  coleta diferentes;
- fazer uma versão mais recente sobrescrever silenciosamente uma observação
  anterior;
- preencher automaticamente falhas ou ausências do detalhe com valores da
  agenda;
- confundir igualdade atual com uma garantia oficial permanente;
- achatar `partes[]`, `itens[]`, documentos, relatorias e pessoas, perdendo
  cardinalidade e papel;
- tratar a cópia contextual sem `partes` como se fosse igual à resposta
  detalhada completa.

**Decisão aprovada:** rejeitar `F13711 ↔ F16294` como alias de subárvores e
substituir a hipótese por um relacionamento determinístico através de
`committee_meeting_id`, no namespace de reuniões de comissão/colegiado do
Senado. A reunião é a mesma entidade quando o código oficial coincide, mas
cada observação conserva `record_type`, endpoint, request, momento de coleta,
caminho, ordem e conteúdo. Campos coincidentes podem alimentar atributos da
mesma entidade em artefato normalizado futuro somente com política explícita
de precedência ou versionamento; divergências não serão apagadas.

O raw não será modificado. A aprovação registra o contrato conceitual, mas não
autoriza implementação nem alteração das specs antes da aprovação final de
G02.

## Família polimórfica de `senado/ccj_notas`

### Bloco 1 — `partes` e `itens` — revisão aprovada

Os dois elementos representam níveis estruturais e não devem virar colunas
escalares contendo objetos serializados.

#### `meeting_part_source` — aprovado

**Finalidade:** representar cada parte oficial que compõe uma reunião de
comissão, vinculada a `committee_meeting_id`.

Categorias observadas e exemplos oficiais:

1. **Parte deliberativa.** Exemplo na reunião `14657`:
   `codigo=18930`, `codigoTipo=2`, `descricaoTipo=Deliberativa`; a parte possui
   11 itens.
2. **Outra parte deliberativa na mesma reunião.** A reunião `14685` contém um
   array de duas partes: `18966`, chamada `Indicação de Autoridade`, com
   `sequencial=1`; e `18967`, chamada `Deliberativa`, com `sequencial=2`.
3. **Audiência pública interativa.** Exemplo na reunião `14817`:
   `codigo=19114`, `codigoTipo=1`,
   `descricaoTipo=Audiência Pública Interativa`; em vez de `itens`, ela contém
   um objeto `evento` de código `10375`, com participantes.

Riscos:

- `partes` é objeto quando há uma única parte, como em `14657`, e array quando
  há mais de uma, como em `14685`;
- `codigoTipo` e `descricaoTipo` são código e rótulo oficiais distintos;
- `codigo` da parte, código do evento aninhado e código da reunião identificam
  entidades diferentes;
- usar somente o nome da parte como identidade fundiria partes homônimas;
- transformar objeto ou array em string destruiria hierarquia e
  cardinalidade.

Decisão aprovada: criar conceitualmente uma ocorrência-filha
`meeting_part_source` por parte, preservando
`meeting_part_official_id`, código e descrição oficiais do tipo, nome,
`sequencial`, índice original, tipo original do contêiner e proveniência
completa. A conversão futura de um objeto único em uma coleção de uma
ocorrência só poderá ser uma regra determinística e sem perda; o raw continuará
com seu tipo original.

#### `agenda_item_source` — aprovado

**Finalidade:** representar cada item oficial dentro de uma parte
deliberativa, ligado simultaneamente à reunião e à parte.

Categorias observadas e exemplos oficiais:

1. **Item de matéria.** Exemplo na parte `18966`:
   `codigo=110487`, `nome=OFS 4/2026`, `ordem=1`, `tipo=MATE` e
   `categoria=Matéria`.
2. **Item de outra parte da mesma reunião.** Na parte `18967`, o primeiro item
   é `codigo=110510`, `nome=PL 565/2022` e também `ordem=1`. Isso demonstra que
   a ordem reinicia por parte.
3. **Parte sem itens.** A parte de audiência pública `19114` não possui
   `itens`; ela contém `evento`. Ausente, nulo e coleção vazia continuarão
   estados distintos.

Riscos:

- `ordem` não identifica globalmente um item e nem sequer é única dentro da
  reunião quando há várias partes;
- `codigo` do item de pauta não é alias automático do ID da proposição, da
  matéria, do processo ou do documento aninhado;
- um item pode conter `doma`, `textosPauta`, relatorias e documentos com suas
  próprias cardinalidades;
- remover o vínculo com a parte perde o contexto em que a matéria foi
  pautada.

Decisão aprovada: criar conceitualmente uma ocorrência-filha
`agenda_item_source`, preservando `agenda_item_official_id`, tipo, categoria,
ordem informada, índice original e vínculo com
`meeting_part_official_id` e `committee_meeting_id`. Código, nome, tipo,
categoria e ordem ficam em atributos separados. Proposição, matéria,
documento e processo aninhados permanecem entidades distintas.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 2 — `doma` e `relatorias` — revisão aprovada

#### `legislative_matter_observation` para `doma` — aprovado

**Finalidade:** conservar o pacote estruturado que descreve a matéria ou
documento legislativo associado a um item de pauta. `doma` será tratado como
uma observação de origem que contém referências a entidades distintas, e não
como um único identificador canônico.

Categorias e exemplos oficiais:

1. **OFS — Ofício “S”.** No item `110487`, a identificação é `OFS 4/2026`,
   com `sigla=OFS`, `numero=00004`, `ano=2026`,
   `codigoMateria=173720`, `idProcesso=9035771`, `idDoma=10208842` e
   `idConteudoInformacional=7654845`.
2. **PL — Projeto de Lei.** No item `110510`, a identificação é
   `PL 565/2022`, com `codigoMateria=155624`, `idProcesso=8347274` e
   `idDoma=9233146`.
3. **REQ — Requerimento.** No item `110825`, a identificação é
   `REQ 18/2026 - CCJ`, com `codigoMateria=174243`,
   `idProcesso=9050592` e `idDoma=10226652`.

As descrições `Ofício "S"`, `Projeto de Lei` e `Requerimento` constam do
vocabulário oficial de tipos e siglas de documentos e processos do Senado.

Riscos:

- `codigoMateria`, `idProcesso`, `idDoma` e `idConteudoInformacional`
  identificam objetos com papéis diferentes e não são aliases;
- o `codigo` do item de pauta também não substitui nenhum desses IDs;
- `identificacao` é uma forma pública legível, não uma chave técnica;
- extrair sigla, número ou ano somente de `identificacao` seria desnecessário
  quando os campos estruturados existem;
- converter `numero=00004` para inteiro sem preservar o valor original
  apagaria a representação oficial;
- `doma.textos` contém documentos ou conteúdos relacionados, com
  cardinalidade própria, e não deve ser incorporado como atributo escalar da
  matéria.

Decisão aprovada: preservar `doma` como observação estruturada ligada ao item e
mapear separadamente, quando preenchidos, `matter_official_id` a partir de
`codigoMateria`, `legislative_process_id` a partir de `idProcesso`,
`doma_official_id` como identificador opaco da própria origem e
`informational_content_id` a partir de `idConteudoInformacional`. Sigla,
número, ano, identificação e o indicador fonte `proposicao` permanecem
atributos separados. O formato público sigla/número/ano continua disponível,
como já decidido, sem substituir os IDs.

#### `rapporteur_assignment_source` para `relatorias` — aprovado

**Finalidade:** representar cada designação de relatoria como uma relação
temporal entre processo, colegiado, pessoa e papel.

Categorias e exemplos oficiais:

1. **Relator.** No processo `9035771`, a relatoria `10219298` tem
   `idTipo=1`, `descricaoTipo=Relator`, `relator=true`, `adhoc=false` e
   `revisor=false`; o parlamentar é `5973`, Senador Cid Gomes, e o colegiado é
   a CCJ de código `34`.
2. **Relator ad hoc.** No processo `8620604`, a relatoria `10221216` tem
   `idTipo=3`, `descricaoTipo=Relator Ad hoc`, `adhoc=true`; o parlamentar é
   `4770`, Senador Izalci Lucas.
3. **Sem relatoria no item.** O item `110825`, `REQ 18/2026 - CCJ`, apresenta
   `relatorias=null`. Isso permanece “presente nulo”, não vira pessoa
   desconhecida nem designação inferida.

Riscos:

- ID da relatoria, ID do processo e ID da pessoa são entidades distintas;
- `descricaoTipo`, `idTipo` e os indicadores `relator`, `adhoc` e `revisor`
  não devem ser colapsados em um único texto;
- partido e UF dentro de `parlamentar` descrevem o contexto dessa observação,
  não necessariamente a filiação atual global;
- uma pessoa pode ter várias relatorias e um processo pode ter zero, uma ou
  várias designações ao longo do tempo;
- ausência, nulo, objeto único e eventual coleção precisam manter estados e
  tipos originais.

Decisão aprovada: criar conceitualmente uma ocorrência-filha
`rapporteur_assignment_source` por designação, preservando
`rapporteur_assignment_official_id`, `legislative_process_id`, colegiado,
código e descrição oficiais do tipo, todos os indicadores de papel, datas de
designação e encerramento, estado aberta/encerrada e vínculo com
`person_official_id`. Não resolver a pessoa por nome e não reduzir
“Relator ad hoc” a “Relator”.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 3 — `doma.textos` e `textosPauta` — revisão aprovada

#### `legislative_document_source` — aprovado

**Finalidade:** representar cada documento legislativo observado nas
coleções aninhadas, sem confundi-lo com a matéria, o processo, o item de pauta
ou o vínculo contextual em que apareceu.

No primeiro item da reunião `14657`, `doma.textos` contém 12 documentos. As
sete classes oficiais observadas nesse exemplo são:

1. **`OFICIO` — Ofício.** Exemplo: `idDoma=10208842`, documento principal do
   `OFS 4/2026`.
2. **`AVULSO_INICIAL` — Avulso inicial da matéria.** Exemplo:
   `idDoma=10209749`.
3. **`RELATORIO` — Relatório Legislativo.** Exemplo:
   `idDoma=10220942`.
4. **`REQUERIMENTO` — Requerimento.** Exemplo:
   `idDoma=10226652`.
5. **`LISTAGEM_RELATORIO` — Listagem ou relatório descritivo.** Exemplos:
   `10226756`, lista de presença, e `10226781`, lista de votação.
6. **`PARECER` — Parecer.** Exemplo: `idDoma=10226807`.
7. **`MENSAGEM` — Mensagem.** Exemplo: `idDoma=10227529`.

Riscos:

- `idDoma` do documento não é alias automático de `codigoMateria`,
  `idProcesso`, `idConteudoInformacional` ou código do item;
- sigla e descrição da classe oficial são componentes distintos;
- `identificacao` e `descricao` não substituem o conteúdo integral;
- `codigoColegiado` identifica o contexto institucional do documento, não seu
  autor automaticamente;
- `urlDownload` tem papel de URL de download e não substitui URL de API,
  requisição ou resposta;
- duas ocorrências com o mesmo `idDoma` não autorizam descartar uma delas sem
  preservar seus caminhos e papéis.

Decisão aprovada: representar conceitualmente cada documento como
`legislative_document_source`, preservando `document_official_id` qualificado
pelo namespace do Senado, sigla e descrição oficiais da classe, identificação,
descrição, data de atualização, colegiado, URL de download, índice e
proveniência. Qualquer união de ocorrências pelo mesmo `idDoma` exigirá
igualdade exata do ID no namespace aprovado; divergências de atributos serão
mantidas como observações versionadas.

#### `document_context_link_source` — aprovado

**Finalidade:** preservar por que e onde o mesmo documento apareceu, sem
duplicar sua identidade documental.

Papéis estruturais e exemplos:

1. **Relacionado à matéria — caminho `doma.textos`.** O item
   `OFS 4/2026` apresenta 12 documentos relacionados, incluindo ofício,
   avulso, relatório, requerimento, listagens, parecer e mensagem.
2. **Listado para a pauta — caminho `textosPauta`.** O mesmo item apresenta
   somente dois documentos: o avulso `10209749`, com `ordemNaPauta=1`, e o
   relatório `10220942`, com `ordemNaPauta=2`.

Os papéis `matter_related` e `agenda_listed` serão rótulos técnicos derivados
exclusivamente do caminho estrutural, não categorias oficiais inventadas para
a API.

Riscos:

- tratar as duas coleções como aliases apagaria que apenas parte dos
  documentos estava listada na pauta;
- `ordemNaPauta` vale para a ocorrência na pauta, não para o documento em
  todos os contextos;
- o mesmo documento pode aparecer em vários itens, reuniões, colegiados,
  runs ou versões;
- comparar somente URL, descrição ou posição pode criar vínculos falsos;
- remover ocorrências repetidas apagaria cardinalidade e proveniência.

Decisão aprovada: criar conceitualmente um vínculo
`document_context_link_source` para cada ocorrência, com
`document_official_id`, papel estrutural, matéria, item, parte, reunião,
colegiado, `ordemNaPauta` quando existir, índice original e proveniência. No
exemplo, `10209749` e `10220942` apontam para as mesmas entidades documentais
em duas relações diferentes; as ocorrências continuam preservadas.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 4 — `evento`, `convidados` e `participantes` — revisão aprovada

#### `committee_embedded_event_source` — aprovado

**Finalidade:** representar o evento temático aninhado em uma parte de
reunião, sem confundi-lo com a própria reunião ou com a parte.

Exemplo oficial:

```json
{
  "committee_meeting_id": "14817",
  "meeting_part_official_id": "19114",
  "meeting_part_type": "Audiência Pública Interativa",
  "embedded_event_id": "10375",
  "finalidade": "Instruir a Proposta de Emenda à Constituição n° 1, de 2026"
}
```

Categorias estruturais observadas no evento:

1. **Convidados.** Quatro convites ou posições convidadas são registrados em
   `convidados`.
2. **Participantes.** Três ocorrências de participação são registradas em
   `participantes`.
3. **Matérias relacionadas.** Duas relações aparecem em
   `domasRelacionados`: a PEC 1/2026 como matéria instruída e o
   REQ 11/2026 - CCJ como solicitação da audiência.
4. **Apresentações.** Uma participante possui documento de apresentação em
   `apresentacoes`.

Riscos:

- `14817`, `19114` e `10375` são, respectivamente, IDs da reunião, da parte e
  do evento; não são aliases;
- `finalidade`, matéria relacionada e requerimento relacionado têm papéis
  diferentes;
- o evento pode estar ausente em partes deliberativas e presente em partes de
  audiência;
- `isPublicado`, `isRealizado`, observações e resultado devem permanecer como
  campos informados pela fonte, sem inferência por título ou texto;
- achatar o evento na reunião apagaria a parte que lhe dá contexto.

Decisão aprovada: criar conceitualmente `committee_embedded_event_source`,
preservando ID oficial do evento no namespace de eventos de comissão do
Senado, vínculo com parte e reunião, finalidade, indicadores fonte,
observações, resultado, caminho, tipo original e proveniência. Matérias,
pessoas e documentos relacionados permanecem relações ou entidades-filhas.

#### `event_involvement_source` — aprovado

**Finalidade:** distinguir convite de participação efetiva ou registrada,
preservando o vínculo determinístico entre os dois quando a API o fornece.

Papéis e exemplos:

1. **Convidado sem participação correspondente.** O convite `43112` registra
   `Representante do Ministério da Fazenda`; não há ocorrência correspondente
   em `participantes`.
2. **Convidado com participação vinculada.** O participante `33679`, Fellipe
   Rodrigues Andrade, traz `codigoConvidado=43113`, ligando-se explicitamente
   ao convite `43113`.
3. **Participante com apresentação.** O participante `33681`, Marcelo Costa
   Martins, liga-se ao convite `43115` e possui uma apresentação PDF com
   `idEcmSenado=36c02a98-9276-4f0c-93db-59867820ded4`.

Riscos:

- código do convite, código da participação e eventual ID oficial da pessoa
  são identificadores distintos;
- convidado pode ser uma posição ainda não preenchida, como “Representante
  do Ministério da Fazenda”, e não uma pessoa resolvível;
- nome, tratamento, cargo e organização representada não autorizam resolução
  de identidade por similaridade;
- `codigoSituacao`, `isDepoentePresente` e `isPorVideoConferencia` devem ser
  preservados literalmente; a presença não será inferida pela coleção em que
  o registro apareceu;
- a apresentação é um documento vinculado à participação, não atributo da
  pessoa;
- ordem do convite e ordem da participação são contextuais ao evento.

Decisão aprovada: criar uma ocorrência `event_involvement_source` por convite ou
participação, com papel estrutural explícito `invited` ou `participant`, ID
próprio, ordem, rótulos pessoais informados, cargo, representação, indicadores
fonte e proveniência. Usar `codigoConvidado` somente como vínculo exato entre
participação e convite. Sem ID oficial de pessoa, conservar a descrição da
pessoa ou posição sem inventar uma identidade global.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 5 — `domasRelacionados` e autoria — revisão aprovada

#### `event_related_matter_link_source` — aprovado

**Finalidade:** representar por que uma matéria ou documento legislativo está
relacionado ao evento aninhado, sem duplicar a identidade da matéria.

Categorias observadas no evento `10375`:

1. **`A` — Instrução de matéria.** Exemplo:
   `PEC 1/2026`, `codigoMateria=172391`, `idProcesso=8986903`,
   `ordem=1`.
2. **`C` — Solicitação de realização de Audiência Pública Interativa.**
   Exemplo: `REQ 11/2026 - CCJ`, `codigoMateria=173815`,
   `idProcesso=9038096`, `ordem=2`.

Riscos:

- código e descrição da finalidade são componentes distintos da categoria
  informada pela fonte;
- a PEC instruída e o requerimento que solicitou a audiência têm papéis
  diferentes;
- a cópia aninhada de `doma` não cria uma nova matéria nem autoriza fundir
  seus diferentes IDs;
- `ordem` é contextual ao evento e não ordena globalmente matérias ou
  processos;
- a finalidade não deve ser inferida do texto livre do evento.

Decisão aprovada: criar conceitualmente
`event_related_matter_link_source` por relação, com evento, matéria, processo,
`doma`, código e descrição da finalidade, ordem, índice e proveniência.
Reutilizar os mesmos IDs separados já aprovados para `doma`, sem duplicar nem
substituir a entidade legislativa.

#### `authorship_assignment_source` — aprovado

**Finalidade:** representar cada relação de autoria entre uma matéria ou
documento e uma pessoa, órgão ou instituição. O resumo
`autorItemPauta` e a lista detalhada `doma.autorias` conservarão papéis
estruturais diferentes.

Categorias de autoria observadas e exemplos:

1. **`TRIBUNAL_SUPERIOR` — Tribunal Superior.** Exemplo: Superior Tribunal de
   Justiça como autor do `OFS 4/2026`.
2. **`CAMARA` — Câmara dos Deputados.** Exemplo: Câmara dos Deputados como
   autora do `PL 4560/2025`.
3. **`SENADOR` — Senador.** Exemplo: Alessandro Vieira,
   `person_official_id=5982`, como autor do `PL 2511/2019`.
4. **`COMISSAO_SENADO` — Comissão do Senado Federal.** Exemplo: CCJ,
   `arena_official_id=34`, como autora do `REQ 15/2026 - CCJ`.

Exemplo de cardinalidade: em `PEC 65/2023`, `autorItemPauta` apresenta
Vanderlan Cardoso e `possuiOutrosAutores=true`, enquanto `doma.autorias`
preserva cada coautor parlamentar com sua própria `ordem`.

Riscos:

- nem todo autor é pessoa; tribunal, Casa legislativa e comissão são entidades
  institucionais distintas;
- `autorItemPauta` é resumo e não substitui a lista detalhada de autorias;
- o nome agregado de vários autores não deve ser dividido por vírgulas nem
  usado para resolver identidades;
- ordem de autoria, tratamento, tipo, partido e UF pertencem à ocorrência;
- `isParlamentar`, `isColegiado` e `possuiOutrosAutores` são indicadores
  fonte, não regras suficientes para preencher IDs ausentes;
- código da pessoa, código do colegiado e identificação textual da
  instituição pertencem a namespaces diferentes.

Decisão aprovada: criar uma ocorrência `authorship_assignment_source` por autoria
detalhada, com papel estrutural `item_author_summary` ou
`matter_authorship_detail`, tipo oficial de autor, ordem, indicadores fonte,
matéria ou documento e referência à entidade autora adequada. Resolver por ID
oficial somente quando presente: parlamentar pelo ID do Senado, comissão pelo
código do colegiado; instituições sem ID permanecem descritas pela fonte, sem
identidade global inventada. Resumo e detalhe não são aliases.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 6 — estados da reunião e resultados dos itens — revisão aprovada

#### `meeting_state_observation_source` — aprovado

**Finalidade:** preservar tanto o estado corrente informado para a reunião
quanto cada ocorrência de mudança de estado em `dataReuniao`.

Na reunião `14657`, as categorias de situação observadas são:

1. **Código `1` — Agendada.** Ocorrência `68174`, em
   `2026-05-13T09:00:00.000`.
2. **Código `3` — Aberta.** Ocorrência `68241`, em
   `2026-05-13T09:05:00.000`.
3. **Código `4` — Suspensa.** Ocorrência `68243`, em
   `2026-05-13T09:51:00.000`.
4. **Código `5` — Reaberta.** Ocorrência `68244`, em
   `2026-05-13T09:54:00.000`.
5. **Código `6` — Realizada.** Ocorrência `68252`, em
   `2026-05-13T10:31:00.000`.

Na raiz da mesma resposta, o estado corrente aparece como
`codigoSituacao=6`, `situacao=Realizada`, `status=Realizada` e
`realizada=true`.

Riscos:

- o `codigo` dentro de `dataReuniao` identifica a ocorrência de mudança, não
  a reunião;
- estado corrente e histórico podem coincidir, mas têm papéis temporais
  diferentes e não são aliases automáticos;
- código, descrição e indicadores booleanos permanecem campos distintos;
- a ordem do array não deve ser presumida como cronológica; o índice original
  e o datetime serão preservados;
- suspensão e reabertura seriam apagadas se apenas o estado final fosse
  mantido.

Decisão aprovada: criar uma ocorrência `meeting_state_observation_source` por
estado, com papel `current_snapshot` ou `state_transition`, ID da ocorrência
quando existir, código e descrição da situação, datetime, indicadores fonte,
índice e proveniência. O histórico continua ligado exclusivamente a
`committee_meeting_id`.

#### `agenda_item_outcome_source` — aprovado

**Finalidade:** representar o resultado de um item no contexto da parte e da
reunião em que foi pautado.

Categorias de resultado observadas nas reuniões `14657` e `14685`:

1. **Código `11` — Aprovado o relatório.** Exemplo:
   `PL 2511/2019`, item `110029`.
2. **Código `13` — Adiado.** Exemplo: `PL 4534/2021`, item `110034`.
3. **Código `14` — Vista concedida.** Exemplo:
   `OFS 4/2026`, item `110415`, na reunião `14657`.
4. **Código `82` — Aprovada a apresentação para o Plenário do Senado.**
   Exemplo: `REQ 15/2026 - CCJ`, item `110469`.
5. **Código `58` — Sabatina realizada com indicação aprovada.** Exemplo:
   `OFS 4/2026`, item `110487`, na reunião posterior `14685`.

Riscos:

- o resultado pertence à ocorrência do item na reunião, não globalmente à
  matéria: `OFS 4/2026` teve vista na reunião `14657` e aprovação na `14685`;
- `codigoTipoResultado`, sua descrição, `siglaResultado`,
  `resultado.descricao`, `resultado.texto` e `descricaoResultado` têm papéis
  próprios e não são aliases automáticos;
- `apreciado=false` ainda pode coexistir com `Adiado` ou `Vista concedida`;
- `dataResultado` pode estar nula mesmo quando existe resultado explícito;
- não se deve inferir resultado plenário a partir de decisão da CCJ;
- texto explicativo do resultado não deve ser analisado para criar categorias
  adicionais.

Decisão aprovada: criar uma ocorrência `agenda_item_outcome_source` por
item-parte-reunião, preservando código e descrição da categoria, rótulos e
texto explicativo em campos separados, datetime quando presente, indicadores
`apreciado`, `emDeliberacao` e suspensão, além de índice e proveniência.
Resultados de reuniões diferentes nunca serão colapsados apenas porque a
matéria é a mesma.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 7 — `quartos` e marcações taquigráficas — revisão aprovada

#### `taquigraphic_quarter_source` — aprovado

**Finalidade:** representar cada bloco temporal entregue pela API
taquigráfica, mantendo texto, áudio e metadados no contexto da reunião.

Exemplo da reunião `14657`:

```json
{
  "codigo": "3765408",
  "dataInicio": "2026-05-13T09:04:00-03:00",
  "dataFim": "2026-05-13T09:08:00-03:00",
  "sequencia": "2",
  "etapa": "3",
  "codStatusGrupoItem": "3",
  "linkAudio": "https://legis.senado.leg.br/escriba-servicosweb/reuniao/audio?...",
  "texto_length": 2468
}
```

A resposta possui 22 quartos, com sequências de `2` a `23`.

Categorias de conteúdo associadas ao quarto:

1. **Texto do quarto.** Exemplo: 2.468 caracteres no quarto `3765408`.
2. **Áudio do quarto.** Exemplo: `linkAudio` específico do mesmo intervalo.
3. **Marcações estruturadas.** Exemplo: dez ocorrências em `itens` no primeiro
   quarto, descrevendo palavras, intercorrências e matéria.

Riscos:

- código do quarto, código da reunião e código das marcações são IDs
  distintos;
- a sequência começa em `2`; renumerá-la apagaria a ordem informada;
- `etapa` e `codStatusGrupoItem` devem permanecer códigos fonte opacos
  enquanto não houver vocabulário aprovado;
- o texto do quarto não deve ser confundido com o agregado
  `TextoIntegral`/`texto` criado pelo coletor;
- o texto pode conter várias falas e marcações sem offsets oficiais que
  permitam atribuir trechos exatos a cada item;
- URL de áudio tem papel próprio e não é URL documental nem URL de API.

Decisão aprovada: criar uma ocorrência `taquigraphic_quarter_source` por quarto,
com ID oficial no namespace taquigráfico, reunião, sequência original, índice,
datas, etapa, status, texto literal, áudio e proveniência. O agregado textual
da reunião mantém linhagem para a sequência de quartos, mas nenhum quarto será
reconstruído a partir do agregado.

#### `taquigraphic_marker_source` — aprovado

**Finalidade:** representar as ocorrências estruturadas de `quartos.itens`
sem confundi-las com itens de pauta nem presumir que cada uma corresponda a um
trecho textual delimitado.

Categorias observadas na reunião `14657`:

1. **`Palavra`.** Exemplo: marcação `15231487`, sequência `1`,
   `codigoOrador=1136922`, `nomeOrador=Otto Alencar` e
   `papelPalavra=Presidente`.
2. **`Intercorrência`.** Exemplo: marcação `15231488`, sequência `2`, com
   descrição `(Pausa.)` e sem orador.
3. **`Matéria`.** Exemplo: marcação `15231490`, sequência `4`, sem orador e
   sem descrição.
4. **`Anotação`.** Exemplo: descrição que registra suspensão e reabertura; o
   valor observado é uma string contendo marcação serializada e permanecerá
   literal, sem interpretação nesta etapa.

Papéis de palavra observados:

1. **`Presidente`.** Exemplo: Otto Alencar na marcação `15231487`.
2. **`Orador`.** Exemplo: Cid Gomes na marcação `15231492`.

Riscos:

- `quartos.itens` pode ser array ou objeto único;
- código da marcação taquigráfica não é o código do item de pauta;
- `codigoOrador` pertence ao contexto do sistema taquigráfico e não é alias
  automático do ID oficial do senador;
- nome do orador não autoriza resolução de identidade;
- a sequência reinicia dentro de cada quarto;
- interpretar a string de `Anotação`, procurar marcadores no texto ou atribuir
  spans a falas violaria o adiamento aprovado da estrutura textual.

Decisão aprovada: criar uma ocorrência `taquigraphic_marker_source` por marcação,
preservando ID, quarto, reunião, sequência, tipo oficial informado, descrição
literal, indicadores editoriais, referência de orador e proveniência. Para
`Palavra`, conservar código, nome e papel do orador como referência fonte;
qualquer vínculo com pessoa oficial exigirá ID compatível ou regra humana
posterior. A união futura de objeto único e array será lossless e guardará o
tipo original.

As duas decisões não autorizam interpretação textual, normalização, Batch ou
alteração das specs antes da aprovação final de G02.

### Bloco 8 — colegiados e presidência da reunião — revisão aprovada

#### `meeting_arena_assignment_source` — aprovado

**Finalidade:** representar o vínculo entre uma reunião e cada colegiado,
preservando o papel estrutural exercido pelo órgão.

Papéis observados:

1. **Colegiado criador — `colegiadoCriador`.** Na reunião `14657`:
   `codigo=34`, `sigla=CCJ`, nome `Comissão de Constituição, Justiça e
   Cidadania`, `siglaCasa=SF`, `codigoTipo=21` e
   `descricaoTipo=Comissão Permanente`.
2. **Colegiado associado — `colegiados`.** Na mesma reunião, a CCJ aparece
   também com `numeroReuniao=7`, `codigoTipoColegiado=21`,
   `nomeTipoColegiado=Comissão Permanente`, `isSubcomissao=false` e
   indicadores de publicidade.

Riscos:

- os valores coincidem nos exemplos recentes, mas “criador” e “associado” são
  papéis distintos e não aliases de subárvores;
- `colegiados` pode representar multiplicidade e seu tipo original deve ser
  preservado;
- código e rótulo do tipo institucional permanecem separados;
- `numeroReuniao` é contextual ao colegiado e não é
  `committee_meeting_id`;
- `numReuniaoConjunta` não será interpretado como indicador de reunião
  conjunta apenas pelo nome do campo;
- `CCJ` do Senado continua distinta da `CCJC` da Câmara e de sessões
  plenárias.

Decisão aprovada: criar uma ocorrência `meeting_arena_assignment_source` por
vínculo, com papel `creator` ou `associated`, ID, sigla e nome do colegiado,
Casa, código e descrição do tipo, número contextual da reunião, indicadores
fonte, índice e proveniência. Se o mesmo colegiado ocupar os dois papéis,
preservar as duas relações.

#### `meeting_presidency_source` — aprovado

**Finalidade:** representar quem presidiu a reunião segundo o metadado
estruturado da reunião.

Categorias de presença observadas:

1. **Presidência identificada.** Na reunião `14657`, o presidente é Otto
   Alencar, `person_official_id=5523`, com observação datada de
   `2026-05-13`.
2. **Presidência identificada por outra pessoa.** Na reunião `14817`, o
   presidente é Laércio Oliveira, `person_official_id=4811`, mostrando que a
   relação varia por reunião.
3. **Presidência presente nula.** Na reunião `14634`,
   `presidente=null`; isso não autoriza inferir o presidente pelas notas
   taquigráficas.

Riscos:

- presidente da reunião e `papelPalavra=Presidente` em uma marcação
  taquigráfica são relações diferentes;
- pessoa, partido, UF e lideranças pertencem ao contexto e à data da
  observação;
- `liderancas` pode ser objeto ou coleção e não define a presidência;
- nome ou fala não deve preencher `presidente` quando o campo estiver nulo;
- presidência de comissão não é presidência de sessão plenária.

Decisão aprovada: criar uma relação `meeting_presidency_source` entre reunião e
pessoa oficial quando o ID estiver preenchido, preservando nomes, cargo, Casa,
partido, UF, data e proveniência como observação contextual. O nulo permanece
nulo. Marcações de fala com papel Presidente continuam separadas e podem ser
comparadas apenas em auditoria posterior.

As duas decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

### Bloco 9 — vídeos e apresentações — revisão aprovada

#### `meeting_video_source` — aprovado

**Finalidade:** representar cada gravação ou transmissão audiovisual associada
à reunião.

Exemplos observados:

1. **Reunião `14657`.** Vídeo `7875`, ordem `1`, URL do YouTube e título
   `Ao vivo: CCJ analisa prazo para denúncia contra violência doméstica –
   13/5/26`.
2. **Reunião `14685`.** Vídeo `7899`, ordem `1`, URL do YouTube sobre
   autonomia financeira do Banco Central.
3. **Reunião `14817`.** Vídeo `8013`, ordem `1`, URL do YouTube sobre
   contribuição previdenciária.

Riscos:

- código do vídeo não é `committee_meeting_id`;
- URL externa de reprodução não é URL de API, documento ou download;
- título do vídeo não substitui título ou finalidade oficiais da reunião;
- `dataHoraReuniao` dentro do vídeo é metadado contextual e não deve
  sobrescrever automaticamente o horário da reunião;
- `videos` pode ter cardinalidade ou tipo de contêiner variável;
- conteúdo audiovisual não será transcrito nem interpretado em G02.

Decisão aprovada: criar uma ocorrência `meeting_video_source` por vídeo, com ID no
namespace audiovisual do Senado, reunião, ordem, URL de reprodução, título,
datetime informado, índice, tipo original e proveniência.

#### `participant_presentation_document_source` — aprovado

**Finalidade:** representar o documento de apresentação associado a uma
participação no evento.

Exemplo observado:

```json
{
  "event_participant_id": "33681",
  "participant_name": "Marcelo Costa Martins",
  "idEcmSenado": "36c02a98-9276-4f0c-93db-59867820ded4",
  "descricao": "Apresentação",
  "nome": "Apresentação_Marcelo Costa Martins_Adial Brasil_PEC 01.2026.pdf",
  "mimeType": "application/pdf",
  "linkDownload": "https://legis.senado.leg.br/sdleg-getter/documento/download/..."
}
```

Riscos:

- `idEcmSenado` pertence a namespace documental diferente de `idDoma`;
- a apresentação é documento ligado à ocorrência de participação, não
  atributo permanente da pessoa;
- nome do arquivo não deve ser analisado para inferir autor, instituição ou
  matéria;
- `mimeType`, descrição, nome do arquivo e URL de download são campos
  distintos;
- `apresentacoes` pode ser objeto único ou coleção e deve manter o tipo
  original;
- o PDF não será lido para criar metadados em G02.

Decisão aprovada: representar a apresentação como documento no namespace ECM do
Senado e criar um vínculo
`participant_presentation_document_source` com evento, participação, ordem ou
índice, ID documental, descrição, nome, MIME, URL de download e proveniência.
Não fundir `idEcmSenado` com `idDoma`; qualquer equivalência futura exigirá
evidência oficial e auditoria explícita.

As duas decisões não autorizam download, leitura de conteúdo, normalização,
Batch ou alteração das specs antes da aprovação final de G02.

### Bloco 10 — tipo, modalidade e período legislativo — revisão aprovada

#### `committee_meeting_type_source` — aprovado

**Finalidade:** preservar a categoria oficial do tipo de reunião de comissão.

Categoria observada nos exemplos recentes:

1. **Código `2`, sigla `EXT`, descrição `Extraordinária`.** Exemplo:
   reunião `14657`.

Riscos:

- código, sigla e descrição são componentes distintos;
- tipo da reunião não é tipo da parte, do evento, da sessão plenária ou da
  fala;
- “Extraordinária” não deve ser inferida do título;
- o conjunto observado nos exemplos não autoriza declarar um vocabulário
  fechado para toda a história.

Decisão aprovada: preservar código, sigla e descrição como
`committee_meeting_type_source`, com caminho e proveniência. Mapas de tipos só
serão fechados após catalogar os valores realmente observados e confrontá-los
com a documentação oficial.

#### `meeting_modality_source` — aprovado

**Finalidade:** representar a modalidade de presença e os controles
operacionais informados para a reunião.

Categorias de presença observadas:

1. **`Presencial`.** Exemplo: reunião `14685`, com
   `permitePresencaApp=false` e
   `permiteVotacaoSemPresencaFisica=false`.
2. **`Semipresencial`.** Exemplo: reunião `14657`, com
   `permitePresencaApp=true` e
   `permiteVotacaoSemPresencaFisica=true`.

Outros indicadores observados nos exemplos:

1. **Sigilo da reunião — `secreta`.** Exemplo: `false` em `14657`.
2. **Possibilidade de votação secreta — `possuiVotacaoSecreta`.** Exemplo:
   `false` em `14657`; não é o mesmo que a reunião ser secreta.
3. **Confirmação — `confirmada`.** Exemplo: `false` em `14657`, ainda que a
   situação corrente seja `Realizada`.
4. **Continuação cancelada — `continuacaoCancelada`.** Exemplo: `false`.
5. **Agendada após suspensão —
   `foiAgendadaAposTerSidoSuspensa`.** Exemplo: `false`.
6. **Local.** Exemplo: `Anexo II, Ala Senador Alexandre Costa, Plenário nº 3`.
7. **Versão da observação.** Exemplo:
   `2026-06-25T03:18:06.268` em `14657`.

Riscos:

- não derivar os booleanos a partir de `tipoPresenca`, nem o inverso;
- “Plenário nº 3” no endereço físico não transforma a reunião da CCJ em
  sessão plenária;
- `secreta` e `possuiVotacaoSecreta` expressam condições diferentes;
- `confirmada=false` não contradiz automaticamente `Realizada`;
- `versao` é timestamp de versão da observação, não data da reunião.

Decisão aprovada: preservar modalidade, local e cada indicador operacional em
atributo próprio, exatamente como informado, com tipo original e proveniência.
Não harmonizar booleanos nem completar valores por associação observada nos
exemplos.

#### `legislative_session_context_source` — aprovado

**Finalidade:** ligar a reunião ao período legislativo institucional em que
ocorreu.

Exemplo:

```json
{
  "codigo": "874",
  "numeroLegislatura": "57",
  "numero": "4",
  "descricao": "57a. Legislatura (2026) - 4a. Sessão Legislativa Ordinária",
  "inicio": "2026-02-02",
  "fim": "2026-12-22"
}
```

Categoria observada:

1. **Sessão Legislativa Ordinária.** Exemplo: a 4ª da 57ª Legislatura,
   código `874`, associada às reuniões de 2026 consultadas.

Riscos:

- sessão legislativa é período do calendário parlamentar, não ocorrência de
  sessão plenária;
- `codigo=874`, `numeroLegislatura=57` e `numero=4` têm papéis distintos;
- o número `4` só é significativo dentro da legislatura;
- início e fim do período não substituem data da reunião;
- a descrição não deve ser analisada para reconstruir campos já
  estruturados.

Decisão aprovada: criar uma relação
`legislative_session_context_source` entre reunião e período legislativo,
preservando ID oficial, legislatura, número, descrição, datas e proveniência.
Manter `legislative_session_id` separado de qualquer
`plenary_session_id`.

As três decisões não autorizam normalização, Batch ou alteração das specs
antes da aprovação final de G02.

## Síntese consolidada para aprovação final

Estado: **aprovada pelo pesquisador em 2026-07-25**.

Esta síntese encerra a revisão conceitual do schema global. Ela consolida
decisões humanas sobre nomes, significados, proveniência, entidades,
cardinalidades, categorias oficiais, aliases e a família polimórfica de
`senado/ccj_notas`. Ela não afirma que as tarefas operacionais de G02 já foram
executadas.

### Escopo efetivamente revisado

1. **Proposta global:** as 40 colunas originais foram avaliadas
   individualmente.
2. **Lacunas temáticas:** foram acrescentadas e aprovadas duas famílias
   conceituais:
   - `speech_indexing_source_raw`, por exemplo `Indexacao` do Senado e
     `keywords` da Câmara;
   - `proposition_subject_source`, por exemplo o tema oficial da Câmara
     `codTema=43`, `Direito Penal e Processual Penal`.
3. **Aliases:** oito hipóteses foram examinadas:
   - sete pares foram reclassificados como duplicações técnicas criadas pelos
     coletores, sempre restritas a `source + dataset + record_type`;
   - a equivalência entre subárvores de agenda e detalhe da reunião foi
     rejeitada: são observações distintas ligadas por
     `committee_meeting_id`.
4. **`senado/ccj_notas`:** dez blocos polimórficos foram revisados e
   aprovados, cobrindo partes, itens, matérias, processos, documentos,
   relatorias, autorias, eventos, participantes, estados, resultados,
   taquigrafia, colegiados, presidência, vídeos, apresentações, tipo,
   modalidade e sessão legislativa.
5. **Proveniência técnica:** foram aprovadas a coordenada do registro, a
   coordenada concreta do valor e a política que separa indexação temática,
   índice temporário de aliases e índice físico de consulta.

Nos registros do diário, uma decisão histórica escrita como “revisar” não
significa pendência: significa que a coluna foi aprovada com a reformulação
recomendada, em vez de ser aceita literalmente como apareceu na proposta.

### Entidades e cardinalidades consolidadas

As cardinalidades abaixo são o contrato conceitual mínimo. `0..N` preserva
ausência e multiplicidade; não autoriza inventar elementos nem colapsar
repetições.

| Origem | Relação aprovada | Exemplo |
|---|---|---|
| registro raw | `1:N` ocorrências de valor | uma linha JSONL contém vários campos e elementos aninhados |
| reunião de comissão | `1:N` observações da fonte | agenda e detalhe da reunião `14657` |
| reunião de comissão | `0:N` partes | reunião `14685` com partes `18966` e `18967` |
| parte | `0:N` itens de pauta | parte `18930` da reunião `14657`, com 11 itens |
| parte | `0:N` eventos aninhados | parte `19114` da audiência da reunião `14817`, com evento `10375` |
| item de pauta | `0:N` observações de matéria, resultados, documentos e autorias | a mesma `OFS 4/2026` teve vista na reunião `14657` e aprovação na `14685` |
| matéria/processo | `0:N` relatorias e autorias | designações preservam pessoa ou instituição, papel, colegiado e tempo |
| documento | `0:N` vínculos contextuais | o mesmo documento pode aparecer em `doma.textos` e `textosPauta` sem que as aparições sejam aliases |
| evento aninhado | `0:N` matérias relacionadas e envolvimentos | convidados e participantes permanecem ocorrências distintas |
| participante | `0:N` apresentações | documento ECM ligado à participação, não confundido com vídeo da reunião |
| reunião | `0:N` estados, vídeos, quartos taquigráficos e vínculos de arena | estados oficiais `1`, `3`, `4`, `5` e `6` formam observações, não um booleano |
| reunião | `0..1` presidência em cada observação da fonte | reunião `14657`: Otto Alencar, ID `5523`; reunião `14634`: valor nulo |
| quarto taquigráfico | `0:N` marcações | tipos `Palavra`, `Intercorrência`, `Matéria` e `Anotação` |
| reunião | `0..1` contexto de sessão legislativa por observação | período legislativo não é sessão plenária |
| fala/pronunciamento | `0:N` metadados temáticos literais | `Indexacao` do Senado ou `keywords` da Câmara |

Os seguintes objetos permanecem entidades distintas, mesmo quando aparecem
aninhados ou compartilham números e textos:

1. **Casas e arenas:** Senado, Câmara, Congresso, CCJ, CCJC e plenários.
2. **Ocorrências institucionais:** reunião de comissão, evento da Câmara,
   evento aninhado de audiência e sessão plenária.
3. **Objetos legislativos:** proposição, matéria, processo, item de pauta,
   resultado do item, parecer e documento.
4. **Atores e papéis:** pessoa, autor, relator, orador, presidente, convidado,
   participante, partido e unidade federativa.
5. **Objetos textuais:** pronunciamento, discurso, notas agregadas, quarto
   taquigráfico, marcação, ementa, resumo e texto integral.
6. **Metadados técnicos:** requisição, resposta, tentativa, status de coleta,
   coordenada raw e índice de execução.

### Invariantes aprovadas

1. **Raw imutável.** Nenhum campo, alias, forma `object|array`, valor nulo,
   texto duplicado ou posição original será alterado no raw.
2. **Proveniência por ocorrência.** Toda ocorrência normalizada futura deverá
   carregar coordenada do registro e JSON Pointer concreto; o caminho
   catalogado com `[]` sozinho não basta.
3. **IDs com namespace.** IDs oficiais são opacos e qualificados por fonte,
   conjunto e tipo de registro. Igualdade aparente entre Casas ou entidades
   não prova identidade.
4. **Categorias oficiais literais.** Código, sigla, descrição e flags da API
   ficam separados. Exemplos: `codTipoEvento=112` é categoria de evento,
   enquanto `id=81996` identifica a ocorrência; `PL`, `PEC` e `OFS` continuam
   siglas oficiais, não categorias inventadas.
5. **Proposição no uso público.** Número e ano continuam componentes
   analíticos de primeira classe, preservando o formato conhecido
   `tipo número/ano`, sem substituir o ID oficial.
6. **Sem resolução por texto ou nome.** Não unir pessoas por nome, não
   associar arrays paralelos por posição, não inferir gênero, não interpretar
   conteúdo e não promover ementa ou resumo a texto integral.
7. **Sexo registrado pela fonte.** O dado disponível será preservado
   literalmente como rótulo reportado, com a limitação explícita de que não
   representa necessariamente identidade de gênero, inclusive para
   parlamentares trans.
8. **Aliases com escopo estrito.** Uma duplicação técnica só vale no coletor e
   `record_type` demonstrados; nunca se transforma em equivalência global de
   conceitos.
9. **Comissão não é plenário.** CCJ do Senado, CCJC da Câmara e sessões
   plenárias são domínios diferentes. Tipo de reunião, modalidade e sessão
   legislativa também não são sessão plenária.
10. **Ausência é dado.** Ausente, `null`, vazio e preenchido permanecem
    distinguíveis; variantes `object|array` serão representadas sem perda.
11. **Indexações separadas.** `Indexacao`, `keywords` e temas de proposição são
    dados temáticos; índices de alias são artefatos temporários; índices
    físicos dependem da materialização futura. Não haverá coluna canônica
    genérica `index`.

### Resultado das oito hipóteses de alias

Duplicações técnicas aprovadas, todas com escopo restrito:

1. Câmara/CCJC: `CodigoEvento` ↔ `evento_id`.
2. Câmara/CCJC: `TextoIntegral` ↔ `texto`.
3. Câmara/pareceres de PEC: `TextoIntegral` ↔ `texto`.
4. Senado/CCJ: `CodigoReuniao` ↔ `codigo_reuniao`.
5. Senado/CCJ: `TextoIntegral` ↔ `texto`.
6. Senado/Congresso: `CodigoPronunciamento` ↔
   `codigo_pronunciamento`.
7. Senado/Plenário: `CodigoPronunciamento` ↔
   `codigo_pronunciamento`.

Hipótese rejeitada:

8. As subárvores de agenda e detalhe da CCJ não são aliases. Mesmo quando
   coincidem integralmente, como foi observado na reunião `14657`, continuam
   respostas distintas, obtidas por endpoints e momentos distintos, ligadas
   pelo ID oficial da reunião.

### Produto lógico agora e camada física depois

As colunas e famílias aprovadas formam um **vocabulário lógico canônico**. Elas
não determinam que haverá um único Parquet largo, um Parquet por coluna ou
qualquer nome físico específico.

O produto de G02 é documental e contratual. Exemplos:

1. `schema_normalizado.schema.json`, para expressar tipos, campos e
   cardinalidades do contrato lógico;
2. `livro_campos.csv`, para registrar a decisão de cada caminho raw;
3. `mapeamentos_propostos.csv`, para relacionar caminho de origem, destino
   canônico, regra e proveniência;
4. `auditoria_aliases.csv`, para preservar evidências e decisões sobre pares
   como `CodigoReuniao` ↔ `codigo_reuniao`;
5. `senado_ccj_notas.md`, para documentar a hierarquia polimórfica específica.

Depois de G02, os adaptadores determinísticos serão especificados e aprovados
em G03. A execução integral e a geração da camada processada ocorrerão somente
em G05, depois da etapa separada de marcadores textuais de G04. O formato
físico dessa camada, inclusive a escolha por Parquet, quantidade de tabelas,
nomes, partições e chaves físicas, ainda precisará de contrato próprio.

Se Parquet for escolhido, uma disposição coerente com as decisões atuais
poderia conter, apenas como **exemplo ilustrativo não aprovado**:

| Parquet futuro ilustrativo | Unidade de linha | Exemplo |
|---|---|---|
| `committee_meetings.parquet` | identidade de reunião | reunião da CCJ `14657` |
| `committee_meeting_observations.parquet` | observação por endpoint e coleta | agenda e detalhe da reunião `14657` |
| `meeting_parts.parquet` | parte de reunião | partes `18966` e `18967` da reunião `14685` |
| `agenda_items.parquet` | item de pauta contextual | um dos 11 itens da parte `18930` |
| `agenda_item_outcomes.parquet` | resultado observado em reunião e item | vista da `OFS 4/2026` na reunião `14657` |
| `legislative_documents.parquet` | identidade documental | documento declarado em `doma.textos` |
| `document_context_links.parquet` | aparição e papel de documento | vínculo do documento com matéria ou pauta |
| `taquigraphic_quarters.parquet` | quarto taquigráfico | quarto `3765408` |
| `taquigraphic_markers.parquet` | marcação dentro do quarto | marcação do tipo `Palavra` ou `Matéria` |
| `speeches.parquet` | fala ou pronunciamento | pronunciamento do Senado com `Indexacao` |

Essa separação evita repetir todos os dados da reunião em cada item,
documento ou marcação e evita perder relações `1:N`. A proveniência poderá
ser composta por colunas técnicas em cada tabela ou por estruturas auxiliares;
essa escolha física também permanece aberta. Em qualquer disposição, os
Parquets seriam derivados novos e o raw continuaria imutável.

### Efeito da aprovação final

A consolidação autorizou somente sincronizar `requirements.md`, `plan.md`,
`validation.md` e `tech-stack.md` de `02_schema_normalizado` com as decisões
registradas neste diário. Essa sincronização foi realizada em 2026-07-25.

A aprovação final **não autorizou**:

- executar Batch;
- implementar ou materializar a normalização;
- modificar qualquer dado raw;
- alterar coletores ou código de produção;
- declarar concluídas validações operacionais ainda não executadas;
- marcar G02 inteiro como operacionalmente concluído apenas porque a revisão
  humana terminou.

G02 ainda contém trabalho operacional posterior, incluindo a aplicação
reprodutível das regras aos caminhos catalogados e a validação dos artefatos
resultantes. Portanto, a aprovação final fecha a decisão humana do contrato,
mas não substitui execução nem evidência de validação.

## Referências oficiais consultadas

Consulta em 2026-07-25:

- Câmara — API e recursos de eventos:
  <https://dadosabertos.camara.leg.br/swagger/api.html>
- Câmara — situações oficiais de eventos:
  <https://dadosabertos.camara.leg.br/api/v2/referencias/eventos/codSituacaoEvento>
- Câmara — tipos oficiais de eventos:
  <https://dadosabertos.camara.leg.br/api/v2/referencias/eventos/codTipoEvento>
- Câmara — proposições:
  <https://dadosabertos.camara.leg.br/swagger/api.html?tab=api>
- Câmara — tipos de proposição:
  <https://dadosabertos.camara.leg.br/api/v2/referencias/proposicoes/siglaTipo>
- Câmara — schema oficial de discursos, incluindo `keywords`:
  <https://dadosabertos.camara.leg.br/api/v2/api-docs>
- Câmara — temas oficiais de proposições:
  <https://dadosabertos.camara.leg.br/api/v2/proposicoes/2252029/temas>
- Câmara — detalhe oficial do evento `81996` da CCJC:
  <https://dadosabertos.camara.leg.br/api/v2/eventos/81996>
- Senado — documentação OpenAPI:
  <https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html>
- Senado — exemplo oficial de `Indexacao` em pronunciamentos:
  <https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20240701/20240702.json>
- Senado — exemplo oficial de pronunciamentos do Congresso Nacional:
  <https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20240501/20240531.json?siglaCasa=CN&v=4>
- Senado — detalhe oficial de reunião da CCJ:
  <https://legis.senado.leg.br/dadosabertos/comissao/reuniao/14657.json>
- Senado — agenda oficial que contém a reunião `14657`:
  <https://legis.senado.leg.br/dadosabertos/comissao/agenda/20260513/20260513.json?v=2>
- Senado — reunião `14685`, exemplo de `partes` como array:
  <https://legis.senado.leg.br/dadosabertos/comissao/reuniao/14685.json?v=2>
- Senado — reunião `14817`, exemplo de parte de audiência pública:
  <https://legis.senado.leg.br/dadosabertos/comissao/reuniao/14817.json?v=2>
- Senado — notas taquigráficas estruturadas da reunião `14657`:
  <https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/reuniao/14657.json?v=1>
- Senado — tipos de uso da palavra:
  <https://legis.senado.leg.br/dadosabertos/senador/lista/tiposUsoPalavra.json>
- Senado — tipos e siglas de documentos e processos:
  <https://legis.senado.leg.br/dadosabertos/processo/siglas.json>

## Pendências da revisão

- Nenhuma pendência na revisão humana do vocabulário conceitual.
- As pendências operacionais de G02 continuam registradas nas quatro specs,
  sem autorização para Batch, adaptadores, normalização ou alteração do raw.

## Histórico de atualização

- 2026-07-25 — Criado o diário e transcritas as 21 decisões tomadas até
  `proposition_type_acronym`.
- 2026-07-25 — `proposition_number` e `proposition_year` aprovados como
  componentes analíticos comuns no formato número/ano, mantendo IDs e
  proveniência distintos.
- 2026-07-25 — `proposition_abstract_source` aprovada somente para ementa
  explícita da fonte, sem fusão com ementa detalhada, resumo ou texto integral.
- 2026-07-25 — `document_id` e `document_type_source` marcados para revisão,
  preservando namespaces de IDs e separando taxonomia oficial de classificação
  derivada pelo coletor.
- 2026-07-25 — `document_url` e `document_media_type` marcados para revisão,
  preservando papéis de URL e separando MIME declarado, resposta HTTP e
  detecção técnica.
- 2026-07-25 — `opinion_deliberative_status_source` e
  `opinion_superseded_source` marcados para revisão, reclassificando os campos
  atuais como derivações do coletor e distinguindo “vencido” de “substituído”.
- 2026-07-25 — `person_official_id` e `person_name_source` marcados para
  revisão, preservando namespaces de IDs, papéis dos nomes e autoria não
  necessariamente pessoal.
- 2026-07-25 — Explicitada a separação obrigatória entre reuniões da CCJ do
  Senado, reuniões da CCJC da Câmara e sessões plenárias das duas Casas.
- 2026-07-25 — `speaker_role_source` marcado para revisão, separando papel da
  fala, cargo autoral, função autoral e forma de tratamento por participação.
- 2026-07-25 — `party_acronym_source` e `federative_unit_source` marcados para
  revisão, preservando partido e UF por papel, tempo e namespace.
- 2026-07-25 — `sex_or_gender_source_reported` revisado para representar
  somente o rótulo de sexo registrado pela fonte, com limitação explícita para
  identidade de gênero e representação trans.
- 2026-07-25 — `text_content_raw` e `text_status_source` marcados para revisão,
  separando artefatos textuais por origem e status técnicos por tentativa do
  coletor.
- 2026-07-25 — `request_metadata` e `response_metadata` aprovados como objetos
  de controle técnico. Concluída a revisão individual das 40 colunas da
  proposta global.
- 2026-07-25 — Registrada a lacuna da proposta quanto à posição concreta em
  arrays e separadas quatro noções de indexação: ocorrência raw, coordenada do
  registro, índice de candidatos a alias e índice físico de consulta.
- 2026-07-25 — Corrigida a ambiguidade de “indexação”: `Indexacao` do Senado e
  `keywords` da Câmara são metadados temáticos de pronunciamentos/discursos.
  Registrada nova família temática, distinta de índices técnicos e de temas
  estruturados de proposições.
- 2026-07-25 — Aprovada a inclusão da família temática omitida, com
  `speech_indexing_source_raw` para indexação literal de falas e
  `proposition_subject_source` para assuntos estruturados de proposições.
- 2026-07-25 — A observação humana sobre `CodigoReuniao` foi confirmada no
  escopo de `senado/ccj_notas`: o coletor filtra reuniões da CCJ e cria
  `CodigoReuniao` e `codigo_reuniao` com o mesmo valor. Proposta revisão do
  alias para duplicação técnica restrita a reuniões de comissão.
- 2026-07-25 — Aprovada a revisão para `committee_meeting_id`, restrita a
  reuniões de comissão/colegiado do Senado. Explicitada a imutabilidade do raw:
  as duas grafias permanecem como coletadas e eventual deduplicação somente
  poderá ocorrer em artefato normalizado futuro e separado.
- 2026-07-25 — Verificado que `CodigoEvento` e `evento_id` são cópias criadas
  pelo coletor em `camara/ccjc_eventos/notas_taquigraficas`, a partir do `id`
  oficial do recurso de evento da Câmara. Proposta reclassificação do alias
  para duplicação técnica restrita ao `record_type`.
- 2026-07-25 — Investigada e rejeitada, para esse par, a hipótese de o valor
  ser código de tipo: `id=81996` identifica uma ocorrência, enquanto
  `codTipoEvento=112` identifica a categoria `Reunião Deliberativa`. O ID
  continuará opaco, sem inferência por aparente sequencialidade.
- 2026-07-25 — Aprovada a reclassificação de `CodigoEvento` e `evento_id`
  como duplicação técnica do coletor, restrita às notas da CCJC. O destino
  conceitual continua `event_id`, separado do código e rótulo do tipo.
- 2026-07-25 — Verificado que os pares `TextoIntegral` ↔ `texto` nas notas da
  CCJC e nos pareceres de PEC são cópias criadas pelos respectivos coletores.
  Proposta revisão com artefatos textuais distintos por origem e método.
- 2026-07-25 — Aprovada a reclassificação dos dois pares textuais da Câmara
  como duplicações técnicas do coletor, mantendo separados o agregado das
  notas da CCJC e o texto extraído de cada documento de parecer.
- 2026-07-25 — Verificado que `TextoIntegral` e `texto` nas notas da CCJ do
  Senado recebem a mesma variável do coletor, após API normal, API forçada ou
  fallback HTML. Proposta revisão com preservação explícita desses métodos.
- 2026-07-25 — Aprovada a reclassificação de `TextoIntegral` e `texto` nas
  notas da CCJ do Senado como duplicação técnica, mantendo métodos, tentativas,
  quartos e fallback HTML separados.
- 2026-07-25 — Verificado que os pares `CodigoPronunciamento` e
  `codigo_pronunciamento` de Congresso e Plenário são cópias do construtor
  compartilhado. Proposta revisão separada por `house_scope=CN` e `SF`.
- 2026-07-25 — Aprovada a reclassificação dos dois pares de pronunciamento
  como duplicações técnicas, mantendo separados `house_scope=CN` e
  `house_scope=SF` e sem pressupor namespace global entre eles.
- 2026-07-25 — Auditado o candidato `F13711 ↔ F16294`: agenda e detalhe são
  respostas distintas ligadas pelo código oficial da reunião. Embora o
  exemplo `14657` fosse exatamente igual nos dois endpoints no momento da
  consulta, foi proposta a rejeição como alias e a substituição por
  relacionamento com proveniência e cardinalidades preservadas.
- 2026-07-25 — Aprovada a rejeição de `F13711 ↔ F16294` como alias de
  subárvores. Agenda e detalhe permanecerão observações distintas da mesma
  reunião, ligadas por `committee_meeting_id`.
- 2026-07-25 — Iniciada a revisão separada da família polimórfica de
  `senado/ccj_notas`. No primeiro bloco, proposto tratar `partes` e `itens`
  como ocorrências-filhas hierárquicas, preservando IDs, tipos oficiais,
  ordem, variantes `object|array` e estados de ausência.
- 2026-07-25 — Aprovadas `meeting_part_source` e `agenda_item_source` como
  ocorrências-filhas hierárquicas, mantendo o vínculo
  reunião → parte → item e sem confundir seus IDs com evento, matéria,
  proposição, processo ou documento.
- 2026-07-25 — No segundo bloco polimórfico, proposto tratar `doma` como
  observação estruturada com IDs distintos de matéria, processo, origem e
  conteúdo, e `relatorias` como designações temporais entre processo,
  colegiado, pessoa e papel.
- 2026-07-25 — Aprovados `legislative_matter_observation` para `doma` e
  `rapporteur_assignment_source` para `relatorias`, preservando entidades,
  papéis e temporalidade sem resolver pessoas por nome.
- 2026-07-25 — No terceiro bloco polimórfico, proposto representar documentos
  de `doma.textos` como entidades documentais e cada aparição em
  `doma.textos` ou `textosPauta` como vínculo contextual distinto.
- 2026-07-25 — Aprovados `legislative_document_source` e
  `document_context_link_source`: documentos mantêm identidade própria e
  aparições em matéria e pauta conservam papéis, ordem e proveniência.
- 2026-07-25 — No quarto bloco polimórfico, proposta a separação entre
  reunião, parte e evento aninhado, além de ocorrências distintas para
  convidados e participantes vinculadas somente por `codigoConvidado` exato.
- 2026-07-25 — Aprovados `committee_embedded_event_source` e
  `event_involvement_source`, mantendo distintos reunião, parte, evento,
  convite, participação, pessoa e documento de apresentação.
- 2026-07-25 — No quinto bloco polimórfico, propostos vínculos próprios para
  matérias relacionadas ao evento e para autorias de pessoas ou instituições,
  sem tratar `autorItemPauta` e `doma.autorias` como aliases.
- 2026-07-25 — Aprovados `event_related_matter_link_source` e
  `authorship_assignment_source`, preservando finalidade, ordem, autores
  individuais e autores institucionais em seus papéis próprios.
- 2026-07-25 — No sexto bloco polimórfico, proposto preservar a linha do tempo
  de estados da reunião e resultados por ocorrência de item, sem atribuir à
  matéria um resultado global.
- 2026-07-25 — Aprovados `meeting_state_observation_source` e
  `agenda_item_outcome_source`, mantendo estados históricos e resultados
  contextualizados por reunião, parte e item.
- 2026-07-25 — No sétimo bloco polimórfico, proposto representar quartos e
  marcações taquigráficas como ocorrências distintas, sem interpretar texto,
  resolver oradores por nome ou confundir marcação com item de pauta.
- 2026-07-25 — Aprovados `taquigraphic_quarter_source` e
  `taquigraphic_marker_source`, preservando texto, áudio, tipos, papéis,
  sequências e variantes de contêiner sem segmentação inferida.
- 2026-07-25 — No oitavo bloco polimórfico, proposto preservar separadamente
  vínculos de colegiado criador e associado e a presidência contextual da
  reunião.
- 2026-07-25 — Aprovados `meeting_arena_assignment_source` e
  `meeting_presidency_source`, preservando papéis institucionais e presidência
  contextual sem inferência a partir de fala.
- 2026-07-25 — No nono bloco polimórfico, proposto separar vídeos da reunião
  e apresentações documentais de participantes, com namespaces e papéis de
  URL próprios.
- 2026-07-25 — Aprovados `meeting_video_source` e
  `participant_presentation_document_source`, mantendo separados vídeo,
  documento ECM, participação e papéis de URL.
- 2026-07-25 — No décimo bloco polimórfico, proposto preservar o tipo oficial
  da reunião, modalidade e indicadores operacionais, além do período de
  sessão legislativa separado de sessão plenária.
- 2026-07-25 — Aprovados `committee_meeting_type_source`,
  `meeting_modality_source` e `legislative_session_context_source`. Concluída
  a revisão substantiva da família polimórfica de `senado/ccj_notas`.
- 2026-07-25 — Aberta a decisão técnica final: proposta coordenada obrigatória
  de registro, JSON Pointer concreto por valor e separação entre indexação
  temática, índice temporário de aliases e índice físico de consulta.
- 2026-07-25 — Aprovadas `source_record_coordinate`,
  `source_value_coordinate` e `technical_index_policy`, com caminho raw
  relativo, convenção explícita de número de registro, JSON Pointer concreto,
  forma original dos contêineres, hash reproduzível e proibição de usar
  posição como identidade.
- 2026-07-25 — Consolidada para decisão humana final a revisão das 40 colunas,
  das duas famílias temáticas omitidas, das oito hipóteses de alias, dos dez
  blocos polimórficos de `senado/ccj_notas` e das três políticas técnicas. A
  consolidação distingue aprovação do contrato humano de conclusão
  operacional de G02.
- 2026-07-25 — Esclarecido que G02 define o vocabulário e o schema lógico, não
  cria Parquets nem fixa sua disposição física. Registrado um exemplo
  ilustrativo de possíveis tabelas por entidade para tornar visível o produto
  futuro, mantendo formato, nomes, partições e chaves sujeitos aos contratos
  posteriores.
- 2026-07-25 — O pesquisador aprovou integralmente a síntese consolidada e
  autorizou sua incorporação às specs. `requirements.md`, `plan.md`,
  `validation.md` e `tech-stack.md` foram sincronizados sem executar Batch,
  implementar adaptadores ou normalização, materializar Parquets ou alterar
  dados raw.
- 2026-07-25 — Em autorização posterior e específica, o pesquisador liberou
  uma operação Batch controlada para propor o mapeamento dos 23.786
  `field_id` no vocabulário já aprovado e a auditoria integral do `raw/` em
  modo somente leitura. A autorização permite reutilizar a
  `OPENAI_API_KEY` local, sem exibi-la ou preservá-la, e não libera aplicação
  da proposta, normalização, adaptadores, Parquets ou alteração do raw.
- 2026-07-25 — A tentativa Batch com o alias `gpt-5.6` foi rejeitada pela API
  antes de processar requisições. A tentativa foi preservada e o contrato
  corrigido para o identificador Batch compatível `gpt-5.6-sol`.
- 2026-07-25 — Submetida a tentativa válida
  `batch_6a6560b67d108190b7be8423e6e55906`, com 99 requisições independentes,
  1.353.952 tokens de entrada contados, o mesmo vocabulário congelado em
  todas as linhas e `proposal_applied=false`.
- 2026-07-25 — Iniciada no Colab a auditoria integral
  `schema-evidence-full-20260725`, lendo o raw sem modificá-lo e escrevendo
  primeiro em `/content`. A cópia final está destinada à pasta de auditoria
  separada no Drive.
- 2026-07-25 — A tentativa Batch válida terminou as 99 requisições, mas o
  validador bloqueou cobertura incompleta: 19.779 IDs válidos, 3.984 omitidos
  e 23 combinações incompatíveis com o contrato, totalizando 4.007 IDs
  pendentes. O custo efetivo foi US$ 16,066915 e nada foi aplicado.
- 2026-07-25 — O pesquisador autorizou reenvios controlados até obter
  cobertura exata. Foi submetido o reparo incremental
  `batch_6a6565aebe008190a562302473110088`, somente com os 4.007 IDs pendentes,
  em 43 requisições de até 100 campos e 361.313 tokens de entrada.
- 2026-07-25 — O primeiro reparo reconciliou 4.005 dos 4.007 IDs pelo custo
  efetivo de US$ 3,6864725. `F01575` foi rejeitado por combinação semântica
  inválida e `F05877` foi omitido; ambas as respostas brutas foram
  preservadas sem correção silenciosa.
- 2026-07-25 — Com autorização expressa para reenviar até obter cobertura
  exata, foi submetido o segundo reparo
  `batch_6a656c92f3dc81908c4e008f436cb241`, contendo somente `F01575` e
  `F05877`, em duas requisições de um campo.
- 2026-07-25 — O segundo reparo validou os dois IDs pelo custo efetivo de
  US$ 0,0180515. A união disjunta das três tentativas reconciliou exatamente
  23.786 IDs únicos, sem ausentes ou inventados, ao custo total de
  US$ 19,7714390. Todos permanecem com `human_decision=nao_avaliado` e
  `proposal_applied=false`; o gate passou somente para revisão humana.
- 2026-07-26 — A auditoria integral raw
  `schema-evidence-full-20260725` terminou com sucesso e releu 1.148.740
  registros. O fingerprint
  `7cd7fa0d9f7cec648187e8d2da857c8bdac8861ac6f476662ce6bb97d9730da2`
  permaneceu idêntico antes e depois; nenhum dado raw foi escrito.
- 2026-07-26 — O livro produzido contém as 23.786 chaves únicas do
  inventário, sem ausentes nem inventadas. Permanecem não avaliadas
  humanamente 23.768 linhas do livro e todas as 23.786 propostas Batch; a
  conclusão técnica não foi convertida em aprovação operacional.
- 2026-07-26 — A auditoria preservou 543 conflitos, a distribuição
  `540 + 1 + 2` e os 20.523 caminhos de `senado/ccj_notas`. Oito comparações
  de duplicação técnica tiveram igualdade exata de 100% no escopo preenchido;
  `agenda` e `detalhe` divergiram nas 983 coocorrências, confirmando que não
  são aliases. Todas as decisões operacionais de alias continuam
  `nao_avaliado`.
- 2026-07-26 — Identificada e documentada uma deduplicação de avisos herdada
  de G01: a contagem por arquivo registrava 14 rejeições, mas a lista de
  inconsistências continha 9 linhas porque não usava o número da linha na
  chave de deduplicação. O raw e a auditoria original foram preservados.
- 2026-07-26 — A operação suplementar
  `schema-evidence-full-20260725-rejected-lines-reconciliation` releu somente
  os seis arquivos afetados e reconciliou 14 coordenadas e 14 hashes únicos,
  recuperando as cinco coordenadas omitidas da lista de avisos. O fingerprint
  permaneceu igual e não houve escrita no raw ou materialização normalizada.
