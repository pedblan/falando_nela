# Requisitos operacionais — G02 migração integral e corte de armazenamento

## Estado

Contrato proposto para revisão em `2026-08-11`. A produção destas specs não
autoriza implementação, upload, alteração de infraestrutura nem corte. G02 só
pode executar depois da conclusão integral e documentada dos gates G01-B,
G01-C e G01-D.

## Resultado principal

Copiar a baseline raw canônica do Google Drive para
`gs://falando-nela-pedblan-data/data/raw/v1/` em lotes imutáveis e retomáveis,
reconciliar os 2.887 objetos e 14.686.043.352 bytes, demonstrar restauração e
idempotência e, somente após aprovação humana própria, declarar o GCS como
fonte oficial de dados raw. O Drive permanecerá intacto e disponível como
arquivo somente leitura para rollback.

## Pré-condições e bloqueios

- **G02-PRE-01:** G01 deverá ter encerrado seus três gates remotos, com plano
  OpenTofu vazio, três sentinelas íntegros no GCS e evidência de que o projeto
  `default` do `gcloud`, o ADC e o Drive permaneceram inalterados.
- **G02-PRE-02:** antes de qualquer acesso remoto, o operador confirmará conta,
  project ID `falando-nela-pedblan`, região `southamerica-east1`, bucket
  `falando-nela-pedblan-data`, prefixo `data/raw/v1` e pasta Drive raw de ID
  `1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9`.
- **G02-PRE-03:** o destino inicial conterá exatamente os três objetos
  sentinela aprovados em G01, com os mesmos tamanhos, hashes e gerações, e
  nenhum outro objeto sob o prefixo raw.
- **G02-PRE-04:** a implementação de G01 rejeita atualmente objetos com zero
  byte; essa incompatibilidade deverá ser corrigida e validada em tarefa
  própria antes do preflight de G02. A spec não autoriza corrigir G01 durante a
  migração integral.
- **G02-PRE-05:** qualquer divergência de infraestrutura, permissões, baseline,
  hashes, custo ou pré-condição bloqueará G02 sem reparo remoto automático.

## Baseline congelada

| Evidência | Valor exigido |
|---|---|
| Catálogo histórico | `data_samples/operations/organize_drive/r03-drive-copy-batched-20260803/copy-catalog.jsonl` |
| SHA-256 do arquivo de catálogo | `cabe9aae5071d25bdae6459b99064d2ed37110ffaed0c30b95867dd798d22319` |
| SHA-256 lógico pós-limpeza | `6a8395a9fb60a999a97562b7f0c791ac766f161e01664ea549ad52bf36bb0930` |
| Plano histórico de lotes | `data_samples/operations/organize_drive/r03-drive-copy-batched-20260803/copy-execution-plan.json` |
| SHA-256 do arquivo de plano | `ef933d8cbe89ff5d1110c5e743fddfd2cb314711b31c9eed7dbb60fc1a56606b` |
| Arquivos | 2.887 |
| Bytes | 14.686.043.352 |
| Metadata | 70 arquivos; 7.474.785.101 bytes |
| Monthly text | 2.811 arquivos; 7.193.005.043 bytes |
| Transcription queue | 6 arquivos; 18.253.208 bytes |

- **G02-BASE-01:** a execução copiará apenas objetos presentes nessa baseline;
  conteúdo surgido depois dela exigirá uma atualização temporal futura.
- **G02-BASE-02:** o preflight reconciliará a baseline com a pasta raw do Drive
  por locator, tamanho e hashes disponíveis, sem escrever em nenhum sistema.
- **G02-BASE-03:** os dois objetos vazios abaixo são parte legítima da baseline:
  `camara/plenario_discursos/ano=1954/mes=12/prod-historico-camara-plenario.jsonl`
  e
  `camara/plenario_discursos/ano=1956/mes=06/prod-historico-camara-plenario.jsonl`.
  Ambos têm MD5 `d41d8cd98f00b204e9800998ecf8427e`; para a reconciliação,
  seu SHA-256 esperado será normalizado para
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- **G02-BASE-04:** SHA-256 ausente em objeto não vazio, outro zero byte não
  aprovado ou qualquer diferença de locator, tamanho ou MD5 bloqueará a etapa.

