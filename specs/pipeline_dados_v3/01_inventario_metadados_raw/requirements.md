# Requisitos — inventário de metadados raw

## Estado

Contrato aprovado. Implementação autorizada; execução integral depende do
smoke e de sua revisão.

## Objetivo

Descrever de maneira completa e neutra os metadados recebidos nas coletas,
antes de definir categorias normalizadas, regras de correspondência ou
tratamento textual.

## Raiz

```text
/content/drive/MyDrive/falando_nela/data/raw
```

A raiz será lida recursivamente e nunca alterada.

## Universo esperado

O inventário deve detectar o universo real, sem se limitar à lista abaixo.
São esperadas ao menos estas coleções:

- `camara/plenario_discursos`;
- `camara/plenario_apartes`;
- `camara/parlamentares`;
- `camara/pareceres_pec`;
- `camara/ccjc_eventos`;
- `senado/plenario_discursos`;
- `senado/congresso_discursos`;
- `senado/plenario_apartes`;
- `senado/parlamentares`;
- `senado/pareceres_pec`;
- `senado/ccj_notas`.

Nenhum filtro temporal será aplicado.

## Unidade de observação

O inventário distinguirá:

- item do sistema de arquivos;
- registro estruturado;
- caminho de campo dentro do registro;
- valor escalar observado.

As contagens dessas unidades nunca poderão ser misturadas.

## Definição operacional de metadado

Nesta etapa, “metadado” significa todo campo estruturado recebido ou produzido
pelo coletor para descrever identidade, origem, evento, participante,
documento, data, proveniência ou estado operacional do registro.

O inventário não decidirá sozinho se um campo textual é conteúdo parlamentar,
cabeçalho ou metadado. Ele registrará o caminho do campo de forma neutra. A
classificação semântica ocorrerá somente depois da revisão humana.

## Requisitos funcionais

### Catálogo de arquivos

Para cada descendente da raiz, registrar:

- caminho relativo;
- tipo de item;
- extensão ou formato aparente;
- tamanho;
- fonte e dataset derivados exclusivamente da posição no diretório;
- partições explícitas no caminho, como `ano=YYYY` e `mes=MM`;
- possibilidade técnica de leitura;
- erro de leitura, se houver.

### Catálogo de campos

Para cada caminho de campo observado em formatos estruturados, registrar:

- fonte;
- dataset;
- tipo de registro ou envelope, quando declarado;
- caminho exato do campo;
- tipos técnicos observados;
- registros em que o campo está presente;
- valores nulos, vazios e não vazios;
- proporção de preenchimento;
- cardinalidade exata ou estimada, com método identificado;
- tamanhos mínimo, mediano e máximo para strings;
- primeira e última partição em que aparece;
- conflito de tipos entre arquivos ou períodos.

Os caminhos usarão uma notação técnica estável:

- `$` representa a raiz do registro;
- `.campo` representa uma chave de objeto;
- `[]` representa qualquer item de uma coleção;
- pontos e barras invertidas pertencentes à chave serão escapados.

A presença será contada por registro, mesmo quando um caminho aparecer várias
vezes dentro de uma coleção. Tipos, comprimentos e frequências de valores
escalares poderão contar as ocorrências internas.

### Valores observados

- Campos escalares de baixa cardinalidade terão tabela de valores e
  frequências.
- O limite que define baixa cardinalidade deverá constar na configuração.
- Campos escalares de alta cardinalidade terão estimativa KMV baseada em
  SHA-256 e amostra pequena, determinística e limitada.
- Objetos e coleções terão presença, estado, tipos e amostras estruturais, mas
  cardinalidade marcada como não aplicável; seu conteúdo será observado pelos
  caminhos descendentes.
- Strings longas não serão copiadas para relatórios ou amostras; serão
  representadas por tamanho e hash.
- O inventário não fará equivalência semântica entre valores.

### Ausência

O inventário distinguirá:

- campo não presente;
- valor JSON nulo;
- string vazia;
- coleção vazia;
- valor preenchido.

Nenhum desses estados será convertido em outro.

### Limites de Python

Python poderá:

- percorrer diretórios e partições;
- fazer parse técnico de formatos estruturados;
- enumerar caminhos de campos;
- medir tipos, presença, preenchimento, cardinalidade e tamanho;
- produzir amostras determinísticas.

Python não poderá:

- inferir o significado de um campo pelo texto de seus valores;
- procurar marcadores, separadores ou padrões no conteúdo parlamentar;
- usar regex no texto para classificar estrutura discursiva;
- propor preenchimento para metadados ausentes;
- normalizar categorias nesta etapa.

### GPT

O inventário não chamará GPT-5.6 nem qualquer outro modelo. Os resultados
servirão de entrada humana para a futura especificação das categorias.

## Saídas

Todas as saídas serão temporárias, fora do Drive, até aprovação:

```text
/content/falando_nela_v3_inventory/{operation_id}/
```

Artefatos obrigatórios:

| Artefato | Finalidade |
|---|---|
| `relatorio.md` | mapa humano e próxima decisão |
| `inventario_arquivos.csv` | reconciliação dos itens raw |
| `inventario_campos.csv` | cobertura e tipos por caminho de campo |
| `valores_observados.csv` | frequências de baixa cardinalidade |
| `amostras_campos.jsonl` | exemplos pequenos e determinísticos |
| `inconsistencias.csv` | falhas de leitura e conflitos estruturais |
| `manifest.json` | configuração, contagens e proveniência |

Não haverá log separado quando a execução terminar normalmente. Erros deverão
ser resumidos no manifest e em `inconsistencias.csv`.

## Modos

### Smoke

- Cataloga todos os descendentes da raiz.
- Abre uma amostra determinística e distribuída no caminho ordenado para cada
  combinação `fonte × dataset × formato`.
- Usa `max_files_per_group` positivo.
- Termina com gate `not_evaluated` e não pode aprovar G01.

### Completo

- Seleciona todos os arquivos estruturados suportados.
- Usa `max_files_per_group=null`.
- Termina com gate `needs_review`, mesmo quando a execução sucede.

## Configuração mínima registrada

- `operation_id`;
- commit Git;
- raiz aprovada;
- formatos suportados;
- limite de baixa cardinalidade;
- limite e semente das amostras;
- limite de comprimento copiável;
- limite em bytes para JSON não linear;
- política para cardinalidade exata ou estimada;
- data e ambiente da execução.

## Não objetivos

- Definir o schema v3.
- Criar categorias canônicas.
- Corrigir registros.
- Segmentar textos.
- Identificar oradores ou participantes.
- Enviar dados à OpenAI.
- Escrever no Drive.
