# Requirements

## Objetivo

Transformar a camada `raw` gerada na fase 2 em uma camada `processed`
versionada, rastreavel e pronta para cadernos analiticos.

## Entrada

- Ler um diretorio de dados no layout operacional ja usado pelos coletores:
  `raw/{portal}/{dataset}/ano=YYYY/mes=MM/{run_id}.jsonl`.
- Usar `FALANDO_NELA_DATA_ROOT` como origem em producao, especialmente no
  Colab com Google Drive montado em `/content/drive/MyDrive/falando_nela/data`.
- Ignorar `metadata/` e `transcription_queue/` como unidades analiticas, exceto
  quando forem necessarios para enriquecer registros textuais, como o mapa de
  deputados da Camara.

## Saida

- Criar `processed/textos_parlamentares/v1/ano=YYYY/mes=MM/{run_id}.jsonl`.
- Criar `processed/manifests/{run_id}.json` com contagens de entrada, saida,
  duplicatas, arquivos lidos e `raw_run_id`s incorporados.
- Criar uma camada Parquet unificada por base, derivada dos JSONLs
  normalizados, para uso analitico em pandas, Polars ou DuckDB.
- Em producao no Colab, gravar os Parquets em:
  `processed/textos_parlamentares/v1/parquet/{source}__{dataset}.parquet`.
- Em amostras locais, gravar os Parquets em:
  `data/samples/textos_parlamentares/v1/parquet/{source}__{dataset}.parquet`.
- Nao assumir que o caminho local de samples e o caminho do Colab compartilham
  o mesmo `data_root`; o processo deve aceitar raizes explicitas de entrada e
  saida para cada ambiente.
- Manter o dicionario de dados em
  `data/schemas/processed_textos_parlamentares_v1.dictionary.md`.
- Manter `dataset_version = "v1"` em cada registro processado.
- Preservar ponte para a origem por `raw_path`, `raw_run_id`,
  `raw_source_id`, `raw_record_type`, `raw_checksum` e `raw_response_url`.

## Cadernos operacionais

- Manter `notebooks/processamento/normalizacao_armazenamento_colab.ipynb`
  como caminho recomendado para executar a normalizacao no Colab sem depender
  de terminal separado.
- Manter `notebooks/processamento/geracao_parquets_colab.ipynb` como caminho
  recomendado para gerar ou regerar somente os Parquets no Colab, a partir dos
  JSONLs processed ja existentes no Drive.
- Manter `notebooks/processamento/descricao_analitica_bases_colab.ipynb`
  para descrever cada base processada por fonte, dataset, ano, familia textual,
  tamanho de texto, cobertura temporal e preenchimento de campos.
- Manter cadernos exploratorios de Parquet, independentes dos cadernos ja
  executados de normalizacao e geracao:
  - `notebooks/processamento/exploracao_parquets_colab.ipynb`, lendo os
    Parquets completos no Google Drive;
  - `notebooks/processamento/exploracao_parquets_samples_local.ipynb`, lendo os
    Parquets de `data/samples/textos_parlamentares/v1/parquet/`.
- Atualizar estes cadernos sempre que o contrato `textos_parlamentares/v1`,
  os caminhos de dados ou o fluxo de validacao mudarem.

## Normalizacao minima

Cada registro processado deve expor campos comuns para:

- fonte, casa, dataset, ambito e orgao;
- tipo documental e unidade analitica;
- data, ano e mes;
- parlamentar quando houver autoria individual;
- identificadores de pronunciamento, sessao, reuniao, evento, proposicao,
  materia e documento quando disponiveis;
- classificacao de parecer de PEC: `documento_classe`,
  `status_deliberativo` e `vencido`;
- texto, tamanho do texto, forma, status e metodo de obtencao;
- URLs/fontes oficiais.

## Deduplicacao

- `texto_id` deve ser estavel por unidade textual, independente do `run_id`.
- O `run_id` da normalizacao identifica somente a execucao processed e os
  arquivos de saida; ele nao precisa coincidir com nenhum `run_id` bruto.
- A entrada pode combinar varios `run_id`s brutos por base, por exemplo uma
  execucao `_v3` do Plenario da Camara junto de execucoes anteriores que cobrem
  outros periodos.
- Quando houver varias execucoes brutas com a mesma unidade textual, o arquivo
  mais novo no sistema de arquivos deve ser lido primeiro e ganhar a deduplicacao.
