# Plano operacional — G02 migração integral e corte de armazenamento

## G02-A — contrato e preparação local

- [x] Criar branch própria a partir do commit local de G01.
- [x] Congelar catálogo, digests, contagem, bytes e distribuição da baseline.
- [x] Registrar os dois objetos vazios e sua normalização de SHA-256.
- [x] Congelar 38 lotes, limites e quatro exceções de objeto grande.
- [x] Definir gates, custo, amostra de restauração e política de parada.
- [ ] Corrigir em tarefa própria a incompatibilidade de zero byte de G01.
- [ ] Confirmar conclusão documentada de G01-B, G01-C e G01-D.
- [ ] Implementar `gcs-migrate full` e `gcs-migrate cutover`.
- [ ] Cobrir preflight, lotes, retomada, reconciliação, restauração e corte.
- [ ] Executar validações locais sem acesso remoto ou credencial.

**Gate G02-A:** contrato aprovado, G01 integralmente concluído, implementação
local validada e nenhum efeito remoto novo produzido por G02.

## G02-B — preflight e dry-run integral

- [ ] Criar um `operation_id` novo e registrar os inputs por digest.
- [ ] Fazer readback explícito de conta, projeto, região, bucket e prefixo.
- [ ] Confirmar que o destino contém exatamente os três sentinelas de G01.
- [ ] Reconciliar o Drive com 2.887 objetos e 14.686.043.352 bytes.
- [ ] Confirmar os dois zeros aprovados e recusar qualquer caso adicional.
- [ ] Gerar deterministicamente 38 lotes para os 2.884 objetos pendentes.
- [ ] Confirmar os quatro objetos grandes em lotes isolados.
- [ ] Executar dry-run combinado com três `=` e 2.884 `+`.
- [ ] Confirmar zero marcador de remoção, diferença, erro ou surpresa.
- [ ] Registrar comando redigido e estimativa atualizada menor ou igual a US$ 1,00.
- [ ] Obter aprovação humana de identidade, baseline, lotes, comando e custo.

**Gate G02-B:** origem e destino congelados, dry-run exato, aprovação humana
registrada e nenhuma escrita de dados executada.

## G02-C — cópia recuperável e reconciliação

- [ ] Gerar token curto por impersonação de `fn-migrator` sem persistência.
- [ ] Executar sequencialmente os 38 lotes, uma tentativa por objeto ausente.
- [ ] Após cada lote, reconciliar estados exato, ausente e conflitante.
- [ ] Resolver resultado ambíguo por readback antes de qualquer retomada.
- [ ] Relistar o prefixo no projeto explícito após o último lote.
- [ ] Confirmar 2.887 objetos, 14.686.043.352 bytes e zero surpresa.
- [ ] Comparar locator, tamanho e MD5 de todos os objetos.
- [ ] Registrar CRC32C, generation, metageneration e storage class do GCS.
- [ ] Selar o catálogo e o manifest final por SHA-256, local e remotamente.
- [ ] Reexecutar a operação e comprovar zero upload e generations idênticas.
- [ ] Restaurar a amostra de 16 objetos e 13.966.298 bytes em diretório novo.
- [ ] Comparar tamanho e SHA-256 dos 16 objetos restaurados.
- [ ] Reconciliar novamente o Drive e confirmar a baseline intacta.
- [ ] Registrar custo observado, erros, retomadas e recursos persistentes.

**Gate G02-C:** cópia integral, idempotente e restaurável no GCS; Drive
inalterado; GCS ainda não declarado fonte oficial.

## G02-D — aprovação e corte da autoridade raw

- [ ] Apresentar reconciliação, generations, restauração e custo para revisão.
- [ ] Obter aprovação humana explícita para tornar GCS a fonte oficial raw.
- [ ] Executar separadamente `gcs-migrate cutover` com confirmações literais.
- [ ] Atualizar a configuração versionada para `authoritative_raw = "gcs"`.
- [ ] Publicar `cutover.json` com precondição create-only e verificar readback.
- [ ] Confirmar o remote Drive read-only e a baseline remota inalterados.
- [ ] Registrar o Drive como arquivo de rollback, sem alterar sua configuração.
- [ ] Revisar diff, manifests e documentação, excluindo segredos e dados raw.

**Gate G02-D:** GCS é a fonte oficial da baseline raw para G03 e fases
seguintes; Drive permanece arquivo read-only e o executável só muda em G05.
