# Validação: backfill de discursos do Senado e do Congresso em 2015–2016

## Princípio de aceite

O problema só está corrigido quando a descoberta oficial, o raw, o processed,
os Parquets e o novo snapshot são reconciliáveis por identificador. Contagens
anuais maiores que zero e a presença das quatro sentinelas são gates
necessários, mas não suficientes.

## 1. Validação local estrutural

Executar as suítes afetadas, incluindo os novos testes da recuperação:

```bash
.venv/bin/python -m pytest \
  tests/test_senado_plenario.py \
  tests/test_congresso_discursos.py \
  tests/test_normalizacao.py \
  tests/test_parquet.py \
  tests/test_discursos_plenario.py \
  tests/test_analysis_colab_notebooks.py \
  tests/test_discursos_historicos.py \
  tests/test_backfill_discursos_colab_notebook.py
```

Depois, executar a suíte completa:

```bash
.venv/bin/python -m pytest
```

Se notebooks forem alterados:

- abrir cada `.ipynb` com `nbformat` e validar o schema;
- compilar todas as células Python com `ast.parse`;
- executar o gerador em modo `--check` e exigir árvore sincronizada;
- executar também
  `scripts/generate_backfill_2015_2016_colab_notebook.py --check`;
- confirmar Drive na primeira célula executável, flags de produção `False` e
  confirmação explícita do `cycle_id`.

## 2. Testes unitários obrigatórios

### Detecção da fonte

- Endpoint mensal não vazio: mantém a estratégia primária e registra o probe.
- Endpoint mensal vazio em 2015–2016 e fallback oficial não vazio: classifica
  `source_anomaly` e usa o adaptador histórico.
- Endpoint mensal e fallback vazios: classifica `unresolved` e bloqueia a
  coleta, sem marcar o mês como atividade inexistente.
- Mês legitimamente vazio: pode concluir a partição somente com concordância
  das fontes aceitas e registro explícito da evidência.
- Resposta HTTP 200 malformada ou sem metadados esperados falha; não equivale a
  coleção vazia válida.

### Descoberta alternativa

- Paginação completa da busca oficial.
- Autor com e sem `CodigoParlamentar`.
- Mesmo `CodigoPronunciamento` encontrado por duas fontes: uma unidade textual,
  com ambas as proveniências preservadas.
- Mesmo identificador com casas ou datas divergentes: conflito auditado e gate
  bloqueado.
- Detalhe `Senado Federal` gera dataset `plenario_discursos` e prefixo `SF`.
- Detalhe `Congresso Nacional` gera dataset `congresso_discursos` e prefixo
  `CN`.
- Casa fora do escopo não entra em nenhuma das duas bases e aparece na
  auditoria.
- Texto integral, fallback de sessão e fila de transcrição preservam o contrato
  existente.
- Falha inesperada de um item deixa a partição retomável.
- Segunda execução com o mesmo `run_id --resume` não repete descoberta nem texto
  já gravado e não duplica linhas.

### Cobertura e snapshot

- Fixture com `senado/2015=0` falha no gate anual.
- Fixture com `congresso/2016=0` falha no gate anual.
- Mês zero dentro de um ano com outros meses cobertos não falha por si só.
- Todos os anos completos e as três arenas presentes aprovam o gate anual.
- A reconciliação explica registros removidos como duplicata exata
  Senado × Congresso; perda sem justificativa falha.
- A célula autônoma do caderno 00 continua lendo um snapshot já pronto e agora
  falha quando existe ano completo ausente em qualquer arena obrigatória.

## 3. Probes oficiais antes da produção

Repetir e arquivar os probes mensais da janela alvo para `SF` e `CN`. A
validação deve inspecionar o conteúdo, não apenas o status HTTP.

Também consultar controles dinâmicos em ambos os lados da lacuna. Os resultados
observados em 2026-07-14 foram:

| Casa | Controle | Sessões | Pronunciamentos |
| --- | --- | ---: | ---: |
| SF | 2014-05 | 22 | 358 |
| SF | 2017-03 | 4 | 65 |
| CN | 2014-05 | 8 | 35 |
| CN | 2017-04 | 1 | 7 |

Esses números devem ser gravados como observação, não codificados como verdade
eterna. O gate de paridade compara conjuntos de `CodigoPronunciamento` obtidos
na mesma execução:

- `missing_from_fallback = primary_ids - fallback_ids` deve ser vazio;
- todo item em `fallback_ids - primary_ids` deve ter casa, data, autor e URL
  oficial validados;
- nenhuma casa pode aparecer no dataset oposto;
- a taxa de erro HTTP não resolvida deve ser zero.

O endpoint por senador deve ser auditado separadamente, preservando o payload
e respeitando a janela máxima de um ano:

```bash
python -m coleta.senado.auditoria_discursos_historicos \
  --cycle-dir "$CYCLE_DIR" \
  --data-inicio 2015-01-01 --data-fim 2016-12-31 \
  --resume --strict
```

## 4. Smokes das sentinelas

Antes do backfill completo, confirmar que as quatro páginas oficiais e os
textos individuais estão acessíveis:

| Arena | Ano | `CodigoPronunciamento` | Casa esperada |
| --- | ---: | ---: | --- |
| senado | 2015 | 414849 | Senado Federal |
| senado | 2016 | 422757 | Senado Federal |
| congresso | 2015 | 411219 | Congresso Nacional |
| congresso | 2016 | 426642 | Congresso Nacional |

