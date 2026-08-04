# Requisitos — refundação local-first do Falando Nela

## Estado

Contrato aprovado pelo usuário em `2026-08-03` para implementação incremental.
A aprovação não autoriza chamadas às fontes oficiais, recursos pagos, exclusões
ou troca da branch principal; esses efeitos conservam seus gates próprios.

## Objetivo

Refundar o projeto no mesmo repositório Git `pedblan/falando_nela`, tornando a
máquina local o ambiente operacional padrão, marimo a interface principal de
cadernos, uma amostra anual determinística de 1% o corpus local de trabalho e
a nuvem uma capacidade complementar para operações integrais sob demanda, sem
refazer a coleta nem perder a proveniência já acumulada.

## Identidade e histórico Git

- **RF-GIT-01:** o repositório remoto, seu nome `falando_nela`, sua URL, issues,
  histórico e autoria deverão ser preservados.
- **RF-GIT-02:** a refundação deverá usar commits, branches e tags normais. É
  proibido reescrever a história publicada ou fazer `force-push` para simular
  um repositório novo.
- **RF-GIT-03:** a última revisão estável da arquitetura centrada em Colab será
  marcada com a tag anotada `legacy-colab-final`, depois de o
  trabalho pendente da branch `migrar-para-disco` ser resolvido e validado.
- **RF-GIT-04:** a arquitetura local-first só poderá substituir `main` depois
  dos gates definidos em `validation.md`. Até lá, deverá evoluir em branches
  próprias sem misturar alterações não relacionadas.
- **RF-GIT-05:** o checkout local chamado `falando_nela` será a pasta canônica
  do projeto. A pasta irmã `falando_nela_refundacao` será apenas uma worktree
  temporária para desenvolver e validar a linha local-first; ela não constitui
  outro repositório, outra história nem uma nova raiz de dados. Essa worktree
  local é independente da pasta homônima de reserva existente no Google Drive.
- **RF-GIT-06:** depois de a linha local-first ser integrada e publicada em
  `main`, o checkout `falando_nela` será atualizado por fast-forward e validado
  no mesmo commit remoto. A worktree `falando_nela_refundacao` só poderá ser
  removida quando não contiver alterações ou commits exclusivos e deverá ser
  retirada com `git worktree remove`, nunca por exclusão direta da pasta.

## Preservação e migração dos dados

- **RF-DATA-01:** a refundação não fará uma nova coleta histórica. Durante a
  migração, nenhuma chamada aos portais da Câmara, Senado ou Congresso será
  permitida.
- **RF-DATA-02:** o raw existente continuará sendo a fonte de verdade. A
  importação deverá registrar caminho de origem, tamanho, formato, contagem de
  registros e SHA-256 antes de qualquer transformação.
- **RF-DATA-03:** a população analítica integral terá data substantiva igual
  ou posterior a `2010-01-01`. A seleção será feita pela data contratual do
  registro, não apenas pelo ano presente no nome do arquivo. O corpus local
  padrão será uma amostra dessa população, não uma nova população canônica.
- **RF-DATA-04:** arquivos de metadados mistos poderão ser preservados
  integralmente quando forem necessários à descoberta ou proveniência de
  registros de 2010 em diante. Registros anteriores a 2010 presentes nesses
  arquivos não poderão entrar silenciosamente no snapshot analítico ativo.
- **RF-DATA-05:** dados anteriores a 2010 serão retirados da área local ativa,
  mas não serão apagados pela tarefa de refundação. A eventual exclusão local
  exigirá tarefa própria, backup imutável completo, restauração verificada,
  inventário de dependências e aprovação humana explícita.
- **RF-DATA-05A:** a limpeza R09, autorizada separadamente em `2026-08-03`,
  poderá retirar cópias antigas já substituídas desde que use apenas Lixeiras
  recuperáveis, preserve a árvore canônica reconciliada e registre alvos por
  caminho ou ID. Essa autorização não permite esvaziar as Lixeiras.
- **RF-DATA-06:** a migração deverá ser retomável e idempotente. Reexecutar a
  mesma operação com o mesmo `operation_id` não poderá duplicar, substituir ou
  reinterpretar registros já reconciliados.
- **RF-DATA-07:** toda operação de migração produzirá manifest versionado com
  entradas aceitas, rejeitadas e mantidas apenas por proveniência; hashes do
  conteúdo de origem e do objeto armazenado; contagens; parâmetros; commit do
  código; início, término e estado.

