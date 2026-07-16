# Validation: discursos da Camara por deputado

## Smoke Test

```bash
python -m coleta.camara.plenario_discursos.collect \
  --mode dev \
  --run-id smoke-camara-discursos
```

Para smoke local com `run_id` reutilizado, apague os arquivos de `data/dev`
desse `run_id` ou use um novo identificador.

## Exemplo Colab

Assume que a celula base do README ja montou o Drive, definiu
`FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

O caderno pronto para este fluxo fica em:

```text
notebooks/coleta/coleta_camara_plenario.ipynb
```

No backfill historico geral, use:

```bash
python -m coleta.camara.plenario_discursos.collect \
  --mode prod \
  --resume \
  --run-id prod-historico-camara-plenario \
  --data-inicio 1946-01-01 \
  --data-fim 2026-05-28 \
  --no-sample
```

O comando acima valida o backfill historico dedicado. Ele nao faz parte do
ciclo incremental `20260713`. Nesse ciclo, o caderno 05 deve gerar somente:

```bash
python -u -m coleta.camara.plenario_discursos.collect \
  --mode prod \
  --output-dir /content/drive/MyDrive/falando_nela/data \
  --data-inicio 2026-05-01 \
  --data-fim 2026-07-13 \
  --run-id prod-atualizacao-20260713-camara-plenario \
  --no-sample \
  --resume
