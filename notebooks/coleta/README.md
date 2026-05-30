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

No backfill textual, consultas anuais ou trimestrais podem existir apenas como
preflight em `metadata/`. O corpus textual em `ano=YYYY/mes=MM/` deve ser
formado somente por requisicoes mensais; o caderno de backfill audita esse
contrato antes do processamento.
