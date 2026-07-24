# Tech stack — snapshot de discursos v2

Status: **contrato aprovado em 2026-07-23**.

Este documento especializa
[`../tech-stack.md`](../tech-stack.md).

## Ferramentas e formatos

- Notebook Colab em `notebooks/dados/` como interface operacional futura.
- Funções Python testáveis fora do notebook.
- `pandas` ou `polars` para transformação; `pyarrow` para Parquet e schema.
- `hashlib` para identidade e integridade.
- JSON Schema para o manifest; Markdown, CSV e Parquet para evidências.
- Testes unitários para IDs, regras de fonte, corte e deduplicação.

## Reprodutibilidade

- ordenação determinística antes da escrita;
- serialização estável dos campos usados em IDs;
- algoritmo de hash e versão da regra registrados;
- versões de dependências relevantes registradas por referência;
- entradas resolvidas por ID/caminho canônico e hash.

## Restrições

- Não usar OpenAI API.
- Não depender de saídas da análise v1.
- Não incluir lógica científica apenas em células do notebook.
- Não depender da ordem de listagem do Drive.
- Não usar CSV como formato principal quando ele perder tipos ou estrutura.
