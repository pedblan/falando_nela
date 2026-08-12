# Stack técnica — refundação GCP-first do Falando Nela

## Estado

Escolhas aprovadas em `2026-08-11`; G02 tornou o GCS a fonte raw oficial. O
recorte G03 e o app G04 foram validados na GCP. Durante G05, o executável e o
caderno operacional passaram a usar o caminho cloud-first por padrão; a
regressão final e a integração em `main` permanecem pendentes.

## Topologia fixada

| Papel | Escolha |
|---|---|
| Projeto | `falando-nela-pedblan` explícito em toda operação |
| Região | `southamerica-east1` (São Paulo) |
| IaC | OpenTofu 1.12.5, HCL e provider Google bloqueado por lockfile |
| Estado IaC | `gs://falando-nela-pedblan-tfstate` |
| Dados | `gs://falando-nela-pedblan-data` Standard |
| Raw | `data/raw/v1/`, cópia byte a byte do Drive |
| Derivados | `data/processed/v1/`, Parquet Zstandard |
| Jobs | Cloud Run Jobs |
| Cadernos publicados | serviço Cloud Run privado com `marimo run` |
| Catálogo analítico remoto | BigQuery adiado |

Os buckets de state e dados existem em `southamerica-east1`; o raw integral foi
reconciliado no bucket de dados. Artifact Registry, contas do pipeline e Cloud
Run Job ainda não existem antes do gate G03.

## Infraestrutura como código

- `infra/gcp/` conterá providers, APIs, buckets, IAM, service accounts,
  Artifact Registry, Cloud Run e alertas de orçamento.
- OpenTofu usará backend GCS separado. O bucket de estado será o único recurso
  criado por bootstrap explícito fora do próprio estado.
- `.terraform.lock.hcl` será versionado; `.terraform/`, `*.tfstate*`, planos
  binários e arquivos de variáveis pessoais serão ignorados.
- Todo `tofu plan` receberá `project_id=falando-nela-pedblan` e
  `region=southamerica-east1`; o plano será revisado antes do apply.
- Imports serão preferidos a recriação quando um recurso esperado já existir.

## Cloud Storage

O bucket de dados usará acesso uniforme, prevenção de acesso público e classe
Standard. O raw manterá o caminho atual para evitar reescrever locators e será
publicado somente por criação imutável. Manifests SHA-256 próprios continuarão
sendo a prova portátil; MD5/CRC32C do provedor serão evidências adicionais.

O bucket de estado terá acesso ainda mais restrito e versionamento. Seu nome,
localização e proteções serão validados após o bootstrap e antes de
`tofu init`.

## Transporte Drive → GCS

- origem rclone `drive.readonly`, fixada pelo ID canônico do Drive;
- destino GCS autenticado sem chave JSON e fixado pelo bucket explícito;
- `rclone copy --immutable --checksum`, no máximo quatro transferências;
- dry-run, sentinela, cópia em lotes retomáveis e relistagem integral;
- nunca usar `sync`, `move`, delete ou server-side copy entre os backends;
- catálogo final por locator, bytes, hash da origem, hash do destino e ID do
  objeto quando disponível.

Os bytes atravessarão o cliente que executa rclone. A primeira migração poderá
ser iniciada no Mac por usar a credencial Drive já validada; isso não torna o
Mac fonte de dados nem ambiente do pipeline após o corte.

## Containers e execução

- Python 3.13 e dependências resolvidas por `uv.lock` com `--locked`;
- imagem OCI Linux reproduzível, marcada por commit;
- bases da imagem fixadas por digest e runtime não-root (UID 10001);
- Artifact Registry regional `falando-nela`;
- Cloud Build para builds remotos depois de API e orçamento aprovados;
- pacote-fonte de build isolado em `operations/builds/g03/` no bucket de dados;
- service accounts `fn-builder` e `fn-pipeline`, ambas sem chave exportável;
- logs estruturados em Cloud Logging e resultados persistidos somente no GCS.

Cloud Run Jobs será usado antes de Google Cloud Batch porque o recorte inicial é
um container finito, pequeno e sem necessidade comprovada de VMs dedicadas. O
job começará com uma tarefa, sem paralelismo, uma tentativa e limites explícitos.

Referências oficiais:

- [Cloud Run: serviços e jobs](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run)
- [Criação de Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Localizações do Cloud Storage](https://docs.cloud.google.com/storage/docs/bucket-locations)
- [Preços do Cloud Storage](https://cloud.google.com/storage/pricing)
- [Preços do Cloud Run](https://cloud.google.com/run/pricing)

## Marimo

- notebooks permanecem `.py` sob `notebooks/` e não guardam outputs volumosos;
- edição ocorre no Mac com `marimo edit` e revisão normal do Git;
- CI executa `marimo check` e o arquivo como script com fixture;
- publicação usa `marimo run <arquivo> --host 0.0.0.0 -p 8080`;
- serviço Cloud Run exige autenticação, escala a zero e tem máximo de uma
  instância no piloto;
- acesso humano inicial usa caminho autenticado; nenhuma permissão pública é
  concedida;
- o app lê Parquet no GCS com identidade `fn-marimo`, sem acesso de escrita.

## Desenvolvimento local e configuração

`config/gcp.toml` será a fonte versionada dos identificadores não secretos. A
CLI aceitará override explícito, mas falhará se o valor divergir do contrato.
Credenciais ficarão no ADC/gerenciador do sistema; CI local usará fixtures e
não dependerá de ADC.

O perfil local continuará disponível para testes e desenvolvimento. “GCP-first”
significa que dados oficiais, processamento de produção e app publicado vivem
na nuvem, não que cada teste unitário exija rede.

## Tecnologias não adotadas no primeiro ciclo

- BigQuery e Dataform antes de consultas e schema estáveis;
- Google Cloud Batch antes de Cloud Run Jobs demonstrar insuficiência;
- VMs, Workstations, Colab, JupyterHub ou Kubernetes para editar cadernos;
- filesystem montado como contrato de persistência do Cloud Run;
- chaves JSON de service account;
- bucket público ou serviço Marimo anônimo.
