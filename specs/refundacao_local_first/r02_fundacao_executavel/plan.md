# Plano operacional — R02 fundação executável local

- [x] Delimitar objetivo, requisitos, não objetivos, casos e validação de R02.
- [x] Criar metadados de projeto, grupos de dependências e lockfile.
- [x] Criar o pacote `src/falando_nela/` e o entrypoint `falando-nela`.
- [x] Implementar configuração validada e diagnóstico sem rede.
- [x] Implementar primitivas raw preparatórias sem importar dados.
- [x] Adicionar fixtures, testes unitários e testes da CLI.
- [x] Configurar Ruff e CI sem credenciais ou acesso externo.
- [x] Executar instalação locked, lint, formatação, testes e diagnóstico.
- [x] Revisar o diff e sincronizar o contrato principal.

## Gate

R02 termina somente quando uma instalação limpa pelo lockfile passa em todas as
verificações, o diagnóstico válido funciona e configurações perigosas falham de
modo explícito. O gate não autoriza R03.
