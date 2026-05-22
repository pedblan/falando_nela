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
- Manter o dicionario de dados em
  `data/schemas/processed_textos_parlamentares_v1.dictionary.md`.
- Manter `dataset_version = "v1"` em cada registro processado.
- Preservar ponte para a origem por `raw_path`, `raw_run_id`,
  `raw_source_id`, `raw_record_type`, `raw_checksum` e `raw_response_url`.

## Cadernos operacionais

- Manter `notebooks/processamento/normalizacao_armazenamento_colab.ipynb`
  como caminho recomendado para executar a normalizacao no Colab sem depender
  de terminal separado.
- Manter `notebooks/processamento/descricao_analitica_bases_colab.ipynb`
  para descrever cada base processada por fonte, dataset, ano, familia textual,
  tamanho de texto, cobertura temporal e preenchimento de campos.
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
facilitar o download local. Cada ZIP deve conter JSONLs da base correspondente,
separados por ano e mes.

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