## Interface e artefatos recuperáveis

```text
falando-nela gcs-migrate full \
  --through preflight|dry-run|copy|verify|idempotency|restore \
  --operation-id ID --gcp-config config/gcp.toml \
  --source-catalog CAMINHO --g01-operation-root CAMINHO \
  --rclone-config CAMINHO --source-remote drive.readonly \
  --source-folder-id 1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9 \
  --confirm-source-folder-id 1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9 \
  --confirm-project-id falando-nela-pedblan \
  --confirm-bucket falando-nela-pedblan-data \
  --operator-account CONTA \
  --batch-max-files 100 --batch-max-bytes 536870912
```

- **G02-CLI-01:** cada etapa usará `RecoverableOperation`, arquivos temporários
  e promoção atômica; mudança em configuração ou artefato ascendente invalidará
  etapas descendentes.
- **G02-CLI-02:** a operação persistirá sob um `operation_id` novo e não
  reutilizará os artefatos mutáveis de G01 ou da cópia histórica R03.
- **G02-CLI-03:** manifests registrarão apenas parâmetros não secretos,
  digests, comandos redigidos, decisões, estados e evidências. Conta pessoal,
  access token, ADC e conteúdo do arquivo rclone não serão serializados.
- **G02-CLI-04:** resultado remoto ambíguo será reconciliado antes de nova
  tentativa. A ferramenta nunca presumirá falha nem repetirá escrita às cegas.
- **G02-CLI-05:** nenhuma etapa executará `sync`, `move`, delete, overwrite,
  criação de bucket, alteração de IAM ou mudança do projeto `default`.

## Dry-run, lotes e cópia

- **G02-COPY-01:** o dry-run combinado deverá produzir exatamente três
  igualdades para os sentinelas e 2.884 criações pendentes; remoção, diferença,
  conflito ou objeto inesperado bloqueará o upload.
- **G02-COPY-02:** os 2.884 objetos pendentes serão divididos
  deterministamente em 38 lotes, com máximo de 100 arquivos e alvo de
  536.870.912 bytes. Um único arquivo maior que o alvo formará lote isolado e
  não será fragmentado.
- **G02-COPY-03:** os quatro lotes excepcionalmente grandes serão congelados:

| Lote | Locator | Bytes |
|---|---|---:|
| `batch-0008` | `data/raw/v1/camara/plenario_apartes/metadata/prod-camara-plenario-apartes-baseline.jsonl` | 2.152.427.540 |
| `batch-0021` | `data/raw/v1/senado/ccj_notas/metadata/prod-historico-senado-ccj.jsonl` | 1.306.048.420 |
| `batch-0022` | `data/raw/v1/senado/ccj_notas/metadata/prod-senado-ccj-baseline.jsonl` | 1.259.261.628 |
| `batch-0023` | `data/raw/v1/senado/ccj_notas/metadata/prod-senado-ccj-complemento-ate-2024.jsonl` | 1.011.872.949 |

- **G02-COPY-04:** lotes serão executados sequencialmente; dentro de um lote,
  rclone usará `copy`, `--immutable`, `--checksum`, `--check-first`, uma
  tentativa, uma low-level retry e no máximo quatro transferências.
- **G02-COPY-05:** retomada recalculará o conjunto exato, ausente e conflitante;
  copiará somente ausentes e recusará substituir um objeto existente.
- **G02-COPY-06:** a origem será o remote `drive.readonly` fixado pelo ID raw; o
  destino usará credencial curta por impersonação de `fn-migrator` e project
  number versionado, sem depender do projeto ativo do `gcloud`.

## Reconciliação, restauração e idempotência

- **G02-VER-01:** a reconciliação final relistará o GCS no projeto explícito e
  exigirá exatamente 2.887 locators e 14.686.043.352 bytes, sem faltantes,
  surpresas ou conflitos.
- **G02-VER-02:** por objeto, o manifest final registrará locator de origem e
  destino, bytes, MD5 e SHA-256 esperados, MD5 e CRC32C observados no GCS,
  generation, metageneration, storage class e estado da verificação.
