# Análise de plenário v1 — arquivo histórico

Status: **encerrada sem validação científica em 2026-07-23**.

Este diretório preserva a tentativa v1 da análise comparativa de discursos de
plenário. Os caminhos internos reproduzem a localização original dos arquivos
no repositório.

## Identidade preservada

| Campo | Valor |
|---|---|
| Branch de origem | `main` |
| Commit de origem | `64b313cfad8561a199a48b9c54b284f1409bc1cf` |
| Mensagem do commit | `Refaz episódios multiturno do caderno 3` |
| Execução associada no Drive | `analise-plenario-20260717-v1` |
| Estado científico | `encerrada_sem_validacao_cientifica` |
| Arquivos do mapa aprovado | 53 |
| Bytes preservados do mapa | 794.298 |

O mapa de origem, destino, tamanho e SHA-256 está em
[`specs/reinicio_analise_plenario/01_arquivamento_v1/mapa_arquivamento.csv`](../../../specs/reinicio_analise_plenario/01_arquivamento_v1/mapa_arquivamento.csv).

## Conteúdo

- `analise/`: pacote Python, configuração e specs metodológicas da suíte v1;
- `notebooks/analise/`: notebooks 00–09 e célula auxiliar;
- `notebooks/coleta/` e `notebooks/processamento/`: dois orquestradores
  históricos que ainda construíam o snapshot v1;
- `scripts/`: geradores desses notebooks;
- `specs/`: contratos dos dois ciclos históricos associados;
- `tests/`: testes da suíte e cópia integral do teste misto de discursos
  históricos.

## Por que foi encerrada

A tentativa não estabeleceu com segurança o universo total de discursos e
transcrições. Além disso, a segmentação de intervenções podia separar respostas
curtas de seu contexto conversacional, prejudicando a análise qualitativa dos
atos de fala. A revisão humana da segmentação não foi concluída.

Execução técnica concluída, arquivo produzido ou Batch processado não devem ser
interpretados como aprovação científica.

## O que permanece válido

- dados oficiais nas camadas `raw` e `processed`;
- Parquets canônicos, sujeitos ao novo inventário;
- evidências operacionais e proveniência dos backfills;
- snapshots e saídas antigas como material auditável, nunca como entrada
  automática da nova análise.

Nenhum dado local ou do Drive foi apagado por este arquivamento.

## Reutilização

Estes arquivos não devem ser executados diretamente nem copiados de volta em
bloco. Lógica específica pode ser consultada e reaproveitada somente depois de
ser reavaliada contra as novas specs.

A nova sequência de trabalho está em
[`specs/reinicio_analise_plenario/`](../../../specs/reinicio_analise_plenario/README.md):

1. inventário dos dados e execuções no Drive;
2. contrato simplificado de relatório, manifest e log;
3. snapshot v2 aprovado;
4. uma spec própria para cada etapa científica.
