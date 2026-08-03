# Plano — refundação local-first do Falando Nela

## Estado

Contrato aprovado em `2026-08-03`; implementação incremental iniciada na
branch `codex/refundacao-r02-foundation`, em worktree própria a partir de
`main`. Nenhuma migração real, remoção ou operação paga foi autorizada por essa
aprovação.

## Resultado principal

Entregar, no mesmo repositório Git, uma linha local-first capaz de processar e
inspecionar uma amostra anual determinística de 1% dos dados já coletados de
2010 em diante, produzir derivados reproduzíveis, gerar backup restaurável e
executar operações integrais sob demanda no Google Cloud ou num SSD local, sem
depender de Colab e sem refazer a coleta.

## Regra de execução

Cada etapa abaixo é uma unidade de trabalho própria, com branch, spec
operacional e validação proporcionais. A aprovação destas quatro specs não
autoriza executar automaticamente a etapa seguinte. Remoção de legado e
exclusão de dados permanecem tarefas separadas.

## R00 — contrato da refundação

- [x] Confirmar que o nome, o remote e o histórico de `falando_nela` serão preservados.
- [x] Confirmar que o corpus existente será migrado sem nova coleta histórica.
- [x] Inspecionar branch, worktree, alterações pendentes, specs, notebooks e pressupostos de Colab.
- [x] Isolar estas specs na branch `codex/refundacao-local-first` sem tocar em `migrar-para-disco`.
- [x] Revisar humanamente `requirements.md`.
- [x] Revisar humanamente `tech-stack.md`.
- [x] Revisar humanamente `validation.md`.
- [x] Aprovar humanamente as quatro specs como contrato da refundação.

**Gate R00:** quatro specs aprovadas e nenhuma divergência conhecida entre
objetivo, requisitos, stack e validação.

## R01 — congelar a linhagem anterior

- [x] Concluir, arquivar ou rejeitar explicitamente as alterações pendentes de `migrar-para-disco`.
- [x] Executar os testes relevantes da última revisão centrada em Colab.
- [x] Registrar o commit estável que encerra essa linhagem.
- [x] Criar a tag anotada `legacy-colab-final` nesse commit.
- [x] Publicar branch e tag por fluxo não destrutivo.
- [x] Inventariar módulos, notebooks, geradores, testes e specs ainda necessários como fontes de migração.

**Gate R01:** nenhuma alteração de usuário solta, tag recuperável no remote e
inventário do legado aprovado. A criação da tag não remove nem move arquivos.

Evidência de `2026-08-03`: `main` e a tag anotada `legacy-colab-final` apontam
para o commit `782c337bf412ae33f9079dd87b68dedcd7a3ad92`; 176 testes passaram
tanto na worktree candidata quanto em clone limpo da tag. O inventário foi
registrado em `docs/refundacao/inventario_legado_colab_20260803.md`.

## R02 — fundação executável local

- [x] Criar spec operacional própria para o scaffold local-first.
- [x] Introduzir `pyproject.toml`, `.python-version`, `uv.lock` e layout `src/falando_nela/`.
- [x] Definir o entrypoint `falando-nela` e configuração validada por ambiente.
- [x] Criar o perfil local com limite de 4 GiB, quatro threads e spill em disco.
- [x] Adicionar fixtures mínimas fora da área de dados de produção.
- [x] Configurar pytest, Ruff e CI sem acesso externo.
- [x] Comprovar instalação limpa e execução de um comando diagnóstico.

**Gate R02:** clone limpo instala com lockfile, roda lint e testes e recusa
produção quando `FALANDO_NELA_DATA_ROOT` não estiver configurado corretamente.

## R03 — piloto da amostra anual de 1% no Drive

