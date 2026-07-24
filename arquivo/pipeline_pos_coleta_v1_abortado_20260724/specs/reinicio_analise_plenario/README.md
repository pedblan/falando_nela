# Reinício controlado da análise de plenário

Status: **contrato aprovado em 2026-07-23 — gates progressivos ativos**.

As aprovações e decisões são registradas em [`decisoes.md`](decisoes.md).

Este pacote especifica o arquivamento da análise de plenário v1, a
simplificação dos relatórios operacionais do Colab, o inventário dos dados no
Drive e a construção opcional de um snapshot v2. Ele não define ainda as
etapas científicas da nova análise.

## Como ler estas specs

- `requirements.md`: o que deve ser verdadeiro e quais decisões não podem ser
  tomadas implicitamente.
- `validation.md`: quais evidências demonstram que os requisitos foram
  atendidos.
- `tech-stack.md`: ferramentas permitidas, fronteiras técnicas e formatos.
- `plan.md`: ordem de trabalho, checkpoints humanos e condições de parada.

Cada submódulo repete essa estrutura apenas para seu próprio escopo:

1. `01_arquivamento_v1`;
2. `02_relatorios_colab`;
3. `03_inventario_dados_drive`;
4. `04_snapshot_discursos_v2`.

Specs de análise substantiva só podem ser criadas depois da aprovação do
snapshot. O inventário exploratório orienta o reinício, mas seu saneamento não
é pré-condição para identificar diretamente as entradas do snapshot.

## Para não se perder

Não é necessário revisar todos os documentos de uma vez. A ordem recomendada é:

1. este índice e as decisões D01–D07;
2. `requirements.md` e `validation.md` gerais;
3. somente os quatro documentos do próximo submódulo;
4. implementação e validação desse submódulo;
5. aprovação humana antes de abrir o seguinte.

O `tech-stack.md` de cada submódulo é deliberadamente curto: registra apenas
exceções e escolhas próprias, sem repetir o stack global.

| Escopo | Contrato | Evidência | Limites técnicos | Sequência |
|---|---|---|---|---|
| Geral | [requirements](requirements.md) | [validation](validation.md) | [tech-stack](tech-stack.md) | [plan](plan.md) |
| 01 — arquivo v1 | [requirements](01_arquivamento_v1/requirements.md) | [validation](01_arquivamento_v1/validation.md) | [tech-stack](01_arquivamento_v1/tech-stack.md) | [plan](01_arquivamento_v1/plan.md) |
| 02 — relatórios do Colab | [requirements](02_relatorios_colab/requirements.md) | [validation](02_relatorios_colab/validation.md) | [tech-stack](02_relatorios_colab/tech-stack.md) | [plan](02_relatorios_colab/plan.md) |
| 03 — inventário do Drive | [requirements](03_inventario_dados_drive/requirements.md) | [validation](03_inventario_dados_drive/validation.md) | [tech-stack](03_inventario_dados_drive/tech-stack.md) | [plan](03_inventario_dados_drive/plan.md) |
| 04 — snapshot v2 | [requirements](04_snapshot_discursos_v2/requirements.md) | [validation](04_snapshot_discursos_v2/validation.md) | [tech-stack](04_snapshot_discursos_v2/tech-stack.md) | [plan](04_snapshot_discursos_v2/plan.md) |

## Princípios

- Nenhum arquivo antigo será apagado.
- Nenhum Batch pago será criado por estas etapas.
- Inventário precede migração.
- Relatório humano, manifest técnico e log têm finalidades diferentes.
- Notebook é um orquestrador fino, não a fonte exclusiva da lógica.
- Toda decisão científica relevante exige aprovação explícita do pesquisador.
- Contagens devem sempre declarar seu universo e denominador.

## Mapa de decisões

| ID | Decisão | Recomendação inicial | Estado |
|---|---|---|---|
| D01 | Caminho final do arquivo local | `notebooks/arquivo/analise_plenario_v1_abortada_20260723/` | **executada em 2026-07-23** |
| D02 | Marcar a execução antiga no Drive | adicionar marcador, sem mover dados | **executada em 2026-07-23** |
| D03 | Universo do snapshot v2 | três bases de discursos; intervenção textual oficial | **aprovada em 2026-07-23** |
| D04 | Data de corte do snapshot v2 | `2010-01-01` a `2026-07-13`, inclusive | **aprovada em 2026-07-23** |
| D05 | Tratamento de duplicatas Senado/Congresso | preservar todos os IDs; não deduplicar entre fontes | **aprovada em 2026-07-23** |
| D06 | Campos mínimos do manifest técnico | [contrato da fase 2](02_relatorios_colab/proposta_d06.md) | **aprovada em 2026-07-23** |
| D07 | Perguntas e unidades da nova análise | definir somente após o snapshot v2 | pendente |

## Ponto de controle atual

As fases 1 e 2 foram concluídas. A fase 3 foi executada em modo somente leitura
e encerrada como baseline exploratório: 7.859 itens foram reconciliados, sem
escritas no Drive. O saneamento de referências, órfãos e duplicidades legadas
foi adiado. O censo read-only foi executado, D03–D05 e o schema foram
aprovados. A transformação de smoke está implementada com saída temporária e
gates fechados. O próximo ato é executar e revisar essa amostra no Colab; a
execução integral permanece bloqueada.

## Gates progressivos de implementação

Nenhum submódulo pode ser implementado enquanto as specs gerais e seus quatro
documentos próprios não estiverem aprovados. Além disso:

- arquivo v1: exige D01; o marcador do Drive exige D02 separadamente;
- relatórios: exige D06 antes de o padrão ser incorporado aos notebooks;
- inventário: exige aprovação das raízes, da taxonomia e do contrato D06, mas
  não depende de D03–D05;
- snapshot v2: exige o baseline exploratório registrado, validação direta das
  bases de entrada e as decisões D03–D05;
- nova análise científica: exige snapshot aprovado e D07.

Esse encadeamento evita exigir uma decisão antes de produzir a evidência
necessária para tomá-la.

Alterações futuras devem registrar a decisão em `decisoes.md`.
