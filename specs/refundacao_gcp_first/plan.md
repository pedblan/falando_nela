# Plano — refundação GCP-first do Falando Nela

## Estado

Contrato aprovado em `2026-08-11`. Cada fase abaixo é uma unidade de trabalho
própria, com branch, spec operacional e validação. Concluir uma fase não
autoriza automaticamente a seguinte.

## G00 — contrato e preservação da base

- [x] Inspecionar branch, worktree, alterações do usuário e relação com `main`.
- [x] Confirmar `falando-nela-pedblan` como projeto GCP explícito e o estado
  vazio dos recursos de dados.
- [x] Escolher `southamerica-east1` como região única inicial.
- [x] Escolher GCS + Parquet e adiar BigQuery.
- [x] Escolher Cloud Run Jobs e serviço Marimo privado.
- [x] Escolher edição Marimo local com execução na GCP.
- [x] Escolher OpenTofu como executor IaC.
- [x] Escolher GCS como fonte oficial após reconciliação integral.
- [x] Preservar o Drive como arquivo somente leitura depois do corte.
- [x] Revisar e aprovar humanamente `README.md`, `requirements.md`,
  `tech-stack.md`, `plan.md` e `validation.md`.

**Gate G00:** contrato aprovado, nenhuma divergência conhecida e nenhum efeito
remoto executado.

## G01 — fundação GCP e sentinela

- [x] Criar spec operacional própria para bootstrap e sentinela.
- [x] Registrar `config/gcp.toml` com projeto, região, buckets e prefixos.
- [x] Adicionar `infra/gcp/`, versões, lockfile e ignores de estado.
- [x] Revalidar disponibilidade dos dois nomes globais de bucket.
- [x] Estimar custo e aprovar o bootstrap do bucket de estado.
- [x] Criar e verificar o bucket de estado por comando explícito e único.
- [x] Executar `tofu init`, `fmt`, `validate` e `plan` sem apply implícito.
- [x] Aprovar humanamente o plano exato e o budget de R$ 25,00, mantendo
  US$ 5,00 como referência conservadora.
- [x] Aplicar bucket de dados, IAM mínimo e alerta de orçamento.
- [x] Reconciliar novamente o inventário canônico do Drive.
- [x] Executar dry-run e copiar somente o lote sentinela congelado.
- [x] Comparar paths, bytes e hashes e repetir sem nova cópia.

**Gate G01:** infraestrutura mínima declarativa, sentinela íntegro e retomável,
default do `gcloud` inalterado e custo dentro do limite.

## G02 — migração integral e corte de armazenamento

- [x] Criar spec operacional própria para a cópia integral.
- [x] Congelar inventários de origem e destino sob novo `operation_id`.
- [x] Confirmar origem com 2.887 objetos e 14.686.043.352 bytes.
- [x] Preparar lotes limitados e relatório combinado de dry-run.
- [x] Aprovar humanamente contagem, bytes, custo e comando de cópia.
- [x] Copiar em lotes imutáveis e retomáveis, sem alterar o Drive.
- [x] Relistar GCS e reconciliar locator, tamanho e hashes de todos os objetos.
- [x] Reexecutar a operação e comprovar zero duplicação ou substituição.
- [x] Restaurar uma amostra do GCS em diretório vazio e validar seus hashes.
- [x] Aprovar humanamente GCS como fonte oficial.
- [x] Confirmar o remote Drive como arquivo read-only de rollback, sem alterá-lo.

Evidência: operação `g02-full-20260811-v1`, manifesto de migração
SHA-256 `230e40d4dfa2a57dd27659724f07b2cba3279e8b1e7f9e9f911bec5ee958a5e7`.
Corte aplicado com `authoritative_raw = "gcs"` em `config/gcp.toml` por
`g02-full-20260811-v1` (`cutover.json` em
`manifests/migrations/g02/g02-full-20260811-v1`, geração
`1786530130887793`).

**Gate G02:** raw integral reconciliado e restaurável no GCS; Drive intacto e
preservado como rollback.

## G03 — primeiro Parquet em Cloud Run Job

- [x] Criar spec operacional do recorte R03 de 30 discursos.
- [x] Implementar leitor GCS e escritor Parquet fora do caderno.
- [x] Criar imagem OCI reproduzível e validá-la localmente com fixture.
- [x] Declarar Artifact Registry, Cloud Build, service account e job em OpenTofu.
- [x] Executar e revisar `tofu plan` antes de aplicar.
- [x] Publicar a imagem marcada por commit.
- [x] Executar uma única tarefa Cloud Run com uma tentativa.
- [x] Publicar Parquet e manifest em prefixo imutável.
- [x] Comparar registros e hashes com a execução local.
- [x] Reexecutar por operation ID e comprovar retomada.

**Gate G03:** o mesmo input produz Parquet equivalente localmente e na GCP,
com proveniência e custo observados.

## G04 — primeiro app Marimo privado

- [x] Criar spec operacional do app do recorte piloto.
- [x] Criar caderno fino que consulta somente o Parquet aprovado.
- [x] Validar `marimo check`, execução como script e revisão humana local.
- [x] Declarar service account read-only e serviço Cloud Run privado.
- [x] Fixar zero instâncias mínimas e máximo de uma instância.
- [x] Construir e publicar a imagem marcada por commit.
- [x] Verificar autenticação, WebSocket, health check e leitura do GCS.
- [x] Confirmar em cold start que a instância não depende de estado local.
- [x] Confirmar que usuário anônimo não acessa o app.

**Gate G04:** app privado reproduz o resultado aprovado sem armazenamento local
persistente nem permissão pública.

## G05 — corte operacional cloud-first

- [x] Criar spec operacional própria com modelo e esforço por tarefa.
- [x] Atualizar missão, README, descrição do pacote e documentação operacional.
- [x] Tornar GCS a fonte padrão de produção mantendo fixtures locais.
- [x] Documentar deploy, execução, rollback, custos e diagnóstico.
- [x] Confirmar que nenhuma operação oficial exige Colab ou Drive montado.
- [x] Preservar referência às specs e à tag do legado.
- [x] Executar instalação limpa, lint, testes, IaC e caderno com fixtures.
- [x] Integrar a linha aprovada em `main` sem reescrever histórico.
- [x] Publicar e verificar `origin/main` no mesmo commit.

**Gate G05:** caminho cloud-first documentado e reproduzível, com Drive apenas
como arquivo e desenvolvimento local sem dependência de credenciais.

Modelo, esforço, fronteiras e gate único de cada tarefa estão definidos em
`g05_corte_operacional_cloud_first/`.

## G06 — experimento de escala do Marimo

- [x] Medir cold start do app `fn-marimo` e consolidar latência de primeiro acesso.
- [x] Validar duas abas autenticadas com WebSockets independentes.
- [x] Registrar recomendação de manter `0–1` e critérios simples de reavaliação.
- [x] Atualizar a documentação com os resultados do experimento leve.
- [x] Aprovar humanamente o encerramento de G06 mantendo a escala atual.

**Gate G06:** aprovado em `2026-08-12`; manter escala `0–1` e reavaliar somente
se o uso real justificar, sem alteração de infraestrutura nesta etapa.

## Limites globais

- Nenhuma chamada a fontes parlamentares durante G00–G04.
- Nenhum apply, build remoto, upload ou job sem gate explícito da fase.
- Orçamento inicial total de US$ 5,00 e uma tentativa paga por piloto.
- Três falhas equivalentes sem nova hipótese interrompem a etapa.
- BigQuery, atualização periódica e remoção do Drive exigem tarefas futuras.
