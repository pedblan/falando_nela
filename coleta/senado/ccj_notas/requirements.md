# Requirements: notas taquigraficas da CCJ do Senado

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador da execucao.

## Separacao de dados

- Agenda e detalhes de reuniao ficam em `data/raw/senado/ccj_notas/metadata/{run_id}.jsonl`.
- Notas taquigraficas e textos integrais ficam em `data/raw/senado/ccj_notas/ano=YYYY/mes=MM/{run_id}.jsonl`.
- A particao mensal do corpus nao deve ser preenchida apenas com pauta, ementa ou detalhe.

## Campos obrigatorios

- Agenda mensal bruta.
- Codigo da reuniao quando disponivel.
- Detalhe e notas/texto integral por reuniao CCJ quando a API entregar.
- Log de reunioes sem codigo ou endpoints indisponiveis.

## Limites

- Nem toda reuniao tera notas taquigraficas publicadas.
- A coleta deve preservar essa ausencia como log, nao como dado inventado.
- Pautas, ementas e detalhes da reuniao nao substituem notas taquigraficas ou texto integral para analise textual.
