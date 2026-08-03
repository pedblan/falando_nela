# Validação operacional — R03 piloto raw do Drive

## Validação local obrigatória

- [x] Confirmar `pronunciamento_texto` em coletor, spec, fixture e filtro.
- [x] Reconciliar fixture local por caminho, tamanho, contagem e hash.
- [x] Confirmar seleção independente da ordem de arquivos e registros.
- [x] Confirmar aritmética exata de `max(1, ceil(N × 0,01))`, incluindo `2.996 -> 30`.
- [x] Confirmar que o ledger não contém payload raw.
- [x] Confirmar que somente selecionados aparecem no JSONL gzip publicado.
- [x] Comparar hashes de cada registro entre origem e gzip descompactado.
- [x] Confirmar gzip byte a byte idêntico em duas operações equivalentes.
- [x] Recusar duplicata de identidade, JSON inválido, ano inválido e estrato divergente.
- [x] Aceitar somente `<repo>/data_samples` dentro do clone para a amostra local e recusar outros caminhos internos, quota insuficiente e destino conflitante.
- [x] Confirmar que nenhum conteúdo sob `data_samples/` aparece em `git status`.
- [x] Reexecutar o mesmo `operation_id` sem repetir streams concluídos.
- [x] Alterar entrada ou configuração e confirmar bloqueio do snapshot publicado.
- [x] Injetar falhas nas fronteiras de cada etapa e verificar estado e retomada.
- [x] Confirmar que os únicos subcomandos do importador read-only são `lsjson` e `cat`.
- [x] Confirmar que testes bloqueiam rede e não exigem `rclone` instalado.
- [x] Confirmar que a configuração cifrada é inspecionada somente por projeção redigida e sem prompt.
- [x] Confirmar que cada comando fixa o ID da raiz aprovado sem expor a configuração descriptografada.
- [x] Executar lockfile, Ruff, formatação, pytest e CLI com fixtures.

## Gate humano e validação real

- [x] Concluir a organização copy-first e seu catálogo final.
- [x] Confirmar a raiz antiga `falando_nela_arquivo` e a reserva `falando_nela_refundacao` por nome e ID.
- [x] Criar a nova raiz operacional `falando_nela` pelo remote `drive.file` e confirmar por readback o ID `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
- [x] Confirmar `type=drive`, `scope=drive.readonly` e `root_folder_id` canônico por override literal.
- [x] Disponibilizar localmente o CSV G01 e confirmar seu SHA-256 no manifest.
- [x] Reconciliar exatamente 2.891 arquivos e 14.686.044.612 bytes.
- [x] Confirmar por listagem read-only os 11 arquivos e 89.253.442 bytes do estrato de 2010.
- [x] Confirmar `N=2.996`, ou bloquear e revisar se a leitura atual divergir.
- [x] Confirmar `k=30`, ou recalcular somente depois de aprovar nova população.
- [x] Materializar, validar e publicar apenas os selecionados.
- [x] Reexecutar a operação real e observar zero nova leitura de conteúdo.
- [x] Revisar manifest, ledger, gzip, quota, rejeições e integridade da origem.

O gate R03 foi fechado para o estrato piloto de 2010. Isso não autoriza ampliar
para outros anos nem materializar o corpus integral.
