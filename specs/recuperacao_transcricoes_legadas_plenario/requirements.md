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

## Auditoria segura posterior

- O caderno 11 deve ler a recuperação operacional pelo `recovery_id` explícito
  e reconciliar suas contagens com `summary.json` antes de analisar conteúdo.
- Hash e comprimento de todo texto aceito devem ser recalculados; a amostra de
  aceitos é estratificada por método/ano e exibida integralmente.
- Conflitos devem ser reduzidos também ao nível de candidato e classificados
  como múltiplas variantes textuais, linha legada compartilhada, ambas ou não
  classificado, sem decisão automática.
- Vínculos com escore inferior a 90 permanecem em revisão manual e recebem
  somente uma amostra reproduzível para inspeção.
- Não encontrados devem ser contados por casa/ano.
- A Câmara deve ser auditada somente no corpus mensal. A métrica distingue
  ocorrências raw de unidades únicas e considera uma unidade audiovisual
  resolvida quando qualquer ocorrência contém `transcricao`.
- Os Parquets `camara__plenario_discursos.parquet`,
  `senado__plenario_discursos.parquet` e
  `senado__congresso_discursos.parquet` são lidos para 2010, 2015 e 2016. O
  caderno sorteia poucos textos integrais por arena/ano com semente fixa e uma
  amostra adicional cuja proveniência contenha `diario`.
- A exibição integral não trunca cabeçalhos ou marcas editoriais; cartões HTML
  recolhíveis podem ser usados para manter a saída navegável.

## Segurança operacional

- Flags de download do Parquet e de escrita começam em `False`.
- Escritas exigem `CONFIRM_PROBE_ID` igual ao id da recuperação.
- O Parquet legado só é lido após validar tamanho e magic bytes.
- Downloads usam arquivo `.part` e promoção atômica após validação.
- Saídas ficam exclusivamente em `operations/`.
- O caderno não instala nem chama ferramentas de ASR ou download de mídia.
- A auditoria começa com `GRAVAR_AUDITORIA=False`, exige confirmação literal do
  `audit_id`, recusa sobrescrever uma auditoria existente e escreve somente em
  `operations/auditorias/transcricoes_legadas/{audit_id}/`.

## Promoção revisada

- A população promovível tem exatamente 471 registros, todos do Senado, com
  estado de revisão aceito, `publication_status=operations_only`, escore
  `>=90` e vínculo `exact_speech_id`, `exact_audio_url` ou `exact_video_url`.
- A decisão humana registra aprovação de uma amostra aleatória de 30%, nota,
  `audit_id` e `recovery_id`.
- Texto raw não vazio já associado ao código bloqueia a primeira promoção.
  Câmara, revisão manual, conflitos e não encontrados são excluídos.
- Cada registro usa `record_type=pronunciamento_texto`, método
  `legacy_parquet_transcricao_audiovisual_v1`, partição mensal e proveniência
  completa em `metadata.legacy_recovery`.
- Arquivos raw e manifest são novos, escritos por `.partial` e publicados sem
  overwrite. Falha anterior ao manifest remove os arquivos publicados pela
  tentativa.
- `PROMOVER_TRANSCRICOES` e `REGERAR_DERIVADOS` começam em `False` e exigem
  confirmações literais independentes.
- A fotografia anterior dos sete Parquets é persistida antes da escrita raw e
  reutilizada em uma retomada.

## Limpeza derivada do Diário

- O raw e os PDFs oficiais permanecem imutáveis.
- A regra só incide sobre método
  `diario-congresso-oficial-por-codigo-v1` e examina as cinco primeiras e cinco
  últimas linhas não vazias de cada página delimitada por `\f`.
- Apenas números de página e linhas editoriais reconhecidas podem ser
  removidos; uma menção ao Diário no corpo não é alvo.
- A transformação é idempotente, preserva texto não vazio e registra versão,
  hashes, comprimentos, quebras de página e linhas removidas em
  `fontes.normalizacao_texto_diario`.
- O rebuild só é liberado após confirmação literal de
  `diario-congresso-limpeza-editorial-v1`.

## Artefato executável

O fluxo é implementado por
`notebooks/coleta/10_sondagem_transcricoes_audiovisuais_plenario_colab.ipynb`,
gerado de forma reproduzível por
`scripts/generate_video_transcription_probe_colab_notebook.py`.
A revisão posterior é implementada por
`notebooks/coleta/11_auditoria_transcricoes_e_amostras_plenario_colab.ipynb`,
gerado por
`scripts/generate_video_transcription_audit_colab_notebook.py`.
A promoção e o rebuild controlado são implementados por
`notebooks/coleta/12_promocao_transcricoes_legadas_plenario_colab.ipynb`,
gerado por
`scripts/generate_legacy_transcription_promotion_colab_notebook.py`.
