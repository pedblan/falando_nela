# Plano: apartes do Plenario do Senado

## Objetivo

Coletar metadados oficiais de apartes em pronunciamentos do Plenario do Senado
Federal como base relacional separada do corpus textual. A unidade analitica
inicial nao e o texto do aparte, mas a relacao oficial
`aparteante -> pronunciamento`.

Essa coleta pode rodar antes do backfill historico completo de discursos,
porque grava somente descoberta e contexto em `metadata/`. O vinculo posterior
com `textos_parlamentares/v1` usa `CodigoPronunciamento` quando o corpus
textual estiver disponivel.

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Casa: Senado Federal, `casa=SF`.
- Fonte principal:
  `GET /dadosabertos/senador/{codigo}/apartes`.
- Parametros: `casa=SF`, `dataInicio=AAAAMMDD`, `dataFim=AAAAMMDD`,
  `numeroSessao`, `tipoSessao` e `v=5` quando aplicavel.
- Fonte auxiliar para enumerar senadores:
  - preferencialmente `processed/parlamentares/v1`;
  - fallback: endpoints oficiais de legislatura/lista atual do Senado.
- Fonte auxiliar de auditoria:
  `GET /dadosabertos/senador/{codigo}/discursos`, porque alguns
  pronunciamentos tambem trazem `Aparteantes`.

## Unidade de coleta

- Unidade de requisicao: um senador e uma janela temporal.
- Unidade bruta: uma resposta oficial do endpoint de apartes do senador.
- Unidade processada futura: uma linha por relacao
  `aparteante -> CodigoPronunciamento`.

`Apartes=null` e uma resposta valida: deve ser preservada no raw para auditar
cobertura, mas nao gera linha processada de aparte.

## Fluxo

1. Particionar o periodo por mes.
2. Carregar senadores de `parlamentares/v1` quando existir no mesmo
   `data_root`; se nao existir, descobrir senadores por legislatura usando os
   endpoints oficiais do Senado.
3. Para cada senador e particao, requisitar
   `/dadosabertos/senador/{codigo}/apartes` com `casa=SF` e `v=5`.
4. Gravar cada resposta em
   `data/raw/senado/plenario_apartes/metadata/{run_id}.jsonl` com
   `record_type=senador_apartes_metadata`.
5. Usar `source_id` deterministico no formato
   `SF:senador:{codigo}:apartes:{dataInicio}:{dataFim}`.
6. Em `--sample`, limitar a primeira particao e poucos senadores.
7. Marcar a particao como concluida somente depois de processar os senadores
   selecionados para aquela particao.

## Saidas

- `data/raw/senado/plenario_apartes/metadata/{run_id}.jsonl`.
- `data/checkpoints/senado/plenario_apartes.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.
- `data/manifests/{run_id}.autosave.json`.

Nao ha saida em `ano=YYYY/mes=MM/`, porque esta base nao descarrega corpus
textual.

## Dev e producao

- `dev`: usa amostra, grava em `data/dev` e aplica `--sample-limit` por
  default.
- `prod`: coleta completa, exige destino externo via `--output-dir` ou
  `FALANDO_NELA_DATA_ROOT`.
- A janela de producao recomendada tenta maximizar a cobertura historica com
  `--data-inicio 1900-01-01`, preservando lacunas ou anos sem retorno como
  metadados de cobertura. Para analise substantiva, o recorte recomendado e
  `2010-01-01` em diante.
- O `run_id` recomendado para producao e especifico do dataset, por exemplo
  `prod-senado-plenario-apartes`.

## Resiliencia operacional

- Usar a infra comum de CLI, retries, checkpoints, logs e manifests.
- Respeitar `Retry-After` e registrar respostas `429` no log.
- Com `--resume`, pular requisicoes ja gravadas para o mesmo `run_id`.
- Falhas por senador ou particao devem ser registradas e nao devem derrubar a
  coleta inteira quando houver caminho seguro para continuar.

## Fora do escopo atual

- Nao baixar texto individual do aparte.
- Nao tentar segmentar apartes dentro do texto integral do pronunciamento.
- Nao inferir genero, partido ou UF a partir de nome; esses atributos entram
  somente no processamento via `parlamentares/v1`.
