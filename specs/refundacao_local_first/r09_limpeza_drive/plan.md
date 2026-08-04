# Plano — R09 limpeza de versões antigas no Drive

- [x] Reconstruir o inventário dos dez IDs imediatamente antes da operação.
- [x] Baixar os 106 notebooks para staging local segregado por raiz de origem.
- [x] Validar JSON e registrar SHA-256 de cada notebook preservado.
- [x] Copiar os notebooks para `falando_nela/notebooks/consulta_legacy/`.
- [x] Baixar e comparar a cópia remota com o staging local.
- [x] Confirmar 106 objetos, caminhos únicos, tamanhos e hashes reconciliados.
- [x] Enviar os dez IDs autorizados à Lixeira do Drive, nove diretamente e um pela raiz ancestral.
- [x] Confirmar que os dez IDs não aparecem mais fora da Lixeira.
- [x] Relistar a árvore canônica e revalidar o raw R03.
- [x] Registrar relatório final sem segredos ou payloads.
- [x] Criar commit próprio para a limpeza remota.

**Gate:** os notebooks permanecem consultáveis e verificados, as dez raízes
antigas estão recuperáveis na Lixeira e o raw canônico continua idêntico.

Evidência: `data_samples/operations/r09_drive_cleanup_20260803/result.json` e
os catálogos da mesma operação. O staging reconciliado foi movido para a
Lixeira do macOS após a validação.
