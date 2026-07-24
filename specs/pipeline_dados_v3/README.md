# Pipeline de dados v3

## Estado

Contrato geral aprovado. Apenas o submódulo
`01_inventario_metadados_raw` possui specs e implementação nesta etapa.

A implementação e o smoke do passo 01 estão autorizados. Nenhum outro
submódulo, batch da OpenAI ou dado derivado v3 está autorizado.

## Objetivo

Reconstruir, a partir do `raw/` preservado, toda a linha pós-coleta do projeto:

```text
raw imutável
  → inventário de metadados
  → vocabulário normalizado
  → adaptadores por fonte
  → plano declarativo de marcadores por GPT-5.6
  → validação e normalização por um motor Python comum
  → snapshot
  → análise
```

## Estrutura

| Submódulo | Estado | Finalidade |
|---|---|---|
| `01_inventario_metadados_raw` | implementado; aguardando smoke Colab | observar campos e valores recebidos |
| `02_schema_normalizado` | reservado | definir categorias e schema v3 |
| `03_adaptadores_fontes` | reservado | mapear metadados preenchidos por fonte |
| `04_oradores_turnos` | reservado | identificar marcadores textuais com GPT-5.6 |
| `05_normalizacao_integral` | reservado | gerar a camada processada v3 |
| `06_snapshot_plenario` | reservado | selecionar o corpus científico |
| `07_analise` | reservado | definir perguntas e métodos analíticos |

Os diretórios reservados não contêm decisões implícitas. Suas specs serão
escritas e aprovadas uma etapa por vez.

Cada submódulo ativo terá, no mínimo, `requirements.md`, `validation.md`,
`tech-stack.md` e `plan.md`.
