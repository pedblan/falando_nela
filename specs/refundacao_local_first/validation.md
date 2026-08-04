# Validação — refundação local-first do Falando Nela

## Estado

Contrato de validação aprovado pelo usuário em `2026-08-03`. V00, V01 e V02
estão aprovados; comandos, migrações e gates seguintes exigem evidência própria.

## Princípios

- Sucesso de comando não substitui reconciliação de dados nem aprovação humana.
- Validações começam com fixtures e um único estrato anual antes de alcançar a
  amostra multianual, backup ou nuvem.
- Toda prova registra commit, ambiente, parâmetros, entrada, saída, duração e
  código de retorno.
- Uma fonte externa só é acessada quando o gate anterior estiver fechado e a
  operação tiver autorização compatível com seu custo e efeito.

## Gates de aceitação

| Gate | Critério | Evidência obrigatória | Estado |
|---|---|---|---|
| V00 — contrato | quatro specs coerentes e aprovadas | revisão humana e diff restrito | aprovado em 2026-08-03 |
| V01 — legado | última linha Colab recuperável | commit validado, tag anotada e inventário | aprovado em 2026-08-03 |
| V02 — ambiente | instalação local reproduzível | lockfile, lint, testes e CLI diagnóstica | aprovado em 2026-08-03 |
| V03 — amostragem piloto | um estrato anual importado somente como raw | manifest, quota contratual, hashes e retomada | pendente |
| V04 — contrato amostral | seleção temporal, estratificada e rotulada | cobertura, identidade, seed, `undated` e sentinelas | pendente |
| V05 — recorte vertical | pipeline e caderno reproduzem o piloto | testes, Parquet, DuckDB e marimo | pendente |
| V06 — backup | piloto restaurável em raiz vazia | log de upload, restore e hashes | pendente |
| V07 — amostra local | meta de 1% por ano e estrato desde 2010 | manifest global, quota, relatório e restauração da amostra | pendente |
| V08 — cloud opcional | mesmo job produz resultado equivalente | recibo Batch, custo e comparação local/cloud | pendente |
| V09 — corte | `main` é local-first sem perder história | instalação limpa, docs, remote e tag legado | pendente |

## V00 — validação das specs

- [x] Confirmar `plan.md`, `requirements.md`, `tech-stack.md` e `validation.md` como as quatro specs do contrato principal; specs operacionais ficam em subdiretórios próprios.
- [x] Confirmar que toda ação de `plan.md` usa checkbox CommonMark.
- [x] Confirmar que nenhum gate humano foi marcado como concluído sem aprovação explícita.
- [x] Procurar contradições sobre nome do repositório, recoleta, corte de 2010, amostra de 1%, raw integral, gzip, backup, Colab e Google Cloud.
- [x] Revisar o diff contra o pedido de refundação e excluir mudanças de implementação.

## V01 — preservação Git e legado

- [x] Confirmar `origin` como `https://github.com/pedblan/falando_nela.git`.
- [x] Confirmar que a worktree anterior não contém alterações não resolvidas antes da tag.
- [x] Executar a suíte relevante da revisão candidata à tag.
- [x] Verificar assinatura textual, alvo e mensagem da tag anotada.
- [x] Clonar o remote em diretório vazio e fazer checkout da tag sem referência local adicional.
- [x] Comparar o commit clonado com o commit registrado no inventário do legado.

Evidência de `2026-08-03`: a worktree de `main` ficou limpa e sincronizada com
`origin/main`; a tag anotada `legacy-colab-final` tem o objeto
`17a84c674472205e7c13ce1c3a74230fbd462722` e resolve para o commit
`782c337bf412ae33f9079dd87b68dedcd7a3ad92`. Em clone remoto vazio, o ambiente
criado a partir de `requirements.txt` passou em `pip check` com 96 pacotes e
em `PYTHONPATH=. python -m pytest -q` com 176 testes. O checkout da tag ficou
limpo e coincidiu com o commit registrado no inventário do legado.

