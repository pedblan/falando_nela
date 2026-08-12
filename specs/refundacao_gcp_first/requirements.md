# Requisitos — refundação GCP-first do Falando Nela

## Estado

Contrato aprovado em `2026-08-11`. Aprovações de arquitetura não autorizam
`tofu apply`, habilitação de APIs, criação de recursos, uploads ou gastos. Cada
efeito remoto conserva o gate específico de `plan.md` e `validation.md`.

## Objetivo

Tornar o Google Cloud o ambiente operacional do corpus Falando Nela sem refazer
a coleta histórica: migrar o raw canônico do Drive para armazenamento privado,
processar derivados Parquet por jobs reproduzíveis e disponibilizar cadernos
Marimo privados, mantendo Git como fonte do código e o Drive como arquivo de
rollback.

## Identidade e configuração

- **GF-ID-01:** toda operação GCP usará explicitamente o project ID
  `falando-nela-pedblan`; o projeto ativo do `gcloud` não será fonte de decisão.
- **GF-ID-02:** armazenamento, Artifact Registry, Cloud Run e logs operacionais
  usarão `southamerica-east1`, salvo serviço sem suporte regional equivalente.
- **GF-ID-03:** configuração versionada registrará project ID, região, nomes de
  recursos e prefixos, sem conta pessoal, token, credencial ou billing account.
- **GF-ID-04:** CLI, IaC, scripts e bibliotecas cliente recusarão projeto ausente
  ou divergente antes de qualquer efeito remoto.
- **GF-ID-05:** autenticação e projeto-alvo permanecerão conceitos separados;
  Application Default Credentials não substituirá a seleção explícita do projeto.

## Infraestrutura reproduzível

- **GF-IAC-01:** recursos persistentes serão descritos em HCL sob `infra/gcp/`
  e executados com OpenTofu; alterações manuais posteriores serão tratadas como
  drift e reconciliadas no código.
- **GF-IAC-02:** OpenTofu e o provider Google terão restrições de versão e
  `.terraform.lock.hcl` versionado; `.tfstate`, planos binários e credenciais
  permanecerão fora do Git.
- **GF-IAC-03:** o backend remoto usará o bucket privado
  `falando-nela-pedblan-tfstate`, criado por bootstrap explícito, com acesso
  uniforme, prevenção de acesso público e versionamento.
- **GF-IAC-04:** o bucket de dados será
  `falando-nela-pedblan-data`, classe Standard, região
  `southamerica-east1`, acesso uniforme e prevenção de acesso público.
- **GF-IAC-05:** os dois nomes globais de bucket serão revalidados antes do
  bootstrap; indisponibilidade bloqueará a criação e exigirá registrar novos
  nomes nas quatro specs antes de prosseguir.
- **GF-IAC-06:** APIs serão habilitadas somente na etapa que as utiliza. Storage
  e Service Usage existentes não autorizam antecipar Cloud Run, Artifact
  Registry ou Cloud Build.

## Layout e preservação dos dados

- **GF-DATA-01:** a origem é a árvore canônica `falando_nela/data/raw/v1/` do
  Drive, cuja raiz operacional tem ID
  `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq` e cuja pasta `raw` tem ID
  `1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9`.
- **GF-DATA-02:** a baseline pós-limpeza registra 2.887 objetos,
  14.686.043.352 bytes e catálogo SHA-256
  `6a8395a9fb60a999a97562b7f0c791ac766f161e01664ea549ad52bf36bb0930`.
- **GF-DATA-03:** o destino preservará locators sob
  `gs://falando-nela-pedblan-data/data/raw/v1/`; nenhuma transformação ocorrerá
  durante a cópia.
- **GF-DATA-04:** derivados serão publicados sob `data/processed/v1/`; manifests
  fechados e ledgers ficarão sob `manifests/` e `operations/`. Temporários nunca
  serão promovidos por simples sucesso de upload.
- **GF-DATA-05:** a migração será copy-first, retomável, idempotente e sem
  sobrescrita. `sync`, `move`, exclusão e mutação da origem Drive serão proibidos.
- **GF-DATA-06:** o inventário atual do Drive deverá coincidir com a baseline em
  caminho, contagem, bytes e hashes antes do primeiro upload. Divergência
  interromperá a tarefa; não será reparada por recoleta nem por heurística.
