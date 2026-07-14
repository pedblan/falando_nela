# Plano: backfill de discursos do Senado e do Congresso em 2015–2016

## Resultado esperado

Ao final, os Parquets canônicos e um novo snapshot analítico contêm a cobertura
oficial reconciliada de 2015 e 2016 para Senado e Congresso. A recuperação é
repetível, retomável e isolada do ciclo incremental; a fotografia anterior e
todo o raw preexistente permanecem auditáveis.

## Mapa da implementação

- Adaptador paginado do portal e reconciliação com a lista mensal:
  `coleta/senado/discursos_historicos.py`.
- Estratégia CLI compartilhada e persistência raw:
  `coleta/senado/discursos.py`.
- Probe diagnóstico do endpoint por senador, sempre em janelas anuais:
  `coleta/senado/auditoria_discursos_historicos.py`.
- Cobertura pre/post e reconciliação por `texto_id`:
  `processamento/reconciliacao_discursos.py`.
- Gate anual e artefatos da etapa 00:
  `analise/discursos_plenario/snapshot.py` e
  `notebooks/analise/celulas/00_validacao_snapshot.py`.
- Orquestrador seguro do ciclo:
  `notebooks/coleta/06_backfill_discursos_senado_congresso_2015_2016_colab.ipynb`,
  gerado por `scripts/generate_backfill_2015_2016_colab_notebook.py`.

O repositório implementa e testa o fluxo; a coleta longa e a aceitação dos
artefatos no Google Drive permanecem ações operacionais explícitas no Colab.

## 1. Congelar o estado anterior

1. Confirmar a raiz ativa
   `/content/drive/MyDrive/falando_nela/data` e não misturar cópias antigas do
   Drive.
2. Criar o `cycle_id` histórico e fixar os dois `run_id`s de coleta.
3. Adquirir os locks de `senado/plenario_discursos` e
   `senado/congresso_discursos`.
4. Arquivar manifests, checkpoints, inventário por ano/mês, contagens e
   checksums dos dois Parquets e do snapshot usado para detectar a lacuna.
5. Gerar `coverage_pre.csv` e a primeira versão de
   `reconciliation_ids.parquet`, sem escrever em raw ou processed.

## 2. Reproduzir e classificar a anomalia da fonte

1. Consultar novamente os 24 meses de 2015–2016 com `siglaCasa=SF` e `CN` no
   endpoint mensal atual.
2. Arquivar cada resposta em `source_probes.jsonl`, inclusive respostas vazias.
3. Consultar meses-controle não vazios antes e depois da lacuna para cada casa.
4. Classificar o resultado:
   - `primary_recovered`, se o endpoint mensal voltou a fornecer a população;
   - `source_anomaly`, se os alvos seguem vazios e fontes oficiais alternativas
     encontram pronunciamentos;
   - `unresolved`, se não há fonte alternativa que prove a população.
5. Bloquear mutações enquanto a classificação for `unresolved`.

## 3. Construir e validar o adaptador de descoberta

1. Implementar uma estratégia explícita de recuperação histórica na esteira
   compartilhada de discursos do Senado, preservando o comportamento default
   dos coletores atuais.
2. Prototipar a combinação de:
   - discursos por senador, com casa e janela explícitas;
   - busca oficial de pronunciamentos, seus autores, paginação e detalhes;
   - texto integral e notas de sessão pelos endpoints já contratados.
3. Normalizar os candidatos por `CodigoPronunciamento`, data e casa.
4. Comparar o adaptador com o endpoint mensal nos meses-controle:
   - nenhum identificador da referência pode faltar;
   - adicionais precisam de detalhe oficial compatível;
   - `SF` e `CN` não podem ser misturados.
5. Criar fixtures pequenas a partir da estrutura das respostas, sem depender de
   rede nos testes unitários.
6. Só promover o adaptador depois da paridade e dos testes de paginação,
   deduplicação, retries e retomada.

## 4. Executar piloto histórico

1. Rodar um mês de 2015 e um de 2016 para `SF`, com limite pequeno de textos.
2. Rodar meses com atividade comprovada para `CN`, também com limite pequeno.
3. Confirmar as quatro sentinelas ou equivalentes da mesma casa/ano no inventário
   de descoberta e validar pelo menos uma sentinela de cada dataset ponta a ponta.
