# Requisitos operacionais — G01 fundação GCP e sentinela

## Estado

Contrato operacional aprovado para implementação local em `2026-08-11`.
Aplicações remotas permanecem separadas pelos gates G01-B, G01-C e G01-D deste
contrato. G00 foi encerrado no commit `3da1dae`.

## Resultado principal

Declarar e validar a fundação mínima do projeto
`falando-nela-pedblan`, criar seu state remoto de OpenTofu, aplicar somente o
bucket de dados, IAM migrador e alerta de custo, e provar o transporte
Drive→GCS com um lote imutável de três objetos e 78.822 bytes.

## Configuração versionada

- **G01-CFG-01:** `config/gcp.toml` registrará schema version, project ID
  `falando-nela-pedblan`, project number `818569314985`, região
  `southamerica-east1`, nomes dos buckets,
  prefixos, service account migradora, teto mensal e sentinela.
- **G01-CFG-02:** conta pessoal, billing account, access token, credencial,
  arquivo rclone e valores obtidos do ambiente não serão versionados.
- **G01-CFG-03:** todo comando mutável exigirá confirmação literal de project
  ID, bucket e ID da pasta raw; ausência ou divergência bloqueará antes da rede.
- **G01-CFG-04:** o default local do `gcloud` não será alterado nem usado para
  escolher o alvo.

## OpenTofu e recursos

- **G01-IAC-01:** `infra/gcp/` usará OpenTofu `~> 1.12.0` e provider Google
  `~> 7.40.0`, com `.terraform.lock.hcl` versionado.
- **G01-IAC-02:** o provider declarará `project`, `region`, `billing_project` e
  `user_project_override`; o filtro do budget usará o project number
  versionado, e nenhum valor virá do projeto ativo do `gcloud`.
- **G01-IAC-03:** o backend GCS usará bucket
  `falando-nela-pedblan-tfstate` e prefixo `opentofu/g01`.
- **G01-IAC-04:** o bucket de state será criado por um único comando bootstrap
  explícito, protegido antes do import e então importado como
  `google_storage_bucket.tfstate`; ele terá Standard,
  `southamerica-east1`, acesso uniforme, prevenção pública, soft delete de sete
  dias, versionamento, `force_destroy=false` e `prevent_destroy`.
- **G01-IAC-05:** o bucket `falando-nela-pedblan-data` terá Standard,
  `southamerica-east1`, namespace plano, acesso uniforme, prevenção pública,
  soft delete de sete dias, sem versionamento, `force_destroy=false` e
  `prevent_destroy`.
- **G01-IAC-06:** G01 gerenciará somente
  `storage.googleapis.com`, `cloudresourcemanager.googleapis.com`,
  `iam.googleapis.com`,
  `iamcredentials.googleapis.com`, `cloudbilling.googleapis.com` e
  `billingbudgets.googleapis.com`, sempre com `disable_on_destroy=false`.
  Cloud Resource Manager é a dependência mínima usada pelo provider para ler o
  projeto enquanto habilita as outras APIs; ela não autoriza criar recursos
  adicionais. Por circularidade de bootstrap, ela poderá ser habilitada por um
  único comando `gcloud services enable` com projeto explícito e será importada
  imediatamente em seu endereço `google_project_service` antes do novo plano.
- **G01-IAC-07:** a conta `fn-migrator` receberá no bucket de dados somente
  `roles/storage.objectCreator` e `roles/storage.objectViewer`; não receberá
  permissão de exclusão, administração de bucket nem chave JSON.
- **G01-IAC-08:** a conta operadora, fornecida fora do Git, receberá
  `roles/iam.serviceAccountTokenCreator` somente sobre `fn-migrator`.
- **G01-IAC-09:** o budget mensal `falando-nela-gcp-first` terá valor de
  R$ 25,00, moeda imutável da billing account e referência conservadora ao teto
  aprovado de US$ 5,00; terá escopo exclusivo no projeto e alertas de gasto
  atual em 50%, 90% e 100%, mais previsão em 100%.
- **G01-IAC-10:** destinatários padrão por IAM permanecerão habilitados para
  Billing Admins e Owner do projeto; nenhum canal de e-mail pessoal será criado.

## Autenticação sem estado global

- **G01-AUTH-01:** OpenTofu usará token de curta duração da conta operadora;
  rclone usará token de curta duração obtido por impersonação de
  `fn-migrator`.
- **G01-AUTH-02:** tokens existirão apenas em memória/ambiente do subprocesso,
  nunca em argumento serializado, manifest, log, config ou state.
- **G01-AUTH-03:** G01 não executará `gcloud auth application-default login`,
  não gravará ADC e não criará chave de service account.
- **G01-AUTH-04:** conta ativa, project ID, localização e recursos serão
  exibidos antes de cada gate remoto; todo readback repetirá o projeto explícito.

