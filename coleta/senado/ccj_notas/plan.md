# Plano: notas taquigraficas da CCJ do Senado

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Colegiado alvo: CCJ, codigo `34`.
- Agenda: `GET /dadosabertos/comissao/agenda/{dataInicio}/{dataFim}.json`.
- Detalhe: `GET /dadosabertos/comissao/reuniao/{codigo}.json`.
- Metadado de notas: `GET /dadosabertos/comissao/reuniao/notas/{codigo}.json`.
- Texto das notas: `GET /dadosabertos/taquigrafia/notas/reuniao/{codigo}.json`.
- Fallback HTML: `https://www25.senado.leg.br/web/atividade/notas-taquigraficas/-/notas/r/{codigo}`.

## Fluxo

- Particionar o periodo por mes.
- Coletar a agenda de comissoes para a particao e grava-la em `metadata/{run_id}.jsonl`.
- Filtrar reunioes cujo colegiado seja `CCJ` ou codigo `34`.
- Para cada reuniao CCJ, coletar detalhe e metadado de notas como metadados.
- Tentar transferir o texto integral por `/dadosabertos/taquigrafia/notas/reuniao/{codigo}.json`.
- Para reunioes ate `2024-12-31`, tentar a API textual mesmo quando `IndicadorNotasTaquigraficas=N`, pois esse indicador pode divergir da disponibilidade real.
- Quando o metadado indicar `N` mas a API textual entregar texto, gravar a nota com `metodo_obtencao=api_taquigrafia_notas_reuniao_forcado`.
- Se a API textual falhar ou nao trouxer texto, tentar a pagina HTML publica de notas e gravar com `metodo_obtencao=pagina_notas_reuniao_html` quando houver texto.
- Quando nenhuma fonte textual entregar conteudo, gravar `notas_taquigraficas_status` em `metadata/` com `tentativas_texto` e motivo da ausencia.
- Gravar notas/textos integrais em `ano=YYYY/mes=MM/{run_id}.jsonl`; agenda, detalhes e metadados de notas permanecem em `metadata/{run_id}.jsonl`.
- Se no futuro houver texto segmentado por fala/discurso, esse texto por fala deve ter prioridade sobre a nota integral da sessao.
- Registrar falhas por reuniao no log sem interromper a particao inteira.

## Complementacao operacional

- Rodar a complementacao com `run_id` fixo e separado, por exemplo `prod-senado-ccj-complemento-ate-2024`.
- Janela recomendada: `2011-05-18` a `2024-12-31`, com `--resume`.
- O objetivo do run complementar e preencher reunioes em que a coleta original gravou agenda/detalhes/metadado, mas nao gerou `notas_taquigraficas`.
- O caderno operacional especifico fica em `notebooks/coleta/coleta_senado_ccj_complemento.ipynb`.

## Saidas

- `data/raw/senado/ccj_notas/metadata/{run_id}.jsonl`: agenda, detalhes de reuniao, metadados de disponibilidade e status de ausencia das notas.
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
- Em run complementar, `--resume` deve pular notas/status ja gravados no mesmo `run_id`, mas nao deve considerar um metadado `IndicadorNotasTaquigraficas=N` como prova de ausencia textual.
