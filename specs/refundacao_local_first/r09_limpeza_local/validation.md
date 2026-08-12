# Validação — R09 limpeza local do legado

- [x] Registrar baseline de 803 arquivos e 3.361.388.830 bytes sob `data/samples/textos_parlamentares/v1`; o alvo completo somava 804 arquivos e 3.361.394.978 bytes.
- [x] Registrar baseline de 52 arquivos e 18.304.168 bytes sob `data/dev`.
- [x] Confirmar catálogo SHA-256 completo antes da movimentação.
- [x] Confirmar que os alvos foram movidos para `/Users/pedblan/.Trash/falando_nela-r09-local-20260803.3AC5Xg/` e podem ser recuperados.
- [x] Confirmar que `data/samples/.gitkeep`, `data/schemas/.gitkeep` e `data/.gitkeep` permanecem rastreados.
- [x] Confirmar 52 notebooks rastreados e documentação de consulta legada.
- [x] Confirmar hash inalterado da amostra R03: `09ce1293e61ca8d8ef8691b35d87319c957e89bbc3bd109b239ae7623ed9b0cc`.
- [x] Confirmar que `.idea/falando_nela.iml` continua como única alteração preexistente do usuário.
- [x] Executar Ruff, pytest, `git diff --check` e validação JSON dos notebooks.
- [x] Confirmar que a worktree temporária foi removida com `git worktree remove`.