- Duplicatas ignoradas devem aparecer no manifest como `duplicate_texto_id`.
- Quando for necessario restringir a entrada, o normalizador deve aceitar uma
  lista opcional de `raw_run_ids`.

## Amostras locais

Depois de consolidar `processed`, o Colab deve produzir ZIPs por base para
facilitar o download local. Cada ZIP deve conter os JSONLs da base
correspondente, separados por ano e mes, e pode conter tambem o Parquet
unificado dessa mesma base quando ele ja tiver sido gerado no Colab.

Diretorio local padrao para descompactar os ZIPs:

```text
data/samples/textos_parlamentares/v1/
```

A amostragem analitica deve preservar aproximadamente 1% de cada ano e de cada
familia textual:

- discursos/pronunciamentos de plenario;
- notas taquigraficas de reunioes ou eventos;
- pareceres e documentos equivalentes de PEC.

A amostra deve preservar o schema v1 e ser pequena o suficiente para cadernos
locais de exemplo.

Depois de descompactadas, as amostras locais devem poder gerar seus proprios
Parquets sem depender do caminho do Google Drive:

```text
data/samples/textos_parlamentares/v1/parquet/
```

## Parquet por base

Cada base canonica deve ter um unico arquivo Parquet por ambiente, agrupando
todos os anos e meses disponiveis naquele ambiente:

- `senado__plenario_discursos.parquet`;
- `senado__congresso_discursos.parquet`;
- `senado__ccj_notas.parquet`;
- `senado__pareceres_pec.parquet`;
- `camara__plenario_discursos.parquet`;
- `camara__ccjc_eventos.parquet`;
- `camara__pareceres_pec.parquet`.

Regras obrigatorias:

- O conteudo de cada Parquet deve ser equivalente ao subconjunto JSONL em que
  `source` e `dataset` correspondem ao nome do arquivo.
- Os Parquets devem manter o contrato `textos_parlamentares/v1`, sem renomear
  campos nem descartar colunas do schema processado.
- Colunas ausentes em alguma base devem existir no Parquet com valores nulos,
  preservando compatibilidade entre bases.
- A ordem preferencial das colunas deve seguir
  `processed_textos_parlamentares_v1.schema.json` quando esse arquivo existir,
  ou a lista `PROCESSED_FIELDS` do normalizador.
- A rotina deve registrar um manifest de Parquet com raiz de entrada, raiz de
  saida, arquivos lidos, arquivos escritos, contagens por base e schema usado.

## Exploracao dos Parquets

Os cadernos exploratorios devem ajudar a aprender a base e inspecionar o texto
integral sem rerodar coletas, normalizacao ou geracao de Parquets.

Requisitos minimos:

- Permitir selecionar uma base Parquet por nome de arquivo, por exemplo
  `camara__plenario_discursos.parquet` ou `senado__pareceres_pec.parquet`.
- Carregar a base selecionada em um `DataFrame` com `pandas`, mantendo uma
  opcao de limite de linhas para leituras exploratorias de bases grandes.
- Expor blocos didaticos com:
  - `df.shape`;
  - `df.head()`;
  - `df.info()`;
  - `df.describe(include="all")` ou equivalente apropriado para colunas
    textuais e categoricas;
  - contagem de nulos por coluna;
  - `value_counts()` para campos-chave como `source`, `dataset`,
    `documento_tipo`, `unidade_analitica`, `ano`, `mes`, `ambito`,
    `orgao_sigla`, `parlamentar_partido`, `parlamentar_uf`,
    `documento_classe`, `status_deliberativo` e `texto_status`, quando
    existirem.
- Usar o melhor visualizador interativo disponivel no ambiente para tabelas,
  preferencialmente `itables` no Colab/Jupyter, com fallback claro para
  visualizacao padrao do pandas.
- Oferecer filtros simples antes da leitura detalhada do texto: ano, mes,
  documento_tipo, parlamentar_nome, proposicao_identificacao, orgao_sigla e
  busca textual por palavra ou expressao.
- Permitir selecionar e exibir `texto` integral por `texto_id` ou indice do
  `DataFrame`, sem truncamento, em bloco legivel com metadados essenciais
  (`source`, `dataset`, `data`, `documento_tipo`, `titulo`,
  `parlamentar_nome`, `proposicao_identificacao`, `url_texto` e `raw_path`).
- Manter uma visualizacao compacta separada para tabelas, evitando que o texto
  integral torne `head()` e tabelas interativas pesadas ou ilegíveis.
- Explicar em celulas curtas o que cada comando basico mostra, sem transformar
  o caderno em tutorial longo.
