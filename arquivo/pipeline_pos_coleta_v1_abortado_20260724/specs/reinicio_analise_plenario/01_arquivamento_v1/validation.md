# Validação — arquivamento da análise v1

Status: **validação concluída em 2026-07-23**.

## Evidências obrigatórias

| Requisito | Evidência de aprovação |
|---|---|
| ARQ-R01, ARQ-R10 | tabela de migração com caminhos de origem e destino |
| ARQ-R02 | decisão D01 aprovada e destino idêntico ao mapa |
| ARQ-R03 | comparação de quantidade, tamanho e hash dos arquivos antes/depois |
| ARQ-R04 | checklist de notebooks, specs, revisões e referências operacionais |
| ARQ-R05 | leitura do `README.md` do arquivo sem depender de logs |
| ARQ-R06 | busca por referências locais quebradas após a mudança |
| ARQ-R07 | registro do marcador criado no Drive, ou decisão de não criá-lo |
| ARQ-R08 | busca que demonstre que a v1 não é entrada do snapshot v2 |
| ARQ-R09 | branch e commit registrados no índice |

## Testes de aceitação

1. O pesquisador identifica, pelo índice, a finalidade e o estado de cada
   notebook arquivado.
2. A quantidade de arquivos e o conjunto de hashes não diminuem após a
   migração.
3. Nenhum dado do Drive muda de caminho.
4. Nenhum notebook arquivado aparece na lista de notebooks operacionais.
5. A restauração dos caminhos antigos pode ser planejada apenas com a tabela de
   migração.

## Condições de reprovação

- arquivo ausente ou hash divergente;
- destino não aprovado;
- vínculo histórico perdido;
- saída da v1 consumida pelo pipeline v2 sem autorização;
- documentação que sugira que a v1 foi cientificamente validada.

## Evidência final esperada

Um relatório curto `relatorio_arquivamento.md`, acompanhado de
`mapa_arquivamento.csv`, deve registrar o resultado. O relatório não substitui
o índice permanente do diretório arquivado.
