# Requirements: discursos da Camara por deputado

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint para o mesmo `run_id`.
- `--run-id`: identificador da execucao.

## Separacao de dados

- Paginas de deputados ficam em `data/raw/camara/plenario_discursos/metadata/{run_id}.jsonl`.
- Paginas de discursos ficam em `data/raw/camara/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`, porque podem conter `transcricao`.

## Campos obrigatorios

- Id do deputado no `source_id`.
- Periodo consultado.
- Pagina de discursos retornada pela API.
- `transcricao` deve ser preservada como texto prioritario quando estiver disponivel.
- URL final, status HTTP, payload e checksum.

## Limites

- O endpoint de discursos e por deputado; a coleta completa faz muitas requisicoes.
- O endpoint pode incluir discursos em eventos diversos; filtros analiticos de Plenario ficam para normalizacao posterior.
- `sumario` e `keywords` nao substituem a transcricao/texto integral.

## Concorrencia operacional

- Pode rodar em paralelo com `senado/ccj_notas` e `camara/ccjc_eventos`, pois usa `raw/camara/plenario_discursos/` e checkpoint proprio.
- O `run_id` deve ser distinto dos outros notebooks ativos, porque logs e manifests sao indexados por `run_id`.
- Nao rode duas instancias de `camara/plenario_discursos` com o mesmo `run_id` ao mesmo tempo.

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de deputado ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas pelo mesmo `run_id` e registros ja presentes no JSONL do mesmo `run_id`.
