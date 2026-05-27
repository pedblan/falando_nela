# Plan

## Tarefa operacional de amanha: inventario de separadores

Tarefa planejada para quarta-feira, 2026-05-27.

- Implementar o CLI `python -m processamento.inventario_separadores`.
- Criar o notebook Colab:

```text
notebooks/processamento/inventario_separadores_colab.ipynb
```

- Rodar o inventario sobre os Parquets completos do Drive e salvar os
  relatorios em:

```text
/content/drive/MyDrive/falando_nela/data/processed/audits/separadores/{run_id}/
```

## Etapa 1: contrato processed v1

- Definir o dataset `textos_parlamentares/v1`.
- Registrar schema versionado em `data/schemas/processed_textos_parlamentares_v1.schema.json`.
- Registrar dicionario de dados em
  `data/schemas/processed_textos_parlamentares_v1.dictionary.md`.
- Manter JSONL particionado por `ano` e `mes` como formato inicial, sem
  adicionar dependencia pesada.

## Etapa 2: normalizador

- Implementar CLI em `python -m processamento.normalizacao`.
- Ler o diretorio `raw/` inteiro ou um subconjunto informado por `--dataset`.
- Normalizar os record types textuais:
  - `pronunciamento_texto`;
  - `discursos_page`;
  - `notas_taquigraficas`;
  - `parecer_pec_texto`.
- Usar metadados de deputados da Camara apenas para enriquecer registros de
  discursos.
- Escrever manifest de execucao em `processed/manifests/`.

## Etapa 2.1: inventario de separadores

- Criar uma rotina read-only para descobrir separadores em todos os Parquets
  completos de `textos_parlamentares/v1`, antes de aplicar qualquer corte
  automatico no campo `texto`.
- Usar os Parquets completos do Drive como fonte principal:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Permitir perfil local contra samples em:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- Gerar relatorios em `processed/audits/separadores/{run_id}/`:
  - `separadores_resumo.csv`;
  - `separadores_exemplos.jsonl`;
  - `parenteticos_resumo.csv`;
  - `amostra_ia_textos.jsonl`;
  - `amostra_ia_prompt.md`;
  - `amostra_ia_schema.json`;
  - `manifest.json`.
- Classificar candidatos como:
  - `hard_cut`: separadores fortes de anexos e documentos agregados;
  - `review`: cabecalhos frequentes mas ambiguos;
  - `keep`: marcas taquigraficas, incluindo linhas entre parenteses.
- Tratar como candidatos de alta prioridade:
  - `ARTIGO A QUE SE REFERE O ORADOR`;
  - `DOCUMENTO A QUE SE REFERE`;
  - linhas de `*****` no Senado quando combinadas com cabecalhos estruturais
    proximos;
  - cabecalhos como `SEGUE, NA INTEGRA` e `PRONUNCIAMENTO ENCAMINHADO`.
- Manter parenteses taquigraficos no texto analitico por default, registrando
  sua frequencia apenas para auditoria.
- Gerar amostra de IA estratificada de 0,1% por `source/dataset/ano`, com
  minimo de 1 texto por estrato, e pedir resposta estruturada segundo schema
  JSON para apoiar a revisao humana dos separadores.

## Etapa 2.2: processamento do texto integral

- Criar um modulo separado da leitura bruta para processar e normalizar o campo
  `texto` antes da analise, preservando a rastreabilidade para o texto oficial
  original via metadados de origem ja existentes.
- Separar o corpo principal de discursos, pronunciamentos e notas
  taquigraficas de blocos anexos, artigos referidos pelo orador, expedientes,
  documentos transcritos e outros conteudos agregados que nao sejam fala ou
  nota principal.
- Usar o inventario de separadores como requisito previo para definir regras de
  corte. Comecar por regras auditaveis de alta confianca, como:

```text
ARTIGO A QUE SE REFERE O ORADOR
```

- Registrar, por texto processado, o metodo aplicado, os separadores
  encontrados, se houve corte e os tamanhos antes/depois da limpeza.
- Manter testes com exemplos sinteticos e reais pequenos para evitar remover
  trechos validos da fala quando o separador aparecer em contexto ordinario.
- Definir se o schema v1 recebera campos novos, como `texto_original`,
  `texto_processado`, `texto_processamento_status` e
  `texto_processamento_metodo`, ou se a mudanca exigira uma versao posterior do
  dataset processado.

## Etapa 3: validacao local

- Testar normalizadores por fonte com registros sinteticos.
- Rodar um smoke em `data/dev`.
- Confirmar que a saida particionada e o manifest sao gerados.
- Confirmar que reexecucoes duplicadas nao inflam a saida.

## Etapa 4: execucao no Drive

- Usar o notebook operacional:

```text
notebooks/processamento/normalizacao_armazenamento_colab.ipynb
```

- O notebook monta o Drive, atualiza o repositorio, instala dependencias e
  chama `normalize_data_root(...)` diretamente em Python.
- Usar `PROCESSED_RUN_ID` para nomear a execucao processada. Esse identificador
  nao precisa coincidir com os `run_id`s brutos.
- Deixar `RAW_RUN_IDS = []` para consolidar todos os JSONLs em `raw/` com
  deduplicacao por `texto_id`. Preencher `RAW_RUN_IDS` apenas se for necessario
  restringir explicitamente quais execucoes brutas entram.
- Alternativamente, em ambientes com terminal, rodar:

```bash
export FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data
python -m processamento.normalizacao --mode prod --run-id processed-textos-v1-YYYYMMDD
```

- Revisar o manifest gerado no Drive.
- Se necessario, repetir com `--dataset fonte/dataset` para isolar problemas.

## Etapa 5: descricao analitica das bases

