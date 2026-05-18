# Validation: eventos da CCJC da Camara

## Smoke test

```bash
python -m coleta.camara.ccjc_eventos.collect --mode dev --run-id smoke-camara-ccjc
```

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.ccjc_eventos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-camara-ccjc",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```

## Criterios

- Gera paginas de eventos da CCJC.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Para cada evento encontrado, tenta gerar detalhe e participantes.
- Eventos, detalhes e participantes ficam em `metadata/{run_id}.jsonl`, nao na particao mensal do corpus textual.
- Paginacao segue links `rel=next`.
- Registros preservam periodo, request, response, payload e checksum.
- Texto integral/notas da reuniao, quando existirem em fonte oficial, tem prioridade sobre metadados de evento.
- Lacunas de transcricao de reuniao ficam documentadas na spec e nao quebram a coleta.
