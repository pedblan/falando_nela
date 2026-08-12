# Validação operacional — G03 Parquet em Cloud Run Job

## Local e sem rede

- [x] Confirmar que `selection.json` contém 30 identidades e hashes únicos.
- [x] Ler `.jsonl`, `.jsonl.gz` e recusar extensão ou JSON inválido.
- [x] Materializar do gzip aprovado exatamente 30 registros e o hash congelado.
- [x] Simular os objetos GCS e obter o mesmo JSONL selecionado.
- [x] Recusar locator, linha, identidade ou hash divergente.
- [x] Validar nomes, tipos e nulabilidade do schema Parquet.
- [x] Confirmar Parquet 2.6, compressão Zstandard, 30 linhas e um row group.
- [x] Repetir a transformação e comparar hash binário e fingerprint lógico.
- [x] Confirmar publicação somente depois da validação.
- [x] Injetar falha entre publicação e recibo e retomar sem substituição.
- [x] Reexecutar o operation ID concluído sem reler nem reescrever.
- [x] Alterar entrada ou configuração e confirmar recusa do operation ID.
- [x] Executar CLI local e conferir manifesto, Parquet, validação e recibo.

## Container e infraestrutura

- [x] Construir a imagem localmente e executar a fixture sem credencial.
- [x] Confirmar imagem não-root, lockfile congelado e entrypoint da CLI.
- [x] Executar `tofu fmt`, `init -backend=false`, `validate` e `test`.
- [x] Confirmar no plano apenas APIs e recursos G03 esperados.
- [x] Confirmar ausência de chave JSON, `allUsers`, Editor ou Owner.
- [x] Confirmar leitura do pacote-fonte somente no prefixo operacional G03.
- [x] Confirmar IAM de leitura raw e criação/leitura somente nos prefixos G03.
- [x] Confirmar uma tarefa, paralelismo 1, uma tentativa e limites explícitos.

## Remoto após aprovação

- [x] Registrar hipótese, uma execução, limite de US$ 0,10 e condição de parada.
- [x] Aprovar humanamente o plan e o comando exatos do gate único.
- [x] Publicar a imagem com tag de commit e registrar seu digest.
- [x] Aplicar o job apontando para o digest aprovado.
- [x] Executar uma vez e registrar duração, CPU, memória, bytes e custo.
- [x] Baixar metadata/manifest e comparar 30 IDs, hashes e fingerprint lógico.
- [x] Reexecutar o mesmo operation ID e confirmar objetos/generations inalterados.

## Matriz de modelo e esforço da validação

| ID | Validação | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G03-V01 | Confirmar que `selection.json` contém 30 identidades e hashes únicos. | GPT-5.6-Codex | Baixo |
| G03-V02 | Ler `.jsonl`, `.jsonl.gz` e recusar extensão ou JSON inválido. | GPT-5.6-Codex | Baixo |
| G03-V03 | Materializar do gzip aprovado exatamente 30 registros e o hash congelado. | GPT-5.6-Codex | Baixo |
| G03-V04 | Simular os objetos GCS e obter o mesmo JSONL selecionado. | GPT-5.6-Codex | Médio |
| G03-V05 | Recusar locator, linha, identidade ou hash divergente. | GPT-5.6-Codex | Médio |
| G03-V06 | Validar nomes, tipos e nulabilidade do schema Parquet. | GPT-5.6-Codex | Médio |
| G03-V07 | Confirmar Parquet 2.6, compressão Zstandard, 30 linhas e um row group. | GPT-5.6-Codex | Médio |
| G03-V08 | Repetir a transformação e comparar hash binário e fingerprint lógico. | GPT-5.6-Codex | Médio |
| G03-V09 | Confirmar publicação somente depois da validação. | GPT-5.6-Codex | Médio |
| G03-V10 | Injetar falha entre publicação e recibo e retomar sem substituição. | GPT-5.6-Codex | Alto |
| G03-V11 | Reexecutar o operation ID concluído sem reler nem reescrever. | GPT-5.6-Codex | Alto |
| G03-V12 | Alterar entrada ou configuração e confirmar recusa do operation ID. | GPT-5.6-Codex | Médio |
| G03-V13 | Executar CLI local e conferir manifesto, Parquet, validação e recibo. | GPT-5.6-Codex | Médio |
| G03-V14 | Construir a imagem localmente e executar a fixture sem credencial. | GPT-5.6-Codex | Médio |
| G03-V15 | Confirmar imagem não-root, lockfile congelado e entrypoint da CLI. | GPT-5.6-Codex | Médio |
| G03-V16 | Executar `tofu fmt`, `init -backend=false`, `validate` e `test`. | GPT-5.6-Codex | Alto |
| G03-V17 | Confirmar no plano apenas APIs e recursos G03 esperados. | GPT-5.6-Codex | Médio |
| G03-V18 | Confirmar ausência de chave JSON, `allUsers`, Editor ou Owner. | GPT-5.6-Codex | Alto |
| G03-V19 | Confirmar leitura do pacote-fonte somente no prefixo operacional G03. | GPT-5.6-Codex | Médio |
| G03-V20 | Confirmar IAM de leitura raw e criação/leitura somente nos prefixos G03. | GPT-5.6-Codex | Médio |
| G03-V21 | Confirmar uma tarefa, paralelismo 1, uma tentativa e limites explícitos. | GPT-5.6-Codex | Médio |
| G03-V22 | Registrar hipótese, uma execução, limite de US$ 0,10 e condição de parada. | GPT-5.3-Codex-Spark | Médio |
| G03-V23 | Aprovar humanamente o plan e o comando exatos do gate único. | GPT-5.3-Codex-Spark | Médio |
| G03-V24 | Publicar a imagem com tag de commit e registrar seu digest. | GPT-5.3-Codex-Spark | Alto |
| G03-V25 | Aplicar o job apontando para o digest aprovado. | GPT-5.3-Codex-Spark | Alto |
| G03-V26 | Executar uma vez e registrar duração, CPU, memória, bytes e custo. | GPT-5.3-Codex-Spark | Alto |
| G03-V27 | Baixar metadata/manifest e comparar 30 IDs, hashes e fingerprint lógico. | GPT-5.3-Codex-Spark | Alto |
| G03-V28 | Reexecutar o mesmo operation ID e confirmar objetos/generations inalterados. | GPT-5.3-Codex-Spark | Médio |

