# Missao

O `falando_nela` e um projeto de pesquisa computacional dedicado a analisar empiricamente o conteudo constitucional em discursos e debates parlamentares brasileiros.

O objetivo primario e estudar como temas constitucionais aparecem, circulam e sao disputados em pronunciamentos, debates e registros parlamentares, com foco na construcao de dados rastreaveis e analises reprodutiveis.

## Escopo de coleta

As fontes-alvo sao:

- Plenario do Senado Federal.
- Plenario do Congresso Nacional.
- Plenario da Camara dos Deputados.
- Comissao de Constituicao, Justica e Cidadania do Senado Federal.
- Comissao de Constituicao e Justica e de Cidadania da Camara dos Deputados.
- Pareceres, relatorios e documentos equivalentes de PEC no Senado Federal e
  na Camara dos Deputados.
- Metadados de parlamentares necessarios para juncao temporal com os textos.

A diretriz de coleta e maximizar a cobertura historica auditavel: cada fonte
deve ser consultada ate a data mais antiga em que a fonte oficial entregue dados
uteis, preservando lacunas, falhas e mudancas de formato como metadados de
proveniencia. Para analises substantivas, o recorte `2010-01-01` em diante e o
default recomendado, porque a qualidade e a regularidade dos dados anteriores a
2010 tendem a ser piores. Dados anteriores a 2010 podem entrar no corpus, mas
devem ser marcados como historicos e de menor confianca.

## Principios

- Rastreabilidade: cada dado coletado deve preservar referencia a fonte, data, identificadores disponiveis e metodo de obtencao.
- Reprodutibilidade: coletas e analises devem poder ser refeitas a partir de parametros, scripts e ambientes documentados.
- Separacao entre coleta e analise: o modulo de coleta deve produzir dados organizados para consumo posterior por cadernos analiticos.
- Prioridade textual: sempre que disponivel, a coleta deve transferir o texto integral dos discursos, debates, sessoes ou reunioes, deixando metadados e resumos como contexto, nao como corpus analitico principal.
- Separacao entre metadados e corpus: respostas de lista, descoberta e contexto devem ser preservadas em area propria de `metadata`, sem inflar os arquivos mensais de registros textuais.
- Versionamento por specs: mudancas relevantes de escopo, metodo, dados e tecnologia devem ser registradas em especificacoes antes da implementacao.
- Execucao adequada ao ambiente: testes locais devem ser leves e usar apenas uma parcela estratificada dos dados; coletas longas devem ser preparadas para execucao confiavel no Google Colab.
- Specs sempre atualizadas: novos notebooks operacionais, mudancas de janela
  historica, criterios de qualidade e regras de limpeza textual devem atualizar
  as specs correspondentes no mesmo ciclo de trabalho.
