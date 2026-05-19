# Requirements: notas taquigraficas da CCJ do Senado

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit`: limita a quantidade de reunioes CCJ processadas; default `5` em `dev` e sem limite em `prod`.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador da execucao.

## Separacao de dados

- Agenda, detalhes de reuniao, metadados de disponibilidade e status de ausencia das notas ficam em `data/raw/senado/ccj_notas/metadata/{run_id}.jsonl`.
- Notas taquigraficas e textos integrais ficam em `data/raw/senado/ccj_notas/ano=YYYY/mes=MM/{run_id}.jsonl`.
- A particao mensal do corpus nao deve ser preenchida apenas com pauta, ementa ou detalhe.
- Complementacoes devem usar um `run_id` proprio, preservando a coleta original e permitindo comparar cobertura antes/depois.

## Campos obrigatorios

- Agenda mensal bruta.
- Codigo da reuniao quando disponivel.
- Metadado de notas por reuniao via `/dadosabertos/comissao/reuniao/notas/{codigoReuniao}`.
- Detalhe e notas/texto integral por reuniao CCJ quando a API textual ou a pagina publica entregar.
- Registros de notas com `CodigoReuniao`, `codigo_reuniao`, `TextoIntegral`, `texto`, `forma`, `metodo_obtencao`, `texto_status`, `metadata` e `fontes`.
- `tentativas_texto` quando houver divergencia entre metadado, endpoint textual e HTML publico.
- Status `notas_taquigraficas_status` em `metadata/` quando nenhuma fonte textual entregar conteudo.
- Log de reunioes sem codigo ou endpoints indisponiveis.

## Complementacao de lacunas ate 2024

- O `IndicadorNotasTaquigraficas=N` de `/dadosabertos/comissao/reuniao/notas/{codigoReuniao}` nao deve ser tratado como ausencia definitiva para reunioes ate `2024-12-31`.
- Para reunioes CCJ sem registro `notas_taquigraficas` ja gravado, o coletor deve tentar `GET /dadosabertos/taquigrafia/notas/reuniao/{codigoReuniao}.json` mesmo quando o indicador vier como `N`.
- Se a API textual retornar texto, a reuniao deve gerar corpus mensal com `metodo_obtencao=api_taquigrafia_notas_reuniao_forcado` quando o metadado indicava `N`.
- Se a API textual falhar ou nao trouxer texto, o coletor deve tentar a pagina publica `https://www25.senado.leg.br/web/atividade/notas-taquigraficas/-/notas/r/{codigoReuniao}`.
- A reuniao `11176` em `2023-03-29` e caso de validacao obrigatorio: o metadado indica `N`, mas a API textual e a pagina publica entregam notas.
- Quando nenhuma fonte textual entregar conteudo, registrar a ausencia no log e em `notas_taquigraficas_status`, sem inventar corpus textual.

## Limites

- Nem toda reuniao tera notas taquigraficas publicadas.
- A coleta deve preservar essa ausencia como log, nao como dado inventado.
- Pautas, ementas e detalhes da reuniao nao substituem notas taquigraficas ou texto integral para analise textual.
- O backfill nao deve apagar nem sobrescrever registros de runs anteriores; a consolidacao posterior deve escolher a melhor cobertura por `codigo_reuniao`.

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de reuniao, endpoint ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
