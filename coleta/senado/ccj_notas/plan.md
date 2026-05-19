# Plano: notas taquigraficas da CCJ do Senado

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Colegiado alvo: CCJ, codigo `34`.
- Agenda: `GET /dadosabertos/comissao/agenda/{dataInicio}/{dataFim}.json`.
- Detalhe: `GET /dadosabertos/comissao/reuniao/{codigo}.json`.
- Metadado de notas: `GET /dadosabertos/comissao/reuniao/notas/{codigo}.json`.
- Texto das notas, quando o metadado indicar disponibilidade: `GET /dadosabertos/taquigrafia/notas/reuniao/{codigo}.json`.

## Fluxo

- Particionar o periodo por mes.
- Coletar a agenda de comissoes para a particao e grava-la em `metadata/{run_id}.jsonl`.
- Filtrar reunioes cujo colegiado seja `CCJ` ou codigo `34`.
- Para cada reuniao CCJ, coletar detalhe e metadado de notas como metadados.
- Quando `IndicadorNotasTaquigraficas=S`, transferir o texto integral das notas da reuniao.
- Gravar notas/textos integrais em `ano=YYYY/mes=MM/{run_id}.jsonl`; agenda, detalhes e metadados de notas permanecem em `metadata/{run_id}.jsonl`.
- Se no futuro houver texto segmentado por fala/discurso, esse texto por fala deve ter prioridade sobre a nota integral da sessao.
- Registrar falhas por reuniao no log sem interromper a particao inteira.

## Saidas

- `data/raw/senado/ccj_notas/metadata/{run_id}.jsonl`: agenda, detalhes de reuniao e metadados de disponibilidade das notas.
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
