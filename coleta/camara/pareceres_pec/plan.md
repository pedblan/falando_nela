# Plano: pareceres de PEC na Camara

## Fonte

- Portal: Dados Abertos da Camara dos Deputados.
- Descoberta de PECs: `GET /api/v2/proposicoes?siglaTipo=PEC`.
- Detalhe da proposicao: `GET /api/v2/proposicoes/{id}`.
- Tramitacoes: `GET /api/v2/proposicoes/{id}/tramitacoes`.
- Texto do parecer: download da URL oficial informada na tramitacao filtrada.

## Escopo

O alvo analitico nao e o texto-base da PEC. O alvo e cada documento oficial de parecer associado a tramitacao de PEC no Plenario ou na Comissao de Constituicao e Justica.

Como uma PEC pode ter varios pareceres, votos em separado, parecer vencedor, relatorio vencido convertido em voto em separado e versoes documentais, cada tramitacao com documento oficial deve gerar uma linha propria. O coletor nao deve deduplicar por PEC.

A Camara nao oferece a mesma taxonomia documental do Senado para pareceres. O ponto de coleta e a tramitacao, cuja representacao e provisoria na propria API, combinando `descricaoTramitacao`, `codTipoTramitacao`, `despacho`, `siglaOrgao`, `uriOrgao` e `url`. Portanto, a especificacao deve tratar o tipo do documento como classificacao derivada da tramitacao e do texto descritivo, nao como campo nativo equivalente a `siglaTipo` do Senado.

## Filtros

- Proposicao: `siglaTipo=PEC`.
- Orgao da tramitacao:
  - `PLEN`: `ambito=plenario`.
  - `CCJC` e historico `CCJR`: `ambito=ccj`.
  - Comissoes especiais de PEC com sigla dinamica, como `PEC17193`, devem ser preservadas com `ambito=comissao_especial` quando o documento for claramente parecer, voto em separado ou complementacao de voto. Esse ambito nao substitui `ccj` ou `plenario`, mas evita perder o parecer de merito das PECs na Camara.
- Conteudo da tramitacao:
  - Incluir `descricaoTramitacao`, `despacho`, `descricaoSituacao` ou `regime` contendo `parecer`.
  - Incluir codigos de parecer e correlatos: `322` parecer do relator, `323` parecer do relator sobre emendas, `324` manifestacao, `325` parcial, `326` revisao, `327` relator do vencedor, `328` relator parcial, `330` leitura/publicacao de parecer, `335` rejeicao do parecer, `336` aprovacao do parecer, `431` voto em separado e `1040` ratificacao de parecer quando houver URL ou despacho de parecer.
  - Incluir expressoes como `parecer vencedor`, `parecer reformulado`, `complementacao de voto`, `voto em separado`, `relator do vencedor`, `parecer do relator` e `parecer proferido`.
  - Excluir requerimentos e atos de criacao de comissao mesmo quando o despacho mencionar "proferir parecer".
- Documento: tramitacao com `url` ou `urlDocumento`.
- `documento_classe` derivado:
  - `parecer`: parecer do relator, parecer vencedor, parecer reformulado, parecer de redacao e parecer proferido.
  - `voto_em_separado`: voto em separado e documentos equivalentes de divergencia.
  - `relatorio`: usar apenas quando o texto da tramitacao ou documento indicar relatorio.
- `status_deliberativo` derivado:
  - `vencedor`: quando houver `parecer vencedor`, `relator do vencedor` ou documento equivalente.
  - `vencido`: quando a tramitacao disser que o parecer original passou a constituir voto em separado, ou quando o documento/descricao indicar vencido.
  - `aprovado` ou `rejeitado`: quando a tramitacao indicar aprovacao/rejeicao do parecer.
  - `proposto`: parecer ou voto apresentado sem desfecho claro.
  - `indeterminado`: quando a fonte nao permitir inferencia segura.

## Fluxo

- Particionar o periodo por mes.
- Para cada particao, listar PECs com atividade no periodo pela API da Camara.
- Gravar a pagina de descoberta em `metadata/{run_id}.jsonl`.
- Para cada PEC, baixar detalhe e tramitacoes.
- Gravar detalhe e tramitacoes brutas em `metadata/{run_id}.jsonl`.
- Filtrar tramitacoes de parecer, voto em separado e parecer vencedor em `PLEN`, `CCJC`, `CCJR` ou comissao especial de PEC.
- Derivar `documento_classe`, `status_deliberativo` e um indicador booleano `vencido`.
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
], check=False)
```

Para smoke test no Colab ou local:

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.camara.pareceres_pec.collect",
    "--mode", "dev",
    "--sample-limit", "2",
    "--run-id", "smoke-camara-pareceres-pec",
], check=False)
```

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de proposicao, tramitacao, documento ou particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular registros existentes.
