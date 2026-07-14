# Validation: discursos do Plenario do Congresso

## Smoke test

```bash
python -m coleta.senado.congresso_discursos.collect --mode dev --run-id smoke-senado-cn
```

Smoke da recuperação:

```bash
python -m coleta.senado.congresso_discursos.collect \
  --mode dev --data-inicio 2015-01-01 --data-fim 2015-01-31 \
  --discovery-strategy historical-official \
  --run-id smoke-congresso-2015-historical
```

Confirmar `CN` sem itens `SF`, paginação completa, páginas raw em metadata e
paridade em mês-controle. Produção exige 24 partições completas, `errors=0`,
sem amostra e presença das sentinelas `411219` e `426642`.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.congresso_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-congresso",
    "--data-inicio", "1996-05-01",
    "--data-fim", "2026-05-18",
], check=False)
```

## Criterios

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- As listas mensais ficam em `metadata/{run_id}.jsonl`; registros
  `pronunciamento_texto` ficam em `ano=YYYY/mes=MM/{run_id}.jsonl`.
- O backfill operacional usa `1996-05-01` como inicio para evitar varrer meses
  anteriores sem cobertura no endpoint.
- A coleta continua mensal; nao deve depender de preflight anual/trimestral no
  endpoint de lista do Senado.
- Cada item com `CodigoPronunciamento` tenta o endpoint oficial de texto
  integral e, quando necessario, notas da sessao.
- O campo `texto` contem o corpo transferido, nunca a URL de texto integral.
- Casos audiovisuais sem texto aparecem em `transcription_queue` e nao entram
  silenciosamente no corpus analitico.
- O request preserva `siglaCasa=CN`.
- Analises futuras devem usar o texto integral transferido, nao `Resumo` ou apenas metadados de sessao.
- Uma segunda execucao com `--resume` pula a particao concluida.
- O manifest soma corretamente os registros escritos.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular registros ja gravados.
- Falha inesperada de item deixa a particao retomavel; uma execucao posterior
  tenta apenas os pronunciamentos faltantes.
