# Validation: discursos do Plenario do Congresso

## Auditoria de lacunas

Para a auditoria histórica, validar separadamente que IDs por senador ausentes
no raw são reportados em senator_endpoint_missing_ids.jsonl; não aceitar IDs
adicionais do raw como falha, pois CN também tem autores não senadores.

Os IDs ausentes devem ser recuperados pelo caderno
08_backfill_discursos_senadores_por_codigo_2010_colab.ipynb e só podem seguir
para derivados após reauditoria strict require-complete.

Para CN/2010, validar também que cada código encontrado no raw tem
`texto`/`TextoIntegral` não vazio. Se houver somente metadados, o caderno 09
deve congelar `congresso_2010_text_missing_population.jsonl` e executar:

```bash
python -m coleta.senado.recuperar_textos_diario \
  --mode prod --no-sample --resume \
  --output-dir "$FALANDO_NELA_DATA_ROOT" \
  --data-inicio 2010-01-01 --data-fim 2010-12-31 \
  --run-id backfill-discursos-plenario-2010-congresso-diario \
  --population-path "$POPULATION_PATH"
```

O manifest precisa ter `status=completed`, `errors=0` e um
`pronunciamento_texto` com texto não vazio para cada código da população. A
proveniência deve indicar `diario-congresso-oficial-por-codigo-v1`, `DCN`, o
código do diário e as páginas baixadas. Falta de texto, publicação DCN ambígua,
PDF sem texto ou delimitação de orador ambígua é falha retomável, não cobertura.
Quando a população não trouxer nome, a proveniência deve registrar
`speaker_source=portal_oficial` e o portal deve ter sido consultado pelo mesmo
`CodigoPronunciamento` da população.
Falas breves com cabeçalho oficial, delimitadas do próximo orador e com corpo
não vazio devem entrar no corpus; tamanho curto não é motivo de exclusão.
Cobrir em teste título institucional, nome com quebra hifenizada e o caso em
que a mesma pessoa atua como Presidência e faz discurso ordinário. Neste último,
o texto aprovado deve respeitar o tipo oficial de uso da palavra. Para edição
conjunta indexada em data diferente, validar que `lookup_date` e
`lookup_date_fallback_days` apontam para o caderno DCN que contém a página
histórica; uma edição próxima sem a página não pode ser aceita.

## Smoke test

```bash
python -m coleta.senado.congresso_discursos.collect --mode dev --run-id smoke-senado-cn
```

Smoke da recuperação:

```bash
python -m coleta.senado.congresso_discursos.collect \
  --mode dev --data-inicio 2015-01-01 --data-fim 2015-01-31 \
  --discovery-strategy historical-official \
  --run-id smoke-congresso-2015-historical
```

Confirmar `CN` sem itens `SF`, paginação completa, páginas raw em metadata e
paridade em mês-controle. Produção exige 24 partições completas, `errors=0`,
sem amostra e presença das sentinelas `411219` e `426642`.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu `FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.congresso_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-congresso",
    "--data-inicio", "1996-05-01",
    "--data-fim", "2026-05-18",
], check=False)
```

## Criterios

- Gera JSONL bruto, log, manifest e checkpoint.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- As listas mensais ficam em `metadata/{run_id}.jsonl`; registros
  `pronunciamento_texto` ficam em `ano=YYYY/mes=MM/{run_id}.jsonl`.
- O backfill operacional usa `1996-05-01` como inicio para evitar varrer meses
  anteriores sem cobertura no endpoint.
- A coleta continua mensal; nao deve depender de preflight anual/trimestral no
  endpoint de lista do Senado.
- Cada item com `CodigoPronunciamento` tenta o endpoint oficial de texto
  integral e, quando necessario, notas da sessao.
- O campo `texto` contem o corpo transferido, nunca a URL de texto integral.
- Casos audiovisuais sem texto aparecem em `transcription_queue` e nao entram
  silenciosamente no corpus analitico.
- O request preserva `siglaCasa=CN`.
- Analises futuras devem usar o texto integral transferido, nao `Resumo` ou apenas metadados de sessao.
- Uma segunda execucao com `--resume` pula a particao concluida.
- O manifest soma corretamente os registros escritos.

## Validacao de resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de particao, em `failed_partitions` no checkpoint.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular registros ja gravados.
- Falha inesperada de item deixa a particao retomavel; uma execucao posterior
  tenta apenas os pronunciamentos faltantes.
