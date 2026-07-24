# Cadernos do pipeline de dados v3

Estes cadernos reconstruirão a linha pós-coleta usando somente
`/content/drive/MyDrive/falando_nela/data/raw` como entrada imutável.

## Passo 01 — inventário de metadados raw

`01_inventario_metadados_raw_colab.ipynb`:

- verifica que `data/` contém somente `raw/`;
- faz um smoke determinístico por fonte, dataset e formato;
- grava os sete artefatos temporários somente sob `/content`;
- não chama a OpenAI;
- não escreve no Drive;
- mantém a execução completa bloqueada até a revisão humana do smoke.

Não use `Run all` para autorizar uma operação. As flags de smoke e execução
completa nascem desligadas e cada gate exige a cópia literal do respectivo
`operation_id`.
