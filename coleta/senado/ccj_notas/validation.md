# Validation: notas taquigraficas da CCJ do Senado

## Smoke test

```bash
python -m coleta.senado.ccj_notas.collect \
  --mode dev \
  --no-sample \
  --data-inicio 2026-05-01 \
  --data-fim 2026-05-18 \
  --sample-limit 1 \
  --run-id smoke-senado-ccj
```

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

O notebook pronto para esse fluxo fica em `notebooks/coleta/coleta_senado_ccj.ipynb`. Ele segue o mesmo padrao do caderno de Plenario: monta o Drive, atualiza o repo, instala dependencias, roda uma validacao curta e deixa a coleta completa em uma celula retomavel com `--resume`.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.ccj_notas.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-ccj",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=False)
```

## Criterios

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- A agenda mensal e sempre preservada em `metadata/{run_id}.jsonl`.
- Reunioes CCJ geram registros `reuniao_detalhe` e `notas_taquigraficas_metadata` em `metadata/{run_id}.jsonl`.
- `notas_taquigraficas_metadata` preserva a resposta de `/dadosabertos/comissao/reuniao/notas/{codigoReuniao}`.
- Quando `IndicadorNotasTaquigraficas=S`, a reuniao gera `notas_taquigraficas` na particao mensal.
- Quando `IndicadorNotasTaquigraficas=N`, a ausencia fica preservada no metadado e nao deve criar texto inventado no corpus mensal.
- Cada `notas_taquigraficas` contem `CodigoReuniao`, `TextoIntegral`, `texto`, `metodo_obtencao`, `texto_status`, `metadata` e `fontes`.
- Quando `texto_status=disponivel`, `TextoIntegral` e `texto` contem o texto retornado nas notas taquigraficas, nao apenas links ou pauta.
- Para analise textual, `notas_taquigraficas` ou texto integral da reuniao tem prioridade sobre agenda, pauta e detalhe.
- Falhas de detalhe ou notas aparecem em log estruturado.
- O checkpoint so marca a particao apos processar a agenda e as reunioes encontradas.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular registros ja gravados.
