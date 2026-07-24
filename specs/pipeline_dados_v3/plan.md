# Plano do pipeline de dados v3

## Regra de avanço

Uma etapa por vez. O próximo submódulo só recebe specs depois que o anterior
for revisado e aprovado.

## Etapas

- [x] Concluir e verificar o arquivamento dos derivados antigos.
- [x] Aprovar as specs de `01_inventario_metadados_raw`.
- [x] Implementar o inventário em modo somente leitura.
- [x] Executar e revisar o smoke local com fixtures sintéticas.
- [x] Executar e revisar o smoke no Colab.
- [x] Executar o inventário completo no Colab.
- [x] Revisar o relatório e aprovar G01.
- [x] Especificar `02_schema_normalizado`.
- [ ] Propor categorias usando apenas os metadados observados.
- [ ] Especificar adaptadores determinísticos por fonte.
- [ ] Especificar e pilotar planos declarativos de identificação textual com
  GPT-5.6, incluindo comparação de qualidade, tokens e custo.
- [ ] Normalizar o universo completo.
- [ ] Definir e gerar o snapshot.
- [ ] Especificar a análise.

## Estado atual

- Estrutura v3: criada.
- Contrato geral: aprovado.
- Primeiro submódulo: concluído; G01 aprovado.
- Segundo submódulo: ferramenta implementada; execução integral e G02
  pendentes.
- Demais submódulos: reservados.
