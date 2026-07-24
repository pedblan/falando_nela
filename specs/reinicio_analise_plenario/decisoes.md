# Registro de decisões — reinício da análise de plenário

Este registro documenta aprovações humanas vinculadas às specs deste pacote.
Uma decisão aprovada não comprova que a ação correspondente já foi executada.

## Aprovação do contrato

| Campo | Valor |
|---|---|
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Decisor | pesquisador |
| Decisão | aprovar as specs gerais e as specs dos quatro submódulos |
| Efeito | os contratos deixam de ser rascunhos; cada implementação continua condicionada aos gates aplicáveis |
| Execução | nenhuma ação operacional realizada por esta aprovação |

## D01 — caminho do arquivo local

| Campo | Valor |
|---|---|
| Estado | **aprovada** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Caminho aprovado | `notebooks/arquivo/analise_plenario_v1_abortada_20260723/` |
| Condições | inventário prévio, preservação integral e mapa reversível de caminhos |
| Execução | concluída e validada em 2026-07-23 |

## D02 — marcador da execução antiga no Drive

| Campo | Valor |
|---|---|
| Estado | **aprovada** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Execução em escopo | `analise-plenario-20260717-v1` |
| Marcador aprovado | `encerrada_sem_validacao_cientifica` |
| Condições | não mover, apagar nem regravar os dados antigos |
| Execução | marcador criado e verificado em 2026-07-23 |
| Arquivo no Drive | `ENCERRADA_SEM_VALIDACAO_CIENTIFICA.md` |
| ID do arquivo | `1JJN7_SFKmwWeutJuyuNz5fhbCr1t_5lJ` |
| Pasta confirmada | `1LVULojH62hRTJ4mVhZSVo09KrXCpefS-` |

## D06 — contrato mínimo de relatório e manifest

| Campo | Valor |
|---|---|
| Estado | **aprovada** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Proposta | [`02_relatorios_colab/proposta_d06.md`](02_relatorios_colab/proposta_d06.md) |
| Evidência | três relatórios fictícios, manifest de exemplo, JSON Schema e catálogo de artefatos |
| Decisão | aprovar o formato, os dois estados independentes, os 21 campos e os nomes canônicos |
| Efeito da aprovação | autorizar a implementação da biblioteca reutilizável |
| Fora do efeito | não autoriza o piloto, alteração no Drive nem criação do snapshot v2; esses passos conservam seus próprios gates |
| Execução | biblioteca implementada e validada localmente em 2026-07-23 |

## Gate inicial da fase 3 — raiz e taxonomia

| Campo | Valor |
|---|---|
| Estado | **aprovado** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Raiz | `/content/drive/MyDrive/falando_nela/data` |
| Taxonomia | classe, camada, fonte e origem da classificação |
| Limite de conteúdo | arquivos estruturados selecionados de até 5 MiB |
| Saída | `/content/falando_nela_inventory/<operation_id>/` |
| Efeito | autorizar construção e teste local do notebook piloto |
| Fora do efeito | não autoriza a varredura real, escrita no Drive, migração ou snapshot |
| Execução | módulo e notebook implementados; Drive não varrido |

## Decisões ainda pendentes

- D03 — universo do snapshot v2;
- D04 — data de corte do snapshot v2;
- D05 — tratamento de duplicatas entre fontes;
- D07 — perguntas e unidades da nova análise.
