# Validation: auditoria de cobertura de discursos de senadores desde 2010

## Testes locais

    PYTHONPATH=. .venv/bin/python -m pytest \
      tests/test_auditoria_discursos_senadores.py \
      tests/test_senator_speech_audit_colab_notebook.py \
      tests/test_discursos_historicos.py

Os testes devem comprovar extração de CodigoPronunciamento, consulta por
CodigoParlamentar mesmo com diacríticos no nome, exclusão de metadata e
transcription_queue do raw, detecção de IDs ausentes, ano inconclusivo após
erro e retomada pela última resposta válida.

## Execução no Colab

Abrir 07_auditoria_cobertura_discursos_senadores_2010_colab.ipynb, manter as
flags desativadas até revisar o AUDIT_ID e, em seguida, definir
RODAR_AUDITORIA = True e CONFIRM_AUDIT_ID = AUDIT_ID.

O aceite exige errors=0, invalid_probe_lines=0, invalid_raw_lines=0 e
source_conflicts=0. IDs ausentes não são erro de execução: são a população da
recuperação posterior. Não executar derivados enquanto houver linhas no
arquivo senator_endpoint_missing_ids.jsonl.
