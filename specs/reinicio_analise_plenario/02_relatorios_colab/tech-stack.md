# Tech stack — relatórios operacionais do Colab

Status: **contrato aprovado em 2026-07-23**.

Este documento especializa
[`../tech-stack.md`](../tech-stack.md).

## Ferramentas e formatos

- Markdown para o relatório humano.
- JSON para o manifest, validado por JSON Schema.
- JSONL ou texto estruturado para logs técnicos.
- CSV ou Parquet para anexos tabulares extensos.
- Python `logging` para eventos; funções puras para montar contagens e
  relatórios.
- `jsonschema` 4.x para validar o contrato D06.
- `nbformat` e AST para verificar a célula final e padrões dos notebooks.

A implementação compartilhada fica em
[`../../../relatorios_operacionais/`](../../../relatorios_operacionais/). O
schema canônico permanece junto desta spec.

## Organização recomendada

Cada operação deve produzir:

```text
<operation_id>/
├── relatorio.md
├── manifest.json
├── logs/
│   └── execution.jsonl
└── artifacts/
    └── ...
```

O caminho físico pode variar por módulo, mas os três papéis e seus nomes
canônicos devem permanecer estáveis.

## Restrições

- Não introduzir plataforma de observabilidade, banco ou dashboard.
- Não usar OpenAI API para resumir logs.
- Não serializar objetos Python arbitrários.
- Timestamps devem incluir fuso; hashes devem declarar o algoritmo.
- O renderizador de relatório não deve depender do ambiente interativo do
  Colab.
