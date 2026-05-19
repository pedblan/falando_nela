# Plano: pareceres de PEC no Senado

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Descoberta de PECs: `GET /dadosabertos/processo`.
- Parametros principais: `sigla=PEC`, `dataInicioApresentacao`, `dataFimApresentacao`, `v=1`.
- Documentos do processo: `GET /dadosabertos/processo/documento?idProcesso={idProcesso}&v=1`.
- Texto do parecer: download do `urlDocumento` oficial de cada documento filtrado.

## Escopo

O alvo analitico nao e o texto-base da PEC. O alvo e cada documento de parecer ou relatorio legislativo de PEC no Plenario ou na Comissao de Constituicao, Justica e Cidadania.

Como uma PEC pode ter mais de um parecer, relatorio, avulso, relatorio do vencido ou versao documental, cada documento oficial filtrado deve gerar uma linha propria. O coletor nao deve deduplicar por PEC, numero ou ementa.

O Senado permite uma abordagem baseada em tipo documental, porque `processo/documento` entrega campos como `siglaTipo`, `descricaoTipo`, `descricao`, `siglaColegiadoRecebedor`, `nomeColegiadoRecebedor` e `urlDocumento`. A normalizacao deve preservar esses metadados brutos e derivar apenas campos canonicos para analise comparavel com a Camara.

## Filtros

- Tipo documental principal: `PARECER`, `RELATORIO`, `AVULSO_PARECER` e variantes de parecer como `PARECER_REDACAO`, quando associadas a PEC.
- Excluir listagens administrativas, como `LISTAGEM_RELATORIO`, ainda que o texto contenha a palavra relatorio.
- `documento_classe` derivado:
  - `parecer`: documentos de parecer, inclusive parecer de redacao.
  - `relatorio`: relatorios legislativos, inclusive relatorio do vencido.
  - `avulso_parecer`: avulsos de parecer.
- `status_deliberativo` derivado:
  - `vencido`: quando `descricao`, `identificacao` ou texto do documento indicar relatorio do vencido.
  - `vencedor` ou `aprovado`: quando a identificacao/descritivo indicar parecer vencedor ou parecer aprovado.
  - `proposto`: relatorios/pareceres ainda sem sinal de deliberacao.
  - `indeterminado`: quando a fonte nao permitir inferencia segura.
- Colegiado alvo:
  - `CCJ` ou nome contendo `Constituicao`: `ambito=ccj`.
  - `PLEN`/`PLENARIO` ou nome contendo `Plenario`: `ambito=plenario`.
- Para `AVULSO_PARECER` sem colegiado preenchido, preservar o registro quando houver vinculo claro com a PEC e marcar `ambito=indeterminado` em vez de descartar silenciosamente.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, listar processos `PEC` apresentados no periodo.
- Gravar a lista bruta em `metadata/{run_id}.jsonl`.
- Para cada processo, listar documentos oficiais do processo.
- Gravar a lista bruta de documentos em `metadata/{run_id}.jsonl`.
- Filtrar documentos de parecer/relatorio/avulso em `ccj`, `plenario` ou `indeterminado` quando a propria classe documental justificar preservacao.
- Derivar `documento_classe`, `status_deliberativo` e um indicador booleano `vencido`.
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
], check=False)
```

Para smoke test no Colab ou local:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.pareceres_pec.collect",
    "--mode", "dev",
    "--sample-limit", "2",
    "--run-id", "smoke-senado-pareceres-pec",
], check=False)
```

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de processo, documento ou particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular registros existentes.