- [ ] Criar spec própria para inventário, amostragem anual e materialização do raw existente.
- [ ] Confirmar humanamente a pasta raw de origem pelo ID `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`.
- [ ] Configurar um remote `rclone` exclusivo com escopo `drive.readonly`.
- [ ] Comparar a listagem atual do Drive com o inventário G01 aprovado.
- [ ] Gerar inventário somente leitura do corpus de origem sem chamar APIs parlamentares.
- [ ] Definir a população ativa por data substantiva a partir de `2010-01-01`.
- [ ] Escolher o primeiro ano não vazio do estrato `senado × plenario_discursos × discurso`.
- [ ] Contar a população `N` do estrato e persistir identidades, chaves e locators.
- [ ] Calcular `k=max(1, ceil(N × 0.01))` e congelar as `k` menores chaves.
- [ ] Materializar somente os registros selecionados sem alterar a origem.
- [ ] Compactar a amostra fechada como gzip determinístico.
- [ ] Reconciliar população, selecionados, identidades, hashes, bytes e rejeições.
- [ ] Encerrar a operação após publicar raw e metadados técnicos, sem produzir Parquet, DuckDB ou análise.
- [ ] Reexecutar a mesma operação e comprovar idempotência.
- [ ] Injetar interrupção entre cada etapa e comprovar retomada sem repetir etapa concluída.

**Gate R03:** raw e manifest do estrato piloto aprovados, quota exata da meta
anual de 1% segundo o contrato, zero chamada de coleta, origem intacta e
retomada demonstrada.

## R04 — primeiro recorte vertical amostral em marimo

- [ ] Criar spec própria para o recorte vertical selecionado em R03.
- [ ] Iniciar o processamento sob novo `operation_id`, consumindo somente o raw local publicado em R03.
- [ ] Portar somente os leitores e validadores necessários ao recorte.
- [ ] Ler `.jsonl` e `.jsonl.gz` pela mesma interface.
- [ ] Materializar Parquet Zstandard com schema e proveniência explícitos.
- [ ] Consultar o resultado com DuckDB dentro do orçamento local de recursos.
- [ ] Criar um caderno marimo fino para parâmetros, inspeção e apresentação.
- [ ] Exibir em toda saída a marca `AMOSTRA ANUAL DE DESENVOLVIMENTO — NÃO É O CORPUS INTEGRAL`.
- [ ] Executar o caderno em modo script sem interação humana.
- [ ] Comparar contagens e hashes entre raw, Parquet, query e caderno.

**Gate R04:** um comando reproduz o recorte local de ponta a ponta e o caderno
passa em `marimo check`, modo script e revisão humana.

## R05 — backup restaurável

- [ ] Criar spec operacional do backup versionado.
- [ ] Configurar remote Google Drive com credencial fora do Git.
- [ ] Gerar `backup_id`, catálogo SHA-256 e dry-run do conjunto R04.
- [ ] Copiar o conjunto para `falando_nela/backups/<backup_id>/` sem sincronizar exclusões.
- [ ] Verificar o remote por catálogo, tamanho e hashes suportados.
- [ ] Restaurar o backup em diretório local vazio.
- [ ] Reexecutar a validação do recorte restaurado.

**Gate R05:** restauração integral do piloto comprovada. A existência do upload
sem restore não fecha o gate.

## R06 — amostra anual local completa

- [ ] Revalidar tamanhos e hashes do Drive contra o inventário G01 antes da cópia.
- [ ] Congelar os estratos por fonte, dataset, tipo e ano a partir de 2010.
- [ ] Criar o estrato auxiliar `undated` sem promovê-lo ao corpus analítico anual.
- [ ] Preservar rejeições e casos raros no conjunto separado `sentinels`.
- [ ] Executar `inventory` e `rank` em streaming para todos os estratos.
- [ ] Congelar um único manifest global com população e quota exata da meta de 1% por estrato.
- [ ] Publicar a seleção sob novo `sample_id` imutável, sem alterar amostra anterior no próprio lugar.
- [ ] Materializar do Drive apenas os registros selecionados pelo manifest.
- [ ] Interromper a publicação se raw, manifests, índices técnicos e temporários da importação, somados aos derivados locais existentes, excederem 2 GiB.
- [ ] Validar que permanecem pelo menos 5 GiB livres depois da materialização.
- [ ] Publicar somente raw amostral, manifests, índices técnicos e relatório de cobertura por estrato.
- [ ] Encerrar a operação de importação antes de iniciar qualquer derivado multianual.
- [ ] Criar backup imutável da amostra e executar restauração integral.
- [ ] Aprovar humanamente o manifest, a cobertura, `undated`, sentinelas e rejeições.

