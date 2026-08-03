# Pipeline de dados v3

## Estado

Contrato geral aprovado. `01_inventario_metadados_raw` foi concluído e a
ferramenta de evidências de `02_schema_normalizado` está implementada.

O passo 01 foi concluído e G01 foi aprovado. O catálogo global `schema_core`
foi executado; a entrada final foi recontada em 692.031 tokens, incluindo o
JSON Schema fechado. A chamada produziu `gpt56-global-schema-proposal-v1`,
cujo vocabulário conceitual foi revisado e aprovado em 2026-07-25. A chamada
foi reconciliada e o contrato lógico foi incorporado ao gerador. O livro
integral e a auditoria raw somente leitura foram produzidos e reconciliados.
O Batch autorizado e dois reparos incrementais reconciliaram propostas para
os 23.786
`field_id`, sem aplicá-las; elas ainda aguardam revisão humana. As
demais validações operacionais, G02 e qualquer dado normalizado v3 continuam
condicionados aos gates explícitos do passo 02. Pilotos
exploratórios e aprovação conceitual não substituem a aprovação operacional
de G02. A síntese pronta para essa decisão está em
`02_schema_normalizado/g02_gate_humano_operacional_20260726.md`.

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
| `02_schema_normalizado` | Batch e auditoria reconciliados; gate humano de G02 pendente | propor categorias e schema v3 sem aplicá-los |
| `03_adaptadores_fontes` | reservado | mapear metadados preenchidos por fonte |
| `04_oradores_turnos` | reservado | identificar marcadores textuais com GPT-5.6 |
| `05_normalizacao_integral` | reservado | gerar a camada processada v3 |
| `06_snapshot_plenario` | reservado | selecionar o corpus científico |
| `07_analise` | reservado | definir perguntas e métodos analíticos |

Os diretórios reservados não contêm decisões implícitas. Suas specs serão
escritas e aprovadas uma etapa por vez.

Cada submódulo ativo terá, no mínimo, `requirements.md`, `validation.md`,
`tech-stack.md` e `plan.md`.