## Importação do Google Drive

- **RF-IMPORT-01:** a fonte inicial será a pasta raw atualmente aprovada no
  Drive, ID `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`, sob
  `falando_nela_arquivo/data/raw`. O projeto antigo foi renomeado de
  `falando_nela` para `falando_nela_arquivo` em `2026-08-03`, preservando o ID
  de sua raiz `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB`, o conteúdo e a posição no
  Meu Drive. O ID do raw deverá ser repetido no manifest e confirmado
  humanamente antes do primeiro download.
- **RF-IMPORT-02:** o inventário G01
  [`inventario_arquivos.csv`](https://drive.google.com/file/d/12s9Rs4iLVEH9locUUqvSzrwFQh5ZJNL1/view)
  será a baseline da importação. A medição de `2026-08-03` registra 2.891
  arquivos e 13,68 GiB: 5,07 GiB em partições de 2010 em diante, 1,63 GiB em
  partições anteriores e 6,98 GiB sem ano no caminho.
- **RF-IMPORT-03:** a população de leitura usada para formar a amostra incluirá
  partições de 2010 em diante e os arquivos sem ano ainda não classificados,
  totalizando no máximo 12,05 GiB na baseline. Essa população será lida em
  streaming do Drive ou em staging cloud e não será materializada
  integralmente no disco interno por default.
- **RF-IMPORT-04:** a importação usará um remote `rclone` somente leitura,
  listagem estruturada e leitura em streaming. `copy` só será permitido quando
  um artefato de origem inteiro pertencer à seleção; `sync`, `move`, exclusão,
  renomeação e upload no Drive serão proibidos. Artefatos locais incompletos
  usarão sufixo temporário e não entrarão no manifest aprovado.
- **RF-IMPORT-05:** antes de materializar, o comando deverá listar o remote,
  comparar o inventário atual com G01 e gerar uma seleção fechada de locators
  de origem. Mudança de tamanho, hash ou população interrompe a operação para
  revisão; não será corrigida por recoleta.
- **RF-IMPORT-06:** o perfil de amostra terá quota local máxima inicial de
  2 GiB e preservará 5 GiB livres como reserva. Durante a importação, contam
  somente raw selecionado, manifests, índices técnicos e temporários próprios;
  derivados posteriores deverão caber no saldo da mesma quota. Ultrapassá-la
  bloqueará a publicação e exigirá revisão do contrato.
- **RF-IMPORT-07:** com aproximadamente 27 GiB livres medidos em `2026-08-03`,
  o Mac comporta a amostra anual de 1% e seus derivados dentro dessa quota.
  Uma materialização integral local continuará opcional e exigirá
  `2 × bytes_selecionados + 10 GiB`; para a baseline atual, 34,1 GiB livres ou
  um SSD local adequado.
- **RF-IMPORT-08:** a operação de importação terminará ao publicar os registros
  raw selecionados, sem perda de conteúdo, e seus manifests, índices técnicos
  e provas de integridade. Ela não normalizará, deduplicará semanticamente,
  enriquecerá, analisará nem produzirá Parquet ou banco DuckDB. Compressão gzip
  determinística é apenas representação de armazenamento do mesmo raw.
- **RF-IMPORT-09:** o ledger SQLite e os manifests JSON da operação serão
  exclusivamente técnicos: estados, tentativas, contagens, identidades,
  chaves, locators e hashes. Eles não serão expostos como corpus, derivado
  analítico ou interface de consulta científica.

## Organização canônica do raw no Drive

- **RF-DRIVE-ORG-01:** a pasta raw atual, ID
  `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`, permanecerá imutável durante a
  refundação. Sua raiz antiga agora se chama `falando_nela_arquivo`; a
  organização será feita por cópia para uma nova pasta canônica versionada,
  nunca por movimento ou reorganização in-place do raw.
- **RF-DRIVE-ORG-02:** o destino operacional tem o nome `falando_nela` na
  raiz do Meu Drive e foi criado pelo remote `raw-destination-rw` com escopo
  `drive.file`. Seu ID canônico, confirmado por readback do mesmo cliente
  OAuth em `2026-08-03`, é `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`; o remote
  ficou enraizado nesse ID e a pasta começou vazia. A pasta
  `falando_nela_refundacao`, ID
  `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, é reserva e ficará intocada, fora da
  origem, do destino e dos backups da operação. A raiz lógica publicada será
  `data/raw/v1/`.
- **RF-DRIVE-ORG-03:** origem e destino usarão remotes e credenciais distintos.
  A origem exigirá `drive.readonly`; o destino usará o menor escopo gravável
  compatível com uma pasta dedicada, `drive.file`. A configuração rclone será
  cifrada, privada no filesystem e desbloqueada pelo Chaves do macOS via
  `RCLONE_PASSWORD_COMMAND`; `RCLONE_CONFIG_PASS` será recusado. O programa
  validará somente a projeção de `rclone config redacted`. Como o rclone 1.75
  mascara `root_folder_id` nessa projeção, toda referência remota fixará
  explicitamente o ID aprovado por override local, sem abrir a configuração
  descriptografada. Tokens não entrarão em argumentos, manifests, logs, testes
  ou Git.
- **RF-DRIVE-ORG-03A:** o cliente OAuth pertence ao projeto Google Cloud
  `falando-nela-pedblan`, com Drive API habilitada, tipo desktop e audiência
  externa em teste. O JSON temporário baixado do Console será removido depois
  de as credenciais serem importadas e verificadas na configuração cifrada.
- **RF-DRIVE-ORG-04:** todo arquivo será copiado byte a byte para o mesmo
  caminho relativo sob `data/raw/v1/<source>/<dataset>/`. A organização não
  converterá JSONL, não aplicará gzip, não concatenará runs e não alterará
  envelopes raw.
- **RF-DRIVE-ORG-05:** corpus textual de plenários e comissões conservará a
  periodicidade mensal `ano=YYYY/mes=MM/`. Listas, pautas, detalhes e respostas
  de descoberta permanecerão em `metadata/`; candidatos audiovisuais
  permanecerão em `transcription_queue/`.
- **RF-DRIVE-ORG-06:** o contrato alcança, inicialmente, plenários e comissões
  da Câmara e do Senado, incluindo discursos, apartes, notas taquigráficas,
  eventos de CCJ/CCJC, pareceres de plenário ou comissão e os metadados
  transversais `camara/parlamentares` e `senado/parlamentares`. Bases
  metadata-only não ganharão partição mensal artificial.
- **RF-DRIVE-ORG-07:** antes de copiar, um catálogo congelará origem, destino,
  tamanho, hash disponível, categoria, periodicidade e decisão. Caminho não
  classificável será bloqueado para revisão, não rearranjado por heurística.
- **RF-DRIVE-ORG-07A:** a reconciliação G01 inventariará todos os arquivos antes
  do filtro. Na baseline real, isso significa 2.891 arquivos: 2.887 JSONL
  elegíveis e quatro itens não raw, dois notebooks e dois arquivos sem
  extensão. Estes quatro receberão decisão explícita de exclusão e nunca serão
  tratados como ausência da origem.
- **RF-DRIVE-ORG-07B:** os dois itens sem extensão que o rclone apresenta com o
  mesmo caminho serão distinguidos pelo ID estável do provedor antes da
  reconciliação caminho a caminho. A baseline G01 usa `Untitled` e
  `Untitled (1)`; nenhum sufixo será inferido silenciosamente. Quando a baseline
  não contiver IDs e os objetos tiverem caminho visível, tamanho, hash e decisão
  iguais, a reconciliação preservará todos os IDs em um grupo de equivalência
  ligado ao conjunto de locators da baseline, sem fabricar uma correspondência
  individual impossível de provar.
- **RF-DRIVE-ORG-08:** a única mutação remota permitida será cópia imutável para
  um destino ausente. `sync`, `move`, `delete`, `purge`, substituição e limpeza
  da origem serão proibidos. A cópia não forçará operação server-side entre os
  remotes: os bytes serão transferidos em streaming pelo cliente para manter
  compatibilidade com o escopo mínimo do destino.
- **RF-DRIVE-ORG-09:** a execução começará com dry-run e um lote sentinela
  pequeno. Lotes posteriores só avançarão depois de reconciliar caminhos,
  tamanhos e hashes do lote anterior.
- **RF-DRIVE-ORG-10:** a cópia termina somente depois de catálogo de destino,
  igualdade com a origem e retomada sem duplicação. A árvore antiga continuará
  preservada; eventual retirada será outra tarefa com restore e aprovação.

## Amostra anual local de 1%

- **RF-SAMPLE-01:** o perfil local padrão será
  `sample_annual_1pct`, construído somente a partir do raw integral preservado.
  Ele servirá a desenvolvimento, testes, inspeção e exploração preliminar.
- **RF-SAMPLE-02:** a unidade de seleção será o registro raw completo, nunca o
  arquivo. Os estratos serão a combinação
  `source × dataset × record_type × substantive_year` para cada ano a partir
  de 2010.
- **RF-SAMPLE-03:** em cada estrato não vazio serão selecionados exatamente
  `max(1, ceil(N × 0.01))` registros, onde `N` é a população reconciliada do
  estrato no inventário congelado da operação. Esse arredondamento define a
  quota exata da meta de 1%; estratos pequenos poderão, portanto, ter fração
  observada superior a 1%.
- **RF-SAMPLE-04:** a identidade canônica sempre incluirá
  `(source, dataset, record_type, substantive_year)` e usará, nesta ordem,
  identificador oficial já presente no envelope raw ou a tupla
  `(relative_path, record_number, raw_checksum)`. Ausência de identidade
  estável bloqueará o registro e será relatada; não será substituída por
  posição instável ou texto normalizado.
- **RF-SAMPLE-05:** a chave de ordenação será
  `SHA-256("falando-nela-amostra-anual-v1\0" + identidade_canônica)`. Em cada
  estrato serão escolhidas as `k` menores chaves; empates serão resolvidos pela
  identidade canônica. O algoritmo e a seed são parte do contrato e não podem
  mudar silenciosamente.
- **RF-SAMPLE-06:** registros sem ano substantivo formarão o estrato auxiliar
  `undated` por fonte, dataset e tipo. Sua amostra de 1% servirá apenas à
  validação de proveniência e não entrará no corpus analítico anual.
- **RF-SAMPLE-07:** rejeições conhecidas, conflitos de schema e outros casos
  sentinela serão preservados num conjunto separado `sentinels`. Eles não
  contarão para o 1% nem para estatísticas produzidas sobre a amostra.
- **RF-SAMPLE-08:** a seleção será feita em duas passagens recuperáveis: a
  primeira conta os estratos e persiste identidades e chaves; a segunda
  materializa somente os registros do manifest congelado. Nenhuma etapa
  seguinte recalculará a população implicitamente.
- **RF-SAMPLE-09:** o manifest da amostra registrará `sample_id`, versão do
  contrato, seed, fingerprint do inventário integral, população e selecionados
  por estrato, identidades, chaves, locators raw, hashes, bytes, estados,
  tentativas e proveniência de Drive ou Cloud.
- **RF-SAMPLE-10:** os estados das etapas serão `pending`, `running`,
  `completed`, `failed`, `blocked` ou `cancelled`. Retomada reutilizará etapa
  concluída somente quando entrada, configuração, versão e hashes coincidirem;
  mudança no inventário invalida seleção, materialização e derivados.
- **RF-SAMPLE-11:** qualquer tabela, gráfico, caderno ou exportação baseada no
  perfil de 1% será rotulada `AMOSTRA ANUAL DE DESENVOLVIMENTO — NÃO É O CORPUS
  INTEGRAL`. Resultados científicos finais exigirão execução no universo
  integral ou uma spec metodológica que aprove explicitamente inferência por
  amostragem.
- **RF-SAMPLE-12:** a amostra não será extrapolada por multiplicação simples,
  não substituirá auditorias de cobertura e não autorizará exclusão do raw
  integral remoto.
- **RF-SAMPLE-13:** “anual” significa uma amostra estratificada por ano
  substantivo, e não uma agenda de importação executada uma vez por ano. Cada
  novo snapshot aprovado do inventário produzirá um `sample_id` imutável; uma
  mudança na população nunca alterará uma amostra publicada no próprio lugar.

## Armazenamento local

- **RF-STORE-01:** dados integrais e de produção ficarão fora do clone Git. A
  raiz será obrigatoriamente fornecida por `FALANDO_NELA_DATA_ROOT`; não haverá
  caminho pessoal ou de Colab como default de produção. A única exceção dentro
  do clone será `<repo>/data_samples`, exatamente para os profiles `local` e
  `sample_annual_1pct`; ela será integralmente ignorada pelo Git e nunca poderá
  receber o profile `full` ou execução `cloud`.
- **RF-STORE-02:** a raiz terá as áreas
  `raw/sample_annual_1pct/<sample_id>/`, `sentinels/`, `operations/`,
  `processed/`, `snapshots/`, `cache/` e `tmp/`. Somente `cache/` e `tmp/`
  serão descartáveis.
- **RF-STORE-03:** arquivos raw em escrita permanecerão `.jsonl`. Depois do
  fechamento e da validação da partição, poderão ser promovidos atomicamente
  para `.jsonl.gz`; leitores oficiais deverão aceitar os dois formatos.
- **RF-STORE-04:** a compressão de raw deverá preservar um
  `sha256_uncompressed` comparável ao arquivo de origem e um
  `sha256_stored_object` do `.gz`. Compactação nunca autoriza alterar, ordenar,
  limpar ou normalizar registros.
- **RF-STORE-05:** derivados tabulares canônicos usarão Parquet com compressão
  Zstandard. Arquivos DuckDB serão índices ou áreas de trabalho reconstruíveis,
  salvo contrato posterior que os promova explicitamente.
- **RF-STORE-06:** o perfil local deverá operar num Mac com 8 GiB de RAM. O
  default do DuckDB será limite de 4 GiB, no máximo quatro threads e spill em
  `tmp/`; toda operação integral fará preflight de espaço livre antes de abrir
  saídas temporárias.
- **RF-STORE-07:** nenhuma etapa trabalhará diretamente dentro de uma pasta
  sincronizada pelo Drive ou Dropbox.

## Código, comandos e cadernos

- **RF-CODE-01:** regras reutilizáveis ficarão no pacote
  `src/falando_nela/`; cadernos não duplicarão coletores, migração,
  normalização, validação, backup ou lógica científica.
- **RF-CODE-02:** a interface operacional pública será o comando
  `falando-nela`, com subcomandos explícitos e não interativos para inventário,
  migração, validação, execução de pipeline e backup.
- **RF-CODE-03:** comandos potencialmente mutáveis exigirão `operation_id`,
  `--dry-run` quando aplicável e confirmação literal para exclusões ou gastos.
- **RF-CODE-04:** marimo será o formato primário de caderno. Cada caderno será
  um arquivo `.py`, passará em `marimo check` e poderá executar em modo script
  com parâmetros e fixtures sem depender de cliques ou estado oculto.
- **RF-CODE-05:** o primeiro recorte vertical implementará o estrato
  `senado × plenario_discursos × pronunciamento_texto × substantive_year` para
  o primeiro ano não vazio a partir de 2010, usando exatamente o algoritmo de
  1% aprovado.
- **RF-CODE-06:** esse recorte deverá demonstrar, de ponta a ponta, leitura do
  raw, validação, materialização Parquet, consulta DuckDB, inspeção em marimo e
  backup restaurável.
- **RF-CODE-07:** módulos legados só serão portados quando o recorte atual
  precisar deles e houver teste que caracterize o comportamento preservado.
  Não haverá conversão automática em massa dos notebooks `.ipynb`.
- **RF-CODE-08:** processamento e cadernos consumirão somente raw local já
  publicado por uma importação concluída, em outro `operation_id`; eles não
  acessarão o Drive de origem nem acrescentarão derivados à operação de
  importação.

## Backup e restauração

- **RF-BACKUP-01:** o primeiro destino será Google Drive, acessado por `rclone`;
  a configuração deverá permitir trocar o remote por Dropbox sem mudar o
  pipeline de dados.
- **RF-BACKUP-02:** cada backup será gravado em um prefixo imutável
  `falando_nela/backups/<backup_id>/` usando cópia, nunca sincronização que
  propague exclusões.
- **RF-BACKUP-03:** o backup incluirá raw ativo, manifests, schemas, snapshots
  não reconstruíveis e um catálogo SHA-256. Não incluirá `.git`, ambientes,
  caches, temporários nem arquivos DuckDB reconstruíveis.
- **RF-BACKUP-04:** um backup só será considerado válido depois de restaurado
  em diretório vazio e reconciliado por caminhos, tamanhos, contagens e hashes.
- **RF-BACKUP-05:** credenciais e configuração do `rclone` ficarão fora do
  repositório e dos manifests. A configuração será cifrada e sua senha será
  recuperada pelo gerenciador de credenciais do sistema, nunca armazenada em
  variável de ambiente de valor secreto.

## Computação complementar no Google Cloud

- **RF-CLOUD-01:** Google Cloud será tratado como executor remoto, não como
  memória anexada ao Mac e não como fonte de verdade dos dados.
- **RF-CLOUD-02:** o mesmo entrypoint `falando-nela` deverá executar localmente
  e em container Linux. O núcleo do pipeline não poderá importar APIs do
  Google Cloud.
- **RF-CLOUD-03:** jobs fechados e retomáveis usarão Google Cloud Batch; Cloud
  Storage servirá apenas para staging de entradas e saídas do job. Google Drive
  não será montado no runtime.
- **RF-CLOUD-04:** o primeiro piloto remoto repetirá a seleção de 1% do recorte
  vertical aprovado, deverá produzir o mesmo raw amostral, manifest e hashes
  da execução local e terá teto total de US$ 5,00. Ele dependerá de estimativa
  atualizada e autorização humana imediatamente antes da submissão.
- **RF-CLOUD-05:** recursos temporários deverão ser apagados automaticamente
  após o download e a verificação das saídas. Custos residuais de imagens,
  discos, IPs, logs e objetos de staging deverão ser inventariados.
- **RF-CLOUD-06:** Spot VMs só poderão ser usadas depois de o job provar
  retomada segura e idempotência diante de interrupção.
- **RF-CLOUD-07:** operações integrais usarão um profile `full` explícito,
  staging próprio e novo `operation_id`. O profile `sample_annual_1pct` nunca
  será promovido para full apenas mudando um parâmetro escondido no caderno.

## Segurança e auditabilidade

- **RF-SEC-01:** chaves, tokens OAuth, credenciais GCP, configuração do rclone e
  URLs assinadas não entrarão em código, cadernos, logs, manifests ou Git.
- **RF-SEC-02:** OpenAI continuará sendo acessada apenas por módulos e gates já
  aprovados. A refundação não autoriza novas chamadas, novos modelos nem a
  reaplicação das operações v3 existentes.
- **RF-SEC-03:** cada resultado deverá registrar commit, ambiente, parâmetros,
  entradas, saídas, duração e, quando aplicável, uso e custo externo.

## Compatibilidade e corte

- **RF-COMPAT-01:** missão científica, identificadores de fonte, proveniência e
  contratos v3 já aprovados serão preservados. Mudanças científicas ou de
  schema exigirão specs próprias.
- **RF-COMPAT-02:** a linha local-first poderá ler raw legado, mas não precisará
  reproduzir caminhos `/content/drive/...`, montagem do Drive ou estado de
  células do Colab.
- **RF-COMPAT-03:** notebooks e geradores Colab só poderão ser removidos em
  tarefa posterior, após inventário de referências e prova de que os caminhos
  substitutos cobrem o comportamento ainda necessário.
- **RF-COMPAT-03A:** em R09, os notebooks rastreados não serão removidos: ficam
  explicitamente classificados como material histórico de consulta. Notebooks
  encontrados apenas nas raízes antigas do Drive serão copiados e reconciliados
  numa biblioteca canônica antes da limpeza dessas raízes.
- **RF-COMPAT-04:** a troca de `main` exigirá documentação local-first,
  instalação limpa, recorte vertical aprovado, restauração de backup e
  ausência de dependência operacional obrigatória do Colab.
- **RF-COMPAT-05:** remover a worktree temporária depois do corte não significa
  remover código legado nem dados. O legado continuará recuperável pela tag
  `legacy-colab-final`, e suas remoções permanecerão submetidas a tarefas e
  gates próprios.

## Não requisitos

- Refazer o corpus histórico ou corrigir lacunas de coleta.
- Redesenhar o schema normalizado v3 ou iniciar uma nova análise científica.
- Migrar todos os notebooks antes de existir necessidade comprovada.
- Publicar dataset, site ou aplicação web.
- Apagar dados, branches, tags, releases ou o histórico Git durante a
  refundação.
- Tornar Google Cloud, Drive ou Dropbox requisito para testes locais.
- Tratar a amostra anual de 1% como dataset científico definitivo sem contrato
  metodológico próprio.
