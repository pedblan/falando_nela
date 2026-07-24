# Inventário pré-arquivamento da análise v1

Status: **aprovado e executado em 2026-07-23**.

## Estado observado

| Campo | Valor |
|---|---|
| Branch | `main` |
| Commit | `64b313cfad8561a199a48b9c54b284f1409bc1cf` |
| Mensagem | `Refaz episódios multiturno do caderno 3` |
| Data do commit | `2026-07-23T20:39:15-03:00` |
| Alterações locais anteriores ao inventário | pacote novo `specs/reinicio_analise_plenario/`, ainda não versionado |
| Destino aprovado em D01 | `notebooks/arquivo/analise_plenario_v1_abortada_20260723/` |

O inventário detalhado e os hashes estão em
[`mapa_arquivamento.csv`](mapa_arquivamento.csv).

## Correção do primeiro inventário

O primeiro levantamento propunha reter o snapshot v1 porque dois cadernos
históricos ainda o importavam. O pesquisador observou que esses cadernos também
serão substituídos. A interpretação foi aprovada: imports de orquestradores
antigos não justificam manter o pipeline v1 ativo.

Os dados `raw` e `processed` produzidos por esses fluxos não entram no
arquivamento. A incorporação efetiva de seus resultados às bases canônicas será
verificada pelo inventário do Drive.

## Escopo ampliado proposto

São **53 arquivos versionados**, totalizando **794.298 bytes**:

- todo o pacote Python `analise/` da suíte v1;
- os 10 notebooks analíticos, seu README e sua célula auxiliar;
- as specs metodológicas da análise comparativa;
- três geradores de notebooks históricos;
- cinco testes exclusivos da análise ou dos orquestradores antigos;
- uma cópia integral do teste misto de discursos históricos;
- os dois orquestradores que ainda chamam o snapshot v1;
- as specs históricas dos dois ciclos de backfill associados.

Os destinos reproduzem o caminho original abaixo da raiz de arquivo. Isso
torna o movimento reversível sem depender do histórico do terminal.

`tests/test_discursos_historicos.py` é o único caso especial: a versão completa
será preservada no arquivo e o caminho ativo será recriado sem o import e o
teste exclusivos do snapshot v1. Os testes de coleta permanecerão ativos.

## Itens preservados fora do arquivo

- coletores e parsers oficiais;
- dados `raw`, `processed`, Parquets e snapshots já gravados;
- cadernos de coleta que não constroem o snapshot v1;
- normalização e geração de Parquets;
- auditorias e testes de coleta independentes da análise;
- specs gerais de coleta e processamento.

## Referências que deverão ser atualizadas

O movimento só poderá ser considerado concluído depois de remover ou substituir
referências ativas nos seguintes pontos:

- `notebooks/coleta/README.md`;
- `notebooks/processamento/README.md`;
- `notebooks/coleta/09_recuperacao_discursos_plenario_2010_colab.ipynb` e seu
  gerador;
- `processamento/README.md`;
- `processamento/apartes_parlamentares/{plan,requirements}.md`;
- `processamento/normalizacao_armazenamento/plan.md`;
- `specs/roadmap.md`.

As referências históricas dentro do arquivo não serão reescritas.

## Checkpoint humano

O pesquisador aprovou os 53 pares origem–destino de
`mapa_arquivamento.csv`, inclusive:

1. arquivar integralmente o pacote `analise/`;
2. arquivar os dois orquestradores de backfill/derivação que chamam o snapshot
   v1;
3. arquivar as specs, geradores e testes diretamente ligados a eles;
4. preservar no caminho ativo apenas a parte de
   `tests/test_discursos_historicos.py` independente do snapshot v1.

As ações aprovadas foram executadas:

1. os arquivos serão movidos;
2. o índice permanente do arquivo será criado;
3. o teste misto será separado;
4. referências ativas serão atualizadas;
5. notebooks remanescentes serão validados com `nbformat` e AST;
6. a suíte de testes será executada;
7. contagens, tamanhos e SHA-256 serão comparados;
8. será produzido o relatório final do arquivamento local.

O marcador D02 foi aplicado como operação separada e verificado por leitura de
metadados. O resultado completo está em
[`relatorio_arquivamento.md`](relatorio_arquivamento.md).
