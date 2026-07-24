# Tech stack — inventário dos dados no Drive

Status: **contrato aprovado em 2026-07-23**.

Este documento especializa
[`../tech-stack.md`](../tech-stack.md).

## Ferramentas

- Notebook Colab fino para autenticação, seleção das raízes e execução.
- Python com `pathlib`, `os`, `csv`, `json` e `hashlib`; o primeiro piloto não
  exige `pandas`, `polars` nem `pyarrow`.
- Sistema de arquivos montado pelo Google Drive para listar metadados e abrir
  artefatos selecionados. IDs não expostos pela montagem permanecem ausentes;
  um conector só será adicionado se essa lacuna impedir a auditoria.
- CSV para o primeiro catálogo e para inspeção simples; Parquet somente se o
  volume real justificar; Markdown para o mapa humano.
- [`processamento/inventario_drive.py`](../../../processamento/inventario_drive.py)
  para a lógica testável.
- [`notebooks/dados/00_inventario_drive_colab.ipynb`](../../../notebooks/dados/00_inventario_drive_colab.ipynb)
  como orquestrador protegido.
- [`relatorios_operacionais`](../../../relatorios_operacionais/) para relatório,
  manifest e log no padrão D06.

O primeiro piloto usa CSV, suficiente para inspeção e para o inventário de
metadados. A adoção de Parquet será decidida somente se o volume real
justificar.

## Restrições

- Não usar OpenAI API para inferir a finalidade dos arquivos.
- Não calcular hash integral de todo o Drive por padrão.
- Não depender de um banco de dados novo.
- Não fazer download integral quando os metadados bastarem.
- Caminhos e IDs do Drive permanecem dados; não devem ser reconstruídos por
  concatenação quando um identificador canônico estiver disponível.