- **G02-VER-03:** a validação aproveitará MD5 e CRC32C fornecidos pelo GCS e não
  fará download integral dos 14,7 GB apenas para recalcular SHA-256. SHA-256
  será confirmado por restauração independente da amostra, conforme o modelo
  oficial de [validação de dados do Cloud Storage](https://docs.cloud.google.com/storage/docs/data-validation).
- **G02-VER-04:** a amostra determinística será a união dos três sentinelas,
  dois objetos vazios e o primeiro objeto não vazio, com até 16 MiB e SHA-256,
  de cada par distinto `(source, dataset)`. A baseline atual resulta em 16
  objetos únicos e 13.966.298 bytes.
- **G02-VER-05:** a restauração ocorrerá em diretório temporário novo, fora do
  repositório e de `data/`, preferencialmente fixando a generation; tamanho e
  SHA-256 de todos os 16 objetos deverão coincidir.
- **G02-VER-06:** a reexecução integral fará preflight, dry-run e reconciliação,
  produzirá zero upload e manterá todas as generations GCS inalteradas.
- **G02-VER-07:** antes do gate de corte, o catálogo e a evidência final serão
  selados localmente e, com `ifGenerationMatch=0`, em
  `manifests/migrations/g02/<operation_id>/migration-complete.json`.

## Gates humanos e corte

- **G02-GATE-01:** antes da cópia, uma pessoa aprovará project ID, identidade,
  origem, destino, catálogo, contagem, bytes, 38 lotes, quatro exceções,
  comando redigido, estimativa e limite de custo.
- **G02-GATE-02:** conter uma cópia íntegra no GCS não muda por si só a fonte
  oficial; uma segunda aprovação humana examinará a reconciliação, a
  idempotência, a restauração, o custo e a integridade do Drive.
- **G02-GATE-03:** após G02-GATE-02, um comando `gcs-migrate cutover` separado
  atualizará a configuração versionada para `authoritative_raw = "gcs"` e
  publicará, com a precondição `ifGenerationMatch=0`, um manifest create-only em
  `manifests/migrations/g02/<operation_id>/cutover.json`, conforme as
  [precondições de requisição do Cloud Storage](https://docs.cloud.google.com/storage/docs/request-preconditions).
- **G02-GATE-04:** o corte não habilitará ainda o executável cloud-first; essa
  mudança operacional pertence a G05. Em G02 muda somente a autoridade dos
  dados raw para as fases G03 e seguintes.
- **G02-GATE-05:** o Drive não será reconfigurado, movido nem apagado. O
  readback final apenas comprovará que o remote usado continua read-only e que
  a pasta raw preserva a baseline.

## Custo e interrupção

- **Hipótese:** 14.686.043.352 bytes correspondem a aproximadamente 13,68 GiB;
  em Standard regional, a estimativa de armazenamento é cerca de US$ 0,27/mês.
  As 2.887 escritas Class A custam aproximadamente US$ 0,02, e a entrada de
  dados no GCS é gratuita segundo a
  [tabela oficial](https://cloud.google.com/storage/pricing).
- **Amostra mínima paga:** uma tentativa por objeto ausente e uma restauração
  de 13.966.298 bytes; a reexecução idempotente deverá produzir zero escrita.
- **Máximo de G02:** estimativa conservadora de US$ 1,00, subordinada ao budget
  já aprovado de US$ 5,00 e excluído consumo anterior do projeto.
- **Parada:** falta de margem no budget, estimativa acima de US$ 1,00, operação
  não prevista, repetição paga, checksum divergente ou resultado ambíguo não
  reconciliável exige interrupção e nova aprovação.

## Fora do escopo

- implementar G02 durante esta tarefa de especificação;
- corrigir a incompatibilidade de zero byte de G01 dentro de G02;
- alterar IaC, APIs, bucket, IAM, budget, service accounts ou lifecycle;
- transformar raw em Parquet, executar Cloud Run, BigQuery ou Marimo;
- consultar fontes parlamentares ou incorporar conteúdo posterior à baseline;
- apagar, mover, reorganizar ou tornar gravável qualquer conteúdo do Drive;
- excluir, sobrescrever ou versionar objetos GCS existentes;
- tornar o executável de produção cloud-first antes de G05.
