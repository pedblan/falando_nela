# Plano: eventos da CCJC da Camara

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Orgao alvo: CCJC, id `2003`.
- Eventos: `GET /api/v2/orgaos/2003/eventos`.
- Detalhe: `GET /api/v2/eventos/{id}`.
- Deputados participantes: `GET /api/v2/eventos/{id}/deputados`.
- Fonte textual: `https://escriba.camara.leg.br/escriba-servicosweb/html/{id}`, usando o `id` do evento descoberto pela API oficial.
- PDF associado quando disponivel: `https://escriba.camara.leg.br/escriba-servicosweb/pdf/{id}?isTaquigrafia=false`.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, descobrir eventos da CCJC pela API oficial; nao varrer ids sequenciais do Escriba.
- Para cada evento, coletar detalhe e participantes.
- Para eventos da CCJC no escopo textual `2019+`, tentar o HTML do Escriba em `/html/{id}`.
- Gravar uma linha JSONL por pagina de eventos, detalhe, pagina de participantes, status Escriba e HTML bruto disponivel em `metadata/{run_id}.jsonl`.
- Quando o Escriba responder `200` com nota valida, parsear cabecalho, blocos por horario, oradores, falas, intercorrencias e fontes.
- Gravar a nota parseada em `ano=YYYY/mes=MM/{run_id}.jsonl` com `record_type=notas_taquigraficas`.
- Quando o Escriba responder `404`, registrar `texto_status=ausente` em metadata e continuar a particao.
- Preservar URLs de PDF, audio, video, HTML Escriba e `urlRegistro` como fontes.
- Em `--sample`, limitar a primeira particao e respeitar `--sample-limit` para quantidade maxima de eventos.

## Saidas

- `data/raw/camara/ccjc_eventos/metadata/{run_id}.jsonl`: eventos, detalhes, participantes, status Escriba e HTML bruto disponivel.
- `data/raw/camara/ccjc_eventos/ano=YYYY/mes=MM/{run_id}.jsonl`: notas taquigraficas parseadas do Escriba.
- `data/checkpoints/camara/ccjc_eventos.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Dev e producao

- `dev`: primeira particao mensal e amostra limitada por `--sample-limit`, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de evento/particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular API, status Escriba, HTML bruto e corpus existentes.
