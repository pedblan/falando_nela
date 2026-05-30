# Validation: apartes do Plenario da Camara

## Smoke local

```bash
python -m coleta.camara.plenario_apartes.collect \
  --mode dev \
  --sample-limit 5 \
  --run-id smoke-camara-apartes
```

## Validacao Colab

Assume que a celula base de `coleta/README.md` ja montou o Drive, definiu
`FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.plenario_apartes.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-camara-plenario-apartes-validacao-curta",
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
- Quando `processed/parlamentares/v1` existir, o log da particao registra
  `planejamento=parlamentares_periodos` e as consultas por nome ficam limitadas
  aos deputados com mandato oficial que intercepta a janela.
- Quando `processed/parlamentares/v1` nao existir, o coletor usa o fallback
  oficial `/api/v2/deputados`.
- Todos os registros ficam em `metadata/{run_id}.jsonl`.
- Nao existem particoes mensais `ano=YYYY/mes=MM/` para
  `camara/plenario_apartes`.
- O checkpoint usa particoes anuais, como `2025`, mesmo quando o raw fica em
  `metadata/`.
- O preflight anual tem `record_type=sitaq_apartes_year_probe`.
- O preflight trimestral tem `record_type=sitaq_apartes_quarter_probe`.
- Janelas mensais expandidas em trimestres positivos ou inconclusivos tem
  `record_type=sitaq_apartes_search_page`.
- Cada `source_id` e deterministico por aparteante, periodo e pagina.
- O HTML bruto da pagina oficial e preservado.
- Paginas com zero resultados sao preservadas.
- Uma segunda execucao com `--resume` nao duplica paginas ja gravadas.
- Se houver uma linha JSONL parcial deixada por interrupcao anterior, a retomada
  deve preservar a linha invalida isolada e gravar novos registros em linhas
  JSON validas.

## Fixtures esperadas

- HTML com zero resultados.
- HTML com uma pagina e um resultado.
- HTML com uma pagina e varios resultados.
- HTML com multiplas paginas.
- HTML com link `TextoHTML.asp` completo.
- HTML com resultado sem link parseavel, preservado como pagina bruta.

## Falhas que bloqueiam aceite

- Gravar qualquer registro em `ano=YYYY/mes=MM/`.
- Inferir genero, partido ou UF no coletor.
- Descartar HTML quando o parser falhar.
- Tratar a API REST `/api/v2/deputados/{id}/discursos` como fonte de
  aparteante.
- Execucao `prod` gravando dentro do repositorio local.

## Checks manuais recomendados

```bash
wc -l data/dev/raw/camara/plenario_apartes/metadata/{run_id}.jsonl
```

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("data/dev/raw/camara/plenario_apartes/metadata/{run_id}.jsonl")
for line in path.read_text(encoding="utf-8").splitlines()[:5]:
    record = json.loads(line)
    payload = record["payload"]
    print(record["record_type"], record["source_id"], payload.get("aparteante_consultado"))
PY
```
