# Plano operacional — R03 organização copy-first do Drive

- [x] Registrar a decisão humana por cópia versionada, sem reorganização in-place.
- [x] Delimitar layout, periodicidade, remotes, estados e proibições.
- [x] Implementar classificação estrita dos caminhos raw.
- [x] Implementar catálogo e plano imutável de cópia.
- [x] Implementar adaptadores separados de origem e destino.
- [x] Implementar dry-run sem criação de objeto remoto.
- [ ] Implementar execução por lote e reconciliação antes de retry.
- [x] Implementar manifest de planejamento e tentativas com escrita atômica.
- [x] Testar planejamento sintético, credenciais sentinelas, interrupções e retomada.
- [x] Renomear a raiz antiga para `falando_nela_arquivo` e confirmar que o ID `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB` não mudou.
- [x] Confirmar que `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, permanece reserva fora da operação.
- [x] Exigir configuração rclone cifrada, privada, redigida e desbloqueada pelo Chaves do macOS sem prompt.
- [x] Instalar rclone `>=1.64` e validar os remotes com escopos mínimos.
- [x] Criar pelo remote `drive.file` a nova raiz operacional `falando_nela`, confirmar vazia e congelar o ID retornado.
- [x] Executar dry-run integral e revisar o conjunto exato.
- [x] Reconciliar pelo ID do provedor os dois itens não raw com caminho rclone duplicado antes do dry-run.
- [ ] Executar um lote sentinela e validar hashes.
- [ ] Ampliar em lotes somente após aprovação do resultado anterior.
- [ ] Publicar catálogo da árvore `data/raw/v1/` e manter a origem intacta.

## Gate

A autorização da arquitetura e a criação da reserva não autorizam uma cópia.
A nova pasta operacional já foi criada pelo cliente OAuth e confirmada vazia;
a cópia ainda depende de dry-run revisado e `operation_id` confirmado. Nenhuma etapa de
cópia apaga, move, renomeia ou substitui arquivos existentes.

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
