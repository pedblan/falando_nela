# Plano operacional — R03 organização copy-first do Drive

- [x] Registrar a decisão humana por cópia versionada, sem reorganização in-place.
- [x] Delimitar layout, periodicidade, remotes, estados e proibições.
- [x] Implementar classificação estrita dos caminhos raw.
- [x] Implementar catálogo e plano imutável de cópia.
- [x] Implementar adaptadores separados de origem e destino.
- [x] Implementar dry-run sem criação de objeto remoto.
- [x] Implementar execução por lote e reconciliação antes de retry.
- [x] Implementar manifest de planejamento e tentativas com escrita atômica.
- [x] Testar planejamento sintético, credenciais sentinelas, interrupções e retomada.
- [x] Renomear a raiz antiga para `falando_nela_arquivo` e confirmar que o ID `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB` não mudou.
- [x] Confirmar que `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, permanece reserva fora da operação.
- [x] Exigir configuração rclone cifrada, privada, redigida e desbloqueada pelo Chaves do macOS sem prompt.
- [x] Instalar rclone `>=1.64` e validar os remotes com escopos mínimos.
- [x] Criar pelo remote `drive.file` a nova raiz operacional `falando_nela`, confirmar vazia e congelar o ID retornado.
- [x] Executar dry-run integral e revisar o conjunto exato.
- [x] Reconciliar pelo ID do provedor os dois itens não raw com caminho rclone duplicado antes do dry-run.
- [x] Executar um lote sentinela e validar hashes.
- [x] Ampliar em lotes somente após aprovação do resultado anterior.
- [x] Publicar catálogo da árvore `data/raw/v1/` e manter a origem intacta.

## Gate

A autorização da arquitetura e a criação da reserva não autorizavam, sozinhas,
uma cópia. O dry-run, o sentinela e a ampliação foram aprovados pelo plano R03
executado em `2026-08-03`. Nenhuma etapa apaga, move, renomeia ou substitui
arquivos existentes.

Evidência de `2026-08-03`: o subcomando `drive-organize plan`, a
classificação, o plano, o preflight de destino vazio e a reconciliação antes de
retry foram implementados e exercitados com fixtures. O projeto
`falando-nela-pedblan`, o cliente OAuth desktop e os remotes separados foram
configurados. `raw-destination-rw` criou a raiz `falando_nela`, ID
`17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`, e confirmou zero entrada interna por
readback. A outra mutação concluída foi a renomeação reversível da raiz antiga
para `falando_nela_arquivo`; a reserva permaneceu intacta e nenhuma cópia raw
ocorreu. A operação read-only `r03-g01-reconcile-20260803` autenticou o CSV G01
e reconciliou 2.891 arquivos, 14.686.044.612 bytes e quatro IDs de provedor,
com zero ausência, acréscimo ou alteração. Os dois IDs associados ao mesmo
caminho `Untitled` foram preservados como grupo de equivalência ligado aos dois
locators G01, sem atribuição individual não demonstrável.

Evidência do dry-run de `2026-08-03`: a operação
`r03-drive-dry-run-20260803` consumiu os artefatos G01 reconciliados, congelou
2.887 destinos e 14.686.043.352 bytes e registrou quatro exclusões por ID,
totalizando 1.260 bytes. A primeira tentativa de preparação bloqueou ao revelar
os dez JSONL metadata-only de `camara/parlamentares` e
`senado/parlamentares`; a inclusão explícita desses metadados transversais
permitiu concluir a segunda tentativa. O dry-run remoto terminou na primeira
tentativa, com 2.887 marcadores `+`, nenhum marcador divergente, retorno zero e
destino vazio antes e depois. A reexecução reutilizou todos os artefatos e não
repetiu a sessão remota. Nenhum arquivo raw foi copiado.

Evidência local posterior de `2026-08-03`: `drive-organize copy` implementa
preflight compatível, sentinela determinístico por categoria, lotes limitados,
checkpoint por objeto, reconciliação antes de retry, bijeção final e nova
verificação da origem. As fixtures comprovaram pausa no sentinela, retomada até
o catálogo completo e reexecução sem novo `copyto`; nenhuma escrita real foi
feita por essa validação local.

Evidência real de conclusão em `2026-08-03`: as operações reconstruídas
`r03-g01-reconcile-20260803-rebuilt` e
`r03-drive-dry-run-20260803-rebuilt` reproduziram as mesmas baselines antes de
qualquer escrita. O sentinela da operação `r03-drive-copy-20260803` copiou e
verificou três arquivos, um por categoria, totalizando 78.822 bytes. A medição
real revelou overhead excessivo no executor por objeto; a tentativa foi
interrompida de forma recuperável e substituída, sem apagar os objetos já
confirmados, pela operação
`r03-drive-copy-batched-20260803`. Ela adotou três sentinelas e cinco objetos
de lote já presentes, executou 38 lotes client-side com retorno zero, zero
ausência e zero conflito, e publicou o catálogo SHA-256
`cabe9aae5071d25bdae6459b99064d2ed37110ffaed0c30b95867dd798d22319`.
A árvore final contém 2.887 arquivos e 14.686.043.352 bytes. A relistagem da
origem confirmou 2.891 arquivos e 14.686.044.612 bytes inalterados; a
reexecução idêntica reutilizou todos os artefatos sem nova cópia.
