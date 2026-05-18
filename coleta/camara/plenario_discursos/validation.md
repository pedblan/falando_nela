# Validation: discursos da Camara por deputado

## Smoke test

```bash
python -m coleta.camara.plenario_discursos.collect --mode dev --run-id smoke-camara-discursos
```

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.plenario_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-camara-plenario",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```

## Criterios

- Gera registros de metadados de deputados.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Metadados de deputados ficam em `metadata/{run_id}.jsonl`.
- Gera paginas de discursos para a particao de amostra em `ano=YYYY/mes=MM/{run_id}.jsonl`.
- Paginacao segue links `rel=next`.
- Registros preservam id do deputado, periodo, request, response, payload e checksum.
- Quando `transcricao` estiver presente, ela e o texto prioritario para analise; `sumario` e `keywords` sao apenas metadados.
- Uma segunda execucao com `--resume` pula particoes concluidas.
