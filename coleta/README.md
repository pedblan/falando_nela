# Modulo de coleta

Este modulo organiza coletas independentes dos portais oficiais de dados abertos do Senado Federal, Congresso Nacional e Camara dos Deputados.

## Convencoes comuns

- Periodo baseline: `2011-05-18` a `2026-05-18`.
- Cliente HTTP: `httpx`, com `Accept: application/json`, retries e respeito a `Retry-After`.
- Execucao local: usar `--mode dev`, que grava em `data/dev` e usa amostra por default.
- Execucao de producao: usar `--mode prod`, preferencialmente no Google Colab com Drive montado.
- Retomada: usar `--resume` para pular particoes ja concluidas no checkpoint.
- Dados completos: ficam fora do Git, em uma pasta externa como Google Drive.

## Modos de execucao

- `dev`: default. Usa `--sample` por default, grava em `data/dev` quando nenhum destino e informado, e serve para smoke tests locais.
- `prod`: usa `--no-sample` por default e exige destino externo via `--output-dir` ou `FALANDO_NELA_DATA_ROOT`.
- Em `prod`, o coletor recusa diretorios dentro do repositorio para evitar gravar uma coleta completa no Git local.
- Precedencia do destino: `--output-dir`, depois `FALANDO_NELA_DATA_ROOT`, depois `data/dev` apenas em `dev`.
- Progresso: os scripts imprimem eventos simples no stdout (`partition_started`, `partition_completed`, falhas e skips), alem de gravarem o log JSONL.
- Autosave: registros JSONL sao gravados linha a linha; checkpoints e `manifests/{run_id}.autosave.json` sao atualizados durante a execucao.
- Retomada: com `--resume`, o coletor pula particoes concluidas e tambem le JSONLs existentes do mesmo `run_id` para nao baixar novamente registros ja gravados.
- Falhas: erros de item ou particao devem ser capturados, registrados no log/checkpoint e nao devem impedir a continuacao das demais particoes quando houver caminho seguro.

No Colab, o destino padrao recomendado e:

```bash
export FALANDO_NELA_DATA_ROOT=/content/drive/MyDrive/falando_nela/data
```

## Layout de dados

- `data/raw/{portal}/{dataset}/ano=YYYY/mes=MM/{run_id}.jsonl`: registros textuais envelopados, isto e, o corpus bruto para analise futura.
- `data/raw/{portal}/{dataset}/metadata/{run_id}.jsonl`: paginas/listas de metadados, respostas de descoberta, pautas e contexto auxiliar.
- `data/raw/{portal}/{dataset}/transcription_queue/{run_id}.jsonl`: casos sem texto oficial e candidatos a transcricao futura.
- `data/checkpoints/{portal}/{dataset}.json`: particoes concluidas.
- `data/logs/{run_id}.jsonl`: log estruturado da execucao.
- `data/manifests/{run_id}.json`: resumo auditavel da execucao.
- `data/manifests/{run_id}.autosave.json`: resumo parcial sobrescrito durante a execucao para inspecao em caso de interrupcao.
- `data/schemas/`: schemas versionaveis.
- `data/samples/`: amostras pequenas versionaveis quando necessario.

Regra operacional: respostas de lista ou descoberta nao devem ser misturadas ao JSONL mensal do corpus textual. Esses payloads podem ser grandes e sao preservados em `metadata/` para auditoria, enquanto `ano=YYYY/mes=MM/` fica reservado a registros como `pronunciamento_texto`.

## Envelope bruto

Cada linha JSONL preserva:

- `run_id`, `collected_at`, `source`, `dataset`, `record_type`, `source_id`.
- `partition` e `periodo`.
- `request` com metodo, endpoint e parametros.
- `response` com URL final, status e cabecalhos relevantes.
- `checksum` calculado sobre o payload.
- `payload` com a resposta da fonte com minima transformacao.

O `source_id` combinado com `record_type` e usado na retomada fina por `run_id`. Ao repetir uma execucao interrompida com o mesmo `--run-id --resume`, registros ja presentes no JSONL sao reconhecidos e pulados.

## Unidade textual

A unidade analitica preferencial e o pronunciamento com texto integral. Sempre que houver endpoint oficial de texto, o coletor deve combinar os metadados do pronunciamento com o texto integral antes de gerar o registro analitico bruto.

Ordem de prioridade para formar corpus textual:

1. Texto integral do discurso ou pronunciamento, quando houver endpoint oficial por item.
2. Texto integral ou notas taquigraficas da sessao, reuniao ou evento, quando o texto por discurso nao estiver disponivel.
3. Campo de transcricao textual entregue pela API, quando a fonte ja devolver texto estruturado.
4. Fila de transcricao a partir de video/audio oficial, sem substituir silenciosamente texto oficial existente.

Metadados, resumos, indexacao, pautas e listas de eventos sao contexto e rastreabilidade; nao sao corpus analitico principal quando houver texto integral disponivel.

Para PECs, a unidade analitica prioritaria neste momento e o parecer, nao o texto-base da PEC. Como uma PEC pode ter varios pareceres e versoes documentais, cada parecer/documento oficial deve ser preservado em registro proprio.

Quando uma fonte exigir duas etapas, a primeira etapa localiza os itens e grava a resposta bruta em `metadata/`; a segunda etapa baixa o texto integral e grava somente o registro textual consolidado na particao mensal. Esse desenho evita inflar os arquivos de corpus com listas completas de metadados.

Campos textuais esperados quando aplicavel:

