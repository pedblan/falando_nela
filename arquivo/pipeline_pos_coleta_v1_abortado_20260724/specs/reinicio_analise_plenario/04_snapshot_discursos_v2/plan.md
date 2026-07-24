# Plano — snapshot de discursos v2

Status: **schema aprovado — smoke implementado; execução real pendente**.

1. Registrar o baseline exploratório e identificar diretamente as bases
   processadas candidatas a canônicas.
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

- após o passo 1: aprovação das bases que podem alimentar o censo;
- após o passo 3: aprovação das decisões D03–D05;
- após o passo 5: aprovação da amostra e das regras;
- após o passo 9: autorização para a execução completa;
- após o passo 11: decisão sobre o gate científico.

## Progresso

- [x] Baseline exploratório da fase 3 registrado.
- [x] Três bases candidatas e política de leitura aprovadas.
- [x] Módulo do censo somente leitura implementado.
- [x] Notebook fino com dois gates desligados por padrão implementado.
- [x] Fixtures locais e pacote D06 validados.
- [x] Revisão identificável do censo publicada na `main`.
- [x] Operação `snapshot-census-20260724t024812z` executada no Colab.
- [x] Cobertura revisada: 428.372 registros e IDs distintos.
- [x] D03–D05 aprovadas.
- [x] Aprovar o schema do snapshot v2.
- [x] Implementar transformação e notebook de smoke.
- [ ] Executar o smoke no Colab e revisar a amostra.
- [ ] Autorizar separadamente a implementação e execução integral.

## Ponto de parada

Uma diferença de contagem sem explicação interrompe a promoção do snapshot,
mesmo que a execução técnica termine com sucesso.
