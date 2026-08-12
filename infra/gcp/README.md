# Infraestrutura GCP — G01 a G04

Este diretório declara a fundação aprovada em G01, o job G03 e o serviço Marimo
G04. O backend e o provider fixam o projeto `falando-nela-pedblan`; o projeto
ativo do `gcloud` não participa da escolha do alvo. O uso cotidiano, acesso,
rollback, custo e diagnóstico estão em `docs/operacao_cloud_first.md`.

## Validação local

```bash
tofu -chdir=infra/gcp init -backend=false -input=false
tofu -chdir=infra/gcp fmt -check -recursive
tofu -chdir=infra/gcp validate
tofu -chdir=infra/gcp test
```

`tofu test` usa provider simulado e não acessa nem altera a GCP.

## Gate G01-B — bootstrap do state

Os comandos abaixo são o conteúdo revisável do gate; documentá-los não
autoriza executá-los. Imediatamente antes da aprovação, é obrigatório repetir
os readbacks e a verificação global dos dois nomes.

```bash
gcloud storage buckets create gs://falando-nela-pedblan-tfstate \
  --project=falando-nela-pedblan \
  --location=southamerica-east1 \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --soft-delete-duration=7d

gcloud storage buckets update gs://falando-nela-pedblan-tfstate \
  --project=falando-nela-pedblan \
  --versioning \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --soft-delete-duration=7d

gcloud storage buckets describe gs://falando-nela-pedblan-tfstate \
  --project=falando-nela-pedblan
```

Somente depois do readback íntegro o backend pode ser inicializado e o bucket
importado. As quatro variáveis públicas devem coincidir com `config/gcp.toml`;
`billing_account_id` e `operator_principal` entram apenas pela sessão local.

## Gate G01-C — plano e apply

Cloud Resource Manager é uma dependência circular do provider: ela precisa
estar habilitada para que o provider consiga ler o projeto enquanto gerencia
`google_project_service`. Portanto, antes do plano de G01-C, ela é habilitada
por um único comando explícito e imediatamente importada no state:

```bash
gcloud services enable cloudresourcemanager.googleapis.com \
  --project=falando-nela-pedblan

tofu -chdir=infra/gcp import \
  'google_project_service.required["cloudresourcemanager.googleapis.com"]' \
  falando-nela-pedblan/cloudresourcemanager.googleapis.com
```

Esse bootstrap não autoriza nenhuma outra API ou recurso e deve produzir um
plano posterior sem recriação da API importada.

O plano deve usar token curto da conta operadora, variáveis explícitas e o
state remoto já importado. O arquivo `*.tfplan` é local e ignorado. Antes do
apply, o JSON do plano deve ser revisado e aprovado humanamente; o apply recebe
o plano binário aprovado e não cria um segundo plano implícito.

Variáveis obrigatórias:

```text
project_id         = falando-nela-pedblan
project_number     = 818569314985
region             = southamerica-east1
state_bucket       = falando-nela-pedblan-tfstate
data_bucket        = falando-nela-pedblan-data
billing_account_id = valor obtido por readback
operator_principal = user:conta obtida por readback
```

Nenhuma etapa deste diretório altera `gcloud config configurations`, grava ADC
ou cria chave JSON de service account.

## G03 — Artifact Registry, build e Cloud Run Job

O estado sem `pipeline_image` declara somente a fundação G03: três APIs,
repositório Docker regional com tags imutáveis, contas `fn-builder` e
`fn-pipeline` e IAM condicionado. Informar conjuntamente `pipeline_image`,
`pipeline_operation_id` e `pipeline_revision` acrescenta o job apontando para
um digest já existente.

Validação sem rede ou efeito remoto:

```bash
tofu -chdir=infra/gcp fmt -check -recursive
tofu -chdir=infra/gcp init -backend=false -input=false
tofu -chdir=infra/gcp validate
tofu -chdir=infra/gcp test
```

O gate humano único de G03 pode autorizar a sequência abaixo, desde que os dois
planos permaneçam dentro do diff descrito nas specs, haja apenas um build e uma
execução e a estimativa total permaneça abaixo de US$ 0,10:

1. revisar e aplicar o plano da fundação G03, ainda sem job;
2. enviar um build com `deploy/g03/cloudbuild.yaml`, pelo comando abaixo;
3. obter o digest por readback do Artifact Registry;
4. revisar e aplicar o plano final com a imagem por digest, operation ID e
   revisão preenchidos em conjunto;
5. executar `fn-parquet-pilot` uma vez em `southamerica-east1` e comparar o
   manifest publicado com a validação local.

O build usa a service account `fn-builder` declarada no próprio YAML e envia
logs apenas ao Cloud Logging. Seu pacote-fonte fica sob o prefixo operacional
`operations/builds/g03/` do bucket já existente, que `fn-builder` pode somente
ler. O runtime usa `fn-pipeline`; nenhuma das duas tem chave exportável.
Documentar esses comandos não autoriza executá-los.

```bash
REVISION="$(git rev-parse HEAD)"
IMAGE_URI="southamerica-east1-docker.pkg.dev/falando-nela-pedblan/falando-nela/parquet-pilot"

gcloud builds submit . \
  --project=falando-nela-pedblan \
  --region=southamerica-east1 \
  --config=deploy/g03/cloudbuild.yaml \
  --gcs-source-staging-dir=gs://falando-nela-pedblan-data/operations/builds/g03/source \
  --substitutions="_REVISION=${REVISION},_IMAGE_URI=${IMAGE_URI}"
```

## G04 — app privado Marimo para o recorte G03

O app G04 usa uma imagem dedicada em `deploy/g04`. A imagem roda o notebook em
`marimo run` com `host=0.0.0.0` e `port=8080`.

```
REVISION="$(git rev-parse HEAD)"
IMAGE_URI="southamerica-east1-docker.pkg.dev/falando-nela-pedblan/falando-nela/marimo-primeiro"

gcloud builds submit . \
  --project=falando-nela-pedblan \
  --region=southamerica-east1 \
  --config=deploy/g04/cloudbuild.yaml \
  --gcs-source-staging-dir=gs://falando-nela-pedblan-data/operations/builds/g04/source \
  --substitutions="_REVISION=${REVISION},_IMAGE_URI=${IMAGE_URI}"
```

Após `marimo_image` apontar para a referência por digest em `pipeline`:

1. `tofu -chdir=infra/gcp plan` com variável `marimo_image=<.../marimo-primeiro@sha256:...>`
2. revisar o plano para: `fn-marimo`, IAM `roles/run.invoker` apenas para
   operador e ausência de binding público;
3. aprovar, aplicar e registrar operação de deploy;
4. validar fumaça autenticada contra `fn-marimo` e URL confirmando 30 registros.
