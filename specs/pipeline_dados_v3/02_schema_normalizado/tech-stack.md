# Stack técnica — schema normalizado v3

## Estado

Stack aprovada e implementada para produzir as evidências e o contrato de
G02. Os pilotos exploratórios foram executados, e o catálogo global, seu
upload e a contagem exata estão implementados. A execução integral desses
artefatos e a chamada global permanecem sujeitas aos gates do plano; a
aplicação do schema continua bloqueada.

## Ambiente

- Google Colab para a auditoria integral sobre o Drive montado em modo de
  leitura.
- Python 3, com versão efetiva registrada no manifest.
- Repositório Git como fonte das specs e da implementação.
- Saída temporária fora do Drive até a revisão humana.
- Raiz raw em
  `/content/drive/MyDrive/falando_nela/data/raw`, sempre imutável.

O caminho da cópia aprovada de
`raw-metadata-full-20260724t184418z` deverá ser fornecido explicitamente. A
ferramenta falhará se o diretório, o `operation_id` ou os hashes não
corresponderem a G01. O SHA-256 aprovado do próprio `manifest.json` será uma
âncora externa fixada no contrato e na implementação, pois um manifest não
pode autenticar o próprio hash.

## Entradas

- `manifest.json` e os outros seis artefatos do inventário aprovado;
- registros raw legíveis, acessados em streaming para auditoria recorde a
  recorde;
- arquivo declarativo de pares candidatos adicionados por revisão humana;
- arquivo declarativo de regras determinísticas propostas.

Nenhum derivado v1/v2 será carregado como entrada científica.

## Representações

| Artefato | Representação proposta |
|---|---|
| livro de campos e auditorias | CSV UTF-8 com cabeçalho fixo |
| schema lógico | JSON Schema Draft 2020-12 |
| regras e configuração efetiva | JSON fechado e versionado |
| amostras seguras | JSONL com coordenadas e hashes |
| previews textuais de contexto | JSONL separado e limitado |
| catálogo global do modelo | TXT UTF-8 line-oriented, reversível |
| crosswalk do catálogo global | CSV UTF-8 com caminho original integral |
| trilha de amostras do catálogo | CSV UTF-8 |
| recibo de upload e tokens | JSON |
| propostas GPT e trilha de execução | JSONL validado por schema fechado |
| avaliação A/B | CSV UTF-8 |
| manifest | JSON |
| relatório humano | Markdown |

JSON Schema expressará o contrato lógico. O formato físico de tabelas
normalizadas, inclusive eventual Parquet, pertence à etapa que implementar os
adaptadores e não será presumido aqui.

## Python permitido

A implementação usa preferencialmente a biblioteca padrão:

- `csv` e `json` para artefatos;
- `pathlib` para caminhos;
- `hashlib` para integridade, valores indexados e amostras;
- `collections` para contagens;
- `decimal` para cálculo reproduzível de taxas;
- `datetime` apenas em regras de metadados explicitamente aprovadas;
- `dataclasses` e `typing` para contratos internos.

Os parsers de raw deverão ser os formatos efetivamente registrados no
manifest aprovado. `pyarrow` só poderá ser importado se G01 registrar Parquet
entre os arquivos estruturados lidos.

Nenhuma biblioteca adicional será incorporada sem requisito, versão fixada e
registro no manifest.

## Comparação tipada

A igualdade basal de aliases será exata e sensível ao tipo.

Valores serão representados canonicamente para hashing com JSON determinístico:

- chaves de objeto ordenadas;
- separadores estáveis;
- UTF-8;
- tipo técnico mantido;
- nenhuma remoção de espaços dentro de strings;
- nenhuma conversão de maiúsculas, acentos, datas ou números;
- arrays com ordem preservada.

O hash será SHA-256. Um hash igual deverá ser confirmado por igualdade do valor
canônico quando o valor puder ser mantido em memória com segurança.

Objetos e coleções não serão convertidos para string de domínio. A
serialização canônica servirá somente à comparação técnica e ao hash.

## Motor de caminhos e registros

O leitor deverá preservar a notação do inventário:

- `$` para raiz;
- `.campo` para chave de objeto;
- `[]` para ocorrência em coleção;
- escape das chaves conforme o contrato de G01.

Como `[]` não contém índice nem identidade de elemento, o motor de aliases
comparará por padrão o conjunto ordenado de ocorrências do caminho dentro do
mesmo registro, mantendo multiplicidade. Qualquer correspondência entre
elementos de coleções exigirá chave preenchida e regra determinística
aprovada.

Cada leitura produzirá uma coordenada técnica estável com arquivo relativo,
número do registro, fonte, dataset e `record_type`.

## Índices para candidatos a alias

Para evitar comparação quadrática irrestrita, Python poderá construir índices
determinísticos por:

- escopo estrutural;
- chave terminal exata;
- conjunto de tipos técnicos;
- hash de valor tipado preenchido.

Os índices apenas produzem candidatos. Eles não atribuem equivalência.

`senado/ccj_notas` terá processamento em streaming, checkpoints locais
temporários e relatórios por `record_type`. Limites de memória ou tempo deverão
falhar explicitamente; não poderão truncar os 20.523 caminhos ou os 540
conflitos.

