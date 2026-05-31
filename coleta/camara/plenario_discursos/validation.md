# Validation: discursos da Camara por deputado

## Smoke Test

```bash
python -m coleta.camara.plenario_discursos.collect \
  --mode dev \
  --run-id smoke-camara-discursos
```

Para smoke local com `run_id` reutilizado, apague os arquivos de `data/dev`
desse `run_id` ou use um novo identificador.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu
`FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

O caderno pronto para este fluxo fica em:

```text
notebooks/coleta/coleta_camara_plenario.ipynb
```

No backfill historico geral, use:

```bash
python -m coleta.camara.plenario_discursos.collect \
  --mode prod \
  --resume \
  --run-id prod-historico-camara-plenario \
  --data-inicio 1946-01-01 \
  --data-fim 2026-05-28 \
  --no-sample
```

## Testes Automatizados

```bash
pytest tests/test_camara_plenario.py -q
```

Os testes devem cobrir:

- carregamento de `parlamentares_periodos` e filtragem de mandatos por janela;
- paginacao de deputados por intervalo anual;
- escrita de `deputados_page` em `metadata/`;
- probe anual vazio sem abertura de meses;
- probe anual/trimestral positivo abrindo meses;
- fallback do probe para consulta sem ordenacao quando a API retorna 500;
- fallback mensal para paginacao `itens=1` quando a pagina ordenada e a pagina
  sem ordenacao retornam 500;
- registro `discursos_page_error` em `metadata/` para paginas persistentes que
  continuam quebrando mesmo com `itens=1`;
- preservacao de `transcricao` em paginas mensais;
- escrita mensal exclusivamente em `ano=YYYY/mes=MM/`.

## Criterios

- Gera registros de metadados de deputados.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Metadados de deputados e probes ficam em `metadata/{run_id}.jsonl`.
- Quando `processed/parlamentares/v1` existir, o manifest registra
  `deputados_periodos_carregados > 0` e o log da particao mostra
  `planejamento=parlamentares_periodos`.
- Quando `processed/parlamentares/v1` nao existir, o coletor cai no fallback
  oficial `api_deputados_periodo`.
- `discursos_year_probe` e `discursos_quarter_probe` nunca aparecem em
  `ano=YYYY/mes=MM/`.
- `discursos_page` e gravado apenas para requisicoes mensais.
- `discursos_page_error` aparece somente em `metadata/` e nao bloqueia a
  gravacao de outras paginas recuperaveis do mesmo mes.
- Paginacao mensal segue links `rel=next`.
- Quando o fallback `itens=1` for acionado, paginas recuperadas podem aparecer
  com indices nao contiguos se uma pagina intermediaria persistir com 500; a
  lacuna deve estar registrada no erro correspondente em `metadata/`.
- Registros preservam id do deputado, periodo, request, response, payload e
  checksum.
- Quando `transcricao` estiver presente, ela e o texto prioritario para
  analise; `sumario` e `keywords` sao apenas metadados.
- Uma segunda execucao com o mesmo `--run-id --resume` pula particoes
  concluidas desse `run_id`.
- Pode rodar em paralelo com a complementacao `senado/ccj_notas` e com
  `camara/ccjc_eventos` quando os `run_id`s forem distintos.

## Validacao De Resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a
  execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da
  execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de
  particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular
  particoes/registros ja gravados desse `run_id`, sem pular particoes
  concluidas por outro `run_id`.

## Checks Manuais

```bash
python - <<'PY'
import json
from pathlib import Path

run_id = "prod-historico-camara-plenario"
root = Path("/content/drive/MyDrive/falando_nela/data/raw/camara/plenario_discursos")
metadata = root / "metadata" / f"{run_id}.jsonl"
counts = {}
for line in metadata.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    record = json.loads(line)
    counts[record["record_type"]] = counts.get(record["record_type"], 0) + 1
print(counts)
for path in root.glob(f"ano=*/mes=*/{run_id}.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines()[:10]:
        record = json.loads(line)
        assert record["record_type"] == "discursos_page", path
PY
```
