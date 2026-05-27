# Plano: metadados de parlamentares

## Objetivo

Criar um modulo transversal para baixar metadados oficiais de parlamentares da
Camara dos Deputados e do Senado Federal no mesmo periodo dos bancos de textos,
permitindo correlacionar discursos, notas e pareceres com atributos como
genero, sexo informado pela fonte, partido, UF, mandato e legislatura.

O periodo baseline do projeto continua sendo `2011-05-18` a `2026-05-18`.
Esse intervalo cobre, no fluxo atual, as legislaturas 54, 55, 56 e 57.

## Fontes

### Camara

- Portal: Dados Abertos da Camara dos Deputados.
- Lista/descoberta: `GET /api/v2/deputados`, preferencialmente filtrando por
  legislaturas ou por `dataInicio` e `dataFim`.
- Detalhe: `GET /api/v2/deputados/{id}`, que inclui dados civis, nascimento,
  ultimo status e `sexo`.
- Historico parlamentar: `GET /api/v2/deputados/{id}/historico`, quando
  disponivel, para recuperar mudancas de partido, UF, situacao e legislatura.
- Arquivo completo opcional: `arquivos/deputados/json/deputados.json`, usado
  como fallback ou auditoria para a lista de IDs.

### Senado

- Portal: Dados Abertos Legislativos do Senado Federal e Congresso Nacional.
- Lista por legislatura:
  `GET /dadosabertos/senador/lista/legislatura/{inicio}/{fim}.json`.
- Lista atual: `GET /dadosabertos/senador/lista/atual.json`.
- Detalhe: `GET /dadosabertos/senador/{codigo}.json`.
- Mandatos: `GET /dadosabertos/senador/{codigo}/mandatos.json`.
- Filiacoes: `GET /dadosabertos/senador/{codigo}/filiacoes.json`.
- O cliente deve enviar `Accept: application/json` e usar sufixo `.json` quando
  suportado. Se algum servico oficial retornar apenas XML, o coletor deve fazer
  parse estruturado de XML e preservar o payload bruto normalizado no envelope.

## Fluxo

- Descobrir IDs oficiais de parlamentares a partir das listas oficiais de cada
  casa para as legislaturas que interceptam `--data-inicio` e `--data-fim`.
- Complementar a lista de IDs com os IDs ja encontrados em `raw/` e em
  `processed/textos_parlamentares/v1`, quando houver dados disponiveis no mesmo
  `data_root`.
- Para cada deputado descoberto, baixar detalhe e historico.
- Para cada senador descoberto, baixar detalhe, mandatos e filiacoes.
- Gravar todas as respostas oficiais como metadados brutos, sem criar particao
  mensal de corpus textual.
- Normalizar a camada bruta em uma dimensao processada
  `processed/parlamentares/v1`.
- Gerar uma tabela de intervalos pronta para juncao temporal com
  `textos_parlamentares/v1`.
- Produzir auditoria de cobertura da juncao entre textos e metadados de
  parlamentares.

## Saidas brutas

- `data/raw/camara/parlamentares/metadata/{run_id}.jsonl`.
- `data/raw/senado/parlamentares/metadata/{run_id}.jsonl`.
- `data/checkpoints/camara/parlamentares.json`.
- `data/checkpoints/senado/parlamentares.json`.
- `data/logs/{run_id}.jsonl`.
- `data/manifests/{run_id}.json`.
- `data/manifests/{run_id}.autosave.json`.

Registros brutos esperados:

- `camara_deputados_page`;
- `camara_deputado_detalhe`;
- `camara_deputado_historico`;
- `senado_parlamentares_legislatura`;
- `senado_parlamentares_atual`;
- `senado_senador_detalhe`;
- `senado_senador_mandatos`;
- `senado_senador_filiacoes`.

## Saidas processed

Criar o dataset processado `parlamentares/v1`:

