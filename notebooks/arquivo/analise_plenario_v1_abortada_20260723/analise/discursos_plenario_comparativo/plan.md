# Plano: análise comparativa dos discursos em plenário

## Objetivo

Produzir uma suíte reprodutível de cadernos Colab para comparar discursos da
Câmara dos Deputados, do Senado Federal e do Congresso Nacional entre
`2010-02-02` e `2026-07-13`, preservando as três arenas e a Casa de origem do
parlamentar como dimensões distintas.

Os notebooks são orquestradores finos. Filtros, amostragem, testes, modelos,
gráficos e persistência pertencem a `analise.discursos_plenario`, de modo que a
mesma implementação possa sustentar cadernos Marimo e variantes narrativas em
inglês no futuro.

## Rodada analítica ativa

A suíte 00–09 usa por padrão `analise-plenario-20260717-v1`. O snapshot 00
dessa rodada foi validado com 384.191 discursos e deve permanecer imutável. Os
cadernos seguintes reutilizam esse mesmo `RUN_ID`; a configuração conserva o
corte analítico em `2026-07-13`.

## Gate de cobertura anual

Na etapa 00, construir a matriz cartesiana de todas as arenas configuradas e
todos os anos `complete_year_start..complete_year_end`. Persistir a matriz e
a lista de zeros junto ao snapshot. Somente depois de gravar esses artefatos e
o manifest, permitir continuidade se as arenas observadas forem exatamente
`camara`, `senado` e `congresso` e a lista de zeros estiver vazia. O ano YTD
continua visível na matriz de inspeção do caderno, mas fora desse gate.

## Entradas somente leitura

- `processed/textos_parlamentares/v1/parquet/camara__plenario_discursos.parquet`;
- `processed/textos_parlamentares/v1/parquet/senado__plenario_discursos.parquet`;
- `processed/textos_parlamentares/v1/parquet/senado__congresso_discursos.parquet`;
- `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`;
- `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet`.

Nenhuma etapa analítica altera os Parquets canônicos. As saídas ficam em
`analises/discursos_plenario/v1/{run_id}/` no mesmo `data_root` externo ao
repositório.

## Recorte e unidade institucional

- Data inicial inclusiva: `2010-02-02`.
- Data final inclusiva: `2026-07-13`.
- Câmara e Senado: `ambito=plenario`.
- Congresso: `ambito=congresso`.
- Séries anuais completas: 2010–2025.
- 2026: descrição YTD, sem anualização e fora dos modelos anuais completos.
- `arena` recebe `camara`, `senado` ou `congresso`.
- `casa_origem` preserva a origem registrada para o parlamentar.

## Arquitetura

O contrato central está em `analise/discursos_plenario/config.v1.json`. Cada
execução recebe `run_id`, lê entradas imutáveis, grava artefatos de etapa e um
manifest com configuração, checksums, contagens e caminhos.

O ambiente Colab usa o par binário fixo `numpy==2.0.2` e `pandas==2.2.3`,
compatível com o runtime 2026.04. A célula compartilhada de preparação
reinstala esse par sem cache, instala `requirements-analise.txt` e valida as
duas importações tanto no kernel quanto em um subprocesso antes de carregar
qualquer módulo analítico.

Módulos:

- `snapshot.py`: filtros, limpeza aprovada, auditoria de duplicação e junção temporal;
- `genero.py`: fila de pesquisa, evidências e publicação revisada;
- `descritivas.py`: painéis exatos e bootstrap opcional por orador;
- `apartes.py`: ponte da Câmara, díades e testes de associação;
- `apartes_episodios.py`: turnos determinísticos, episódios multiturno v2,
  reconstrução local e gate humano;
- `nlp.py`: TextDescriptives, morfossintaxe e padrões específicos;
- `inferencia.py`: correlações, primeiras diferenças, BH e tendências HAC;
- `clusterizacao.py`: avaliação de `k=2…8` e estabilidade;
- `topicos.py`: amostra balanceada e modelo BERTopic comum;
- `figuras.py`: codebook, Batch API, Structured Outputs e validação;
- `sintese.py`: inventário, cobertura, tabelas e figuras finais.

## Etapas

### 00 — Snapshot e auditoria

Filtrar as três arenas; manter `texto_original` e `texto_analitico`; aplicar
somente regras `hard_cut` aprovadas; calcular elegibilidade; realizar junção
temporal; auditar conflitos de `texto_id`, duplicatas exatas e quase duplicatas
Senado × Congresso.

