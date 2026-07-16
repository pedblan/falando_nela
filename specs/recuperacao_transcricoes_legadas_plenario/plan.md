# Plano: recuperação de transcrições legadas de plenário

## Resultado esperado

Produzir um inventário conjunto das lacunas textuais com mídia na Câmara e no
Senado. Como `DiscursosTodos.parquet` contém somente Senado, recuperar dele
apenas os textos senatoriais e gerar, separadamente, a fila de mídias da Câmara
que ainda precisarão ser baixadas e transcritas. Os resultados permanecem em
uma área operacional até revisão e etapas posteriores próprias por casa.

## Entradas

- raw cumulativo de `camara/plenario_discursos`;
- `raw/senado/plenario_discursos/transcription_queue`;
- arquivo legado do Google Drive com id
  `1R5Xz3tydoPYHSjzmKM8_KDvTzQ51RFk2`, nome `DiscursosTodos.parquet` e tamanho
  esperado de `252122904` bytes;
- mapeamento de colunas inferido e, quando necessário, corrigido explicitamente
  em `OLD_COLUMN_MAP`.

## Fluxo

1. Montar o Drive antes de carregar código do projeto.
2. Materializar o Parquet legado pela API autenticada do Drive, caso ainda não
   exista no caminho de referência.
3. Recusar HTML de login, download parcial ou arquivo divergente pelo tamanho e
   pelos marcadores `PAR1` do cabeçalho e rodapé.
4. Inventariar a fila do Senado por `CodigoPronunciamento` e as páginas mensais
   da Câmara com mídia e `transcricao` vazia.
5. Na Câmara, retirar uma pendência quando outra ocorrência raw da mesma unidade
   já trouxer texto.
6. Cruzar somente a fila do Senado com o legado nesta ordem:
   - identificador oficial idêntico;
   - URL de áudio ou vídeo idêntica;
   - parlamentar, data e sessão idênticos, somente para revisão.
7. Rejeitar vínculo por nome isolado, conflito entre textos e uma linha legada
   ambígua entre múltiplos candidatos.
8. Impedir que qualquer candidato da Câmara entre no cruzamento legado.
9. Exportar textos senatoriais de chave forte, revisões, conflitos, auditoria
   sem texto, fila de download da Câmara e resumo somente sob confirmação.

## Saídas

Sob
`operations/recuperacoes/transcricoes_legadas/{recovery_id}/`:

- `recovered_legacy_texts.parquet`;
- `legacy_matches_manual_review.parquet`;
- `legacy_match_conflicts.parquet`;
- `legacy_match_audit.parquet`;
- `camara_media_download_queue.parquet` e `.csv`;
- `candidate_status.csv`;
- `summary.json`.

## Limite desta etapa

O caderno não baixa mídia, não executa Whisper ou outro ASR e não escreve em
`raw/`, `processed/`, Parquets canônicos ou snapshots. A promoção dos textos
senatoriais exige revisão humana e contrato raw versionado. A fila da Câmara
serve para dimensionar uma aquisição retomável posterior, não como texto.
