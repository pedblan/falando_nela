# Tech stack — arquivamento da análise v1

Status: **contrato aprovado em 2026-07-23**.

Este documento especializa
[`../tech-stack.md`](../tech-stack.md). Só registra diferenças relevantes.

## Ferramentas

- Git e comandos de sistema somente para inventário e movimentação local
  explícita.
- Python padrão (`pathlib`, `hashlib`, `csv`) para gerar o mapa e verificar
  hashes.
- Markdown e CSV para o índice e o mapa de arquivamento.
- Conector do Google Drive apenas para inspeção e, se D02 for aprovada, criação
  do marcador autorizado.

## Restrições

- Não usar OpenAI API.
- Não regravar notebooks para “limpá-los”.
- Não usar comandos destrutivos nem movimentações recursivas com alvo
  implícito.
- Não copiar conteúdo do Drive para reorganizá-lo nesta etapa.
- Não transformar o arquivamento em migração de dados.
