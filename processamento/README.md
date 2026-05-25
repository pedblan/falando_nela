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
