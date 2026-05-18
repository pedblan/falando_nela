# Validation: notas taquigraficas da CCJ do Senado

## Smoke test

```bash
python -m coleta.senado.ccj_notas.collect --mode dev --run-id smoke-senado-ccj
```

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.ccj_notas.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-ccj",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```

## Criterios

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- A agenda mensal e sempre preservada em `metadata/{run_id}.jsonl`.
- Reunioes CCJ geram registros `reuniao_detalhe` em `metadata/{run_id}.jsonl` e, quando disponivel, `notas_taquigraficas` na particao mensal.
- Para analise textual, `notas_taquigraficas` ou texto integral da reuniao tem prioridade sobre agenda, pauta e detalhe.
- Falhas de detalhe ou notas aparecem em log estruturado.
- O checkpoint so marca a particao apos processar a agenda e as reunioes encontradas.
