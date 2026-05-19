# Requirements: pareceres de PEC na Camara

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

- A API da Camara limita algumas consultas por intervalo de datas; o coletor usa particoes mensais.
- O endpoint de proposicoes com `dataInicio` e `dataFim` deve ser tratado como descoberta de PECs com atividade no periodo, nao necessariamente PECs apresentadas no periodo.
- Em `dev`, o coletor processa apenas a primeira particao e respeita `--sample-limit`.

## Campos obrigatorios do payload

- `IdProposicao`, `SiglaTipo`, `Numero`, `Ano`.
- `documento_classe`: `parecer`, `relatorio` ou `voto_em_separado`.
- `status_deliberativo`: `proposto`, `vencedor`, `vencido`, `aprovado`, `rejeitado` ou `indeterminado`.
- `vencido`: booleano derivado da tramitacao, despacho, documento ou relacao com parecer vencedor/voto em separado.
- `TextoIntegral`: texto extraido do documento oficial ou `null`.
- `TextoIntegralUrl`: URL oficial do documento indicado pela tramitacao.
- `texto`: mesmo conteudo canonico de `TextoIntegral`.
- `forma`: `texto` quando ha texto extraido; `documento` quando o arquivo foi encontrado mas ainda nao gerou texto.
- `metodo_obtencao`: `pdf_text_extraction`, `html_text_extraction`, `text_document_download` ou erro documentado.
- `texto_status`: `disponivel`, `ausente` ou `erro`.
- `colegiado.ambito`: `ccj`, `plenario`, `comissao_especial` ou `indeterminado`.
- `metadata.proposicao`, `metadata.detalhe` e `metadata.tramitacao`: objetos brutos da API.
- `documento.sha256`, `documento.tamanho_bytes`, `documento.content_type`, `documento.url_final`.

## Classificacao documental

- A Camara nao entrega uma taxonomia documental equivalente ao Senado; o coletor deve classificar a partir de `descricaoTramitacao`, `codTipoTramitacao`, `despacho`, `siglaOrgao`, `uriOrgao` e URL oficial.
- Codigos de tramitacao que devem ser candidatos a documento de parecer: `322`, `323`, `324`, `325`, `326`, `327`, `328`, `330`, `335`, `336`, `431` e `1040` quando houver URL ou despacho documental compativel.
- Expressoes candidatas: `parecer do relator`, `parecer proferido`, `parecer vencedor`, `parecer reformulado`, `complementacao de voto`, `relator do vencedor`, `voto em separado` e `relatorio`.
- Requerimentos e atos de criacao de comissao devem ser excluidos mesmo quando mencionarem "proferir parecer".
- Quando uma tramitacao indicar que o parecer do relator passou a constituir voto em separado, o documento original deve ser classificado como `status_deliberativo=vencido` se houver URL recuperavel; os votos em separado devem ser preservados como `documento_classe=voto_em_separado`.

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
- `try/except` deve isolar falhas de proposicao, tramitacao, documento ou particao sem derrubar o fluxo inteiro.
- Com `--resume`, o coletor deve pular particoes concluidas e registros ja presentes no JSONL do mesmo `run_id`.
