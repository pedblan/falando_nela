# Validação — inventário dos dados no Drive

Status: **piloto real revisado em 2026-07-23 — aceito somente como baseline exploratório**.

## Evidência local

- módulo:
  [`../../../processamento/inventario_drive.py`](../../../processamento/inventario_drive.py);
- notebook:
  [`../../../notebooks/dados/00_inventario_drive_colab.ipynb`](../../../notebooks/dados/00_inventario_drive_colab.ipynb);
- testes do módulo:
  [`../../../tests/test_inventario_drive.py`](../../../tests/test_inventario_drive.py);
- testes do notebook:
  [`../../../tests/test_drive_inventory_colab_notebook.py`](../../../tests/test_drive_inventory_colab_notebook.py).

As fixtures locais demonstram:

- nenhuma alteração nos arquivos sob a raiz examinada;
- recusa de saída localizada dentro da raiz;
- limite de leitura dos arquivos estruturados;
- classificação explícita e incerteza preservada;
- referência ausente convertida em aviso, sem correção;
- pacote D06 com `succeeded` e `needs_review`;
- notebook integralmente executável com os gates desligados.

## Evidência real

A operação `drive-inventory-20260724t020749z` registrou:

- `execution_status=succeeded` e `scientific_gate=needs_review`;
- 7.859 itens catalogados e reconciliados;
- 4.987 arquivos e 2.872 diretórios;
- 91 manifests estruturados reconhecidos;
- 0 escritas na raiz aprovada;
- 1.871 inconsistências sinalizadas, sem correção automática.

O diagnóstico agregado mostrou que 1.688 das 1.692 referências ausentes eram
relativas. Destas, 1.682 pertenciam a duas cópias do mesmo manifest de
amostras, e 6 ao inventário de separadores. O código produtor declara essas
referências relativamente a `input_root` ou `parquet_root`, enquanto o piloto
tentou resolvê-las contra a pasta do manifest ou a raiz geral.

Essa limitação invalida o uso do piloto para saneamento ou migração, mas não a
contagem de itens nem a comprovação de leitura somente leitura.

## Evidências obrigatórias

| Requisito | Evidência de aprovação |
|---|---|
| INV-R01, INV-R02 | raiz aprovada, teste local somente leitura e futura evidência real |
| INV-R03 | amostra confrontada com os metadados reais do Drive |
| INV-R04, INV-R06 | execuções reconstruídas e referências verificadas |
| INV-R05 | dicionário das unidades e denominadores usados no relatório |
| INV-R07, INV-R08 | método de triagem e justificativa dos hashes calculados |
| INV-R09 | campos de inferência, confiança e motivo preenchidos |
| INV-R10, INV-R11 | mapa e tabelas abertos na fixture; revisão real pendente |
| INV-R12 | plano de migração separado, sem alterações aplicadas |
| INV-R13 | soma dos grupos de universo igual ao total do catálogo |

## Testes de aceitação para eventual migração

O pesquisador deve conseguir responder, usando apenas `mapa_dados.md`:

1. quais são as bases candidatas a canônicas;
2. qual período e unidade cada contagem representa;
3. onde estão os snapshots;
4. quais execuções foram concluídas operacionalmente;
5. quais execuções não foram validadas cientificamente;
6. quais artefatos estão órfãos, duplicados ou sem finalidade conhecida;
7. se todos os itens foram reconciliados e quais unidades ainda não têm
   fonte, camada ou finalidade suficientemente identificadas.

Esses testes permanecem pendentes e só voltam a bloquear o trabalho se uma
migração, reorganização ou limpeza do Drive for proposta. A fase 4 deve validar
suas próprias entradas diretamente.

## Controles quantitativos

- contagem por raiz e por tipo;
- soma dos tamanhos por camada;
- contagem de execuções por estado;
- contagem de referências válidas, ausentes e ambíguas;
- cobertura de campos obrigatórios;
- amostra manual de pelo menos um item de cada camada identificada.

## Condições de reprovação

- alteração no Drive durante a fase somente leitura;
- contagem sem unidade ou denominador;
- inferência apresentada como fato;
- duplicata excluída ou consolidada automaticamente;
- impossibilidade de rastrear uma linha do catálogo até o item de origem.
