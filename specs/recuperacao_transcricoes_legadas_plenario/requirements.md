# Requisitos: recuperação de transcrições legadas de plenário

## Objetivo

Reaproveitar transcrições audiovisuais do Senado produzidas na pesquisa
anterior e inventariar separadamente as lacunas da Câmara que exigem aquisição
de mídia. O banco legado não é fonte oficial primária e não contém Câmara.

## Identidade e vínculo

- Senado usa `CodigoPronunciamento` como chave preferencial.
- URL oficial idêntica também pode vincular um registro do Senado.
- Parlamentar, data e sessão no Senado servem somente para localizar casos de
  revisão, nunca para aceite automático.
- Nenhum candidato da Câmara pode participar do cruzamento com o legado.
- Nome do parlamentar nunca é chave de identidade ou deduplicação.
- Um candidato associado a mais de um hash textual é conflito.
- Uma linha legada associada a mais de um candidato é ambígua e não pode ser
  aceita automaticamente.
- Duplicatas legadas com o mesmo candidato e mesmo hash textual podem ser
  reduzidas a uma ocorrência, preservando a auditoria.

## Conteúdo e proveniência

Cada texto aceito deve preservar:

- `candidate_id`, casa, data e identificadores atuais;
- método e escore do vínculo;
- campos legados usados no vínculo;
- texto recuperado, comprimento e SHA-256;
- id do arquivo legado e `recovery_id`;
- `review_status` e `publication_status=operations_only`.

O texto legado não pode substituir silenciosamente texto oficial já disponível.
A fila atual é formada somente por unidades sem texto na fotografia raw
inspecionada.

## Fila da Câmara

- Cada item preserva `candidate_id`, deputado, data, evento, tipo, URL de mídia,
  proveniência raw e prioridade de download.
- Áudio direto precede vídeo na prioridade de aquisição.
- O estado inicial é `download_status=pending` e
  `transcription_status=pending_after_download`.
- A fila não contém texto legado e não autoriza download ou ASR nesta etapa.

## Segurança operacional

- Flags de download do Parquet e de escrita começam em `False`.
- Escritas exigem `CONFIRM_PROBE_ID` igual ao id da recuperação.
- O Parquet legado só é lido após validar tamanho e magic bytes.
- Downloads usam arquivo `.part` e promoção atômica após validação.
- Saídas ficam exclusivamente em `operations/`.
- O caderno não instala nem chama ferramentas de ASR ou download de mídia.

## Artefato executável

O fluxo é implementado por
`notebooks/coleta/10_sondagem_transcricoes_audiovisuais_plenario_colab.ipynb`,
gerado de forma reproduzível por
`scripts/generate_video_transcription_probe_colab_notebook.py`.
