# Plano operacional — G02 migração integral e corte do raw

## Estado

Spec pronta para execução. G01 está concluído, e a implementação local de
migração já existe. Nenhum item deste documento autoriza por si só upload ou
corte remoto: G02 conserva apenas duas decisões humanas obrigatórias, uma antes
da cópia integral e outra antes da mudança de autoridade para o GCS.

## Resultado

Copiar a baseline raw canônica do Drive para
`gs://falando-nela-pedblan-data/data/raw/v1/`, provar que a cópia é íntegra,
retomável e restaurável e, com aprovação explícita, tornar o GCS a fonte
oficial desse raw. O Drive permanece intacto como arquivo de rollback.

## Como usar este plano

- Os checkboxes acompanham resultados observáveis, não uma sequência rígida de
  comandos.
- Tamanho e quantidade de lotes, concorrência, retries, formato dos relatórios
  e tamanho exato da amostra podem ser ajustados durante a operação.
- Ajustes operacionais não exigem reescrever a spec quando preservam os
  requisitos, ficam registrados no relatório e não elevam materialmente risco
  ou custo.
- Divergência de conteúdo, possibilidade de sobrescrita, mudança de projeto ou
  origem, custo fora do orçamento ou necessidade de escrever no Drive exigem
  interrupção e nova decisão.

## G02-A — preparar e autorizar a cópia

- [x] Confirmar a conclusão de G01 e a presença dos três sentinelas no GCS.
- [x] Manter implementação e testes locais da migração e do corte.
- [x] Definir requisitos e validação proporcionais ao risco de G02.
- [x] Abrir uma operação recuperável com identificador próprio.
- [x] Fazer readback do projeto, bucket, prefixo, identidade e origem Drive.
- [x] Inventariar a origem em modo somente leitura e comparar com a baseline.
- [x] Inventariar o destino e classificar objetos iguais, ausentes e conflitantes.
- [x] Produzir um plano de cópia em lotes adequados aos arquivos e ao ambiente.
- [x] Registrar estimativa de custo, comando ou procedimento e condição de parada.
- [ ] Obter aprovação humana para a cópia integral.

**Decisão 1:** autorizar a cópia quando origem e destino estiverem identificados,
não houver conflito ou surpresa sem explicação e o custo couber no orçamento.

Preflight e dry-run `g02-full-20260811-v1` concluídos em `2026-08-11`, sob a
revisão `afebd26`: 2.887 objetos e 14.686.043.352 bytes na origem, três
sentinelas iguais no destino, 2.884 criações previstas, 38 lotes correntes e
zero conflito, remoção ou erro. A estimativa conservadora é US$ 0,30 e o digest
submetido à aprovação é
`7c536e2ee91e79cf312891b40a726bcb1da663e852dbe810019409a718871e41`.

## G02-B — copiar e retomar

- [ ] Copiar somente objetos ausentes, sem transformar paths ou conteúdo.
- [ ] Registrar progresso suficiente para retomar sem repetir lotes já íntegros.
- [ ] Em falha ou resultado ambíguo, consultar o destino e continuar do estado
  observado.
- [ ] Ajustar lotes, concorrência ou retries quando necessário, sem nova
  aprovação, desde que os requisitos e o limite de custo continuem atendidos.
- [ ] Encerrar a cópia com todos os objetos esperados presentes e nenhum
  conflito, overwrite ou mutação do Drive.

## G02-C — provar integridade e restauração

- [ ] Reconciliar inventários completos de origem e destino por locator e bytes.
- [ ] Comparar checksums disponíveis e investigar toda divergência.
- [ ] Demonstrar idempotência por nova verificação ou reexecução sem escrita.
- [ ] Restaurar em diretório vazio uma amostra representativa, incluindo casos
  pequenos, grandes, vazios e categorias distintas da baseline.
- [ ] Comparar tamanho e hash do conteúdo restaurado com a origem esperada.
- [ ] Confirmar novamente que o Drive e as configurações locais permaneceram
  inalterados.
- [ ] Consolidar evidências, incidentes resolvidos e custo observado em um
  relatório curto de conclusão da migração.

## G02-D — aprovar e executar o corte

- [ ] Apresentar o relatório de integridade, restauração, idempotência e custo.
- [ ] Obter aprovação humana explícita para tornar o GCS a autoridade raw.
- [ ] Executar o corte separadamente da cópia e registrar sua proveniência.
- [ ] Atualizar `authoritative_raw = "gcs"` na configuração versionada.
- [ ] Publicar e reler uma evidência de corte no GCS sem substituir artefato
  existente.
- [ ] Confirmar que o Drive segue disponível somente para leitura e rollback.
- [ ] Revisar o diff e encerrar G02 sem antecipar processamento, Marimo ou G05.

**Decisão 2:** autorizar o corte somente depois das provas de integridade e
restauração. A aprovação vale para o corte desta baseline e não para mudanças
posteriores no corpus.

## Limites de esforço e custo

- A operação deve permanecer dentro do budget da refundação, hoje com
  referência conservadora total de US$ 5,00.
- A expectativa de G02 é inferior a US$ 1,00; ultrapassar essa expectativa
  exige apenas uma justificativa antes de continuar, desde que o budget total
  permaneça protegido.
- Não repetir uma operação paga sem primeiro reconciliar o estado remoto.
- Três falhas equivalentes sem hipótese nova encerram a tentativa para
  diagnóstico; não impedem retomar G02 depois da correção.

## Fora do escopo

- alterar IaC, IAM, buckets, APIs ou o budget de G01;
- transformar raw em Parquet ou executar Cloud Run e Marimo;
- consultar fontes parlamentares ou incorporar atualização temporal;
- mover, apagar, reorganizar ou tornar gravável o Drive;
- excluir ou substituir objetos existentes no GCS;
- mudar o executável inteiro para cloud-first antes de G05.
