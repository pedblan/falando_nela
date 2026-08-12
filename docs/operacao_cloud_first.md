# Operação cloud-first

Este é o guia canônico para operar o recorte GCP-first já implantado do Falando
Nela. O alvo é sempre o projeto `falando-nela-pedblan`, na região
`southamerica-east1`; o projeto ativo do `gcloud` e o projeto de quota do ADC
não substituem esses valores.

O fluxo cotidiano é curto: validar localmente, fazer readback do recurso
envolvido e executar apenas a ação necessária. Testes locais, consultas
read-only e acesso normal ao app existente não exigem um novo gate. Build,
execução de job, `tofu apply`, mudança de IAM ou troca de imagem exigem uma
tarefa delimitada com amostra, máximo de tentativas, limite de custo e
aprovação imediatamente antes do efeito remoto.

## Contrato implantado

| Papel | Recurso |
| --- | --- |
| Projeto e região | `falando-nela-pedblan`, `southamerica-east1` |
| Dados oficiais | `gs://falando-nela-pedblan-data` |
| State OpenTofu | `gs://falando-nela-pedblan-tfstate/opentofu/g01` |
| Imagens | `southamerica-east1-docker.pkg.dev/falando-nela-pedblan/falando-nela` |
| Pipeline | Cloud Run Job `fn-parquet-pilot`, identidade `fn-pipeline` |
| Consulta | Cloud Run Service privado `fn-marimo`, identidade `fn-marimo` |

Os nomes, locators e limites versionados estão em `config/gcp.toml`; recursos e
IAM estão em `infra/gcp/`. ADC autentica a identidade local, mas o código e cada
comando continuam declarando o projeto de destino.

## Desenvolvimento e validação local

Preparar dependências e validar o ambiente não baixa o corpus:

```bash
uv sync --locked --group dev --group cloud --group notebooks
FALANDO_NELA_DATA_ROOT="$PWD/data_samples" uv run falando-nela doctor --json
uv run pytest -q tests/refundacao_gcp_first
uv run --locked --group cloud --group notebooks \
  marimo check notebooks/primeiro_recorte_discursos.py
```

O caderno usa GCS por padrão e requer ADC. Para executar sem credenciais, a
fixture deve ser escolhida explicitamente; falhas não acionam fallback:

```bash
FALANDO_NELA_G04_SOURCE=fixture \
FALANDO_NELA_G04_FIXTURE=/caminho/fixture.parquet \
uv run --locked --group cloud --group notebooks \
  python notebooks/primeiro_recorte_discursos.py
```

Fixtures são pequenas e descartáveis. O corpus raw de aproximadamente 14,7 GB
e seus derivados oficiais permanecem na nuvem.

## Readback de produção

Estes comandos consultam o estado sem alterar recursos. A conta ativa é apenas
um diagnóstico; confirmar que ela é a identidade operadora pretendida antes do
proxy. Quando necessário, selecionar outra conta com `--account` somente nessa
invocação. Não executar `gcloud config set project`:

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud projects describe falando-nela-pedblan \
  --project=falando-nela-pedblan \
  --format='value(projectId,lifecycleState)'

gcloud run jobs describe fn-parquet-pilot \
  --project=falando-nela-pedblan \
  --region=southamerica-east1

gcloud run services describe fn-marimo \
  --project=falando-nela-pedblan \
  --region=southamerica-east1 \
  --format='value(status.url)'

gcloud storage objects describe \
  gs://falando-nela-pedblan-data/data/processed/v1/g03/senado/plenario_discursos/ano=2010/operation_id=g03-pilot-20260812-t120/part-00000.parquet \
  --project=falando-nela-pedblan
```

Readback não deve imprimir tokens, billing account, state nem texto integral
dos discursos em registros de tarefa.

## Acesso ao Marimo privado

O caminho normal usa o proxy autenticado do Cloud Run. Ele vincula somente o
localhost e pode iniciar uma instância dentro do limite já contratado de
zero a uma:

```bash
gcloud run services proxy fn-marimo \
  --project=falando-nela-pedblan \
  --region=southamerica-east1 \
  --port=2718
```

Abrir `http://127.0.0.1:2718/`. Um `403` indica que a identidade usada pelo
proxy não possui `roles/run.invoker`; isso não deve ser contornado tornando o
serviço público. Se a porta estiver ocupada, usar outra porta local não altera
o serviço.

Para edição, executar `marimo edit` localmente como descrito em
`notebooks/README.md`. O editor nunca é publicado no Cloud Run.

## Pipeline e deploy

