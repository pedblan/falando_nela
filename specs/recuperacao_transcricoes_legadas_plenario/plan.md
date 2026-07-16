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
10. Em caderno separado, auditar hashes/comprimentos dos aceitos, classificar
    conflitos por causa, amostrar vínculos manuais, distribuir ausências por
    ano e medir por ano a cobertura texto/mídia da Câmara em unidades únicas.
11. Ler os Parquets canônicos sem modificá-los e sortear, com semente fixa,
    poucos textos integrais de 2010, 2015 e 2016 para Câmara, Senado e
    Congresso, incluindo amostra adicional dos registros cuja proveniência
    mencione o Diário.
12. Depois da aprovação humana, promover em caderno próprio somente os 471
    aceitos por chave forte. Recusar códigos com texto raw anterior e registrar
    fingerprints integrais dos sete Parquets antes da escrita.
13. Publicar registros mensais novos do Senado com método
    `legacy_parquet_transcricao_audiovisual_v1` e proveniência da recuperação,
    auditoria e decisão visual.
14. Reconstruir a fotografia `current`, aplicando somente na normalização a
    limpeza editorial versionada dos 83 textos recuperados do Diário.
15. Validar o acréscimo exato de 471 linhas e provar por fingerprints que o
    drift ficou restrito aos promovidos e ao subconjunto do Diário.

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

Sob
`operations/auditorias/transcricoes_legadas/{audit_id}/`, somente após
confirmação no caderno 11:

- amostras dos aceitos e dos vínculos manuais;
- diagnóstico e amostra das variantes conflitantes;
- distribuição anual dos não encontrados;
- cobertura texto/mídia da Câmara;
- inventário e amostras integrais dos anos históricos;
- relatório HTML e `provenance.json` com commit, parâmetros, semente e
  checksums das entradas e saídas.

Sob `operations/promocoes/transcricoes_legadas/{promotion_run_id}/`:

- fotografia e fingerprints anteriores ao rebuild;
- decisão da revisão visual e cópia do manifest raw;
- estado retomável da operação;
- validação final com gates e fingerprints posteriores.

## Limite desta etapa

Os cadernos 10 e 11 não baixam mídia, não executam Whisper ou outro ASR e não
escrevem em `raw/`, `processed/`, Parquets canônicos ou snapshots. A promoção
posterior é isolada no caderno 12 e exige revisão humana, contrato raw
versionado e confirmações distintas para raw e derivados. A fila da Câmara
serve para dimensionar uma aquisição posterior, não como texto. Conflitos,
vínculos manuais e não encontrados permanecem diagnósticos.
