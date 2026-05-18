# Plano: notas taquigraficas da CCJ do Senado

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Colegiado alvo: CCJ, codigo `34`.
- Agenda: `GET /dadosabertos/comissao/agenda/{dataInicio}/{dataFim}.json`.
- Detalhe: `GET /dadosabertos/comissao/reuniao/{codigo}.json`.
- Notas: `GET /dadosabertos/taquigrafia/notas/reuniao/{codigo}.json`.

## Fluxo

- Particionar o periodo por mes.
- Coletar a agenda de comissoes para a particao e grava-la em `metadata/{run_id}.jsonl`.
- Filtrar reunioes cujo colegiado seja `CCJ` ou codigo `34`.
- Para cada reuniao CCJ, coletar detalhe como metadado e transferir prioritariamente as notas taquigraficas/texto integral da reuniao quando disponiveis.
- Gravar notas/textos integrais em `ano=YYYY/mes=MM/{run_id}.jsonl`; agenda e detalhes permanecem em `metadata/{run_id}.jsonl`.
- Se no futuro houver texto segmentado por fala/discurso, esse texto por fala deve ter prioridade sobre a nota integral da sessao.
- Registrar falhas por reuniao no log sem interromper a particao inteira.

## Saidas

- `data/raw/senado/ccj_notas/metadata/{run_id}.jsonl`: agenda e detalhes de reuniao.
- `data/raw/senado/ccj_notas/ano=YYYY/mes=MM/{run_id}.jsonl`: notas taquigraficas/texto integral.
- `data/checkpoints/senado/ccj_notas.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Dev e producao

- `dev`: amostra mensal por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de reuniao/particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular registros existentes.
