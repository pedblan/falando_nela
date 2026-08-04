# Plano — R09 limpeza local do legado

- [x] Catalogar os dois alvos locais com caminhos, tamanhos e SHA-256.
- [x] Confirmar que nenhum arquivo dos alvos é rastreado, exceto sentinelas preservadas fora deles.
- [x] Registrar os notebooks rastreados como consulta legada.
- [x] Mover os dois alvos para uma pasta exclusiva na Lixeira do macOS.
- [x] Confirmar ausência dos alvos e preservação de `data_samples/`.
- [x] Executar testes e revisar o diff da tarefa local.
- [x] Criar commit próprio para a limpeza local.
- [ ] Avançar o checkout canônico por fast-forward.
- [ ] Remover a worktree temporária somente depois da tarefa remota e da validação final.

**Gate:** um único checkout canônico contém o código validado, os notebooks
continuam consultáveis, os dados antigos estão recuperáveis na Lixeira e
`data_samples/` permanece inalterado.

Evidência: `data_samples/operations/r09_local_cleanup_20260803/`. Os 856
arquivos catalogados, somando 3.379.699.146 bytes, foram reencontrados na
Lixeira com os mesmos hashes.
