# Notebooks de coleta

Esta pasta guarda notebooks operacionais para execucao de coletores, especialmente no Google Colab com Drive montado.

Convencoes:

- A primeira celula executavel deve montar o Google Drive quando o notebook depender de `FALANDO_NELA_DATA_ROOT`.
- O clone/pull do repositorio e a instalacao de dependencias devem vir depois da montagem do Drive.
- Estes notebooks nao sao cadernos analiticos de artigo; eles existem para orquestrar coletas e validacoes.
- Cadernos de artigos devem ficar em outras subpastas de `notebooks/`, separadas por tema ou artigo.
- Notebooks de datasets diferentes podem rodar ao mesmo tempo se cada um usar `run_id` distinto.
- Nao rode duas instancias do mesmo notebook/dataset com o mesmo `run_id`; retome com `--resume` apenas depois que a execucao anterior parar.
- `logs/` e `manifests/` sao indexados somente por `run_id`, entao trate o `run_id` como identificador global da execucao.
- A combinacao `coleta_camara_plenario.ipynb`, `coleta_senado_ccj_complemento.ipynb`, `coleta_camara_ccjc.ipynb`, `coleta_senado_pareceres_pec.ipynb` e `coleta_camara_pareceres_pec.ipynb` e suportada em paralelo com os `run_id`s padrao desses cadernos.

Arquivos atuais:

- 07_auditoria_cobertura_discursos_senadores_2010_colab.ipynb: auditoria
  isolada e retomável da cobertura de CodigoPronunciamento de senadores desde
  2010. Consulta exclusivamente por CodigoParlamentar, compara com o raw e não
  altera bases ou derivados.

- 08_backfill_discursos_senadores_por_codigo_2010_colab.ipynb: recuperação
  exclusiva da população apontada pelo caderno 07. Baixa cada texto pelo
  CodigoPronunciamento, preserva o CodigoParlamentar como proveniência e exige
  reauditoria completa antes de derivados. Depois do gate aprovado, preservar
  o resumo e aguardar o snapshot v2; o antigo caderno 07 foi arquivado.

- 09_recuperacao_discursos_plenario_2010_colab.ipynb: fecha a recuperação de
  2010 antes dos derivados. Para CN, transforma códigos que existam no raw mas
  não tenham texto em população fixa e extrai o trecho correspondente do Diário
  do Congresso Nacional oficial; para Câmara, coleta por `id` oficial do
  deputado. O caderno só libera o processamento quando os dois inventários
  tiverem texto/transcrições e manifests aprovados.

- 10_sondagem_transcricoes_audiovisuais_plenario_colab.ipynb: inventaria
  discursos atuais sem texto na Câmara e no Senado. Como
  `DiscursosTodos.parquet` contém apenas Senado, recupera somente os textos
  senatoriais e produz `camara_media_download_queue.parquet` para a aquisição
  posterior da Câmara. Não baixa mídia nem executa ASR; grava somente em
  `operations/` sob confirmação explícita.

- 11_auditoria_transcricoes_e_amostras_plenario_colab.ipynb: revisa, sem
  promover, as saídas operacionais do caderno 10. Recalcula hashes dos aceitos,
  separa causas de conflito, amostra vínculos manuais, distribui os não
  encontrados por ano e mede a cobertura texto/mídia da Câmara por unidade
  única. Também exibe amostras integrais reproduzíveis de 2010, 2015 e 2016 em
  Câmara, Senado e Congresso, com amostra extra de proveniência do Diário.

- 12_promocao_transcricoes_legadas_plenario_colab.ipynb: promove somente os
  471 textos do Senado aceitos por chave forte e aprovados na revisão visual de
  30%. Em uma segunda operação, regenera `processed`/Parquets e remove
  conservadoramente cabeçalhos e rodapés dos 83 textos recuperados do Diário,
  sem alterar o raw. As mutações começam desligadas e o caderno valida drift
  por fingerprints antes/depois.

- `00_auditoria_configuracao_atualizacao_colab.ipynb`: audita o Drive e grava,
  sob confirmacao explicita, o controle do ciclo `20260713`.
- `01_atualizacao_parlamentares_colab.ipynb`: atualiza deputados e senadores e
  regenera `parlamentares/v1` antes das faixas da Camara.
- `02_atualizacao_senado_colab.ipynb`: permite registrar, com confirmacao, o
  adiamento exato de `2015-05` da CCJ historica quando a analise excluir essa
  base; depois prossegue com Plenario, CCJ incremental, pareceres de PEC e
  apartes. O manifest permanece `completed_with_errors` e a excecao fica em
  `operations/atualizacao/ciclos/20260713/deferred_collections.json`. Nao
  edite manualmente checkpoint ou raw.
- `03_backfill_congresso_textos_colab.ipynb`: valida e executa o backfill
  textual mensal do Congresso desde `1996-05-01`.
- `04_atualizacao_camara_demais_bases_colab.ipynb`: recupera a CCJC historica e
  atualiza CCJC, pareceres de PEC e apartes da Camara.
- `05_atualizacao_camara_plenario_colab.ipynb`: coleta somente a sobreposicao
  `2026-05-01` a `2026-07-13`. Copia o plano de mandatos para o disco efemero
  do runtime e preserva, sem executar, o run historico iniciado em 1946. O
  controle valida a identidade exata dessa exclusao e o caderno 06 a arquiva
  separadamente do manifest incremental.

