# Requirements: apartes do Plenario do Senado

## Objetivo

Baixar e versionar metadados oficiais de apartes no Plenario do Senado para
alimentar o dataset relacional `apartes_parlamentares/v1`.

## Interface CLI

- `--data-inicio AAAA-MM-DD`: inicio da janela de coleta.
- `--data-fim AAAA-MM-DD`: fim da janela de coleta.
- `--mode dev|prod`: `dev` usa amostra e `data/dev`; `prod` exige destino
  externo.
- `--output-dir CAMINHO`: raiz de dados, com prioridade sobre
  `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit N`: limita senadores ou requisicoes em amostras.
- `--resume`: pula requisicoes ja gravadas para o mesmo `run_id`.
- `--run-id ID`: identificador da execucao.

## Dependencias

- Python 3.11+.
- `httpx`.
- Infra comum em `coleta/common/` para diretorios, datas, retries, JSONL,
  checkpoints, logs e manifests.
- Leitura opcional de `processed/parlamentares/v1` quando disponivel para
  enumerar senadores.

## Endpoints obrigatorios

- Apartes por senador:
  - path: `/dadosabertos/senador/{codigo}/apartes`;
  - params: `casa=SF`, `dataInicio=AAAAMMDD`, `dataFim=AAAAMMDD`, `v=5`;
  - resposta gravada integralmente em `metadata/`.
- Fallback de enumeracao:
  - `/dadosabertos/senador/lista/legislatura/{inicio}/{fim}.json`;
  - `/dadosabertos/senador/lista/atual.json`.

## Separacao de dados

- O coletor nao produz corpus textual.
- Todos os registros ficam em
  `data/raw/senado/plenario_apartes/metadata/{run_id}.jsonl`.
- Nunca criar `data/raw/senado/plenario_apartes/ano=YYYY/mes=MM/`.
- O dataset raw e `plenario_apartes`.
- O `record_type` principal e `senador_apartes_metadata`.

## Contrato do registro bruto

Cada linha deve preservar o envelope comum:

- `run_id`, `collected_at`, `source`, `dataset`, `record_type`,
  `source_id`;
- `partition` e `periodo`;
- `request` com metodo, endpoint e parametros;
- `response` com URL final, status e cabecalhos relevantes;
- `checksum`;
- `payload` com a resposta oficial.

O payload pode conter `Apartes=null`, `Aparte` como objeto unico ou `Aparte`
como lista. Todos os formatos devem ser preservados sem perda.

## Regras de conteudo

- Cada `Aparte` oficial representa uma relacao entre o senador consultado
  como aparteante e o pronunciamento retornado.
- `CodigoPronunciamento` e a chave preferencial para vincular o aparte ao
  corpus de discursos do Senado.
- `Orador.CodigoParlamentar`, quando presente, e a chave preferencial do
  orador.
- `Publicacoes`, `SessaoPlenaria`, `TextoResumo`, `Indexacao`, `UrlTexto` e
  `UrlTextoBinario` sao metadados de contexto, nao texto analitico do aparte.
- A coleta nao deve criar nem preencher campos de genero.

## Limites e retomada

- Respeitar retries para `429`, `500`, `502`, `503` e `504`.
- Respeitar `Retry-After`.
- Checkpoint e `--resume` atuam por particao e por `source_id`.
- Em `prod`, falhar se nenhum destino externo for definido.

## Saida esperada para processamento

O processamento futuro deve conseguir explodir o raw em linhas com:

- `source=senado`;
- `casa=Senado Federal`;
- `data`, `ano`, `mes`;
- `pronunciamento_id`;
- `sessao_id`;
- `orador_id`, `orador_nome`;
- `aparteante_id`, `aparteante_nome`;
- URLs e campos `raw_*` de proveniencia.