A remoção automática exige concordância de data, autor, sessão, conteúdo e um
identificador não vazio. Quando uma fala do Senado e outra do Congresso
representarem o mesmo registro, preserva-se a arena Congresso e documenta-se a
remoção da cópia do Senado. Sem essa concordância, o par segue para revisão.

### 01 — Gênero oficial; pesquisa suspensa

Nesta rodada, usar somente `genero_oficial` já congelado no snapshot. A
pesquisa pública de deputados fica suspensa por custo e baixa qualidade; o
caderno 01 apenas mostra a cobertura por arena. Casos sem metadado permanecem
`nao_informado`, sem inferência por nome. Metadados oficiais do Senado são
preservados. Artefatos antigos da tentativa de pesquisa não são apagados nem
consumidos pelas etapas seguintes.

### 02 — Estatística descritiva

Gerar contagens e distribuições por arena, ano, mês, gênero, partido,
parlamentar e tipo de fala. As descrições do corpus observado são exatas.
Bootstrap por orador só é executado quando o chamador declara a população à
qual pretende generalizar; usar 2.000 repetições e semente `20260713`.

### 03 — Apartes e ponte da Câmara

Aplicar `2010-02-02…2026-07-13`, inclusivo, à base de apartes antes de
qualquer contagem, díade, teste, ponte ou segmentação. Registrar entrada,
linhas no recorte, datas ausentes e exclusões anteriores/posteriores por
fonte.

Calcular relações, díades de gênero observadas/esperadas, razão O/E, χ², Fisher
para tabela 2×2 esparsa e V de Cramér. Corrigir valores-p por BH dentro da
família arena-ano.

A ponte derivada Câmara liga `discurso_chave` ao snapshot usando, quando
disponíveis, identificadores, data, hora, orador, sessão, fase e evento. Os
estados são `exato`, `provavel_unico`, `ambiguo` e `ausente`. Denominadores só
podem ser usados após mensurar precisão contra conjunto ouro e atingir os
limiares declarados, além da cobertura mínima.

Nem todo discurso contém aparte. O universo de segmentação começa nos
registros da base processada de apartes, não em todos os discursos do
snapshot. Depois da ponte, agrupar os candidatos por `texto_id`. Python cria
turnos brutos e subturnos determinísticos com IDs, falantes observados, ordem
e offsets Unicode exatos. O cadastro de participantes vem da base relacional;
a IA pode resolver apenas atribuições ambíguas e associar IDs.

Uma requisição por transcrição reúne todos os candidatos. Para cada candidato,
a saída estruturada devolve status, zero ou mais episódios e listas de IDs
para falas do participante, backchannels, respostas do orador e intervenções
de contexto. Ela não devolve texto. Python reconstrói todos os trechos,
preserva a cronologia e grava tabelas normalizadas de participantes, turnos,
episódios e vínculos episódio–turno.

Episódios podem se sobrepor e compartilhar contexto; um participante pode ter
mais de um episódio. Subturnos separam respostas dirigidas a pessoas
diferentes dentro do mesmo turno bruto. Pedido e concessão de aparte ficam em
contexto, não na fala substantiva.

Os pedidos são particionados automaticamente antes de 50.000 linhas ou 190
MiB. Manifests registram hashes de fontes e partes; o controle retoma por hash
sem duplicar submissões.

Antes de atos de fala, revisar aproximadamente 30 episódios, incluindo
Geovania/Rogério, Júlio Campos e Izalci. O gate exige booleanos válidos para
atribuição dos participantes, completude, atribuição das respostas e
suficiência do contexto, com precisão mínima de 95% em cada dimensão.

`interacoes_segmentadas_ia.parquet`, `revisao_segmentacao_ia.csv` e os Batches
existentes permanecem integralmente como diagnóstico v1. Todos os artefatos
novos recebem `v2`. Nenhum Batch de atos v2 pode ser gerado antes do novo gate,
e nenhum Batch pago pode ser enviado sem autorização explícita adicional.

Reproduzir a análise qualitativa do TD 355 com dois codebooks:

- aparte: `concordar_apoiar`, `elogiar_reconhecer`, `buscar_compromisso`,
  `apelo_a_autoridade`, `explicar`, `procedimental_regimental`,
  `discordar_contestar`, `ataque_ad_hominem`,
  `perguntar_para_esclarecer` e `critica_politica`;
