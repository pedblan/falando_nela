# Plano: atualizacao completa das bases pelo Colab

## Objetivo

Regularizar as execucoes incompletas observadas no Google Drive e atualizar
todas as bases existentes ate `2026-07-13`, com sobreposicao a partir de
`2026-05-01`. Coletas longas devem acontecer somente no Colab, gravando em
`/content/drive/MyDrive/falando_nela/data`.

## Estado inicial observado

- As coletas historicas textuais mais recentes usaram `2026-05-28` como corte.
- Os apartes foram coletados ate `2026-05-18`.
- `prod-historico-camara-plenario` possui apenas autosave em estado `running`.
- `prod-historico-senado-ccj` terminou com 2 erros e
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
4. Bloquear o processamento final ate todos os manifests obrigatorios estarem
   completos e sem particoes falhas ainda nao concluidas.
5. Regerar as fotografias canonicas `current`, Parquets, auditorias e samples.
6. Validar a nova janela no visualizador Gradio.

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
- Samples e auditorias usam `run_id`s datados e permanecem por ciclo.

## Fora de escopo

- Executar localmente backfills ou coletas de producao.
- Alterar os defaults historicos comuns da CLI.
- Apagar ou mover dados antigos do Drive.
- Promover registros de `transcription_queue` a texto analitico.
