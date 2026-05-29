# Plan

## Objetivo

Criar uma etapa read-only para inventariar separadores e marcas editoriais nos
textos parlamentares antes de implementar corte automatico no campo `texto`.
O backfill historico exige uma subauditoria dos discursos antigos, porque
marcas de separacao anteriores a 2010 podem seguir padroes diferentes dos
registros recentes.

## Etapa 1: CLI de inventario

- Implementar `python -m processamento.inventario_separadores`.
- Suportar `--profile colab`, `--profile samples-local`, `--parquet-root`,
  `--output-root`, `--dataset`, `--run-id`, `--context-chars`,
  `--max-examples-per-separator` e `--overwrite`.
- Ler apenas colunas necessarias dos Parquets: `texto_id`, `source`, `dataset`,
  `ano`, `mes`, `data`, `documento_tipo`, `unidade_analitica` e `texto`.
- Processar textos em batches com PyArrow para evitar carregar bases grandes
  inteiras em memoria.

## Etapa 2: deteccao de candidatos

- Detectar separadores fortes como `ARTIGO A QUE SE REFERE O ORADOR`,
  `DOCUMENTO A QUE SE REFERE`, `DOCUMENTOS A QUE SE REFERE`, `MATERIA A QUE SE
  REFERE`, `NOTA A QUE SE REFERE`, `CARTA A QUE SE REFERE`, `TEXTO A QUE SE
  REFERE`, `SEGUE, NA INTEGRA` e `PRONUNCIAMENTO ENCAMINHADO`.
- Detectar linhas de asteriscos, especialmente `*****` no Plenario do Senado em
  2011-2012, classificando como separador forte apenas quando houver cabecalho
  estrutural proximo.
- Detectar cabecalhos em caixa alta frequentes e ambiguos como `review`.
- Detectar linhas taquigraficas entre parenteses, como `(Soa a campainha.)`,
  `(Pausa.)` e `(Intervencao fora do microfone.)`, classificando como `keep`.

## Etapa 3: relatorios

- Gravar os resultados em:

```text
processed/audits/separadores/{run_id}/
```

- Gerar:
  - `separadores_resumo.csv`: contagens por base, ano, tipo e separador
    normalizado;
  - `separadores_exemplos.jsonl`: exemplos com `texto_id`, posicao, contexto
    antes/depois e tamanho do bloco posterior;
  - `parenteticos_resumo.csv`: frequencia das marcas entre parenteses;
  - `amostra_ia_textos.jsonl`: amostra deterministica de 0,1% por
    `source/dataset/ano`, com minimo de 1 texto por estrato;
  - `amostra_ia_prompt.md`: instrucoes para rotulagem por IA;
  - `amostra_ia_schema.json`: schema de resposta estruturada para IA;
  - `manifest.json`: parametros, caminhos, arquivos lidos e totais.

## Etapa 4: notebook Colab

- Criar:

```text
notebooks/processamento/inventario_separadores_colab.ipynb
```

- O caderno deve montar o Drive, atualizar o repositorio, instalar
  dependencias, listar Parquets disponiveis, executar o CLI e abrir os
  relatorios principais.
- O caderno nao deve executar coleta, normalizacao, geracao de Parquets nem
  alteracao do schema processado.

## Etapa 5: diagnostico historico de discursos

- Criar:

```text
notebooks/processamento/diagnostico_separadores_discursos_antigos_colab.ipynb
```

- O caderno deve ler os Parquets completos do Drive, filtrar por
  `senado/plenario_discursos`, `senado/congresso_discursos` e
  `camara/plenario_discursos`, usar `ano <= 2009` como faixa historica
  principal e incluir `2010-2012` como referencia comparativa curta.
- Gerar relatorios em `processed/audits/separadores_antigos/{run_id}/` com
  cobertura anual, resumo de separadores, exemplos com contexto e resumo de
  marcas parenteticas.
- Nao executar coleta, normalizacao, Parquet, limpeza textual nem alteracao do
  schema processado.

## Etapa 6: decisao posterior

- Revisar os relatorios antes de criar regras de limpeza.
- Usar a amostra de IA como apoio de auditoria, nao como regra automatica.
- Promover para corte automatico apenas padroes `hard_cut` de alta confianca.
- Manter padroes `review` fora do corte automatico ate auditoria manual.
