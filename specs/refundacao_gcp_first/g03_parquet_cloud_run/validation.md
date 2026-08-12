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
- [ ] Aprovar humanamente o plan e o comando exatos do gate único.
- [ ] Publicar a imagem com tag de commit e registrar seu digest.
- [ ] Aplicar o job apontando para o digest aprovado.
- [ ] Executar uma vez e registrar duração, CPU, memória, bytes e custo.
- [ ] Baixar metadata/manifest e comparar 30 IDs, hashes e fingerprint lógico.
- [ ] Reexecutar o mesmo operation ID e confirmar objetos/generations inalterados.

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
Nenhuma chamada a GCS, build remoto, apply ou Cloud Run Job foi feita.
