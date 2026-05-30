# Validation: metadados de parlamentares

## Smoke test de coleta

```bash
python -m coleta.parlamentares.collect \
  --mode dev \
  --source all \
  --sample-limit 5 \
  --run-id smoke-parlamentares
```

## Smoke test de processamento

```bash
python -m processamento.parlamentares \
  --mode dev \
  --run-id smoke-parlamentares-v1 \
  --overwrite
```

## Exemplo Colab

O caderno pronto para este fluxo fica em:

```text
notebooks/coleta/coleta_parlamentares.ipynb
```

Assume que a celula base do README ja montou o Drive, definiu
`FALANDO_NELA_DATA_ROOT` e entrou no diretorio do repo.

```python
import subprocess

subprocess.run([
    "python", "-m", "coleta.parlamentares.collect",
    "--mode", "prod",
    "--resume",
    "--run-id", "prod-parlamentares-20260527",
    "--data-inicio", "2011-05-18",
    "--data-fim", "2026-05-18",
], check=False)

subprocess.run([
    "python", "-m", "processamento.parlamentares",
    "--mode", "prod",
    "--run-id", "processed-parlamentares-v1-20260527",
    "--overwrite",
], check=False)
```

## Criterios da camada raw

- Existem arquivos:
  - `data/dev/raw/camara/parlamentares/metadata/{run_id}.jsonl`;
  - `data/dev/raw/senado/parlamentares/metadata/{run_id}.jsonl`.
- Nao existem particoes mensais `ano=YYYY/mes=MM` para esse dataset.
- Cada linha JSONL tem envelope bruto comum, incluindo `source`, `dataset`,
  `record_type`, `source_id`, `request`, `response`, `checksum` e `payload`.
- `dataset == "parlamentares"` em todos os registros.
- A Camara gera registros `camara_deputado_detalhe` com campo oficial de sexo
  no payload de detalhe.
- O Senado gera registros de lista, detalhe, mandatos e filiacoes quando os
  endpoints responderem.
- `source_id` e estavel e deduplicavel por casa, parlamentar e endpoint.
- Reexecutar com o mesmo `--run-id --resume` nao duplica linhas ja gravadas.
- Falhas por parlamentar aparecem em `logs/{run_id}.jsonl` e no checkpoint, sem
  impedir a coleta dos demais IDs.

## Criterios da camada processed

- Existem JSONLs:
  - `processed/parlamentares/v1/parlamentares.jsonl`;
  - `processed/parlamentares/v1/mandatos.jsonl`;
  - `processed/parlamentares/v1/filiacoes.jsonl`;
  - `processed/parlamentares/v1/parlamentares_periodos.jsonl`.
- Existem Parquets equivalentes em `processed/parlamentares/v1/parquet/`.
- `parlamentar_key` e unico em `parlamentares.jsonl`.
- `parlamentar_key` usa sempre o prefixo da fonte, por exemplo
  `camara:204379` ou `senado:5672`.
- `sexo_original` preserva o valor oficial.
- `genero` contem apenas `masculino`, `feminino` ou `nao_informado`.
- Nenhum valor de `genero` e inferido por nome.
- Datas de mandatos, filiacoes e intervalos usam formato `AAAA-MM-DD`.
- `vigencia_inicio <= vigencia_fim` quando `vigencia_fim` existir.
- Intervalos abertos ou indefinidos ficam documentados por
  `observacao_qualidade`.
- O manifest processed registra contagens por casa, endpoint, tabela de saida,
  IDs descobertos nos textos e divergencias de metadados.

## Validacao de juncao com textos

Rodar a auditoria depois de gerar Parquets de textos e parlamentares:

```bash
python -m processamento.parlamentares_join_audit \
  --profile samples-local \
  --run-id parlamentares-join-smoke \
  --overwrite
```

No Colab:

```bash
python -m processamento.parlamentares_join_audit \
  --profile colab \
  --run-id parlamentares-join-YYYYMMDD \
  --overwrite
```

Saidas esperadas:

- `processed/audits/parlamentares/{run_id}/join_coverage.csv`;
- `processed/audits/parlamentares/{run_id}/unmatched_textos.jsonl`;
- `processed/audits/parlamentares/{run_id}/ambiguous_matches.jsonl`;
- `processed/audits/parlamentares/{run_id}/gender_distribution.csv`;
- `processed/audits/parlamentares/{run_id}/manifest.json`.

Checks obrigatorios:

