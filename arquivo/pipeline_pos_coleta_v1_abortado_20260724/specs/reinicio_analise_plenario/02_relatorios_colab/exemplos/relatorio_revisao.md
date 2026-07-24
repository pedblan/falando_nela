# Relatório da operação

> **Exemplo fictício do contrato D06 aprovado. As contagens não descrevem o Drive
> real do projeto.**

| Campo | Valor |
|---|---|
| Módulo | inventário do Drive |
| Objetivo | catalogar artefatos legados sem mover ou regravar dados |
| Operação | `drive-inventory-20260723-example` |
| Período observado | conteúdo disponível até 2026-07-23 |
| Unidade observada | item do Drive |
| Estado da execução | **succeeded** |
| Gate científico | **needs_review** |

## Resultado

O programa terminou normalmente, mas o inventário **ainda não está
aprovado**. Foram catalogados **1.297 itens**, encontrados nas três raízes
autorizadas. Eles foram agrupados em 18 execuções aparentes.

| Contagem | Valor | Universo ou regra |
|---|---:|---|
| itens catalogados | 1.297 | todos os itens acessíveis nas três raízes aprovadas |
| execuções aparentes | 18 | agrupamento por IDs e caminhos declarados |
| referências verificadas | 164 | referências de manifest que puderam ser resolvidas |
| referências válidas | 157 | subconjunto das 164 referências verificadas |
| referências ausentes | 7 | subconjunto das 164 referências verificadas |
| relações inferidas | 23 | relações sem ID explícito, inferidas pelo caminho e nome |

Nenhum item foi movido, apagado ou regravado.

## Pontos que exigem revisão

1. Há **7 referências ausentes**. Elas podem representar artefatos removidos,
   caminhos antigos ou manifests incompletos.
2. Há **23 relações inferidas**, não comprovadas por um identificador
   canônico.
3. O agrupamento em 18 execuções é operacional; ele ainda não define quais
   dados serão considerados canônicos no snapshot v2.

## Artefatos

| Artefato | Finalidade | Local | Ação |
|---|---|---|---|
| catálogo completo | listar os 1.297 itens | `artifacts/catalogo.parquet` | consultar por filtros |
| inconsistências | mostrar as 7 referências ausentes | `artifacts/inconsistencias.csv` | revisar |
| manifest | registrar proveniência e contagens | `manifest.json` | não é necessário para a revisão normal |
| log | diagnóstico técnico | `logs/execution.jsonl` | abrir somente se houver dúvida técnica |

## Avisos e erros

Há avisos de consistência, mas não houve falha de execução. Os detalhes estão
em `artifacts/inconsistencias.csv`.

## Próxima ação

Revise as sete inconsistências e confirme ou corrija as 23 relações inferidas.
Depois disso, aprove ou rejeite o inventário. **Não inicie o snapshot v2
enquanto o gate continuar em `needs_review`.**
