# Proposta de schema — snapshot de discursos v2

Status: **proposta para aprovação humana**.

## Decisões já incorporadas

- D03: três bases de discursos de Câmara, Senado e Congresso;
- D04: `2010-01-01` a `2026-07-13`, inclusive;
- D05: nenhuma deduplicação entre fontes;
- autores ausentes permanecem no corpus;
- fontes processadas permanecem imutáveis.

## Unidade e chave

Cada linha representa uma **intervenção textual oficial de plenário**.

- `texto_id` continua sendo a chave primária, sem rehash ou renomeação;
- `unidade_analitica` preserva `discurso` ou `pronunciamento`;
- `unidade_snapshot` usa o valor comum
  `intervencao_textual_oficial`;
- `snapshot_id` identifica o artefato congelado, não a análise futura.

O censo encontrou 428.372 `texto_id` distintos, sem ausência, duplicata interna
ou colisão entre as três bases.

## Inclusão

Uma linha entra no snapshot principal quando:

1. pertence a um dos três arquivos aprovados;
2. `data` é válida;
3. `2010-01-01 <= data <= 2026-07-13`;
4. `texto_id` é não vazio e único;
5. `texto` é não vazio.

Qualquer quebra dos itens 4 ou 5 interrompe a execução em vez de excluir
silenciosamente. Autor ausente não impede inclusão.

## Exclusões auditáveis

Datas inválidas, ausentes ou fora do período não entram no Parquet principal,
mas devem aparecer em `registros_excluidos.parquet` com:

- `texto_id`;
- arquivo de entrada;
- data original;
- motivo exato;
- campos de proveniência.

Para cada base:

```text
entrada
- data inválida ou ausente
- data anterior a 2010-01-01
- data posterior a 2026-07-13
= snapshot
```

Não existe termo de deduplicação na equação D05 aprovada.

## Campos

O schema legível por máquina está em
[`schema/snapshot_discursos_v2.record.schema.json`](schema/snapshot_discursos_v2.record.schema.json).
Todos os campos devem existir em cada linha, ainda que os explicitamente
anuláveis tenham valor nulo.

### Identidade

- `snapshot_id`;
- `texto_id`;
- `dataset_version`;
- `input_parquet`;
- `source`;
- `dataset`.

### Instituição e unidade

- `casa`;
- `ambito`;
- `orgao_sigla`;
- `orgao_nome`;
- `documento_tipo`;
- `unidade_analitica`;
- `unidade_snapshot`.

### Tempo

- `data`;
- `data_hora`;
- `ano`;
- `mes`.

No Parquet, `data` deve usar `date32`; `ano` e `mes`, inteiros.

### Descrição e autoria

- `titulo`;
- `resumo`;
- `indexacao`;
- `tipo_discurso`;
- `tipo_uso_palavra`;
- `fase_evento`;
- `parlamentar_id`;
- `parlamentar_nome`;
- `parlamentar_partido`;
- `parlamentar_uf`;
- `parlamentar_cargo`;
- `autor_disponivel`.

### Identificadores institucionais

- `pronunciamento_id`;
- `sessao_id`;
- `evento_id`.

### Texto

- `texto`;
- `texto_tamanho`;
- `texto_status`;
- `forma`;
- `metodo_obtencao`.

### URLs e proveniência

- `url_texto`;
- `url_audio`;
- `url_video`;
- `url_origem`;
- `raw_run_id`;
- `raw_record_type`;
- `raw_source_id`;
- `raw_partition`;
- `raw_collected_at`;
- `raw_checksum`;
- `raw_path`;
- `raw_response_url`.

Ao menos um de `raw_path` ou `raw_source_id` deve ser não vazio.

### Qualidade

- `qualidade_flags`: lista ordenada e sem duplicatas.

Flags iniciais permitidas:

- `autor_ausente`;
- `partido_ausente`;
- `uf_ausente`;
- `data_hora_ausente`;
- `sessao_id_ausente`;
- `evento_id_ausente`;
- `pronunciamento_id_ausente`.

As flags descrevem a linha; não determinam elegibilidade analítica.

## Artefatos previstos

- `snapshot_discursos_v2.parquet`;
- `registros_excluidos.parquet`;
- `schema.json`;
- `contagens_por_etapa.csv`;
- `contagens_por_ano.csv`;
- `contagens_por_base.csv`;
- `relatorio.md`;
- `manifest.json`;
- `logs/execution.jsonl`.

## Gate

A aprovação deste documento autoriza implementar testes, transformação e
notebook de smoke. Não autoriza a execução completa nem a promoção do snapshot.
