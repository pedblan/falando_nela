# Tech stack: reinício controlado da análise de plenário

Status: **contrato aprovado em 2026-07-23**.

Este documento complementa `specs/tech-stack.md`. Em caso de divergência, esta
spec mais específica prevalece somente dentro do reinício analítico.

## Ambiente

- Python 3.11+.
- Google Colab para leitura das bases completas no Drive.
- Ambiente local para specs, geradores, testes e fixtures pequenas.
- Jupyter/Colab como interface operacional; lógica substantiva em módulos
  Python importáveis.

## Dados

- Parquet para snapshots e catálogos tabulares volumosos.
- CSV apenas para tabelas pequenas destinadas a inspeção humana.
- Markdown para relatórios humanos.
- JSON para manifests técnicos pequenos e schemas estáveis.
- JSONL apenas quando append, streaming ou Batch justificarem o formato.

## Bibliotecas

- `pathlib` e biblioteca padrão para caminhos e inventário básico.
- `pandas` e `pyarrow` para Parquet e validação tabular.
- `nbformat` e `ast` para validação de notebooks.
- `hashlib` com leitura em blocos para hashes selecionados.
- JSON Schema ou validação Python explícita para manifests e relatórios.
- DuckDB pode ser adotado após benchmark e aprovação, não por default.

## Relatórios

- Geração por funções Python determinísticas.
- Markdown simples como formato primário humano.
- Tabelas compactas; nenhum dump integral de objetos de configuração.
- Links e caminhos devem ser produzidos a partir de artefatos observados.

## IA

- OpenAI não é dependência dos módulos de arquivamento, inventário, relatório
  ou snapshot.
- Qualquer uso futuro exige spec própria, Structured Outputs, orçamento,
  piloto e aprovação explícita.

## Restrições

- Não introduzir banco, framework de workflow ou ferramenta de observabilidade
  antes de demonstrar necessidade.
- Não usar notebook como única implementação.
- Não depender de estado oculto entre células.
- Não duplicar o stack global inteiro em specs de submódulo; registrar apenas
  escolhas e restrições adicionais.
