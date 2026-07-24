# Stack técnica — inventário de metadados raw

## Estado

Stack de implementação aprovada. O smoke ainda deverá confirmar quais parsers
são efetivamente usados no raw.

## Ambiente de execução

- Google Colab para ler a raiz completa montada no Drive.
- Python 3, com versão efetiva registrada no manifest.
- Saída temporária sob `/content/falando_nela_v3_inventory/{operation_id}/`.
- Repositório Git como fonte do código e das specs aprovadas.

## Princípios de implementação

- Leitura em streaming sempre que o formato permitir.
- Nenhuma cópia integral do corpus para memória.
- Nenhuma escrita no Drive.
- Ordenação determinística de arquivos, campos, valores e amostras.
- Parsers técnicos por formato; nenhuma interpretação semântica do texto.
- Dependências mínimas, fixadas e registradas somente depois do smoke.

## Matriz preliminar de formatos

| Formato observado | Estratégia permitida |
|---|---|
| JSONL/NDJSON | leitura linha a linha e parse de cada registro |
| JSON | parse do envelope com limite padrão de 64 MiB, registrado no manifest |
| CSV | leitura tabular preservando cabeçalhos e estados vazios |
| Parquet | leitura de schema e batches, se o formato existir no raw |
| arquivo desconhecido | catalogar sem tentar inferir conteúdo |

A tabela é uma política inicial, não a afirmação de que todos esses formatos
existem. O smoke registrará os formatos encontrados e abrirá uma decisão antes
de adicionar qualquer parser ou dependência não prevista.

## Bibliotecas

- Biblioteca padrão do Python para sistema de arquivos, hashing, JSON, CSV,
  contagens e amostragem.
- `pyarrow` será importado somente se um Parquet for observado; sua versão
  efetiva pertence ao ambiente registrado da execução.
- Nenhuma biblioteca de NLP, expressão regular semântica ou cliente da OpenAI
  será usada neste submódulo.

## Representação das saídas

- CSV UTF-8 para catálogos e frequências tabulares.
- JSONL UTF-8 para amostras de campos.
- JSON para o manifest.
- Markdown para o relatório humano.

Campos complexos terão somente resumo estrutural nas amostras. Valores
textuais acima do limite aprovado serão substituídos por comprimento e hash,
nunca truncados de forma que pareçam o valor original completo.

Cardinalidade de escalares será exata até o limite configurado e, depois,
estimada por KMV sobre hashes SHA-256. Cardinalidade de objetos e coleções será
marcada como não aplicável.

## Segurança e privacidade operacional

- Segredos não são necessários.
- Caminhos absolutos locais não serão tratados como identificadores
  científicos.
- Mensagens de erro deverão evitar reproduzir conteúdo textual longo.
- O programa deverá falhar antes de iniciar se a saída estiver dentro do
  Drive ou da raiz raw.

## Valores iniciais do smoke

- até 2 arquivos por `fonte × dataset × formato`;
- baixa cardinalidade: até 100 valores;
- amostra: 5 valores por caminho de campo;
- texto copiável: até 200 caracteres;
- JSON não linear: até 64 MiB;
- cardinalidade exata: até 10.000 valores;
- KMV: 1.024 hashes.

## Decisões que o smoke poderá revisar

- formatos efetivamente suportados;
- biblioteca e estratégia para Parquet, se necessário;
- limiar de baixa cardinalidade;
- comprimento máximo copiável;
- cardinalidade exata ou estimada;
- tamanho e semente das amostras.
