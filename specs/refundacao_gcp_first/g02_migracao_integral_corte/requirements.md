# Requisitos — G02 migração integral e corte do raw

## Objetivo

Migrar sem transformação a baseline raw aprovada do Google Drive para o bucket
GCS da refundação, com evidência suficiente para confiar no destino e restaurar
dados. Depois de uma decisão humana própria, o GCS passa a ser a autoridade raw
para G03 e fases seguintes; o Drive permanece arquivo de rollback.

## Baseline e destinos

- **G02-DATA-01:** a origem é a pasta raw canônica do Drive, ID
  `1n0FTylozV_HRSGcWHyJhpZAuHOcnZ3f9`, acessada em modo somente leitura.
- **G02-DATA-02:** a referência de G02 é o catálogo pós-limpeza com 2.887
  objetos, 14.686.043.352 bytes e digest lógico
  `6a8395a9fb60a999a97562b7f0c791ac766f161e01664ea549ad52bf36bb0930`.
- **G02-DATA-03:** um inventário atual deverá confirmar essa baseline antes da
  cópia. Diferença de locator, conteúdo ou tamanho deverá ser explicada e
  resolvida; G02 não fará recoleta nem aceitará silenciosamente uma nova
  baseline.
- **G02-DATA-04:** o destino é
  `gs://falando-nela-pedblan-data/data/raw/v1/`, no projeto explícito
  `falando-nela-pedblan`. O locator relativo e o conteúdo serão preservados.
- **G02-DATA-05:** os três objetos enviados em G01 contam como parte da
  baseline e deverão ser reconhecidos como iguais, não recopiados.
- **G02-DATA-06:** arquivos vazios já documentados na baseline são válidos; a
  validação usará o hash conhecido do conteúdo vazio sem criar uma regra geral
  para aceitar outros casos inesperados.

## Segurança e preservação

- **G02-SAFE-01:** nenhuma etapa poderá escrever, mover ou excluir conteúdo no
  Drive. A credencial da origem terá escopo somente leitura.
- **G02-SAFE-02:** a cópia criará somente objetos ausentes. Objeto existente
  diferente é conflito e nunca será substituído, apagado ou versionado para
  “corrigir” a migração.
- **G02-SAFE-03:** projeto, bucket, prefixo e pasta de origem serão explícitos
  na operação; o projeto default do `gcloud` não decidirá o alvo.
- **G02-SAFE-04:** serão usadas credenciais curtas ou identidade anexada, sem
  chave JSON nova. Tokens, contas pessoais e configuração rclone não entrarão
  em manifests, logs ou Git.
- **G02-SAFE-05:** logs e relatórios registrarão locators, hashes, contagens,
  estados e erros redigidos, sem copiar o conteúdo parlamentar integral.

## Execução recuperável

- **G02-OPS-01:** cada execução terá identificador e evidências persistidas que
  permitam distinguir planejamento, progresso, verificação e corte.
- **G02-OPS-02:** a cópia será dividida em lotes retomáveis. Quantidade,
  tamanho, ordem e concorrência poderão ser escolhidos ou ajustados conforme os
  arquivos, limites da ferramenta e estabilidade observada.
- **G02-OPS-03:** a retomada consultará o estado do destino, pulará objetos já
  íntegros e trabalhará somente nos ausentes. Resultado remoto ambíguo será
  reconciliado antes de nova escrita.
- **G02-OPS-04:** retries serão limitados e justificáveis. Não é necessária
  aprovação humana por lote nem por ajuste operacional dentro dos limites
  desta spec.
- **G02-OPS-05:** antes da cópia integral haverá um dry-run ou prova equivalente
  que mostre objetos iguais, ausentes, conflitantes e inesperados, junto da
  estimativa de custo.
- **G02-OPS-06:** a operação produzirá um relatório auditável, mas nomes de
  arquivos e formato interno dos artefatos são escolhas da implementação.

## Integridade e restauração

- **G02-VER-01:** a verificação final exigirá o conjunto completo esperado no
  GCS, com os mesmos locators e bytes e sem objetos inesperados sob o prefixo.
- **G02-VER-02:** todo checksum comparável disponível deverá coincidir. Quando
  origem e GCS não oferecerem o mesmo algoritmo, a evidência poderá combinar
  metadados do inventário, checksum do transporte e restauração por conteúdo.
- **G02-VER-03:** uma segunda verificação ou reexecução deverá demonstrar que o
  estado íntegro produz zero nova escrita e preserva as gerações existentes.
- **G02-VER-04:** será restaurada em diretório vazio uma amostra representativa
  escolhida antes do download. Ela cobrirá categorias e casos relevantes da
  baseline, incluindo pelo menos um arquivo grande, um pequeno e os vazios
  conhecidos.
- **G02-VER-05:** o tamanho exato da amostra não é contratual. Ela será grande
  o bastante para cobrir os casos relevantes e pequena o bastante para manter
  a validação rápida e barata; locator, bytes e hash do conteúdo deverão
  coincidir em todos os itens selecionados.
- **G02-VER-06:** incidentes recuperados podem ser aceitos se a causa, a ação e
  o readback final ficarem registrados e nenhum requisito de integridade for
  relaxado.

## Decisões humanas e corte

- **G02-GATE-01:** uma pessoa aprovará a cópia integral após revisar origem,
  destino, inventários, conflitos, método e estimativa. Essa é a única
  aprovação necessária durante a transferência, salvo mudança material de
  escopo, risco ou custo.
- **G02-GATE-02:** presença dos dados no GCS não muda automaticamente a fonte
  oficial. Outra aprovação humana revisará reconciliação, idempotência,
  restauração, preservação do Drive e custo observado.
- **G02-GATE-03:** o corte será uma ação separada e recuperável: atualizará
  `authoritative_raw = "gcs"` e registrará no GCS uma evidência create-only
  associada à operação aprovada.
- **G02-GATE-04:** até a aprovação e o readback do corte, o Drive continua
  sendo a fonte oficial. Depois do corte, permanece arquivo read-only; o
  comportamento geral do executável só muda em G05.

## Margem operacional

Sem alterar esta spec, o operador pode mudar:

- quantidade e tamanho dos lotes;
- ordem de transferência e paralelismo seguro;
- limites de retry e timeout;
- ferramenta ou comando usados pela implementação existente;
- formato e nomes dos artefatos auxiliares;
- composição e tamanho da amostra de restauração.

Essas escolhas devem apenas ficar registradas e preservar os requisitos de
destino explícito, origem read-only, create-only, retomada, integridade, custo e
auditoria. Mudança em qualquer desses invariantes exige revisão antes de seguir.

## Custo e condição de parada

- A migração usará o budget já criado em G01; não criará infraestrutura nova.
- O planejamento registrará uma estimativa e um teto operacional. A referência
  inicial é até US$ 1,00 para G02 dentro do limite global de US$ 5,00.
- Estimativa acima da referência poderá ser aceita com justificativa humana,
  desde que não comprometa o limite global.
- Conflito de conteúdo, risco de overwrite, destino incerto, escrita no Drive,
  credencial persistente ou custo sem margem bloqueiam a operação.

## Fora do escopo

- nova coleta, atualização temporal ou mudança de schema;
- IaC, IAM, lifecycle ou novos recursos GCP;
- processamento Parquet, Cloud Run, BigQuery ou Marimo;
- remoção, reorganização ou reconfiguração do Drive;
- limpeza de objetos GCS conflitantes;
- corte operacional cloud-first de G05.
