# Plano: discursos da Camara por deputado

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Deputados: `GET /api/v2/deputados`.
- Discursos: `GET /api/v2/deputados/{id}/discursos`.

## Fluxo

- Coletar a lista de deputados como metadado auxiliar.
- Particionar o periodo por mes.
- Para cada deputado e particao, paginar discursos por `dataInicio` e `dataFim`.
- Gravar deputados em `metadata/{run_id}.jsonl`.
- Gravar uma linha JSONL por pagina de discursos em `ano=YYYY/mes=MM/{run_id}.jsonl`, preservando o campo textual `transcricao` como texto oficial quando entregue pela API.
- Quando houver endpoint oficial mais granular para texto integral do discurso ou sessao, esse texto deve ter prioridade sobre metadados, `sumario` e palavras-chave.
- Em `--sample`, limitar a primeira particao e os tres primeiros deputados retornados.

## Saidas

- `data/raw/camara/plenario_discursos/metadata/{run_id}.jsonl`.
- `data/raw/camara/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`.
- `data/checkpoints/camara/plenario_discursos.json`, com retomada por `run_id`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Otimizacao historica

- O backfill de `1900-01-01` pode consultar
  `/api/v2/deputados/{id}/discursos` por ano como preflight por deputado.
- Se a primeira pagina anual vier sem `dados`, o ano pode ser marcado como
  vazio em `metadata/` sem abrir 12 janelas mensais para aquele deputado.
- Se houver discursos, a coleta pode consultar trimestres como segundo
  preflight. Trimestres vazios param ali; trimestres positivos ou
  inconclusivos abrem meses.
- Requisicoes anuais ou trimestrais nunca devem ser gravadas no corpus
  `ano=YYYY/mes=MM/`; elas sao somente descoberta em `metadata/`, porque podem
  misturar meses diferentes.
- So paginas de requisicoes mensais podem ser gravadas em
  `ano=YYYY/mes=MM/{run_id}.jsonl`.

## Dev e producao

- `dev`: primeira particao mensal e ate tres deputados por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de deputado/particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular particoes/registros existentes desse `run_id`.
- Pode rodar em paralelo com os coletores `senado/ccj_notas` e `camara/ccjc_eventos` se cada execucao tiver `run_id` distinto.
