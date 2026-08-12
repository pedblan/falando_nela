# Requisitos operacionais — G06 experimento de escala do Marimo

## Objetivo

Confirmar, com uma prova pequena, que o app `fn-marimo` atende ao uso de um único
pesquisador: aceitar o cold start esperado e suportar duas abas autenticadas ao
mesmo tempo. A saída é uma decisão simples sobre manter a escala atual.

## Regras de mensuração (experimento)

- **G06-REQ-01:** confirmar um primeiro request em instância criada por
  autoscaling e compará-lo com quatro requests aquecidos.
- **G06-REQ-02:** registrar status, latência do primeiro request e mediana dos
  requests aquecidos, sem coletar conteúdo dos discursos.
- **G06-REQ-03:** abrir duas abas autenticadas, confirmar 30 registros em cada
  uma e dois WebSockets distintos com handshake bem-sucedido.
- **G06-REQ-04:** manter uma única nota curta no repositório com projeto,
  região, horários, resultados e limitações, sem credenciais.

## Resultados esperados

- **G06-RES-01:** nota com cold start, quatro acessos aquecidos e mediana.
- **G06-RES-02:** duas abas funcionais, sem erro no console e com WebSockets
  independentes.
- **G06-RES-03:** recomendação explícita de manter `0–1` ou reavaliar a escala.

## Não objetivos

- Não mudar `min_instance_count`/`max_instance_count` nesta etapa.
- Não ampliar o recorte de registros ou carregar novos datasets no app.
- Não mudar service account ou políticas IAM.
- Não executar chamadas de APIs parlamentares no experimento.
- Não fazer teste de carga, criar dashboards ou definir SLO/SLA.
- Não preparar deployment industrial ou operação multiusuário.

## Modelo e esforço por requisito

| ID | Requisito | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G06-REQ-01 | Cold start e sequência aquecida curta. | GPT-5.3-Codex-Spark | Baixo |
| G06-REQ-02 | Métricas mínimas sem conteúdo de pesquisa. | GPT-5.3-Codex-Spark | Baixo |
| G06-REQ-03 | Duas abas e WebSockets independentes. | GPT-5.3-Codex-Spark | Baixo |
| G06-REQ-04 | Evidência curta e versionada. | GPT-5.3-Codex-Spark | Baixo |

## Validação de custo e risco aceito

Sem mudança remota, `tofu apply`, build ou upload. A escala só será reconsiderada
se o pesquisador perceber espera recorrente ou passar a usar o app com outras pessoas.
