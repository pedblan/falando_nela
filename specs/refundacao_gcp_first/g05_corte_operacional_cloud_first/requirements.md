# Requisitos operacionais — G05 corte cloud-first

## Objetivo

Encerrar a refundação tornando o caminho GCP-first a apresentação e a operação
padrão do repositório, sem alterar os dados ou a infraestrutura já aprovados em
G00–G04. O resultado principal é um candidato reproduzível em clone limpo,
documentado e integrado em `main`, com desenvolvimento local por fixtures e sem
dependência de ADC, Colab ou Drive montado.

## Escopo e unidade de entrega

- **G05-SCOPE-01:** G05 abrange defaults de produção, missão e metadata do
  pacote, documentação operacional, regressão em clone limpo e integração Git.
- **G05-SCOPE-02:** correções pequenas exigidas pelas validações de G05 podem
  permanecer na tarefa quando compartilham os mesmos critérios de aceitação.
- **G05-SCOPE-03:** qualquer melhoria independente descoberta durante o corte
  será registrada para tarefa posterior, sem bloquear o corte salvo regressão
  ou risco real.
- **G05-SCOPE-04:** G05 não cria, altera ou remove recursos GCP e não repete
  build, deploy, upload, job ou migração já comprovados.

## Identidade e defaults cloud-first

- **G05-CLOUD-01:** `config/gcp.toml` continuará declarando GCS como autoridade
  raw, com projeto `falando-nela-pedblan`, região `southamerica-east1` e bucket
  `falando-nela-pedblan-data` explícitos.
- **G05-CLOUD-02:** entradas de produção que ofereçam escolha de backend usarão
  GCS como padrão ou exigirão seleção explícita; não escolherão local ou Drive
  silenciosamente.
- **G05-CLOUD-03:** o app Marimo continuará usando GCS por padrão e fixture
  somente com `FALANDO_NELA_G04_SOURCE=fixture` e
  `FALANDO_NELA_G04_FIXTURE` explícitos, sem fallback.
- **G05-CLOUD-04:** projeto, região, bucket ou autoridade divergentes serão
  recusados antes de qualquer efeito remoto.
- **G05-CLOUD-05:** exemplos oficiais de produção usarão projeto e região
  explícitos e não dependerão do projeto ativo do `gcloud`.

## Documentação e operação

- **G05-DOC-01:** o repositório terá `README.md` canônico com missão
  cloud-first, arquitetura curta, início local e entrada para a operação GCP.
- **G05-DOC-02:** a descrição do pacote e docstrings de apresentação deixarão
  de chamar o núcleo atual de local-first.
- **G05-DOC-03:** a documentação cobrirá os caminhos atuais de processamento
  G03 e consulta G04, incluindo execução, deploy já declarado, autenticação,
  diagnóstico e rollback.
- **G05-DOC-04:** custo será explicado de forma proporcional: escala a zero,
  limites existentes, budget como alerta e necessidade de novo gate para nova
  operação paga; G05 não exige estimativa granular nova.
- **G05-DOC-05:** exemplos locais usarão fixture ou testes e funcionarão sem
  credenciais; exemplos remotos identificarão quando ADC/IAM é necessário.

## Legado e Drive

- **G05-LEGACY-01:** nenhuma operação oficial dependerá de Colab, montagem em
  `/content/drive` ou Drive como fonte de produção.
- **G05-LEGACY-02:** referências históricas em `notebooks/arquivo/` e specs
  anteriores podem permanecer quando estiverem claramente rotuladas como
  arquivo; G05 não fará reescrita ampla desses artefatos.
- **G05-LEGACY-03:** a tag `legacy-colab-final` e as specs históricas deverão
  continuar acessíveis e documentadas como pontos de recuperação.
- **G05-LEGACY-04:** o Drive permanecerá intacto e somente leitura como arquivo
  de rollback; excluir, mover, reorganizar ou remover código legado fica fora
  de G05.

## Qualidade e reprodutibilidade

- **G05-QUAL-01:** o candidato deverá instalar a partir de `uv.lock` em clone
  limpo com todos os grupos necessários às validações.
- **G05-QUAL-02:** Ruff, formatação e suíte completa deverão passar no clone
  limpo.
- **G05-QUAL-03:** testes GCP-first e o caderno Marimo deverão funcionar com
  fixture sem ADC e sem acesso a GCP, Drive ou fontes parlamentares.
