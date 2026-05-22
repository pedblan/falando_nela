# Notebooks de processamento

Esta pasta guarda notebooks operacionais da fase 3, especialmente para execucao
no Google Colab com Drive montado.

Convencoes:

- A primeira celula executavel deve montar o Google Drive.
- O clone/pull do repositorio e a instalacao de dependencias devem vir depois
  da montagem do Drive.
- A execucao principal deve chamar funcoes Python do projeto diretamente quando
  isso for mais claro no Colab.
- Estes notebooks nao sao cadernos analiticos de artigo; eles existem para
  consolidar e validar dados processados.

Arquivos atuais:

- `normalizacao_armazenamento_colab.ipynb`: executa
  `processed/textos_parlamentares/v1` a partir do `raw/` no Google Drive.
- `descricao_analitica_bases_colab.ipynb`: resume a base processada por fonte,
  dataset, ano, familia textual e preenchimento de campos.
