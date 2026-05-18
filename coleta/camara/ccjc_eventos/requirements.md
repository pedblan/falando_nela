# Requirements: eventos da CCJC da Camara

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador da execucao.

## Separacao de dados

- Eventos, detalhes e participantes ficam em `data/raw/camara/ccjc_eventos/metadata/{run_id}.jsonl`.
- A particao mensal do corpus fica reservada a notas/transcricoes oficiais quando passarem a estar disponiveis.
- Lacunas sem texto oficial devem ser documentadas sem inventar corpus textual.

## Campos obrigatorios

- Id do orgao `2003` no manifest.
- Id do evento no `source_id`.
- Paginas de eventos, detalhes de eventos e participantes.
- URLs oficiais presentes no payload, incluindo `urlRegistro` quando a API entregar.

## Politica API-only

- A API v2 nao expoe de forma clara a integra taquigrafica por evento de comissao.
- Esta tarefa coleta somente eventos, participantes, metadados e URLs oficiais disponiveis na API.
- Se texto integral/notas da reuniao passarem a estar disponiveis por fonte oficial, eles devem ser transferidos antes de qualquer fallback por video.
- Ausencia de transcricao nao deve ser preenchida por scraping nesta fase; deve virar candidato documentado para transcricao futura.

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de evento ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
