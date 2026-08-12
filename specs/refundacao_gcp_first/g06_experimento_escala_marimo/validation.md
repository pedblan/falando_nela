# Validação operacional — G06 experimento de escala do Marimo

## Estado

As medições pequenas e o gate humano foram concluídos em `2026-08-12`. O
pesquisador aprovou manter a escala `0–1`.

## Checklist

- [x] Medir cold start com serviço em estado frio e registrar tempo de resposta por tentativa.
- [x] Validar duas abas autenticadas com WebSockets independentes.
- [x] Consolidar evidência mínima em `auditoria_g06_20260812.md`.
- [x] Recomendar manter a capacidade atual e registrar quando reavaliá-la.
- [x] Obter aprovação humana para encerrar G06.

## Regras de execução recomendadas

1. Confirmar por log que o primeiro acesso criou uma instância por autoscaling.
2. Comparar esse acesso com quatro requests aquecidos.
3. Abrir duas abas pelo proxy autenticado e confirmar 30 registros, conexões
   WebSocket distintas e ausência de erro visível.
4. Registrar tudo em uma nota curta, sem conteúdo dos discursos.

## Evidência esperada

- **G06-EV-01:** cold start registrado e classificado.
- **G06-EV-02:** duas abas autenticadas executadas sem erro funcional.
- **G06-EV-03:** recomendação escrita de manter `0–1`.
- **G06-EV-04:** condição simples de reavaliação registrada.

## Matriz de validação

| ID | Validação | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G06-V01 | Confirmar cold start e quatro requests aquecidos. | GPT-5.3-Codex-Spark | Baixo |
| G06-V02 | Validar duas abas e WebSockets independentes via proxy. | GPT-5.3-Codex-Spark | Baixo |
| G06-V03 | Consolidar a evidência e a recomendação. | GPT-5.3-Codex-Spark | Baixo |
| G06-V04 | Registrar decisão de capacidade com aprovação humana. | GPT-5.3-Codex-Spark | Baixo |

## Comandos base (orientativos)

```bash
# Medição local (já validado em G04):
uv run --locked --group cloud --group notebooks marimo run notebooks/primeiro_recorte_discursos.py \
  --host 127.0.0.1 --port 2718

# Medição remota (autenticada), sem mudanças de infraestrutura:
gcloud run services proxy fn-marimo --region southamerica-east1 --project falando-nela-pedblan --port 8080
# Em seguida abrir duas abas e confirmar o carregamento do app.
```

Observação: o modo de autenticação deve permanecer o já adotado no G04 e a
aplicação não deve receber tráfego público durante o experimento.

## Custos e interrupção (fase experimental)

Sem criação de recurso novo e sem aplicação de IaC nesta fase.
Não há teste de carga nesta fase. Reavaliar somente diante de falha funcional ou
espera recorrente percebida pelo pesquisador.

Evidência de conclusão: aprovação explícita do pesquisador em `2026-08-12`,
sem mudança de infraestrutura.
