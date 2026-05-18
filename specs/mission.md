# Missao

O `falando_nela` e um projeto de pesquisa computacional dedicado a analisar empiricamente o conteudo constitucional em discursos e debates parlamentares brasileiros.

O objetivo primario e estudar como temas constitucionais aparecem, circulam e sao disputados em pronunciamentos, debates e registros parlamentares, com foco na construcao de dados rastreaveis e analises reprodutiveis.

## Escopo inicial

As fontes-alvo iniciais sao:

- Plenario do Senado Federal.
- Plenario do Congresso Nacional.
- Plenario da Camara dos Deputados.
- Comissao de Constituicao, Justica e Cidadania do Senado Federal.
- Comissao de Constituicao e Justica e de Cidadania da Camara dos Deputados.

A janela inicial de coleta cobre os ultimos quinze anos, usando como baseline o periodo de `2011-05-18` a `2026-05-18`. Esse intervalo deve ser parametrizavel em implementacoes futuras.

## Principios

- Rastreabilidade: cada dado coletado deve preservar referencia a fonte, data, identificadores disponiveis e metodo de obtencao.
- Reprodutibilidade: coletas e analises devem poder ser refeitas a partir de parametros, scripts e ambientes documentados.
- Separacao entre coleta e analise: o modulo de coleta deve produzir dados organizados para consumo posterior por cadernos analiticos.
- Versionamento por specs: mudancas relevantes de escopo, metodo, dados e tecnologia devem ser registradas em especificacoes antes da implementacao.
- Execucao adequada ao ambiente: testes locais devem ser leves e usar apenas uma parcela estratificada dos dados; coletas longas devem ser preparadas para execucao confiavel no Google Colab.
