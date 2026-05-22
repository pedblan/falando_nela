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