```

O caderno acrescenta `--parlamentares-periodos-path` com uma copia local do
Parquet. Ele deve falhar antes da chamada se janela ou `run_id` divergirem e
nao deve conter uma celula capaz de retomar o run historico. A presenca dos
artefatos antigos no Drive e informativa e nao autoriza edicao ou remocao.

## Testes Automatizados

```bash
pytest tests/test_camara_plenario.py -q
```

Os testes devem cobrir:

- carregamento de `parlamentares_periodos` e filtragem de mandatos por janela;
- paginacao de deputados por intervalo anual;
- escrita de `deputados_page` em `metadata/`;
- probe anual vazio sem abertura de meses;
- probe anual/trimestral positivo abrindo meses;
- fallback do probe para consulta sem ordenacao quando a API retorna 500;
- fallback mensal para paginacao `itens=1` quando a pagina ordenada e a pagina
  sem ordenacao retornam 500;
- garantia de que o 500 nos pontos com fallback conhecido nao consome todos os
  retries antes de trocar de estrategia;
- registro `discursos_page_error` em `metadata/` para paginas persistentes que
  continuam quebrando mesmo com `itens=1`;
- preservacao de `transcricao` em paginas mensais;
- preservação exata de nomes e transcrições com diacríticos em UTF-8, sem `�`;
- escrita mensal exclusivamente em `ano=YYYY/mes=MM/`.
- aceite da retomada rapida quando o ultimo `partition_started` possui
  `partition_completed`, e recusa quando uma particao da janela permanece
  aberta ou falha;
- persistência e reaproveitamento de fronteira por deputado na retomada de uma
  partição aberta, sem nova consulta para o deputado já confirmado;
- migração segura do prefixo de manifest interrompido somente quando os probes
  raw e o plano de mandatos comprovarem a mesma ordem e quantidade;
- teto de 60 segundos para um `Retry-After` excessivo e `status=interrupted`
  após interrupção explícita, sem manifest falsamente `completed`;
- reaproveitamento de probe e de página mensal raw numa retomada, sem qualquer
  chamada HTTP para o `source_id` já gravado;
- aplicação do intervalo mínimo também nas requisições de fallback rápido e
  emissão de `discursos_page_request_started` antes de página sem cache;
- paginação contraditória (`next` após `last`) encerrada na última página
  declarada, com páginas anteriores já persistidas; URL repetida deve falhar
  antes de nova chamada HTTP;
- uso de um `parlamentares_periodos` explicito fora do `data_root`;
- progresso visivel da varredura de registros existentes e heartbeats por
  lote de deputados.

## Criterios

- Gera registros de metadados de deputados.
- Em `dev`, grava em `data/dev` e usa amostra por default.
- Em `prod`, exige destino externo e registra `mode=prod` no manifest.
- Metadados de deputados e probes ficam em `metadata/{run_id}.jsonl`.
- Quando `processed/parlamentares/v1` existir, o manifest registra
  `deputados_periodos_carregados > 0` e o log da particao mostra
  `planejamento=parlamentares_periodos`.
- Quando `processed/parlamentares/v1` nao existir, o coletor cai no fallback
  oficial `api_deputados_periodo`.
- `discursos_year_probe` e `discursos_quarter_probe` nunca aparecem em
  `ano=YYYY/mes=MM/`.
- `discursos_page` e gravado apenas para requisicoes mensais.
- `discursos_page_error` aparece somente em `metadata/` e nao bloqueia a
  gravacao de outras paginas recuperaveis do mesmo mes.
- Paginação mensal reconstrói cada URL com os filtros mensais originais; um
  `rel=next` sem as datas não pode ampliar o escopo da coleta.
- O inventário operacional do backfill só conta uma página raw cuja requisição
  registrada confirme o mesmo `dataInicio` e `dataFim` do seu período e cujo
  payload permaneça dentro dele. Página imutável de uma execução anterior que
  viole uma dessas condições é diagnosticada e excluída do gate, para que a
  página corrigida possa ser auditada separadamente.
- Quando o fallback `itens=1` for acionado, paginas recuperadas podem aparecer
  com indices nao contiguos se uma pagina intermediaria persistir com 500; a
  lacuna deve estar registrada no erro correspondente em `metadata/`.
- Testes de fallback devem conferir tambem o numero de tentativas da URL que
  retornou 500, para evitar regressao para retries longos em erro persistente.
- Registros preservam id do deputado, periodo, request, response, payload e
  checksum.
- Quando `transcricao` estiver presente, ela e o texto prioritario para
  analise; `sumario` e `keywords` sao apenas metadados.
- Uma segunda execucao com o mesmo `--run-id --resume` pula particoes
  concluidas desse `run_id`.
- Pode rodar em paralelo com a complementacao `senado/ccj_notas` e com
  `camara/ccjc_eventos` quando os `run_id`s forem distintos.

## Validacao De Resiliencia

- O stdout deve mostrar eventos de progresso suficientes para acompanhar a
  execucao no Colab.
- O arquivo `manifests/{run_id}.autosave.json` deve existir durante/depois da
  execucao.
- Falhas isoladas devem aparecer em `logs/{run_id}.jsonl` e, quando forem de
  particao, em `failed_partitions` no checkpoint.
- Erro de deputado ou de página mensal deve deixar o ano em
  `failed_partitions`, nunca em `completed_partitions`; depois de uma retomada
  bem-sucedida, a conclusão posterior do mesmo ano é a única autorização para
  pulá-lo.
- Reexecutar com o mesmo `--run-id --resume` deve ler JSONLs existentes e pular
  particoes, registros e deputados concluídos desse `run_id`, sem pular
  particoes concluidas por outro `run_id`.
- Para um deputado parcialmente coletado, `--resume` deve reutilizar cada
  `discursos_year_probe`, `discursos_quarter_probe` e `discursos_page` raw
  válido antes de tentar a próxima resposta ausente; `record_resume_reused`
  deve anteceder qualquer nova chamada desse item.
- Em retomada parcial, o stdout deve mostrar `resume_record_scan_started`,
  `resume_record_scan_progress`, `resume_record_scan_completed` e depois
  `deputy_started`/`deputy_progress`; o autosave deve indicar `existing_record_scan=filtered`,
  `existing_record_scan_years` com os anos parciais e `active_partition`.
- Se checkpoint e log nao permitirem provar o escopo parcial, o autosave deve
  indicar `existing_record_scan=loaded` e a retomada deve ler todo o run.
- Cada chamada mensal não presente no raw deve ser precedida no stdout por
  `discursos_page_request_started`, com deputado, página e período.
- Uma sequência de `rel=next` não pode gerar milhares de páginas em memória:
  o JSONL mensal deve receber cada página imediatamente e o log deve registrar
  `discursos_pagination_next_ignored` quando `next` contradisser `last`.
- Em fronteira limpa validada, o manifest deve indicar
  `skip_existing_record_scan=true` e `existing_record_scan=skipped`.

## Checks Manuais

```bash
python - <<'PY'
import json
from pathlib import Path

run_id = "prod-historico-camara-plenario"
root = Path("/content/drive/MyDrive/falando_nela/data/raw/camara/plenario_discursos")
metadata = root / "metadata" / f"{run_id}.jsonl"
counts = {}
for line in metadata.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    record = json.loads(line)
    counts[record["record_type"]] = counts.get(record["record_type"], 0) + 1
print(counts)
for path in root.glob(f"ano=*/mes=*/{run_id}.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines()[:10]:
        record = json.loads(line)
        assert record["record_type"] == "discursos_page", path
PY
```

## Validação Da Recuperação Legada

- O inventário seleciona somente páginas mensais `discursos_page` com mídia e
  texto vazio e elimina a unidade quando uma ocorrência posterior tem texto.
- A varredura lê apenas `ano=YYYY/mes=MM/*.jsonl`: JSONL parcial em
  `metadata/` não interrompe a sondagem, mas JSON inválido no corpus mensal
  continua sendo erro bloqueante.
- Nenhum candidato da Câmara entra em `recovered_legacy_texts.parquet` ou nos
  matches do banco legado, mesmo se houver colisão artificial de id.
- `camara_media_download_queue.parquet` contém apenas Câmara, URL não vazia e
  estados pendentes de download e transcrição.
- A execução do caderno 10 não modifica raw, checkpoint ou manifest do coletor.
