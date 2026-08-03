# Validação operacional — R03 piloto raw do Drive

## Validação local obrigatória

- [x] Confirmar `pronunciamento_texto` em coletor, spec, fixture e filtro.
- [ ] Reconciliar fixture local por caminho, tamanho, contagem e hash.
- [ ] Confirmar seleção independente da ordem de arquivos e registros.
- [x] Confirmar aritmética exata de `max(1, ceil(N × 0,01))`, incluindo `2.996 -> 30`.
- [ ] Confirmar que o ledger não contém payload raw.
- [ ] Confirmar que somente selecionados aparecem no JSONL gzip publicado.
- [ ] Comparar hashes de cada registro entre origem e gzip descompactado.
- [ ] Confirmar gzip byte a byte idêntico em duas operações equivalentes.
- [ ] Recusar duplicata de identidade, JSON inválido, ano inválido e estrato divergente.
- [ ] Recusar raiz de dados dentro do clone, quota insuficiente e destino conflitante.
- [ ] Reexecutar o mesmo `operation_id` sem repetir streams concluídos.
- [ ] Alterar entrada ou configuração e confirmar bloqueio do snapshot publicado.
- [ ] Injetar falhas nas fronteiras de cada etapa e verificar estado e retomada.
- [x] Confirmar que os únicos subcomandos do importador read-only são `lsjson` e `cat`.
- [x] Confirmar que testes bloqueiam rede e não exigem `rclone` instalado.
- [x] Confirmar que a configuração cifrada é inspecionada somente por projeção redigida e sem prompt.
- [x] Confirmar que cada comando fixa o ID da raiz aprovado sem expor a configuração descriptografada.
- [x] Executar lockfile, Ruff, formatação, pytest e CLI com fixtures.

## Gate humano e validação real

- [ ] Concluir a organização copy-first e seu catálogo final.
- [x] Confirmar a raiz antiga `falando_nela_arquivo` e a reserva `falando_nela_refundacao` por nome e ID.
- [x] Criar a nova raiz operacional `falando_nela` pelo remote `drive.file` e confirmar por readback o ID `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
- [ ] Confirmar `type=drive`, `scope=drive.readonly` e `root_folder_id` canônico no remote dedicado.
- [x] Disponibilizar localmente o CSV G01 e confirmar seu SHA-256 no manifest.
- [x] Reconciliar exatamente 2.891 arquivos e 14.686.044.612 bytes.
- [x] Confirmar por listagem read-only os 11 arquivos e 89.253.442 bytes do estrato de 2010.
- [ ] Confirmar `N=2.996`, ou bloquear e revisar se a leitura atual divergir.
- [ ] Confirmar `k=30`, ou recalcular somente depois de aprovar nova população.
- [ ] Materializar, validar e publicar apenas os selecionados.
- [ ] Reexecutar a operação real e observar zero nova leitura de conteúdo.
- [ ] Revisar manifest, ledger, gzip, quota, rejeições e integridade da origem.

O gate R03 permanece aberto enquanto qualquer item da validação real estiver
pendente. Aprovar código e fixtures não autoriza ampliar para todos os anos.
