# Validação operacional — G02 migração integral e corte de armazenamento

## Evidência documental congelada

- [x] Confirmar que o catálogo histórico tem 2.887 linhas e 14.686.043.352 bytes.
- [x] Confirmar SHA-256 do arquivo de catálogo igual a `cabe9aae5071d25bdae6459b99064d2ed37110ffaed0c30b95867dd798d22319`.
- [x] Confirmar digest lógico pós-limpeza igual a `6a8395a9fb60a999a97562b7f0c791ac766f161e01664ea549ad52bf36bb0930`.
- [x] Confirmar SHA-256 do plano histórico igual a `ef933d8cbe89ff5d1110c5e743fddfd2cb314711b31c9eed7dbb60fc1a56606b`.
- [x] Confirmar distribuição de 70 metadata, 2.811 monthly text e 6 transcription queue.
- [x] Confirmar exatamente dois objetos vazios, ambos com o MD5 do conteúdo vazio.
- [x] Confirmar 2.884 pendentes, três sentinelas e 38 lotes no plano histórico.
- [x] Confirmar quatro lotes acima de 512 MiB, cada qual com um único objeto.
- [x] Confirmar a amostra determinística com 16 objetos e 13.966.298 bytes.

## Validação local da implementação

- [x] Confirmar que todo passo acionável deste plano usa checkbox CommonMark.
- [x] Recusar G02 quando qualquer gate de G01 estiver incompleto.
- [x] Recusar projeto, bucket, prefixo, source remote ou folder ID divergente.
- [x] Recusar dependência do projeto ativo do `gcloud` em toda chamada GCP.
- [x] Aceitar somente os dois zeros aprovados e normalizar seu SHA-256.
- [x] Recusar SHA-256 ausente em objeto não vazio e zero inesperado.
- [x] Produzir 38 lotes determinísticos e isolar os quatro objetos grandes.
- [x] Testar dry-run exato, faltante, surpresa, diferença, remoção e erro.
- [x] Testar cópia parcial, retomada, conflito e resultado remoto ambíguo.
- [x] Testar invalidação descendente quando input ou artefato mudar.
- [x] Testar reconciliação de bytes, MD5, CRC32C e generations.
- [x] Testar reexecução com zero chamada mutável e generations idênticas.
- [x] Testar seleção determinística dos 16 objetos de restauração.
- [x] Testar `cutover` ausente, não aprovado, repetido e com manifest conflitante.
- [x] Confirmar ausência de token, conta pessoal, ADC e config rclone em artefatos.
- [x] Confirmar ausência de `sync`, `move`, delete, overwrite e mutação de IaC/IAM.
- [x] Executar lock, lint, formatação, testes unitários e integração local relevante.
- [x] Revisar diff por caches, credenciais, dados raw e mudanças fora do escopo.

## Readback anterior a qualquer acesso remoto

```bash
gcloud projects describe falando-nela-pedblan \
  --project=falando-nela-pedblan
gcloud storage buckets describe gs://falando-nela-pedblan-data \
  --project=falando-nela-pedblan
gcloud storage ls 'gs://falando-nela-pedblan-data/data/raw/v1/**' \
  --project=falando-nela-pedblan
```

- [ ] Registrar conta ativa esperada sem persisti-la no repositório.
- [ ] Confirmar projeto ACTIVE, billing habilitado e região `southamerica-east1`.
- [ ] Confirmar bucket privado, Standard, PAP enforced e acesso uniforme.
- [ ] Confirmar permissões da migradora limitadas a criar e visualizar objetos.
- [ ] Confirmar prefixo com exatamente três sentinelas e nenhuma surpresa.
- [ ] Registrar checksums das configurações locais do gcloud e do ADC existente.

## Gate G02-B — preflight e dry-run

- [ ] Confirmar source catalog e config pelos digests congelados.
- [ ] Confirmar a origem Drive por locator, tamanho e hashes disponíveis.
- [ ] Confirmar contagem e bytes por categoria e no total.
- [ ] Confirmar os dois zeros e nenhuma outra exceção de integridade.
- [ ] Confirmar 38 lotes, máximo de 100 arquivos e quatro singletons grandes.
- [ ] Confirmar três `=`, 2.884 `+` e zero outro marcador no dry-run.
- [ ] Confirmar comando sem segredo, uma tentativa e quatro transferências.
- [ ] Atualizar a estimativa com a tabela vigente do Cloud Storage.
- [ ] Obter aprovação humana registrada antes de emitir token ou copiar.

## Gate G02-C — cópia e integridade

- [ ] Confirmar uma tentativa por objeto ausente e execução sequencial dos lotes.
- [ ] Confirmar artefato de progresso e reconciliação para cada lote.
- [ ] Confirmar que toda incerteza remota foi resolvida por readback.
- [ ] Confirmar 2.887 locators, 14.686.043.352 bytes e zero surpresa no GCS.
- [ ] Comparar tamanho e MD5 dos 2.887 objetos.
- [ ] Registrar CRC32C e generation de todos os objetos.
- [ ] Confirmar SHA-256 lógico e do manifest final.
- [ ] Publicar `migration-complete.json` com `ifGenerationMatch=0` e verificar
  sua generation.
- [ ] Reexecutar e comprovar zero escrita e nenhuma nova generation.
- [ ] Restaurar 16 objetos em diretório temporário vazio e fora do repositório.
- [ ] Comparar tamanho e SHA-256 de toda a amostra restaurada.
- [ ] Reconciliar o Drive e comprovar que a baseline continua intacta.
- [ ] Confirmar checksums de gcloud/ADC idênticos ao snapshot inicial.
- [ ] Confirmar custo observado menor ou igual ao aprovado.

## Gate G02-D — corte

- [ ] Revisar humanamente o catálogo final, restauração, idempotência e custo.
- [ ] Registrar aprovação explícita de GCS como fonte oficial raw.
- [ ] Confirmar novamente identidade, project ID, bucket, prefixo e operation ID.
- [ ] Publicar `cutover.json` com `ifGenerationMatch=0`.
- [ ] Fazer readback da generation exata do manifest de corte.
- [ ] Confirmar `authoritative_raw = "gcs"` na configuração versionada.
- [ ] Confirmar que nenhuma configuração local ou remota do Drive foi alterada.
- [ ] Confirmar que o executável ainda não foi antecipado para o corte G05.

## Critério de conclusão

G02 termina somente quando todos os objetos da baseline estão reconciliados no
GCS, a reexecução não cria generations, a amostra é restaurada por conteúdo, o
Drive permanece intacto, o custo está dentro do aprovado e o gate humano de
corte está registrado. Até esse último gate, a fonte oficial continua sendo o
Drive, mesmo que a cópia integral já exista.
