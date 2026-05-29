# Validation: apartes_parlamentares/v1

## Smoke local

```bash
python -m processamento.apartes_parlamentares \
  --mode dev \
  --run-id smoke-apartes-parlamentares-v1 \
  --overwrite
```

## Validacao Colab

```bash
python -m processamento.apartes_parlamentares \
  --mode prod \
  --data-root /content/drive/MyDrive/falando_nela/data \
  --run-id processed-apartes-parlamentares-v1-YYYYMMDD \
  --overwrite
```

## Criterios de aceite

- Gera:
  - `processed/apartes_parlamentares/v1/apartes_parlamentares.jsonl`;
  - `processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet`;
  - `processed/manifests/{run_id}-apartes-parlamentares.json`;
  - auditorias em `processed/audits/apartes_parlamentares/{run_id}/`.
- Cada linha representa uma relacao `aparteante -> discurso/pronunciamento`.
- `aparte_id` e unico e deterministico.
- `source` contem apenas `camara` ou `senado`.
- `ano` e `mes` derivam de `data`.
- `genero` aparece somente quando veio de `parlamentares/v1`.
- Nenhuma linha contem campo textual de aparte.
- Duplicatas de raw runs diferentes nao inflam as contagens.

## Testes com fixtures

- Senado:
  - `Apartes=null` nao gera linha processada, mas entra em contagem de entrada.
  - `Aparte` objeto unico gera uma linha.
  - `Aparte` lista gera uma linha por item.
  - `Orador` ausente gera linha com `match_status` apropriado.
- Camara:
  - HTML com zero resultados nao gera linha processada, mas entra no manifest.
  - HTML com um resultado gera uma linha.
  - HTML com varias paginas gera linhas deduplicadas.
  - Link `TextoHTML.asp` com parametros completos gera `discurso_chave`.
  - Nome de aparteante ambiguo gera `match_status=ambiguous`.

## Relatorios obrigatorios

- `contagens_anuais.csv` contem colunas:
  `source`, `ano`, `aparteante_genero`, `aparteante_partido`,
  `aparteante_uf`, `apartes`.
- `match_status.csv` contem contagens por `source`, `ano` e `match_status`.
- `cobertura_parlamentares.csv` separa cobertura de orador e aparteante.

## Falhas que bloqueiam aceite

- Inferir genero por nome.
- Usar texto integral de discurso para criar apartes por regex nesta etapa.
- Alterar `textos_parlamentares/v1`.
- Inflar contagem anual com duplicatas exatas de pagina ou raw run.
- Falhar quando `parlamentares/v1` estiver ausente; nesse caso, gerar a tabela
  com nomes e `match_status` apropriado.

## Checks manuais recomendados

```bash
python - <<'PY'
import pandas as pd

path = "data/dev/processed/apartes_parlamentares/v1/parquet/apartes_parlamentares.parquet"
df = pd.read_parquet(path)
print(df.groupby(["source", "ano", "aparteante_genero"]).size())
print(df["match_status"].value_counts(dropna=False))
PY
```
