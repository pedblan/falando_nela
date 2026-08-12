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

- [ ] Criar spec operacional própria para bootstrap e sentinela.
- [ ] Registrar `config/gcp.toml` com projeto, região, buckets e prefixos.
- [ ] Adicionar `infra/gcp/`, versões, lockfile e ignores de estado.
- [ ] Revalidar disponibilidade dos dois nomes globais de bucket.
- [ ] Estimar custo e aprovar o bootstrap do bucket de estado.
- [ ] Criar e verificar o bucket de estado por comando explícito e único.
- [ ] Executar `tofu init`, `fmt`, `validate` e `plan` sem apply implícito.
- [ ] Aprovar humanamente o plano exato e o limite de US$ 5,00.
- [ ] Aplicar bucket de dados, IAM mínimo e alerta de orçamento.
- [ ] Reconciliar novamente o inventário canônico do Drive.
- [ ] Executar dry-run e copiar somente o lote sentinela congelado.
- [ ] Comparar paths, bytes e hashes e repetir sem nova cópia.

**Gate G01:** infraestrutura mínima declarativa, sentinela íntegro e retomável,
default do `gcloud` inalterado e custo dentro do limite.

## G02 — migração integral e corte de armazenamento

- [ ] Criar spec operacional própria para a cópia integral.
- [ ] Congelar inventários de origem e destino sob novo `operation_id`.
- [ ] Confirmar origem com 2.887 objetos e 14.686.043.352 bytes.
- [ ] Preparar lotes limitados e relatório combinado de dry-run.
- [ ] Aprovar humanamente contagem, bytes, custo e comando de cópia.
- [ ] Copiar em lotes imutáveis e retomáveis, sem alterar o Drive.
- [ ] Relistar GCS e reconciliar locator, tamanho e hashes de todos os objetos.
- [ ] Reexecutar a operação e comprovar zero duplicação ou substituição.
- [ ] Restaurar uma amostra do GCS em diretório vazio e validar seus hashes.
- [ ] Aprovar humanamente GCS como fonte oficial.
- [ ] Reconfigurar o remote Drive apenas como arquivo read-only, sem excluir nada.

**Gate G02:** raw integral reconciliado e restaurável no GCS; Drive intacto e
preservado como rollback.

## G03 — primeiro Parquet em Cloud Run Job

- [ ] Criar spec operacional do recorte R03 de 30 discursos.
- [ ] Implementar leitor GCS e escritor Parquet fora do caderno.
- [ ] Criar imagem OCI reproduzível e validá-la localmente com fixture.
- [ ] Declarar Artifact Registry, Cloud Build, service account e job em OpenTofu.
- [ ] Executar e revisar `tofu plan` antes de aplicar.
- [ ] Publicar a imagem marcada por commit.
- [ ] Executar uma única tarefa Cloud Run com uma tentativa.
- [ ] Publicar Parquet e manifest em prefixo imutável.
- [ ] Comparar registros e hashes com a execução local.
- [ ] Reexecutar por operation ID e comprovar retomada.

**Gate G03:** o mesmo input produz Parquet equivalente localmente e na GCP,
com proveniência e custo observados.

## G04 — primeiro app Marimo privado

- [ ] Criar spec operacional do app do recorte piloto.
- [ ] Criar caderno fino que consulta somente o Parquet aprovado.
- [ ] Validar `marimo check`, execução como script e revisão humana local.
- [ ] Declarar service account read-only e serviço Cloud Run privado.
- [ ] Fixar zero instâncias mínimas e máximo de uma instância.
- [ ] Construir e publicar a imagem marcada por commit.
- [ ] Verificar autenticação, WebSocket, health check e leitura do GCS.
- [ ] Confirmar que reiniciar a instância não perde estado necessário.
- [ ] Confirmar que usuário anônimo não acessa o app.

**Gate G04:** app privado reproduz o resultado aprovado sem armazenamento local
persistente nem permissão pública.

## G05 — corte operacional cloud-first

- [ ] Atualizar missão, README, descrição do pacote e documentação operacional.
- [ ] Tornar GCS a fonte padrão de produção mantendo fixtures locais.
- [ ] Documentar deploy, execução, rollback, custos e diagnóstico.
- [ ] Confirmar que nenhuma operação oficial exige Colab ou Drive montado.
- [ ] Preservar referência às specs e à tag do legado.
- [ ] Executar instalação limpa, lint, testes, IaC e caderno com fixtures.
- [ ] Integrar a linha aprovada em `main` sem reescrever histórico.
- [ ] Publicar e verificar `origin/main` no mesmo commit.

**Gate G05:** caminho cloud-first documentado e reproduzível, com Drive apenas
como arquivo e desenvolvimento local sem dependência de credenciais.

## Limites globais

- Nenhuma chamada a fontes parlamentares durante G00–G04.
- Nenhum apply, build remoto, upload ou job sem gate explícito da fase.
- Orçamento inicial total de US$ 5,00 e uma tentativa paga por piloto.
- Três falhas equivalentes sem nova hipótese interrompem a etapa.
- BigQuery, atualização periódica e remoção do Drive exigem tarefas futuras.
