# Validation: eventos da CCJC da Camara

## Smoke test

```bash
python -m coleta.camara.ccjc_eventos.collect \
  --mode dev \
  --run-id smoke-camara-ccjc-escriba \
  --data-inicio 2026-05-12 \
  --data-fim 2026-05-12 \
  --sample-limit 2
```

O smoke acima usa data conhecida em que a API da CCJC lista o evento `81996`, cujo HTML do Escriba deve estar disponivel.

O notebook pronto para esse fluxo fica em `notebooks/coleta/coleta_camara_ccjc.ipynb`. Ele monta o Drive, atualiza o repo, instala dependencias, roda a validacao curta em `2026-05-12` e deixa a coleta completa protegida por uma flag.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.ccjc_eventos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-camara-ccjc",
    "--data-inicio", "2019-01-01",
    "--data-fim", "2026-05-18",
], check=False)
```

## Criterios

- Gera paginas de eventos da CCJC.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Para cada evento encontrado, tenta gerar detalhe e participantes.
- Para eventos no escopo `2019+`, tenta obter o HTML do Escriba por `https://escriba.camara.leg.br/escriba-servicosweb/html/{id}`.
- Eventos, detalhes, participantes, status Escriba e HTML bruto disponivel ficam em `metadata/{run_id}.jsonl`.
- Quando o Escriba responde `200` com nota valida, a particao mensal deve conter `record_type=notas_taquigraficas`, `metodo_obtencao=scraping_escriba_html`, `texto_status=disponivel` e `texto` preenchido.
- Quando o Escriba responde `404`, o status deve ficar documentado em metadata e nao deve quebrar a execucao.
- Paginacao segue links `rel=next`.
- Registros preservam periodo, request, response, payload e checksum.
- Fontes preservam URL HTML do Escriba, URL PDF quando houver, audio, video e `urlRegistro`.
- Para anos anteriores a 2019, a coleta preserva metadados e documenta lacunas sem gerar corpus textual.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular registros de API, status Escriba, HTML bruto e corpus ja gravados.
