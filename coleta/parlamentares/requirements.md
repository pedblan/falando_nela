# Requirements: metadados de parlamentares

## Objetivo

Baixar, versionar e normalizar metadados oficiais de deputados e senadores para
que o corpus `textos_parlamentares/v1` possa ser correlacionado a atributos de
parlamentares, especialmente genero/sexo informado pela fonte, partido, UF,
legislatura e periodos de mandato. A mesma dimensao deve atender bases
relacionais como `apartes_parlamentares/v1`.
`parlamentares_periodos` tambem deve poder ser usado pelos coletores historicos
da Camara como plano de mandato para reduzir consultas de deputados fora de
exercicio.

## Parametros

- `--data-inicio`, `--data-fim`: periodo em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev` por default; `prod` usa
  coleta completa e destino externo.
- `--output-dir`: raiz de dados; tem prioridade sobre
  `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit`: quantidade maxima de parlamentares por casa em amostras.
- `--resume`: pula endpoints ja concluidos no checkpoint para o mesmo `run_id`.
- `--run-id`: identificador da execucao.
- `--source camara|senado|all`: restringe a casa coletada quando necessario.
- `--skip-existing-id-scan`: pula a varredura de `raw/` e
  `processed/textos_parlamentares/v1` para complementar IDs. Recomendado na
  etapa preparatoria de backfill historico, quando a lista oficial por periodo
  basta e a varredura do Drive tornaria o inicio silencioso/lento.
- `--skip-detail-endpoints`: pula endpoints individuais de detalhe, historico,
  mandatos e filiacoes. Recomendado apenas para gerar rapidamente um plano de
  mandatos por legislatura antes dos coletores historicos; nao substitui a
  coleta completa de genero/detalhes.

## Separacao de dados

- O coletor nao produz corpus textual.
- Todos os registros brutos devem ficar em `metadata/{run_id}.jsonl`.
- A Camara deve gravar em `data/raw/camara/parlamentares/metadata/`.
- O Senado deve gravar em `data/raw/senado/parlamentares/metadata/`.
- Respostas de descoberta, detalhes, mandatos, historicos e filiacoes devem
  preservar o envelope bruto comum: `run_id`, `collected_at`, `source`,
  `dataset`, `record_type`, `source_id`, `request`, `response`, `checksum` e
  `payload`.
- O dataset raw e `parlamentares` para as duas casas.
- O coletor deve imprimir progresso no stdout via log estruturado durante
  descoberta de IDs, listagens oficiais e processamento por lotes de
  parlamentares.
- Na Camara, o progresso deve indicar legislatura corrente e
  `paginas_estimadas` quando a API trouxer link `last`.

## Fontes oficiais

- Usar somente APIs ou arquivos oficiais da Camara e do Senado.
- Camara:
  - `GET /api/v2/legislaturas`;
  - `GET /api/v2/deputados?idLegislatura={id}` como descoberta preferencial;
  - `GET /api/v2/deputados`;
  - `GET /api/v2/deputados/{id}`;
  - `GET /api/v2/deputados/{id}/historico`;
  - arquivo `arquivos/deputados/json/deputados.json` como fallback/auditoria.
- Senado:
  - `GET /dadosabertos/senador/lista/legislatura/{inicio}/{fim}.json`;
  - `GET /dadosabertos/senador/lista/atual.json`;
  - `GET /dadosabertos/senador/{codigo}.json`;
  - `GET /dadosabertos/senador/{codigo}/mandatos.json`;
  - `GET /dadosabertos/senador/{codigo}/filiacoes.json`.
- Registrar versao de servico, data de versao, schema ou metadados equivalentes
  quando a fonte entregar esses campos.

## Campos processed: parlamentares

`processed/parlamentares/v1/parlamentares.jsonl` deve conter uma linha por
parlamentar oficial e preservar pelo menos:

- `parlamentar_key`: `"{source}:{parlamentar_id}"`;
- `dataset_version`: `v1`;
- `source`;
- `casa`;
- `parlamentar_id`;
- `codigo_publico`, quando houver;
- `nome_parlamentar`;
- `nome_civil`;
- `sexo_original`;
- `genero`;
- `genero_fonte`;
- `data_nascimento`;
- `data_falecimento`;
- `uf_nascimento`;
- `municipio_nascimento`;
- `url_foto`;
- `url_pagina`;
- `email_publico`;
- `raw_run_id`;
- `raw_source_id`;
- `raw_checksum`;
- `raw_path`;
- `raw_response_url`.

## Regra de genero

- `sexo_original` deve preservar exatamente o valor oficial, como `M`, `F`,
  `Masculino` ou `Feminino`.
- `genero` deve ser uma normalizacao analitica simples derivada somente de
  campo oficial de sexo/genero da fonte.
- Valores aceitos para `genero`: `masculino`, `feminino`, `nao_informado`.
- Nao inferir genero por nome, foto, tratamento, pronome ou texto de discurso.
- Quando a fonte oficial divergir entre endpoints, manter o valor do endpoint
  de detalhe como preferencial e registrar divergencia em auditoria.

## Campos processed: mandatos

`processed/parlamentares/v1/mandatos.jsonl` deve conter uma linha por periodo
oficial de mandato ou exercicio:

- `parlamentar_key`;
- `source`;
- `casa`;
- `parlamentar_id`;
- `mandato_id`;
- `legislatura`;
- `data_inicio`;
- `data_fim`;
- `uf`;
- `partido_sigla`;
- `situacao`;
- `condicao`;
- `participacao`;
- `cargo`;
- `titular_key`, quando o registro representar suplente;
- `raw_*` de proveniencia.

## Campos processed: filiacoes

`processed/parlamentares/v1/filiacoes.jsonl` deve conter historico partidario
quando a fonte disponibilizar:

- `parlamentar_key`;
- `source`;
- `parlamentar_id`;
- `partido_sigla`;
- `partido_nome`, quando houver;
- `data_inicio`;
- `data_fim`;
- `raw_*` de proveniencia.

## Campos processed: periodos de juncao

`processed/parlamentares/v1/parlamentares_periodos.jsonl` deve ser a tabela
preferencial para cruzar textos com metadados:

- uma linha por intervalo de vigencia;
- `vigencia_inicio`, `vigencia_fim` e `vigencia_fim_exclusivo` em
  `AAAA-MM-DD`;
- `parlamentar_key`, `source`, `parlamentar_id`, `nome_parlamentar`,
  `nome_civil`, `genero`, `sexo_original`;
- `partido_sigla`, `uf`, `cargo`, `legislatura`, `mandato_id`;
- campos de qualidade: `intervalo_fonte`, `match_priority`,
  `intervalo_inferido`, `observacao_qualidade`.

Os intervalos devem ser fechados no inicio e abertos no fim para juncao
computacional (`data >= vigencia_inicio` e `data < vigencia_fim_exclusivo`), mas
tambem devem expor `vigencia_fim` legivel para auditoria.

Para planejamento de coleta, `camara/plenario_discursos` e
`camara/plenario_apartes` podem ler essa tabela e filtrar somente linhas com
`source=camara`, `intervalo_fonte=mandato` e `intervalo_inferido=false`,
clipando a janela da requisicao ao intervalo de mandato que intercepta o ano.
Em execucoes completas, amostras pequenas de `parlamentares_periodos` nao devem
ser usadas como plano suficiente.
Quando `parlamentares/v1` for gerado em modo rapido com
`--skip-detail-endpoints`, a Camara deve construir esses intervalos a partir das
listas oficiais por legislatura. Campos como genero podem ficar
`nao_informado` ate a coleta completa de detalhes.

## Parquets

Gerar Parquets equivalentes:

- `processed/parlamentares/v1/parquet/parlamentares.parquet`;
- `processed/parlamentares/v1/parquet/mandatos.parquet`;
- `processed/parlamentares/v1/parquet/filiacoes.parquet`;
- `processed/parlamentares/v1/parquet/parlamentares_periodos.parquet`.

Os Parquets devem preservar as mesmas colunas dos JSONLs, com schema estavel e
valores nulos para campos indisponiveis em uma casa.

## Caderno operacional

- Manter `notebooks/coleta/coleta_parlamentares.ipynb` como caderno Colab
  recomendado para coleta, processamento e auditoria de juncao.
- O caderno deve montar o Google Drive antes de clonar, atualizar ou instalar o
  projeto.
- O caderno deve definir
  `FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data`.
- A validacao curta deve rodar em `--mode prod --sample` para confirmar escrita
  no Drive sem baixar a base completa.
- A coleta completa deve ficar protegida por flag booleana, usar `run_id` fixo
  e passar `--resume`.
- O caderno deve ter celulas para consultar manifest, autosave e log do
  `run_id` fixo.

## Juncao com textos parlamentares

- A juncao oficial deve usar `source`, `parlamentar_id` e data do texto.
- IDs iguais em casas diferentes nunca devem ser unidos sem `source`.
- Textos sem `parlamentar_id` devem ficar sem match automatico.
- Textos com `parlamentar_id` e sem match devem aparecer em
  `unmatched_textos.jsonl`.
- Matches multiplos devem aparecer em `ambiguous_matches.jsonl`.
- A rotina deve calcular cobertura por `source/dataset/documento_tipo/ano`.
- A rotina deve gerar uma visao enriquecida opcional, sem substituir a tabela
  de textos como fonte primaria:
  `processed/textos_parlamentares_enriquecidos/v1/parquet/`.

## Juncao com apartes parlamentares

- `apartes_parlamentares/v1` deve usar `parlamentares_periodos` como fonte
  oficial de genero, partido, UF, cargo e legislatura por data.
- O match preferencial usa `source`, `parlamentar_id` e data.
- Quando o raw da Camara tiver somente nome de aparteante, a reconciliacao por
  nome deve ocorrer no processamento de apartes, nao no coletor.
- Matches por nome devem registrar status explicito:
  `matched`, `name_only` ou `ambiguous`.
- Nenhum campo de genero em apartes pode ser inferido por nome, tratamento,
  pronome, foto ou texto.
- A auditoria de apartes deve reportar cobertura de match para oradores e
  aparteantes separadamente.

## Integracao com atualizacao

Depois de uma atualizacao temporal de qualquer base textual:

1. Rodar as coletas raw de textos.
2. Rodar `coleta.parlamentares.collect` para o mesmo periodo ou para o periodo
   total consolidado.
3. Rodar `processamento.parlamentares`.
4. Rodar `processamento.normalizacao` dos textos.
5. Rodar `processamento.parquet` dos textos.
6. Rodar a auditoria de juncao entre textos e `parlamentares_periodos`.
7. Gerar amostras locais incluindo Parquets de textos e de parlamentares.

Depois de uma atualizacao de apartes:

1. Rodar os coletores raw `senado/plenario_apartes` e/ou
   `camara/plenario_apartes`.
2. Rodar `coleta.parlamentares.collect` se houver novos IDs ou nomes sem
   cobertura suficiente.
3. Rodar `processamento.parlamentares`.
4. Rodar `processamento.apartes_parlamentares`.
5. Revisar `contagens_anuais.csv`, `match_status.csv` e cobertura por casa.

## Integracao com expansao

Ao adicionar nova base textual:

- registrar na spec da base qual campo oficial identifica o parlamentar;
- preservar esse ID no payload bruto;
- normalizar o ID para `parlamentar_id` em `textos_parlamentares/v1`;
- validar cobertura contra `parlamentares/v1`;
- documentar excecoes quando a unidade textual nao tiver autoria parlamentar
  individual, como notas de reuniao sem orador segmentado.

Ao adicionar uma base relacional parlamentar, como apartes:

- registrar qual campo oficial identifica cada participante;
- preservar nomes brutos quando o ID oficial nao existir;
- fazer reconciliacao por nome apenas em processamento auditavel;
- usar `parlamentares/v1` como unica fonte de genero normalizado.

## Limites

- A fonte oficial costuma expor sexo, nao necessariamente identidade de genero
  autodeclarada. A coluna `genero` e uma normalizacao operacional desse campo e
  deve manter `sexo_original` para transparencia.
- Historicos partidarios e de exercicio podem ser incompletos ou variar entre
  endpoints. O manifest deve registrar endpoints faltantes e divergencias.
- Dados atuais nao devem sobrescrever silenciosamente dados historicos. Para
  analise por data, usar sempre `parlamentares_periodos`.
- Servicos depreciados do Senado devem ser detectados pelos cabecalhos
  `Deprecation`, `Sunset` e `Link`, com registro no manifest.

## Concorrencia operacional

- Pode rodar em paralelo com coletores de textos, pois escreve em
  `raw/camara/parlamentares/` e `raw/senado/parlamentares/`.
- O `run_id` deve ser distinto dos outros notebooks ativos, porque logs e
  manifests sao globais por `run_id`.
- Nao rodar duas instancias de `coleta.parlamentares.collect` com o mesmo
  `run_id` ao mesmo tempo.
- Em `--resume`, o coletor deve pular endpoints ja gravados para o mesmo
  `run_id`, sem pular registros de outro `run_id`.
