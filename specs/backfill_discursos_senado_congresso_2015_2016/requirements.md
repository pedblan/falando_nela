# Requisitos: backfill de discursos do Senado e do Congresso em 2015–2016

## Objetivo

Detectar em qual camada desaparecem os discursos de 2015 e 2016 das arenas
`senado` e `congresso`, recuperar o conjunto histórico por fontes oficiais,
incorporá-lo ao raw cumulativo e reconstruir os derivados canônicos sem
alterar a Câmara, outros anos ou execuções analíticas anteriores.

Esta é uma recuperação histórica explicitamente solicitada. Ela não faz parte
do ciclo incremental normal e deve usar ciclo, `run_id`s, manifests, auditorias
e locks próprios.

## Evidência inicial e hipótese operacional

- O caderno
  `notebooks/analise/00_snapshot_discursos_plenario_colab.ipynb` monta uma
  matriz completa por `arena/ano` e lista anos com zero discursos, mas hoje não
  bloqueia a análise quando um ano completo está ausente.
- Em 2026-07-14, probes mensais em
  `GET /dadosabertos/plenario/lista/discursos/{dataInicio}/{dataFim}.json`, com
  `v=4` e `siglaCasa=SF` ou `CN`, retornaram `Sessoes=null` para todos os 48
  pares casa/mês entre `2015-01` e `2016-12`.
- Na mesma data, a fonte retornou dados fora da lacuna, entre eles:
  `SF/2014-05` com 358 pronunciamentos, `SF/2017-03` com 65,
  `CN/2014-05` com 35 e `CN/2017-04` com 7.
- Pronunciamentos dos anos ausentes continuam disponíveis em páginas oficiais,
  no endpoint por senador e no endpoint de texto integral. Portanto, resposta
  mensal vazia em 2015–2016 deve ser classificada como `source_anomaly` até
  prova em contrário, nunca como comprovação de que não houve atividade.

Essas contagens são evidência diagnóstica datada, não constantes permanentes.
A execução deve repetir os probes e registrar o payload, o status HTTP, a data
da consulta e o checksum.

## Escopo temporal e institucional

- Janela inclusiva: `2015-01-01` a `2016-12-31`.
- Bases afetadas:
  - `senado/plenario_discursos`, com casa `SF` e arena `senado`;
  - `senado/congresso_discursos`, com casa `CN` e arena `congresso`.
- Base de controle, sem mutação: `camara/plenario_discursos`.
- Anos de controle da fonte: pelo menos um mês não vazio antes e outro depois
  da lacuna para cada casa.
- Outros anos e datasets ficam fora da coleta histórica e devem permanecer
  idênticos nos derivados, salvo mudança explicitamente auditada e aprovada.

## Controle do ciclo histórico

- Criar um `cycle_id` exclusivo, por exemplo
  `backfill-discursos-senado-congresso-2015-2016-AAAAMMDD`.
- Gravar sua configuração em
  `operations/atualizacao/ciclos/{cycle_id}/config.json` e usar
  `operations/atualizacao/active.json` somente enquanto esse ciclo estiver
  efetivamente ativo.
- Registrar:
  - `collection_start = 2015-01-01`;
  - `collection_end = 2016-12-31`;
  - `overlap_start = 2015-01-01`;
  - `raw_policy = immutable_cumulative`;
  - `processed_policy = canonical_current`;
  - duas entradas em `historical_recoveries`, uma por dataset;
  - estratégia de descoberta escolhida, probes, controles e `run_id`s;
  - commit do repositório e versões das dependências.
- Fixar uma vez os `run_id`s de coleta e reutilizá-los com `--resume`. Não
  trocar o `run_id` para ocultar falhas ou partições incompletas.
- Usar lock persistente separado para cada `source/dataset`.

## Auditoria em camadas

Antes de qualquer escrita, produzir um inventário imutável `pre` e depois um
inventário `post`, ambos por `source/dataset/ano/mes`, contendo no mínimo:

- resposta da descoberta oficial e quantidade de sessões/pronunciamentos;
- `CodigoPronunciamento` descobertos;
- registros raw `pronunciamento_texto` e estado do texto;
- `texto_id`s nos JSONLs processados;
- `texto_id`s nos Parquets;
- linhas no snapshot analítico;
- `run_id`, caminho, checksum e timestamp dos artefatos lidos;
- motivo de exclusão em cada transição de camada.