- `coleta_template.ipynb`: template geral para rodar todos os coletores, incluindo pareceres de PEC.
- `coleta_backfill_historico_colab.ipynb`: orquestrador Colab para backfill historico longo de todas as bases, com `run_id`s fixos, `--resume`, validacao curta, auditoria de layout raw, processamento, Parquets e samples.
- `coleta_senado_plenario.ipynb`: fluxo especifico para validar e rodar a coleta do Plenario do Senado.
- `coleta_senado_ccj.ipynb`: fluxo especifico para validar e rodar a coleta de notas da CCJ do Senado.
- `coleta_senado_ccj_complemento.ipynb`: fluxo especifico para complementar lacunas de notas da CCJ do Senado ate 2024.
- `coleta_senado_pareceres_pec.ipynb`: fluxo especifico para validar e rodar a coleta de pareceres, relatorios e avulsos de parecer de PEC no Senado.
- `coleta_camara_plenario.ipynb`: fluxo especifico para validar e rodar a coleta de discursos do Plenario da Camara por deputado.
- `coleta_camara_ccjc.ipynb`: fluxo especifico para validar e rodar a coleta de eventos e notas da CCJC da Camara via Escriba.
- `coleta_camara_pareceres_pec.ipynb`: fluxo especifico para validar e rodar a coleta de pareceres, votos em separado e pareceres vencedores de PEC na Camara.
- `coleta_parlamentares.ipynb`: fluxo transversal para validar, coletar e processar metadados de deputados e senadores para juncao com os textos parlamentares.
- `coleta_senado_plenario_apartes.ipynb`: fluxo metadata-only para apartes do Plenario do Senado.
- `coleta_camara_plenario_apartes.ipynb`: fluxo metadata-only para apartes do Plenario da Camara via Banco de Discursos/Sitaq.

Os notebooks de apartes podem rodar antes do backfill historico completo de
discursos, desde que usem `run_id`s distintos e gravem apenas em `metadata/`.
Os coletores de apartes usam preflight anual e trimestral para evitar consultas
mensais vazias no recorte historico amplo; trimestres positivos sao expandidos
para meses.

Na Camara, `coleta_camara_plenario.ipynb`,
`coleta_camara_plenario_apartes.ipynb` e o backfill historico geral devem
aproveitar `processed/parlamentares/v1` quando existir. Os coletores leem
`parlamentares_periodos` para mapear deputados por ano de mandato e evitar
consultas de deputados fora de exercicio; se a tabela ainda nao existir, eles
voltam ao fallback oficial pela API. Em coleta completa, uma tabela muito
pequena e tratada como amostra insuficiente.

No caderno `coleta_backfill_historico_colab.ipynb`, a etapa de
`parlamentares/v1` deve rodar antes dos coletores textuais lentos da Camara
quando o backfill completo estiver ligado.
Essa etapa usa `--skip-existing-id-scan` para evitar uma varredura inicial
silenciosa de todo o Drive; o coletor ainda imprime progresso nas listagens e a
cada lote de parlamentares.
Ela tambem usa `--skip-detail-endpoints` para gerar rapidamente o plano de
mandatos por legislatura. Depois, rode a coleta completa de parlamentares sem
essa flag quando precisar dos metadados enriquecidos de genero/detalhe.

Depois da coleta raw de apartes, a geracao da tabela e do Parquet deve ser feita
em `notebooks/processamento/geracao_apartes_parlamentares_colab.ipynb`. Esse
processamento ignora os probes anuais/trimestrais para as linhas analiticas e
usa `parlamentares/v1` como fonte de genero, partido e UF por data.

No backfill textual, consultas anuais ou trimestrais podem existir apenas como
preflight em `metadata/`. O corpus textual em `ano=YYYY/mes=MM/` deve ser
formado somente por requisicoes mensais; o caderno de backfill audita esse
contrato antes do processamento.

No backfill historico geral, `camara/plenario_discursos` deve usar
`1946-01-01` como inicio operacional, respeitando a cobertura documentada do
Banco de Discursos da Camara. O intervalo `1900-01-01` a `1945-12-31` deve ser
tratado apenas como diagnostico separado de anomalias, se necessario.

Para os discursos do Senado no endpoint `plenario/lista/discursos`, o caderno
de backfill deve usar os inicios operacionais encontrados por probes mensais:
`1995-02-01` para `senado/plenario_discursos` e `1996-05-01` para
`senado/congresso_discursos`. Esse endpoint rejeita janelas trimestrais/anuais,
entao esses dois coletores continuam mensais.

No ciclo `20260713`, execute primeiro os cadernos 00 e 01. Depois, os cadernos
02 a 05 podem rodar em paralelo ou em ondas, desde que nunca existam duas
execucoes simultaneas do mesmo dataset. Todas as celulas longas ficam
desativadas por default, usam datas e `run_id`s do controle ativo, imprimem
saida continuamente e retomam com `--resume`.

Os sete cadernos do ciclo sao gerados de forma reproduzivel com `nbformat`:

```bash
python scripts/generate_update_colab_notebooks.py
```

O gerador valida o schema do notebook antes de gravar cada `.ipynb`; a suite
local tambem compila individualmente todas as celulas de codigo.

O antigo caderno isolado da recuperação 2015–2016 e seu gerador foram
arquivados em
`notebooks/arquivo/analise_plenario_v1_abortada_20260723/`. Seus dados
produzidos permanecem nas camadas canônicas e serão conferidos pelo inventário
do Drive.

O caderno de recuperação das transcrições legadas também tem gerador próprio:

```bash
python scripts/generate_video_transcription_probe_colab_notebook.py
python scripts/generate_video_transcription_probe_colab_notebook.py --check
```

A auditoria segura dessas saídas e das amostras históricas é gerada por:

```bash
python scripts/generate_video_transcription_audit_colab_notebook.py
python scripts/generate_video_transcription_audit_colab_notebook.py --check
```

A promoção revisada e o rebuild controlado são gerados por:

```bash
python scripts/generate_legacy_transcription_promotion_colab_notebook.py
python scripts/generate_legacy_transcription_promotion_colab_notebook.py --check
```
