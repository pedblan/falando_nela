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

- [x] Confirmar conta operadora esperada e `roles/owner` no projeto.
- [x] Confirmar `roles/billing.admin` na billing account vinculada.
- [x] Confirmar `falando-nela-pedblan` ACTIVE e billing habilitado.
- [x] Confirmar `southamerica-east1` e os dois nomes ainda inexistentes.
- [x] Registrar checksum da pasta de configurações gcloud e do ADC existente.

Readback executado em `2026-08-11`: projeto e project number coincidiram com o
contrato, billing estava habilitado e aberto, a conta operadora possuía os dois
papéis exigidos e ambos os nomes globais retornaram `404`. Os digests da única
configuração local do gcloud, do seletor ativo e do ADC permaneceram idênticos
antes e depois. Identidade e billing account ID não foram versionados.

Estimativa conservadora pré-aprovação do bootstrap: até `US$ 0,001`, cobrindo
com folga as poucas operações de criação, atualização, leitura e escrita do
primeiro state. O gate foi aprovado e executado em `2026-08-11`.

## Gate G01-B — state

- [x] Revisar o comando de criação com project ID, região e nome literais.
- [x] Confirmar Standard, acesso uniforme, PAP enforced e soft delete de sete dias.
- [x] Confirmar versionamento antes de inicializar o backend.
- [x] Importar como `google_storage_bucket.tfstate` e obter plan sem recriação.
- [x] Confirmar state sob `opentofu/g01/default.tfstate` e locking funcional.

## Gate G01-C — apply

- [x] Confirmar provider Google resolvido em 7.40.x pelo lockfile.
- [x] Confirmar no plano somente o conjunto de recursos autorizado.
- [x] Confirmar `force_destroy=false`, `prevent_destroy`, PAP e acesso uniforme.
- [x] Confirmar migrator somente com Object Creator + Object Viewer.
- [x] Confirmar Token Creator somente no service account migrador.
- [x] Confirmar budget R$ 25,00, projeto único e destinatários IAM ativos.
- [x] Aplicar o plano salvo sem segundo `plan` implícito.
- [x] Executar novo plan e obter zero mudança.

## Gate G01-D — sentinela

- [x] Confirmar inventário Drive exato e origem `drive.readonly` fixada pelo ID raw,
      listando o prefixo físico `v1` com locators canônicos relativos a ele.
- [x] Confirmar bucket vazio antes do dry-run.
- [x] Confirmar dry-run com três `+` e zero outro marcador.
- [x] Confirmar no log seguro uma tentativa e três objetos copiados.
- [x] Comparar por objeto locator, bytes, MD5 e SHA-256.
- [x] Registrar as gerações GCS e mantê-las idênticas na reexecução.
- [x] Encerrar após readback e idempotência imediatos, sem espera prolongada ou
  restauração do canário; a restauração amostral permanece no gate de G02.
- [x] Reconciliar novamente a origem e confirmar zero alteração.
- [x] Confirmar checksums de gcloud/ADC idênticos ao snapshot inicial.

## Critério de conclusão

G01 termina somente quando todos os readbacks coincidem com o contrato, o novo
plano OpenTofu é vazio, a sentinela foi verificada imediatamente e é idempotente,
o Drive está inalterado e nenhuma alteração fora do escopo aparece no diff. A
presença dos três objetos não autoriza G02 nem muda a fonte oficial.

Resultado de `2026-08-11`: todos os gates passaram. A operação externa
`g01-sentinel-20260811-v2` preserva manifesto e artefatos redigidos; o primeiro
preflight bloqueado documenta a descoberta do prefixo físico `v1`, sem upload.
