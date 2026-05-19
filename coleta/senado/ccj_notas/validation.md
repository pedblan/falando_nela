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

## Smoke test de complementacao

```bash
python -m coleta.senado.ccj_notas.collect \
  --mode dev \
  --no-sample \
  --data-inicio 2023-03-29 \
  --data-fim 2023-03-29 \
  --sample-limit 1 \
  --run-id smoke-senado-ccj-complemento-11176
```

Esse smoke deve cobrir a reuniao `11176`: `/comissao/reuniao/notas/11176.json` retorna `IndicadorNotasTaquigraficas=N`, mas `/taquigrafia/notas/reuniao/11176.json` e a pagina publica `/notas/r/11176` entregam texto.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

O notebook pronto para esse fluxo fica em `notebooks/coleta/coleta_senado_ccj.ipynb`. Ele segue o mesmo padrao do caderno de Plenario: monta o Drive, atualiza o repo, instala dependencias, roda uma validacao curta e deixa a coleta completa em uma celula retomavel com `--resume`.

O notebook especifico da complementacao fica em `notebooks/coleta/coleta_senado_ccj_complemento.ipynb`. A validacao curta roda sem `--resume`; o backfill completo usa `run_id` separado, janela ate `2024-12-31` e `--resume`.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.ccj_notas.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-ccj-complemento-ate-2024",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2024-12-31",
], check=False)
```

## Criterios

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- A agenda mensal e sempre preservada em `metadata/{run_id}.jsonl`.
- Reunioes CCJ geram registros `reuniao_detalhe` e `notas_taquigraficas_metadata` em `metadata/{run_id}.jsonl`.
- `notas_taquigraficas_metadata` preserva a resposta de `/dadosabertos/comissao/reuniao/notas/{codigoReuniao}`.
- Quando o corpus nao e criado por ausencia textual, `metadata/{run_id}.jsonl` contem `notas_taquigraficas_status` com `motivo` e `tentativas_texto`.
- Quando `IndicadorNotasTaquigraficas=S`, a reuniao gera `notas_taquigraficas` na particao mensal.
- Quando `IndicadorNotasTaquigraficas=N`, o coletor ainda deve tentar `/dadosabertos/taquigrafia/notas/reuniao/{codigoReuniao}.json` para reunioes ate `2024-12-31`.
- Se o endpoint textual entregar texto apesar do indicador `N`, a reuniao deve gerar `notas_taquigraficas` com `metodo_obtencao=api_taquigrafia_notas_reuniao_forcado`.
- Se a API textual falhar, a pagina HTML publica `/web/atividade/notas-taquigraficas/-/notas/r/{codigoReuniao}` deve ser tentada como fallback.
- Quando nenhuma fonte textual entregar texto, a ausencia fica preservada em `notas_taquigraficas_status` e no log, sem criar texto inventado no corpus mensal.
- Cada `notas_taquigraficas` contem `CodigoReuniao`, `TextoIntegral`, `texto`, `metodo_obtencao`, `texto_status`, `metadata` e `fontes`.
- Quando `texto_status=disponivel`, `TextoIntegral` e `texto` contem o texto retornado nas notas taquigraficas, nao apenas links ou pauta.
- A reuniao `11176` deve gerar `notas_taquigraficas` em `ano=2023/mes=03/{run_id}.jsonl`, mesmo com metadado de notas indicando `N`.
- Para analise textual, `notas_taquigraficas` ou texto integral da reuniao tem prioridade sobre agenda, pauta e detalhe.
- Pode rodar em paralelo com `camara/plenario_discursos` e `camara/ccjc_eventos` quando os `run_id`s forem distintos.
- Falhas de detalhe ou notas aparecem em log estruturado.
- O checkpoint so marca a particao apos processar a agenda e as reunioes encontradas.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular particoes/registros de corpus/status ja gravados desse `run_id`, sem pular particoes concluidas por outro `run_id`.
