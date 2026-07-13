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

- `00_auditoria_configuracao_atualizacao_colab.ipynb`: audita o Drive e grava,
  sob confirmacao explicita, o controle do ciclo `20260713`.
- `01_atualizacao_parlamentares_colab.ipynb`: atualiza deputados e senadores e
  regenera `parlamentares/v1` antes das faixas da Camara.
- `02_atualizacao_senado_colab.ipynb`: recupera a CCJ historica e atualiza
  Plenario, CCJ, pareceres de PEC e apartes do Senado. A recuperacao preserva
  o mesmo `run_id --resume`; respostas JSON interrompidas ou com HTTP 5xx sao
  subdivididas pelo coletor e, se necessario, o ultimo dia usa a agenda XML.
  Nao edite manualmente checkpoint ou raw.
- `03_backfill_congresso_textos_colab.ipynb`: valida e executa o backfill
  textual mensal do Congresso desde `1996-05-01`.
- `04_atualizacao_camara_demais_bases_colab.ipynb`: recupera a CCJC historica e
  atualiza CCJC, pareceres de PEC e apartes da Camara.
- `05_atualizacao_camara_plenario_colab.ipynb`: conclui o backfill historico do
  Plenario antes de iniciar a faixa incremental. Copia o plano de mandatos
  para o disco efemero do runtime, audita checkpoint/log e restringe o indice
  de duplicatas aos anos parciais quando esse escopo e comprovado. O stdout
  mostra o progresso da indexacao e heartbeats por lote de deputados.

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
