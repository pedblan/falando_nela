# Validação: recuperação de transcrições legadas de plenário

## Testes automatizados

- validar o notebook com `nbformat`;
- compilar cada célula de código com `ast.parse`;
- verificar sincronização entre notebook e gerador;
- comprovar montagem do Drive como primeira célula executável;
- comprovar flags desligadas e confirmação explícita;
- comprovar ausência de `faster-whisper`, `yt-dlp` e `ffmpeg`;
- testar inventário e deduplicação das duas casas com fixtures JSONL;
- comprovar que JSONL inválido em `camara/.../metadata/` é ignorado e que a
  mesma corrupção em `ano=YYYY/mes=MM/` continua bloqueante;
- testar que vídeo de sessão do Senado permanece marcado para alinhamento;
- comprovar em teste sintético que um id da Câmara presente no Parquet de teste
  continua excluído do cruzamento legado;
- comprovar recarga explícita do módulo no caderno e gate de versão, para que um
  runtime Colab já usado não mantenha a implementação anterior em memória;
- testar inferência de aliases do schema legado;
- testar recusa de arquivo sem `PAR1` ou tamanho esperado.
- validar o caderno 11 com `nbformat`, AST e sincronização com seu gerador;
- testar a auditoria de cobertura da Câmara com ocorrência vazia posteriormente
  resolvida, unidade audiovisual ainda pendente e texto sem mídia;
- comprovar no caderno 11 a classificação explícita das causas de conflito, a
  distribuição anual dos não encontrados e a revisão manual sem aceite;
- comprovar anos fixos `2010, 2015, 2016`, semente fixa, as três arenas, texto
  integral sem truncamento e priorização de proveniência contendo `diario`;
- comprovar escrita desligada, confirmação literal, recusa de sobrescrita e
  `provenance.json` somente em `operations/auditorias/`.

## Gates no Colab

- `DiscursosTodos.parquet` tem exatamente `252122904` bytes, cabeçalho e rodapé
  `PAR1` e metadata Parquet legível;
- `candidate_id` é único no inventário;
- todo recuperado tem texto não vazio e SHA-256;
- `candidate_id` é único em `recovered_legacy_texts.parquet`;
- recuperados usam apenas métodos com escore `>= 90`;
- todos os recuperados têm `house=senado`;
- nenhum recuperado aparece também em conflitos;
- vínculos senatoriais por parlamentar/data/sessão ficam somente em revisão;
- todo candidato da Câmara tem `workflow_status=requires_media_download`;
- `camara_media_download_queue.parquet` contém somente Câmara, mídia não vazia
  e estados pendentes de download/transcrição;
- `summary.json` registra contagens por casa e estado;
- nenhum caminho canônico é escrito pelo caderno.

No caderno 11:

- hashes e comprimentos recalculados coincidem com os 471 aceitos lidos;
- números de candidatos únicos em revisão, conflito e não encontrado coincidem
  com `candidate_status.csv`, distinguindo-os das linhas de correspondência;
- a auditoria anual da Câmara é não vazia e informa cobertura entre unidades
  únicas com mídia, sem transformar ausência em aceite ou falha estrutural;
- existem linhas e amostras não vazias para cada combinação de Câmara, Senado e
  Congresso com 2010, 2015 e 2016;
- a quantidade de linhas do Diário e sua amostra ficam registradas como achado
  substantivo; ausência não autoriza promoção nem é ocultada;
- `canonical_outputs_untouched=True` e nenhuma escrita ocorre fora da pasta
  imutável da auditoria.

## Revisão antes da promoção

No Senado, inspecionar por método de vínculo uma amostra contendo texto,
autor/id, data, sessão e URL. Na Câmara, revisar a quantidade, os anos e a
acessibilidade das URLs antes de autorizar qualquer download. Promoção e
aquisição são tarefas posteriores distintas.