- **G05-QUAL-04:** `marimo check`, `falando-nela doctor --json`, `tofu fmt`,
  `tofu validate` e `tofu test` deverão passar conforme os comandos de
  `validation.md`.
- **G05-QUAL-05:** o diff final não incluirá credenciais, state, planos
  binários, caches, artefatos operacionais ou mudanças alheias ao corte.

## Git e gate final

- **G05-GIT-01:** a implementação partirá do candidato G00–G04 revisado em
  branch dedicada; alterações existentes serão preservadas e consolidadas antes
  do clone limpo.
- **G05-GIT-02:** haverá um único gate humano depois das validações e da revisão
  do diff, imediatamente antes de integrar e publicar `main`.
- **G05-GIT-03:** a integração preservará o histórico, usando fast-forward
  quando possível ou merge comum quando necessário; rebase destrutivo,
  `reset --hard` e force-push são proibidos.
- **G05-GIT-04:** depois do push, `main` local e `origin/main` deverão apontar
  para o mesmo commit, e as specs serão atualizadas com a evidência final.

## Critérios de aceitação

G05 estará concluído quando todos os itens de `validation.md` passarem em clone
limpo, o caminho oficial estiver documentado como cloud-first, fixtures locais
continuarem funcionais sem credenciais, o legado permanecer recuperável e o
commit aprovado estiver publicado em `origin/main`.

O protocolo possui um único gate final. Uma falha localizada deve ser corrigida
e revalidada no menor escopo útil; não é necessário repetir a suíte ampla sem
mudança que possa afetá-la.

## Modelo e esforço por requisito

| ID | Modelo | Nível de esforço |
| --- | --- | --- |
| G05-SCOPE-01 | GPT-5.3-Codex-Spark | Baixo |
| G05-SCOPE-02 | GPT-5.3-Codex-Spark | Baixo |
| G05-SCOPE-03 | GPT-5.3-Codex-Spark | Baixo |
| G05-SCOPE-04 | GPT-5.3-Codex-Spark | Médio |
| G05-CLOUD-01 | GPT-5.3-Codex-Spark | Baixo |
| G05-CLOUD-02 | GPT-5.6-Codex | Médio |
| G05-CLOUD-03 | GPT-5.3-Codex-Spark | Médio |
| G05-CLOUD-04 | GPT-5.6-Codex | Médio |
| G05-CLOUD-05 | GPT-5.3-Codex-Spark | Baixo |
| G05-DOC-01 | GPT-5.3-Codex-Spark | Médio |
| G05-DOC-02 | GPT-5.3-Codex-Spark | Baixo |
| G05-DOC-03 | GPT-5.3-Codex-Spark | Médio |
| G05-DOC-04 | GPT-5.3-Codex-Spark | Baixo |
| G05-DOC-05 | GPT-5.3-Codex-Spark | Médio |
| G05-LEGACY-01 | GPT-5.3-Codex-Spark | Médio |
| G05-LEGACY-02 | GPT-5.3-Codex-Spark | Baixo |
| G05-LEGACY-03 | GPT-5.3-Codex-Spark | Baixo |
| G05-LEGACY-04 | GPT-5.3-Codex-Spark | Médio |
| G05-QUAL-01 | GPT-5.6-Codex | Médio |
| G05-QUAL-02 | GPT-5.6-Codex | Alto |
| G05-QUAL-03 | GPT-5.6-Codex | Alto |
| G05-QUAL-04 | GPT-5.6-Codex | Alto |
| G05-QUAL-05 | GPT-5.3-Codex-Spark | Médio |
| G05-GIT-01 | GPT-5.6-Codex | Médio |
| G05-GIT-02 | GPT-5.3-Codex-Spark | Baixo |
| G05-GIT-03 | GPT-5.6-Codex | Alto |
| G05-GIT-04 | GPT-5.3-Codex-Spark | Médio |

## Não objetivos

- remover módulos, notebooks, specs ou dados legados;
- modificar IAM, OpenTofu, Cloud Run, buckets ou imagens já implantadas, salvo
  correção indispensável de documentação ou teste sem efeito remoto;
- executar nova coleta, migração, transformação, build ou deploy;
- ampliar o corpus, mudar schemas ou introduzir BigQuery;
- tornar o Marimo público ou criar novo mecanismo de login;
- reorganizar ou excluir conteúdo no Google Drive.