## Regras determinísticas

Cada regra futura será dados declarativos, não código arbitrário por campo. O
registro mínimo conterá:

```json
{
  "rule_id": "identificador_estavel",
  "rule_version": "1",
  "source_scope": {
    "source": "observado",
    "dataset": "observado",
    "record_type": "observado",
    "field_path": "$.caminho.observado"
  },
  "input_states": ["filled"],
  "operation": "operacao_aprovada",
  "output_field": "categoria_aprovada",
  "on_error": "preserve_and_report"
}
```

O vocabulário de `operation` será fechado, pequeno, testado e aprovado em G02.
Não incluirá regex semântica, prompt, código executável ou fallback textual.

Esta definição serve para desenhar o contrato. O motor que aplicará regras aos
dados será especificado em `03_adaptadores_fontes` e não será implementado
neste submódulo.

## Segurança textual

- O SDK oficial da OpenAI poderá ser dependência da etapa para o piloto
  GPT-5.6, com versão efetiva fixada no manifest.
- As chamadas usarão a Responses API com Structured Outputs e JSON Schema
  fechado.
- O alias solicitado, o modelo efetivamente resolvido e os parâmetros de
  raciocínio serão registrados.
- A chave será lida de segredo do Colab ou variável de ambiente e nunca será
  gravada no repositório, notebook, artefato ou log.
- Nenhuma biblioteca de NLP, embeddings ou busca aproximada será usada.
- Strings longas em artefatos de auditoria serão substituídas por coordenada,
  tipo, tamanho e hash.
- Os pacotes enviados ao modelo poderão conter valores curtos já classificados
  como metadados e definições das APIs oficiais.
- Conteúdo parlamentar poderá ser lido por Python como bytes/valor para
  transporte, tamanho, hash, seleção estrutural e recorte literal.
- Somente previews aprovados, com até 500 caracteres Unicode e
  `context_only=true`, poderão ser enviados ao modelo em G02.
- O modelo não poderá usar previews como evidência de categoria, coluna,
  preenchimento ou alias.
- Marcadores e estruturas textuais serão reservados aos futuros planos JSON
  declarativos do GPT-5.6.

## Gerador de amostras

Python produzirá dois artefatos independentes:

- `amostras_estruturais.jsonl`, com estrutura completa, metadados curtos e
  textos longos substituídos por descritores;
- `previews_contexto.jsonl`, com os recortes textuais literais, limites,
  hashes, posições e coordenadas.

A seleção será streaming, determinística e configurável. Critérios e
desempates não inspecionarão o significado do texto. O comprimento do preview
será contado em caracteres Unicode conforme `len()` de `str` no Python
registrado no manifest.

Os identificadores terão namespaces distintos, `evidence_id` e `context_id`,
para que o validador impeça o uso acidental de contexto como evidência.

## Cliente GPT-5.6

O piloto usa chamadas síncronas e pequenas. Depois da revisão exploratória, a
definição do vocabulário global usará uma única chamada da Responses API com
`catalogo_global_gpt56.txt` como `input_file`.

O catálogo será enviado pela Files API com `purpose=user_data`. Antes da
geração, `responses.input_tokens.count` receberá exatamente o mesmo modelo,
arquivo, prompt e estrutura de mensagens. A chamada será bloqueada acima de
922.000 tokens de entrada e usará truncamento desabilitado.

O arquivo do modelo será TXT. CSV e XLSX não serão usados como `input_file`
para esta decisão porque o fluxo de planilhas processa apenas uma visão
reduzida das primeiras 1.000 linhas por aba. `File Search` também não será
usado para definir o schema global, pois recuperação por relevância não
garante que todos os caminhos integrem a decisão.

O formato line-oriented terá:

- cabeçalho com a operação G01 e suas contagens vinculantes;
- legenda fechada de tipos técnicos;
- linhas `G` para proveniência repetida por grupo;
- linhas `P` para prefixos de caminho reversíveis;
- exatamente uma linha `F` e um `field_id` por caminho inventariado;
- linhas `S` apenas para amostras seguras marcadas `context_only`;
- linhas `X` para as inconsistências preservadas de G01.

No perfil `schema_core`, cada linha `F` manterá caminho, tipos, fração
`preenchidos/universo`, máscara dos estados presentes, cardinalidade,
comprimento máximo de string e conflito. Contadores completos, `fill_rate`,
mínimo, mediana, partições e demais métricas permanecerão no crosswalk, que
não é enviado ao modelo nessa chamada.

O crosswalk separado preservará o caminho original integral e todas as
métricas, permitindo provar que `P + componente F` reproduz o inventário
exatamente. A compactação não modifica o raw e não interpreta nomes ou
valores.

Batch só poderá ser considerado depois que a proposta global for revisada e o
vocabulário canônico for congelado. Cada linha Batch será tratada como
requisição independente e receberá a mesma versão do schema; Batch aplicará o
vocabulário aos `field_id`, mas nunca será usado para descobri-lo.

