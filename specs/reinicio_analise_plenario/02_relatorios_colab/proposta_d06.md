# Proposta D06 — contrato mínimo de relatório e manifest

Status: **aprovada pelo pesquisador em 2026-07-23**.

Este documento registra o contrato aprovado no ponto de controle da fase 2.
A aprovação autorizou a biblioteca de relatórios, mas não autoriza alterar o
Drive nem executar o inventário da fase 3.

## Organização de uma operação

```text
<operation_id>/
├── relatorio.md
├── manifest.json
├── logs/
│   └── execution.jsonl
└── artifacts/
    └── ...
```

O caminho-base pode variar por módulo. Os nomes e os papéis acima são
canônicos.

## Dois estados independentes

`execution_status` informa o resultado do programa:

- `not_started`;
- `running`;
- `succeeded`;
- `failed`;
- `cancelled`.

`scientific_gate` informa a situação do resultado para uso científico:

- `not_applicable`;
- `not_evaluated`;
- `needs_review`;
- `approved`;
- `rejected`.

Assim, uma operação pode terminar com `execution_status: succeeded` e ainda
exigir `scientific_gate: needs_review`.

## Campos mínimos do manifest

Todas as chaves abaixo existem em todo manifest. Quando um campo não se
aplicar, seu valor será `null`, e não uma expressão ambígua.

| Campo | Finalidade |
|---|---|
| `schema_version` | versão do contrato do manifest |
| `module` | módulo que executou a operação |
| `operation_id` | identidade única da operação |
| `analysis_run_id` | identidade compartilhada entre operações de uma análise |
| `snapshot_id` | snapshot consumido ou produzido |
| `spec_ref` | spec que rege a operação |
| `spec_version` | versão declarada da spec |
| `code_commit` | commit do código executado |
| `execution_status` | estado computacional |
| `scientific_gate` | estado de aprovação científica |
| `started_at` | início com fuso horário |
| `finished_at` | término com fuso horário |
| `inputs` | entradas compactas e verificáveis |
| `outputs` | saídas compactas e verificáveis |
| `config_ref` | referência à configuração completa |
| `config_hash` | hash da configuração |
| `counts` | contagens centrais, com significado definido pelo módulo |
| `report_ref` | referência ao relatório humano |
| `log_ref` | referência ao log técnico |
| `warnings_ref` | referência aos avisos detalhados |
| `errors_ref` | referência aos erros detalhados |

Cada item de `inputs` ou `outputs` contém:

- `name`;
- `role`;
- `uri`;
- `format`;
- `size_bytes`;
- `sha256`;
- `rows`.

Listas grandes de arquivos, schemas detalhados e conteúdo de avisos não são
incorporados ao manifest; ficam em artefatos referenciados.

## Evidência aprovada

- [inventário dos formatos legados](inventario_formatos_legados.md);
- [catálogo dos artefatos](catalogo_artefatos.md);
- [relatório de sucesso](exemplos/relatorio_sucesso.md);
- [relatório com revisão pendente](exemplos/relatorio_revisao.md);
- [relatório de falha](exemplos/relatorio_falha.md);
- [manifest de exemplo](exemplos/manifest_revisao.json);
- [JSON Schema proposto](schema/manifest.schema.json).

Os exemplos são fictícios e servem somente para testar a compreensão do
contrato.

## Resultado do gate

O pesquisador aprovou o formato em 2026-07-23. Foram aceitos:

- a compreensão da operação pelo relatório, sem abrir JSON ou log;
- a separação entre `succeeded` e `approved`;
- os 21 campos mínimos;
- os nomes canônicos dos quatro diretórios ou arquivos principais.

A implementação compartilhada está em
[`../../../relatorios_operacionais/`](../../../relatorios_operacionais/) e
continua sujeita aos testes e gates descritos em
[`validation.md`](validation.md).
