# Plano: atualizacao completa das bases pelo Colab

## Objetivo

Atualizar as bases existentes ate `2026-07-13`, com sobreposicao a partir de
`2026-05-01`. O recorte de atualizacao cobre pouco mais de dois meses porque
as ultimas coletas ocorreram em maio; ele nao autoriza refazer a historia das
bases. Coletas longas devem acontecer somente no Colab, gravando em
`/content/drive/MyDrive/falando_nela/data`.

## Estado inicial observado

- As coletas historicas textuais mais recentes usaram `2026-05-28` como corte.
- Os apartes foram coletados ate `2026-05-18`.
- `prod-historico-camara-plenario` possui apenas autosave em estado `running`.
- `prod-historico-senado-ccj` terminou inicialmente com 2 erros e
  `prod-historico-camara-ccjc` com 33 erros.
- A fotografia processada de `2026-06-03` tem 407.084 textos em seis bases.
- `senado/congresso_discursos` possui somente listas em `metadata/`; o corpus
  textual deve ser completado nesta atualizacao.
- `processed/apartes_parlamentares/v1` ainda nao existe no Drive ativo.

## Fluxo operacional

1. Auditar o Drive, fixar o ciclo e gravar a configuracao operacional.
2. Atualizar e processar `parlamentares/v1`.
3. Rodar, em paralelo ou em ondas, quatro faixas sem colisao de dataset:
   Senado, Congresso, demais bases da Camara e Plenario da Camara.
   A faixa Senado retoma `prod-historico-senado-ccj`, subdivide
   automaticamente respostas JSON de agenda interrompidas ou com HTTP 5xx e,
   no ultimo dia ainda problematico, usa a agenda XML diaria. O mesmo
   `run_id --resume`, checkpoint e raw cumulativo sao preservados.
   A faixa do Plenario da Camara copia `parlamentares_periodos.parquet` para o
   disco efemero do Colab e coleta somente `2026-05-01` a `2026-07-13`.
4. Bloquear o processamento final ate todos os manifests obrigatorios estarem
   completos e sem particoes falhas ainda nao concluidas. Uma base excluida da
   analise corrente pode ter excecao exata, datada e auditada, sem alterar seu
   manifest de erro nem ampliar a tolerancia para outras particoes.
5. Regerar as fotografias canonicas `current`, Parquets, auditorias e samples.
6. Validar a nova janela no visualizador Gradio.

Na execucao de `2026-07-13`, `prod-historico-camara-plenario` chegou a uma
particao anterior ao recorte da pesquisa e consumiu o runtime sem contribuir
para a atualizacao iniciada em maio. A decisao operacional posterior substitui
a retomada historica prevista originalmente: esse run fica fora dos gates do
ciclo, sem ser chamado de concluido. Raw, checkpoint, log, autosave e eventual
manifest permanecem intactos no Drive para uma tarefa historica separada.

Essa exclusao e fechada sobre a identidade exata
`camara_plenario_historico` / `prod-historico-camara-plenario` / janela
`1946-01-01` a `2026-05-28`. Ela nao permite omitir a faixa incremental nem
qualquer outra coleta. O caderno 5 fixa por `assert` a janela incremental
`2026-05-01` a `2026-07-13`; nao ha `try/except` para esconder uma execucao
historica incompleta, pois ela simplesmente nao pertence ao escopo temporal da
atualizacao.

Na recuperacao da CCJ do Senado em `2026-07-13`, `2013-10` foi concluida e
somente `2015-05` permaneceu falha por JSON malformado da API. Como o artigo
corrente usa Plenario e exclui `senado/ccj_notas`, essa particao pode ser
registrada em `deferred_collections.json` e retomada em ciclo posterior. O
caderno 2 continua com as demais coletas do Senado; o caderno 6 registra a
cobertura degradada, mas nao chama a CCJ historica de concluida.

## Cadernos

Os cadernos de coleta ficam em `notebooks/coleta/`:

- `00_auditoria_configuracao_atualizacao_colab.ipynb`;
- `01_atualizacao_parlamentares_colab.ipynb`;
- `02_atualizacao_senado_colab.ipynb`;
- `03_backfill_congresso_textos_colab.ipynb`;
- `04_atualizacao_camara_demais_bases_colab.ipynb`;
- `05_atualizacao_camara_plenario_colab.ipynb`.

O fechamento fica em
`notebooks/processamento/06_processamento_validacao_atualizacao_colab.ipynb`.

## Retencao e proveniencia

- Raw, logs, checkpoints e manifests de coleta permanecem cumulativos.
- As fotografias processadas usam `run_id`s estaveis terminados em `current`
  e sao substituidas com `--overwrite`.
- A fotografia historica existente nao deve ser removida.
- A configuracao, os manifests processados e o resumo final de cada ciclo sao
  copiados para `operations/atualizacao/ciclos/{cycle_id}/`.
- Runs preservados, mas retirados do escopo depois da auditoria, aparecem em
  `preserved_out_of_scope_runs` e no resumo final com motivo e lista de
  artefatos mantidos.
- Samples e auditorias usam `run_id`s datados e permanecem por ciclo.
- Adiamentos excepcionais ficam em
  `operations/atualizacao/ciclos/{cycle_id}/deferred_collections.json`, com
  base excluida da analise, motivo, particoes exatas e acao de acompanhamento.

## Fora de escopo

- Executar localmente backfills ou coletas de producao.
- Alterar os defaults historicos comuns da CLI.
- Apagar ou mover dados antigos do Drive.
- Promover registros de `transcription_queue` a texto analitico.
