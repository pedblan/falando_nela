# Requirements: eventos da CCJC da Camara

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador da execucao.

## Separacao de dados

- Eventos, detalhes, participantes, status do Escriba e HTML bruto disponivel ficam em `data/raw/camara/ccjc_eventos/metadata/{run_id}.jsonl`.
- A particao mensal do corpus recebe apenas notas taquigraficas parseadas a partir de HTML valido do Escriba.
- Lacunas sem texto oficial devem ser documentadas sem inventar corpus textual.

## Campos obrigatorios

- Id do orgao `2003` no manifest.
- Id do evento no `source_id`.
- Paginas de eventos, detalhes de eventos e participantes.
- Status da tentativa no Escriba para cada evento elegivel.
- URLs oficiais presentes no payload, incluindo `urlRegistro` quando a API entregar, URL HTML do Escriba e URL PDF quando houver.

## Politica de fonte textual

- Eventos devem ser descobertos por `GET /api/v2/orgaos/2003/eventos`; nao se deve varrer ids sequenciais do Escriba.
- O `id` do evento da API deve ser usado para tentar `https://escriba.camara.leg.br/escriba-servicosweb/html/{id}`.
- O escopo textual v1 via Escriba comeca em `2019+`; anos anteriores continuam com metadados da API e lacunas documentadas.
- `404` do Escriba e um status esperado para evento sem nota publicada, evento futuro, evento cancelado ou periodo sem cobertura; nao deve falhar a particao.
- Corpus textual so deve ser criado quando o HTML do Escriba entregar nota valida e parseavel.
- Quando houver texto, o registro mensal deve usar `record_type=notas_taquigraficas`, `metodo_obtencao=scraping_escriba_html`, `texto_status=disponivel`, `texto` e `fontes`.

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de evento ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros de API, status Escriba, HTML bruto e corpus ja presentes no JSONL do mesmo `run_id`.
