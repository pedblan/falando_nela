# Requirements: apartes do Plenario da Camara

## Objetivo

Baixar e versionar paginas oficiais do Banco de Discursos/Sitaq que indicam
discursos de Plenario com determinado aparteante, para alimentar
`apartes_parlamentares/v1`.

## Interface CLI

- `--data-inicio AAAA-MM-DD`: inicio da janela de coleta.
- `--data-fim AAAA-MM-DD`: fim da janela de coleta.
- `--mode dev|prod`: `dev` usa amostra e `data/dev`; `prod` exige destino
  externo.
- `--output-dir CAMINHO`: raiz de dados, com prioridade sobre
  `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit N`: limita nomes ou requisicoes em amostras.
- `--resume`: pula buscas ou paginas ja gravadas para o mesmo `run_id`.
- `--run-id ID`: identificador da execucao.

## Dependencias

- Python 3.11+.
- `httpx`.
- Parser HTML estruturado da biblioteca padrao ou dependencia explicita futura,
  se a implementacao justificar.
- Infra comum em `coleta/common/`.
- Leitura opcional de `processed/parlamentares/v1` para obter nomes oficiais e
  IDs dos deputados.

## Fontes oficiais

- Banco de Discursos/Sitaq:
  - path: `/internet/SitaqWeb/ResultadoPesquisaDiscursos.asp`;
  - params: `BasePesq=plenario`, `dtInicio`, `dtFim`, `txAparteante`,
    `CampoOrdenacao`, `TipoOrdenacao`, `PageSize` e pagina corrente quando
    aplicavel.
- Webservice de sessoes:
  - `/SitCamaraWS/SessoesReunioes.asmx/ListarDiscursosPlenario`;
  - usado para validar chaves de sessao/discurso quando necessario.
- API REST de discursos:
  - `/api/v2/deputados/{id}/discursos`;
  - usada como contexto textual do projeto, nao como fonte de aparteante.

## Separacao de dados

- O coletor nao produz corpus textual.
- Todos os registros ficam em
  `data/raw/camara/plenario_apartes/metadata/{run_id}.jsonl`.
- Nunca criar `data/raw/camara/plenario_apartes/ano=YYYY/mes=MM/`.
- O dataset raw e `plenario_apartes`.
- O `record_type` principal e `sitaq_apartes_search_page`.

## Contrato do registro bruto

Cada linha deve preservar o envelope comum:

- `run_id`, `collected_at`, `source`, `dataset`, `record_type`,
  `source_id`;
- `partition` e `periodo`;
- `request` com metodo, endpoint e parametros;
- `response` com URL final, status e cabecalhos relevantes;
- `checksum`;
- `payload`.

O `payload` deve preservar:

- `html`: HTML bruto da pagina oficial;
- `query`: parametros usados;
- `aparteante_consultado`: nome consultado;
- `aparteante_id_consultado`: ID oficial quando veio de `parlamentares/v1`;
- `page_number` e metadados de paginacao quando disponiveis;
- `result_count_text` ou equivalente bruto quando a pagina informar contagem;
- lista preliminar de chaves extraidas de `TextoHTML.asp`, quando o parser
  conseguir extrair sem ambiguidade.

## Regras de conteudo

- Cada resultado do Sitaq representa uma relacao candidata
  `aparteante -> discurso`.
- A chave preferencial do discurso da Camara e composta por data da sessao,
  `nuSessao`, `nuQuarto`, `nuOrador`, `nuInsercao`, fase e orador.
- Quando o nome consultado nao tiver match unico em `parlamentares/v1`, o raw
  deve ser preservado e o processamento deve marcar `match_status=name_only` ou
  `ambiguous`.
- A coleta nao deve criar nem preencher campos de genero.
- Paginas com zero resultados devem ser gravadas para auditoria.

## Limites e retomada

- A busca do Sitaq pode ser sensivel a janelas longas; a implementacao deve
  reduzir janelas quando houver muitos resultados ou falha recorrente.
- Checkpoint e `--resume` atuam por parlamentar, janela e pagina.
- Em `prod`, falhar se nenhum destino externo for definido.
- O coletor deve registrar HTML e URL final mesmo quando o parser de resultados
  nao conseguir extrair todas as chaves.

## Saida esperada para processamento

O processamento futuro deve conseguir produzir linhas com:

- `source=camara`;
- `casa=Camara dos Deputados`;
- `data`, `ano`, `mes`;
- `discurso_chave`;
- `sessao_id`;
- `fase_sessao`;
- `orador_nome`;
- `aparteante_id` quando houver match unico;
- `aparteante_nome`;
- URLs e campos `raw_*` de proveniencia.
