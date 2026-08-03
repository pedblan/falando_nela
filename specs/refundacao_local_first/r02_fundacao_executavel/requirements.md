# Requisitos operacionais — R02 fundação executável local

## Objetivo

Criar a fundação instalável e testável do caminho local-first sem acessar dados
de produção, Drive, APIs parlamentares ou recursos pagos.

## Requisitos

- **R02-REQ-01:** o projeto usará CPython `>=3.13,<3.14`, `pyproject.toml`,
  `.python-version`, `uv.lock` e layout `src/falando_nela/`.
- **R02-REQ-02:** o entrypoint `falando-nela` oferecerá `doctor` com saída
  humana e `--json`, códigos de retorno distintos e nenhuma chamada de rede.
- **R02-REQ-03:** `FALANDO_NELA_DATA_ROOT` será obrigatório para operações de
  produção. A raiz será absoluta, não poderá estar dentro do clone e será
  criada somente quando um comando mutável futuro a solicitar explicitamente.
- **R02-REQ-04:** a configuração validará profiles `local|cloud`, data profiles
  `sample_annual_1pct|full`, memória DuckDB, threads, temporários, quota local,
  reserva livre e ID esperado da pasta Drive.
- **R02-REQ-05:** o profile `full` será recusado sem opt-in explícito; nenhuma
  configuração de caderno poderá promovê-lo silenciosamente.
- **R02-REQ-06:** a biblioteca fornecerá primitivas de JSON canônico, SHA-256,
  escrita JSON atômica, gzip determinístico e leitura streaming de
  `.jsonl|.jsonl.gz`, preparatórias para R03, sem implementar a migração.
- **R02-REQ-07:** CI e testes usarão somente fixtures pequenas versionadas,
  sem credenciais nem rede.
- **R02-REQ-08:** dados, ambientes, caches, temporários e credenciais ficarão
  ignorados pelo Git.

## Não objetivos

- Configurar ou acessar Google Drive, Dropbox ou Google Cloud.
- Importar, processar, fazer backup ou excluir dados.
- Criar caderno marimo de produção.
- Portar ou remover notebooks e módulos legados.
- Criar a tag `legacy-colab-final` enquanto a worktree legada estiver suja.

## Casos relevantes

- `doctor` sem data root: diagnóstico estruturado e retorno não zero.
- data root relativo ou dentro do clone: recusa explícita.
- data root externo válido: configuração calculada sem criar dados.
- profile `full` sem confirmação: recusa explícita.
- duas compressões do mesmo JSONL: bytes e hashes idênticos.
- JSONL aberto e gzip fechado: mesmos registros e hashes de conteúdo.
