# Validação — refundação GCP-first do Falando Nela

## Estado

Contrato aprovado em `2026-08-11`. G00 e G01 foram concluídos; a fundação GCP
e os três objetos sentinela existem, enquanto o Drive permanece fonte oficial.

## Gates

| Gate | Resultado | Evidência | Estado |
|---|---|---|---|
| G00 | contrato coerente | revisão humana e diff restrito | aprovado |
| G01 | fundação e sentinela | plan IaC, readback, catálogo e reexecução | aprovado |
| G02 | raw integral no GCS | inventários, hashes, restore e gate humano | pendente |
| G03 | Parquet em Cloud Run Job | paridade local/cloud, manifest e custo | pendente |
| G04 | Marimo privado | check, script, autenticação e leitura GCS | pendente |
| G05 | corte cloud-first | clone limpo, docs, testes e remote | pendente |

## G00 — contrato

- [x] Confirmar coerência entre as quatro specs e o README.
- [x] Confirmar que ações do plano usam checkboxes CommonMark.
- [x] Confirmar que `falando-nela-pedblan` aparece em todo exemplo operacional
  que exige projeto concreto.
- [x] Confirmar região `southamerica-east1` em Storage, registry e Cloud Run.
- [x] Confirmar que BigQuery, Batch e edição remota estão fora do primeiro ciclo.
- [x] Confirmar que R00–R03 e R09 anteriores permanecem preservados.
- [x] Confirmar que nenhum gate remoto foi marcado como concluído.
- [x] Aprovar humanamente o contrato.

Evidência de investigação em `2026-08-11`: o projeto
`falando-nela-pedblan` está `ACTIVE`, com faturamento habilitado; listagens
explícitas retornaram zero bucket, zero dataset BigQuery e zero service account.
Os dois nomes planejados de bucket retornaram `404`. Nenhum comando alterou o
projeto ativo local nem criou recursos.

## G01 — IaC e sentinela

Validações obrigatórias antes do primeiro apply:

```bash
tofu -chdir=infra/gcp fmt -check -recursive
tofu -chdir=infra/gcp init -backend=false
tofu -chdir=infra/gcp validate
tofu -chdir=infra/gcp plan -var='project_id=falando-nela-pedblan' \
  -var='region=southamerica-east1'
```

- [x] Confirmar que o plan contém somente os recursos autorizados em G01.
- [x] Confirmar que state, credenciais e planos binários não estão no Git.
- [x] Confirmar acesso uniforme e prevenção de acesso público nos buckets.
- [x] Confirmar que IAM não concede Owner, Editor, chaves JSON ou `allUsers`.
- [x] Confirmar que a identidade migradora não pode excluir objetos.
- [x] Comparar o checksum da configuração `default` do gcloud antes e depois.
- [x] Executar dry-run do sentinela sem escrita.
- [x] Copiar somente locators congelados e reconciliar contagem, bytes e hashes.
- [x] Reexecutar e comprovar zero novo upload.
- [x] Registrar custo estimado e recursos persistentes.

G01 encerrou com plan OpenTofu vazio, dois buckets privados, seis APIs
gerenciadas, uma service account sem chave, IAM mínimo, budget mensal de
R$ 25,00 e três sentinelas (78.822 bytes). A repetição marcou três igualdades e
zero escrita; a estimativa do upload foi `US$ 0,000001`.

## G02 — migração integral

- [ ] Reconciliar a origem atual contra 2.887 objetos e 14.686.043.352 bytes.
- [ ] Confirmar relatório de dry-run com exatamente um marcador por destino.
- [ ] Registrar início, fim e tentativa de cada lote.
- [ ] Confirmar que todo objeto destino tem uma origem única.
- [ ] Confirmar zero ausência, surpresa, substituição ou mismatch.
- [ ] Comparar hash do catálogo fechado da origem e do destino.
- [ ] Reexecutar e comprovar idempotência.
- [ ] Restaurar sentinelas e comparar bytes localmente.
- [ ] Confirmar Drive inalterado por ID, contagem e bytes.
- [ ] Obter aprovação humana para o corte da fonte oficial.

## G03 — Cloud Run Job

- [ ] Testar leitor e escritor com `.jsonl`, `.jsonl.gz` e fixture inválida.
- [ ] Validar schema Parquet, compressão, contagem e hashes localmente.
- [ ] Confirmar imagem pelo digest e commit, não apenas por tag mutável.
- [ ] Confirmar job com project ID, região, service account e limites explícitos.
- [ ] Executar uma tarefa, uma tentativa e sem paralelismo no piloto.
- [ ] Comparar conteúdo lógico local/cloud registro a registro.
- [ ] Confirmar que falha não promove output parcial.
- [ ] Reexecutar por operation ID e comprovar retomada.
- [ ] Registrar duração, CPU, memória, bytes e custo observado.

## G04 — Marimo privado

```bash
uv run --locked marimo check notebooks/primeiro_recorte_discursos.py
uv run --locked python notebooks/primeiro_recorte_discursos.py
```

- [ ] Confirmar que o notebook contém somente orquestração e apresentação.
- [ ] Confirmar leitura read-only do Parquet pelo service account do app.
- [ ] Confirmar `marimo run` em `0.0.0.0:8080` e health check saudável.
- [ ] Confirmar WebSocket e interações em sessão autenticada.
- [ ] Confirmar recusa de acesso anônimo.
- [ ] Reiniciar instância e repetir a consulta sem depender do filesystem local.
- [ ] Confirmar zero instâncias mínimas e máximo de uma instância.

## G05 — regressão e corte

- [ ] Executar lockfile, Ruff, formatação e suíte completa em clone limpo.
- [ ] Executar testes e caderno com fixtures sem ADC ou rede.
- [ ] Confirmar que produção recusa projeto, região ou bucket divergentes.
- [ ] Confirmar documentação de deploy, execução, custo e rollback.
- [ ] Procurar dependências operacionais restantes de Colab e Drive montado.
- [ ] Confirmar que specs históricas continuam acessíveis e rotuladas.
- [ ] Revisar diff por segredos, state, outputs, caches e mudanças alheias.

## Custos e interrupção

Para cada operação paga registrar:

```text
Hipótese:
Amostra mínima:
Número máximo de tentativas:
Estimativa ou limite de gasto:
Condição de parada:
```

O primeiro ciclo não ultrapassará US$ 5,00 sem novo gate humano. Três falhas
equivalentes sem nova hipótese encerram a tentativa e exigem diagnóstico.
