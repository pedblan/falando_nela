# Notebooks de dados

Esta pasta contém operações preparatórias anteriores à análise científica.
Esses cadernos não definem perguntas de pesquisa nem executam modelos.

## Inventário do Drive

[`00_inventario_drive_colab.ipynb`](00_inventario_drive_colab.ipynb) cataloga
somente a raiz aprovada:

```text
/content/drive/MyDrive/falando_nela/data
```

Controles:

- montagem do Drive desligada por padrão;
- execução do inventário desligada por padrão;
- confirmação literal do `operation_id`;
- leitura seletiva limitada a 5 MiB por arquivo estruturado;
- saída somente em `/content/falando_nela_inventory/<operation_id>/`;
- nenhuma chamada à OpenAI;
- nenhuma escrita, movimentação ou exclusão no Drive.

O primeiro resultado real deve permanecer em `scientific_gate: needs_review`
até a revisão conjunta de `relatorio.md`, `mapa_dados.md`,
`catalogo_universos.csv` e `inconsistencias.csv`.

Contrato:
[`../../specs/reinicio_analise_plenario/03_inventario_dados_drive/`](../../specs/reinicio_analise_plenario/03_inventario_dados_drive/).

## Censo das bases candidatas ao snapshot v2

[`01_censo_bases_snapshot_v2_colab.ipynb`](01_censo_bases_snapshot_v2_colab.ipynb)
mede somente:

```text
processed/textos_parlamentares/v1/parquet/
├── camara__plenario_discursos.parquet
├── senado__plenario_discursos.parquet
└── senado__congresso_discursos.parquet
```

Controles:

- montagem do Drive e execução desligadas por padrão;
- confirmação literal de um novo `operation_id`;
- leitura de metadados e colunas de controle, sem carregar `texto`;
- saída em `/content/falando_nela_snapshot_census/<operation_id>/`;
- nenhum `snapshot_id`, escrita no Drive ou chamada à OpenAI.

Contrato:
[`../../specs/reinicio_analise_plenario/04_snapshot_discursos_v2/`](../../specs/reinicio_analise_plenario/04_snapshot_discursos_v2/).
