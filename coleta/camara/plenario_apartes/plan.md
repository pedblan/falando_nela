# Plano: apartes do Plenario da Camara

## Objetivo

Coletar metadados oficiais de apartes no Plenario da Camara dos Deputados como
base relacional separada do corpus textual. A unidade analitica inicial e a
relacao `aparteante -> discurso`, nao o texto individual de cada aparte.

Essa coleta pode rodar antes do backfill historico completo de discursos,
porque grava as paginas oficiais de busca em `metadata/` e deixa o vinculo com
`textos_parlamentares/v1` para o processamento posterior.

## Fonte

- Portal principal de discursos: Dados Abertos da Camara dos Deputados.
- Endpoint textual atual: `GET /api/v2/deputados/{id}/discursos`, sem campo
  estruturado de aparteante.
- Fonte oficial de aparteante: Banco de Discursos/Sitaq, que permite pesquisa
  por `Aparteante`.
- Busca: `GET /internet/SitaqWeb/ResultadoPesquisaDiscursos.asp`.
- Parametros principais da busca:
  - `BasePesq=plenario`;
  - `dtInicio=DD/MM/AAAA`;
  - `dtFim=DD/MM/AAAA`;
  - `txAparteante={nome}`;
  - `CampoOrdenacao=dtSessao`;
  - `TipoOrdenacao=ASC`;
  - `PageSize=50`.
- Fonte auxiliar para validar chaves de sessao/discurso:
  `GET /SitCamaraWS/SessoesReunioes.asmx/ListarDiscursosPlenario`.
- Fonte auxiliar para inteiro teor, quando necessario em auditoria:
  `GET /SitCamaraWS/SessoesReunioes.asmx/obterInteiroTeorDiscursosPlenario`.

## Unidade de coleta

- Unidade de requisicao: um parlamentar aparteante e uma janela temporal.
- Unidade bruta: uma pagina oficial de resultado do Sitaq.
- Unidade processada futura: uma linha por relacao
  `aparteante -> discurso`.

Paginas sem resultados sao respostas validas e devem ser preservadas para
auditar cobertura.

## Fluxo

1. Particionar o periodo por ano para fazer preflight de existencia.
2. Se a busca anual retornar zero resultados, preservar a pagina anual em
   `metadata/` e nao abrir meses.
3. Se a busca anual retornar resultados, for inconclusiva ou falhar, abrir
   aquele ano em trimestres.
4. Se a busca trimestral retornar resultados, for inconclusiva ou falhar, abrir
   aquele trimestre em meses e gravar as paginas mensais em `metadata/`.
5. Carregar deputados e variantes de nome de `parlamentares/v1` quando existir
   no mesmo `data_root`; se nao existir, usar a API oficial de deputados como
   fallback.
6. Para cada parlamentar e janela, consultar o Sitaq com `txAparteante`.
7. Paginar resultados do Sitaq ate a ultima pagina disponivel.
8. Gravar cada pagina em
   `data/raw/camara/plenario_apartes/metadata/{run_id}.jsonl` com
   `record_type=sitaq_apartes_search_page`.
9. Preservar HTML bruto e parametros de busca no payload.
10. Extrair, quando possivel, chaves de `TextoHTML.asp` apenas como metadados
   auxiliares: `nuSessao`, `nuQuarto`, `nuOrador`, `nuInsercao`, fase, data e
   apelido do orador.
11. Em processamento posterior, reconciliar `txAparteante` com
   `parlamentares/v1` e marcar ambiguidades.

## Saidas

- `data/raw/camara/plenario_apartes/metadata/{run_id}.jsonl`.
- `data/checkpoints/camara/plenario_apartes.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.
- `data/manifests/{run_id}.autosave.json`.

Nao ha saida em `ano=YYYY/mes=MM/`, porque esta base nao descarrega corpus
textual.

## Dev e producao

- `dev`: usa amostra, grava em `data/dev` e limita a poucos nomes/janelas.
- `prod`: coleta completa, exige destino externo via `--output-dir` ou
  `FALANDO_NELA_DATA_ROOT`.
- A janela de producao recomendada tenta maximizar a cobertura historica com
  `--data-inicio 1900-01-01`, preservando lacunas ou anos sem retorno como
  metadados de cobertura. Para analise substantiva, o recorte recomendado e
  `2010-01-01` em diante.
- O `run_id` recomendado para producao e especifico do dataset, por exemplo
  `prod-camara-plenario-apartes`.

## Resiliencia operacional

- Usar a infra comum de CLI, logs, checkpoints e manifests.
- Requisicoes HTML devem registrar URL final, status, parametros e checksum.
- Com `--resume`, pular paginas ou buscas ja gravadas para o mesmo `run_id`.
- Falhas por parlamentar, pagina ou janela devem ser registradas sem derrubar
  a coleta inteira quando houver caminho seguro para continuar.

## Fora do escopo atual

- Nao baixar texto individual do aparte.
- Nao raspar texto por inferencia de padroes na transcricao.
- Nao inferir genero, partido ou UF por nome; esses atributos entram somente
  no processamento via `parlamentares/v1`.
- Nao usar a API REST de discursos como fonte de aparteante, porque ela nao
  disponibiliza campo estruturado para isso.
