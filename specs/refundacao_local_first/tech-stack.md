# Stack técnica — refundação local-first do Falando Nela

## Estado

Contrato histórico aprovado em `2026-08-03`. Esta stack descreve a fundação e
as operações concluídas R00–R03 e R09. As escolhas prospectivas para R04–R08
foram substituídas em `2026-08-11` por `../refundacao_gcp_first/` e não devem
orientar novos recursos.

## Ambiente Python

- CPython `>=3.13,<3.14`, compatível com o Python 3.13.7 presente na máquina do
  pesquisador.
- `uv` como gerenciador de Python, ambiente, dependências, grupos e lockfile.
- `pyproject.toml` como contrato de projeto; `.python-version` solicita Python
  3.13; `uv.lock` é versionado.
- Layout de pacote `src/falando_nela/` e entrypoint público `falando-nela`.
- Grupos de dependências separados: núcleo, cadernos, análise, nuvem e
  desenvolvimento. Dependência pesada só entra quando o módulo que a exige for
  aprovado.

O `uv` valida o ambiente contra `pyproject.toml` e o lockfile antes de
`uv run`; o lockfile deve ser usado com `--locked` na validação e na nuvem.
Referência: [projetos e lockfile do uv](https://docs.astral.sh/uv/guides/projects/).

## Layout local do repositório

- `falando_nela/` é o checkout local canônico e, depois do corte R08, deverá
  acompanhar `origin/main` por fast-forward.
- `falando_nela_refundacao/` é uma worktree Git irmã e temporária, vinculada ao
  mesmo repositório, usada somente para desenvolver e validar a refundação.
- O sufixo `/` distingue essa worktree local da pasta homônima de reserva no
  Google Drive; elas não compartilham conteúdo nem finalidade operacional.
- Nenhuma das duas pastas é raiz de produção ou backup dos dados; essas raízes
  permanecem externas ao clone e são configuradas por ambiente.
- Depois do merge, a igualdade entre o commit do checkout canônico e
  `origin/main`, a ausência de trabalho exclusivo na worktree temporária e a
  suíte final deverão ser verificadas antes de executar
  `git worktree remove`.
- A pasta temporária não será apagada diretamente com comandos de sistema de
  arquivos. Sua remoção será registrada pelo Git e não afetará a tag
  `legacy-colab-final`, branches, dados ou backups.

## Núcleo e qualidade

- Biblioteca padrão para paths, streaming JSONL, gzip, hashes, manifests e
  execução de processos.
- `pydantic>=2,<3` somente para contratos persistidos e configuração validada;
  dataclasses permanecem adequadas para objetos internos simples.
- `httpx>=0.28,<1` para futuras atualizações incrementais, fora da migração.
- `pytest>=8,<10` para testes unitários, de contrato e integração com fixtures.
- `ruff` para lint e formatação; CI usa `ruff check` e `ruff format --check`.
- Type hints fazem parte das interfaces públicas. Um verificador estático só
  será acrescentado quando houver uma baseline limpa, em tarefa própria.
- `sqlite3` da biblioteca padrão somente para o ledger transacional das
  operações de importação; não será uma camada analítica.

## Dados locais

- Corpus local padrão: amostra anual determinística de 1% sob
  `raw/sample_annual_1pct/<sample_id>/`.
- Raw aberto: JSON Lines UTF-8 (`.jsonl`).
- Raw fechado: gzip determinístico (`.jsonl.gz`, sem timestamp variável no
  cabeçalho) e hashes do conteúdo descompactado e do objeto armazenado.
- Tabelas canônicas: Parquet com compressão Zstandard e particionamento
  explícito apenas quando definido pelo contrato do dataset.
- `duckdb>=1.4,<2` como motor de consulta e transformação maior que a RAM.
- `pyarrow>=20,<24` para contratos e interoperabilidade Parquet.
- `pandas>=2.2,<3` para compatibilidade com módulos e apresentação existentes;
  Polars não será dependência inicial.

DuckDB consulta Parquet diretamente, aplica projeção e filtros e suporta
spill para disco em workloads maiores que a memória. O perfil local fixa
`memory_limit='4GB'`, `threads=4` e `temp_directory` sob
`FALANDO_NELA_DATA_ROOT/tmp/`; operações sensíveis também evitam preservar
ordem quando ela não fizer parte do contrato. Referências:
[Parquet no DuckDB](https://duckdb.org/docs/stable/data/parquet/overview) e
[processamento maior que a memória](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads).

Arquivos `.duckdb` serão caches ou índices reconstruíveis. Parquet, manifests
e schemas constituirão as saídas portáveis.

## Cadernos

- `marimo>=0.20,<0.21` como ambiente primário de cadernos.
- Cadernos versionados como Python sob `notebooks/`, sem cópia de outputs
  volumosos no Git.
- Execução interativa por `uv run marimo edit` ou `uv run marimo run`.
- Execução verificável por `uv run python <caderno.py>` e
  `uv run marimo check <caderno.py>`.
- Runtime lazy será usado quando uma interação puder disparar cálculo caro;
  cálculo pago ou destrutivo continua exigindo gate explícito no comando de
  domínio.
- Componentes reutilizáveis, queries e algoritmos ficam no pacote; o caderno
  combina parâmetros, chamadas e apresentação.

Marimo armazena o caderno como Python, calcula dependências reativas e permite
executá-lo como script, propriedades que justificam sua adoção no lugar de
`.ipynb` como formato principal. Referência:
[documentação do marimo](https://docs.marimo.io/).

## Configuração e interfaces

Variáveis não secretas padronizadas:

| Variável | Contrato |
|---|---|
| `FALANDO_NELA_DATA_ROOT` | `/Users/pedblan/PycharmProjects/falando_nela/data_samples` para a amostra local; dados integrais permanecem externos |
| `FALANDO_NELA_PROFILE` | `local` ou `cloud`; default `local` |
| `FALANDO_NELA_DUCKDB_MEMORY_LIMIT` | default local `4GB` |
| `FALANDO_NELA_DUCKDB_THREADS` | default local `4` |
| `FALANDO_NELA_TEMP_ROOT` | default `<data-root>/tmp` |
| `FALANDO_NELA_DRIVE_SOURCE` | remote e caminho read-only da origem raw |
| `FALANDO_NELA_DRIVE_SOURCE_FOLDER_ID` | ID esperado da pasta raw de origem |
| `FALANDO_NELA_RCLONE_BACKUP_REMOTE` | remote gravável de backup; default lógico `drive-backup` |
| `FALANDO_NELA_DATA_PROFILE` | `sample_annual_1pct` por default; `full` exige gate explícito |
| `FALANDO_NELA_SAMPLE_SEED` | constante versionada `falando-nela-amostra-anual-v1` |
| `FALANDO_NELA_SAMPLE_LOCAL_QUOTA` | default `2GiB` para amostra e temporários próprios |
| `RCLONE_PASSWORD_COMMAND` | comando absoluto que recupera do Chaves do macOS a senha da configuração cifrada |

- Configuração versionável fica em TOML ou JSON sem segredos.
- `.env` poderá ser usado localmente, será ignorado pelo Git e não será lido
  implicitamente em CI ou produção sem biblioteca e contrato aprovados.
- A CLI `falando-nela` retorna código diferente de zero em falha, escreve
  progresso humano em stderr e oferece resultado estruturado em JSON quando
  solicitado.

## Importação do Drive

- `rclone` fornecerá listagem estruturada e streaming da origem para staging
  local identificado; não será necessário copiar cada arquivo remoto inteiro.
- O remote de origem usará escopo OAuth `drive.readonly` e ficará separado do
  remote gravável de backup.
- A pasta aprovada de origem tem ID
  `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`; o caminho humano não substituirá a
  conferência do ID.
- O inventário e a leitura de registros serão feitos em streaming por arquivo;
  não haverá montagem pelo Google Drive Desktop, Colab ou FUSE.
- Somente os registros presentes no manifest congelado da amostra serão
  materializados localmente. Downloads ou streams parciais não entram na raiz
  ativa e usam staging identificado pela operação.
- A interface com o Drive entrega somente raw e metadados técnicos de
  proveniência. Parquet, DuckDB, normalização, análise e apresentação começam
  apenas depois da publicação raw, em outra operação e sem acesso ao Drive de
  origem.
- `rclone sync`, `move`, `delete` e qualquer operação server-side mutável são
  proibidos no remote de origem.

### Organização copy-first no Drive

- O remote `raw-source-ro` aponta para o raw da árvore antiga com
  `scope=drive.readonly` e `root_folder_id=1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`,
  sob `falando_nela_arquivo`; o remote `raw-destination-rw`, com
  `scope=drive.file`, criou na raiz do Drive a nova pasta operacional
  `falando_nela`, ID `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`, vazia e dedicada
  à árvore `data/raw/v1/`.
- `falando_nela_refundacao` é pasta de reserva e não será usada por nenhum dos
  remotes. Como `drive.file` enxerga os itens criados pelo próprio aplicativo,
  o remote gravável criará a pasta operacional antes de seu ID ser congelado
  em `root_folder_id`.
- O plano de cópia será um JSONL imutável com uma linha por arquivo, ordenado
  por destino. Cada linha conterá locators de origem e destino, bytes, hashes,
  classe de layout e periodicidade, sem credenciais.
- O transporte real usará `rclone copy --files-from0 --immutable --checksum`
  sobre lotes congelados, com até quatro transferências client-side. `--dry-run`
  antecederá toda escrita. A opção `--server-side-across-configs` não será usada:
  os dados atravessarão o cliente rclone em streaming, sem exigir que a
  credencial `drive.file` do destino tenha visibilidade sobre o raw legado.
- Para o dry-run integral, sem efeito remoto, os locators congelados serão
  passados em arquivo NUL-delimited a uma única sessão
  `rclone copy --files-from0 --dry-run --immutable --checksum --retries 1`.
  O relatório `--combined` deverá conter somente `+` e exatamente o conjunto
  planejado; isso evita milhares de processos e não altera o transporte
  individual `copyto` escolhido para a execução real.
- A versão mínima do rclone será `1.64`, que oferece `config redacted`. O
  arquivo de configuração ficará cifrado, com modo `0600` ou mais restrito; a
  aplicação executará `config encryption check` e analisará apenas a projeção
  efêmera de `config redacted`. Todos os comandos usarão
  `--ask-password=false`, e a senha será obtida do Chaves do macOS por
  `RCLONE_PASSWORD_COMMAND`; `RCLONE_CONFIG_PASS` será recusado.
- Como `config redacted` mascara `root_folder_id` no rclone 1.75, cada origem e
  destino será referenciado como remote com override explícito do ID aprovado.
  Assim, o caminho efetivo fica fixado sem ler ou registrar a configuração
  descriptografada.
- A instância instalada é rclone 1.75.0. O cliente OAuth desktop próprio fica
  no projeto Google Cloud `falando-nela-pedblan`; o arquivo cifrado fica em
  `~/Library/Application Support/falando-nela/rclone/rclone.conf`, fora do
  clone, com modo `0600`.
- A retomada inventariará o destino e reconstruirá cada lote somente com os
  objetos ainda ausentes depois de uma tentativa ambígua. Objeto já presente e
  idêntico será reutilizado; objeto presente e divergente bloqueará o lote.
- `falando-nela drive-organize reconcile` gera, antes do dry-run, inventário
  read-only JSONL e relatório de reconciliação sob
  `operations/organize_drive/<operation_id>/`. O fingerprint inclui ID do
  provedor, caminho, tamanho, hashes e modificação. Quando uma baseline sem IDs
  não distingue objetos atuais de mesmo caminho e conteúdo, um mapa JSON
  validado preserva o conjunto dos IDs como grupo de equivalência ligado ao
  conjunto de locators da baseline; ele não inventa uma bijeção individual.
- Textos de plenário e comissão mantêm `ano=YYYY/mes=MM/`; `metadata/` e
  `transcription_queue/` mantêm seus caminhos. O organizador não abre nem
  reserializa o conteúdo para decidir o destino.
- A árvore canônica validada será lida pela credencial `raw-source-ro`, com
  escopo `drive.readonly` e override literal para o ID canônico. A credencial
  gravável não será usada pelo importador local.

### Dimensionamento observado em 2026-08-03

| População do inventário G01 | Arquivos | Tamanho |
|---|---:|---:|
| raw completo | 2.891 | 13,68 GiB |
| partições com ano >= 2010 | 1.679 | 5,07 GiB |
| partições com ano < 2010 | 1.134 | 1,63 GiB |
| arquivos sem ano no caminho | 78 | 6,98 GiB |
| população lida para formar a amostra | 1.757 | 12,05 GiB |

O filesystem interno tem aproximadamente 27 GiB livres. O profile local não
persistirá os 12,05 GiB: ele materializará 1% dos registros anuais, com quota
total inicial de 2 GiB e reserva mínima de 5 GiB livres. Portanto, a amostra
cabe confortavelmente no Mac. A taxa por registros não garante 1% dos bytes;
o tamanho real será medido e a quota bloqueará casos patológicos. Uma
materialização integral ainda exigirá 34,1 GiB livres pela baseline atual ou
um SSD local. Ganhos de gzip não serão antecipados.

## Seleção anual de 1%

- A leitura é streaming; nenhum dataframe integral será construído em memória.
- A primeira passagem persiste um ledger técnico SQLite com estrato,
  identidade canônica, chave SHA-256, locator raw e hash do registro.
- A identidade canônica prefixa o identificador oficial ou fallback com
  fonte, dataset, tipo e ano, evitando colisões entre sistemas de origem.
- Uma consulta SQLite calcula `N`, `k=max(1, ceil(N × 0.01))`, ordena por chave
  e identidade e grava o manifest JSON fechado da seleção.
- A segunda passagem materializa somente identidades presentes no manifest,
  preservando o envelope raw completo e seu locator original.
- O índice, o manifest e os artefatos de cada etapa usam escrita temporária e
  promoção atômica. O estado `running` é persistido antes de ler Drive, Cloud
  Storage ou iniciar Batch.
- O manifest distingue operação, etapa e tentativa; registra `remote_id`,
  bytes lidos, custo observado e erro remoto ambíguo quando houver.
- Etapas contratuais da importação: `inventory`, `rank`, `freeze_selection`,
  `materialize_raw`, `validate_raw` e `publish_raw`. Backup e processamento
  usam operações posteriores e independentes.
- `inventory`, `rank` e `materialize_raw` podem retomar por arquivo fechado;
  mudança no fingerprint do inventário invalida as etapas dependentes, nunca
  apenas o arquivo recém-chegado.
- Cada snapshot aprovado gera um novo `sample_id` imutável; “anual” descreve a
  estratificação por ano substantivo, não a periodicidade do job.
- O conjunto `sentinels` permanece separado fisicamente e por metadados para
  não contaminar contagens ou visualizações da amostra.

## Backup

- `rclone` como ferramenta externa de transporte, com remote diferente do
  remote read-only de importação.
- Google Drive como primeiro backend e Dropbox como alternativa configurável.
- `rclone copy`, nunca `sync`, para prefixos de backup imutáveis.
- `--immutable`, `--checksum` quando suportado, dry-run prévio e catálogo
  SHA-256 próprio como defesa contra substituição ou diferenças de backend.
- O remote usa o menor escopo OAuth que permita criar e validar a árvore de
  backup; tokens ficam na configuração cifrada do usuário, fora do projeto, e
  a senha da configuração permanece no gerenciador de credenciais do sistema.

O backend Drive expõe hashes e o comando `copy` não apaga o destino;
`--immutable` falha diante de substituição. Referências:
[backend Google Drive](https://rclone.org/drive/) e
[`rclone copy`](https://rclone.org/commands/rclone_copy/).
O manuseio da configuração segue a
[cifra de configuração](https://rclone.org/docs/#configuration-encryption) e
[`rclone config redacted`](https://rclone.org/commands/rclone_config_redacted/).

## Computação sob demanda

- Imagem OCI Linux reproduzível, construída a partir do `uv.lock` e marcada
  com commit; execução local deve preceder publicação.
- Artifact Registry para imagens e Cloud Storage para staging efêmero.
- Google Cloud Batch para jobs fechados de CPU/RAM; Compute Engine interativo
  só será avaliado em tarefa separada se Batch não atender um caso comprovado.
- Autenticação por Application Default Credentials e contas de serviço com
  privilégio mínimo; nenhuma chave JSON versionada.
- Logs técnicos no Cloud Logging sem payload parlamentar integral ou segredos.
- Recursos por job, timeout, retries, região, bytes de staging e teto de custo
  são parte obrigatória do manifest de submissão.
- Spot VMs permanecem desabilitadas no primeiro piloto.
- O primeiro job cloud reproduz somente o raw do mesmo estrato piloto de 1% e
  compara manifest e conteúdo byte a byte com a seleção local.
- Um job integral usa profile `full`, staging e manifest diferentes. A amostra
  não é expandida em memória para simular o universo completo.

Google Cloud Batch cria e remove os recursos computacionais definidos para o
job; o projeto ainda precisa controlar objetos de staging, imagens e logs que
podem gerar custo residual. Referência:
[execução de jobs no Google Cloud Batch](https://docs.cloud.google.com/batch/docs/create-run-job).

## Git e integração contínua

- O remote permanece `pedblan/falando_nela`; a migração não cria outro
  repositório.
- GitHub Actions executará apenas instalação locked, lint, formatação, testes e
  cadernos em modo script com fixtures pequenas.
- CI não montará Drive, não acessará o corpus privado do pesquisador, não fará
  chamadas às fontes, OpenAI ou Google Cloud e não executará backups.
- Dados, `.venv`, outputs, caches, temporários, credenciais e configuração do
  rclone permanecem ignorados pelo Git.

## Tecnologias deliberadamente não adotadas na fundação

- Bash como lugar da lógica do pipeline; scripts shell poderão apenas envolver
  um único comando Python quando necessário.
- DVC, Git LFS, banco remoto ou data lake como pré-requisito inicial.
- Kubernetes, Airflow, Prefect ou outro orquestrador permanente.
- Conversão em massa de Jupyter para marimo.
- Drive ou Dropbox montado como filesystem de trabalho.
- Google Cloud como ambiente padrão de desenvolvimento.
