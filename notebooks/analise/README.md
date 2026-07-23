# Cadernos de análise dos discursos em plenário

Esta pasta contém a versão narrativa canônica, em português, dos cadernos
Colab. Execute-os em ordem e use o mesmo `RUN_ID`:

1. `00_snapshot_discursos_plenario_colab.ipynb`;
2. `01_enriquecimento_genero_colab.ipynb` — pesquisa de deputados suspensa;
3. `02_descritivas_discursos_plenario_colab.ipynb`;
4. `03_apartes_relacionais_colab.ipynb`, incluindo ponte, segmentação,
   codebooks de atos de fala, possível descortesia e piloto humano;
5. `04_nlp_leiturabilidade_morfossintaxe_colab.ipynb`;
6. `05_inferencia_series_temporais_colab.ipynb`;
7. `06_clusterizacao_discursos_colab.ipynb`;
8. `07_topicos_bertopic_colab.ipynb`;
9. `08_figuras_linguagem_gpt56_colab.ipynb`;
10. `09_sintese_comparativa_colab.ipynb`.

A rodada analítica ativa usa, por padrão,
`RUN_ID = "analise-plenario-20260717-v1"`. Seu snapshot validado contém
384.191 discursos e mantém o corte analítico da configuração em
`2026-07-13`. A data do `RUN_ID` identifica a rodada; não amplia por si só o
recorte temporal.

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
chamada e nunca a imprime ou grava. O mesmo vale para a classificação
qualitativa dos apartes.

Na rodada `analise-plenario-20260717-v1`, a pesquisa pública de gênero para
deputados está suspensa por custo e baixa qualidade. O caderno 01 é somente
leitura: mostra a cobertura do metadado oficial, não cria fila, não chama API e
não publica enriquecimento. Casos sem metadado permanecem `nao_informado`;
gênero não é inferido pelo nome. Metadados oficiais já existentes, inclusive
os do Senado, continuam preservados. Artefatos eventualmente criados por uma
execução anterior do caderno 01 não são apagados nem consumidos pelos cadernos
seguintes. Prossiga diretamente ao caderno 02.

No caderno 03, o recorte temporal é reaplicado à base de apartes antes de
qualquer resultado. Nem todo discurso é considerado um aparte: a base
processada fornece os candidatos, a ponte seleciona as transcrições ligadas e
cada discurso é enviado uma única vez à IA, mesmo quando possui vários
candidatos. A transcrição é dividida localmente em blocos numerados; o modelo
devolve somente status e limites de blocos, e texto/offsets são reconstruídos
na máquina local.

A segmentação por marcadores permanece como diagnóstico. O resultado oficial
`interacoes_segmentadas_ia.parquet` é criado apenas após processar o Batch de
segmentação; o antigo `interacoes_segmentadas.parquet` não é consumido por
nenhuma etapa nova. `aparte_nao_localizado`,
`incerto` e ausência de resposta explícita são estados válidos. O Batch de
atos de fala permanece bloqueado até pelo menos 100 revisões humanas completas
confirmarem precisão de 95% para aparte e resposta; campos vazios não contam
como revisão. Discurso inteiro, URL ou metadado relacional não substituem o
texto segmentado.

Os dois Batches do caderno 03 são divididos automaticamente em partes de até
50.000 pedidos e 190 MiB. Os manifests `batch_segmentacao_requests.json` e
`batch_atos_fala_requests.json`, junto dos controles de submissão, permitem
retomar o trabalho depois de reiniciar o Colab sem reenviar partes já
registradas. O codebook e os arquivos `revisao_segmentacao_ia.csv` e
`piloto_atos_fala_ia.csv` preservam preenchimentos humanos; os artefatos
legados sem `_ia` não são consumidos.

## Resultados

Todos os artefatos ficam em:

```text
analises/discursos_plenario/v1/{RUN_ID}/
```

O snapshot e o manifest 00 devem ser considerados imutáveis após a revisão. Se
o corpus ou a configuração mudar, use outro `RUN_ID`.
Como o snapshot de `analise-plenario-20260717-v1` já foi validado, prossiga do
caderno 01 em diante e não reexecute a geração do caderno 00 com
`RODAR_ETAPA=True`.

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
