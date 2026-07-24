# Requisitos — relatórios operacionais do Colab

Status: **contrato e D06 aprovados em 2026-07-23**.

## Objetivo

Substituir o acúmulo indistinto de logs e manifests por três artefatos
complementares:

1. **relatório humano:** explica o que ocorreu e o próximo passo;
2. **manifest técnico:** registra proveniência e permite automação;
3. **log técnico:** preserva detalhes de diagnóstico.

Uma pessoa não deve precisar ler JSON ou milhares de linhas de log para
entender o estado de uma execução.

## Vocabulário de estado aprovado no D06

O estado da execução e o estado científico são independentes:

- `execution_status`: `not_started`, `running`, `succeeded`, `failed`,
  `cancelled`;
- `scientific_gate`: `not_applicable`, `not_evaluated`, `needs_review`,
  `approved`, `rejected`.

`succeeded` significa que o programa terminou; não significa que o resultado
foi aprovado para análise científica.

## Relatório humano

- **REL-R01 — um relatório por operação:** cada operação relevante deve gerar
  `relatorio.md` em local previsível.
- **REL-R02 — resumo obrigatório:** o início do relatório deve informar
  módulo, objetivo, IDs, período, unidade observada, entradas, saídas, status
  operacional e gate científico.
- **REL-R03 — contagens explicadas:** números devem declarar unidade,
  denominador, filtros e contagens antes/depois.
- **REL-R04 — artefatos:** cada artefato deve ser listado com nome, finalidade,
  caminho e ação esperada do pesquisador.
- **REL-R05 — problemas acionáveis:** avisos e erros devem explicar impacto,
  evidência e próximo passo, sem despejar o traceback inteiro.
- **REL-R06 — próxima ação:** o fim do relatório deve dizer claramente se é
  necessário revisar, aprovar, corrigir, reexecutar ou não fazer nada.
- **REL-R07 — comparação:** quando houver execução anterior comparável, o
  relatório deve destacar mudanças relevantes de contagem, configuração ou
  cobertura.

## Manifest técnico

- **REL-R08 — schema versionado:** todo manifest deve declarar
  `schema_version` e `module`.
- **REL-R09 — identidade:** deve registrar `operation_id`, `analysis_run_id`
  quando aplicável, `snapshot_id` quando aplicável e referências à spec e ao
  commit.
- **REL-R10 — proveniência mínima:** entradas e saídas devem registrar papel,
  caminho ou ID canônico, formato, tamanho, número de registros quando
  aplicável e hash disponível.
- **REL-R11 — configuração por referência:** configurações extensas não devem
  ser copiadas integralmente para todo manifest. Registrar `config_ref`,
  `config_hash` e somente parâmetros operacionais decisivos.
- **REL-R12 — resultados compactos:** registrar contagens, estados, gates e
  referências a avisos/erros; conteúdo volumoso permanece em artefatos
  próprios.
- **REL-R13 — campos obrigatórios:** os campos mínimos aprovados no D06 são:
  `schema_version`, `module`, `operation_id`, `analysis_run_id`,
  `snapshot_id`, `spec_ref`, `spec_version`, `code_commit`,
  `execution_status`, `scientific_gate`, `started_at`, `finished_at`,
  `inputs`, `outputs`, `config_ref`, `config_hash`, `counts`, `report_ref`,
  `log_ref`, `warnings_ref` e `errors_ref`. Campos inaplicáveis podem ser
  nulos, nunca ambíguos.

## Log técnico e notebook

- **REL-R14 — log separado:** logs completos devem ficar em arquivo próprio,
  com níveis e timestamps; não devem ser incorporados ao relatório.
- **REL-R15 — saída controlada:** durante a execução, o notebook mostra
  progresso resumido. Em erro, mostra mensagem curta e no máximo as últimas
  linhas necessárias para diagnóstico, com link/caminho para o log completo.
- **REL-R16 — célula final:** todo notebook operacional deve terminar com um
  painel textual compacto contendo estados, contagens centrais, alertas,
  artefatos e próxima ação.
- **REL-R17 — catálogo de artefatos:** deve existir um dicionário que explique
  nomes, papéis, formatos, retenção e relação entre relatório, manifest e log.
- **REL-R18 — segurança:** relatórios, manifests e logs não podem expor chaves,
  tokens, cabeçalhos de autorização nem conteúdo sensível desnecessário.
- **REL-R19 — falhas parciais:** mesmo em falha, deve ser gravado um registro
  mínimo com o ponto de interrupção e a localização do diagnóstico, quando
  tecnicamente possível.

## Fora de escopo

- observabilidade em tempo real;
- dashboard web;
- banco central de execuções;
- padronizar retrospectivamente todos os artefatos antigos;
- definir métricas científicas de cada análise.

## Gate humano

A decisão D06 foi aprovada em 2026-07-23 após a revisão do vocabulário, dos
campos mínimos e dos exemplos renderizados. O contrato pode ser aplicado ao
notebook piloto somente depois dos gates próprios da fase 3.
