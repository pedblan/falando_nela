# Requirements

## Objetivo

Inventariar separadores, anexos e marcas editoriais nos textos parlamentares
processados, sem alterar o corpus, para orientar uma etapa posterior de limpeza
auditavel do texto integral.

O inventario tambem deve suportar diagnostico especifico dos discursos antigos,
especialmente registros anteriores a `2010-01-01`, porque o backfill historico
pode trazer marcas editoriais e separadores diferentes dos observados no
baseline recente.

## Entrada

- Fonte principal em producao:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

- Fonte local para smoke e desenvolvimento:

```text
data/samples/textos_parlamentares/v1/parquet/
```

- JSONLs `processed` e registros `raw` devem ser usados apenas como fallback ou
  auditoria pontual quando um exemplo do inventario parecer suspeito.

## Saida

- Em producao, gravar relatorios em:

```text
/content/drive/MyDrive/falando_nela/data/processed/audits/separadores/{run_id}/
```

- Em samples locais, gravar relatorios em:

```text
data/samples/textos_parlamentares/v1/audits/separadores/{run_id}/
```

- Arquivos obrigatorios:
  - `separadores_resumo.csv`;
  - `separadores_exemplos.jsonl`;
  - `parenteticos_resumo.csv`;
  - `amostra_ia_textos.jsonl`;
  - `amostra_ia_prompt.md`;
  - `amostra_ia_schema.json`;
  - `manifest.json`.

Para diagnostico de discursos antigos, os relatorios derivados devem ficar em:

```text
/content/drive/MyDrive/falando_nela/data/processed/audits/separadores_antigos/{run_id}/
```

Arquivos esperados:

- `cobertura_discursos_antigos.csv`;
- `separadores_antigos_resumo.csv`;
- `separadores_antigos_exemplos.jsonl`;
- `parenteticos_antigos_resumo.csv`;
- `manifest.json`.

## Classificacao

Cada candidato deve receber uma acao sugerida:

- `hard_cut`: separador forte de anexo, documento agregado ou pronunciamento
  encaminhado que provavelmente deve virar regra de corte.
- `review`: cabecalho ou padrao frequente mas ambiguo, exigindo auditoria antes
  de qualquer corte.
- `keep`: marca taquigrafica ou informacao contextual que deve permanecer no
  texto analitico.

## Regras iniciais

- Classificar como candidatos fortes expressoes como:
  - `ARTIGO A QUE SE REFERE O ORADOR`;
  - `DOCUMENTO A QUE SE REFERE`;
  - `DOCUMENTOS A QUE SE REFERE`;
  - `MATERIA A QUE SE REFERE`;
  - `NOTA A QUE SE REFERE`;
  - `CARTA A QUE SE REFERE`;
  - `TEXTO A QUE SE REFERE`;
  - `SEGUE, NA INTEGRA`;
  - `PRONUNCIAMENTO ENCAMINHADO`.
- No Senado, linhas de `*****` devem ser tratadas como `hard_cut` somente
  quando houver cabecalho estrutural proximo; sem esse contexto, devem ficar em
  `review`.
- Linhas entre parenteses devem ser mantidas por default, inclusive marcas como
  `(Soa a campainha.)`, `(Pausa.)` e `(Intervencao fora do microfone.)`.

## CLI

O comando planejado para Colab e:

```bash
python -m processamento.inventario_separadores \
  --profile colab \
  --run-id separadores-textos-v1-YYYYMMDD \
  --overwrite
```

Opcoes obrigatorias do modulo:

- `--profile colab`;
- `--profile samples-local`;
- `--parquet-root`;
- `--output-root`;
- `--dataset source/dataset`, repetivel;
- `--context-chars`, com default `280`;
- `--max-examples-per-separator`, com default `25`;
- `--ai-sample-rate`, com default `0.001`;
- `--ai-sample-min-per-stratum`, com default `1`;
- `--ai-sample-max-chars`, com default operacional para limitar custo de
  revisao por IA;
- `--no-ai-sample`, para desativar a geracao dos insumos de IA;
- `--overwrite`.

## Amostra para IA

- A amostra deve ser estratificada por `source/dataset/ano`.
- O tamanho padrao deve ser 0,1% dos textos de cada estrato, com minimo de 1
  texto quando o estrato tiver registros textuais.
- A selecao deve ser deterministica para permitir reproducibilidade.
- Textos muito longos podem ser truncados para reduzir custo, preservando inicio
  e fim do texto e marcando `texto_truncado = true`.
- O prompt deve pedir resposta JSON conforme `amostra_ia_schema.json`, incluindo
  `texto_id`, `tem_bloco_agregado`, `precisa_texto_completo`, lista de
  separadores com `acao_sugerida`, `confianca` e `motivo`, alem de politica
  para parenteses taquigraficos.

## Caderno operacional

Manter o notebook:

```text
notebooks/processamento/inventario_separadores_colab.ipynb
```

O notebook deve montar o Drive, preparar o repositorio, instalar dependencias,
conferir Parquets, executar o CLI, abrir os relatorios e deixar claro que a
etapa e read-only.

Manter tambem o notebook:

```text
notebooks/processamento/diagnostico_separadores_discursos_antigos_colab.ipynb
```

Esse caderno deve focar `senado/plenario_discursos`,
`senado/congresso_discursos` e `camara/plenario_discursos`, filtrar por anos
anteriores a 2010 como faixa principal, incluir `2010-2012` como referencia
comparativa curta, comparar cobertura por ano e salvar exemplos com contexto
para revisao manual dos separadores historicos.
