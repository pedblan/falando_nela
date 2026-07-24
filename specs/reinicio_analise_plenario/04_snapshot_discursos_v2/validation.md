# Validação — snapshot de discursos v2

Status: **contrato aprovado em 2026-07-23 — validação ainda não executada**.

## Gate de entrada

A validação não começa sem:

1. inventário do Drive aprovado;
2. fontes canônicas identificadas;
3. D03, D04 e D05 aprovadas;
4. schema e definição de “discurso” aprovados.

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
