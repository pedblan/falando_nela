# Plan

## Etapa 1: contrato processed v1

- Definir o dataset `textos_parlamentares/v1`.
- Registrar schema versionado em `data/schemas/processed_textos_parlamentares_v1.schema.json`.
- Registrar dicionario de dados em
  `data/schemas/processed_textos_parlamentares_v1.dictionary.md`.
- Manter JSONL particionado por `ano` e `mes` como formato inicial, sem
  adicionar dependencia pesada.

## Etapa 2: normalizador

- Implementar CLI em `python -m processamento.normalizacao`.
- Ler o diretorio `raw/` inteiro ou um subconjunto informado por `--dataset`.
- Normalizar os record types textuais:
  - `pronunciamento_texto`;
  - `discursos_page`;
  - `notas_taquigraficas`;
  - `parecer_pec_texto`.
- Usar metadados de deputados da Camara apenas para enriquecer registros de
  discursos.
- Escrever manifest de execucao em `processed/manifests/`.

## Etapa 3: validacao local

- Testar normalizadores por fonte com registros sinteticos.
- Rodar um smoke em `data/dev`.
- Confirmar que a saida particionada e o manifest sao gerados.
- Confirmar que reexecucoes duplicadas nao inflam a saida.

## Etapa 4: execucao no Drive

- Usar o notebook operacional:

```text
notebooks/processamento/normalizacao_armazenamento_colab.ipynb
```

- O notebook monta o Drive, atualiza o repositorio, instala dependencias e
  chama `normalize_data_root(...)` diretamente em Python.
- Usar `PROCESSED_RUN_ID` para nomear a execucao processada. Esse identificador
  nao precisa coincidir com os `run_id`s brutos.
- Deixar `RAW_RUN_IDS = []` para consolidar todos os JSONLs em `raw/` com
  deduplicacao por `texto_id`. Preencher `RAW_RUN_IDS` apenas se for necessario
  restringir explicitamente quais execucoes brutas entram.
- Alternativamente, em ambientes com terminal, rodar:

```bash
export FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data
python -m processamento.normalizacao --mode prod --run-id processed-textos-v1-YYYYMMDD
```

- Revisar o manifest gerado no Drive.
- Se necessario, repetir com `--dataset fonte/dataset` para isolar problemas.

## Etapa 5: descricao analitica das bases

- Usar o notebook:

```text
notebooks/processamento/descricao_analitica_bases_colab.ipynb
```

- Produzir uma leitura resumida por fonte/dataset/familia textual.
- Conferir cobertura temporal, quantidade de registros, tamanho medio de texto,
  preenchimento de campos-chave e exemplos compactos por base.
- Usar essa descricao para decidir prioridades dos cadernos analiticos e da
  amostragem local.

## Etapa 6: amostras locais

- Criar, depois da validacao de `processed`, uma rotina separada para ZIPs de
  amostras por base.
- Critério inicial: 1% por ano e por familia textual, com minimo operacional a
  definir para anos muito pequenos.
- No Colab, gravar ZIPs em
  `/content/drive/MyDrive/falando_nela/data/processed/downloads/{run_id}/`.
- Depois do download, descompactar localmente em:

```text
data/samples/textos_parlamentares/v1/
```

- Manter os nomes dos JSONLs com base, ano e mes para evitar colisao quando
  varios ZIPs forem descompactados no mesmo diretorio.
