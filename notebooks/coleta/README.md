# Notebooks de coleta

Esta pasta guarda notebooks operacionais para execucao de coletores, especialmente no Google Colab com Drive montado.

Convencoes:

- A primeira celula executavel deve montar o Google Drive quando o notebook depender de `FALANDO_NELA_DATA_ROOT`.
- O clone/pull do repositorio e a instalacao de dependencias devem vir depois da montagem do Drive.
- Estes notebooks nao sao cadernos analiticos de artigo; eles existem para orquestrar coletas e validacoes.
- Cadernos de artigos devem ficar em outras subpastas de `notebooks/`, separadas por tema ou artigo.

Arquivos atuais:

- `coleta_template.ipynb`: template geral para rodar todos os coletores, incluindo pareceres de PEC.
- `coleta_senado_plenario.ipynb`: fluxo especifico para validar e rodar a coleta do Plenario do Senado.
- `coleta_senado_ccj.ipynb`: fluxo especifico para validar e rodar a coleta de notas da CCJ do Senado.