**Gate R06:** amostra raw local de 1% completa, rotulada, reconciliada e
restaurável; raw integral permanece preservado no Drive, não foi copiado
integralmente nem excluído e nenhum derivado foi produzido pela importação.

## R07 — prova opcional de computação sob demanda

- [ ] Criar spec própria com hipótese, recursos, região, timeout e estimativa vigente.
- [ ] Construir e executar localmente a imagem OCI usando o lockfile.
- [ ] Preparar staging somente com o estrato piloto aprovado em R03.
- [ ] Obter autorização humana para um gasto total máximo de US$ 5,00.
- [ ] Submeter um único job Google Cloud Batch sem Spot VM.
- [ ] Baixar manifest e raw amostral e compará-los byte a byte com a execução local.
- [ ] Injetar uma interrupção e retomar pelo identificador remoto sem duplicar o job confirmado.
- [ ] Remover staging e inventariar qualquer recurso ou custo residual.
- [ ] Documentar o profile `full` como operação distinta, sem executá-lo no piloto.

**Gate R07:** equivalência local/cloud comprovada dentro do teto. Este gate não
bloqueia o uso local nem autoriza ampliar o job.

## R08 — corte operacional local-first

- [ ] Atualizar missão, roadmap, stack raiz e READMEs para declarar local-first como caminho oficial.
- [ ] Documentar amostra local, execução integral, configuração, backup e restauração em máquina limpa.
- [ ] Confirmar que nenhuma operação oficial exige montar Drive ou abrir Colab.
- [ ] Confirmar que outputs amostrais não podem ser confundidos com resultados integrais.
- [ ] Confirmar que os contratos v3 aprovados continuam referenciáveis.
- [ ] Integrar a linha aprovada em `main` por fluxo sem reescrita de histórico.
- [ ] Publicar `main` e verificar o remote `pedblan/falando_nela`.
- [ ] Atualizar o checkout canônico `falando_nela` por fast-forward até a `main` publicada.
- [ ] Confirmar que `falando_nela` e `origin/main` apontam para o mesmo commit e passam na validação final.
- [ ] Confirmar que a worktree `falando_nela_refundacao` não contém alterações ou commits exclusivos.
- [ ] Remover `falando_nela_refundacao` com `git worktree remove` e verificar o registro de worktrees.

**Gate R08:** `main` local-first verificável, com mesmo nome e histórico do
repositório, checkout canônico atualizado, worktree temporária removida com
segurança e caminho documentado até o legado etiquetado.

## R09 — remoções posteriores e independentes

- [ ] Abrir tarefa própria para caracterizar e remover notebooks e geradores Colab substituídos.
- [ ] Abrir tarefa própria para inventariar e copiar o universo anterior a 2010 para arquivo imutável.
- [ ] Restaurar e reconciliar o arquivo anterior a 2010 em diretório vazio.
- [ ] Abrir tarefa própria para retirar cópias locais anteriores a 2010 após restore e aprovação humana.
- [ ] Procurar referências restantes antes de cada remoção.
- [ ] Atualizar specs, testes, documentação e empacotamento no mesmo ciclo de cada remoção.

R09 não faz parte do critério de conclusão da refundação. Ideias adicionais,
novas bases, correções de coleta, mudança de schema, análise científica e
publicação permanecem fora do escopo.

## Fronteiras de custo e interrupção

- Amostragem e backup começam por um único estrato anual e uma única restauração.
- Nenhuma chamada paga é autorizada por estas specs.
- O primeiro piloto Google Cloud tem no máximo uma submissão e US$ 5,00 após
  autorização humana específica.
- Três falhas equivalentes sem nova hipótese interrompem a etapa para
  diagnóstico.
- Divergência entre origem, manifest, conteúdo descompactado, Parquet ou
  restauração bloqueia ampliação e exclusão.

## Critério de conclusão

A refundação termina em R08 quando o mesmo repositório oferece um caminho
local-first documentado e reproduzível, a amostra anual de 1% desde 2010 foi
materializada sem recoleta, rotulada e restaurada com sucesso, o corpus
integral continua preservado e executável sob profile próprio e o legado
permanece recuperável. Operações integrais pagas e remoções posteriores
conservam gates e tarefas próprios.
