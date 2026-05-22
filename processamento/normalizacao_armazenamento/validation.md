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
  - `raw_run_ids` incorporados ao processed;
  - `raw_run_id_filter`, quando usado;
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

## Validacao das amostras locais

Depois de baixar os ZIPs de
`/content/drive/MyDrive/falando_nela/data/processed/downloads/{run_id}/`,
descompactar localmente em:

```text
data/samples/textos_parlamentares/v1/
```

Conferir que os arquivos descompactados:

- sao JSONL validos;
- mantem `dataset_version = v1`;
- preservam `texto_id`, `source`, `dataset`, `documento_tipo`, `ano`, `mes`,
  `texto` e `raw_path`;
- carregam nomes que identificam base, ano e mes.

## Validacao dos Parquets unificados

Rodar a conversao Parquet nos dois ambientes suportados, sempre conferindo que
as raizes de entrada e saida sao as corretas para o ambiente.

### Colab

Usar o notebook dedicado:

```text
notebooks/processamento/geracao_parquets_colab.ipynb
```

Entrada esperada:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/
```

Saida esperada:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

O manifest da conversao deve ficar em:

```text
/content/drive/MyDrive/falando_nela/data/processed/manifests/{run_id}-parquet.json
```

### Samples locais

Entrada esperada:

```text
data/samples/textos_parlamentares/v1/
```

Saida esperada:

```text
data/samples/textos_parlamentares/v1/parquet/
```

O manifest da conversao deve ficar em:

```text
data/samples/textos_parlamentares/v1/parquet/manifest.json
```

### Checks obrigatorios

- Existem Parquets para todas as bases presentes nos JSONLs de entrada.
- Cada arquivo Parquet contem apenas uma combinacao `source/dataset`, coerente
  com o nome `{source}__{dataset}.parquet`.
- A soma de linhas dos Parquets bate com a quantidade de `texto_id`s distintos
  dos JSONLs processados lidos.
- `dataset_version` e sempre `v1`.
- As colunas seguem o schema processado v1; campos sem valor em uma base ficam
  nulos, nao ausentes.
- Nenhum arquivo dentro de `parquet/` entra novamente como input da conversao.
- No Colab, nenhum arquivo e gravado dentro do repositorio local do notebook;
  a saida deve permanecer no Drive montado.
- Nas samples locais, nenhum caminho absoluto do Colab deve aparecer no manifest
  local, exceto em campos de proveniencia bruta preservados dos registros.

## Validacao dos cadernos exploratorios de Parquet

Validar os cadernos:

```text
notebooks/processamento/exploracao_parquets_colab.ipynb
notebooks/processamento/exploracao_parquets_samples_local.ipynb
```

Checks obrigatorios:

- O JSON do notebook e valido.
- Todas as celulas de codigo compilam com `ast.parse`.
- O caderno Colab aponta para:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- O caderno local aponta para:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- Nenhum dos cadernos executa coleta, normalizacao ou geracao de Parquets.
- O usuario consegue escolher uma base Parquet antes de carregar o `DataFrame`.
- O caderno exibe `df.shape`, `df.head()`, `df.info()`,
  `df.describe(include="all")`, nulos por coluna e `value_counts()` basicos.
- A tabela compacta nao inclui `texto` por default, para manter a navegacao
  responsiva.
- Quando `itables` estiver instalado, a tabela compacta usa visualizacao
  interativa; quando nao estiver, o fallback pandas funciona sem erro.
- Ha uma celula para selecionar `texto_id` ou indice e exibir o `texto` integral
  sem truncamento, junto de metadados de contexto.
- Filtros por ano, mes, documento_tipo, parlamentar, proposicao, orgao e busca
  textual funcionam mesmo quando algumas colunas estao ausentes ou so possuem
  valores nulos.
- O caderno local roda contra os Parquets de samples sem depender de Google
  Drive ou de caminhos `/content/`.
