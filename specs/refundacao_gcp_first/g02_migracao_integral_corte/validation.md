# Validação — G02 migração integral e corte do raw

## Princípio

G02 será aceito pelas provas do resultado, não pela repetição literal de um
roteiro. Comandos, nomes de artefatos e quantidade de lotes podem variar. Uma
evidência automatizada pode substituir uma conferência manual equivalente se
for legível e permanecer associada ao identificador da operação.

## Contrato e implementação local

- [x] Confirmar que `plan.md`, `requirements.md` e este documento descrevem o
  mesmo objetivo, baseline, destino e dois pontos de decisão humana.
- [x] Confirmar que as specs não fixam quantidade de lotes, concorrência,
  retries, formato de relatório ou tamanho exato da amostra.
- [x] Confirmar que ajustes operacionais seguros podem ocorrer sem nova
  aprovação a cada lote.
- [x] Executar os testes locais de configuração, migração, retomada,
  reconciliação, restauração e corte.
- [x] Confirmar que testes locais e CI não dependem de GCP ou Drive reais.
- [x] Revisar código e logs para impedir overwrite, mutação do Drive e exposição
  de credenciais.

Validação local sugerida:

```bash
uv run pytest \
  tests/refundacao_gcp_first/test_gcp_config.py \
  tests/refundacao_gcp_first/test_gcs_migration.py \
  tests/refundacao_gcp_first/test_gcs_full_migration.py
```

Comandos equivalentes do ambiente são aceitáveis; não é preciso executar a
suíte completa se as mudanças e o risco permanecerem restritos a G02.

Resultado em `2026-08-11`: os 50 testes direcionados e os 317 testes da suíte
completa passaram em ambiente local. Os testes G02 usam doubles para GCS e
Drive, bloqueiam rede externa e não exigem credenciais ou efeitos remotos.

## Evidência antes da cópia

- [x] Registrar identificador da operação, commit e configuração usada.
- [x] Confirmar projeto `falando-nela-pedblan`, bucket
  `falando-nela-pedblan-data` e prefixo `data/raw/v1` por readback explícito.
- [x] Confirmar origem Drive correta e credencial somente leitura.
- [x] Confirmar que o inventário atual corresponde à baseline de 2.887 objetos
  e 14.686.043.352 bytes.
- [x] Confirmar no destino os três sentinelas íntegros e classificar todo o
  restante como ausente, igual, conflitante ou inesperado.
- [x] Resolver conflitos e surpresas sem overwrite antes de continuar.
- [x] Registrar plano de lotes, estimativa, teto de custo e condição de parada.
- [x] Registrar aprovação humana da cópia integral.

**Aceite pré-cópia:** alvo e origem inequívocos, baseline reconciliada, nenhum
conflito pendente e custo aprovado. Não se exige uma quantidade predeterminada
de lotes ou um texto literal de comando.

Evidência de `2026-08-11`: a operação recuperável
`g02-full-20260811-v1`, vinculada à revisão `afebd26`, concluiu preflight e
dry-run na primeira tentativa. O relatório contém três `=`, 2.884 `+` e zero
`-`, `*` ou `!`; o GCS continua com somente os três sentinelas e 78.822 bytes.
Os parâmetros correntes são lotes de até 100 arquivos ou 512 MiB, quatro
transferências, um retry, uma low-level retry e amostra com objetos de até
16 MiB. São parâmetros ajustáveis, mas qualquer alteração posterior produzirá
outro digest de aprovação. Estimativa: US$ 0,30; teto proposto: US$ 1,00;
condição de parada: conflito, overwrite, destino/origem divergente, escrita no
Drive, credencial persistente ou custo acima do teto sem nova decisão.
A aprovação humana vinculou a cópia ao digest
`7c536e2ee91e79cf312891b40a726bcb1da663e852dbe810019409a718871e41`
e ao teto de US$ 1,00.

## Evidência da migração

- [x] Demonstrar que somente objetos ausentes foram criados.
- [x] Manter progresso suficiente para retomar depois de ao menos uma parada
  simulada ou real, sem recópia do que já estiver íntegro.
