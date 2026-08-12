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
- [x] Registrar estimativa menor que US$ 0,01 e obter aprovação do bootstrap.
- [x] Criar somente `falando-nela-pedblan-tfstate` pelo comando aprovado.
- [x] Habilitar versionamento e verificar todas as proteções no mesmo projeto.
- [x] Inicializar backend remoto e importar o bucket sem state local persistente.

**Gate G01-B:** state bucket privado, versionado, importado e recuperável;
nenhum outro recurso novo.

## G01-C — plano e apply da fundação

- [x] Gerar plano binário com variáveis externas de billing e conta operadora.
- [x] Inspecionar JSON e confirmar somente APIs, data bucket, migrator, IAM e budget.
- [x] Obter aprovação humana do plano e do budget mensal de R$ 25,00, limitado
  pela referência aprovada de US$ 5,00.
- [x] Aplicar exatamente o plano salvo uma vez.
- [x] Fazer readback explícito de APIs, buckets, IAM, service account e budget.
- [x] Confirmar zero dataset, job, serviço, registry, chave JSON ou acesso público.

**Gate G01-C:** infraestrutura mínima coincide com o state e com o plano aprovado.

## G01-D — sentinela Drive→GCS

- [x] Reconciliar a origem com 2.887 objetos, 14.686.043.352 bytes e hashes.
- [x] Congelar os três locators e confirmar 78.822 bytes antes do upload.
- [x] Executar dry-run e obter exatamente três criações previstas.
- [x] Obter aprovação humana do comando e dos três objetos.
- [x] Gerar token curto por impersonação sem persistência.
- [x] Copiar uma vez com imutabilidade, checksum, uma tentativa e quatro transfers.
- [x] Reconciliar tamanho, MD5 e SHA-256 dos três objetos.
- [x] Reexecutar e comprovar zero upload e zero nova geração.
- [x] Confirmar a origem Drive e as configurações locais inalteradas.
- [x] Registrar custo observado e recursos persistentes.

**Gate G01-D:** sentinela íntegro, verificado imediatamente e idempotente; GCS
ainda não é fonte oficial e a migração integral continua bloqueada em G02. Por
decisão humana de `2026-08-11`, G01 não fará espera prolongada nem restauração
do canário; a prova de restauração integral permanece em G02.

G01 foi concluído em `2026-08-11`. O canário persistente contém três objetos e
78.822 bytes; a operação estimou `US$ 0,000001` para as três escritas e zero
para a repetição idempotente. O Drive permanece a fonte oficial até G02.
