# Validation: pareceres de PEC na Camara

## Smoke test

```bash
python -m coleta.camara.pareceres_pec.collect \
  --mode dev \
  --sample-limit 2 \
  --run-id smoke-camara-pareceres-pec
```

## Criterios de aceite

- A execucao gera manifest, log, checkpoint e pelo menos registros de `metadata`.
- Quando houver tramitacao de parecer em `PLEN`, `CCJC` ou `CCJR`, a execucao gera registros `record_type=parecer_pec_texto`.
- Cada registro textual preserva `metadata.proposicao`, `metadata.detalhe`, `metadata.tramitacao`, `fontes`, `documento.sha256` e `TextoIntegralUrl`.
- `TextoIntegral` e `texto` devem conter o texto extraido, nunca apenas a URL do documento.
- `colegiado.ambito` deve ser `ccj` ou `plenario`.
- Documentos diferentes da mesma PEC devem permanecer como linhas diferentes.

## Checks manuais

- Conferir se `TextoIntegralUrl` abre documento oficial da Camara.
- Conferir se `documento.url_final` reflete eventual meta-refresh para `imagem.camara.gov.br`.
- Conferir se `texto_status=disponivel` implica `texto` nao vazio.
- Conferir se `texto_status=ausente` ou `erro` preserva `erro` ou `tentativas_texto` suficientes para depuracao.

## Colab

Depois da celula de montagem do Drive:

```python
import json
import os
import subprocess
from pathlib import Path

run_id = "smoke-camara-pareceres-pec"
subprocess.run([
    "python", "-m", "coleta.camara.pareceres_pec.collect",
    "--mode", "prod",
    "--sample",
    "--sample-limit", "2",
    "--resume",
    "--run-id", run_id,
], check=True)

manifest = Path(os.environ["FALANDO_NELA_DATA_ROOT"]) / "manifests" / f"{run_id}.json"
print(json.dumps(json.loads(manifest.read_text()), indent=2, ensure_ascii=False))
```

## Lacunas esperadas

- PDFs digitalizados podem nao produzir texto com `pypdf`; nesses casos, manter `forma=documento` e planejar OCR em etapa futura.
- A API pode registrar pareceres em tramitacoes antigas com links HTML intermediarios; o coletor segue um meta-refresh, mas nao faz scraping fora de URLs oficiais.
- O coletor nao decide qual parecer e final ou substitutivo; essa decisao deve ficar para processamento posterior.
