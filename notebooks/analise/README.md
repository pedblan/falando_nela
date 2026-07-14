# Cadernos de análise dos discursos em plenário

Esta pasta contém a versão narrativa canônica, em português, dos cadernos
Colab. Execute-os em ordem e use o mesmo `RUN_ID`:

1. `00_snapshot_discursos_plenario_colab.ipynb`;
2. `01_enriquecimento_genero_colab.ipynb`;
3. `02_descritivas_discursos_plenario_colab.ipynb`;
4. `03_apartes_relacionais_colab.ipynb`, incluindo ponte, segmentação,
   codebooks de atos de fala, possível descortesia e piloto humano;
5. `04_nlp_leiturabilidade_morfossintaxe_colab.ipynb`;
6. `05_inferencia_series_temporais_colab.ipynb`;
7. `06_clusterizacao_discursos_colab.ipynb`;
8. `07_topicos_bertopic_colab.ipynb`;
9. `08_figuras_linguagem_gpt56_colab.ipynb`;
10. `09_sintese_comparativa_colab.ipynb`.

## Execução

A primeira célula executável monta o Drive. A segunda prepara o repositório e
instala `requirements-analise.txt`. O corpus completo esperado está em:

```text
/content/drive/MyDrive/falando_nela/data
```

A preparação reinstala e valida o par binário `numpy==2.0.2` e
`pandas==2.2.3`, compatível com o runtime Colab 2026.04, antes de importar a
lógica analítica. A saída da célula deve terminar com
`ABI: NumPy 2.0.2; pandas 2.2.3`. Se outra versão já estiver carregada ou a
sessão tiver sido alterada por uma execução anterior, desconecte e exclua o
runtime, conecte uma sessão nova e rode o caderno desde o início.

Cada etapa cara começa com `RODAR_ETAPA = False`. Revise configuração,
entradas e cadernos anteriores; mude para `True` apenas quando desejar criar os
artefatos. O caderno de figuras lê `OPENAI_API_KEY` do ambiente no momento da
chamada e nunca a imprime ou grava. O mesmo vale para a pesquisa de gênero e a
classificação qualitativa dos apartes.

No caderno 03, a análise relacional pode ser executada antes da qualitativa. O
Batch de atos de fala permanece bloqueado até uma amostra humana confirmar a
segmentação do turno do aparte e da resposta. Discurso inteiro, URL ou metadado
relacional não substituem o texto segmentado.

## Resultados

Todos os artefatos ficam em:

```text
analises/discursos_plenario/v1/{RUN_ID}/
```

O snapshot e o manifest 00 devem ser considerados imutáveis após a revisão. Se
o corpus ou a configuração mudar, use outro `RUN_ID`.

A validação final do caderno 00 também está disponível como célula autônoma em
`notebooks/analise/celulas/00_validacao_snapshot.py`. Ela pode ser adicionada
diretamente a uma sessão Colab que já tenha o Drive montado: usa `RUN_ID`,
`DATA_ROOT` e `RUN_OUTPUT_ROOT` quando existirem e, caso contrário, aplica os
valores padrão da análise. Ela apenas lê o snapshot pronto; não reinstala
dependências nem reexecuta a geração.

Depois de publicar a versão no GitHub, a célula pode ser carregada diretamente
em um caderno Colab já aberto com uma única célula auxiliar:

```python
from urllib.request import urlopen

CELL_URL = "https://raw.githubusercontent.com/pedblan/falando_nela/main/notebooks/analise/celulas/00_validacao_snapshot.py"
exec(compile(urlopen(CELL_URL).read().decode("utf-8"), CELL_URL, "exec"))
```

## Marimo e inglês

Os notebooks mantêm lógica substantiva fora das células, IDs Markdown estáveis
e configuração serializável. Uma fase futura pode criar equivalentes em
`notebooks/analise/marimo/` com `marimo convert` e variantes `_en.ipynb` que
substituem apenas Markdown. Português permanece a fonte narrativa de verdade;
código e resultados devem ser idênticos entre idiomas e formatos.
