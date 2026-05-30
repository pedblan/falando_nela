# Plano: discursos do Plenario do Senado

## Objetivo

Coletar pronunciamentos do Plenario do Senado Federal como unidade textual analitica. A lista mensal de discursos serve apenas para descobrir `CodigoPronunciamento` e metadados de contexto; o corpus bruto deve ser formado por registros com texto integral baixado do endpoint oficial por pronunciamento.

## Fonte

- Portal: Dados Abertos Legislativos do Senado Federal.
- Casa: Senado Federal, `siglaCasa=SF`.
- Descoberta mensal: `GET /dadosabertos/plenario/lista/discursos/{dataInicio}/{dataFim}.json`.
- Texto integral por pronunciamento: `GET /dadosabertos/discurso/texto-integral/{codigoPronunciamento}`.
- Fallback textual por sessao: `GET /dadosabertos/taquigrafia/notas/sessao/{codigoSessao}.json`.
- Fonte candidata para transcricao futura: `GET /dadosabertos/taquigrafia/videos/sessao/{codigoSessao}` e URLs de video/binario presentes no payload de descoberta.

## Unidade de Coleta

- Unidade de descoberta: lista mensal de sessoes e pronunciamentos.
- Unidade de corpus: um `pronunciamento_texto` por `CodigoPronunciamento`.
- Unidade de fallback futuro: uma entrada `transcription_queue` por pronunciamento sem texto oficial aproveitavel e com fonte candidata de video/audio/binario.

`metadata.pronunciamento.TextoIntegral`, quando existir no payload de descoberta, pode ser uma URL original da fonte. Esse campo bruto nao e a coluna textual canonica. O texto efetivo deve estar em `payload.TextoIntegral` e `payload.texto` no registro `pronunciamento_texto`.

## Fluxo

1. Particionar o periodo por mes.
2. Para cada particao, requisitar a lista mensal de discursos com `siglaCasa=SF` e `v=4`.
3. Gravar essa lista como `record_type=discursos_periodo_metadata` em `data/raw/senado/plenario_discursos/metadata/{run_id}.jsonl`.
4. Extrair de cada pronunciamento:
   - `CodigoPronunciamento`;
   - metadados da sessao;
   - metadados do pronunciamento;
   - URLs oficiais ou candidatas, incluindo `TextoIntegralTxt`, `TextoIntegral`, `UrlTextoBinario`, video e notas da sessao.
5. Para cada `CodigoPronunciamento`, baixar o texto em `GET /dadosabertos/discurso/texto-integral/{codigoPronunciamento}` usando `OpenDataClient.get_text()`.
6. Se o endpoint por pronunciamento devolver texto nao vazio, gravar `pronunciamento_texto` com `forma=texto`, `metodo_obtencao=api_texto_integral` e `texto_status=disponivel`.
7. Se o endpoint por pronunciamento falhar ou vier vazio, tentar notas/texto da sessao.
8. Se o fallback de sessao devolver texto, gravar `pronunciamento_texto` com `forma=texto`, `metodo_obtencao=api_notas_sessao` e `tentativas_texto`.
9. Se nao houver texto oficial, gravar o registro com `texto=null`, `TextoIntegral=null`, `forma=video`, `metodo_obtencao=pendente_transcricao_video` e, quando houver fonte candidata, tambem gravar em `transcription_queue/{run_id}.jsonl`.
10. Marcar a particao como concluida somente depois de processar os pronunciamentos selecionados.

## Saidas

- `data/raw/senado/plenario_discursos/metadata/{run_id}.jsonl`: listas mensais brutas, somente `discursos_periodo_metadata`.
- `data/raw/senado/plenario_discursos/ano=YYYY/mes=MM/{run_id}.jsonl`: corpus bruto, somente `pronunciamento_texto`.
- `data/raw/senado/plenario_discursos/transcription_queue/{run_id}.jsonl`: candidatos a transcricao futura.
- `data/checkpoints/senado/plenario_discursos.json`: particoes mensais concluidas.
- `data/logs/{run_id}.jsonl`: eventos estruturados da execucao.
- `data/manifests/{run_id}.json`: resumo auditavel de contagens, modo, periodo e amostra.

## Otimizacao historica

- O backfill de `1900-01-01` pode consultar o endpoint de lista por ano como
  preflight antes de abrir em meses.
- Anos sem `Pronunciamento` podem ser registrados em `metadata/` e marcados no
  checkpoint sem disparar 12 consultas mensais vazias.
- Anos com retorno podem ser expandidos para trimestres como segundo preflight.
  Trimestres vazios param ali; trimestres positivos ou inconclusivos abrem
  meses.
- Requisicoes anuais ou trimestrais nunca devem ser gravadas no corpus
  `ano=YYYY/mes=MM/`; elas sao somente descoberta em `metadata/`, porque podem
  misturar meses diferentes.
- So requisicoes mensais podem gerar `pronunciamento_texto`; se a resposta
  anual ou trimestral for grande, incompleta ou instavel, a coleta deve cair
  para janelas menores sem alterar os IDs deterministas dos pronunciamentos.

## Dev e Producao

- `dev`: default. Usa amostra, grava em `data/dev` e aplica `--sample-limit 5` por default.
- `prod`: coleta completa, exige destino externo via `--output-dir` ou `FALANDO_NELA_DATA_ROOT`, e nao deve gravar dentro do repo.
- `--sample-limit N` limita o numero de textos baixados na execucao, nao o tamanho da lista mensal salva em `metadata/`.
- Em uma execucao dev com `--sample-limit 2`, a expectativa normal e 1 requisicao de lista mensal mais 2 requisicoes ao endpoint de texto integral, salvo fallback/erro.

## Exemplo Colab

Assume que o Drive ja foi montado e que `FALANDO_NELA_DATA_ROOT` aponta para `/content/drive/MyDrive/falando_nela/data`.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.senado.plenario_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-plenario",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=False)
```

Em notebooks de orquestracao, use `check=False` para que uma falha registrada pelo coletor nao interrompa o restante do fluxo.

## Resiliencia operacional

- Imprimir progresso minimo no stdout para acompanhamento no Colab.
- Gravar JSONL linha a linha, checkpoint e `manifest.autosave.json` durante a execucao.
- Capturar falhas de pronunciamento ou particao com `try/except`, registrar log estruturado e continuar quando possivel.
- Em `--resume`, ler progresso ja gravado no mesmo `run_id` e pular pronunciamentos existentes.

## Fora do Escopo Atual

- Nao executar Whisper, ffmpeg ou transcricao de video nesta etapa.
- Nao raspar HTML se o endpoint oficial de texto integral entregar conteudo valido.
- Nao tratar `Resumo`, `Indexacao`, publicacoes ou URLs como substitutos do texto integral.