- [x] Registrar ajustes relevantes de lote, concorrência ou retry e seus motivos.
- [x] Confirmar ao final todos os locators e bytes esperados e zero surpresa.
- [x] Confirmar checksums comparáveis de todos os objetos e explicar qualquer
  método complementar usado quando os algoritmos diferirem.
- [x] Demonstrar por reexecução ou verificação equivalente zero nova escrita e
  preservação das gerações existentes.
- [x] Confirmar por inventário final que o Drive permaneceu inalterado.
- [x] Registrar custo observado e eventuais incidentes resolvidos.

**Aceite da migração:** baseline completa no GCS, nenhum objeto substituído,
retomada e idempotência demonstradas e Drive intacto.

Resultado da operação `g02-full-20260811-v1`: 2.884 objetos ausentes e
14.685.964.530 bytes foram criados; os três sentinelas existentes foram
preservados. Os 38 lotes terminaram na primeira tentativa, com progresso
persistido por objeto e por lote; as simulações locais cobrem retomada após
interrupção. Não foi necessário ajustar os parâmetros aprovados. O inventário
final contém os 2.887 locators e 14.686.043.352 bytes esperados, com checksums
comparáveis íntegros e origem relistada como `unchanged`. A segunda passagem
produziu 2.887 marcadores `=`, zero escrita e o mesmo fingerprint de metadados.
A estimativa foi US$ 0,30, dentro do teto de US$ 1,00, e não houve incidente.

## Evidência de restauração

- [x] Registrar antes do download a amostra e a razão de sua composição.
- [x] Incluir categorias distintas e pelo menos um arquivo grande, um pequeno e
  os vazios conhecidos.
- [x] Restaurar em diretório vazio fora do repositório e de `data/`.
- [x] Comparar locator, bytes e hash do conteúdo de todos os itens restaurados.
- [x] Excluir o diretório temporário somente depois de registrar o resultado,
  ou preservá-lo fora do repositório até a aprovação do corte.

**Aceite da restauração:** cobertura representativa e correspondência integral
da amostra. Não há número fixo de arquivos ou bytes se os casos relevantes
estiverem cobertos.

A seleção registrada usou a estratégia
`sentinels+known_empty+source_dataset+smallest+largest_within_limit`: 17 objetos
e 30.335.827 bytes. Todos os locators, tamanhos e hashes coincidiram com o
catálogo final, e o diretório temporário foi removido somente após a emissão de
`restore.json`.

## Evidência do corte

- [x] Consolidar inventários, checksums, idempotência, restauração, preservação
  do Drive, incidentes e custo em uma síntese revisável.
- [x] Registrar aprovação humana explícita para GCS como autoridade raw.
- [x] Executar o corte como ação separada, ligada à operação aprovada.
- [x] Confirmar `authoritative_raw = "gcs"` na configuração versionada.
- [x] Fazer readback da evidência create-only publicada no GCS.
- [x] Confirmar que o Drive continua disponível somente para leitura e rollback.
- [x] Confirmar que G02 não antecipou processamento, app Marimo ou o corte G05.

O manifesto candidato ao corte foi publicado create-only em
`manifests/migrations/g02/g02-full-20260811-v1/migration-complete.json`, geração
`1786505426515430`, e relido com o mesmo SHA-256 local e remoto:
`230e40d4dfa2a57dd27659724f07b2cba3279e8b1e7f9e9f911bec5ee958a5e7`.
O corte final foi publicado em
`manifests/migrations/g02/g02-full-20260811-v1/cutover.json`, geração
`1786530130887793`, e relido com o mesmo `SHA-256` de payload
`35e68992b94de2671775e99b3eb73b3a24334dcfa7d4ae1a98fa45b5377f6b95`.
`authoritative_raw` está `gcs` em `config/gcp.toml`.

## Critério de conclusão

G02 termina quando a baseline estiver integralmente reconciliada no GCS, a
retomada e a ausência de nova escrita forem demonstradas, uma amostra
representativa for restaurada por conteúdo, o Drive permanecer intacto, o
custo estiver aprovado e o corte para `authoritative_raw = "gcs"` tiver
aprovação e readback. Até o último passo, o Drive continua sendo a fonte
oficial, mesmo que a cópia já esteja completa.