As condições A e B serão executadas como pares com o mesmo modelo resolvido,
parâmetros, prompt, JSON Schema e evidências. A condição B acrescentará somente
os previews `context_only`. Ordem do par e identificador de pareamento serão
registrados.

Cada resposta deverá seguir schema fechado para:

- categoria e coluna propostas;
- caminhos de origem e evidências;
- referência à categoria oficial da API, quando houver;
- `evidence_ids` obrigatórios e `context_refs` opcionais;
- operação determinística sugerida;
- possível alias;
- conflitos, ressalvas e evidência insuficiente;
- necessidade de revisão humana.

O consumidor Python validará estrutura, enums e referências. Ele não executará
a proposta nem a converterá automaticamente em regra.

## Determinismo e manifest

Toda execução futura registrará:

- commit Git;
- versão Python e dependências;
- operação G01 e hashes de entrada;
- fingerprint do raw antes e depois;
- configuração e pares candidatos;
- versões de schema e regras;
- contagens por etapa;
- hashes e número de linhas das saídas;
- horário e ambiente;
- estado do gate sempre `needs_review`.

Ordenação de arquivos, chaves, pares e linhas produzidas por Python será
determinística. A mesma entrada e configuração deverão reproduzir os hashes
desses artefatos, exceto campos temporais explicitamente isolados.

Respostas GPT não serão presumidas idênticas entre execuções. A
reprodutibilidade da chamada será garantida pela preservação do modelo
resolvido, parâmetros, prompt, JSON Schema, hashes da entrada e resposta bruta.

## Testes

- `pytest` para unidades de caminho, estados, igualdade tipada, métricas,
  vínculos e regras;
- fixtures sintéticas para conflitos `array|object`;
- fixture específica de coleções aninhadas semelhante à complexidade técnica
  de `senado/ccj_notas`, sem copiar seu conteúdo textual;
- testes da seleção estrutural e dos limites de preview;
- teste que rejeita proposta sustentada somente por `context_id`;
- teste pareado A/B em resposta simulada;
- teste de integração em amostra estratificada;
- testes de resposta GPT válida, referência inexistente, recusa, erro e
  evidência insuficiente;
- execução integral somente em gate separado, depois dos testes locais.

## Checklist técnico

- [x] T02-01 — Aprovar Python 3 e Colab para a auditoria integral.
- [x] T02-02 — Aprovar CSV, JSON, JSONL e Markdown para evidências.
- [x] T02-03 — Aprovar JSON Schema Draft 2020-12 para o contrato lógico.
- [x] T02-04 — Fixar as versões efetivas no manifest da implementação.
- [x] T02-05 — Implementar comparação JSON tipada e exata.
- [x] T02-06 — Implementar cálculo reproduzível das quatro taxas.
- [x] T02-07 — Implementar vínculos determinísticos com detecção de ambiguidade.
- [x] T02-08 — Implementar índices de candidatos sem decisão automática.
- [x] T02-09 — Implementar streaming integral de `senado/ccj_notas`.
- [x] T02-10 — Testar preservação de arrays, objetos, ordem e multiplicidade.
- [x] T02-11 — Aprovar Responses API e Structured Outputs para o piloto GPT-5.6.
- [x] T02-12 — Fixar SDK, modelo resolvido, prompt e JSON Schema no manifest.
- [x] T02-13 — Validar referências das propostas contra o inventário.
- [x] T02-14 — Registrar tokens, latência, custo, erros e recusas.
- [x] T02-15 — Implementar amostras `evidence` com substituição de textos longos.
- [x] T02-16 — Implementar previews limitados e rotulados `context_only`.
- [x] T02-17 — Impedir `context_id` de satisfazer evidência obrigatória.
- [x] T02-18 — Executar e comparar condições A/B pareadas.
- [x] T02-19 — Reproduzir hashes das saídas determinísticas de Python.
- [x] T02-20 — Implementar catálogo TXT global e crosswalk lossless.
- [x] T02-21 — Implementar seleção compacta de amostras `context_only`.
- [x] T02-22 — Implementar reutilização idempotente dos artefatos globais.
- [x] T02-23 — Integrar upload `user_data` e contagem exata de tokens ao caderno.
- [x] T02-24 — Implementar perfil `schema_core` sem remover caminhos ou métricas do crosswalk.
- [ ] T02-25 — Executar a contagem exata com o catálogo `schema_core` integral.
- [ ] T02-26 — Confirmar que a entrada global cabe no máximo de 922.000 tokens.
- [ ] T02-27 — Executar e preservar a proposta global sem aplicação automática.
- [ ] T02-28 — Fixar o schema revisado antes de preparar Batch por `field_id`.

## Dependências proibidas nesta etapa

- bibliotecas de NLP ou embeddings;
- mecanismos de fuzzy matching;
- clientes de modelo diferentes do cliente GPT-5.6 aprovado;
- chamadas de modelo fora do prompt e do JSON Schema versionados;
- previews acima do limite ou sem aprovação humana;
- uso de `context_id` como evidência estrutural;
- execução de código recebido em configuração;
- dependências do pipeline arquivado tratadas como canônicas.