- Usar o notebook:

```text
notebooks/processamento/descricao_analitica_bases_colab.ipynb
```

- Produzir uma leitura resumida por fonte/dataset/familia textual.
- Conferir cobertura temporal, quantidade de registros, tamanho medio de texto,
  preenchimento de campos-chave e exemplos compactos por base.
- Usar essa descricao para decidir prioridades dos cadernos analiticos e da
  amostragem local.

## Etapa 6: amostras locais

- Criar, depois da validacao de `processed`, uma rotina separada para ZIPs de
  amostras por base.
- Critério inicial: 1% por ano e por familia textual, com minimo operacional a
  definir para anos muito pequenos.
- No Colab, gravar ZIPs em
  `/content/drive/MyDrive/falando_nela/data/processed/downloads/{run_id}/`.
- Depois do download, descompactar localmente em:

```text
data/samples/textos_parlamentares/v1/
```

- Manter os nomes dos JSONLs com base, ano e mes para evitar colisao quando
  varios ZIPs forem descompactados no mesmo diretorio.

## Etapa 7: Parquets unificados por base

- Implementar uma rotina separada da normalizacao principal para converter os
  JSONLs normalizados em Parquet por `source/dataset`.
- A rotina deve aceitar raizes explicitas para entrada e saida, porque os
  arquivos completos no Colab e as amostras locais ficam em diretorios
  diferentes.
- Perfil Colab:

```text
entrada: /content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/
saida:   /content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Perfil samples locais:

```text
entrada: data/samples/textos_parlamentares/v1/
saida:   data/samples/textos_parlamentares/v1/parquet/
```

- Gerar um arquivo por base:
  - `senado__plenario_discursos.parquet`;
  - `senado__congresso_discursos.parquet`;
  - `senado__ccj_notas.parquet`;
  - `senado__pareceres_pec.parquet`;
  - `camara__plenario_discursos.parquet`;
  - `camara__ccjc_eventos.parquet`;
  - `camara__pareceres_pec.parquet`.
- Ler todos os JSONLs abaixo da raiz de entrada, ignorando subdiretorios
  `parquet/`, manifests e arquivos que nao sejam registros processados v1.
- Deduplicar por `texto_id` antes de escrever Parquet, mantendo a mesma
  politica de preferencia do normalizador quando houver duplicatas nos JSONLs.
- Escrever um manifest de conversao em:
  - Colab: `processed/manifests/{run_id}-parquet.json`;
  - samples locais: `data/samples/textos_parlamentares/v1/parquet/manifest.json`.
- Criar e manter o notebook `geracao_parquets_colab.ipynb` para gerar os
  Parquets no Drive sem rerodar ou reabrir notebooks de normalizacao ja
  executados.
- Atualizar o fluxo local para permitir regerar os Parquets a partir dos JSONLs
  descompactados em `data/samples/textos_parlamentares/v1/`.

## Etapa 8: exploracao didatica dos Parquets

- Criar um caderno Colab independente:

```text
notebooks/processamento/exploracao_parquets_colab.ipynb
```

- Criar um caderno local para samples:

```text
notebooks/processamento/exploracao_parquets_samples_local.ipynb
```

- O caderno Colab deve montar o Drive, atualizar o repositorio, instalar
  dependencias e ler diretamente:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- O caderno local deve ler diretamente:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- Ambos devem permitir escolher a base Parquet antes de carregar o `DataFrame`.
- Ambos devem incluir uma primeira passada de EDA basica:
  - lista de Parquets disponiveis;
  - schema/colunas;
  - `df.shape`;
  - `df.head()`;
  - `df.info()`;
  - `df.describe(include="all")`;
  - contagem de nulos;
  - `value_counts()` para campos categoricos relevantes.
- Ambos devem separar uma visao tabular compacta, sem a coluna `texto`, de uma
  visao de texto integral.
- A visao tabular deve usar `itables` quando disponivel, com fallback para
  `IPython.display.display`.
- A visao de texto integral deve permitir selecionar por `texto_id` ou indice,
  mostrar metadados essenciais e imprimir o campo `texto` completo sem
  truncamento.
- Incluir filtros simples por ano, mes, familia textual, parlamentar,
  proposicao, orgao e busca textual para reduzir o conjunto antes de abrir
  textos completos.

## Etapa 9: visualizador Gradio dos Parquets

Tarefa operacional planejada anteriormente para segunda-feira, 2026-05-25;
manter como componente de inspecao read-only dos Parquets.

- Criar um caderno Colab independente:

```text
notebooks/processamento/visualizador_parquets_gradio_colab.ipynb
```

- O caderno deve montar o Drive, atualizar o repositorio, instalar dependencias
  e iniciar um app Gradio com link publico temporario via `share=True`.
- Ler os Parquets diretamente de:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Usar DuckDB ou PyArrow como camada de consulta para evitar carregar a base
  completa em memoria antes dos filtros.
- Interface minima:
  - seletor de base Parquet;
  - filtros por ano, mes, familia textual, unidade analitica, orgao,
    parlamentar, proposicao e busca textual;
  - limite de linhas;
  - tabela compacta sem `texto`;
  - campo para selecionar `texto_id`;
  - painel de metadados;
  - painel de texto integral sem truncamento.
- A tabela deve retornar apenas colunas compactas e linhas limitadas; o texto
  integral deve ser carregado apenas quando um `texto_id` for selecionado.
- Incluir um botao ou acao para limpar filtros.
- O app nao deve escrever no Drive nem rerodar normalizacao, geracao de
  Parquets ou coleta.
- Atualizar `requirements.txt` com dependencias do visualizador, como `gradio`
  e `duckdb`, quando a implementacao for feita.
