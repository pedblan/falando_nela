# Validation

## Checks obrigatorios

- `pytest` deve passar.
- O CLI deve rodar em `data/dev` sem depender do Google Drive:

```bash
python -m processamento.normalizacao --mode dev --run-id smoke-processed-v1 --overwrite
```

- O manifest deve indicar:
  - `dataset = textos_parlamentares`;
  - `dataset_version = v1`;
  - `output_records > 0` quando houver dados textuais em `raw/`;
  - contagens por `source/dataset`;
  - duplicatas, se houver reexecucoes sobre a mesma unidade textual.

## Inspecao de saida

Verificar que ha arquivos em:

```text
data/dev/processed/textos_parlamentares/v1/ano=YYYY/mes=MM/
```

Conferir uma linha JSONL e confirmar campos essenciais:

- `texto_id`;
- `source`;
- `dataset`;
- `data`, `ano`, `mes`;
- `documento_tipo`;
- `unidade_analitica`;
- `texto`;
- `texto_tamanho`;
- `raw_path`.

## Validacao por familia textual

- Discursos do Senado devem preencher `pronunciamento_id` e, quando disponivel,
  `parlamentar_nome`, `parlamentar_partido` e `parlamentar_uf`.
- Discursos da Camara devem usar o mapa de deputados de `metadata/` para
  preencher parlamentar.
- Notas taquigraficas devem preencher `reuniao_id` ou `evento_id`.
- Pareceres de PEC devem preencher `proposicao_identificacao`,
  `documento_classe`, `status_deliberativo` e `vencido` quando a coleta bruta
  disponibilizar esses campos.

## Validacao no Drive

No Colab, usar:

```text
notebooks/processamento/normalizacao_armazenamento_colab.ipynb
```

Depois da execucao, revisar o manifest em:

```text
/content/drive/MyDrive/falando_nela/data/processed/manifests/
```

Comparar as familias processadas com os manifests de coleta em:

```text
/content/drive/MyDrive/falando_nela/data/manifests/
```

## Validacao do caderno de descricao

Depois da normalizacao, usar:

```text
notebooks/processamento/descricao_analitica_bases_colab.ipynb
```

O caderno deve reportar:

- manifest processed selecionado;
- contagens por `source/dataset/documento_tipo`;
- contagens por ano e familia textual;
- cobertura temporal por base;
- preenchimento de campos-chave;
- exemplos compactos por base;
- manifests de coleta relacionados quando presentes.