Para cada sentinela, validar:

- detalhe oficial com data dentro da janela e casa esperada;
- texto integral HTTP 200 e não vazio;
- texto não é URL nem página de erro;
- `source_id`, dataset, `CodigoPronunciamento` e checksum coerentes;
- presença no raw, processed e Parquet depois da produção;
- presença no snapshot ou justificativa de duplicação no audit correspondente.

## 5. Gate das coletas de produção

Para cada um dos dois `run_id`s:

- manifest final existe;
- `source=senado` e dataset exato;
- `mode=prod`;
- `sample=false` e `sample_limit=null`;
- janela exata `2015-01-01..2016-12-31`;
- `status=completed` e `errors=0`;
- `discovery_strategy=historical-official` e versões das fontes registradas;
- 24 partições mensais presentes em `completed_partitions` do mesmo `run_id`;
- nenhuma falha do mesmo run permanece sem conclusão posterior;
- nenhum lock ativo;
- JSONL válido, sem linhas truncadas;
- `metadata/` contém apenas descoberta e os diretórios mensais contêm apenas
  `pronunciamento_texto`;
- `CodigoPronunciamento` e `source_id` são únicos dentro do dataset;
- toda descoberta possui um estado raw final auditável;
- as quatro sentinelas estão presentes.

Reprovar se o manifest indicar `completed_with_errors`, mesmo que os anos já
tenham contagens positivas.

## 6. Reconciliação por identificador

Para cada `source/dataset/ano/mes`, calcular:

```text
discovered_ids
raw_ids
raw_available_text_ids
raw_unavailable_text_ids
processed_ids
parquet_ids
snapshot_ids
snapshot_duplicate_removed_ids
```

Exigir:

- `discovered_ids == raw_ids`;
- `raw_available_text_ids == processed_ids`, salvo exclusão nominal e
  justificada no manifest;
- `processed_ids == parquet_ids`;
- `parquet_ids == snapshot_ids ∪ snapshot_duplicate_removed_ids` dentro do
  recorte e da arena correspondentes;
- conjuntos sem duplicatas internas;
- datas e casas coerentes em todas as camadas;
- nenhum `normalization_loss`, `parquet_loss` ou `snapshot_filter_loss` sem
  justificativa aprovada.

Casos `text_unavailable` ficam fora do processed, mas devem permanecer no raw e
na reconciliação com método, tentativas e fonte candidata registrados.

## 7. Validação dos derivados canônicos

Nos JSONLs processados e Parquets:

- `dataset_version=v1`;
- `texto_id` único;
- `texto` não vazio;
- `source=senado`;
- dataset, `ambito`, casa e prefixo do `texto_id` coerentes;
- `ano` e `mes` derivados da data oficial;
- `raw_run_id`, `raw_path`, `raw_source_id` e checksums preenchidos;
- as contagens JSONL e Parquet coincidem por base/ano/mês.

Comparar a fotografia anterior e a nova:

- fora de 2015–2016, conjuntos de `texto_id`, hashes dos textos e contagens são
  idênticos;
- em 2015–2016, adições, alterações e remoções são listadas por `texto_id`;
- Câmara é invariável em todos os anos;
- nenhum dos sete Parquets esperados desaparece;
- o manifest de normalização incorpora os `run_id`s históricos novos.

## 8. Validação do novo snapshot

Executar a etapa 00 com novo `analysis_run_id` e sem sobrescrever a rodada
anterior. Exigir:

- arenas observadas exatamente `camara`, `senado`, `congresso`;
- contagem maior que zero em 2015 e 2016 para as três arenas;
- nenhum ano completo ausente em qualquer arena requerida;
- 2026 continua YTD e inelegível à inferência anual;
- matriz completa de cobertura persistida, sem truncamento;
- reconciliação integral dos dois Parquets afetados;
- duplicatas Senado × Congresso explicadas no audit;
- manifest com checksums dos Parquets e contagens por arena.

## 9. Drift e fechamento

O `summary.json` deve conter:

- classificação final da anomalia da fonte;
- estratégia oficial usada e resultado da paridade;
- contagens `pre/post` por camada, dataset, ano e mês;
- totais adicionados, removidos e alterados por `texto_id`;
- casos sem texto e fila de transcrição;
- sentinelas e seus caminhos nas camadas;
- invariância fora do recorte;
- todos os gates e a decisão final.

Aceitar o ciclo somente se todos os gates automáticos passarem e a inspeção
manual de amostra confirmar casa, autor, data e texto. Caso contrário, manter
os artefatos, marcar o ciclo como rejeitado e não reexecutar as análises
posteriores.

## Falhas que bloqueiam o aceite

- Tratar `Sessoes=null` em 2015–2016 como prova de ausência de atividade.
- Usar somente o endpoint por senador sem auditar autores não cobertos.
- Aceitar amostra, página parcial ou paginação incompleta como backfill.
- Misturar pronunciamentos `SF` e `CN`.
- Concluir partição após falha inesperada de item.
- Editar ou substituir raw antigo.
- Regenerar Parquet a partir apenas dos `run_id`s do backfill e perder o corpus
  cumulativo.
- Fazer o caderno apenas imprimir anos ausentes sem falhar.
- Aceitar o ciclo com contagem positiva, mas reconciliação incompleta.
- Alterar qualquer dado fora do recorte sem justificativa nominal.
