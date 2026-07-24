# Requisitos — inventário dos dados no Drive

Status: **D06, raiz e taxonomia aprovados — execução real pendente**.

## Objetivo

Construir um mapa confiável e legível das bases, snapshots, execuções,
manifests, relatórios e logs existentes no Drive antes de qualquer migração ou
nova análise. O inventário deve explicar o universo de cada contagem, inclusive
permitir distinguir qualquer subconjunto operacional do conjunto total
disponível na raiz.

## Contrato funcional

- **INV-R01 — somente leitura:** a primeira execução não pode criar, mover,
  renomear nem apagar itens no Drive.
- **INV-R02 — raízes aprovadas:** cada raiz examinada deve ser listada
  explicitamente; a busca não pode se expandir silenciosamente para todo o
  Drive.
- **INV-R03 — catálogo de itens:** cada arquivo ou diretório relevante deve
  registrar caminho, nome, tipo, camada aparente, finalidade inferida ou
  declarada, tamanho, data de modificação e origem da evidência.
- **INV-R04 — catálogo de execuções:** execuções devem registrar os IDs
  disponíveis, módulo, período, status operacional, gate científico, entradas,
  saídas e relações com manifests, relatórios e logs.
- **INV-R05 — universos explícitos:** toda contagem deve declarar unidade,
  filtros, fontes, intervalo temporal e denominador. “Transcrições”,
  “discursos”, “documentos” e “linhas” não podem ser usados como sinônimos.
- **INV-R06 — relações:** o inventário deve detectar referências ausentes,
  saídas órfãs, múltiplos manifests para a mesma execução e caminhos que não
  existem mais.
- **INV-R07 — duplicidade:** itens potencialmente duplicados devem ser
  sinalizados, sem exclusão automática.
- **INV-R08 — custo proporcional:** hashes existentes têm precedência. Na falta
  deles, tamanho e data de modificação são usados para triagem; hash integral
  só é calculado quando necessário para resolver uma dúvida.
- **INV-R09 — incerteza preservada:** finalidade, camada ou equivalência
  inferidas devem ser marcadas como inferência, com confiança e motivo.
- **INV-R10 — saída humana:** `mapa_dados.md` deve permitir ao pesquisador
  localizar bases canônicas, snapshots e execuções sem abrir manifests ou logs.
- **INV-R11 — saídas tabulares:** devem existir `catalogo_dados.csv` ou
  `.parquet`, `catalogo_universos.csv`, `catalogo_execucoes.csv` e
  `inconsistencias.csv`.
- **INV-R12 — plano separado:** sugestões de reorganização devem aparecer em
  `plano_migracao.csv`; o inventário não as executa.
- **INV-R13 — cobertura integral:** `catalogo_universos.csv` deve atribuir cada
  item catalogado a exatamente um grupo de fonte, camada, classe e tipo. A soma
  dos grupos deve reconciliar com `catalogo_dados.csv`. Nenhum subconjunto ou
  total histórico recebe tratamento privilegiado.

## Fora de escopo

- corrigir arquivos;
- promover uma base como canônica sem aprovação;
- deduplicar registros;
- gerar novo snapshot;
- executar análise com modelos;
- reorganizar o Drive.

## Gate humano

O contrato D06, a raiz do Drive e a taxonomia inicial de
[`proposta_gate_inicial.md`](proposta_gate_inicial.md) foram aprovados em
2026-07-23. A execução real ainda exige que o pesquisador arme a célula
explícita do notebook e confirme seu `operation_id`. O inventário não depende
das decisões D03–D05. Depois, o pesquisador aprova o mapa e a interpretação
dos universos antes de qualquer migração ou snapshot.