- A auditoria usa `source`, `parlamentar_id` e data; nao usa apenas nome.
- IDs de Camara e Senado nao colidem, mesmo quando o numero for igual.
- Registros textuais com `parlamentar_id` e `data` devem ter cobertura alta por
  `source/dataset`; excecoes precisam aparecer em `unmatched_textos.jsonl`.
- Registros sem autoria parlamentar individual podem ficar fora do denominador
  principal, mas devem ser contados separadamente.
- Matches multiplos aparecem em `ambiguous_matches.jsonl` com os intervalos
  candidatos.
- A distribuicao de genero e calculada apenas para textos com match valido.
- A auditoria reporta cobertura por `source/dataset/documento_tipo/ano`.

## Validacao de juncao com apartes

Depois de gerar `apartes_parlamentares/v1`, a auditoria desse processamento
deve confirmar:

- `aparteante_genero`, `aparteante_partido` e `aparteante_uf` vieram de
  `parlamentares_periodos` ou ficaram nulos quando nao houve match.
- `orador_genero`, `orador_partido` e `orador_uf` seguem a mesma regra.
- Nenhum genero foi inferido por nome.
- Casos da Camara sem ID oficial aparecem como `name_only` ou `ambiguous`.
- A cobertura de match e reportada separadamente para oradores e aparteantes.
- As contagens anuais por genero, partido e UF usam somente linhas com match
  valido quando o agrupamento exigir atributo parlamentar.

## Validacao da integracao com atualizacao

- O roteiro de atualizacao deve incluir `coleta.parlamentares.collect` e
  `processamento.parlamentares` antes da auditoria final de Parquets.
- O caderno `notebooks/coleta/coleta_parlamentares.ipynb` deve permitir rodar
  validacao curta, coleta completa com `--resume`, processamento e auditoria de
  juncao sem editar codigo do projeto dentro do Colab.
- Os manifests de textos, parlamentares e auditoria devem compartilhar o mesmo
  periodo baseline ou declarar explicitamente o periodo diferente.
- Depois de atualizar um periodo novo de discursos, a auditoria deve mostrar se
  surgiram `parlamentar_id`s sem metadados.
- Samples locais devem incluir Parquets de `parlamentares/v1` suficientes para
  reproduzir o join localmente.
- No backfill historico geral, `parlamentares/v1` deve estar disponivel antes
  de `camara/plenario_discursos` e `camara/plenario_apartes` quando a meta for
  reduzir consultas vazias; os logs desses coletores devem indicar
  `planejamento=parlamentares_periodos`.

## Validacao da integracao com expansao

- Toda nova base textual deve ter teste de normalizacao preservando
  `parlamentar_id` quando a fonte oficial oferecer esse identificador.
- Toda nova base deve aparecer na auditoria de cobertura por
  `source/dataset/documento_tipo/ano`.
- Bases sem autoria individual devem documentar essa limitacao na propria spec
  e na auditoria.
- O visualizador ou notebook exploratorio deve conseguir exibir, apos join,
  `genero`, `sexo_original`, `partido_sigla`, `uf` e `legislatura` para uma
  amostra de textos com `parlamentar_id`.

## Testes unitarios esperados

- Camara: paginacao de `/api/v2/deputados` e coleta de detalhe por ID.
- Camara: parse de `/deputados/{id}/historico` em intervalos ordenados.
- Senado: requisicoes com `Accept: application/json` e sufixo `.json`.
- Senado: normalizacao de `SexoParlamentar`, mandatos e filiacoes.
- Processed: deduplicacao por `parlamentar_key`.
- Processed: construcao de `parlamentares_periodos` sem sobreposicoes
  silenciosas.
- Common coleta: carregamento de `parlamentares_periodos` e filtragem por
  janela de mandato para planejamento de coletores.
- Join: match por intervalo temporal, unmatched e ambiguidades.
- CLI: `--mode prod` recusa destino dentro do repositorio.
- Resume: segunda execucao com mesmo `run_id` nao duplica endpoints.
- Manifest: cabecalhos de deprecacao do Senado sao preservados quando presentes.

## Validacao manual minima

- Abrir uma amostra de discursos da Camara e confirmar match com deputado pelo
  `parlamentar_id` da API da Camara.
- Abrir uma amostra de discursos do Senado e confirmar match com senador pelo
  `CodigoParlamentar`.
- Conferir manualmente pelo menos um caso feminino e um masculino em cada casa.
- Conferir um caso de suplente ou mudanca de partido, validando que a juncao usa
  o periodo correto para a data do texto.