- **GF-DATA-07:** um sentinela fechado precederá a cópia integral. A ampliação
  exigirá reconciliação exata, reexecução idempotente e aprovação humana.
- **GF-DATA-08:** GCS só se tornará fonte oficial depois da cópia integral, da
  reconciliação e do gate humano. Até lá, o Drive permanece fonte oficial.
- **GF-DATA-09:** depois do corte, o Drive será preservado como arquivo somente
  leitura. Exclusão, Lixeira ou esvaziamento do Drive não pertencem a esta
  refundação.
- **GF-DATA-10:** nenhum portal da Câmara, Senado ou Congresso será chamado pela
  migração; atualização temporal futura será uma tarefa separada.

## Segurança e identidades

- **GF-SEC-01:** nenhuma chave JSON de conta de serviço será criada ou
  versionada. Bootstrap local usará identidade do usuário e impersonação
  quando aplicável; runtimes usarão service accounts anexadas ao recurso.
- **GF-SEC-02:** identidades distintas separarão migração, pipeline e app
  Marimo; cada uma receberá apenas leitura ou criação nos prefixos necessários.
- **GF-SEC-03:** a identidade migradora não terá permissão de excluir objetos e
  o transporte recusará substituir objeto já existente.
- **GF-SEC-04:** o serviço Marimo será privado, sem `allUsers`, sem editor remoto
  e com acesso somente aos derivados necessários.
- **GF-SEC-05:** logs não incluirão textos parlamentares integrais, tokens,
  credenciais ou URLs assinadas; registrarão IDs, contagens, hashes, duração e
  erros redigidos.

## Processamento e Marimo

- **GF-RUN-01:** processamento fechado e finito usará Cloud Run Jobs; Google
  Cloud Batch não fará parte do primeiro ciclo.
- **GF-RUN-02:** a primeira execução processará apenas o piloto R03 de 30
  discursos do Senado de 2010 e produzirá Parquet Zstandard determinístico.
- **GF-RUN-03:** cada job receberá project ID, região, bucket, prefixos,
  operation ID, commit e limites de CPU, memória, timeout e tentativas.
- **GF-RUN-04:** outputs serão publicados por novo prefixo imutável; retomada
  reconciliará estado remoto antes de repetir trabalho.
- **GF-MARIMO-01:** cadernos serão arquivos Python versionados em Git, editados
  localmente e validados por `marimo check` e execução como script.
- **GF-MARIMO-02:** a publicação usará `marimo run` em serviço Cloud Run privado,
  com filesystem descartável, zero instâncias mínimas e no máximo uma instância
  no piloto.
- **GF-MARIMO-03:** o app lerá Parquet do GCS e não gravará alterações no
  caderno nem tratará o container como armazenamento persistente.

## Custos e gates humanos

- **GF-COST-01:** o primeiro ciclo terá orçamento operacional máximo de US$ 5,00
  e alerta mensal no projeto; alerta não será tratado como hard cap.
- **GF-COST-02:** antes de cada `tofu apply`, build, upload integral ou execução
  Cloud Run, registrar estimativa, amostra, máximo de tentativas e condição de
  parada.
- **GF-COST-03:** nenhum recurso pago ou persistente será criado sem revisão do
  plano OpenTofu e autorização humana para a etapa exata.
- **GF-COST-04:** três falhas equivalentes sem nova hipótese bloquearão nova
  tentativa automática.

## Compatibilidade

- **GF-COMPAT-01:** histórico Git, tag `legacy-colab-final`, evidências R00–R03
  e R09 e o piloto local permanecerão recuperáveis.
- **GF-COMPAT-02:** o executável local continuará funcional com fixtures e
  testes sem credenciais; testes de CI não acessarão GCP ou Drive.
- **GF-COMPAT-03:** a descrição local-first do código só será alterada no corte
  G05, quando o caminho cloud-first tiver sido comprovado.

## Fora do escopo inicial

- BigQuery, Dataflow, Dataproc, GKE, Vertex AI Workbench e edição remota de
  cadernos;
- conversão em massa dos notebooks Colab/Jupyter;
- mudança de schema global, nova análise científica ou nova coleta;
- remoção de legado ou exclusão de dados no Drive;
- tornar o app Marimo público;
- automação de atualização periódica antes do primeiro recorte vertical.
