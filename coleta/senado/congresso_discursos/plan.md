# Plano: discursos do Plenario do Congresso

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal e Congresso Nacional.
- Endpoint: `GET /dadosabertos/plenario/lista/discursos/{dataInicio}/{dataFim}.json`.
- Parametros fixos: `siglaCasa=CN`, `v=4`.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, requisitar os discursos do Congresso Nacional.
- Gravar a resposta mensal como metadado de apoio em `metadata/{run_id}.jsonl`, sem misturar a lista ao corpus textual mensal.
- Extrair `CodigoPronunciamento` e transferir prioritariamente o texto integral de cada discurso pelo endpoint oficial de texto integral, seguindo o mesmo contrato de `senado/plenario_discursos`.
- Gravar registros textuais consolidados em `ano=YYYY/mes=MM/{run_id}.jsonl` quando a etapa de texto integral for implementada.
- Se texto por pronunciamento nao estiver disponivel, usar texto/notas da sessao como proximo caminho antes de fila de transcricao.
- Usar checkpoint por particao mensal para retomada.

## Saidas

- `data/raw/senado/congresso_discursos/metadata/{run_id}.jsonl`: listas mensais brutas.
- `data/raw/senado/congresso_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`: registros textuais consolidados quando implementados.
- `data/checkpoints/senado/congresso_discursos.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Dev e producao

- `dev`: amostra mensal por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.