- `processed/parlamentares/v1/parlamentares.jsonl`: uma linha por
  `source/parlamentar_id`, com atributos pessoais estaveis.
- `processed/parlamentares/v1/mandatos.jsonl`: uma linha por mandato,
  legislatura ou periodo oficial de exercicio.
- `processed/parlamentares/v1/filiacoes.jsonl`: uma linha por filiacao
  partidaria quando a fonte oferecer historico.
- `processed/parlamentares/v1/parlamentares_periodos.jsonl`: tabela
  denormalizada e intervalar para juncao com textos por data.
- `processed/parlamentares/v1/parquet/*.parquet`: Parquets equivalentes aos
  JSONLs acima.
- `processed/manifests/{run_id}-parlamentares.json`: manifest da normalizacao.
- `processed/audits/parlamentares/{run_id}/`: relatorios de cobertura da
  juncao com `textos_parlamentares/v1`.

## Juncao com textos

- A chave canonica do parlamentar e `parlamentar_key = "{source}:{id}"`.
- Textos processados devem juntar com `parlamentares_periodos` por:
  `source`, `parlamentar_id` e `data` dentro de `vigencia_inicio` e
  `vigencia_fim`.
- Quando houver mais de um periodo valido, escolher o intervalo mais especifico
  e registrar a ambiguidade em auditoria.
- Quando `parlamentar_id` estiver ausente no texto, nao inferir parlamentar por
  nome sem etapa explicita de reconciliacao.
- A camada `textos_parlamentares/v1` nao deve depender de inferencia por nome
  para preencher genero. A fonte de verdade para genero/sexo fica em
  `parlamentares/v1`.

## Integracao operacional

- Manter o caderno Colab `notebooks/coleta/coleta_parlamentares.ipynb` como
  caminho recomendado para validar, rodar e retomar a coleta completa no Drive.
- Incluir o coletor na rotina de atualizacao depois das coletas brutas de
  textos e antes da normalizacao analitica final, para que novos IDs
  descobertos pelos textos tambem sejam enriquecidos.
- Em expansoes de base, todo novo coletor deve preservar o ID oficial do
  parlamentar quando a fonte disponibilizar esse campo.
- A normalizacao de textos deve continuar preenchendo
  `parlamentar_id`, `parlamentar_nome`, `parlamentar_partido`,
  `parlamentar_uf` e `parlamentar_cargo` quando esses dados estiverem no
  proprio payload, mas a analise de genero deve usar a dimensao
  `parlamentares/v1`.
- Amostras locais devem incluir amostras ou Parquets pequenos de
  `parlamentares/v1`, suficientes para validar joins em notebooks locais.

## Dev e producao

- `dev`: limitar a poucas legislaturas/IDs por `--sample-limit`, gravando em
  `data/dev`.
- `prod`: baixar todas as legislaturas que interceptam o periodo informado,
  gravando em diretorio externo, normalmente Google Drive via
  `FALANDO_NELA_DATA_ROOT`.
- O modulo previsto e:

```bash
python -m coleta.parlamentares.collect \
  --mode prod \
  --resume \
  --run-id prod-parlamentares-YYYYMMDD \
  --data-inicio 2011-05-18 \
  --data-fim 2026-05-18
```

## Resiliencia operacional

- Usar `coleta.common.cli` para os parametros comuns.
- Suportar `--source camara|senado|all`, com `all` como default.
- Gravar JSONL linha a linha, checkpoint e autosave durante a execucao.
- Com `--resume`, pular IDs e endpoints ja gravados para o mesmo `run_id`.
- Registrar cabecalhos de deprecacao, `Sunset`, `Retry-After` e `Link` no
  envelope bruto quando aparecerem.
- Respeitar `Retry-After` e limitar a taxa do Senado para evitar HTTP 429.
- Falhas por parlamentar ou endpoint devem ir para log/checkpoint sem derrubar
  a coleta das demais casas.
