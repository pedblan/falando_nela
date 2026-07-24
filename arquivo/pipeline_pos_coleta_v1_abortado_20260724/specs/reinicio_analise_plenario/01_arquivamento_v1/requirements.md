# Requisitos — arquivamento da análise v1

Status: **implementado em 2026-07-23 — validação concluída**.

## Objetivo

Encerrar a tentativa de análise v1 de forma reversível e compreensível,
preservando notebooks, specs, revisões humanas e referências aos artefatos do
Colab. Arquivar não significa validar nem promover os resultados científicos
da v1.

## Contrato funcional

- **ARQ-R01 — inventário prévio:** antes de qualquer renomeação, deve existir
  uma lista dos arquivos locais em escopo, com caminho original, tipo e destino
  proposto.
- **ARQ-R02 — destino explícito:** o caminho recomendado é
  `notebooks/arquivo/analise_plenario_v1_abortada_20260723/`, condicionado à
  aprovação da decisão D01.
- **ARQ-R03 — preservação:** nenhum arquivo da v1 pode ser apagado, truncado ou
  sobrescrito.
- **ARQ-R04 — conteúdo:** devem ser preservados, quando existirem, notebooks,
  specs correspondentes, arquivos de revisão manual, referências de commits,
  IDs de Batch e caminhos de saídas.
- **ARQ-R05 — índice humano:** o arquivo deve conter um `README.md` que explique
  por que a tentativa foi encerrada, o que cada notebook pretendia fazer, quais
  saídas produziu e por que essas saídas não devem ser tratadas como resultado
  científico final.
- **ARQ-R06 — referências internas:** renomeações locais devem atualizar apenas
  referências documentais necessárias para localizar o material arquivado.
  Elas não podem alterar silenciosamente contratos históricos.
- **ARQ-R07 — Drive:** a execução antiga no Drive não deve ser movida nem
  apagada nesta etapa. Se D02 for aprovada, deve receber apenas um marcador
  legível informando `encerrada_sem_validacao_cientifica`.
- **ARQ-R08 — dados:** os dados produzidos pela v1 permanecem imutáveis e fora
  da cadeia de entrada do snapshot v2, salvo decisão posterior documentada.
- **ARQ-R09 — proveniência:** o índice deve registrar a branch e o commit que
  representam o último estado conhecido da v1.
- **ARQ-R10 — reversibilidade:** deve ser possível reconstruir o mapeamento
  `caminho_original -> caminho_arquivado` sem consultar logs do terminal.

## Fora de escopo

- corrigir ou reexecutar notebooks da v1;
- validar a segmentação produzida;
- reutilizar classificações científicas da v1;
- apagar Batches, relatórios ou diretórios no Drive;
- decidir o desenho da nova análise.

## Gate humano

A implementação exige aprovação explícita de:

1. caminho de destino (D01);
2. lista exata de arquivos em escopo;
3. texto do marcador do Drive (D02), caso ele seja criado.
