# Plano: eventos da CCJC da Camara

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Orgao alvo: CCJC, id `2003`.
- Eventos: `GET /api/v2/orgaos/2003/eventos`.
- Detalhe: `GET /api/v2/eventos/{id}`.
- Deputados participantes: `GET /api/v2/eventos/{id}/deputados`.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, coletar eventos da CCJC.
- Para cada evento, coletar detalhe e participantes.
- Gravar uma linha JSONL por pagina de eventos, detalhe e pagina de participantes em `metadata/{run_id}.jsonl`, pois ainda sao metadados de descoberta e contexto.
- Se a API ou fonte oficial disponibilizar texto integral/notas da reuniao, esse texto deve ser transferido com prioridade sobre metadados do evento.
- Reservar `ano=YYYY/mes=MM/{run_id}.jsonl` para registros textuais futuros, caso a fonte oficial entregue notas/transcricao.
- Enquanto a API nao entregar transcricao textual, preservar URLs oficiais de registro para fila futura de transcricao por video/audio.
- Em `--sample`, limitar a primeira particao e ate tres eventos.

## Saidas

- `data/raw/camara/ccjc_eventos/metadata/{run_id}.jsonl`: eventos, detalhes e participantes.
- `data/raw/camara/ccjc_eventos/ano=YYYY/mes=MM/{run_id}.jsonl`: registros textuais futuros quando houver fonte oficial.
- `data/checkpoints/camara/ccjc_eventos.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Dev e producao

- `dev`: primeira particao mensal e ate tres eventos por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.
