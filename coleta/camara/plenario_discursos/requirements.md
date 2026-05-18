# Requirements: discursos da Camara por deputado

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint.
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

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de deputado ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
