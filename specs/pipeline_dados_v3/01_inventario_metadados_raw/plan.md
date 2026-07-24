# Plano — inventário de metadados raw

## Estado

Specs aprovadas e implementação local validada. A execução no Drive ainda não
foi iniciada.

## Sequência futura

- [x] Implementar o módulo e a CLI somente leitura.
- [x] Criar o notebook Colab com gates separados.
- [x] Fazer smoke local com fixtures sintéticas.
- [x] Validar que conteúdo textual longo não é copiado para as saídas locais.
- [ ] Confirmar G00 e a raiz exata no Drive montado.
- [ ] Fazer smoke Colab em uma pequena amostra por fonte e formato.
- [ ] Revisar os campos do smoke e confirmar que nenhum texto longo foi copiado.
- [ ] Executar o inventário completo em modo somente leitura.
- [ ] Reconciliar arquivos, registros e presença de campos.
- [ ] Gerar os sete artefatos obrigatórios fora do Drive.
- [ ] Revisar humanamente o relatório e as tabelas.
- [ ] Registrar aprovação ou rejeição de G01.
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

Ainda não entrega:

- execução no Drive;
- catálogo do universo real;
- aprovação G01;
- schema normalizado;
- chamada GPT.
