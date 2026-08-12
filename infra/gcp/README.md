# Fundação GCP — G01

Este diretório declara somente a fundação aprovada em G01. O backend e o
provider fixam o projeto `falando-nela-pedblan`; o projeto ativo do `gcloud`
não participa da escolha do alvo.

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
