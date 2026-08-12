# Auditoria P03 — Entrypoints, defaults e metadata

## Escopo

Inventariar, sem alterar comportamento, os pontos que ainda descrevem a operação
como local-first e validar o que já está alinhado com cloud-first.

## Achados (2026-08-12)

### Itens já alinhados com cloud-first

- `config/gcp.toml` já declara `authoritative_raw = "gcs"` com contrato de G04.
- O contrato de Marimo (`specs/refundacao_gcp_first/g04_primeiro_marimo_privado`) e a
  validação do G04 já especificam `source=gcs` como padrão operacional.
- O app de produção está registrado como privado em `specs/refundacao_gcp_first/g04_primeiro_marimo_privado`.

### Itens que ainda aparecem como local-first (esperado nesta etapa)

- `pyproject.toml`: `description = "Pipeline local-first para o corpus parlamentar` (não oficial, metadata de pacote).
- `src/falando_nela/__init__.py`: docstring `"""Núcleo local-first do Falando Nela.""`.
- `src/falando_nela/cli.py`: `parquet-pilot` aceita `--backend` com
  `default="local"` e valida `--local-input` no backend local. Não há produção G04
  aqui, mas o comportamento ainda precisa entrar no escopo de P04.
- `specs/refundacao_gcp_first/README.md` e `specs/refundacao_gcp_first/tech-stack.md`:
  `O executável geral permanece local-first até o corte G05`, como texto histórico
  de transição.
- `notebooks/README.md` e vários artefatos de `specs/refundacao_local_first`:
  marcados como históricos/arquivo e não como entrada oficial.

### Risco de inconsistência

- O comando `parquet-pilot --backend` com padrão `local` pode gerar ruído operacional
  fora de produção até P04, já que não é a fonte oficial da consulta G04/Cloud.
- A metadata do pacote (`pyproject.toml` e docstring de pacote) ainda anuncia
  um estado anterior e deve ser atualizada em P05.

### Conclusão da auditoria

P03 concluiu em estado limpo: não foram feitas mudanças de código, apenas leitura e
classificação. P04 corrigiu posteriormente o default de `parquet-pilot` para GCS,
mantendo a entrada local explícita e sem fallback. P05 atualizou posteriormente
a metadata, a apresentação do núcleo e os READMEs canônicos; os textos acima
permanecem como registro dos achados observados em P03.
