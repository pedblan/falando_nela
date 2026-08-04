# Plano — refundação local-first do Falando Nela

## Estado

Contrato aprovado em `2026-08-03`; R01 e R02 foram concluídos e R02 foi
integrado localmente em `main` a partir da branch
`codex/refundacao-r02-foundation`. As etapas seguintes continuarão em branches
e worktrees próprias. Autorizações posteriores ficam limitadas às tarefas que
as registram; em R09, isso inclui a limpeza recuperável local e no Drive
aprovada em `2026-08-03`. Nenhuma operação paga foi autorizada.

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
- [x] Integrar a fundação validada em `main` por merge não destrutivo.

**Gate R02:** clone limpo instala com lockfile, roda lint e testes e recusa
produção quando `FALANDO_NELA_DATA_ROOT` não estiver configurado corretamente.

Evidência de `2026-08-03`: o commit R02
`341297f2d31021b765c9865a0d4e7e68cae4778a` foi integrado pelo merge
`c0563d249c8a0d0af36af9e37e24acba94b5ffef`; um clone limpo do estado
integrado passou em lockfile, Ruff, formatação, 189 testes e diagnóstico.

## R03 — piloto da amostra anual de 1% no Drive

- [x] Criar spec própria para inventário, amostragem anual e materialização do raw existente.
- [x] Aprovar a organização copy-first do raw em nova árvore canônica no Drive.
- [x] Criar spec operacional própria para a organização canônica do Drive.
- [x] Implementar e testar localmente inventário, preflight de destino vazio e mapa canônico retomável.
- [x] Renomear a raiz antiga para `falando_nela_arquivo`, preservando o ID `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB` e todo o conteúdo.
- [x] Confirmar que `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, permanece reserva e não será usada pela operação.
- [x] Implementar inspeção segura de configuração rclone cifrada e redigida, sem token em texto puro ou prompt.
- [x] Instalar rclone `>=1.64` e configurar a senha cifrada no Chaves do macOS.
- [x] Configurar remotes separados de origem read-only e destino gravável dedicado.
- [x] Criar pelo remote `drive.file` uma nova raiz operacional `falando_nela`, confirmar vazia e congelar seu ID por readback.
- [x] Congelar o mapeamento de plenários e comissões sem alterar conteúdo nem periodicidade.
- [x] Executar e revisar dry-run integral da cópia imutável.
- [x] Copiar e reconciliar um lote sentinela antes de ampliar.
- [x] Copiar em lotes retomáveis e validar a árvore canônica `data/raw/v1/`.
- [x] Expor a árvore canônica validada por remote read-only para a amostragem.
- [x] Confirmar humanamente a pasta raw de origem pelo ID `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`.
- [x] Configurar um remote `rclone` exclusivo com escopo `drive.readonly`.
- [x] Comparar a listagem atual do Drive com o inventário G01 aprovado.
- [x] Reconciliar pelo ID do provedor os dois arquivos acidentais que o rclone lista com o mesmo caminho `camara/plenario_discursos/ano=1900/Untitled`.
- [x] Gerar inventário somente leitura do corpus de origem sem chamar APIs parlamentares.
- [x] Definir a população ativa do piloto por data substantiva em 2010.
- [x] Escolher o primeiro ano não vazio do estrato `senado × plenario_discursos × pronunciamento_texto`.
- [x] Contar a população `N` do estrato e persistir identidades, chaves e locators.
- [x] Calcular `k=max(1, ceil(N × 0.01))` e congelar as `k` menores chaves.
- [x] Materializar somente os registros selecionados sem alterar a origem.
- [x] Compactar a amostra fechada como gzip determinístico.
- [x] Reconciliar população, selecionados, identidades, hashes, bytes e rejeições.
- [x] Encerrar a operação após publicar raw e metadados técnicos, sem produzir Parquet, DuckDB ou análise.
- [x] Reexecutar a mesma operação e comprovar idempotência.
- [x] Injetar interrupção entre cada etapa e comprovar retomada sem repetir etapa concluída.

**Gate R03:** árvore canônica copy-first reconciliada sem alterar a origem; raw
e manifest do estrato piloto aprovados; quota exata da meta anual de 1%; zero
chamada de coleta; periodicidade preservada e retomada demonstrada.

Evidência de bootstrap de `2026-08-03`: o projeto Google Cloud
`falando-nela-pedblan` tem Drive API, app OAuth externo em teste e cliente
desktop próprio. O rclone 1.75.0 usa configuração cifrada fora do clone,
desbloqueada pelo Chaves do macOS, com os remotes `raw-source-ro`
(`drive.readonly`, raiz `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`) e
`raw-destination-rw` (`drive.file`, raiz
`17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`). O primeiro listou `camara/` e
`senado/`; o segundo criou `falando_nela`, registrou seu ID por readback e
confirmou zero entrada dentro da nova raiz. A listagem integral da origem
reproduziu a manchete G01 de 2.891 arquivos e 14.686.044.612 bytes. A operação
recuperável `r03-g01-reconcile-20260803` autenticou localmente o CSV G01 pelo
SHA-256 `1ab73d3173454b4f556eff02cd202d0dd76740dd7d42d8e24093785dd0cc21a6`
e confirmou zero ausência, acréscimo ou alteração. Os 2.887 JSONL formam o raw
elegível; os dois notebooks e os dois arquivos sem extensão receberam exclusão
explícita. Como a baseline não contém IDs, os dois `Untitled` de mesmo caminho,
tamanho e hash foram preservados como um grupo de equivalência com dois IDs do
Drive ligado ao par G01 `Untitled`/`Untitled (1)`, sem atribuição heurística
individual. A reexecução reutilizou as duas etapas concluídas, cada uma com uma
única tentativa. A operação `r03-drive-dry-run-20260803` congelou e ensaiou
2.887 destinos, 14.686.043.352 bytes, com 70 arquivos metadata, 2.811 de corpus
mensal e seis de fila de transcrição. Os quatro itens não raw, 1.260 bytes,
foram excluídos pelo ID. O relatório combinado contém exatamente 2.887
marcadores `+`, nenhum outro marcador, e o readback posterior confirmou o
destino vazio. A preparação bloqueou uma vez ao encontrar os dez JSONL
metadata-only de `camara/parlamentares` e `senado/parlamentares`; eles foram
incluídos explicitamente pelo contrato raw transversal e a segunda tentativa
concluiu. A etapa remota de dry-run concluiu na primeira tentativa e a
reexecução não a repetiu. Nenhum arquivo raw foi copiado.

Evidência posterior de conclusão em `2026-08-03`: o sentinela validou três
arquivos e 78.822 bytes. A operação `r03-drive-copy-batched-20260803` executou
38 lotes, reconciliou 2.887 arquivos e 14.686.043.352 bytes, publicou catálogo
final e relistou a origem com 2.891 arquivos e 14.686.044.612 bytes
inalterados. A operação `r03-sample-pilot-2010-20260803` confirmou 11 arquivos,
89.253.442 bytes, `N=2.996` e `k=30`; publicou somente os 30 registros
selecionados em gzip determinístico e foi reexecutada com zero nova leitura e
zero duplicação. Google Cloud Batch, Marimo e a ampliação para outros estratos
permanecem fora de R03.

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

- [x] Abrir tarefa própria para caracterizar o legado local e manter os notebooks rastreados somente para consulta.
- [x] Inventariar as cópias locais antigas e as dez raízes antigas autorizadas no Drive.
- [x] Preservar e reconciliar os 106 notebooks do Drive em biblioteca de consulta.
- [x] Retirar as duas árvores de dados locais para a Lixeira do macOS após catálogo completo.
- [x] Enviar as dez raízes antigas do Drive à Lixeira, inclusive `falando_nela_arquivo`, sem esvaziá-la.
- [x] Procurar referências restantes e revalidar a árvore raw canônica depois da limpeza.
- [x] Atualizar specs e documentação no mesmo ciclo; nenhum notebook rastreado foi removido.

R09 foi executado em tarefas próprias de limpeza local e remota. Os contratos e
evidências estão em `r09_limpeza_local/` e `r09_limpeza_drive/`. Ideias
adicionais, novas bases, correções de coleta, mudança de schema, análise
científica e publicação permanecem fora do escopo.

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
