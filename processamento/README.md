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

## Amostras locais

Os ZIPs gerados no Colab devem ser descompactados localmente em:

```text
data/samples/textos_parlamentares/v1/
```

Esse diretorio e reservado para os JSONLs pequenos usados em cadernos locais de
exemplo.
