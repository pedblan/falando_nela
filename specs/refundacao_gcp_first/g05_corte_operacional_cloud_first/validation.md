# Validação operacional — G05 corte cloud-first

## Contrato e documentação

- [ ] Confirmar missão cloud-first em `README.md`, `pyproject.toml` e apresentação do pacote.
- [ ] Confirmar documentação de arquitetura, início local, produção, deploy, autenticação, rollback, custo e diagnóstico.
- [ ] Confirmar que exemplos de produção usam projeto/região explícitos e GCS como fonte.
- [ ] Confirmar que exemplos locais usam fixtures/testes e identificam quando ADC é necessário.
- [ ] Confirmar que Colab e Drive aparecem apenas como arquivo, manutenção ou rollback, não como caminho oficial.
- [ ] Confirmar referência acessível à tag `legacy-colab-final` e às specs históricas.

## Defaults e testes direcionados

- [ ] Confirmar `authoritative_raw = "gcs"` no contrato versionado.
- [ ] Confirmar GCS como default de produção onde houver escolha de backend.
- [ ] Confirmar fixture Marimo explícita e ausência de fallback para GCS/Drive.
- [ ] Confirmar recusa de projeto, região, bucket e autoridade divergentes antes de efeito remoto.
- [ ] Executar testes direcionados GCP-first com rede externa bloqueada.

## Clone limpo

- [ ] Criar clone local limpo a partir do commit candidato e registrar o SHA-1 do commit.
- [ ] Executar instalação congelada, Ruff, formatação e suíte completa.
- [ ] Executar `falando-nela doctor --json` sem erro.
- [ ] Executar `marimo check` e o teste do caderno com fixture sem ADC.
- [ ] Executar `tofu fmt -check`, `init -backend=false`, `validate` e `test` sem apply.
- [ ] Confirmar que nenhum teste acessou GCP, Drive ou fonte parlamentar.

## Revisão e integração

- [ ] Revisar o diff por escopo, segredos, state, planos, caches e arquivos acidentais.
- [ ] Confirmar que o Drive não foi alterado e que nenhum recurso GCP foi criado, alterado ou removido.
- [ ] Obter aprovação humana do commit candidato e da integração em `main`.
- [ ] Integrar sem reescrever histórico e publicar `main` sem force-push.
- [ ] Confirmar que `main` local e `origin/main` apontam para o mesmo commit.
- [ ] Atualizar specs-raiz e G05 com o resultado final e pendências reais.

## Matriz de modelo e esforço da validação

| ID | Validação | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G05-V01 | Confirmar missão cloud-first em README, metadata e pacote. | GPT-5.3-Codex-Spark | Baixo |
| G05-V02 | Confirmar documentação operacional completa e curta. | GPT-5.3-Codex-Spark | Médio |
| G05-V03 | Confirmar exemplos remotos com projeto, região e GCS explícitos. | GPT-5.3-Codex-Spark | Médio |
| G05-V04 | Confirmar exemplos locais por fixtures e fronteira de ADC. | GPT-5.3-Codex-Spark | Baixo |
| G05-V05 | Classificar referências Colab/Drive sem reescrever o arquivo. | GPT-5.3-Codex-Spark | Médio |
| G05-V06 | Confirmar tag e specs históricas acessíveis. | GPT-5.3-Codex-Spark | Baixo |
| G05-V07 | Confirmar autoridade raw GCS no contrato. | GPT-5.3-Codex-Spark | Baixo |
| G05-V08 | Confirmar defaults de produção cloud-first. | GPT-5.6-Codex | Médio |
| G05-V09 | Confirmar fixture Marimo explícita e ausência de fallback. | GPT-5.6-Codex | Médio |
| G05-V10 | Confirmar recusa de alvos GCP divergentes. | GPT-5.6-Codex | Médio |
| G05-V11 | Executar testes direcionados sem rede externa. | GPT-5.6-Codex | Médio |
| G05-V12 | Criar clone limpo do commit candidato. | GPT-5.6-Codex | Médio |
| G05-V13 | Executar instalação, Ruff, formatação e suíte completa. | GPT-5.6-Codex | Alto |
| G05-V14 | Executar `doctor --json`. | GPT-5.3-Codex-Spark | Baixo |
| G05-V15 | Validar Marimo e caderno com fixture sem ADC. | GPT-5.6-Codex | Médio |
| G05-V16 | Validar OpenTofu sem backend remoto nem apply. | GPT-5.6-Codex | Alto |
| G05-V17 | Confirmar ausência de chamadas externas nos testes. | GPT-5.6-Codex | Médio |
| G05-V18 | Revisar diff por escopo e artefatos sensíveis. | GPT-5.3-Codex-Spark | Médio |
| G05-V19 | Confirmar ausência de mutações em Drive e GCP. | GPT-5.3-Codex-Spark | Médio |
| G05-V20 | Obter o gate humano único. | GPT-5.3-Codex-Spark | Baixo |
| G05-V21 | Integrar e publicar `main` sem reescrita. | GPT-5.6-Codex | Alto |
| G05-V22 | Comparar `main` local e `origin/main`. | GPT-5.3-Codex-Spark | Médio |
| G05-V23 | Fechar specs e registrar pendências reais. | GPT-5.3-Codex-Spark | Baixo |

## Comandos previstos

No worktree, executar primeiro as provas direcionadas. No clone limpo do commit
candidato, executar o conjunto amplo uma única vez:

```bash
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run falando-nela doctor --json
uv run --locked --group cloud --group notebooks \
  marimo check notebooks/primeiro_recorte_discursos.py
tofu -chdir=infra/gcp fmt -check -recursive
tofu -chdir=infra/gcp init -backend=false -input=false
tofu -chdir=infra/gcp validate
tofu -chdir=infra/gcp test
```

O teste direcionado do caderno gera Parquet temporário e seleciona
`FALANDO_NELA_G04_SOURCE=fixture`; ele deve provar a execução sem ADC e sem
rede. `tofu plan` real, build Docker e smoke GCP não são exigidos em G05 porque
não haverá mudança de infraestrutura ou runtime remoto.

## Evidência final esperada

Registrar somente:

- commit candidato e commit integrado;
- resumo dos comandos e contagens de testes;
- confirmação de ausência de artefatos sensíveis e efeitos GCP/Drive;
- igualdade entre `main` e `origin/main`;
- limitações ou tarefas futuras reais.

Não registrar tokens, conta pessoal, billing account, state, plano binário ou
conteúdo integral de discursos.
