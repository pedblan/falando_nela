# Cadernos de manutenção — consulta legada

> **Status desde R09:** este notebook é preservado para consulta e não autoriza
> manutenção, movimentação ou exclusão de dados no Drive.

Esta pasta contém operações excepcionais sobre a organização do Drive. Não são
cadernos de coleta, normalização ou análise.

`00_arquivar_pos_coleta_v1_colab.ipynb` preserva `data/raw/` e move todos os
demais filhos de `data/` para um arquivo versionado fora dessa raiz. A operação
gera plano, exige confirmação literal e valida o fingerprint estrutural de
`raw/` antes e depois.
