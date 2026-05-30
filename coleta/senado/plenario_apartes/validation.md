# Validation: apartes do Plenario do Senado

## Smoke local

```bash
python -m coleta.senado.plenario_apartes.collect \
  --mode dev \
  --sample-limit 5 \
  --run-id smoke-senado-apartes
```

## Validacao Colab

Assume que a celula base de `coleta/README.md` ja montou o Drive, definiu
`FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.plenario_apartes.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-plenario-apartes-validacao-curta",
    "--data-inicio", "2025-01-01",
    "--data-fim", "2025-12-31",
    "--sample",
    "--sample-limit", "10",
], check=False)
```

Depois da validacao curta, a coleta completa pode remover `--sample-limit`.

## Criterios de aceite

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Todos os registros ficam em `metadata/{run_id}.jsonl`.
- Nao existem particoes mensais `ano=YYYY/mes=MM/` para
  `senado/plenario_apartes`.
- O checkpoint usa particoes anuais, como `2025`, mesmo quando o raw fica em
  `metadata/`.
- O preflight anual tem `record_type=senador_apartes_year_probe`.
- O preflight trimestral tem `record_type=senador_apartes_quarter_probe`.
- Janelas mensais expandidas em trimestres positivos tem
  `record_type=senador_apartes_metadata`.
- Cada `source_id` e deterministico por senador e periodo.
- `Apartes=null` e preservado quando a fonte retornar ausencia de apartes.
- `Aparte` objeto unico e `Aparte` lista sao preservados de forma parseavel no
  payload.
- Uma segunda execucao com `--resume` nao duplica requisicoes ja gravadas.
- Se uma interrupcao ou latencia do Drive deixar linha JSONL parcial, novas
  gravacoes devem comecar em nova linha e as celulas de inspecao devem reportar
  a linha invalida sem derrubar a verificacao do manifest/raw restante.

## Fixtures esperadas

- Payload com `Apartes=null`.
- Payload com `Apartes.Aparte` como objeto unico.
- Payload com `Apartes.Aparte` como lista.
- Payload com `Orador` ausente ou incompleto.
- Resposta com `429` e `Retry-After`, simulada em teste de cliente.

## Falhas que bloqueiam aceite

- Gravar qualquer registro em `ano=YYYY/mes=MM/`.
- Inferir genero, partido ou UF no coletor.
- Descartar respostas `Apartes=null`.
- Usar resumo, indexacao ou URL como substituto de texto de aparte.
- Execucao `prod` gravando dentro do repositorio local.

## Checks manuais recomendados

```bash
wc -l data/dev/raw/senado/plenario_apartes/metadata/{run_id}.jsonl
```

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("data/dev/raw/senado/plenario_apartes/metadata/{run_id}.jsonl")
for line in path.read_text(encoding="utf-8").splitlines()[:5]:
    record = json.loads(line)
    print(record["record_type"], record["source_id"], record["partition"])
PY
```
