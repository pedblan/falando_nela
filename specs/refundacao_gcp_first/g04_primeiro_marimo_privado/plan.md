# Plano operacional — G04 primeiro app Marimo privado

## Modelo e esforço por tarefa

| ID | Tarefa | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G04-P01 | Criar `notebooks/primeiro_recorte_discursos.py` com leitura de Parquet em módulo reutilizável e execução como script sem sessão interativa. | GPT-5.3-Codex-Spark | Médio |
| G04-P02 | Incluir filtros leves e tabela mínima do recorte, mantendo a fonte e schema congelados. | GPT-5.3-Codex-Spark | Médio |
| G04-P03 | Adicionar fixture local explicitamente selecionada, sem fallback, e testes de execução sem ADC. | GPT-5.3-Codex-Spark | Médio |
| G04-P04 | Ajustar dependências e build para incluir `marimo` no artefato do app. | GPT-5.6-Codex | Alto |
| G04-P05 | Criar Dockerfile/Cloud Build dedicado do app (sem quebrar pipeline G03). | GPT-5.6-Codex | Médio |
| G04-P06 | Declarar service account `fn-marimo` e IAM de leitura mínimo em OpenTofu. | GPT-5.3-Codex-Spark | Médio |
| G04-P07 | Publicar serviço Cloud Run privado com zero instâncias mínimas e máximo de uma instância. | GPT-5.3-Codex-Spark | Alto |
| G04-P08 | Configurar autenticação IAM-required e validar que não existe anônimo. | GPT-5.3-Codex-Spark | Médio |
| G04-P09 | Executar `marimo check`, script com fixture, smoke GCS e revisão visual em localhost. | GPT-5.3-Codex-Spark | Médio |
| G04-P10 | Fazer smoke remoto autenticado e validar health check + resposta mínima esperada. | GPT-5.3-Codex-Spark | Alto |
| G04-P11 | Registrar limitações reais da etapa e próximo experimento de escala. | GPT-5.6-Codex | Baixo |

- [x] Criar `notebooks/primeiro_recorte_discursos.py` com leitura de Parquet em módulo reutilizável e execução como script sem sessão interativa.
- [x] Incluir filtros leves e tabela mínima do recorte, mantendo a fonte e schema congelados.
- [x] Adicionar fixture local explicitamente selecionada, sem fallback, e testes de execução sem ADC.
- [x] Ajustar dependências e build para incluir `marimo` no artefato do app.
- [x] Criar Dockerfile/Cloud Build dedicado do app (sem quebrar pipeline G03).
- [x] Declarar service account `fn-marimo` e IAM de leitura mínimo em OpenTofu.
- [x] Publicar serviço Cloud Run privado com zero instâncias mínimas e máximo de uma instância.
- [x] Configurar autenticação IAM-required e validar que não existe anônimo.
- [x] Executar `marimo check`, script com fixture, smoke GCS e revisão visual em localhost.
- [x] Fazer smoke remoto autenticado e validar health check + resposta mínima esperada.
- [x] Registrar limitações reais da etapa e próximo experimento de escala.

## Limite de avanço deste passo

Não avançar para G05 sem:

- app lendo apenas `data/processed/v1/g03/...` com sucesso;
- autenticação validada (sem acesso anônimo);
- retorno local verificável por `marimo run` e smoke remoto.

## Gate (único para G04)

Uma aprovação cobre o pacote completo G04: código do app, container mínimo para
execução, infraestrutura de publicação e smoke autenticado inicial. O mesmo
aprovador localiza:

- dataset e operação confirmada,
- serviço privado sem anônimo,
- execução local por script e smoke remoto positivo.

## Gate concluído

O gate único foi concluído em 2026-08-12. A imagem
`marimo-primeiro@sha256:f21c13d98eb774444cdc00c0cff11c65b8a366d32aed9d70761558e10295491d`
foi publicada e o serviço privado `fn-marimo` foi aplicado em
`southamerica-east1`, com escala de zero a uma instância. O readback posterior
do OpenTofu não encontrou drift.

Evidência local em 2026-08-12: `marimo check` sem achados; 72 testes do ciclo
GCP-first aprovados; smoke via ADC com 30 registros; busca, filtro de partido,
tabela e detalhe verificados em `127.0.0.1:2718`, sem erros no console.
O usuário aprovou a experiência local na mesma data.

Evidência remota em 2026-08-12: acesso anônimo retornou `403`; requisição
autenticada retornou `200`; o app leu GCS com 30 registros, busca e filtros
funcionando; o log de carregamento conteve apenas fonte, operação, contagem e
duração. O IAM do serviço não contém `allUsers` nem `allAuthenticatedUsers`.

## Limitações e próximo experimento

- O acesso é IAM-only: um navegador comum precisa de um cliente que injete a
  identidade Google, como o proxy oficial do Cloud Run. Não há domínio público,
  IAP ou login de aplicação nesta etapa.
- O recorte contém somente 30 discursos e a escala máxima é uma instância;
  cold start é um comportamento esperado com `min_instance_count=0`.
- Próximo experimento de escala: medir cold start e uma sessão autenticada
  concorrente antes de ampliar o recorte ou alterar os limites de instância.
