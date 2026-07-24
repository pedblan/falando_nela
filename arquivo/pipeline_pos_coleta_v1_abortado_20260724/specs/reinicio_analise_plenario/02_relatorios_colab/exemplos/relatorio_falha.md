# Relatório da operação

> **Exemplo fictício do contrato D06 aprovado.**

| Campo | Valor |
|---|---|
| Módulo | snapshot de discursos v2 |
| Objetivo | executar teste reduzido de reconciliação |
| Operação | `snapshot-v2-smoke-20260723-example` |
| Período observado | 2010-01-01 a 2026-07-23 |
| Unidade observada | discurso |
| Estado da execução | **failed** |
| Gate científico | **not_evaluated** |

## Resultado

A operação falhou durante a reconciliação final. A saída não foi promovida
para snapshot.

| Etapa | Contagem |
|---|---:|
| registros de entrada | 1.240 |
| exclusões previstas e justificadas | 12 |
| registros esperados após exclusões | 1.228 |
| registros produzidos | 1.227 |
| diferença não explicada | 1 |

Universo: amostra de teste definida para esta operação. Regra de
reconciliação: `1.240 - 12 = 1.228`; a saída contém 1.227 registros.

## Impacto

Um discurso não foi reconciliado. Como a causa ainda é desconhecida, a saída
é incompleta e não pode ser usada nem aprovada cientificamente.

## Artefatos

| Artefato | Finalidade | Local | Ação |
|---|---|---|---|
| diferença de reconciliação | identificar o registro afetado | `artifacts/errors.csv` | revisar |
| manifest mínimo | preservar estado e proveniência da falha | `manifest.json` | nenhuma |
| log | localizar a etapa técnica da interrupção | `logs/execution.jsonl` | abrir para diagnóstico |

## Próxima ação

Inspecione o identificador registrado em `artifacts/errors.csv`, corrija a
causa e reexecute com **um novo `operation_id`**. Não aprove nem promova esta
saída.
