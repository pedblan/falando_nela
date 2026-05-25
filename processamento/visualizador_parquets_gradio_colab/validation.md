# Validation

## Checks obrigatorios de arquivo

- O notebook existe em:

```text
notebooks/processamento/visualizador_parquets_gradio_colab.ipynb
```

- O JSON do notebook e valido.
- Todas as celulas de codigo compilam com `ast.parse`.
- O notebook aponta para o diretorio Colab:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- O notebook importa ou instala `gradio`, `duckdb` e `altair`.
- O app e iniciado com `share=True`.

## Checks read-only

O notebook nao deve executar:

- `processamento.normalizacao`;
- `processamento.parquet`;
- `processamento.samples`;
- modulos em `coleta.*`;
- comandos de escrita de dados no Drive;
- criacao de manifests, JSONLs, Parquets ou ZIPs.

## Checks da consulta

- A listagem de bases retorna os arquivos `.parquet` existentes no diretorio
  configurado.
- Bases novas aparecem sem alteracao manual de lista no notebook.
- A consulta da tabela compacta usa DuckDB ou camada equivalente para aplicar
  filtros e limite antes de converter o resultado para pandas.
- A coluna `texto` nao aparece na tabela compacta.
- `texto_id` aparece na tabela compacta quando existe na base.
- Filtros por ano, mes, `documento_tipo`, `unidade_analitica`, `orgao_sigla`,
  `parlamentar_nome`, `proposicao_identificacao` e busca textual funcionam
  quando as colunas existem.
- A busca textual aceita frase entre aspas, por exemplo `"saude publica"`,
  sem procurar os caracteres de aspas literalmente.
- A busca textual respeita delimitacao de termo; por exemplo, `plexo` e
  `"plexo"` nao retornam `complexo`.
- A busca textual ignora diferenca basica de acento; por exemplo, `saude`
  encontra `saúde`.
- A busca textual aceita combinacoes com termos simples, `OR` ou `|`, e
  exclusao com `-termo` ou `-"frase"`.
- Filtros opcionais nao quebram o app quando uma coluna esta ausente ou so tem
  valores nulos.
- A ordenacao simples funciona somente com colunas existentes.
- O limite de linhas e respeitado.
- O grafico anual e retornado junto da tabela e nao inclui somente as linhas
  limitadas da tabela compacta.
- O grafico anual contem as series `Resultados`, `Por discurso` e
  `Por mil palavras`.
- O grafico anual usa eixo Y duplo: `Resultados` no eixo esquerdo e as metricas
  relativas no eixo direito.
- As series usam estilos distintos: linha continua, linha pontilhada e linha
  com marcadores triangulares.
- O grafico tem legenda e tooltip/mouseover com ano, serie, valor, resultados,
  discursos/registros e palavras.

## Checks de texto integral

- A selecao por `texto_id` faz uma consulta especifica para carregar a coluna
  `texto`.
- O texto retornado nao e truncado pelo codigo do app.
- O painel de metadados mostra campos essenciais disponiveis:
  `source`, `dataset`, `data`, `documento_tipo`, `unidade_analitica`, `titulo`,
  `parlamentar_nome`, `proposicao_identificacao`, `url_texto` e `raw_path`.
- Um `texto_id` inexistente retorna mensagem clara e nao derruba o app.

## Smoke local

Quando houver Parquets em:

```text
data/samples/textos_parlamentares/v1/parquet/
```

validar localmente que:

- as funcoes auxiliares listam pelo menos uma base;
- uma consulta compacta retorna ate o limite solicitado;
- a consulta compacta nao contem `texto`;
- um `texto_id` retornado pela tabela consegue carregar metadados e texto
  integral;
- filtros com colunas ausentes ou vazias retornam resultado vazio ou mensagem
  legivel, sem excecao nao tratada.

## Validacao no Colab

- Executar o notebook no Colab com Google Drive montado.
- Confirmar que os arquivos `.parquet` do Drive aparecem no seletor.
- Abrir uma base atualizada recentemente e comparar a contagem retornada pelo
  app com uma consulta DuckDB direta ao mesmo arquivo.
- Aplicar pelo menos um filtro temporal, um filtro categorico e uma busca
  textual.
- Selecionar um `texto_id` da tabela compacta e carregar o texto integral.
- Usar o botao de limpeza e confirmar que filtros e resultados voltam ao estado
  inicial esperado.

## Validacao apos atualizacao ou expansao de bases

Depois de rodar o fluxo de atualizacao temporal ou expansao:

- confirmar que `processamento.parquet --profile colab` gerou ou atualizou o
  Parquet esperado no Drive;
- relancar ou recarregar o visualizador;
- confirmar que a base atualizada aparece no seletor;
- conferir que filtros por data e campos-chave encontram os registros novos;
- abrir um `texto_id` novo e verificar que o texto integral e exibido sem
  truncamento.
