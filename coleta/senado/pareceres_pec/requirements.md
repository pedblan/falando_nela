# Requirements: pareceres de PEC no Senado

## Parametros

- `--data-inicio`: inicio do periodo, em `AAAA-MM-DD`.
- `--data-fim`: fim do periodo, em `AAAA-MM-DD`.
- `--mode dev|prod`: `dev` por default.
- `--output-dir`: destino dos dados; em `prod`, deve ser externo ao repositorio.
- `--sample/--no-sample`: `dev` usa amostra por default; `prod` coleta completa por default.
- `--sample-limit`: limite de documentos de parecer processados; default `5` em `dev`.
- `--resume`: pula particoes concluidas no checkpoint.
- `--run-id`: identificador auditavel da execucao.

## Dependencias

- `httpx` para acesso HTTP.
- `pypdf` para extracao textual de PDFs oficiais.
- Python 3.11 ou superior recomendado.

## Limites e particionamento

- O endpoint `processo` aceita janelas limitadas por data de apresentacao; o coletor usa particoes mensais.
- A particao mensal e segura para retomada e tambem evita requisicoes muito amplas.
- Em `dev`, o coletor processa apenas a primeira particao e respeita `--sample-limit`.

## Campos obrigatorios do payload

- `IdProcesso`, `CodigoMateria`, `IdentificacaoPec`.
- `IdDocumento`.
- `TextoIntegral`: texto extraido do documento oficial ou `null`.
- `TextoIntegralUrl`: URL oficial do documento.
- `texto`: mesmo conteudo canonico de `TextoIntegral`.
- `forma`: `texto` quando ha texto extraido; `documento` quando o arquivo foi encontrado mas ainda nao gerou texto.
- `metodo_obtencao`: `pdf_text_extraction`, `html_text_extraction`, `text_document_download` ou erro documentado.
- `texto_status`: `disponivel`, `ausente` ou `erro`.
- `colegiado.ambito`: `ccj` ou `plenario`.
- `metadata.processo` e `metadata.documento`: objetos brutos da API.
- `documento.sha256`, `documento.tamanho_bytes`, `documento.content_type`, `documento.url_final`.

## Politica de retomada

- O checkpoint marca particoes mensais concluidas.
- Uma particao concluida nao e reprocessada quando `--resume` esta ativo.
- Versoes diferentes de parecer continuam como registros separados, mesmo quando pertencem a mesma PEC.

## Google Drive

Em producao no Colab, defina antes de executar:

```python
import os
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")
os.environ["FALANDO_NELA_DATA_ROOT"] = "/content/drive/MyDrive/falando_nela/data"
Path(os.environ["FALANDO_NELA_DATA_ROOT"]).mkdir(parents=True, exist_ok=True)
```
