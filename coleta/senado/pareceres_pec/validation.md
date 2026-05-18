# Validation: pareceres de PEC no Senado

## Smoke test

```bash
python -m coleta.senado.pareceres_pec.collect \
  --mode dev \
  --sample-limit 2 \
  --run-id smoke-senado-pareceres-pec
```

## Criterios de aceite

- A execucao gera manifest, log, checkpoint e pelo menos registros de `metadata`.
- Quando houver parecer/relatorio em `CCJ` ou `PLEN`, a execucao gera registros `record_type=parecer_pec_texto`.
- Cada registro textual preserva `metadata.processo`, `metadata.documento`, `fontes`, `documento.sha256` e `TextoIntegralUrl`.
- `TextoIntegral` e `texto` devem conter o texto extraido, nunca apenas a URL do documento.
- `colegiado.ambito` deve ser `ccj` ou `plenario`.
- Documentos diferentes da mesma PEC devem permanecer como linhas diferentes.

## Checks manuais

- Conferir se `TextoIntegralUrl` abre documento oficial do Senado.
- Conferir se `documento.url_final` corresponde ao documento baixado.
- Conferir se `texto_status=disponivel` implica `texto` nao vazio.
- Conferir se `texto_status=ausente` ou `erro` preserva `erro` ou `tentativas_texto` suficientes para depuracao.

## Colab

Depois da celula de montagem do Drive:

```python
import json
import os
import subprocess
from pathlib import Path

run_id = "smoke-senado-pareceres-pec"
subprocess.run([
    "python", "-m", "coleta.senado.pareceres_pec.collect",
    "--mode", "prod",
    "--sample",
    "--sample-limit", "2",
    "--resume",
    "--run-id", run_id,
], check=False)

manifest = Path(os.environ["FALANDO_NELA_DATA_ROOT"]) / "manifests" / f"{run_id}.json"
print(json.dumps(json.loads(manifest.read_text()), indent=2, ensure_ascii=False))
```

## Lacunas esperadas

- PDFs digitalizados podem nao produzir texto com `pypdf`; nesses casos, manter `forma=documento` e planejar OCR em etapa futura.
- O coletor nao decide qual versao do parecer e final; essa decisao deve ficar para processamento posterior.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular registros ja gravados.
