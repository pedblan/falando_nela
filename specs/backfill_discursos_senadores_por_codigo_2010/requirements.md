# Requisitos: backfill de discursos de senadores por código desde 2010

## Contrato de entrada

- missing-path é um JSONL senator_endpoint_missing_ids.jsonl produzido pela
  auditoria de cobertura de senadores.
- Cada linha selecionada deve ter house, dataset, data,
  codigo_pronunciamento e pronunciamento.
- SF exige dataset plenario_discursos; CN exige dataset congresso_discursos.
- A janela data-inicio/data-fim filtra a população de modo inclusivo.
- Dois registros com o mesmo CodigoPronunciamento só são aceitos se forem
  idênticos após a normalização; divergência interrompe a execução.

## CLI

    python -m coleta.senado.backfill_discursos_por_codigo \
      --mode prod \
      --output-dir /content/drive/MyDrive/falando_nela/data \
      --data-inicio 2010-01-01 --data-fim AAAA-MM-DD \
      --run-id backfill-discursos-senadores-por-codigo-AAAAMMDD-sf \
      --missing-path CAMINHO/senator_endpoint_missing_ids.jsonl \
      --house SF --no-sample --resume

- house aceita SF ou CN e determina o dataset.
- mode, output-dir, run-id, sample e resume seguem o contrato comum de
  CollectionRun.
- Um mesmo run-id e população são retomáveis. Para outra população, usar outro
  run-id.

## Contrato raw

- O caminho é raw/senado/DATASET/ano=AAAA/mes=MM/RUN_ID.jsonl.
- Cada texto é record_type pronunciamento_texto.
- source_id é canônico por casa e CodigoPronunciamento.
- Os campos textuais e os fallbacks são os mesmos de coleta.senado.discursos.
- metadata.senator_endpoint_backfill deve conter missing_path, probe_key,
  parlamentar_ids, data_official e house.
- A leitura da população é registrada em metadata como
  senator_endpoint_backfill_population.

## Segurança e limites

- O raw existente é imutável; o backfill apenas anexa registros novos.
- O coletor exclui metadata e transcription_queue ao verificar IDs existentes.
- ID já presente em qualquer run raw é pulado, sem nova requisição.
- Erro inesperado de um texto deixa somente sua partição falha e é retomado
  com o mesmo run-id e resume.
- CN é cobertura de senadores em sessões conjuntas, não uma substituição da
  descoberta de deputados ou outras autoridades. IDs extras no raw permanecem.

## Reconstrução dos derivados

- A execução depende de senator_endpoint_summary.json com missing_ids,
  errors, invalid_probe_lines, invalid_raw_lines e source_conflicts iguais a
  zero, e somente estado complete na cobertura.
- A normalização usa mode prod, data-root explícito, run-id
  processed-textos-v1-current e overwrite, sem raw-run-id.
- A conversão Parquet usa o perfil colab, o mesmo data-root, run-id
  parquet-textos-v1-current e overwrite.
- O snapshot usa um analysis run id exclusivo do backfill e pode ser refeito
  com overwrite sem alterar raw ou a fotografia current.
