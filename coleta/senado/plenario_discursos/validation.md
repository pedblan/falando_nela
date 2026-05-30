# Validation: discursos do Plenario do Senado

## Smoke Local

```bash
python -m coleta.senado.plenario_discursos.collect \
  --mode dev \
  --sample-limit 5 \
  --run-id smoke-senado-texto
```

Para um smoke mais facil de auditar:

```bash
python -m coleta.senado.plenario_discursos.collect \
  --mode dev \
  --sample-limit 2 \
  --run-id smoke-senado-texto-2
```

## Validacao Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

O notebook pronto para esse fluxo fica em `notebooks/coleta/coleta_senado_plenario.ipynb`. A primeira celula executavel monta o Drive; as celulas seguintes configuram `FALANDO_NELA_DATA_ROOT`, clonam ou atualizam o repo, instalam dependencias, rodam uma validacao curta e deixam a coleta completa protegida por uma flag.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.plenario_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-plenario-validacao-curta",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2011-05-31",
    "--sample-limit", "10",
], check=False)
```

Depois da validacao curta, a coleta completa pode remover `--sample-limit`:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.plenario_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-plenario",
    "--data-inicio", "1995-02-01",
    "--data-fim", "2026-05-18",
], check=False)
```

## Criterios de Aceite

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- `metadata/{run_id}.jsonl` contem a lista mensal como `record_type=discursos_periodo_metadata`.
- O backfill operacional usa `1995-02-01` como inicio para evitar varrer meses
  anteriores sem cobertura no endpoint.
- A coleta continua mensal; nao deve depender de preflight anual/trimestral no
  endpoint de lista do Senado.
- `ano=YYYY/mes=MM/{run_id}.jsonl` contem apenas `record_type=pronunciamento_texto`.
- `discursos_periodo_metadata` nao aparece em particao mensal do corpus textual.
- Cada `pronunciamento_texto` contem `CodigoPronunciamento`, `TextoIntegral`, `TextoIntegralUrl`, `texto`, `forma`, `metodo_obtencao`, `texto_status`, `metadata` e `fontes`.
- Quando `metodo_obtencao=api_texto_integral`, `TextoIntegral` e `texto` sao strings nao vazias e nao sao URLs.
- Quando `metodo_obtencao=api_notas_sessao`, `tentativas_texto` registra a falha ou ausencia do texto por pronunciamento.
- Quando `metodo_obtencao=pendente_transcricao_video`, `TextoIntegral` e `texto` sao `null`, `forma=video`, e o caso entra em `transcription_queue` se houver fonte candidata.
- Analises futuras devem usar `payload.TextoIntegral` ou `payload.texto`, nunca `metadata.pronunciamento.TextoIntegral`, `Resumo`, `Indexacao` ou apenas metadados.
- O periodo do registro fica dentro dos parametros informados.
- Uma segunda execucao com `--resume` pula particao ja concluida.
- O manifest soma corretamente `record_counts` e `partition_counts`.

## Checks Manuais Recomendados

Inspecionar contagens por arquivo:

```bash
wc -l data/dev/raw/senado/plenario_discursos/metadata/{run_id}.jsonl
wc -l data/dev/raw/senado/plenario_discursos/ano=2011/mes=05/{run_id}.jsonl
```

Inspecionar tipos de registro:

```bash
python - <<'PY'
import json
from pathlib import Path

run_id = "smoke-senado-texto-2"
paths = [
    Path(f"data/dev/raw/senado/plenario_discursos/metadata/{run_id}.jsonl"),
    Path(f"data/dev/raw/senado/plenario_discursos/ano=2011/mes=05/{run_id}.jsonl"),
]

for path in paths:
    print(path)
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        payload = record["payload"]
        print(
            record["record_type"],
            record["partition"],
            payload.get("CodigoPronunciamento"),
            payload.get("metodo_obtencao"),
            bool(payload.get("TextoIntegral")),
        )
PY
```

## Falhas que Devem Bloquear Aceite

- `payload.TextoIntegral` contendo URL em vez do texto retornado pelo endpoint `/dadosabertos/discurso/texto-integral/{codigoPronunciamento}`.
- JSONL mensal contendo a lista bruta `discursos_periodo_metadata`.
- Registro textual sem `CodigoPronunciamento`.
- Registro textual com apenas `Resumo` quando o texto integral oficial esta disponivel.
- Execucao `prod` gravando dentro do repositorio local.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular pronunciamentos ja gravados, sem baixar novamente textos integrais salvos.
