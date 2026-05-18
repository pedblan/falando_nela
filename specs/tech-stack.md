# Tech Stack

O projeto sera construido de forma incremental, com prioridade para ferramentas abertas, reprodutiveis e adequadas a pesquisa empirica com dados parlamentares.

## Ambiente

- Python 3.11+ como linguagem principal.
- Jupyter Notebook para exploracao, prototipos e cadernos analiticos.
- Google Colab Pro para tarefas longas, especialmente coletas completas que dependam de conexoes prolongadas.
- Ambiente local usado apenas para prototipos leves, validacao de contratos de dados e uma parcela estratificada dos dados, evitando ocupar espaco com a coleta completa.

## Coleta

A coleta futura usara os portais de dados abertos do Senado Federal, Congresso Nacional e Camara dos Deputados.

O cliente HTTP padrao para o modulo de coleta sera `httpx`, tanto nos prototipos locais quanto nos notebooks preparados para execucao no Colab.

Quando implementado, o modulo de coleta deve prever:

- Parametros explicitos de fonte, periodo e escopo.
- Transferencia prioritaria de texto integral de discurso, sessao ou reuniao, quando a fonte oficial disponibilizar esse conteudo.
- Paginacao nos endpoints que exigirem.
- Retries para falhas temporarias.
- Checkpoints para permitir retomada sem duplicar trabalho.
- Logs suficientes para auditar execucoes locais e no Colab.

## Armazenamento

O armazenamento sera definido por camadas:

- `raw`: respostas ou registros preservados com o minimo de transformacao possivel.
- `processed`: dados normalizados para analise, unificacao de fontes e criacao de cadernos.

Dentro de `raw`, o corpus textual e os metadados de descoberta devem ficar separados:

- `raw/{portal}/{dataset}/ano=YYYY/mes=MM/`: registros textuais consolidados, como pronunciamentos com texto integral.
- `raw/{portal}/{dataset}/metadata/`: listas, paginas de busca, pautas e outros payloads auxiliares usados para localizar os itens textuais.
- `raw/{portal}/{dataset}/transcription_queue/`: itens sem texto oficial e candidatos a transcricao futura.

Os formatos preferenciais serao escolhidos conforme volume e estabilidade dos dados:

- JSONL para registros brutos e append-friendly.
- Parquet para tabelas analiticas maiores.
- DuckDB para consultas locais e consolidacao quando o volume justificar.

A maquina local deve manter apenas uma amostra estratificada suficiente para desenvolvimento, testes e validacao metodologica. Bases completas devem ser geradas e mantidas fora do repositorio local principal, preferencialmente em ambiente Colab ou armazenamento externo apropriado.

## Analise

- pandas ou Polars para manipulacao tabular, conforme tamanho dos dados e ergonomia da etapa.
- Altair como biblioteca principal de visualizacao estatistica.
- Metodos estatisticos e NLP serao adicionados por specs especificas, de acordo com os cadernos por artigo constitucional.

Nenhuma dependencia operacional fica fixada nesta spec inicial; a lista de pacotes deve ser criada apenas quando houver codigo ou notebooks correspondentes.