- resposta: `acolhimento_formal`, `conciliacao`, `desvio_topico`, `escalada`,
  `humor_ironico`, `ignorar`, `ad_hominem`, `reclamacao_interacao` e
  `rebatida_factual`;
- interação: `possivel_descortesia` como marca cautelosa e separada.

Codificar manualmente um piloto adjudicado, comparar os modelos GPT-5.6 nos
mesmos casos e produzir prevalências anuais, diferenças em relação à mediana
histórica, painéis por direção de gênero e uma amostra de casos para leitura
qualitativa contextual. Evidência textual é obrigatória; ausência de resposta
segmentada não equivale automaticamente a `ignorar`.

### 04 — NLP, legibilidade e morfossintaxe

Usar TextDescriptives e `pt_core_news_lg`. Extrair Flesch, Gunning Fog, SMOG,
ARI, Coleman–Liau, LIX, distância de dependência, proporções morfossintáticas,
diversidade lexical, comprimento, repetição, pronomes pessoais e sujeitos,
interrogativas, perífrases com `ir`, usos auxiliares/passivos/avaliativos de
`ser` e os padrões textuais definidos na spec.

### 05 — Inferência temporal

Reproduzir Pearson em níveis anuais e acrescentar Spearman, primeiras
diferenças, BH, tendências lineares com erros HAC/Newey–West e sensibilidade
sem 2020–2021. Reportar número e intervalo dos anos. Toda interpretação é
associativa e não causal.

### 06 — Clusterização

Padronizar proporções de pronomes, preposições e auxiliares; avaliar `k=2…8`
com Silhouette, Davies–Bouldin, Calinski–Harabasz, inércia e estabilidade ARI.
Não selecionar `k` automaticamente nem nomear clusters antes da leitura de
centroides, casos representativos e formulário de decisão humana. A conclusão
“sem clusters estáveis” é válida.

### 07 — BERTopic

Usar somente resumos não vazios. Sortear, com semente fixa, até 2.000 resumos
por arena-ano e treinar um modelo comum com encoder, UMAP, HDBSCAN,
vectorizer e stopwords explícitos. Reportar cobertura, outliers, prevalência e
estabilidade por reestimações com sementes documentadas. Marcar 2026 como YTD.

### 08 — Figuras de linguagem

Construir codebook com positivos, negativos e limítrofes; produzir piloto
humano adjudicado; comparar GPT-5.6 Luna, Terra e Sol; adotar Sol por padrão e
só aceitar modelo menor quando o limite de não inferioridade pré-registrado for
atendido. A produção usa Batch API em `/v1/responses` e Structured Outputs.

Preservar `custom_id`, modelo, prompt, schema, evidências, response ID, uso,
erros e custo calculado com tabela de preços versionada. Resultados fora de
ordem são reconciliados por `custom_id`, nunca pela posição da linha.

### 09 — Síntese

Consumir apenas artefatos anteriores, separar arenas, distinguir reprodução,
robustez e exploração, exibir cobertura de gênero e da ponte, marcar 2026 YTD
e exportar CSV, Parquet, HTML, SVG e PNG.

## Jaccard e validação de classificadores

Jaccard mede sobreposição entre o conjunto humano e o conjunto previsto de
figuras em cada discurso e de atos em cada interação. Casos vazio-vazio são
contados separadamente e não entram na média. A avaliação inclui precisão,
recall, micro-F1, macro-F1 e kappa binário por categoria. Contagens recebem
erro absoluto médio e viés médio.

Comparações de modelos usam bootstrap pareado com o orador como cluster. Um
teste por permutação embaralha previsões dentro dos estratos pré-declarados para
avaliar se a sobreposição supera o acaso. Os resultados permitem inferir
concordância e diferença de desempenho sob o plano amostral, não efeitos
causais ou validade substantiva fora do codebook e corpus avaliados.

## Portabilidade

Português é a narrativa canônica. Todas as células Markdown têm ID estável e
metadado `language=pt-BR`; código, caminhos e parâmetros não dependem da prosa.
Uma variante inglesa futura substitui somente Markdown e preserva hash e ordem
das células de código.

Os notebooks evitam estado oculto, redefinições, magias indispensáveis e
efeitos colaterais fora de funções. Uma conversão futura para Marimo começa por
`marimo convert`, é revisada para dependências reativas e deve produzir os
mesmos manifests, schemas, contagens e resultados dentro das tolerâncias.
