# Relatório da operação

> **Exemplo fictício do contrato D06 aprovado.**

| Campo | Valor |
|---|---|
| Módulo | arquivamento v1 |
| Objetivo | verificar a cópia local antes do encerramento da versão |
| Operação | `archive-validation-20260723-example` |
| Período dos dados | não aplicável |
| Unidade observada | arquivo |
| Estado da execução | **succeeded** |
| Gate científico | **not_applicable** |

## Resultado

A verificação terminou normalmente. Foram comparados **53 arquivos de 53
esperados**. Os 53 pares de origem e destino têm o mesmo tamanho e o mesmo
SHA-256. Não houve arquivo ausente nem hash divergente.

| Contagem | Antes | Depois | Diferença |
|---|---:|---:|---:|
| arquivos no universo do mapa | 53 | 53 | 0 |
| arquivos sem hash verificável | 0 | 0 | 0 |

Universo: somente os caminhos declarados no mapa de arquivamento desta
operação. Nenhum arquivo do Drive foi incluído.

## Artefatos

| Artefato | Finalidade | Local | Ação |
|---|---|---|---|
| mapa do arquivamento | relacionar origem e destino | `artifacts/mapa_arquivamento.csv` | consultar apenas se necessário |
| manifest | registrar proveniência | `manifest.json` | nenhuma |
| log | permitir diagnóstico técnico | `logs/execution.jsonl` | não abrir em operação normal |

## Avisos e erros

Nenhum.

## Próxima ação

Nenhuma ação é necessária. Esta operação não produz resultado científico e,
por isso, seu gate é `not_applicable`.
