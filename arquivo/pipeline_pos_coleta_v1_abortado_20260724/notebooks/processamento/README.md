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
- A suíte comparativa v1 foi arquivada. Novos cadernos analíticos só serão
  criados depois do inventário e do snapshot v2, sempre consumindo estes
  produtos em modo somente leitura.

Arquivos atuais:

O antigo caderno
`07_derivados_backfill_discursos_senadores_por_codigo_colab.ipynb` foi
arquivado com o snapshot v1 em
`notebooks/arquivo/analise_plenario_v1_abortada_20260723/`.

- `06_processamento_validacao_atualizacao_colab.ipynb`: bloqueia derivados ate
  todas as faixas obrigatorias do ciclo `20260713` estarem completas ou
  possuirem adiamento exato e auditado. Registra separadamente o run historico
  da Camara retirado do escopo incremental, sem chama-lo de concluido.
  Distingue o gate aceito do gate estrito, regenera a fotografia `current`,
  produz os sete Parquets, apartes, auditorias e amostras, arquiva a cobertura
  efetiva e abre o visualizador Gradio.

- `normalizacao_armazenamento_colab.ipynb`: executa
  `processed/textos_parlamentares/v1` a partir do `raw/` no Google Drive.
- `geracao_parquets_colab.ipynb`: gera Parquets unificados por base a partir dos
  JSONLs processed ja existentes no Drive, sem rerodar a normalizacao.
- `geracao_apartes_parlamentares_colab.ipynb`: gera
  `processed/apartes_parlamentares/v1` e o Parquet
  `apartes_parlamentares.parquet` a partir dos raws metadata-only de apartes do
  Senado e da Camara, com auditorias anuais e validacao de schema.
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

Esse comando e apenas para `textos_parlamentares/v1`. Para apartes, use:

```bash
python -m processamento.apartes_parlamentares --mode dev --overwrite
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