A auditoria deve distinguir pelo menos:

- `source_anomaly`: fonte primária vazia em janela sabidamente coberta;
- `not_discovered`: ausente em todas as estratégias oficiais aceitas;
- `raw_missing`: descoberto, mas sem registro textual raw;
- `text_unavailable`: registro raw auditável sem texto oficial aproveitável;
- `normalization_loss`: texto raw disponível ausente no processed;
- `parquet_loss`: `texto_id` processado ausente no Parquet correspondente;
- `snapshot_filter_loss`: registro do Parquet ausente no snapshot, com regra de
  filtro ou deduplicação identificada;
- `covered`: reconciliado até a última camada aplicável.

Uma partição mensal pode ser legitimamente vazia, mas somente quando todas as
fontes oficiais aceitas concordarem e o probe estiver arquivado. Um ano alvo
não pode ser aceito apenas porque passou a ter uma linha.

## Estratégia de descoberta oficial

- A CLI compartilhada deve aceitar
  `--discovery-strategy period-session|historical-official`. O default continua
  `period-session`; a recuperação nunca é acionada implicitamente só porque um
  mês veio vazio.
- Reexecutar primeiro o endpoint mensal atual. Se ele voltar a fornecer dados,
  ainda assim comparar seus identificadores com a estratégia alternativa antes
  de declará-lo recuperado.
- Se a anomalia persistir, usar uma estratégia alternativa composta somente por
  fontes oficiais do Senado, avaliando ao menos:
  - `GET /dadosabertos/senador/{codigo}/discursos`, versão vigente, com
    `casa=SF|CN`, `dataInicio` e `dataFim` explícitos;
  - busca oficial de pronunciamentos em
    `https://www25.senado.leg.br/web/atividade/pronunciamentos`, incluindo
    paginação, autores sem código de senador e a casa exibida no detalhe;
  - `GET /dadosabertos/discurso/texto-integral/{CodigoPronunciamento}` para o
    texto canônico;
  - notas de sessão como fallback textual, conforme o contrato já existente.
- O endpoint por senador, isoladamente, não comprova cobertura do Congresso,
  pois a população pode conter deputados, autoridades ou outros autores. A
  busca oficial deve ser usada para auditar e completar autores que não sejam
  alcançados pela enumeração de senadores.
- Como o endpoint por senador aceita no máximo um ano, 2015 e 2016 devem ser
  consultados em janelas separadas, ainda que o ciclo cubra os dois anos.
- A combinação escolhida deve provar paridade em meses-controle nos quais o
  endpoint mensal funciona:
  - recuperar 100% dos `CodigoPronunciamento` da fonte de controle;
  - classificar todo identificador adicional por casa, data e URL oficial;
  - não misturar `SF` e `CN`;
  - deduplicar somente por `CodigoPronunciamento`, preservando divergências de
    metadados na auditoria.
- Se nenhuma combinação atingir a paridade, bloquear o backfill. Não preencher
  a lacuna por amostra, busca web genérica, inferência por sequência numérica ou
  raspagem de fonte não oficial.

## Contrato raw da recuperação

- Preservar o layout já consumido pela normalização:
  `raw/senado/{dataset}/ano=YYYY/mes=MM/{run_id}.jsonl`.
- Preservar `record_type=pronunciamento_texto` e o contrato dos campos
  `CodigoPronunciamento`, `codigo_pronunciamento`, `TextoIntegral`,
  `TextoIntegralUrl`, `texto`, `forma`, `metodo_obtencao`, `texto_status`,
  `metadata` e `fontes`.
- Usar `source_id=SF:pronunciamento:{codigo}` para Senado e
  `source_id=CN:pronunciamento:{codigo}` para Congresso.
- Acrescentar proveniência suficiente para distinguir a estratégia de
  descoberta, a URL oficial consultada, o payload bruto, a data da consulta e
  os conflitos entre fontes.
- Gravar respostas de descoberta em `metadata/`; HTML ou JSON bruto de
  descoberta nunca deve entrar como unidade textual no corpus mensal.
