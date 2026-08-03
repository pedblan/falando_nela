# Requisitos operacionais — R03 piloto raw do Drive

## Objetivo

Importar, sem recoleta e sem escrita remota, exatamente 1% do primeiro estrato
anual não vazio do corpus textual do Plenário do Senado a partir da árvore
canônica copy-first já reconciliada. A operação termina em raw gzip e metadados
técnicos; processamento e análise pertencem a R04.

## Raiz local aprovada

- **R03-PILOT-ROOT-01:** a execução real usará exatamente
  `/Users/pedblan/PycharmProjects/falando_nela/data_samples`.
- **R03-PILOT-ROOT-02:** `data_samples/` será ignorada integralmente pelo Git e
  só será aceita com `profile=local` e
  `data_profile=sample_annual_1pct`; `cloud`, `full` e qualquer outro caminho
  interno ao clone serão recusados.

## Estrato e baseline

- **R03-REQ-01:** o estrato é
  `senado × plenario_discursos × pronunciamento_texto × 2010`. O valor
  `pronunciamento_texto`, e não `discurso`, é o `record_type` literal gravado
  pelo coletor nas partições mensais.
- **R03-REQ-02:** a pasta antiga de origem da organização tem ID confirmado
  `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`, agora sob
  `falando_nela_arquivo/data/raw`. A nova raiz operacional `falando_nela`,
  criada pelo remote `drive.file`, tem o ID confirmado
  `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`. O piloto usará esse ID como
  `root_folder_id` somente depois de sua árvore ser copiada, reconciliada e
  exposta por remote `drive.readonly`. A reserva `falando_nela_refundacao` não
  será usada.
- **R03-REQ-03:** o inventário G01 de ID
  `12s9Rs4iLVEH9locUUqvSzrwFQh5ZJNL1` é a baseline. Ele contém 2.891 arquivos,
  14.686.044.612 bytes e 5.292 itens totais entre arquivos e diretórios.
- **R03-REQ-04:** para 2010, a baseline registra 11 JSONL, 89.253.442 bytes,
  2.996 registros observados e zero rejeição. Logo, se a reconciliação real
  confirmar `N=2.996`, a meta será `k=ceil(2.996 × 0,01)=30` registros.
- **R03-REQ-05:** descoberta read-only autenticada em `2026-08-03` confirmou a
  árvore `senado/plenario_discursos/ano=2010/mes=02..12`, com 11 JSONL e
  89.253.442 bytes. A listagem integral também reproduziu 2.891 arquivos e
  14.686.044.612 bytes da manchete G01. O CSV local foi autenticado pelo
  SHA-256 `1ab73d3173454b4f556eff02cd202d0dd76740dd7d42d8e24093785dd0cc21a6`;
  a reconciliação integral terminou com zero ausência, acréscimo ou alteração
  e quatro IDs do provedor preservados em três grupos de identidade.

## Fonte e preflight

- **R03-REQ-06:** o adaptador remoto aceitará somente `rclone lsjson` e
  `rclone cat`. `copy`, `copyto`, `sync`, `move`, `delete`, `purge`, upload e
  comandos server-side mutáveis não existirão na interface de origem.
- **R03-REQ-07:** a configuração rclone será cifrada e privada. O programa não
  abrirá o INI descriptografado: exigirá `config encryption check` e analisará
  somente a saída efêmera de `config redacted` para confirmar `type=drive`,
  `scope=drive.readonly` e a presença de uma raiz configurada. Como o rclone
  1.75 mascara `root_folder_id` nessa saída, toda leitura fixará o ID canônico
  aprovado como override da referência remota. A senha virá do Chaves do macOS
  por `RCLONE_PASSWORD_COMMAND`, com prompt desativado. Tokens e demais valores
  sensíveis não serão serializados, exibidos nem copiados.
- **R03-REQ-08:** o preflight comparará a árvore canônica com o catálogo final
  da organização e sua linhagem até a baseline G01. Ausência, acréscimo,
  tamanho ou hash diferente bloqueará a operação; nenhuma divergência será
  corrigida por coleta.
- **R03-REQ-09:** o comando remoto que lê conteúdo exigirá a confirmação literal
  do ID canônico validado. Listagem e dry-run não materializam raw.

## Identidade e seleção

- **R03-REQ-10:** a identidade será a serialização canônica de `source`,
  `dataset`, `record_type`, `substantive_year` e `source_id`; os quatro campos
  raw e a data necessária para derivar o ano são obrigatórios no piloto.
- **R03-REQ-11:** o ano substantivo virá de `periodo.data_inicio`. Registros sem
  data válida, fora de 2010 ou fora do estrato serão rejeitados com motivo e
  não entrarão em `N`.
- **R03-REQ-12:** a chave de seleção será
  `SHA-256(sample_seed UTF-8 + NUL + identidade_canônica UTF-8)`. Empates serão
  desfeitos pela identidade.
- **R03-REQ-13:** a primeira passagem persistirá somente identidade, chave,
  locator, linha, hash e contagens no SQLite; não persistirá payload raw.
- **R03-REQ-14:** `k=max(1, ceil(N × 0,01))`. O manifest de seleção será
  congelado antes da segunda passagem e ordenado por chave e identidade.

## Etapas, retomada e publicação

```text
preflight -> inventory -> rank -> freeze_selection -> materialize -> validate -> publish
```

- **R03-REQ-15:** cada etapa seguirá
  `pending -> running -> completed|failed|blocked|cancelled`. Retomada de um
  estado terminal para `pending` será registrada como nova tentativa.
- **R03-REQ-16:** o manifesto distinguirá operação, etapa e tentativa e
  registrará fingerprints de entrada e configuração, versão, dependências,
  artefatos, hashes, bytes lidos, erro e resultado remoto ambíguo.
- **R03-REQ-17:** uma etapa concluída só será reutilizada quando configuração,
  inventário e hash do artefato coincidirem. Alteração depois da publicação
  bloqueará o mesmo `operation_id` e exigirá snapshot novo.
- **R03-REQ-18:** o estado `running` será persistido antes de qualquer stream.
  Artefatos usarão temporário e promoção atômica; `completed` será registrado
  somente depois de o artefato existir e seu hash ser confirmado.
- **R03-REQ-19:** a segunda passagem relerá a origem, conservará cada envelope
  JSON raw selecionado e gravará somente esses registros em JSONL com LF.
- **R03-REQ-20:** o gzip terá `mtime=0`, nome vazio e conteúdo ordenado pela
  seleção. Serão registrados hashes do conteúdo descompactado, do objeto gzip
  e de cada registro.
- **R03-REQ-21:** a publicação ficará em
  `raw/sample_annual_1pct/<sample_id>/senado/plenario_discursos/ano=2010/` e
  será imutável. Reexecução idêntica não substituirá nem duplicará arquivos.
- **R03-REQ-22:** manifestos e ledger ficarão em
  `operations/sample_pilot/<operation_id>/`; os JSONL e gzip temporários ficarão
  em `tmp/<operation_id>/`. Arquivos parciais nunca entrarão no snapshot
  publicado.
- **R03-REQ-23:** o total da operação será bloqueado antes de exceder a quota
  local de 2 GiB ou a reserva mínima de 5 GiB.

## Não objetivos

- Chamar APIs parlamentares, reparar lacunas ou modificar o Drive.
- Importar metadata, fila de transcrição ou outros anos no piloto.
- Normalizar, deduplicar semanticamente, produzir Parquet/DuckDB ou analisar.
- Executar em Google Cloud ou criar backup.
