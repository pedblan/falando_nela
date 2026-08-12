# Validação operacional — G04 primeiro app Marimo privado

## Local

- [x] Confirmar `marimo check notebooks/primeiro_recorte_discursos.py`.
- [x] Confirmar execução como script:
  ```bash
  FALANDO_NELA_G04_SOURCE=fixture \
  FALANDO_NELA_G04_FIXTURE=/caminho/fixture.parquet \
  uv run --locked --group cloud --group notebooks \
    python notebooks/primeiro_recorte_discursos.py
  ```
  sem necessidade de sessão interativa.
- [x] Confirmar leitura da fixture somente quando as duas variáveis forem fornecidas.
- [x] Confirmar ausência de fallback entre fixture e GCS.
- [x] Confirmar rejeição explícita de schema incompatível.
- [x] Confirmar que o app mostra contagem de registros e as colunas mínimas.
- [x] Confirmar smoke local via ADC com 30 registros do Parquet G03 aprovado.
- [x] Confirmar revisão visual do app em `127.0.0.1`, incluindo busca, filtros e tabela.

## Container e infraestrutura

- [x] Confirmar `uv sync --locked --group cloud --group notebooks` (ou equivalente)
  no pacote de build do app.
- [x] Confirmar build local/ci reproduzível com `Dockerfile` do app.
- [x] Confirmar `google_cloud_run_v2_service` com `max_scale=1`, `min_scale=0` e
  `--vpc-access` conforme contrato atual (se aplicável).
- [x] Confirmar `google_service_account` dedicada (`fn-marimo`) sem chave.
- [x] Confirmar IAM de serviço apenas leitura em `data/processed/v1/g03/` e
  manifests/validação relacionados ao recorte.
- [x] Confirmar ausência de `allUsers`/`allAuthenticatedUsers`.

## Remoto e smoke

- [x] Executar deploy com tag/digest aprovado e confirmar URL de serviço.
- [x] Confirmar que endpoint responde sem exposição pública e exige identidade IAM.
- [x] Confirmar health check em `/` e carregamento de recorte estável em uma execução.
- [x] Confirmar que os primeiros resultados têm 30 itens conforme o caminho aprovado.
- [x] Confirmar logs sem texto integral de discurso e sem credenciais/token.

## Matriz de modelo e esforço da validação

| ID | Validação | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G04-V01 | `marimo check notebooks/primeiro_recorte_discursos.py` | GPT-5.3-Codex-Spark | Médio |
| G04-V02 | Execução do script sem sessão interativa (`python ...`) | GPT-5.3-Codex-Spark | Médio |
| G04-V03 | Leitura por fixture local explícita | GPT-5.3-Codex-Spark | Médio |
| G04-V04 | Ausência de fallback e mensagem útil de fonte inválida | GPT-5.3-Codex-Spark | Baixo |
| G04-V05 | Rejeição de schema incompatível | GPT-5.3-Codex-Spark | Médio |
| G04-V06 | Exibição mínima de recorte no app | GPT-5.3-Codex-Spark | Médio |
| G04-V13 | Smoke local via ADC com o Parquet aprovado | GPT-5.3-Codex-Spark | Médio |
| G04-V14 | Revisão visual em `127.0.0.1` | GPT-5.3-Codex-Spark | Médio |
| G04-V07 | Build local/CI reproduzível | GPT-5.3-Codex-Spark | Alto |
| G04-V08 | Build de container e smoke de imagem | GPT-5.3-Codex-Spark | Médio |
| G04-V09 | Escala e limites do serviço revisados | GPT-5.3-Codex-Spark | Médio |
| G04-V10 | IAM de serviço e SA mínima aprovadas | GPT-5.3-Codex-Spark | Alto |
| G04-V11 | Ausência de identidade anônima | GPT-5.3-Codex-Spark | Médio |
| G04-V12 | Smoke remoto autenticado e resposta mínima | GPT-5.3-Codex-Spark | Alto |

## Notas de evidência

- `operation_id` esperado no recorte: `g03-pilot-20260812-t120`
- fonte oficial: `gs://falando-nela-pedblan-data/data/processed/v1/g03/senado/plenario_discursos/ano=2010/operation_id=g03-pilot-20260812-t120/`
- logs do app devem conter tentativa de leitura, contagem e duração, mas não texto
  integral dos discursos.
- validação local em 2026-08-12: 72 testes passaram; o smoke GCS registrou apenas
  fonte, operação, contagem (30) e duração; a revisão visual confirmou busca (1/30),
  filtro PT (5/30), tabela paginada e detalhe sem erros de console.
- aprovação humana do recorte local registrada em 2026-08-12.
- validação remota em 2026-08-12: imagem
  `marimo-primeiro@sha256:f21c13d98eb774444cdc00c0cff11c65b8a366d32aed9d70761558e10295491d`,
  serviço `fn-marimo` em `southamerica-east1`, escala 0--1; `403` sem
  identidade e `200` com identidade IAM. A sessão autenticada carregou GCS com
  30 registros, busca (1/30), filtro de partido (5/30) e combinação partido+UF
  (1/30), sem erros no console. O readback de logs confirmou somente metadados
  de carregamento e o plano OpenTofu posterior retornou `No changes`.

## Envelope de risco aceito

```text
Hipótese: consulta do recorte piloto carrega localmente sem falha com ADC.
Amostra mínima: um único parquet de 30 linhas (ou fixture local equivalente).
Número máximo de tentativas locais: uma validação com fixture + um smoke GCS.
Condição de parada local: falha de ADC, ausência de leitura do dataset aprovado ou exposição fora de localhost.
```
