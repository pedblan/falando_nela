# Stack técnica do pipeline de dados v3

## Estado

Stack mínima proposta. Dependências específicas só serão adicionadas quando o
submódulo correspondente for aprovado.

## Ambiente

- Python 3 no Google Colab para operações sobre o corpus completo.
- Google Drive montado como armazenamento persistente.
- Repositório Git como fonte de código e contratos.
- Execuções locais limitadas a testes e amostras controladas.

## Dados

- JSON, JSONL e demais formatos existentes no raw serão lidos sem mutação.
- CSV ou Parquet poderão ser usados para catálogos tabulares derivados.
- JSON será usado para manifests pequenos e configurações efetivas.
- Markdown será usado para o relatório humano principal de cada operação.

## GPT

- Família aprovada para o piloto de interpretação textual: GPT-5.6.
- O alias `gpt-5.6` e o identificador efetivamente resolvido deverão ser
  registrados; nenhum tier será promovido sem comparação de qualidade e custo.
- API Responses com saída estruturada.
- JSON Schema fechado para planos declarativos de transformação.
- Um motor Python comum e testado aplicará os planos; respostas do modelo não
  serão executadas como código.
- Chamadas síncronas em piloto; Batch API somente depois de gate específico.
- Uso de cache somente depois de medir a repetição real do prefixo do prompt e
  conferir o preço vigente.
- Chave obtida de segredo do Colab ou ambiente, nunca gravada no repositório,
  notebook, manifest ou log.

Os preços não são fixados nesta spec, pois podem mudar. Cada execução aprovada
deverá registrar a tabela de preços consultada, sua data e a fórmula usada na
projeção.

## Restrições

- O submódulo `01_inventario_metadados_raw` não usa GPT nem requer chave.
- Bibliotecas não serão escolhidas antes de existir requisito concreto.
- Nenhuma dependência da implementação v1 é presumida como canônica.
