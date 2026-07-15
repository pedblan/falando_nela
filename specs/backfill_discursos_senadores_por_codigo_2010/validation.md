# Validação: backfill de discursos de senadores por código desde 2010

## Testes locais

    PYTHONPATH=. .venv/bin/python -m pytest \
      tests/test_backfill_discursos_senadores_por_codigo.py \
      tests/test_auditoria_discursos_senadores.py \
      tests/test_senator_speech_backfill_colab_notebook.py

Os testes comprovam consulta de texto pelo CodigoPronunciamento, source_id
canônico, preservação de proveniência, retomada sem download duplicado e
rejeição de população divergente. O notebook deve ser JSON válido, compilar
todas as células e permanecer sincronizado com seu gerador.

## Colab

Abrir 08_backfill_discursos_senadores_por_codigo_2010_colab.ipynb na branch que
contém o coletor. Manter todas as flags falsas durante a inspeção. Revisar o
resumo da auditoria e a tabela por casa/ano; então preencher
CONFIRM_BACKFILL_ID com BACKFILL_ID.

1. Ativar somente RODAR_BACKFILL_SF e executar a célula.
2. Desativar SF, ativar somente RODAR_BACKFILL_CN e executar a mesma célula.
3. Desativar os dois backfills, ativar RODAR_AUDITORIA_POS e executar a
   reauditoria.

O aceite exige manifests de SF e CN completed, errors igual a zero, sem
partições falhas e reauditoria strict require-complete exitosa. Antes desse
gate, processados, Parquets e snapshots permanecem proibidos.
