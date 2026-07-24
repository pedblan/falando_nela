# Plano — snapshot de discursos v2

Status: **contrato aprovado em 2026-07-23 — execução não iniciada**.

1. Aprovar o inventário e as bases candidatas a canônicas.
2. Definir “discurso”, fontes, arenas, período e corte.
3. Decidir a regra de equivalência e duplicidade entre fontes.
4. Aprovar schema, nulabilidade, proveniência e estratégia de IDs.
5. Construir testes e uma pequena amostra de reconciliação.
6. Implementar as transformações fora do notebook.
7. Criar o notebook fino de execução no Colab.
8. Executar primeiro em amostra, sem sobrescrever artefatos.
9. Revisar contagens e casos problemáticos com o pesquisador.
10. Executar o universo aprovado em novo `snapshot_id`.
11. Validar estrutura, reconciliação, determinismo e comparação com v1.
12. Aprovar ou rejeitar formalmente o snapshot.

## Checkpoints humanos

- após o passo 3: aprovação das decisões D03–D05;
- após o passo 5: aprovação da amostra e das regras;
- após o passo 9: autorização para a execução completa;
- após o passo 11: decisão sobre o gate científico.

## Ponto de parada

Uma diferença de contagem sem explicação interrompe a promoção do snapshot,
mesmo que a execução técnica termine com sucesso.
