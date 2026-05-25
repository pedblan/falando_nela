# Requirements

## Objetivo

Criar o notebook operacional:

```text
notebooks/processamento/visualizador_parquets_gradio_colab.ipynb
```

O notebook deve iniciar, no Google Colab, um web app Gradio para navegar pelos
Parquets de `textos_parlamentares/v1` ja existentes no Google Drive. O app e
somente uma ferramenta de inspecao: nao coleta dados, nao normaliza, nao gera
Parquets e nao altera arquivos no Drive.

## Entrada

- Ler Parquets diretamente de:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Listar dinamicamente todos os arquivos `*.parquet` encontrados nesse
  diretorio, incluindo bases novas geradas em expansoes futuras.
- Aceitar um caminho de Parquets configuravel para smoke local contra:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- Assumir o contrato `textos_parlamentares/v1`, mas tolerar colunas opcionais
  ausentes ou totalmente nulas em algumas bases.

## Notebook Colab

- Montar o Google Drive antes de acessar dados.
- Atualizar ou clonar o repositorio antes de importar codigo local.
- Instalar dependencias necessarias para o app, incluindo `gradio`, `duckdb`,
  `altair`, `pandas` e suporte a Parquet.
- Definir constantes claras para repositorio, raiz de dados e diretorio de
  Parquets.
- Iniciar o app com `share=True`, para gerar um link publico temporario no
  Colab.
- Manter as funcoes de consulta separadas da montagem da interface, para
  permitir validacao local sem abrir o app.

## Consulta e memoria

- Usar DuckDB como camada principal de consulta sobre os Parquets.
- Evitar carregar a base completa em memoria antes de aplicar filtros e limite
  de linhas.
- Converter para pandas somente o resultado compacto ja filtrado e limitado.
- Carregar a coluna `texto` somente quando um `texto_id` for solicitado.
- Limitar resultados por default e impor um teto operacional para evitar
  respostas pesadas no Colab.
- Tratar nomes de arquivos, filtros textuais e ordenacao de forma segura,
  sem interpolar valores livres diretamente em SQL.

## Interface Gradio

O app deve expor:

- seletor de base Parquet por nome de arquivo;
- filtros por `ano`, `mes`, `documento_tipo`, `unidade_analitica`,
  `orgao_sigla`, `parlamentar_nome`, `proposicao_identificacao` e busca textual;
- controle de limite de linhas;
- ordenacao simples;
- botao para consultar;
- botao para limpar filtros;
- tabela compacta sem a coluna `texto`;
- grafico de linhas Altair com legenda e mouseover;
- campo de selecao ou digitacao de `texto_id`;
- painel de metadados essenciais;
- painel de texto integral sem truncamento.

## Grafico anual

- O grafico anual deve usar Altair.
- O grafico deve ser gerado a partir dos mesmos filtros da consulta, incluindo
  a busca textual, mas sem aplicar o limite de linhas da tabela.
- O grafico deve usar eixo Y duplo: eixo esquerdo para a contagem absoluta e
  eixo direito para as metricas relativas.
- O grafico deve ter uma linha continua no eixo esquerdo para a contagem
  absoluta de resultados por ano.
- O grafico deve ter uma linha pontilhada no eixo direito para resultados por
  discurso no ano, calculado como `resultados / registros_textuais_do_ano`.
- O grafico deve ter uma linha no eixo direito com marcadores triangulares para
  resultados por mil palavras no ano, calculado como
  `resultados * 1000 / palavras_do_ano`.
- O denominador de discursos/registros e palavras deve usar o corpus do ano
  apos filtros estruturais, mas antes da busca textual.
- A legenda deve identificar as tres series.
- O mouseover deve mostrar ano, serie, valor, resultados, discursos/registros e
  palavras.

## Busca textual

- A busca textual deve seguir semantica parecida com a pesquisa do Google:
  termos simples devem procurar palavras delimitadas, nao substrings internas
  de palavras maiores.
- A busca textual nao deve diferenciar maiusculas/minusculas nem acentos
  basicos.
- Termos separados por espaco devem funcionar como `AND`.
- Aspas devem preservar termos ou frases delimitadas, por exemplo
  `"saude publica"` ou `"plexo"`.
- Termos entre aspas e termos simples nao devem casar dentro de palavras
  maiores; por exemplo, `plexo` e `"plexo"` nao devem retornar ocorrencias de
  `complexo`.
- O operador `OR` ou `|` deve permitir alternativas entre termos ou frases.
- Prefixo `-` deve excluir termos ou frases, por exemplo `-privada` ou
  `-"saude privada"`.
- Os operadores devem ser convertidos em filtros parametrizados do DuckDB; o
  app nao deve aceitar SQL livre digitado pelo usuario.

## Tabela compacta

- A tabela deve sempre incluir `texto_id` quando a coluna existir.
- A tabela nao deve incluir `texto` por default.
- A ordem preferencial das colunas compactas deve priorizar identificacao e
  contexto:
  - `texto_id`;
  - `source`;
  - `dataset`;
  - `data`;
  - `ano`;
  - `mes`;
  - `documento_tipo`;
  - `unidade_analitica`;
  - `orgao_sigla`;
  - `parlamentar_nome`;
  - `proposicao_identificacao`;
  - `titulo`;
  - `texto_tamanho`;
  - `url_texto`;
  - `raw_path`.
- Colunas compactas ausentes devem ser simplesmente omitidas.

## Texto integral

- A selecao por `texto_id` deve fazer uma consulta especifica na base
  selecionada.
- O retorno deve incluir o `texto` integral sem truncamento.
- O painel de metadados deve incluir, quando disponiveis:
  - `source`;
  - `dataset`;
  - `data`;
  - `documento_tipo`;
  - `unidade_analitica`;
  - `titulo`;
  - `parlamentar_nome`;
  - `proposicao_identificacao`;
  - `url_texto`;
  - `raw_path`.
- Quando o `texto_id` nao existir, o app deve mostrar uma mensagem clara sem
  falhar.

## Atualizacao dos dados

- O visualizador deve refletir os Parquets presentes no Drive no momento em que
  o app for iniciado ou recarregado.
- Depois de uma atualizacao temporal ou expansao de base, o fluxo esperado e:
  gerar os Parquets atualizados, abrir ou relancar o notebook do visualizador e
  selecionar a base atualizada.
- Bases novas nao devem exigir mudanca manual em listas fixas no notebook; o
  app deve descobri-las pelo diretorio de Parquets.

## Fora de escopo

- Rodar coletores.
- Rodar `processamento.normalizacao`.
- Rodar `processamento.parquet`.
- Rodar `processamento.samples`.
- Escrever manifests, JSONLs, Parquets, ZIPs ou qualquer outro artefato de
  dados.
- Substituir os notebooks exploratorios didaticos ja existentes.
