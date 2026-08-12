# Falando Nela

O Falando Nela é um projeto de pesquisa computacional sobre a presença, a
circulação e a disputa de temas constitucionais em discursos e debates do
Parlamento brasileiro. O projeto privilegia dados rastreáveis, transformações
reproduzíveis e análises que possam ser auditadas desde a fonte.

## Caminho oficial

O ambiente operacional é cloud-first:

| Camada | Contrato atual |
| --- | --- |
| Código e specs | Git |
| Dados raw oficiais | Cloud Storage em `falando-nela-pedblan` |
| Derivados analíticos | Parquet Zstandard no Cloud Storage |
| Processamento de produção | Cloud Run Jobs |
| Consulta interativa | Marimo privado no Cloud Run |
| Infraestrutura | OpenTofu |

O Google Drive foi preservado somente como arquivo de recuperação. Colab e os
notebooks Jupyter antigos são material histórico, não entradas operacionais.
Os dados volumosos permanecem na nuvem: desenvolvimento e testes locais usam
fixtures pequenas e explícitas, sem manter uma cópia integral do corpus no
computador.

## Começar localmente

O projeto requer Python 3.13 e [uv](https://docs.astral.sh/uv/). A preparação
local não baixa o corpus:

```bash
uv sync --locked --group dev --group cloud --group notebooks
FALANDO_NELA_DATA_ROOT="$PWD/data_samples" uv run falando-nela doctor --json
uv run pytest -q tests/refundacao_gcp_first
```

O primeiro caderno Marimo lê o Parquet oficial no GCS por padrão. Essa execução
requer ADC com acesso ao projeto explícito do contrato:

```bash
uv run --locked --group cloud --group notebooks \
  marimo edit notebooks/primeiro_recorte_discursos.py \
  --host 127.0.0.1 --port 2718
```

Para testes sem credenciais, selecione uma fixture Parquet compatível; não há
fallback automático entre fixture e GCS:

```bash
FALANDO_NELA_G04_SOURCE=fixture \
FALANDO_NELA_G04_FIXTURE=/caminho/fixture.parquet \
uv run --locked --group cloud --group notebooks \
  python notebooks/primeiro_recorte_discursos.py
```

## Onde continuar

- [`specs/mission.md`](specs/mission.md): missão científica e fontes-alvo.
- [`specs/refundacao_gcp_first/`](specs/refundacao_gcp_first/): arquitetura,
  requisitos, fases e evidências do caminho cloud-first.
- [`notebooks/README.md`](notebooks/README.md): índice dos cadernos atuais e do
  arquivo histórico.
- [`config/gcp.toml`](config/gcp.toml): identificadores e contratos GCP
  versionados, sem segredos.
- [`infra/gcp/`](infra/gcp/): infraestrutura declarativa.
- [`docs/operacao_cloud_first.md`](docs/operacao_cloud_first.md): execução,
  acesso privado, deploy, rollback, custo e diagnóstico.

Documentar um comando não autoriza por si só uma operação paga ou uma mutação
remota; o guia operacional distingue ações rotineiras dos novos gates.
