# Auditoria P07 — Colab e Drive

## Escopo

Classificar referências a Colab, Drive montado e `FALANDO_NELA_DATA_ROOT` sem
remover código, cadernos, testes, specs ou dados legados. O critério é simples:
nenhuma superfície canônica pode apresentar Colab ou Drive como caminho de
produção; usos preservados precisam ser históricos, de compatibilidade,
manutenção ou rollback.

## Método e resultado

Em `2026-08-12`, a busca textual excluiu `.git`, ambientes virtuais e caches e
encontrou inicialmente 237 arquivos com pelo menos uma referência relevante.
A quantidade alta é esperada porque o repositório preserva integralmente a
linha anterior. Depois dos rótulos, a mesma busca encontra 238 arquivos porque
o README classificador de `specs/pipeline_dados_v3/` passou a mencionar Colab e
Drive explicitamente. Não foram editados notebooks `.ipynb`, geradores, testes
de caracterização ou contratos internos dessa linha.

| Classe | Superfície | Decisão |
| --- | --- | --- |
| Canônica atual | `README.md`, `docs/operacao_cloud_first.md`, `specs/refundacao_gcp_first/`, `notebooks/README.md` | Drive aparece somente como arquivo/rollback; Colab aparece somente como legado |
| Arquivo explícito | `arquivo/`, `notebooks/arquivo/`, `specs/refundacao_local_first/` | preservar sem reescrita; 115 arquivos encontrados pela busca |
| Compatibilidade congelada | `coleta/`, `pipeline_dados_v3/`, `scripts/`, testes e specs v3 | preservar implementação e caracterização; 87 arquivos encontrados nas superfícies principais |
| Cadernos antigos fora de `arquivo/` | `notebooks/coleta/`, `notebooks/dados_v3/`, `notebooks/manutencao/` | o índice canônico e os READMEs locais os classificam como consulta legada |
| CLI de recuperação | `drive-organize`, `sample`, `gcs-migrate` | manter comportamento, mas rotular ajuda como legado, compatibilidade ou migração/recuperação histórica |
| Configuração compatível | campos Drive em `src/falando_nela/config.py` | manter para leitura e recuperação; não são usados pelo caminho G03/G04 padrão |
| Dependências antigas | `requirements*.txt` e skill Colab versionada | preservar para reprodução; `pyproject.toml` e `uv.lock` definem o ambiente atual |

## Correções localizadas

- `coleta/README.md`, `specs/roadmap.md` e `specs/tech-stack.md` receberam aviso
  de congelamento e ponte para as specs GCP-first.
- `specs/pipeline_dados_v3/README.md` declara que schema, gates e operações
  Colab não foram aplicados e não autorizam retomada.
- o inventário pré-refundação esclarece que seus antigos “pontos de entrada”
  hoje são fontes históricas.
- a ajuda da CLI deixa visível a natureza legada dos comandos dependentes de
  Drive, sem remover opções necessárias à recuperação.

## Recuperabilidade

A tag anotada `legacy-colab-final` existe localmente e aponta para
`17a84c674472205e7c13ce1c3a74230fbd462722`. O inventário de recuperação está em
`docs/refundacao/inventario_legado_colab_20260803.md`; o checkout destacado é
somente para inspeção e reprodução.

Drive permanece intacto e read-only como arquivo de rollback. Esta auditoria
não acessou Drive ou GCP, não montou filesystem remoto, não moveu ou excluiu
arquivos e não alterou dados locais.

## Conclusão

O caminho oficial depende de Git, GCS, Cloud Run, OpenTofu e Marimo. Não há
instrução canônica de produção que exija Colab ou Drive montado. O legado
continua recuperável e explicitamente separado, sem bloquear a evolução do
serviço.
