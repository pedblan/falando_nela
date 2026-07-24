# Gate do censo das bases candidatas

Status: **aprovado pelo pesquisador em 2026-07-23**.

## Finalidade

Medir as bases processadas que podem alimentar o snapshot v2 antes de decidir
o universo D03. O censo produz evidência; ele não aprova nenhuma base e não
cria o snapshot.

## Raiz e entradas autorizadas

Raiz única:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

Arquivos:

```text
camara__plenario_discursos.parquet
senado__plenario_discursos.parquet
senado__congresso_discursos.parquet
```

Ficam fora:

- CCJ e CCJC;
- pareceres de PEC;
- `apartes_parlamentares/v1`;
- amostras e downloads;
- snapshots, manifests e resultados da análise v1.

## Política de leitura

- ler metadados Parquet e colunas de controle;
- não carregar o campo `texto` integral;
- medir schema, registros, período, cobertura textual, autores, proveniência,
  IDs e sobreposições exatas;
- não aplicar filtro temporal, elegibilidade, segmentação ou deduplicação.

## Saída

O piloto grava somente em:

```text
/content/falando_nela_snapshot_census/<operation_id>/
```

O pacote usa D06 e nasce em `scientific_gate=needs_review`.

## O que este gate não autoriza

- aprovar D03, D04 ou D05;
- criar ou sobrescrever snapshot;
- gravar, mover ou apagar dados no Drive;
- incluir bases fora da lista;
- chamar a OpenAI;
- executar análise científica.

Mesmo após a publicação do código, a leitura real depende de flag e confirmação
literal de um novo `operation_id` no Colab.
