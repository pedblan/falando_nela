# Plano operacional — G06 experimento de escala do Marimo

## Estado

G05 concluiu o corte cloud-first e a publicação do app `fn-marimo`. G06 verifica
se a configuração atual atende ao uso individual do pesquisador. Não é um teste
de carga nem uma preparação para operação multiusuário.

## Modelo e esforço por tarefa

| ID | Tarefa | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G06-P01 | Confirmar um cold start e comparar com uma pequena sequência aquecida. | GPT-5.3-Codex-Spark | Baixo |
| G06-P02 | Abrir duas abas autenticadas, confirmar 30 registros e WebSockets independentes. | GPT-5.3-Codex-Spark | Baixo |
| G06-P03 | Registrar a decisão simples de manter ou rever a escala atual. | GPT-5.3-Codex-Spark | Baixo |
| G06-P04 | Sincronizar auditoria curta, checklists e índice das specs. | GPT-5.3-Codex-Spark | Baixo |

- [x] Confirmar cold start por evento de autoscaling e registrar uma pequena sequência aquecida.
- [x] Validar duas abas autenticadas com 30 registros e WebSockets distintos.
- [x] Recomendar manter a escala `0–1` e registrar quando reavaliá-la.
- [x] Sincronizar auditoria, validação, plano raiz e índice das specs.
- [x] Obter aprovação humana para encerrar G06 mantendo a escala `0–1`.

Esta revisão foi executada com GPT-5, alternativa disponível ao
GPT-5.3-Codex-Spark previsto. O esforço prescrito permaneceu baixo e não houve
impacto material no escopo ou no resultado.

## Limite de avanço da etapa

Não aumentar recorte de dataset nem alterar contratos de datasource fora do
escopo de G04/G05. Qualquer alteração de capacidade será uma tarefa posterior,
somente se o uso real do pesquisador mostrar necessidade.

## Gate de G06 (único)

Esta etapa conclui com:

1. Um cold start confirmado por log do Cloud Run;
2. Duas abas autenticadas carregando o app com conexões independentes;
3. Recomendação de capacidade documentada e aprovada pelo pesquisador;
4. Nenhuma modificação de recurso persistente.

## Sequência de execução

- P01 e P02 usam os artefatos já publicados (`fn-marimo`, `marimo-primeiro`).
- P03 registra a recomendação no artefato local, sem alterar infraestrutura.
- P04 mantém as specs sincronizadas e registra a aprovação humana final.

## Evidência de preparação

Em `2026-08-12`, G04 e G05 já foram aprovados e publicados em `main` com app privado
`fn-marimo` e escala inicial de `0–1`. O experimento G06 parte desse estado já estável.

O gate G06 foi aprovado pelo pesquisador em `2026-08-12`, mantendo a escala
`0–1` e sem alteração de infraestrutura.
