# Plano: pareceres de PEC na Camara

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Descoberta de PECs: `GET /api/v2/proposicoes?siglaTipo=PEC`.
- Detalhe da proposicao: `GET /api/v2/proposicoes/{id}`.
- Tramitacoes: `GET /api/v2/proposicoes/{id}/tramitacoes`.
- Texto do parecer: download da URL oficial informada na tramitacao filtrada.

## Escopo

O alvo analitico nao e o texto-base da PEC. O alvo e cada documento oficial de parecer associado a tramitacao de PEC no Plenario ou na Comissao de Constituicao e Justica.

Como uma PEC pode ter varios pareceres e versoes, cada tramitacao com documento oficial deve gerar uma linha propria. O coletor nao deve deduplicar por PEC.

## Filtros

- Proposicao: `siglaTipo=PEC`.
- Orgao da tramitacao:
  - `PLEN`: `ambito=plenario`.
  - `CCJC` e historico `CCJR`: `ambito=ccj`.
- Conteudo da tramitacao: `descricaoTramitacao`, `despacho`, `descricaoSituacao` ou `regime` contendo `parecer`.
- Documento: tramitacao com `url` ou `urlDocumento`.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, listar PECs com atividade no periodo pela API da Camara.
- Gravar a pagina de descoberta em `metadata/{run_id}.jsonl`.
- Para cada PEC, baixar detalhe e tramitacoes.
- Gravar detalhe e tramitacoes brutas em `metadata/{run_id}.jsonl`.
- Filtrar tramitacoes de parecer em `PLEN`, `CCJC` ou `CCJR`.
- Baixar o documento oficial da tramitacao.
- Seguir meta-refresh HTML quando a Camara redirecionar para `imagem.camara.gov.br`.
- Extrair texto de PDF, HTML ou texto simples.
- Gravar uma linha textual consolidada por parecer em `ano=YYYY/mes=MM/{run_id}.jsonl`.

## Saidas

- `data/raw/camara/pareceres_pec/metadata/{run_id}.jsonl`: PECs, detalhes e tramitacoes brutas.
- `data/raw/camara/pareceres_pec/ano=YYYY/mes=MM/{run_id}.jsonl`: pareceres com texto extraido.
- `data/checkpoints/camara/pareceres_pec.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.

## Colab

Depois de montar o Drive e clonar o repositorio:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.pareceres_pec.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-camara-pareceres-pec",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```

Para smoke test no Colab ou local:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.pareceres_pec.collect",
    "--mode", "dev",
    "--sample-limit", "2",
    "--run-id", "smoke-camara-pareceres-pec",
], check=True)
```
