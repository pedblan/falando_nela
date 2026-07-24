# Plano — inventário de metadados raw

## Estado

Etapa concluída. G01 aprovado em 2026-07-24.

## Sequência futura

- [x] Implementar o módulo e a CLI somente leitura.
- [x] Criar o notebook Colab com gates separados.
- [x] Fazer smoke local com fixtures sintéticas.
- [x] Validar que conteúdo textual longo não é copiado para as saídas locais.
- [x] Confirmar G00 e a raiz exata no Drive montado.
- [x] Fazer smoke Colab em uma pequena amostra por fonte e formato.
- [x] Revisar os campos do smoke e confirmar que nenhum texto longo foi copiado.
- [x] Executar o inventário completo em modo somente leitura.
- [x] Reconciliar arquivos, registros e presença de campos.
- [x] Gerar os sete artefatos obrigatórios fora do Drive.
- [x] Revisar humanamente o relatório e as tabelas.
- [x] Registrar aprovação de G01.
- [ ] Somente depois iniciar as specs de `02_schema_normalizado`.

## Gates internos

| Gate | Pergunta |
|---|---|
| I01 | A raiz contém somente o raw aprovado? |
| I02 | O parser cobre os formatos observados no smoke? |
| I03 | As saídas não reproduzem textos longos? |
| I04 | Todas as unidades reconciliam? |
| I05 | O relatório permite desenhar as categorias sem adivinhação? |

## Entrega técnica disponível

Esta etapa já entrega:

- módulo Python somente leitura;
- CLI do inventário;
- notebook Colab com gates separados para smoke e execução completa;
- testes com fixtures sintéticas.

Também entrega:

- execução somente leitura sobre o Drive;
- catálogo do universo real;
- aprovação G01 documentada;

Ainda não entrega:

- schema normalizado;
- chamada GPT.
