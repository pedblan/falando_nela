# Plano: discursos da Camara por deputado

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Deputados: `GET /api/v2/deputados`.
- Discursos: `GET /api/v2/deputados/{id}/discursos`.
- Referencia de cobertura: o Banco de Discursos da Camara documenta
  pronunciamentos de Plenario desde 1946.

## Recorte Historico

- O backfill oficial de `camara/plenario_discursos` deve iniciar em
  `1946-01-01`.
- A data `1900-01-01` nao deve ser usada como default operacional desta base,
  porque pode acionar muitas consultas vazias ou registros anomalos sem data
  real.
- Se houver interesse em investigar registros anteriores a 1946, isso deve ser
  feito como diagnostico separado de `1900-01-01` a `1945-12-31`, com limite
  explicito e saida/auditoria em `metadata/`, sem preencher corpus mensal por
  padrao.
- Para analises substantivas comparaveis entre bases, o recorte recomendado do
  projeto continua sendo `2010-01-01` em diante.

## Fluxo

1. Particionar o periodo por ano.
2. Antes de abrir requisicoes por deputado, tentar carregar
   `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet` ou,
   como fallback local, `processed/parlamentares/v1/parlamentares_periodos.jsonl`.
3. Quando `parlamentares_periodos` existir, montar o plano anual apenas com
   deputados cujos mandatos oficiais interceptam o ano e clipar a janela de
   cada deputado ao intervalo efetivo do mandato naquele ano.
4. Quando `parlamentares_periodos` nao existir, usar o comportamento antigo:
   coletar a lista de deputados ativos no intervalo daquele ano pela API da
   Camara como metadado auxiliar.
5. Para cada deputado ativo no ano, consultar
   `/api/v2/deputados/{id}/discursos` com `itens=1` como preflight anual.
6. Se o preflight anual vier sem `dados`, gravar o probe em `metadata/` e nao
   abrir trimestres nem meses para aquele deputado/ano.
7. Se o ano for positivo, consultar trimestres com `itens=1`.
8. Trimestres vazios param no probe; trimestres positivos abrem as janelas
   mensais daquele trimestre.
9. Apenas requisicoes mensais completas sao paginadas e gravadas em
   `ano=YYYY/mes=MM/{run_id}.jsonl`.
10. Preservar `transcricao` como texto oficial quando entregue pela API.
11. Quando houver endpoint oficial mais granular para texto integral do discurso
   ou sessao, esse texto deve ter prioridade sobre metadados, `sumario` e
   palavras-chave.

## Record Types

- `deputados_page`: lista de deputados ativos no intervalo anual, em
  `metadata/`, usada somente quando `parlamentares_periodos` nao estiver
  disponivel.
- `discursos_year_probe`: primeira pagina anual com `itens=1`, em
  `metadata/`.
- `discursos_quarter_probe`: primeira pagina trimestral com `itens=1`, em
  `metadata/`.
- `discursos_page`: pagina mensal de discursos, em `ano=YYYY/mes=MM/`.

## Saidas

- `data/raw/camara/plenario_discursos/metadata/{run_id}.jsonl`.
- `data/raw/camara/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`.
- `data/checkpoints/camara/plenario_discursos.json`, com retomada por
  `run_id`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Contrato De Corpus

- Requisicoes anuais ou trimestrais nunca devem ser gravadas no corpus
  `ano=YYYY/mes=MM/`; elas sao somente descoberta em `metadata/`, porque podem
  misturar meses diferentes.
- So paginas de requisicoes mensais podem ser gravadas em
  `ano=YYYY/mes=MM/{run_id}.jsonl`.
- O caderno de backfill deve auditar esse contrato antes do processamento.
- O caderno de backfill historico deve coletar e processar `parlamentares/v1`
  antes de `camara/plenario_discursos` sempre que possivel, para reduzir anos
  vazios por deputado.

## Dev E Producao

- `dev`: primeira particao anual e amostra de deputados por default, gravada em
  `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google
  Drive via `FALANDO_NELA_DATA_ROOT`.
- No caderno de backfill historico, esta base deve ter `data_inicio`
  especifica `1946-01-01`, mesmo quando outras bases usarem `1900-01-01`.

## Resiliencia Operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a
  execucao.
- Capturar falhas de deputado/particao com `try/except`, registrar log
  estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular
  particoes/registros existentes desse `run_id`.
- Pode rodar em paralelo com os coletores `senado/ccj_notas` e
  `camara/ccjc_eventos` se cada execucao tiver `run_id` distinto.