## V02 — instalação e qualidade local

Comandos contratuais depois da implementação de R02:

```bash
uv sync --locked --all-groups
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run falando-nela doctor --json
```

- [x] Executar os comandos em cópia limpa sem `.venv` preexistente.
- [x] Confirmar Python 3.13 e dependências exatas do lockfile.
- [x] Confirmar que `doctor` falha claramente quando a raiz de produção está dentro do clone.
- [x] Confirmar que CI usa apenas fixtures e não possui credenciais externas.

Evidência de `2026-08-03`: a candidata R02 passou em 183 testes. Depois do
merge `c0563d249c8a0d0af36af9e37e24acba94b5ffef`, um clone limpo da `main`
instalou 104 pacotes com `uv sync --locked --all-groups`, passou em
`uv lock --check`, Ruff, formatação, 189 testes e
`falando-nela doctor --json`; a raiz externa informada ao diagnóstico não foi
criada.

## V03 — amostragem piloto do Drive e compressão

- [x] Registrar a aprovação humana da estratégia copy-first em `2026-08-03`.
- [x] Confirmar por readback que a raiz antiga foi renomeada para `falando_nela_arquivo`, preservando o ID `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB`.
- [x] Confirmar por readback que `falando_nela_refundacao`, ID `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH`, permanece reserva.
- [x] Criar a nova raiz operacional `falando_nela` pelo remote `drive.file`, confirmar que começa vazia e registrar o ID `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
- [x] Confirmar remotes e credenciais distintos para origem e destino.
- [x] Confirmar localmente que token sentinela não aparece em comando, erro ou manifest.
- [x] Confirmar localmente cifra obrigatória, permissões privadas, inspeção redigida e ausência de prompt na configuração rclone.
- [x] Confirmar que toda referência rclone fixa o `root_folder_id` aprovado mesmo quando a projeção redigida o mascara como `XXX`.
- [x] Classificar com fixtures todo dataset declarado de plenário e comissão sem heurística ambígua.
- [x] Preservar no mapa o caminho relativo exato sob `data/raw/v1/`.
- [x] Confirmar por contrato e fixtures corpus textual em `ano=YYYY/mes=MM/` e metadata fora do corpus mensal.
- [x] Confirmar que comandos construídos não contêm `sync`, `move`, `delete`, `purge`, substituição ou cópia server-side forçada.
- [x] Revisar o dry-run integral e confirmar correspondência exata com o plano congelado.
- [x] Aprovar o lote sentinela.
- [x] Reconciliar sentinela por caminho, tamanho e hash antes do lote seguinte.
- [x] Adulterar artefato local e retomar apenas inventário e mapa dependente.
- [x] Reconciliar integralmente origem e árvore canônica antes da amostragem.
- [x] Confirmar o ID da pasta raw como `1R_AYPVmVEKYK0cQ4qTRzNeGZ1zcSJq_W`.
- [x] Confirmar que o remote de origem tem escopo efetivo somente leitura.
- [x] Reproduzir por listagem read-only 2.891 arquivos e 14.686.044.612 bytes, distinguindo 2.887 JSONL dos quatro itens não raw.
- [x] Reconciliar pelo ID do Drive os dois itens exibidos pelo rclone com o mesmo caminho e a distinção `Untitled`/`Untitled (1)` da baseline G01.
- [x] Reconciliar 2.891 arquivos e 13,68 GiB da baseline ou bloquear diante da divergência.
- [x] Confirmar que nenhum comando usa `sync`, `move`, `delete` ou upload no remote de origem.
- [x] Executar inventário read-only da origem sem chamar rede de coleta parlamentar.
- [x] Selecionar o primeiro ano não vazio de `senado × plenario_discursos × pronunciamento_texto`.
- [x] Confirmar a identidade estável de todo registro da população piloto.
- [x] Verificar que a primeira passagem produz `N`, chaves e locators sem materializar o raw integral.
- [x] Calcular `k=max(1, ceil(N × 0.01))` e selecionar exatamente as `k` menores chaves.
- [x] Recalcular a seleção com ordem de leitura diferente e obter as mesmas identidades.
- [x] Congelar o manifest antes de iniciar a segunda passagem.
- [x] Materializar somente os registros listados no manifest congelado.
- [x] Confirmar que a operação publica somente raw e metadados técnicos, sem Parquet, DuckDB, normalização ou análise.
- [x] Confirmar que ledger SQLite e manifests JSON contêm apenas estado operacional, identidades, locators, contagens e hashes.
- [x] Criar `.jsonl.gz` determinístico em caminho temporário e promovê-lo atomicamente após validação.
- [x] Descompactar em streaming e comparar cada registro e `sha256_uncompressed` com a origem.
- [x] Verificar `sha256_stored_object`, tamanho comprimido e integridade gzip.
- [x] Comparar população, selecionados, válidos, vazios e rejeitados antes e depois da compressão.
- [x] Reexecutar com o mesmo `operation_id` e confirmar zero arquivo duplicado ou substituído.
- [x] Confirmar que nenhum timestamp variável do cabeçalho gzip altera a saída entre execuções.
- [x] Injetar falha antes e depois de cada etapa e confirmar retomada pelo último artefato validado.
- [ ] Confirmar que uma etapa cloud já confirmada é reconciliada por `remote_id` e não repetida.

Evidência de fechamento de R03 em `2026-08-03`: 38 lotes concluídos com zero
ausência e zero retorno de transporte não zero; destino com 2.887 arquivos e
14.686.043.352 bytes; origem inalterada com 2.891 arquivos e 14.686.044.612
bytes. O piloto publicou 30 de 2.996 registros em gzip de 169.507 bytes, com
`mtime=0`, sem nome no header e SHA-256 armazenado
`09ce1293e61ca8d8ef8691b35d87319c957e89bbc3bd109b239ae7623ed9b0cc`.
A reexecução fez zero stream e preservou o mesmo hash. O item cloud permanece
fora de R03.

## V04 — corte temporal, estratificação e proveniência

- [ ] Reconciliar população e selecionados por `source × dataset × record_type × substantive_year`.
- [ ] Confirmar exatamente `max(1, ceil(N × 0.01))` identidades únicas em cada estrato não vazio.
- [ ] Confirmar zero registro substantivo anterior a `2010-01-01` na amostra anual analítica.
- [ ] Confirmar que ausência de data não foi convertida em data válida nem incluída silenciosamente.
- [ ] Confirmar que registros sem ano ficam no estrato `undated` e fora das análises anuais.
- [ ] Confirmar que sentinelas ficam fora do denominador, do numerador e dos derivados amostrais.
- [ ] Confirmar seed, serialização da identidade e desempate idênticos em macOS e Linux.
- [ ] Alterar o inventário de entrada e confirmar invalidação de seleção e etapas dependentes.
- [ ] Confirmar que um snapshot novo recebe outro `sample_id` e não modifica artefatos de uma amostra publicada.
- [ ] Confirmar que “anual” está documentado como estratificação por ano substantivo, não como periodicidade do job.
- [ ] Reconciliar toda exclusão por motivo, fonte, dataset, arquivo e contagem.

## V05 — recorte vertical e marimo

Comandos contratuais depois da implementação de R04:

```bash
uv run falando-nela pipeline run --profile local --operation-id <id> --dataset senado/plenario_discursos
uv run marimo check notebooks/primeiro_recorte_discursos.py
uv run python notebooks/primeiro_recorte_discursos.py
```

- [ ] Confirmar leitura equivalente de fixture `.jsonl` e `.jsonl.gz`.
- [ ] Confirmar que o processamento usa outro `operation_id`, lê o raw local publicado e não acessa o Drive de origem.
- [ ] Confirmar que o comando local usa `sample_annual_1pct` quando nenhum profile é informado.
- [ ] Validar schema, tipos, nulos, proveniência e metadados do Parquet.
- [ ] Comparar contagem e identidade do universo entre raw, Parquet e DuckDB.
- [ ] Executar duas vezes e comparar hashes de todas as saídas determinísticas.
- [ ] Confirmar que o caderno contém apenas orquestração, parâmetros e apresentação.
- [ ] Confirmar a marca amostral em toda tabela, gráfico e exportação.
- [ ] Confirmar que o caderno não oferece ação silenciosa para promover a amostra a `full`.
- [ ] Confirmar ausência de estado oculto por execução em processo Python novo.
- [ ] Medir pico de memória e comprovar conclusão no perfil de 8 GiB.
- [ ] Confirmar spill exclusivamente sob `FALANDO_NELA_TEMP_ROOT` e limpeza segura dos temporários próprios.

## V06 — backup e restauração

- [ ] Gerar catálogo local ordenado com caminho, tamanho e SHA-256.
- [ ] Executar `rclone copy --dry-run` e revisar exatamente o conjunto previsto.
- [ ] Executar `rclone copy --immutable` para um novo `backup_id`.
- [ ] Confirmar que a operação não usa `sync`, não apaga e não substitui objetos remotos.
- [ ] Comparar catálogo local com listagem e hashes disponíveis no Drive.
- [ ] Restaurar em diretório criado vazio e diferente da raiz de trabalho.
- [ ] Recalcular SHA-256 localmente depois da restauração.
- [ ] Executar novamente o pipeline e o caderno sobre a raiz restaurada.
- [ ] Registrar tempos, bytes enviados, bytes restaurados, falhas e retries.

## V07 — amostra anual local completa

- [ ] Aprovar inventário integral e população de todos os estratos desde 2010.
- [ ] Executar lotes pequenos com checkpoints e manifests de etapa independentes.
- [ ] Simular interrupção após um lote e comprovar retomada sem releitura ou duplicação indevida.
- [ ] Reconciliar população, 1% selecionado, `undated`, sentinelas e rejeitados por estrato.
- [ ] Confirmar o fingerprint integral do raw de origem inalterado.
- [ ] Confirmar que raw amostral, índices técnicos, manifests e temporários da importação, somados aos derivados locais existentes, não excedem a quota de 2 GiB.
- [ ] Confirmar ao menos 5 GiB livres depois da publicação local.
- [ ] Restaurar integralmente a amostra em raiz vazia e reproduzir seus manifests.
- [ ] Confirmar que nenhum arquivo integral foi persistido fora do staging da operação.
- [ ] Bloquear qualquer exclusão local enquanto existir divergência ou restore não aprovado.

## V08 — piloto Google Cloud opcional

- [ ] Registrar tabela de preços vigente, região, máquina, memória, CPUs, disco, timeout e bytes de staging.
- [ ] Demonstrar estimativa total menor ou igual a US$ 5,00.
- [ ] Obter aprovação humana literal do `operation_id` e do teto antes da submissão.
- [ ] Executar exatamente um job sem Spot VM.
- [ ] Comparar commit, lockfile, seed, população, selecionados, manifest e hashes com a execução local.
- [ ] Interromper depois de `remote_id` confirmado e comprovar retomada sem segundo job.
- [ ] Confirmar código de retorno, logs, retries e custo efetivo.
- [ ] Apagar staging temporário depois do download validado.
- [ ] Listar imagens, objetos, logs, jobs, discos, IPs e demais recursos remanescentes.
- [ ] Bloquear ampliação se houver divergência ou custo superior ao autorizado.

## V09 — corte e regressões

- [ ] Clonar `main` do remote em diretório vazio e seguir somente a documentação local-first.
- [ ] Executar ambiente, recorte vertical, backup e restore sem abrir Colab ou montar Drive.
- [ ] Confirmar que o profile local padrão usa somente a amostra anual de 1%.
- [ ] Confirmar que o profile `full` exige operação e autorização distintas.
- [ ] Confirmar que resultados amostrais estão rotulados e não são apresentados como integrais.
- [ ] Confirmar que a tag do legado continua acessível e executa seus testes documentados.
- [ ] Confirmar que contratos v3 aprovados e sua proveniência continuam presentes.
- [ ] Procurar caminhos `/content/drive`, imports `google.colab` e `.ipynb` marcados como oficiais.
- [ ] Aceitar referências apenas em arquivo histórico ou documentação explícita de legado.
- [ ] Confirmar que nenhuma branch, tag, issue ou commit foi reescrito ou removido.
- [ ] Confirmar que `falando_nela` é o checkout canônico e aponta para o mesmo commit de `origin/main`.
- [ ] Confirmar que `falando_nela_refundacao` não contém diff nem commit exclusivo antes de sua remoção.
- [ ] Remover a worktree temporária com `git worktree remove`, sem exclusão direta da pasta.
- [ ] Confirmar que `git worktree list` não registra mais `falando_nela_refundacao` e preserva `falando_nela`.
- [ ] Confirmar que a tag `legacy-colab-final`, os dados e os backups permanecem acessíveis após a remoção da worktree.

## V09A — limpeza recuperável do legado

- [x] Catalogar e reconciliar os dois alvos locais antes de movê-los para a Lixeira do macOS.
- [x] Confirmar que os 52 notebooks rastreados permanecem no Git e estão marcados como consulta legada.
- [x] Preservar 106 notebooks do Drive, validar JSON, caminhos, tamanhos e SHA-256.
- [x] Enviar somente os dez IDs autorizados à Lixeira do Drive, sem esvaziá-la.
- [x] Confirmar que a raiz canônica permanece disponível e que o raw conserva 2.887 objetos e 14.686.043.352 bytes.
- [x] Confirmar que o hash da amostra R03 permanece `09ce1293e61ca8d8ef8691b35d87319c957e89bbc3bd109b239ae7623ed9b0cc`.
- [ ] Confirmar o fast-forward do checkout canônico e a remoção registrada da worktree temporária.

## Bloqueios

O gate corrente permanece aberto se ocorrer qualquer condição abaixo:

- chamada a uma fonte parlamentar durante a migração;
- escrita, reordenação ou limpeza do raw de origem;
- hash, contagem ou população não reconciliada;
- dado anterior a 2010 incluído silenciosamente no corpus ativo;
- estrato não vazio sem exatamente `max(1, ceil(N × 0.01))` registros;
- identidade, seed ou algoritmo amostral ausente do manifest;
- amostra apresentada como corpus integral ou resultado científico definitivo;
- sentinela ou `undated` contaminando estatísticas anuais;
- Parquet, DuckDB, normalização ou análise produzida dentro da operação de importação raw;
- backup sem restauração comprovada;
- trabalho direto em pasta sincronizada;
- segredo ou credencial em Git, log, caderno ou manifest;
- dependência obrigatória de Colab no caminho local-first;
- gasto ou recurso cloud sem autorização e inventário;
- remoção de legado ou dados dentro da tarefa de fundação;
- divergência entre estas specs, implementação, testes e documentação.

## Registro de custo

Para cada operação externa, preencher antes de executar:

```text
Hipótese:
Amostra mínima:
Número máximo de tentativas:
Recursos e região:
Estimativa ou teto de gasto:
Condição de parada:
operation_id:
```

Na tarefa de elaboração destas specs:

- chamadas pagas: nenhuma;
- dados transferidos: nenhum;
- builds: nenhum;
- recursos cloud: nenhum.

## Resultado final

Cada gate receberá evidências reais durante sua tarefa. A presença destes
checklists não antecipa aprovação da arquitetura, da migração, do corpus, do
backup, da nuvem ou do corte de `main`.
