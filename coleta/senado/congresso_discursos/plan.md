# Plano: discursos do Plenario do Congresso

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal e Congresso Nacional.
- Endpoint: `GET /dadosabertos/plenario/lista/discursos/{dataInicio}/{dataFim}.json`.
- Parametros fixos: `siglaCasa=CN`, `v=4`.

## Recorte Operacional

- A pagina oficial de Dados Abertos do Senado descreve pronunciamentos como
  discursos, falas e questoes de ordem em sessoes do Senado Federal e do
  Congresso Nacional, mas nao fixa data minima do endpoint.
- Probes mensais no endpoint `plenario/lista/discursos` indicaram primeiro
  retorno em `1996-05-21` para `siglaCasa=CN`; portanto o backfill operacional
  deve iniciar em `1996-05-01`.
- Periodos anteriores devem ser tratados como diagnostico separado, nao como
  backfill normal deste endpoint.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, requisitar os discursos do Congresso Nacional.
- Gravar a resposta mensal como metadado de apoio em `metadata/{run_id}.jsonl`, sem misturar a lista ao corpus textual mensal.
- Extrair `CodigoPronunciamento` e transferir prioritariamente o texto integral de cada discurso pelo endpoint oficial de texto integral, seguindo o mesmo contrato de `senado/plenario_discursos`.
- Gravar registros textuais consolidados em `ano=YYYY/mes=MM/{run_id}.jsonl` quando a etapa de texto integral for implementada.
- Se texto por pronunciamento nao estiver disponivel, usar texto/notas da sessao como proximo caminho antes de fila de transcricao.
- Usar checkpoint por particao mensal para retomada.

## Saidas

- `data/raw/senado/congresso_discursos/metadata/{run_id}.jsonl`: listas mensais brutas.
- `data/raw/senado/congresso_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`: registros textuais consolidados quando implementados.
- `data/checkpoints/senado/congresso_discursos.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Otimizacao historica

- O endpoint de lista de discursos do Senado aceita janelas mensais, mas
  retorna HTTP 400 para janelas trimestrais ou anuais testadas.
- Portanto, este coletor nao deve prometer preflight `ano -> trimestre -> mes`
  nesse endpoint. A reducao de consultas vazias deve vir do recorte operacional
  `1996-05-01` e da retomada por checkpoint.
- Requisicoes mensais de descoberta ficam em `metadata/`; registros textuais,
  quando implementados, continuam restritos a requisicoes mensais em
  `ano=YYYY/mes=MM/`.

## Dev e producao

- `dev`: amostra mensal por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular registros existentes.