## Interface e operação recuperável

```text
falando-nela gcs-migrate sentinel --through preflight|dry-run|copy \
  --operation-id ID --gcp-config config/gcp.toml \
  --source-catalog CAMINHO --rclone-config CAMINHO \
  --source-folder-id ID --confirm-source-folder-id ID \
  --confirm-project-id falando-nela-pedblan \
  --confirm-bucket falando-nela-pedblan-data \
  --operator-account CONTA
```

- **G01-CLI-01:** `preflight` reconciliará por metadados os 2.887 objetos e
  14.686.043.352 bytes da pasta raw canônica, sem ler conteúdo nem acessar GCS.
  Os dois objetos vazios aprovados terão o SHA-256 do conteúdo vazio derivado
  localmente quando o inventário Drive fornecer somente MD5.
- **G01-CLI-01A:** o contrato declarará separadamente o prefixo físico `v1`
  dentro da pasta raw do Drive. Inventário e cópia partirão desse prefixo, mas
  os locators canônicos continuarão relativos a ele (`camara/...`, `senado/...`),
  sem duplicar `v1` no destino `data/raw/v1`.
- **G01-CLI-02:** `dry-run` executará preflight e confirmará o destino: na
  primeira execução ele deve estar vazio e produzir exatamente três marcadores
  de criação; uma retomada já íntegra produzirá três marcadores de igualdade.
  Qualquer outro estado bloqueará sem upload.
- **G01-CLI-03:** `copy` reutilizará preflight e dry-run íntegros, copiará
  somente a sentinela, reconciliará tamanho, MD5 e SHA-256 e repetirá a cópia
  comprovando zero nova geração. A prova será imediata e curta; G01 não fará
  espera prolongada nem restauração do canário. A restauração amostral continua
  obrigatória em G02.
- **G01-CLI-04:** cada etapa usará `RecoverableOperation`, temporário e promoção
  atômica; artefato alterado invalidará a etapa descendente.
- **G01-CLI-05:** a interface GCS existirá em módulo novo e não alterará o
  comportamento histórico de `drive-organize`.
- **G01-CLI-06:** rclone usará `copy`, `--immutable`, `--checksum`,
  `--check-first`, uma tentativa e no máximo quatro transferências; `sync`,
  `move`, exclusão e criação de bucket pela ferramenta serão impossíveis.
- **G01-CLI-07:** a conta operadora será argumento obrigatório, não será
  serializada, e o remote GCS efêmero declarará o project number versionado.

## Sentinela congelado

| Categoria | Locator destino | Bytes | SHA-256 |
|---|---|---:|---|
| metadata | `data/raw/v1/senado/pareceres_pec/metadata/validacao-senado-pareceres-pec-20260530T002409Z.jsonl` | 868 | `7020492564083d1fea1a7f8532e30676fa4d54d8667e71da547d31abc7954cb0` |
| monthly_text | `data/raw/v1/camara/plenario_discursos/ano=1970/mes=01/prod-historico-camara-plenario.jsonl` | 2.694 | `d352c0bfef547e31c1e13124809e8d5c6a9e7c3fa239966cb9e2a145a9adde84` |
| transcription_queue | `data/raw/v1/senado/plenario_discursos/transcription_queue/prod-senado-plenario-20260518T194535Z.jsonl` | 75.260 | `7b6ba3ae0fbde07c35aa47f6816678195f385e59a01ae6d8c62db07cd6658ffb` |

Os três objetos totalizam 78.822 bytes e são exatamente os sentinelas já
validados na organização R03. A origem será a pasta raw de ID
`1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9`; o Drive permanecerá read-only.

## Custo e interrupção

- **Hipótese:** state pequeno, dois buckets e 78.822 bytes custam menos de
  US$ 0,01 no primeiro mês, excluído consumo anterior do projeto.
- **Amostra mínima:** três objetos, uma categoria estrutural por objeto.
- **Máximo:** um apply aprovado e uma tentativa de upload; repetição apenas
  idempotente para comprovar zero escrita.
- **Limite:** budget mensal de R$ 25,00, referência conservadora ao teto de
  US$ 5,00; alerta não é hard cap.
- **Parada:** qualquer divergência de conta, projeto, região, nome, plano,
  inventário, hash, acesso ou custo bloqueia a etapa sem reparo automático.

## Fora do escopo

- migrar os 2.887 objetos integrais ou tornar GCS fonte oficial;
- habilitar BigQuery, Artifact Registry, Cloud Build, Cloud Run ou Batch;
- criar pipeline, Parquet ou caderno Marimo;
- alterar, excluir ou reconfigurar o Drive;
- criar CI autenticada, chave JSON, KMS, retenção bloqueada ou hard cap.