4. Inspecionar manualmente casa, data, autor, texto, URL, método de obtenção e
   `source_id`.
5. Apagar somente saídas descartáveis do piloto no ambiente de desenvolvimento;
   nunca remover raw de produção. O backfill de produção usa `run_id`s próprios.

## 5. Executar o backfill no Colab/Drive

Com flags de produção inicialmente `False` e confirmação explícita do
`cycle_id`, executar cada dataset com:

```bash
python -u -m coleta.senado.plenario_discursos.collect \
  --mode prod \
  --output-dir /content/drive/MyDrive/falando_nela/data \
  --data-inicio 2015-01-01 \
  --data-fim 2016-12-31 \
  --run-id RUN_ID_SENADO_2015_2016 \
  --no-sample \
  --resume \
  --discovery-strategy historical-official
```

```bash
python -u -m coleta.senado.congresso_discursos.collect \
  --mode prod \
  --output-dir /content/drive/MyDrive/falando_nela/data \
  --data-inicio 2015-01-01 \
  --data-fim 2016-12-31 \
  --run-id RUN_ID_CONGRESSO_2015_2016 \
  --no-sample \
  --resume \
  --discovery-strategy historical-official
```

As duas bases podem rodar em sessões separadas, mas nunca duas instâncias do
mesmo dataset.

## 6. Aplicar gates de coleta e reconciliação raw

1. Exigir manifest final `completed`, `mode=prod`, `sample=false`, janela e
   `run_id` exatos.
2. Exigir as 24 partições mensais concluídas por dataset, mesmo quando algum mês
   não possuir pronunciamento.
3. Calcular falhas não resolvidas dentro do mesmo `run_id`; a simples existência
   histórica de uma falha não reprova uma retomada concluída depois.
4. Validar todos os JSONLs e reconciliar descoberta × raw textual por
   `CodigoPronunciamento`.
5. Separar texto disponível, fallback de sessão e pendência de transcrição.
6. Confirmar as quatro sentinelas e impedir processamento se houver
   `raw_missing`, conflito de casa ou partição não auditada.

## 7. Regenerar a fotografia canônica

1. Arquivar os checksums e contagens `pre` dos derivados substituíveis.
2. Regenerar `processed-textos-v1-current` a partir de todo o raw cumulativo.
3. Regenerar `parquet-textos-v1-current` e os Parquets por base.
4. Atualizar auditorias, samples e visualizador apenas depois de os Parquets
   passarem nos gates.
5. Produzir `coverage_post.csv` e concluir `reconciliation_ids.parquet`.
6. Comparar `pre` × `post`; fora da janela alvo, exigir invariância.

## 8. Produzir novo snapshot e medir drift

1. Criar novo `analysis_run_id`, apontando `compared_to` para a rodada que
   revelou a lacuna.
2. Executar apenas a etapa de snapshot antes das análises caras.
3. Persistir a matriz `arena/ano`, a lista de anos ausentes e a reconciliação
   Parquet × snapshot.
4. Exigir contagens positivas em 2015 e 2016 nas três arenas e cobertura integral
   da população oficial aprovada em Senado/Congresso.
5. Separar no relatório:
   - registros adicionados pelo backfill;
   - registros alterados;
   - deduplicações Senado × Congresso;
   - perdas ou mudanças fora do escopo;
   - mudanças de código/schema, se houver.
6. Não reexecutar as etapas analíticas seguintes enquanto o novo snapshot não
   estiver aprovado.

## 9. Encerrar o ciclo

1. Gravar `summary.json` com evidências, manifests, checksums, contagens, gates e
   decisão `accepted` ou `rejected`.
2. Liberar os locks somente depois de conferir os artefatos finais.
3. Preservar a configuração do ciclo e limpar `active.json` apenas conforme o
   contrato operacional vigente.
4. Atualizar specs, READMEs, cadernos e testes listados em `requirements.md`.
5. Registrar separadamente qualquer trabalho restante, sobretudo textos sem
   fonte oficial aproveitável; isso não deve ser ocultado por uma contagem anual
   positiva.
