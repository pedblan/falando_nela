# Requisitos operacionais — R03 organização copy-first do Drive

## Objetivo

Criar uma árvore canônica versionada do raw no Drive, por cópia byte a byte,
preservando a árvore antiga e a periodicidade contratada de plenários e
comissões.

## Layout

O destino lógico de cada arquivo será:

```text
data/raw/v1/<source>/<dataset>/<relative_path_inside_dataset>
```

- Corpus textual continua em `ano=YYYY/mes=MM/<run_id>.jsonl[.gz]`.
- Descoberta, pautas, detalhes e status continuam em `metadata/`.
- Candidatos sem texto continuam em `transcription_queue/`.
- Arquivos de controle fora do raw não entram na árvore canônica por inferência.

O escopo inicial cobre:

- plenários: `camara/plenario_discursos`, `camara/plenario_apartes`,
  `senado/plenario_discursos`, `senado/plenario_apartes` e
  `senado/congresso_discursos`;
- comissões: `camara/ccjc_eventos` e `senado/ccj_notas`;
- documentos que atravessam plenário e comissão:
  `camara/pareceres_pec` e `senado/pareceres_pec`.
- metadados transversais usados pelos dois fluxos:
  `camara/parlamentares` e `senado/parlamentares`, ambos metadata-only.

## Segurança e transporte

- **R03-ORG-01:** o remote de origem será read-only e enraizado no ID
  `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`. Sua raiz de projeto foi renomeada para
  `falando_nela_arquivo`, preservando o ID
  `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB` e todo o conteúdo.
- **R03-ORG-02:** o remote de destino `raw-destination-rw`, com escopo
  `drive.file`, criou uma nova pasta `falando_nela` na raiz do Meu Drive. O ID
  `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq` foi confirmado pelo mesmo cliente OAuth,
  congelado como `root_folder_id` e a pasta foi confirmada vazia antes de
  qualquer cópia.
  `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, é uma
  reserva e não participará da operação.
- **R03-ORG-03:** a configuração rclone será cifrada, terá modo `0600` ou mais
  restrito e ficará fora do clone, backups e manifests. Sua senha será obtida
  do Chaves do macOS por `RCLONE_PASSWORD_COMMAND`; `RCLONE_CONFIG_PASS` será
  recusado. A aplicação exigirá `config encryption check`, analisará somente
  `config redacted` e executará sem prompt interativo. Como essa projeção
  mascara `root_folder_id` no rclone 1.75, cada referência de origem e destino
  carregará explicitamente o ID aprovado como override do remote.
- **R03-ORG-03A:** o cliente OAuth desktop próprio pertence ao projeto Google
  Cloud `falando-nela-pedblan`. O projeto usa audiência externa em teste, a
  conta operacional como usuária de teste e a Drive API habilitada.
- **R03-ORG-04:** o plano permitirá somente listagem, cópia imutável e leitura
  necessária para verificação. Origem nunca receberá comando mutável. A cópia
  atravessará o cliente rclone em streaming, sem
  `--server-side-across-configs`, para preservar o escopo mínimo do destino.
- **R03-ORG-05:** cada destino será único. Colisão entre duas origens, caminho
  fora do layout ou categoria desconhecida bloqueará a geração do plano.
- **R03-ORG-05A:** o inventário usado para reconciliar G01 conterá todos os
  arquivos da origem. Só depois da igualdade integral serão separados os 2.887
  JSONL elegíveis dos quatro itens não raw observados, dois notebooks e dois
  arquivos sem extensão; estes receberão decisão explícita de exclusão.
- **R03-ORG-05B:** os dois arquivos sem extensão que a listagem rclone apresenta
  com o mesmo caminho serão vinculados ao ID do provedor. A distinção G01
  `Untitled`/`Untitled (1)` não será recriada por heurística de nome. Como o CSV
  G01 não contém IDs, caminho visível, tamanho, hash e decisão idênticos
  autorizam somente um grupo de equivalência entre o conjunto dos IDs atuais e
  o conjunto dos locators G01, nunca uma atribuição individual inventada.
- **R03-ORG-05C:** o dry-run integral consumirá somente o inventário e o
  relatório G01 já reconciliados. Ele congelará exatamente os locators
  `copy_immutable` em uma lista NUL-delimited e executará uma única sessão
  `rclone copy --files-from0 --dry-run --immutable --checksum --retries 1`.
  A execução real usará a mesma lista congelada particionada em lotes limitados,
  com `rclone copy --files-from0 --immutable --checksum --retries 1
  --transfers 4`. Cada lote atravessará o cliente, sem cópia server-side, e só
  ganhará checkpoint após readback e reconciliação de todos os seus objetos.

## Operação recuperável

```text
discover -> map -> dry_run -> copy_sentinel -> verify_sentinel
         -> copy_batches -> verify_all -> publish_catalog
```

- **R03-ORG-06:** o manifest registrará fingerprints dos dois inventários, do
  mapeamento e da configuração não secreta; etapas, tentativas, remote IDs,
  bytes, hashes, erros e ambiguidade remota.
- **R03-ORG-07:** antes de cada lote, o destino será inventariado e objetos já
  presentes serão reconciliados. Depois da resposta, o destino será relistado e
  cada objeto do lote será comparado por caminho, tamanho e hash antes de
  `completed`.
- **R03-ORG-08:** se a resposta da cópia for ambígua, a retomada reconciliará o
  destino e reconstruirá a lista apenas com objetos ainda ausentes; não repetirá
  automaticamente efeitos já confirmados.
- **R03-ORG-09:** objeto já existente e idêntico será reutilizado; objeto
  divergente será bloqueado, nunca substituído.
- **R03-ORG-10:** lotes terão contagem e bytes limitados, listas e relatórios de
  transporte próprios, progresso por objeto e avanço condicionado à verificação
  integral do lote anterior.
- **R03-ORG-11:** o catálogo final provará bijeção entre todos os arquivos
  aceitos da origem e seus destinos, com zero ausência, acréscimo ou colisão.
- **R03-ORG-12:** o dry-run só será concluído quando o relatório combinado do
  rclone contiver exatamente uma entrada `+` por locator congelado, nenhuma
  entrada `=`, `-`, `*` ou `!`, zero erro e o destino continuar vazio por
  readback. Plano, lista de locators, relatório combinado e resumo terão
  tamanho e SHA-256 registrados no manifest retomável.

## Não objetivos

- Apagar ou esvaziar a árvore antiga.
- Usar, mover, renomear ou preencher a reserva `falando_nela_refundacao`.
- Mudar nomes de datasets, `record_type`, conteúdo ou granularidade temporal.
- Compactar o raw durante a organização remota.
- Copiar derivados, ambientes, notebooks ou credenciais para `data/raw/v1/`.
- Executar a cópia integral antes do lote sentinela aprovado.
