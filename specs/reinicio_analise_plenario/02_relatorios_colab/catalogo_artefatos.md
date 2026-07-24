# Catálogo proposto de artefatos operacionais

Status: **aprovado no D06 em 2026-07-23**.

| Artefato | Leitor principal | Finalidade | Quando existe | Retenção |
|---|---|---|---|---|
| `relatorio.md` | pesquisador | compreender resultado, impacto e próxima ação | sempre que a operação inicia | permanente |
| `manifest.json` | código e auditoria | validar proveniência e permitir reprodução | sempre que a operação inicia | permanente |
| `logs/execution.jsonl` | diagnóstico técnico | investigar eventos e falhas | sempre que houver execução | conforme política do módulo |
| `artifacts/*` | pesquisa e processamento | armazenar dados, tabelas e anexos produzidos | quando houver saídas | conforme contrato do módulo |
| `artifacts/warnings.*` | pesquisador e diagnóstico | detalhar avisos agregados no relatório | quando houver avisos detalhados | junto da operação |
| `artifacts/errors.*` | diagnóstico técnico | detalhar erros referenciados pelo resumo | quando houver erros detalhados | junto da operação |

## Regras

- O relatório não incorpora o log nem tabelas extensas.
- O manifest não incorpora configurações completas, listas grandes ou
  schemas detalhados.
- O log não é a interface normal do pesquisador.
- A célula final do notebook apresenta apenas estados, contagens centrais,
  alertas, referências aos artefatos e próxima ação.
- Nenhum dos artefatos pode conter chaves, tokens ou cabeçalhos de
  autorização.
- Um artefato referido pelo relatório ou manifest deve existir ou ter uma
  indicação explícita de indisponibilidade.