- Nunca apagar, mover, truncar ou reescrever raw preexistente.
- Cada pronunciamento descoberto deve resultar em exatamente um dos estados:
  texto oficial disponível, fallback oficial disponível ou
  `pendente_transcricao_video`. Falha inesperada não pode ser convertida em
  ausência de texto nem permitir concluir a partição.
- Respeitar o limite oficial de requisições, retries, `Retry-After`, autosave,
  checkpoint por `run_id` e retomada idempotente.

## Reconstrução dos derivados

- Somente após os gates das duas coletas, regenerar a fotografia cumulativa
  completa, sem filtrar a normalização apenas pelos `run_id`s do backfill.
- Usar os identificadores canônicos já adotados pelo projeto, incluindo
  `processed-textos-v1-current` e `parquet-textos-v1-current`, com
  `--overwrite` apenas nos derivados reconstruíveis.
- O normalizador deve escolher uma única ocorrência por `texto_id`, registrar
  duplicatas e manter a proveniência do raw selecionado.
- Registros com texto vazio podem ficar fora do processed somente se aparecerem
  como `text_unavailable` na reconciliação.
- Fora de 2015–2016, `texto_id`, conteúdo e contagens devem permanecer
  invariantes em relação ao inventário `pre`.
- Dentro da janela, remoções ou alterações de registros preexistentes exigem
  justificativa por `texto_id`; a expectativa normal é adição ou substituição
  auditável da mesma unidade.

## Gate de cobertura analítica

- O snapshot deve ter exatamente as arenas `camara`, `senado` e `congresso`.
- Para todos os anos completos definidos por
  `complete_year_start..complete_year_end`, cada arena obrigatória deve ter
  pelo menos um discurso. Zero anual deve falhar cedo, não apenas ser impresso.
- A matriz anual completa e a lista de anos ausentes continuam sendo exibidas
  e passam também a ser artefatos persistidos.
- O gate anual não substitui a reconciliação de identificadores. Para
  2015–2016, o aceite exige cobertura integral da estratégia oficial aprovada.
- O snapshot pós-backfill deve usar novo `analysis_run_id`; resultados da rodada
  anterior são imutáveis e servem como `compared_to`.
- Duplicatas exatas Senado × Congresso removidas do snapshot devem aparecer na
  auditoria própria e explicar a diferença em relação aos Parquets.

## Sentinelas mínimos

Os seguintes pronunciamentos oficiais devem ser localizáveis na descoberta,
no raw e no derivado da arena indicada; eventual ausência do snapshot exige
uma remoção por duplicidade explicitamente comprovada:

- Senado 2015: `CodigoPronunciamento=414849`;
- Senado 2016: `CodigoPronunciamento=422757`;
- Congresso 2015: `CodigoPronunciamento=411219`;
- Congresso 2016: `CodigoPronunciamento=426642`.

As sentinelas não medem completude; apenas impedem que uma execução vazia ou
com classificação de casa incorreta seja aceita.

## Artefatos obrigatórios

Sob `operations/atualizacao/ciclos/{cycle_id}/`, persistir no mínimo:

- `config.json`;
- `source_probes.jsonl`;
- `coverage_pre.csv` e `coverage_post.csv`;
- `reconciliation_ids.parquet`;
- `source_conflicts.jsonl`;
- cópias dos manifests de coleta e processamento;
- checksums dos Parquets antes e depois;
- `summary.json` com gates, contagens, drift e decisão final.

## Sincronização obrigatória na implementação

Quando a recuperação for implementada, atualizar na mesma mudança:

- specs de `coleta/senado/plenario_discursos/` e
  `coleta/senado/congresso_discursos/`;
- specs de `processamento/normalizacao_armazenamento/`;
- specs de `analise/discursos_plenario_comparativo/`;
- READMEs e cadernos de coleta/processamento afetados;
- a célula fonte `notebooks/analise/celulas/00_validacao_snapshot.py`, o gerador
  dos cadernos e seus testes;
- testes do coletor compartilhado, da normalização, do Parquet e do snapshot.

## Fora de escopo

- Refazer toda a história de discursos fora de 2015–2016.
- Alterar ou rebaixar os critérios do corpus da Câmara.
- Tratar transcrição de vídeo como texto oficial nesta recuperação.
- Sobrescrever uma rodada analítica já produzida.
- Declarar a fonte oficial “sem atividade” apenas porque um endpoint respondeu
  HTTP 200 com coleção vazia.
