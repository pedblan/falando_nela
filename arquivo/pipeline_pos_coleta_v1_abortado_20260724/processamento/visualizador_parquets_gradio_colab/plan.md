# Plan

## Etapa 1: revisar contratos e exemplos

- Ler as specs de `processamento/normalizacao_armazenamento/`.
- Conferir o padrao dos notebooks existentes em `notebooks/processamento/`.
- Identificar as colunas compactas e os campos de metadados do contrato
  `textos_parlamentares/v1`.

## Etapa 2: estruturar o notebook Colab

- Criar `notebooks/processamento/visualizador_parquets_gradio_colab.ipynb`.
- Incluir celulas curtas para:
  - montar Google Drive;
  - clonar ou atualizar o repositorio;
  - instalar dependencias;
  - definir caminhos;
  - importar bibliotecas;
  - declarar funcoes auxiliares;
  - montar e iniciar o app Gradio.
- Preservar o padrao Colab do projeto: Drive primeiro, repositorio segundo,
  dependencias terceiro, execucao depois.

## Etapa 3: implementar camada de consulta

- Listar arquivos `*.parquet` dinamicamente no diretorio configurado.
- Abrir consultas com DuckDB sobre o arquivo selecionado.
- Descobrir schema/colunas da base selecionada antes de montar filtros.
- Montar filtros apenas para colunas existentes.
- Aplicar filtros por ano, mes, `documento_tipo`, `unidade_analitica`,
  `orgao_sigla`, `parlamentar_nome`, `proposicao_identificacao` e busca textual.
- Retornar somente colunas compactas e linhas limitadas para a tabela.
- Implementar consulta separada para buscar `texto` integral por `texto_id`.

## Etapa 4: implementar interface Gradio

- Criar seletor de base.
- Criar controles de filtro, limite e ordenacao.
- Criar tabela compacta de resultados.
- Criar entrada para `texto_id`.
- Criar painel de metadados e painel de texto integral.
- Adicionar acoes de consultar, limpar filtros e carregar texto.
- Garantir que estados vazios ou arquivos ausentes retornem mensagens legiveis.

## Etapa 5: garantir comportamento de atualizacao

- Evitar listas hardcoded de bases no app.
- Fazer o seletor refletir os arquivos `.parquet` existentes no diretorio.
- Documentar no notebook que, apos atualizar ou expandir dados, o usuario deve
  regenerar Parquets no fluxo apropriado e relancar/recarregar o visualizador.
- Manter o visualizador estritamente read-only.

## Etapa 6: validar notebook e smoke local

- Validar JSON do notebook.
- Compilar todas as celulas de codigo com `ast.parse`.
- Verificar estaticamente que o notebook nao chama coleta, normalizacao,
  geracao de Parquets ou geracao de samples.
- Quando existirem Parquets locais de sample, exercitar as funcoes de consulta
  contra `data/samples/textos_parlamentares/v1/parquet/`.
- No Colab, confirmar que o app inicia com `share=True` e lista os Parquets do
  Drive.

## Etapa 7: atualizar documentacao operacional

- Se a implementacao adicionar dependencias permanentes, atualizar
  `requirements.txt`.
- Atualizar documentacao curta do processamento quando necessario para apontar
  o notebook como visualizador web dos Parquets.