- `TextoIntegral`: texto integral oficial transferido; este campo nunca deve conter URL.
- `TextoIntegralUrl`: URL oficial usada para rastreabilidade quando houver.
- `texto`: texto integral oficial ou `null`.
- `forma`: `texto` quando o conteudo vem de texto oficial; `video` quando depende de transcricao futura.
- `metodo_obtencao`: por exemplo `api_texto_integral`, `pendente_transcricao_video` ou, futuramente, `whisper`.
- `texto_status`: `disponivel`, `ausente` ou `erro`.
- `fontes`: URLs oficiais usadas ou candidatas.

Os metadados brutos da fonte podem conter campos como `metadata.pronunciamento.TextoIntegral` com URL original. Para analise textual, use sempre o campo canonico `TextoIntegral` ou `texto` no nivel principal do payload.

Registros em `transcription_queue` nao devem ser usados como texto analitico ate passarem por uma etapa futura de transcricao documentada.

Para pareceres em PDF/HTML, `forma=documento` pode aparecer quando o arquivo oficial foi localizado, mas a extracao textual ainda nao produziu texto. Esses casos devem ser tratados em etapa futura de OCR ou revisao documental, sem substituir silenciosamente documentos ja extraidos.

## Tarefas

- `senado/plenario_discursos`: discursos do Plenario do Senado (`siglaCasa=SF`).
- `senado/congresso_discursos`: discursos do Plenario do Congresso (`siglaCasa=CN`).
- `senado/ccj_notas`: agenda, detalhes e notas taquigraficas da CCJ do Senado.
- `senado/pareceres_pec`: pareceres e relatorios de PEC no Plenario e na CCJ do Senado.
- `camara/plenario_discursos`: discursos por deputado na API da Camara.
- `camara/ccjc_eventos`: eventos, participantes e metadados da CCJC da Camara.
- `camara/pareceres_pec`: pareceres de PEC no Plenario, CCJC e historica CCJR da Camara.

## Execucao

Exemplo:

```bash
python -m coleta.senado.plenario_discursos.collect --mode dev --run-id smoke-senado-sf
```

Exemplo de producao no Colab, depois de montar o Drive:

```bash
python -m coleta.senado.plenario_discursos.collect --mode prod --resume --run-id prod-senado-sf
```

Exemplos para pareceres de PEC:

```bash
python -m coleta.senado.pareceres_pec.collect --mode dev --sample-limit 2 --run-id smoke-senado-pareceres-pec
python -m coleta.camara.pareceres_pec.collect --mode dev --sample-limit 2 --run-id smoke-camara-pareceres-pec
```

Todos os scripts aceitam:

```text
--data-inicio AAAA-MM-DD
--data-fim AAAA-MM-DD
--mode dev|prod
--output-dir CAMINHO
--sample / --no-sample
--sample-limit N
--resume
--run-id IDENTIFICADOR
```

## Colab e Google Drive

O notebook `notebooks/coleta/coleta_template.ipynb` monta o Google Drive, define `FALANDO_NELA_DATA_ROOT`, instala dependencias e executa todos os coletores em `--mode prod --resume`.

Os notebooks de coleta nao devem usar `check=True` ao chamar coletores. Um coletor que falhe deve imprimir stdout/stderr, registrar o resultado e permitir que o fluxo siga para o proximo modulo ou para a inspecao dos logs.

Para o fluxo especifico do Plenario do Senado, use `notebooks/coleta/coleta_senado_plenario.ipynb`. A primeira celula executavel desse notebook monta o Drive antes de clonar o repositorio ou carregar qualquer codigo do projeto.

Para o fluxo especifico da CCJ do Senado, use `notebooks/coleta/coleta_senado_ccj.ipynb`. Ele segue o mesmo padrao operacional do Plenario, com validacao curta, inspecao dos JSONLs e coleta completa retomavel.

Para o fluxo especifico do Plenario da Camara, use `notebooks/coleta/coleta_camara_plenario.ipynb`. Ele valida paginas de deputados em `metadata/`, paginas de discursos no JSONL mensal e a presenca de `transcricao` quando a API entregar texto.

O conector Google Drive pode ajudar a localizar e verificar arquivos/pastas, mas a escrita pesada deve ser feita pelo runtime do Colab com Drive montado.

Celula base para usar no Colab:

```python
from google.colab import drive
import os
import subprocess
from pathlib import Path

drive.mount("/content/drive")
os.environ["FALANDO_NELA_DATA_ROOT"] = "/content/drive/MyDrive/falando_nela/data"
Path(os.environ["FALANDO_NELA_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)

REPO_URL = "https://github.com/pedblan/falando_nela.git"
REPO_DIR = Path("/content/falando_nela")

if not REPO_DIR.exists():
    subprocess.run(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
else:
    subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], check=True)

os.chdir(REPO_DIR)
subprocess.run(["python", "-m", "pip", "install", "-r", "requirements.txt"], check=True)
```

Exemplo de celula para executar um coletor em producao:

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

Exemplo de celula para os pareceres de PEC:

```python
import subprocess

for module, run_id in [
    ("coleta.senado.pareceres_pec.collect", "prod-senado-pareceres-pec"),
    ("coleta.camara.pareceres_pec.collect", "prod-camara-pareceres-pec"),
]:
    subprocess.run([
        "python", "-m", module,
        "--mode", "prod",
        "--resume",
        "--run-id", run_id,
        "--data-inicio", "2011-05-18",
        "--data-fim", "2026-05-18",
    ], check=False)
```
