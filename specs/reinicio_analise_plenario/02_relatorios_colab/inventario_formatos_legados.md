# Inventário dos formatos legados

Status: **concluído em 2026-07-23 — inspeção somente leitura**.

Este inventário identifica padrões existentes que devem orientar o D06. Ele
não autoriza regravar artefatos antigos.

## Amostra examinada

| Origem | Formato observado | Uso atual |
|---|---|---|
| análise de plenário v1 arquivada | `manifest.json` com cópia ampla da configuração | proveniência da execução analítica |
| coletores compartilhados | manifest com caminhos, checkpoints, retomada, contagens e campos extras | execução e recuperação operacional |
| processamento para Parquet | manifest com arquivos, schemas e estatísticas | auditoria do processamento |
| apartes parlamentares locais | manifest específico do módulo | acompanhamento intermediário |
| exportações XLSX | planilhas e metadados associados | inspeção humana |
| notebooks antigos | dicionários impressos, logs e resumos livres | interface operacional |

## Achados

### Análise de plenário v1

- O manifest repetia a configuração inteira.
- Informações para máquinas e explicações para pessoas apareciam misturadas.
- Não havia um relatório humano canônico que dissesse, em linguagem direta,
  o que terminou e o que ainda precisava de aprovação.

### Coleta

- Identidade da execução, caminhos de log e autosave, checkpoints, estado de
  retomada, contagens e campos específicos conviviam no mesmo nível.
- O formato era útil para recuperação técnica, mas não constituía uma
  interface breve para o pesquisador.

### Processamento

- As amostras examinadas continham entre 18 e 22 campos no nível superior.
- Listas extensas de arquivos e descrições de schema tornavam alguns manifests
  volumosos.
- Informações estáveis de configuração eram repetidas em vez de referenciadas.

### Notebooks

- Não havia um formato único de encerramento.
- Uma execução normal podia exigir a leitura de dicionários impressos ou do
  log.
- O termo `completed` não distinguia conclusão computacional de aprovação
  científica.

## Problemas que o D06 deve resolver

1. ausência de um relatório humano canônico;
2. ambiguidade entre “programa terminou” e “resultado foi aprovado”;
3. repetição de configurações extensas;
4. inclusão de listas e schemas grandes no manifest principal;
5. uso inconsistente de identificadores de execução;
6. ausência de uma próxima ação explícita;
7. uso de logs e dicionários como interface principal.

## Consequências de projeto

- listas de arquivos, schemas e tabelas detalhadas ficam em anexos;
- configurações são registradas por referência e hash;
- relatório, manifest e log têm arquivos separados;
- a célula final do notebook mostra somente o resumo operacional;
- identidade, estado computacional e gate científico são campos distintos;
- os artefatos antigos permanecem intactos e serão apenas catalogados na
  fase 3.
