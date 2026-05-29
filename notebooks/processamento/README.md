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
- `geracao_parquets_colab.ipynb`: gera Parquets unificados por base a partir dos
  JSONLs processed ja existentes no Drive, sem rerodar a normalizacao.
- `descricao_analitica_bases_colab.ipynb`: resume a base processada por fonte,
  dataset, ano, familia textual e preenchimento de campos, usando os Parquets
  quando eles estiverem disponiveis.
- `exploracao_parquets_colab.ipynb`: explora os Parquets completos no Drive com
  `DataFrame`, contagens basicas, filtros e leitura de texto integral.
- `exploracao_parquets_samples_local.ipynb`: faz a mesma exploracao sobre os
  Parquets das samples locais.
- `visualizador_parquets_gradio_colab.ipynb`: abre um web app Gradio read-only
  para navegar pelos Parquets do Drive no Colab, com fallback para samples
  locais quando executado fora do Colab.
- `inventario_separadores_colab.ipynb`: inventaria separadores nos Parquets
  completos do Drive, gera relatorios read-only e prepara amostra estruturada
  para revisao por IA antes de qualquer limpeza do campo `texto`.
- `diagnostico_separadores_discursos_antigos_colab.ipynb`: diagnostica marcas
  de separacao em discursos antigos, com foco em anos anteriores a 2010 e
  comparacao curta com 2010-2012.

Downloads de amostras gerados no Colab devem ser descompactados localmente em:

```text
data/samples/textos_parlamentares/v1/
```

Depois de descompactar os JSONLs localmente, gere os Parquets das samples com:

```bash
python -m processamento.parquet --profile samples-local --overwrite
```

Para abrir o visualizador local contra os Parquets de samples:

```bash
python -m processamento.visualizador_parquets --profile samples-local
```

Para testar localmente o inventario de separadores contra os Parquets de
samples:

```bash
python -m processamento.inventario_separadores --profile samples-local --overwrite
```
