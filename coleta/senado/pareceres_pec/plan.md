# Plano: pareceres de PEC no Senado

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Descoberta de PECs: `GET /dadosabertos/processo`.
- Parametros principais: `sigla=PEC`, `dataInicioApresentacao`, `dataFimApresentacao`, `v=1`.
- Documentos do processo: `GET /dadosabertos/processo/documento?idProcesso={idProcesso}&v=1`.
- Texto do parecer: download do `urlDocumento` oficial de cada documento filtrado.

## Escopo

O alvo analitico nao e o texto-base da PEC. O alvo e cada documento de parecer ou relatorio legislativo de PEC no Plenario ou na Comissao de Constituicao, Justica e Cidadania.

Como uma PEC pode ter mais de um parecer, relatorio, avulso ou versao documental, cada documento oficial filtrado deve gerar uma linha propria. O coletor nao deve deduplicar por PEC, numero ou ementa.

## Filtros

- Tipo documental: `PARECER`, `RELATORIO` ou `AVULSO_PARECER`.
- Excluir listagens administrativas, como `LISTAGEM_RELATORIO`.
- Colegiado alvo:
  - `CCJ` ou nome contendo `Constituicao`: `ambito=ccj`.
  - `PLEN`/`PLENARIO` ou nome contendo `Plenario`: `ambito=plenario`.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, listar processos `PEC` apresentados no periodo.
- Gravar a lista bruta em `metadata/{run_id}.jsonl`.
- Para cada processo, listar documentos oficiais do processo.
- Gravar a lista bruta de documentos em `metadata/{run_id}.jsonl`.
- Filtrar documentos de parecer/relatorio em `ccj` ou `plenario`.
- Baixar o documento oficial apontado por `urlDocumento`.
- Extrair texto de PDF, HTML ou texto simples quando possivel.
- Gravar uma linha textual consolidada por documento em `ano=YYYY/mes=MM/{run_id}.jsonl`.

## Saidas

- `data/raw/senado/pareceres_pec/metadata/{run_id}.jsonl`: processos e documentos brutos.
- `data/raw/senado/pareceres_pec/ano=YYYY/mes=MM/{run_id}.jsonl`: pareceres com texto extraido.
- `data/checkpoints/senado/pareceres_pec.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Colab

Depois de montar o Drive e clonar o repositorio:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.pareceres_pec.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-pareceres-pec",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```

Para smoke test no Colab ou local:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.pareceres_pec.collect",
    "--mode", "dev",
    "--sample-limit", "2",
    "--run-id", "smoke-senado-pareceres-pec",
], check=True)
```
