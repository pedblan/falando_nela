# Validação operacional — R03 organização copy-first do Drive

## Fixtures e código

- [x] Aceitar todos os caminhos declarados de plenário e comissão.
- [x] Rejeitar arquivo sem source/dataset, partição incompleta e escape de caminho.
- [x] Preservar exatamente o caminho relativo depois de `data/raw/v1/`.
- [x] Rotular `monthly_text`, `metadata` e `transcription_queue` sem abrir payload.
- [x] Rejeitar corpus textual fora de `ano=YYYY/mes=MM/`.
- [x] Permitir metadata-only sem criar mês artificial.
- [x] Detectar duplicação ou colisão de destinos antes de qualquer cópia.
- [x] Confirmar que o dry-run construído exige `copyto --dry-run --immutable` e roda sem rede nas fixtures.
- [x] Confirmar que o dry-run integral usa lista NUL-delimited, uma única sessão rclone, `--dry-run --immutable --checksum --retries 1` e relatório combinado exato.
- [x] Confirmar que a execução real usa listas NUL-delimited por lote, `--immutable --checksum --retries 1 --transfers 4`, transporte client-side e readback integral antes do checkpoint.
- [x] Confirmar comandos sem `sync`, `move`, `delete`, `purge`, overwrite ou `--server-side-across-configs`.
- [x] Testar objeto ausente, idêntico, divergente e resposta remota ambígua.
- [x] Adulterar artefato de inventário e retomar somente as etapas invalidadas.
- [x] Usar token sentinela e confirmar ausência em comandos, erros e manifests locais.
- [x] Exigir configuração cifrada, modo privado, senha via `RCLONE_PASSWORD_COMMAND`, projeção redigida e ausência de prompt.
- [x] Fixar o ID aprovado em toda referência rclone quando `config redacted` mascara `root_folder_id`.
- [x] Validar schema do manifest e adulteração de catálogo.
- [x] Selecionar um sentinela verificável para cada categoria e limitar o agregado a 10 MiB.
- [x] Particionar o restante em lotes determinísticos de até 100 arquivos ou 512 MiB.
- [x] Pausar depois do sentinela, retomar a mesma operação e não repetir cópia confirmada.
- [x] Reconciliar destino parcial compatível e bloquear objeto adicional ou divergente.

## Gate real

- [x] Confirmar por readback a raiz antiga `falando_nela_arquivo`, ID `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB`, e o raw de origem por ID literal.
- [x] Confirmar que a reserva `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, permanece fora da operação.
- [x] Criar pelo remote `drive.file` a nova raiz `falando_nela`, registrar o ID `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq` por readback e confirmar que começa vazia.
- [x] Reconfirmar a pasta de destino vazia imediatamente antes da primeira escrita.
- [x] Confirmar `drive.readonly` na origem e `drive.file` no destino.
- [x] Confirmar a manchete G01 por listagem read-only: 2.891 arquivos, 14.686.044.612 bytes, 2.887 JSONL e quatro itens não raw.
- [x] Reconciliar os dois itens sem extensão pelo ID do provedor e pela identidade preservada em G01.
- [x] Congelar e revisar o catálogo e o dry-run integrais.
- [x] Confirmar no dry-run 2.887 candidatos, quatro exclusões explícitas, 14.686.043.352 bytes planejados e zero marcador diferente de `+`.
- [x] Aprovar `operation_id`, lote sentinela, limites e comandos exatos.
- [x] Copiar sentinela e comparar caminho, tamanho e hash.
- [x] Retomar sentinela e confirmar zero cópia adicional.
- [x] Aprovar ampliação em lotes.
- [x] Reconciliar cada lote antes de avançar.
- [x] Reconciliar catálogo final por bijeção, tamanho e hash.
- [x] Confirmar origem intacta e árvore canônica exposta por remote read-only.

Os itens de código usam somente fixtures e mocks de processo. As marcações do
gate real registram o bootstrap efetivamente realizado no Google Drive em
`2026-08-03`: autenticação dos dois remotes, listagem `camara/` e `senado/` na
origem, criação da raiz pelo destino e readback vazio. A operação
`r03-g01-reconcile-20260803` autenticou o CSV G01 pelo SHA-256
`1ab73d3173454b4f556eff02cd202d0dd76740dd7d42d8e24093785dd0cc21a6`,
reconciliou 2.891 arquivos, 14.686.044.612 bytes e quatro IDs, com zero
divergência, e foi reexecutada sem nova tentativa. A reconstrução local
`r03-g01-reconcile-20260803-rebuilt` e
`r03-drive-dry-run-20260803-rebuilt` reproduziu essas baselines. A conclusão
real usou o sentinela de três arquivos e a operação em 38 lotes
`r03-drive-copy-batched-20260803`: 2.887 destinos, 14.686.043.352 bytes, zero
ausência, zero acréscimo, zero conflito e 2.891 arquivos de origem relistados
sem alteração. A reexecução final não abriu nova sessão de cópia.
