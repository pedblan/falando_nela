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
- `documento_classe`: `parecer`, `relatorio` ou `avulso_parecer`.
- `status_deliberativo`: `proposto`, `vencedor`, `vencido`, `aprovado`, `rejeitado` ou `indeterminado`.
- `vencido`: booleano derivado de `descricao`, `identificacao`, metadados ou texto extraido.
- `TextoIntegral`: texto extraido do documento oficial ou `null`.
- `TextoIntegralUrl`: URL oficial do documento.
- `texto`: mesmo conteudo canonico de `TextoIntegral`.
- `forma`: `texto` quando ha texto extraido; `documento` quando o arquivo foi encontrado mas ainda nao gerou texto.
- `metodo_obtencao`: `pdf_text_extraction`, `html_text_extraction`, `text_document_download` ou erro documentado.
- `texto_status`: `disponivel`, `ausente` ou `erro`.
- `colegiado.ambito`: `ccj`, `plenario` ou `indeterminado`.
- `metadata.processo` e `metadata.documento`: objetos brutos da API.
- `documento.sha256`, `documento.tamanho_bytes`, `documento.content_type`, `documento.url_final`.

## Classificacao documental

- O coletor deve preservar `PARECER`, `RELATORIO`, `AVULSO_PARECER` e variantes claramente documentais de parecer, como parecer de redacao.
- `LISTAGEM_RELATORIO` e listagens administrativas devem ser excluidas, mesmo quando tiverem URL de documento.
- `Relatorio do Vencido` deve ser coletado como `documento_classe=relatorio`, `status_deliberativo=vencido` e `vencido=true`.
- Avulsos de parecer sem colegiado explicito devem ser preservados quando vinculados ao processo de PEC, com `colegiado.ambito=indeterminado`.

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

## Progresso, autosave e retomada

- O script deve imprimir progresso minimo no stdout por particao, skip, falha e conclusao.
- Cada registro deve ser gravado imediatamente em JSONL; checkpoint e `manifest.autosave.json` devem ser atualizados durante a execucao.
- `try/except` deve isolar falhas de processo, documento ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
