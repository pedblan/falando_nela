# Validation: apartes_parlamentares/v1

## Smoke Local

```bash
python -m processamento.apartes_parlamentares \
  --mode dev \
  --run-id smoke-apartes-parlamentares-v1 \
  --overwrite
```

Para limitar a leitura durante validacoes:

```bash
python -m processamento.apartes_parlamentares \
  --mode dev \
  --source senado \
  --limit-records 100 \
  --run-id smoke-apartes-parlamentares-v1-senado \
  --overwrite
```

## Validacao Colab

Use:

```text
notebooks/processamento/geracao_apartes_parlamentares_colab.ipynb
```

ou rode diretamente:

```bash
python -m processamento.apartes_parlamentares \
  --mode prod \
  --data-root /content/drive/MyDrive/falando_nela/data \
  --run-id processed-apartes-parlamentares-v1-YYYYMMDD \
  --overwrite
```

## Testes Automatizados

```bash
pytest tests/test_apartes_parlamentares_processamento.py tests/test_plenario_apartes.py -q
```

Os testes devem cobrir:

- Senado:
  - probes anuais/trimestrais nao viram linhas;
  - `Aparte` objeto unico gera uma linha;
  - `Aparte` lista gera uma linha por item;
  - duplicatas geram `duplicate_aparte_id`;
  - genero vem de `parlamentares/v1`.
- Camara:
  - probes anuais/trimestrais nao viram linhas;
  - pagina mensal com resultado gera linha;
  - `TextoHTML.asp` com parametros completos gera `discurso_chave`;
  - nome de aparteante ambiguo gera `match_status=ambiguous`;
  - ausencia de ID preserva `aparteante_nome`.

## Criterios De Aceite

- Gera:
  - `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`;
  - `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`;
  - `processed/manifests/{run_id}-apartes-parlamentares.json`;
  - auditorias em `processed/audits/apartes_parlamentares/{run_id}/`.
- Cada linha representa uma relacao `aparteante -> discurso/pronunciamento`.
- `aparte_id` e unico e deterministico.
- `source` contem apenas `camara` ou `senado`.
- `ano` e `mes` derivam de `data` quando `data` existe.
- `genero` aparece somente quando veio de `parlamentares/v1`.
- Nenhuma linha contem campo textual de aparte ou campo `texto`.
- Probes anuais/trimestrais aparecem no manifest, mas nao inflam a tabela.
- Duplicatas de raw runs diferentes nao inflam as contagens.

## Relatorios Obrigatorios

- `contagens_anuais.csv` contem colunas:
  `source`, `ano`, `aparteante_genero`, `aparteante_partido`,
  `aparteante_uf`, `apartes`.
- `match_status.csv` contem contagens por `source`, `ano` e `match_status`.
- `cobertura_parlamentares.csv` separa cobertura de orador e aparteante.

## Falhas Que Bloqueiam Aceite

- Inferir genero por nome.
- Usar texto integral de discurso para criar apartes por regex nesta etapa.
- Alterar `textos_parlamentares/v1`.
- Criar linhas a partir de probes anuais ou trimestrais.
- Inflar contagem anual com duplicatas exatas de pagina ou raw run.
- Falhar quando `parlamentares/v1` estiver ausente; nesse caso, gerar a tabela
  com nomes e `match_status` apropriado.

## Checks Manuais Recomendados

```bash
python - <<'PY'
import pandas as pd

path = "data/dev/processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet"
df = pd.read_parquet(path)
print(df.groupby(["source", "ano", "aparteante_genero"]).size())
print(df["match_status"].value_counts(dropna=False))
print(df.columns.tolist())
PY
```
