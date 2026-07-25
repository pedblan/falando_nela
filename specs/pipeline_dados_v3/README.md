# Pipeline de dados v3

## Estado

Contrato geral aprovado. `01_inventario_metadados_raw` foi concluído e a
ferramenta de evidências de `02_schema_normalizado` está implementada.

O passo 01 foi concluído e G01 foi aprovado. O catálogo global `schema_core`
foi executado e medido em 691.302 tokens para arquivo + prompt. A chamada
global foi autorizada e seu fluxo retomável está implementado, mas a resposta,
G02 e qualquer dado normalizado v3 continuam condicionados aos gates
explícitos do passo 02. Pilotos exploratórios foram executados, mas não
substituem a avaliação e a aprovação formal de G02.

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
| `01_inventario_metadados_raw` | concluído; G01 aprovado | observar campos e valores recebidos |
| `02_schema_normalizado` | implementação pronta; G02 pendente | propor categorias e schema v3 sem aplicá-los |
| `03_adaptadores_fontes` | reservado | mapear metadados preenchidos por fonte |
| `04_oradores_turnos` | reservado | identificar marcadores textuais com GPT-5.6 |
| `05_normalizacao_integral` | reservado | gerar a camada processada v3 |
| `06_snapshot_plenario` | reservado | selecionar o corpus científico |
| `07_analise` | reservado | definir perguntas e métodos analíticos |

Os diretórios reservados não contêm decisões implícitas. Suas specs serão
escritas e aprovadas uma etapa por vez.

Cada submódulo ativo terá, no mínimo, `requirements.md`, `validation.md`,
`tech-stack.md` e `plan.md`.
