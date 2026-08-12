# Plano operacional — G01 fundação GCP e sentinela

## G01-A — contrato e implementação local

- [x] Registrar a aprovação humana de G00 sem ampliar seus efeitos remotos.
- [x] Criar branch própria a partir do commit aprovado de G00.
- [x] Congelar projeto, região, recursos, proteções, custo e sentinela.
- [x] Registrar `config/gcp.toml` sem identidade ou segredo pessoal.
- [x] Implementar `infra/gcp/` e testes OpenTofu sem backend remoto ativo.
- [x] Implementar `gcs-migrate sentinel` sem alterar `drive-organize`.
- [x] Cobrir configuração, comandos, falhas, retomada e redaction com fixtures.
- [x] Executar lockfile, Ruff, formatação, pytest e testes OpenTofu locais.

**Gate G01-A:** diff local coerente, nenhum recurso GCP criado e projeto
`default` intacto.

## G01-B — bootstrap do state

- [x] Fazer readback de conta, projeto, billing, região e nomes imediatamente antes.
- [x] Revalidar os dois nomes globais de bucket e interromper se algum existir.
- [ ] Registrar estimativa menor que US$ 0,01 e obter aprovação do bootstrap.
- [ ] Criar somente `falando-nela-pedblan-tfstate` pelo comando aprovado.
- [ ] Habilitar versionamento e verificar todas as proteções no mesmo projeto.
- [ ] Inicializar backend remoto e importar o bucket sem state local persistente.

**Gate G01-B:** state bucket privado, versionado, importado e recuperável;
nenhum outro recurso novo.

## G01-C — plano e apply da fundação

- [ ] Gerar plano binário com variáveis externas de billing e conta operadora.
- [ ] Inspecionar JSON e confirmar somente APIs, data bucket, migrator, IAM e budget.
- [ ] Obter aprovação humana do plano e do limite mensal de US$ 5,00.
- [ ] Aplicar exatamente o plano salvo uma vez.
- [ ] Fazer readback explícito de APIs, buckets, IAM, service account e budget.
- [ ] Confirmar zero dataset, job, serviço, registry, chave JSON ou acesso público.

**Gate G01-C:** infraestrutura mínima coincide com o state e com o plano aprovado.

## G01-D — sentinela Drive→GCS

- [ ] Reconciliar a origem com 2.887 objetos, 14.686.043.352 bytes e hashes.
- [ ] Congelar os três locators e confirmar 78.822 bytes antes do upload.
- [ ] Executar dry-run e obter exatamente três criações previstas.
- [ ] Obter aprovação humana do comando e dos três objetos.
- [ ] Gerar token curto por impersonação sem persistência.
- [ ] Copiar uma vez com imutabilidade, checksum, uma tentativa e quatro transfers.
- [ ] Reconciliar tamanho, MD5 e SHA-256 dos três objetos.
- [ ] Reexecutar e comprovar zero upload e zero nova geração.
- [ ] Confirmar a origem Drive e as configurações locais inalteradas.
- [ ] Registrar custo observado e recursos persistentes.

**Gate G01-D:** sentinela íntegro, idempotente e restaurável; GCS ainda não é
fonte oficial e a migração integral continua bloqueada em G02.
