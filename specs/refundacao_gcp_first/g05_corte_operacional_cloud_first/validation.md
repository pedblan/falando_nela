# Validação operacional — G05 corte cloud-first

## Contrato e documentação

- [x] Confirmar missão cloud-first em `README.md`, `pyproject.toml` e apresentação do pacote.
- [x] Confirmar documentação de arquitetura, início local, produção, deploy, autenticação, rollback, custo e diagnóstico.
- [x] Confirmar que exemplos de produção usam projeto/região explícitos e GCS como fonte.
- [x] Confirmar que exemplos locais usam fixtures/testes e identificam quando ADC é necessário.
- [x] Confirmar que Colab e Drive aparecem apenas como arquivo, manutenção ou rollback, não como caminho oficial.
- [x] Confirmar referência acessível à tag `legacy-colab-final` e às specs históricas.

Evidência de P05 em `2026-08-12`: `README.md`, metadata do pacote, docstring do
núcleo, missão e índice de notebooks apresentam o caminho cloud-first e mantêm
o corpus volumoso na nuvem. Links locais foram conferidos; `uv lock --check`,
Ruff, `doctor --json` com `data_samples/` absoluto e os 40 testes direcionados
passaram. A documentação operacional completa permanece em P06 e a auditoria
integral de Colab/Drive, em P07.

Evidência de P06 em `2026-08-12`: `docs/operacao_cloud_first.md` registra o
contrato implantado, separa rotina de novos gates e cobre validação local,
readback, proxy autenticado, job, deploy por digest/OpenTofu, rollback sem
exclusão, budget e diagnóstico. Todo comando GCP fixa projeto e região quando
aplicável; nenhuma chamada remota foi executada para produzir o guia.

Evidência de P07 em `2026-08-12`: a busca inicial classificou 237 arquivos;
avisos canônicos separam operação atual, compatibilidade e arquivo sem
reescrever o legado. A tag `legacy-colab-final` foi confirmada no commit
`17a84c674472205e7c13ce1c3a74230fbd462722`. Nenhum Drive, GCP ou notebook foi
executado ou alterado.

## Defaults e testes direcionados

- [x] Confirmar `authoritative_raw = "gcs"` no contrato versionado.
- [x] Confirmar GCS como default de produção onde houver escolha de backend.
- [x] Confirmar fixture Marimo explícita e ausência de fallback para GCS/Drive.
- [x] Confirmar recusa de projeto, região, bucket e autoridade divergentes antes de efeito remoto.
- [x] Executar testes direcionados GCP-first com rede externa bloqueada.

Evidência de P04 em `2026-08-12`: o parser assume `backend=gcs`; sem as quatro
confirmações literais, a CLI encerra antes de obter credenciais ou construir o
cliente remoto. `backend=local` continua exigindo `--local-input`. Ruff e 40
testes direcionados de configuração, pipeline e Marimo passaram sem chamadas
externas; o bloqueio formal de rede permanece reservado a P08.

Evidência de P08 em `2026-08-12`: a suíte direcionada bloqueia criação e conexão
de sockets (`create_connection`, `connect` e `connect_ex`), inclui uma prova
positiva do bloqueio e executa o caderno em subprocesso igualmente offline, com
HOME isolado e variáveis ADC/projeto removidas. Defaults, fixture explícita e
recusa de projeto, região, bucket e autoridade divergentes passaram: 46 provas
do recorte e 81 testes da suíte GCP-first. A tarefa previa GPT-5.6-Codex em
esforço médio; foi executada com GPT-5 em esforço médio, a alternativa
disponível mais próxima, sem impacto material no escopo de testes.

Evidência de P09 em `2026-08-12`: `auditoria_p09_diff_scopo_state.md` revisou
diff, segredos, estado e artefatos. Não houve achados bloqueantes.

## Clone limpo

- [x] Criar clone local limpo a partir do commit candidato e registrar o SHA-1 do commit.
- [x] Executar instalação congelada, Ruff, formatação e suíte completa.
- [x] Executar `falando-nela doctor --json` sem erro.
- [x] Executar `marimo check` e o teste do caderno com fixture sem ADC.
- [x] Executar `tofu fmt -check`, `init -backend=false`, `validate` e `test` sem apply.
- [x] Confirmar que nenhum teste acessou GCP, Drive ou fonte parlamentar.

Evidência de P10 em `2026-08-12`: o clone local inicial foi criado sem rede a
partir do candidato `45ac289`; após a correção mecânica encontrada em P11, o
sucessor `ebfde7a` foi clonado em `/tmp/falando-nela-g05-p11.ZA7Y4k/repo`.

Evidência de P11 em `2026-08-12`: o clone limpo do candidato
`ebfde7a6ea4be20d6a4ecbdafa5b1df599f08ab9` resolveu 105 dependências e
instalou 104 pacotes pelo lockfile. Ruff passou; 88 arquivos estavam formatados;
a suíte terminou com 346 testes aprovados e dois pulados. `doctor --json`
retornou `status=ok` com `data_samples/` absoluto e não criou a raiz ausente.
`marimo check` passou, seguido por dez testes do G04 com ADC removido e sockets
bloqueados. OpenTofu 1.12.5 passou em `fmt`, `init -backend=false`, `validate` e
três testes com provider Google simulado, sem `apply` ou chamada à API GCP.
Nenhum teste acessou GCP, Drive ou fonte parlamentar. P11 previa GPT-5.6-Codex
em esforço alto e foi executada com GPT-5 em esforço alto, a alternativa
disponível mais próxima, sem impacto material na cobertura.

## Revisão e integração

- [x] Revisar o diff por escopo, segredos, state, planos, caches e arquivos acidentais.
- [x] Confirmar que o Drive não foi alterado e que nenhum recurso GCP foi criado, alterado ou removido.
- [x] Obter aprovação humana do commit candidato e da integração em `main`.
- [x] Integrar sem reescrever histórico e publicar `main` sem force-push.
- [x] Confirmar que `main` local e `origin/main` apontam para o mesmo commit.
- [x] Atualizar specs-raiz e G05 com o resultado final e pendências reais.

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
FALANDO_NELA_DATA_ROOT="$PWD/data_samples" uv run falando-nela doctor --json
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
