# Validation

## Checks obrigatorios

- `pytest` deve passar depois da implementacao do modulo.
- O CLI deve rodar contra Parquets sinteticos pequenos sem depender do Google
  Drive.
- A execucao deve gerar:
  - `separadores_resumo.csv`;
  - `separadores_exemplos.jsonl`;
  - `parenteticos_resumo.csv`;
  - `amostra_ia_textos.jsonl`;
  - `amostra_ia_prompt.md`;
  - `amostra_ia_schema.json`;
  - `manifest.json`.
- A etapa deve ser read-only em relacao a `processed/textos_parlamentares/v1`,
  aos Parquets de entrada e ao schema processado.

## Casos de teste

- `ARTIGO A QUE SE REFERE O ORADOR` deve ser classificado como `hard_cut`.
- `DOCUMENTO A QUE SE REFERE` e `DOCUMENTOS A QUE SE REFERE` devem ser
  classificados como `hard_cut`.
- Linha de `*****` no Senado seguida de cabecalho estrutural deve ser
  classificada como `hard_cut`.
- Linha de `*****` sem cabecalho estrutural proximo deve ser classificada como
  `review`.
- Mencoes comuns a `anexo` dentro de frases nao devem virar `hard_cut`.
- Parenteses taquigraficos como `(Soa a campainha.)`, `(Pausa.)` e
  `(Intervencao fora do microfone.)` devem ser classificados como `keep`.
- A amostra de IA deve conter 0,1% por `source/dataset/ano`, com minimo de 1
  texto por estrato, e ser deterministica.
- O schema de IA deve exigir resposta estruturada com `acao_sugerida` em
  `hard_cut`, `review` ou `keep`.

## Smoke local

Quando houver Parquets de samples, rodar:

```bash
python -m processamento.inventario_separadores \
  --profile samples-local \
  --run-id separadores-smoke-local \
  --overwrite
```

Conferir que a saida fica em:

```text
data/samples/textos_parlamentares/v1/audits/separadores/separadores-smoke-local/
```

## Validacao no Drive

No Colab, rodar:

```bash
python -m processamento.inventario_separadores \
  --profile colab \
  --run-id separadores-textos-v1-YYYYMMDD \
  --overwrite
```

Conferir que a entrada vem de:

```text
/content/drive/MyDrive/falando_nela/data/processed/textos_parlamentares/v1/parquet/
```

Conferir que a saida fica em:

```text
/content/drive/MyDrive/falando_nela/data/processed/audits/separadores/{run_id}/
```

## Validacao do notebook

Validar:

```text
notebooks/processamento/inventario_separadores_colab.ipynb
```

Checks:

- O JSON do notebook e valido.
- Todas as celulas de codigo compilam com `ast.parse`.
- O notebook monta o Drive antes de preparar o repositorio.
- O notebook aponta para os Parquets completos do Drive.
- O notebook executa apenas o inventario e leitura de relatorios.
- O notebook nao executa coleta, normalizacao, geracao de Parquets nem escrita
  fora de `processed/audits/separadores/{run_id}/`.

## Validacao do diagnostico historico

Validar:

```text
notebooks/processamento/diagnostico_separadores_discursos_antigos_colab.ipynb
```

Checks:

- O JSON do notebook e valido.
- Todas as celulas de codigo compilam com `ast.parse`.
- O notebook monta o Drive antes de preparar o repositorio.
- O notebook aponta para os Parquets completos do Drive.
- O filtro default inclui apenas discursos de Plenario/Congresso, com faixa
  historica anterior a 2010 e faixa comparativa `2010-2012`.
- A escrita fica restrita a
  `processed/audits/separadores_antigos/{run_id}/`.
- A saida esperada inclui `cobertura_discursos_antigos.csv`,
  `separadores_antigos_resumo.csv`, `separadores_antigos_exemplos.jsonl`,
  `parenteticos_antigos_resumo.csv` e `manifest.json`.
