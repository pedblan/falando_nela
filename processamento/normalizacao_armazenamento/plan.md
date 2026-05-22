# Plan

## Etapa 1: contrato processed v1

- Definir o dataset `textos_parlamentares/v1`.
- Registrar schema versionado em `data/schemas/processed_textos_parlamentares_v1.schema.json`.
- Registrar dicionario de dados em
  `data/schemas/processed_textos_parlamentares_v1.dictionary.md`.
- Manter JSONL particionado por `ano` e `mes` como formato inicial, sem
  adicionar dependencia pesada.

## Etapa 2: normalizador

- Implementar CLI em `python -m processamento.normalizacao`.
- Ler o diretorio `raw/` inteiro ou um subconjunto informado por `--dataset`.
- Normalizar os record types textuais:
  - `pronunciamento_texto`;
  - `discursos_page`;
  - `notas_taquigraficas`;
  - `parecer_pec_texto`.
- Usar metadados de deputados da Camara apenas para enriquecer registros de
  discursos.
- Escrever manifest de execucao em `processed/manifests/`.

## Etapa 3: validacao local

- Testar normalizadores por fonte com registros sinteticos.
- Rodar um smoke em `data/dev`.
- Confirmar que a saida particionada e o manifest sao gerados.
- Confirmar que reexecucoes duplicadas nao inflam a saida.

## Etapa 4: execucao no Drive

- Usar o notebook operacional:

```text
notebooks/processamento/normalizacao_armazenamento_colab.ipynb
```

- O notebook monta o Drive, atualiza o repositorio, instala dependencias e
  chama `normalize_data_root(...)` diretamente em Python.
- Usar `PROCESSED_RUN_ID` para nomear a execucao processada. Esse identificador
  nao precisa coincidir com os `run_id`s brutos.
- Deixar `RAW_RUN_IDS = []` para consolidar todos os JSONLs em `raw/` com
  deduplicacao por `texto_id`. Preencher `RAW_RUN_IDS` apenas se for necessario
  restringir explicitamente quais execucoes brutas entram.
- Alternativamente, em ambientes com terminal, rodar:

```bash
export FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data
python -m processamento.normalizacao --mode prod --run-id processed-textos-v1-YYYYMMDD
```

- Revisar o manifest gerado no Drive.
- Se necessario, repetir com `--dataset fonte/dataset` para isolar problemas.

## Etapa 5: descricao analitica das bases

- Usar o notebook:

```text
notebooks/processamento/descricao_analitica_bases_colab.ipynb
```

- Produzir uma leitura resumida por fonte/dataset/familia textual.
- Conferir cobertura temporal, quantidade de registros, tamanho medio de texto,
  preenchimento de campos-chave e exemplos compactos por base.
- Usar essa descricao para decidir prioridades dos cadernos analiticos e da
  amostragem local.

## Etapa 6: amostras locais

- Criar, depois da validacao de `processed`, uma rotina separada para ZIPs de
  amostras por base.
- Critério inicial: 1% por ano e por familia textual, com minimo operacional a
  definir para anos muito pequenos.
- No Colab, gravar ZIPs em
  `/content/drive/MyDrive/falando_nela/data/processed/downloads/{run_id}/`.
- Depois do download, descompactar localmente em:

```text
data/samples/textos_parlamentares/v1/
```

- Manter os nomes dos JSONLs com base, ano e mes para evitar colisao quando
  varios ZIPs forem descompactados no mesmo diretorio.

## Etapa 7: Parquets unificados por base

- Implementar uma rotina separada da normalizacao principal para converter os
  JSONLs normalizados em Parquet por `source/dataset`.
- A rotina deve aceitar raizes explicitas para entrada e saida, porque os
  arquivos completos no Colab e as amostras locais ficam em diretorios
  diferentes.
- Perfil Colab:

```text
entrada: /content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/
saida:   /content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Perfil samples locais:

```text
entrada: data/samples/textos_parlamentares/v1/
saida:   data/samples/textos_parlamentares/v1/parquet/
```

- Gerar um arquivo por base:
  - `senado__plenario_discursos.parquet`;
  - `senado__congresso_discursos.parquet`;
  - `senado__ccj_notas.parquet`;
  - `senado__pareceres_pec.parquet`;
  - `camara__plenario_discursos.parquet`;
  - `camara__ccjc_eventos.parquet`;
  - `camara__pareceres_pec.parquet`.
- Ler todos os JSONLs abaixo da raiz de entrada, ignorando subdiretorios
  `parquet/`, manifests e arquivos que nao sejam registros processados v1.
- Deduplicar por `texto_id` antes de escrever Parquet, mantendo a mesma
  politica de preferencia do normalizador quando houver duplicatas nos JSONLs.
- Escrever um manifest de conversao em:
  - Colab: `processed/manifests/{run_id}-parquet.json`;
  - samples locais: `data/samples/textos_parlamentares/v1/parquet/manifest.json`.
- Criar e manter o notebook `geracao_parquets_colab.ipynb` para gerar os
  Parquets no Drive sem rerodar ou reabrir notebooks de normalizacao ja
  executados.
- Atualizar o fluxo local para permitir regerar os Parquets a partir dos JSONLs
  descompactados em `data/samples/textos_parlamentares/v1/`.

## Etapa 8: exploracao didatica dos Parquets

- Criar um caderno Colab independente:

```text
notebooks/processamento/exploracao_parquets_colab.ipynb
```

- Criar um caderno local para samples:

```text
notebooks/processamento/exploracao_parquets_samples_local.ipynb
```

- O caderno Colab deve montar o Drive, atualizar o repositorio, instalar
  dependencias e ler diretamente:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- O caderno local deve ler diretamente:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- Ambos devem permitir escolher a base Parquet antes de carregar o `DataFrame`.
- Ambos devem incluir uma primeira passada de EDA basica:
  - lista de Parquets disponiveis;
  - schema/colunas;
  - `df.shape`;
  - `df.head()`;
  - `df.info()`;
  - `df.describe(include="all")`;
  - contagem de nulos;
  - `value_counts()` para campos categoricos relevantes.
- Ambos devem separar uma visao tabular compacta, sem a coluna `texto`, de uma
  visao de texto integral.
- A visao tabular deve usar `itables` quando disponivel, com fallback para
  `IPython.display.display`.
- A visao de texto integral deve permitir selecionar por `texto_id` ou indice,
  mostrar metadados essenciais e imprimir o campo `texto` completo sem
  truncamento.
- Incluir filtros simples por ano, mes, familia textual, parlamentar,
  proposicao, orgao e busca textual para reduzir o conjunto antes de abrir
  textos completos.
