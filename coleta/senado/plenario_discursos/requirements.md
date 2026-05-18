# Requirements: discursos do Plenario do Senado

## Interface CLI

- `--data-inicio AAAA-MM-DD`: inicio da janela de coleta; default baseline `2011-05-18`.
- `--data-fim AAAA-MM-DD`: fim da janela de coleta; default baseline `2026-05-18`.
- `--mode dev|prod`: `dev` usa amostra e `data/dev`; `prod` exige destino externo.
- `--output-dir CAMINHO`: raiz de dados; tem prioridade sobre `FALANDO_NELA_DATA_ROOT`.
- `--sample` / `--no-sample`: sobrescreve o default do modo.
- `--sample-limit N`: limite de pronunciamentos textuais baixados; default `5` em `dev` e sem limite em `prod`.
- `--resume`: pula particoes mensais concluidas no checkpoint.
- `--run-id ID`: identificador da execucao, usado em logs, manifests e nomes de JSONL.

## Dependencias

- Python 3.11+.
- `httpx` para cliente HTTP.
- Infra comum em `coleta/common/`:
  - resolucao de diretorio por modo;
  - `OpenDataClient.get_json()`;
  - `OpenDataClient.get_text()`;
  - retries e `Retry-After`;
  - escrita JSONL, logs, checkpoints e manifest.

## Endpoints Obrigatorios

- Lista mensal:
  - path: `/dadosabertos/plenario/lista/discursos/{dataInicio}/{dataFim}.json`;
  - params: `siglaCasa=SF`, `v=4`;
  - resposta gravada em `metadata/`.
- Texto integral:
  - path: `/dadosabertos/discurso/texto-integral/{codigoPronunciamento}`;
  - resposta `text/plain`;
  - corpo da resposta gravado como texto, nao como URL.
- Fallback de sessao:
  - path: `/dadosabertos/taquigrafia/notas/sessao/{codigoSessao}.json`;
  - usado somente quando o texto por pronunciamento falhar ou vier vazio.

## Separacao de Dados

- `metadata/{run_id}.jsonl` recebe somente registros de descoberta, como `discursos_periodo_metadata`.
- `ano=YYYY/mes=MM/{run_id}.jsonl` recebe somente registros textuais consolidados, como `pronunciamento_texto`.
- `transcription_queue/{run_id}.jsonl` recebe somente casos sem texto oficial aproveitavel e com fonte candidata para transcricao futura.
- A particao mensal do corpus nao pode receber a lista mensal bruta.

## Contrato do Registro Textual

Cada `pronunciamento_texto` deve conter:

- `CodigoPronunciamento`: identificador oficial do pronunciamento.
- `codigo_pronunciamento`: alias normalizado do identificador.
- `TextoIntegral`: texto oficial transferido quando disponivel; nunca URL.
- `TextoIntegralUrl`: URL oficial/candidata preservada para rastreabilidade.
- `texto`: mesmo conteudo textual usado para analise, ou `null`.
- `forma`: `texto` ou `video`.
- `metodo_obtencao`: `api_texto_integral`, `api_notas_sessao` ou `pendente_transcricao_video`.
- `texto_status`: `disponivel`, `ausente` ou `erro`.
- `metadata.sessao`: metadados originais da sessao.
- `metadata.pronunciamento`: metadados originais do pronunciamento.
- `fontes`: URLs oficiais usadas ou candidatas.
- `tentativas_texto`: obrigatorio quando houver fallback ou falha.

## Regras de Conteudo

- `payload.TextoIntegral` e `payload.texto` sao os campos canonicos para analise textual.
- `metadata.pronunciamento.TextoIntegral` pode continuar existindo como campo bruto da fonte e pode conter URL.
- `Resumo`, `Indexacao`, publicacoes e links nao substituem texto integral.
- O texto por pronunciamento tem prioridade sobre notas de sessao.
- Notas de sessao tem prioridade sobre fila de video.
- Whisper/ffmpeg nao entram nesta etapa.

## Limites e Retomada

- Respeitar retries para `429`, `500`, `502`, `503` e `504`.
- Respeitar `Retry-After` quando a API informar.
- Checkpoint e `--resume` atuam por particao mensal.
- A particao so deve ser marcada como concluida apos a escrita dos registros selecionados da particao.
- Em `prod`, falhar se nenhum destino externo for definido.

## Exemplo Dev

```bash
python -m coleta.senado.plenario_discursos.collect \
  --mode dev \
  --sample-limit 5 \
  --run-id smoke-senado-plenario
```

## Exemplo Colab

```python
import os
import subprocess

os.environ["FALANDO_NELA_DATA_ROOT"] = "/content/drive/MyDrive/falando_nela/data"

subprocess.run([
    "python", "-m", "coleta.senado.plenario_discursos.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-senado-plenario",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=True)
```
