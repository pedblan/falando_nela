# Validação — snapshot de discursos v2

Status: **schema aprovado — smoke validado localmente; execução real pendente**.

## Gate de entrada

A validação não começa sem:

1. baseline exploratório do Drive registrado, sem exigir saneamento dos
   manifests legados;
2. fontes canônicas identificadas;
3. D03, D04 e D05 aprovadas;
4. schema e definição de “discurso” aprovados.

O censo anterior a esse gate pode ser executado para produzir a evidência das
etapas 2–4. Ele não cria `snapshot_id` e deve permanecer em
`scientific_gate=needs_review`.

## Evidência local do censo

- módulo:
  [`../../../processamento/censo_snapshot_v2.py`](../../../processamento/censo_snapshot_v2.py);
- notebook:
  [`../../../notebooks/dados/01_censo_bases_snapshot_v2_colab.ipynb`](../../../notebooks/dados/01_censo_bases_snapshot_v2_colab.ipynb);
- testes do módulo:
  [`../../../tests/test_censo_snapshot_v2.py`](../../../tests/test_censo_snapshot_v2.py);
- testes do notebook:
  [`../../../tests/test_snapshot_census_colab_notebook.py`](../../../tests/test_snapshot_census_colab_notebook.py).

As fixtures devem demonstrar:

- leitura exclusiva dos três nomes aprovados;
- entradas inalteradas antes e depois;
- recusa de saída dentro da raiz lida;
- recusa de candidato ausente e de `operation_id` reutilizado;
- contagens anuais, cobertura, schema e categorias;
- duplicatas internas e sobreposições exatas entre bases;
- pacote D06 com `snapshot_id=null` e `scientific_gate=needs_review`;
- execução local do notebook com os gates fechados.

## Evidência real do censo

A operação `snapshot-census-20260724t024812z` terminou com `succeeded` e
`needs_review`:

- 428.372 registros em três Parquets;
- 428.372 `texto_id` distintos;
- 0 IDs ausentes;
- 0 duplicatas internas;
- 0 IDs compartilhados entre bases;
- 428.372 textos disponíveis;
- 420.368 autores disponíveis;
- 0 achados estruturais agregados;
- período observado de `1900-01-01` a `2026-07-08`.

D04 exclui do snapshot, de forma auditável, datas anteriores a `2010-01-01` e
posteriores a `2026-07-13`. Nenhum registro é removido das fontes processadas.

## Validação do schema proposto

O schema
[`schema/snapshot_discursos_v2.record.schema.json`](schema/snapshot_discursos_v2.record.schema.json)
deve:

- validar como JSON Schema Draft 2020-12;
- aceitar registros das três bases aprovadas;
- rejeitar datas fora de D04;
- rejeitar texto ou `texto_id` vazio;
- rejeitar arquivos de entrada fora de D03;
- exigir ao menos um ponteiro de proveniência.

## Evidência local do smoke

- módulo:
  [`../../../processamento/snapshot_discursos_v2.py`](../../../processamento/snapshot_discursos_v2.py);
- notebook:
  [`../../../notebooks/dados/02_snapshot_discursos_v2_smoke_colab.ipynb`](../../../notebooks/dados/02_snapshot_discursos_v2_smoke_colab.ipynb);
- testes do módulo:
  [`../../../tests/test_snapshot_discursos_v2.py`](../../../tests/test_snapshot_discursos_v2.py);
- testes do notebook:
  [`../../../tests/test_snapshot_v2_smoke_colab_notebook.py`](../../../tests/test_snapshot_v2_smoke_colab_notebook.py).

O smoke deve demonstrar:

- leitura exclusiva dos três Parquets aprovados;
- entradas inalteradas antes e depois;
- amostra determinística de até 20 elegíveis e 20 excluídos por base;
- corte inclusivo de `2010-01-01` a `2026-07-13`;
- preservação e sinalização de autoria ausente;
- parada por ID duplicado, ID vazio, texto vazio ou proveniência ausente;
- `data` como `date32`, todos os campos do schema e flags ordenadas;
- reconciliação integral das datas por base;
- saídas somente em `/content`, com `scientific_gate=needs_review`;
- notebook executável localmente com montagem e smoke fechados.

Os hashes integrais dos três Parquets não são calculados no smoke. Eles
permanecem obrigatórios antes de uma execução integral promotível.

## Validações estruturais

- schema, tipos e nulabilidade;
- unicidade do ID do discurso;
- presença de proveniência;
- datas parseáveis e regra de corte;
- textos vazios, muito curtos ou anormalmente longos;
- chaves originais ausentes;
- integridade dos hashes e arquivos;
- leitura independente do Parquet.

## Reconciliação de contagens

Para cada fonte e etapa:

```text
entrada
- exclusões aprovadas
- duplicatas comprovadas
= saída
```

Cada termo deve ter tabela de registros correspondente. O total geral não
substitui a reconciliação por fonte, arena e ano.

## Validação de duplicidade

- testar colisões de IDs;
- separar igualdade exata, equivalência normalizada e similaridade;
- revisar amostra de pares removidos;
- manter pares ambíguos no snapshot com sinalização;
- medir o efeito da regra D05 por fonte.

## Comparação com o snapshot anterior

O relatório deve explicar:

- registros presentes apenas em v1;
- registros presentes apenas em v2;
- mudança por fonte, arena e ano;
- alteração causada por corte temporal;
- alteração causada por fonte adicionada ou removida;
- alteração causada por correção de regra;
- diferenças em qualquer subconjunto histórico, sempre pelas mesmas dimensões
  de fonte, arena, base, período e unidade, sem privilegiar um total anterior.

## Testes de aceitação

1. Uma linha escolhida ao acaso pode ser rastreada até a fonte.
2. Toda queda de contagem tem regra, motivo e lista de registros.
3. Nenhum campo da análise v1 influencia a inclusão.
4. Reexecução com as mesmas entradas e versão produz os mesmos IDs, contagens
   e conteúdo.
5. O pesquisador aprova o relatório de cobertura antes de o snapshot receber
   status `approved`.

## Matriz de rastreabilidade

| Requisito | Evidência principal |
|---|---|
| SNP-R01, SNP-R02 | lista de fontes aprovada e inspeção das entradas |
| SNP-R03 | coexistência íntegra dos snapshots anterior e v2 |
| SNP-R04, SNP-R07 | definição da unidade e schema aprovados |
| SNP-R05, SNP-R06 | testes de ID e rastreamento até a origem |
| SNP-R08 | contagens e tabelas de registros por regra |
| SNP-R09 | amostra revisada das duplicatas removidas |
| SNP-R10 | inspeção das colunas e regras de inclusão |
| SNP-R11, SNP-R12 | relatórios de datas e textos problemáticos |
| SNP-R13 | manifest, hashes, commit e versão da spec |
| SNP-R14 | relatório de cobertura por dimensão |
| SNP-R15 | comparação explicada com o snapshot anterior |
| SNP-R16 | IDs distintos para snapshot e análise |

## Condições de reprovação

- universo ou corte implícito;
- diferença não reconciliada;
- exclusão silenciosa;
- duplicata removida apenas por similaridade;
- ID instável;
- proveniência quebrada;
- sobrescrita do snapshot anterior.
