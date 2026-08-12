# Validação operacional — G01 fundação GCP e sentinela

## Validação local obrigatória

- [x] Confirmar que todo passo acionável do plano usa checkbox CommonMark.
- [x] Confirmar projeto e região idênticos em config, código, IaC e specs.
- [x] Recusar config ausente, schema desconhecido e identificador divergente.
- [x] Confirmar os três sentinelas, tamanhos, SHA-256 e soma de 78.822 bytes.
- [x] Aceitar somente os dois zeros aprovados e derivar seu SHA-256 vazio.
- [x] Testar preflight com inventário exato, ausência, surpresa e mismatch.
- [x] Testar dry-run com `+`, destino preexistente igual e destino conflitante.
- [x] Testar cópia, erro ambíguo reconciliável e erro ambíguo bloqueado.
- [x] Testar retomada e invalidação quando config ou artefato mudar.
- [x] Confirmar que token existe apenas no ambiente do subprocesso e é redigido.
- [x] Confirmar ausência de `sync`, `move`, delete, chave JSON e alteração de ADC.
- [x] Executar `uv lock --check`, Ruff, formatação e pytest.
- [x] Executar `tofu fmt -check -recursive`, `init -backend=false`, `validate` e `test`.
- [x] Revisar diff por state, planos, tokens, caches, dados raw e mudanças alheias.

## Readback anterior a qualquer efeito remoto

```bash
gcloud projects describe falando-nela-pedblan \
  --project=falando-nela-pedblan
gcloud billing projects describe falando-nela-pedblan \
  --project=falando-nela-pedblan
gcloud storage buckets list --project=falando-nela-pedblan
```

- [ ] Confirmar conta operadora esperada e `roles/owner` no projeto.
- [ ] Confirmar `roles/billing.admin` na billing account vinculada.
- [ ] Confirmar `falando-nela-pedblan` ACTIVE e billing habilitado.
- [ ] Confirmar `southamerica-east1` e os dois nomes ainda inexistentes.
- [ ] Registrar checksum da pasta de configurações gcloud e do ADC existente.

## Gate G01-B — state

- [ ] Revisar o comando de criação com project ID, região e nome literais.
- [ ] Confirmar Standard, acesso uniforme, PAP enforced e soft delete de sete dias.
- [ ] Confirmar versionamento antes de inicializar o backend.
- [ ] Importar como `google_storage_bucket.tfstate` e obter plan sem recriação.
- [ ] Confirmar state sob `opentofu/g01/default.tfstate` e locking funcional.

## Gate G01-C — apply

- [ ] Confirmar provider Google resolvido em 7.40.x pelo lockfile.
- [ ] Confirmar no plano somente o conjunto de recursos autorizado.
- [ ] Confirmar `force_destroy=false`, `prevent_destroy`, PAP e acesso uniforme.
- [ ] Confirmar migrator somente com Object Creator + Object Viewer.
- [ ] Confirmar Token Creator somente no service account migrador.
- [ ] Confirmar budget US$ 5,00, projeto único e destinatários IAM ativos.
- [ ] Aplicar o plano salvo sem segundo `plan` implícito.
- [ ] Executar novo plan e obter zero mudança.

## Gate G01-D — sentinela

- [ ] Confirmar inventário Drive exato e origem `drive.readonly` fixada pelo ID raw.
- [ ] Confirmar bucket vazio antes do dry-run.
- [ ] Confirmar dry-run com três `+` e zero outro marcador.
- [ ] Confirmar no log seguro uma tentativa e três objetos copiados.
- [ ] Comparar por objeto locator, bytes, MD5 e SHA-256.
- [ ] Registrar as gerações GCS e mantê-las idênticas na reexecução.
- [ ] Restaurar os três objetos em diretório temporário e comparar SHA-256.
- [ ] Reconciliar novamente a origem e confirmar zero alteração.
- [ ] Confirmar checksums de gcloud/ADC idênticos ao snapshot inicial.

## Critério de conclusão

G01 termina somente quando todos os readbacks coincidem com o contrato, o novo
plano OpenTofu é vazio, a sentinela é restaurável e idempotente, o Drive está
inalterado e nenhuma alteração fora do escopo aparece no diff. A presença dos
três objetos não autoriza G02 nem muda a fonte oficial.
