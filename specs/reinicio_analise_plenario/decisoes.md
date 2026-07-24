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
| Execução | módulo e notebook implementados; a varredura real foi autorizada separadamente |

## Encerramento simplificado da fase 3

| Campo | Valor |
|---|---|
| Estado | **aprovado para orientação arquivística** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Operação | `drive-inventory-20260724t020749z` |
| Resultado técnico | `succeeded`; 7.859 itens reconciliados; 0 escritas no Drive |
| Limitação conhecida | 1.688 referências relativas foram resolvidas sem considerar `input_root` ou `parquet_root` declarados nos manifests |
| Decisão | não transformar o piloto em projeto de saneamento do Drive |
| Efeito | encerrar a fase 3 como baseline exploratório e autorizar a identificação controlada das entradas do snapshot v2 |
| Fora do efeito | não aprovar migração, exclusão, deduplicação, base canônica ou os manifests antigos |
| Trabalho adiado | correção do resolvedor, investigação de órfãos e duplicidades e eventual reorganização do Drive |

## Gate de entrada da fase 4 — censo das bases candidatas

| Campo | Valor |
|---|---|
| Estado | **aprovado** |
| Data | 2026-07-23 (`America/Sao_Paulo`) |
| Proposta | [`04_snapshot_discursos_v2/proposta_gate_censo.md`](04_snapshot_discursos_v2/proposta_gate_censo.md) |
| Entradas | três Parquets de discursos de Câmara, Senado e Congresso |
| Leitura | metadados e colunas de controle; sem carregar texto integral |
| Saída | `/content/falando_nela_snapshot_census/<operation_id>/` |
| Efeito | autorizar implementação, publicação e execução controlada do censo |
| Fora do efeito | não aprova D03–D05, não cria snapshot e não autoriza escrita no Drive |

## Decisões ainda pendentes

- D03 — universo do snapshot v2;
- D04 — data de corte do snapshot v2;
- D05 — tratamento de duplicatas entre fontes;
- D07 — perguntas e unidades da nova análise.
