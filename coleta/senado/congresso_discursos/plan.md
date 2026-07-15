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
- Gravar cada pronunciamento consolidado como `pronunciamento_texto` em
  `ano=YYYY/mes=MM/{run_id}.jsonl`.
- Se texto por pronunciamento nao estiver disponivel, usar texto/notas da sessao como proximo caminho antes de fila de transcricao.
- Usar checkpoint por particao mensal para retomada.

## Caminho histórico oficial

Na recuperação explícita de 2015–2016, adicionar
`--discovery-strategy historical-official`. O coletor preserva o probe mensal,
percorre o índice oficial completo por autor, valida contagens e paginação,
retém apenas linhas cuja casa exibida seja `Congresso Nacional`, reconcilia
por `CodigoPronunciamento` e usa o endpoint oficial de texto já compartilhado
com o Senado. A enumeração por senador é apenas controle diagnóstico, pois não
cobre deputados e autoridades que podem falar em sessões conjuntas.

## Auditoria de cobertura de senadores

A auditoria por CodigoParlamentar também pode consultar casa CN para confirmar
que discursos de senadores estejam no raw. Ela não é a população completa do
Congresso: deputados e autoridades podem aparecer somente no raw ou na
descoberta de sessões. Assim, somente IDs da fonte por senador ausentes do raw
são lacunas; IDs adicionais no raw são informativos.

Essas lacunas devem usar coleta.senado.backfill_discursos_por_codigo com house
CN e a população fechada senator_endpoint_missing_ids.jsonl. A chave é
CodigoPronunciamento; CodigoParlamentar é somente proveniência. Isso completa
senadores sem substituir a descoberta de deputados e autoridades.

## Recuperação de texto no Diário do Congresso (CN/2010)

O raw pode conter um `CodigoPronunciamento` sem corpo textual: presença do ID
não é cobertura analítica. Para os códigos CN de 2010 que continuarem sem
`texto`/`TextoIntegral`, o caderno 09 deve produzir uma população fechada que
preserve `CodigoPronunciamento`, data e o objeto oficial `pronunciamento`.

`coleta.senado.recuperar_textos_diario` recupera somente essa população. Para
cada código, ele seleciona a publicação declarada `DCN`, consulta o acervo de
diários do Senado explicitamente com `tipDiario=2` (Congresso Nacional) e baixa
o intervalo de páginas que começa em `PaginaInicial`. Alguns metadados legados
trazem `UrlDiario` com `tipDiario=1`; essa URL não é a seleção autoritativa do
veículo quando a publicação declara `DCN`.

O código, e não o nome, é a identidade do registro. O nome oficial do orador
só delimita o início e o fim de seu trecho dentro do PDF DCN já vinculado ao
código, data e página. Se não houver uma publicação DCN, o PDF não tiver texto
extraível ou o trecho não puder ser delimitado, o item falha e a partição fica
retomável; nunca se grava texto de outro orador como recuperação bem-sucedida.

O cabeçalho pode conter título institucional (por exemplo, `MINISTRO` ou
`VICE-PRESIDENTE`), grafia abreviada ou quebra de linha no nome. A delimitação
aceita essas variações apenas depois de confirmar os tokens do orador. Para
separar fala comum de `Fala da Presidência` do mesmo autor, usa
`TipoUsoPalavra`/tipo do pronunciamento: cabeçalho `PRESIDENTE` só é preferido
para a fala da Presidência. Não há tamanho mínimo: fala breve com cabeçalho
confirmado e corpo não vazio é uma recuperação válida.

O índice atual do Diário pode catalogar uma edição conjunta em data próxima da
`DataPublicacao` histórica. Se a consulta exata não localizar um caderno DCN
que contenha a página declarada, a recuperação pesquisa deterministicamente
até 21 dias antes/depois, aceita somente caderno DCN cujo intervalo contenha
a página e registra no payload a data efetivamente usada e o deslocamento.

Quando o payload histórico por senador não trouxer nome do orador, o
recuperador consulta a página oficial de pronunciamento pelo próprio
`CodigoPronunciamento` para obtê-lo. Essa consulta não descobre nem troca a
identidade do item; apenas fornece o marcador necessário para recortar a página
DCN já escolhida pelo código. Quando necessário, a mesma página fornece o tipo
de uso da palavra para escolher corretamente entre cabeçalho de Presidência e
fala ordinária.

## Saidas

- `data/raw/senado/congresso_discursos/metadata/{run_id}.jsonl`: listas mensais brutas.
- `data/raw/senado/congresso_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`: registros textuais consolidados.
- `data/raw/senado/congresso_discursos/transcription_queue/{run_id}.jsonl`:
  pronunciamentos sem texto oficial e com fonte audiovisual candidata.
- `data/operations/backfills/discursos_plenario_2010/{recovery_id}/congresso_2010_text_missing_population.jsonl`:
  população fixa de códigos CN sem texto antes da recuperação no diário.
- `data/checkpoints/senado/congresso_discursos.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Otimizacao historica

- O endpoint de lista de discursos do Senado aceita janelas mensais, mas
  retorna HTTP 400 para janelas trimestrais ou anuais testadas.
- Portanto, este coletor nao deve prometer preflight `ano -> trimestre -> mes`
  nesse endpoint. A reducao de consultas vazias deve vir do recorte operacional
  `1996-05-01` e da retomada por checkpoint.
- Requisicoes mensais de descoberta ficam em `metadata/`; registros textuais
  continuam restritos a requisicoes mensais em
  `ano=YYYY/mes=MM/`.

## Dev e producao

- `dev`: amostra mensal por default, gravada em `data/dev`.
- `prod`: coleta completa por default, gravada em diretorio externo como Google Drive via `FALANDO_NELA_DATA_ROOT`.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular registros existentes.
