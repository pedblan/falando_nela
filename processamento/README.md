# Processamento

Ferramentas da fase 3 do roadmap: normalizacao e armazenamento.

## Normalizacao

```bash
python -m processamento.normalizacao --mode dev --run-id smoke-processed-v1 --overwrite
```

No Colab, com o Drive montado:

use `notebooks/processamento/normalizacao_armazenamento_colab.ipynb`.

A saida e gravada em `processed/textos_parlamentares/v1`, com um manifest em
`processed/manifests`.

Para uma descricao analitica das bases processadas, use
`notebooks/processamento/descricao_analitica_bases_colab.ipynb`.

## Apartes parlamentares

`apartes_parlamentares/v1` e uma tabela relacional separada de
`textos_parlamentares/v1`. Ela conta relacoes oficiais
`aparteante -> discurso/pronunciamento` por ano e cruza essas relacoes com
`parlamentares/v1` para atributos como genero, partido e UF.

Quando implementado, o processamento deve ler:

```text
raw/senado/plenario_apartes/metadata/
raw/camara/plenario_apartes/metadata/
processed/parlamentares/v1/
```

e gerar:

```text
processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet
processed/audits/apartes_parlamentares/{run_id}/
```

O texto individual do aparte fica fora do escopo inicial, e genero nunca deve
ser inferido por nome.

## Parquets por base

Depois de existir JSONL processado, gere um Parquet unificado por
`source/dataset`.

Samples locais:

```bash
python -m processamento.parquet --profile samples-local --overwrite
```

Colab/Drive:

```bash
python -m processamento.parquet \
  --profile colab \
  --data-root /content/drive/MyDrive/falando_nela/data \
  --run-id processed-textos-v1-YYYYMMDD \
  --overwrite
```

No perfil Colab, os Parquets ficam em
`/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/`.
No perfil local, ficam em `data/samples/textos_parlamentares/v1/parquet/`.

No Colab, o caminho recomendado para cuidar apenas dos Parquets, sem rerodar
notebooks de normalizacao ja executados, e:

```text
notebooks/processamento/geracao_parquets_colab.ipynb
```

Para exploracao didatica dos Parquets, use:

```text
notebooks/processamento/exploracao_parquets_colab.ipynb
notebooks/processamento/exploracao_parquets_samples_local.ipynb
```

Eles permitem escolher uma base, carregar um `DataFrame`, revisar `head`,
`describe`, `value_counts`, aplicar filtros simples e abrir o `texto` integral
sem truncamento.

Para navegar pelos Parquets em um app web Gradio read-only, use no Colab:

```text
notebooks/processamento/visualizador_parquets_gradio_colab.ipynb
```

Localmente, contra os Parquets de samples:

```bash
python -m processamento.visualizador_parquets --profile samples-local
```

Para gerar arquivos Excel dos Parquets locais de samples:

```bash
python -m processamento.parquet_xlsx --profile samples-local --overwrite
```

A saida padrao fica em `data/samples/textos_parlamentares/v1/xlsx/`, com um
`.xlsx` por Parquet e um `manifest.json`. Para gerar uma previa mais leve:

```bash
python -m processamento.parquet_xlsx --profile samples-local --max-rows 1000 --overwrite
```

## Inventario de separadores

Antes de limpar o campo `texto`, rode o inventario read-only de separadores nos
Parquets. No Colab, use:

```text
notebooks/processamento/inventario_separadores_colab.ipynb
```

Ou, no terminal:

```bash
python -m processamento.inventario_separadores \
  --profile colab \
  --run-id separadores-textos-v1-YYYYMMDD \
  --overwrite
```

O inventario gera relatorios em `processed/audits/separadores/{run_id}/`,
incluindo uma amostra de 0,1% por `source/dataset/ano` para revisao por IA com
resposta estruturada.

## Amostras locais

Os ZIPs de amostra devem ser gerados no Colab a partir da base completa no
Google Drive, nao a partir das amostras locais:

```bash
python -m processamento.samples \
  --profile colab \
  --data-root /content/drive/MyDrive/falando_nela/data \
  --run-id samples-textos-v1-YYYYMMDD \
  --include-parquet \
  --overwrite
```

A saida padrao fica em
`/content/drive/MyDrive/falando_nela/data/processed/downloads/{run_id}/`.
Depois do download, descompacte localmente em:

```text
data/samples/textos_parlamentares/v1/
```

O perfil `samples-local` existe apenas para validacao ou reempacotamento local
controlado; ele nao substitui a geracao analitica a partir dos dados completos
no Colab.

Esse diretorio e reservado para os JSONLs pequenos usados em cadernos locais de
exemplo.
