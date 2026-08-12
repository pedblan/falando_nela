# Notebooks

## Caderno operacional atual

`primeiro_recorte_discursos.py` é o primeiro caderno Marimo do caminho
cloud-first. Ele consulta, em modo somente leitura, os 30 discursos do Parquet
G03 aprovado. A fonte padrão é o GCS declarado em `config/gcp.toml`.

Para editar localmente, limitado ao próprio Mac:

```bash
uv run --locked --group cloud --group notebooks \
  marimo edit notebooks/primeiro_recorte_discursos.py \
  --host 127.0.0.1 --port 2718
```

Essa execução usa ADC. Testes locais sem credenciais devem selecionar
explicitamente `FALANDO_NELA_G04_SOURCE=fixture` e fornecer
`FALANDO_NELA_G04_FIXTURE`; uma falha na fonte escolhida nunca aciona fallback.
Fixtures devem ser pequenas e não substituem os dados oficiais mantidos na
nuvem.

## Arquivo histórico

Os notebooks Jupyter e Google Colab nas subpastas são preservados como fontes
históricas de decisões, parâmetros e experimentos. Desde R09, eles não são
entrypoints operacionais, não definem o caminho oficial de dados e não devem
ser executados contra o Drive ou fontes parlamentares sem tarefa própria e
revisão de seus contratos.

Código e documentação da última linha Colab permanecem recuperáveis pela tag
`legacy-colab-final`. Referências a `/content/drive`, montagem do Drive ou
comandos antigos devem ser lidas como história, não como instruções atuais.
