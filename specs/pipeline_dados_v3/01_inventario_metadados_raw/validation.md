# Validação — inventário de metadados raw

## Estado

Contrato cumprido. Execução integral revisada e G01 aprovado em 2026-07-24.

## Pré-condições

- O arquivamento anterior foi concluído.
- A raiz `data/` contém somente `raw/`.
- Não há coletor escrevendo no Drive.
- O commit da execução corresponde às specs aprovadas.

## Testes locais obrigatórios

A implementação futura deverá cobrir ao menos:

- JSONL válido com campos aninhados;
- JSON contendo objeto e lista;
- campos ausentes, nulos, vazios e preenchidos;
- um mesmo campo com tipos conflitantes;
- arquivo vazio;
- linha JSON inválida;
- extensão não suportada;
- campo de baixa cardinalidade;
- campo de alta cardinalidade;
- string longa que não pode aparecer integralmente na saída;
- JSON não linear acima do limite de memória;
- amostra determinística;
- raiz ou `operation_id` inválido;
- tentativa de reutilizar uma saída existente;
- tentativa de gravar sob a raiz do Drive.

## Reconciliações

### Sistema de arquivos

```text
itens catalogados
= arquivos
+ diretórios
```

Cada descendente da raiz deve aparecer exatamente uma vez em
`inventario_arquivos.csv`.

### Registros

Para cada arquivo estruturado:

```text
registros observados
= registros lidos
+ registros rejeitados
```

### Presença de campos

Para cada fonte, dataset e caminho de campo:

```text
registros do universo
= campo ausente
+ campo presente nulo
+ campo presente vazio
+ campo presente preenchido
```

## Invariantes automáticos

- Escritas sob `data/raw`: zero.
- Escritas sob qualquer caminho do Drive: zero.
- Chamadas à OpenAI: zero.
- Caminhos de campos inventados: zero.
- Valores longos copiados integralmente: zero.
- Linhas sem fonte ou dataset: devem ser explicadas como inconsistência.
- Contagens negativas ou proporções fora de `[0, 1]`: zero.
- Amostras com a mesma configuração devem ser idênticas.

## Revisão humana de G01

O relatório deverá permitir responder:

1. Quais fontes e datasets existem realmente?
2. Quais formatos e envelopes foram observados?
3. Quais campos aparecem em cada fonte?
4. Quais campos estão preenchidos e em que períodos?
5. Quais valores têm baixa cardinalidade?
6. Onde existem conflitos de tipo ou significado aparente?
7. Quais campos precisam de leitura humana antes da ontologia?
8. Há algum conjunto raw que ficou fora do inventário?

## Critério de aprovação

G01 só poderá ser aprovado quando:

- o universo de arquivos estiver integralmente reconciliado;
- formatos não suportados estiverem quantificados;
- falhas de parse estiverem localizadas;
- ausência, nulo, vazio e preenchido estiverem separados;
- nenhuma interpretação textual tiver sido realizada;
- o usuário tiver revisado `relatorio.md`, `inventario_campos.csv` e
  `valores_observados.csv`.

O gate permanecerá `needs_review` mesmo quando o programa terminar sem erro.

O smoke permanecerá `not_evaluated`; somente a execução completa poderá abrir
G01.
