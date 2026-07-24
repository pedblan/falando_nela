# Validation: reinício controlado da análise de plenário

Status: **contrato aprovado em 2026-07-23**.

## Aprovação documental

- Os quatro tipos de documento existem no módulo geral e em cada submódulo.
- Cada requisito normativo usa linguagem verificável.
- Decisões pendentes estão identificadas e bloqueiam implementação.
- Não há conflito de caminhos, IDs ou responsabilidades entre os documentos.
- Cada decisão D01–D06 foi aprovada antes da etapa que depende dela.

## Preservação

- O hash e a quantidade de arquivos da execução abortada são registrados antes
  de qualquer operação.
- Nenhum arquivo antigo desaparece após arquivamento ou catalogação.
- O snapshot v1 e seus relatórios continuam acessíveis.
- Os Batches e revisões existentes permanecem referenciáveis.

## Separação operacional

- Testes demonstram que `snapshot_id`, `analysis_run_id` e `operation_id` não
  são intercambiáveis.
- Notebooks de dados não gravam em diretórios de análise.
- Notebooks analíticos não leem diretamente `raw` nem logs operacionais.
- Uma análise referencia o snapshot por ID, caminho e hash.

## Clareza dos relatórios

Para cada notebook piloto, um revisor deve conseguir responder, usando apenas
o relatório humano:

1. qual foi o objetivo;
2. qual universo entrou;
3. quantas linhas entraram e saíram;
4. quais arquivos foram produzidos;
5. quais avisos ou gates falharam;
6. qual é a próxima ação.

O revisor não deve precisar abrir o manifest técnico ou o log completo para
responder a essas perguntas.

## Segurança

- Inventário executa sem alterações no Drive.
- Migração permanece em dry-run por default.
- Nenhuma célula de produção executa por simples `Run all`.
- Credenciais não aparecem em notebook, relatório, manifest ou log.
- Operações destrutivas não existem no fluxo automatizado.

## Validação técnica futura

Quando notebooks forem implementados:

- validar JSON com `nbformat`;
- validar cada célula Python com `ast.parse`;
- executar testes locais com fixtures pequenas;
- verificar schemas de relatórios e manifests;
- executar `git diff --check`;
- comparar contagens e hashes antes/depois de qualquer cópia.

## Gate para iniciar a nova análise

A nova análise só pode receber sua primeira spec substantiva quando:

- o inventário estiver aprovado;
- o relatório de cobertura do snapshot estiver aprovado;
- o snapshot selecionado estiver congelado;
- o catálogo de dados explicar todos os inputs disponíveis;
- não houver decisão pendente sobre universo, período ou unidade básica.