O job existente aponta para imagem por digest, usa uma tarefa, paralelismo 1,
zero retry, 1 CPU, 1 GiB e timeout de 600 segundos. Uma nova execução é uma
operação paga e deve declarar o mesmo `operation_id` idempotente ou introduzir
um novo ID por spec própria. Depois do gate, a execução mínima é:

```bash
gcloud run jobs execute fn-parquet-pilot \
  --project=falando-nela-pedblan \
  --region=southamerica-east1 \
  --wait
```

Não sobrescrever argumentos na linha de comando sem que a mudança esteja na
spec e no OpenTofu. Uma falha deve ser diagnosticada antes de repetir o job.

Deploys seguem uma única sequência:

1. validar código, caderno, imagem e OpenTofu localmente;
2. construir uma imagem marcada pelo commit com o YAML de `deploy/g03/` ou
   `deploy/g04/`;
3. resolver e registrar o digest imutável no Artifact Registry;
4. fornecer o digest ao OpenTofu, revisar o plano e aplicar o plano aprovado;
5. fazer readback do recurso e um smoke mínimo.

Os comandos de build e as variáveis do plano estão em `infra/gcp/README.md`.
`billing_account_id` e `operator_principal` são fornecidos apenas pela sessão
local e nunca versionados. Não usar tag mutável como referência de runtime,
`gcloud run deploy` em paralelo ao OpenTofu ou apply sem plano revisado.

## Rollback

Rollback preserva histórico e dados; ele não começa por exclusão:

- **Código:** criar um `git revert`, validar e publicar pelo fluxo normal. Não
  usar `reset --hard` nem force-push.
- **Serviço ou job:** selecionar o digest anterior já validado, gerar novo
  plano OpenTofu e aplicar somente após o gate. O recurso tem proteção contra
  destruição.
- **Derivado:** voltar a apontar o contrato para um `operation_id` imutável já
  reconciliado. Não substituir nem apagar objetos.
- **Raw:** GCS continua autoridade. O Drive é arquivo read-only de recuperação;
  qualquer restauração dele exige tarefa própria, destino novo e reconciliação
  de hashes.
- **State:** o bucket tem versionamento e soft delete. Recuperação de state é
  excepcional; não editar state manualmente nem restaurar geração sem plano de
  incidente aprovado.

Se o incidente não exigir mutação imediata, primeiro preservar logs, digest,
revision e locators observados. Isso mantém o diagnóstico retomável.

## Custo

O serviço Marimo escala a zero e no máximo a uma instância. O job só consome
Cloud Run quando executado; GCS, Artifact Registry, logs e soft delete têm
custo contínuo proporcional ao uso. O budget mensal `falando-nela-gcp-first`
é de R$ 25,00 e envia alertas, mas não bloqueia gasto.

Acesso rotineiro ao app já implantado cabe no contrato atual. Novo build, job,
upload relevante ou apply deve registrar finalidade, menor amostra útil,
máximo de tentativas e limite de gasto. Interromper diante de crescimento
inesperado, recurso fora do plano ou necessidade de repetir sem hipótese nova.

## Diagnóstico rápido

| Sintoma | Primeira verificação | Próxima ação segura |
| --- | --- | --- |
| `doctor` falha | raiz absoluta em `FALANDO_NELA_DATA_ROOT` | usar `data_samples/`; não baixar o corpus |
| leitura GCS falha localmente | fonte selecionada, ADC e `config/gcp.toml` | corrigir credencial ou usar fixture explícita; não fazer fallback |
| proxy retorna `403` | conta ativa e binding `roles/run.invoker` | corrigir IAM por OpenTofu, nunca adicionar `allUsers` |
| Marimo retorna `5xx` | revisão, digest e logs recentes | reproduzir com fixture; mudar código somente com teste |
| schema ou contagem diverge | locator, operation ID, schema e 30 registros | parar; não promover nem escolher outro arquivo por heurística |
| job falha | execução, argumentos, digest e primeira causa nos logs | corrigir a causa antes de uma nova execução paga |
| OpenTofu mostra drift | plano e origem do recurso divergente | reconciliar no código; não aplicar automaticamente |
| alerta de custo | serviço, job, builds, storage e retenção | suspender novas operações pagas e delimitar investigação |

Logs recentes e limitados:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="fn-marimo" AND severity>=WARNING' \
  --project=falando-nela-pedblan \
  --freshness=1h \
  --limit=50 \
  --format=json

gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="fn-parquet-pilot" AND severity>=WARNING' \
  --project=falando-nela-pedblan \
  --freshness=1h \
  --limit=50 \
  --format=json
```

Não ampliar o período ou repetir automaticamente antes de formular uma nova
hipótese. Se algum payload contiver texto parlamentar ou credencial, não o
copiar para specs, commits ou tarefas.