## Comandos locais previstos

```bash
uv sync --locked --group cloud --group dev
uv run --locked --group cloud --group dev pytest tests/refundacao_gcp_first/test_parquet_pipeline.py
uv run --locked --group cloud --group dev ruff check src tests/refundacao_gcp_first
tofu -chdir=infra/gcp fmt -check -recursive
tofu -chdir=infra/gcp init -backend=false -input=false
tofu -chdir=infra/gcp validate
tofu -chdir=infra/gcp test
```

## Envelope aprovado para revisão

```text
Hipótese: o piloto de 30 discursos termina em uma tarefa com 1 CPU e 1 GiB.
Amostra mínima: exatamente a seleção versionada em selection.json.
Número máximo de tentativas: um build e uma execução do job, sem retry.
Estimativa ou limite de gasto: teto conservador de US$ 0,10 para o gate G03.
Condição de parada: qualquer create fora do plano, falha do build/job,
divergência de hash/contagem ou necessidade de segunda tentativa.
```

Evidência local: 62 testes do recorte GCP e 329 testes da suíte completa
passaram. `tofu validate` passou e `tofu test` concluiu dois runs. A imagem
Linux/amd64 local `sha256:0bdb9171300bb70aea4f0743352d32bb100a009362ef59fc463619459965fb2a`
executou como UID 10001 e reproduziu os mesmos hashes da execução nativa.

Evidência remota em 2026-08-12:

- build aprovado em `southamerica-east1-docker.pkg.dev/falando-nela-pedblan/falando-nela/parquet-pilot@sha256:c0eec0f409f5004d513eee0d1dffcfda95e81792ba9fd6a8be94a09384d8b870`
  (revisão `66d1bf88343582efa6424e1246cb57a55cfa3b8b`);
- manifesto remoto em
  `gs://falando-nela-pedblan-data/manifests/processing/g03/g03-pilot-20260812-t120/manifest.json`
  (generation `1786536014815269`, size `824`);
- parquet remoto em
  `gs://falando-nela-pedblan-data/data/processed/v1/g03/senado/plenario_discursos/ano=2010/operation_id=g03-pilot-20260812-t120/part-00000.parquet`
  (generation `1786536014416388`, size `129389`);
- comparação local x remoto:
  - `selection_manifest_sha256`: `8e6d879159078db7f6549a5997aded0ae29d2dda1311609b0353493f9525a1dc`
    (30 IDs e 30 raw SHA-256 únicos),
  - `selected_jsonl_sha256`: `1f887cd8363fce4aeb4e5ceb7d704be50a363af921beecddbda2cf75005ac484`,
  - `parquet sha256`: `c518b4211d3fb0982469161fc3f2d0d3832ee75e2b37ad990143238b179044a1`,
  - `logical sha256`: `2fb781b8188ec7b4b8029f5b9e4873cab376be742f52b9cd712fbb4197dc0e71`;
- duração registrada:
  `fn-parquet-pilot-b7gl4` 15.741 s e
  `fn-parquet-pilot-kglhj` 13.305 s (ambas com `succeededCount=1`);
- custo observável por execução não exposto pela API de execução; com o envelope de
  1 CPU/1Gi por <30 s total, permaneceu abaixo de `US$ 0,10`.
- rerun do mesmo `operation_id` sem reescrita:
  manifest `generation 1786536014815269`, parquet `generation 1786536014416388`.
