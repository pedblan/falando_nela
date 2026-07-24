# Plano: reinício controlado da análise de plenário

Status: **contrato aprovado em 2026-07-23**.

## Fase 0 — Aprovar o contrato

1. Revisar o mapa das decisões D01–D06 e quando cada uma será tomada.
2. Aprovar requirements, validation e tech-stack gerais.
3. Registrar responsáveis e data da aprovação.
4. Proibir cada implementação enquanto houver decisão bloqueante para ela.

## Fase 1 — Arquivar sem apagar

1. Executar o inventário local dos notebooks e specs atuais.
2. Comparar o inventário com o Git.
3. Aprovar o nome final do diretório de arquivo.
4. Arquivar os notebooks antigos e criar um índice explicativo.
5. Se D02 for aprovada, marcar a execução antiga no Drive sem mover seus dados.

## Fase 2 — Padronizar relatórios

1. Aprovar a separação relatório/manifest/log.
2. Aprovar o vocabulário de estados e os campos mínimos D06.
3. Implementar schemas e renderizador em fixture local.
4. Validar compreensão humana do relatório.
5. Reservar o caderno de inventário como primeiro piloto real.

## Fase 3 — Inventariar o Drive

1. Aprovar a spec do inventário.
2. Executar caderno somente leitura.
3. Produzir catálogo, mapa humano e inconsistências.
4. Revisar juntos os universos e as contagens.
5. Decidir se uma migração física é necessária.

## Fase 4 — Construir snapshot v2

1. Aprovar universo, arenas, datasets, corte e deduplicação.
2. Executar smoke com contagens detalhadas.
3. Revisar diferenças contra o snapshot v1.
4. Executar no Drive.
5. Congelar o snapshot por ID e hash.

## Fase 5 — Especificar a análise

1. Definir perguntas de pesquisa.
2. Definir unidades e denominadores.
3. Propor somente o primeiro passo científico.
4. Aprovar sua spec.
5. Implementar e revisar um piloto antes de planejar o passo seguinte.

## Condições de parada

Interromper se:

- um universo não puder ser explicado;
- uma contagem não reconciliar com seu denominador;
- um relatório exigir leitura do log completo para ser entendido;
- surgir movimentação não prevista de dados;
- houver divergência entre spec, código e notebook;
- uma decisão substantiva estiver sendo tomada implicitamente.
