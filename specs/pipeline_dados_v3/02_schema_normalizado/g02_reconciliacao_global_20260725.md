# Reconciliação da chamada global de G02 — 2026-07-25

## Escopo

Esta nota registra a conferência operacional dos artefatos já produzidos pela
chamada global `schema-global-gpt56-20260724`. A conferência foi somente
leitura. Não executou Batch, não aplicou a proposta, não materializou registros
normalizados e não alterou o `raw/`.

Pasta preservada no Drive:
`falando_nela/auditoria/pipeline_dados_v3/g02/schema-global-gpt56-20260724`.

## Entrada global

| Artefato | Linhas de dados | Bytes | SHA-256 |
|---|---:|---:|---|
| `catalogo_global_gpt56.txt` | 27.061 linhas totais | 1.343.124 | `78833a378079876b18ac38f412d90c4ef6211c83b1203bf08d799631235fbfbd` |
| `catalogo_global_crosswalk.csv` | 23.786 | 5.080.566 | `42413168597c1baa7b8a280c2c50968c7fe8acf0f702184b13cef947fb5f8dff` |
| `catalogo_global_amostras.csv` | 65 | 20.006 | `623d9ed47f878b94d6d67a0890f074358cbb88c3f0733d4e45f87d32184582c3` |

Os hashes recalculados coincidem com
`catalogo_global_manifest.json`. O manifest global referencia:

- operação G01 `raw-metadata-full-20260724t184418z`;
- SHA-256 aprovado do manifest G01
  `b54b1c7c686859b5d95e0e2a65aca6cc74e5f2504b0e3b6ae778af414292f3c9`;
- commit G01 `83378dd84aa26a19b16211cc24eb381c9788245e`;
- 1.148.754 registros observados;
- 1.148.740 registros legíveis;
- 14 rejeições;
- 50 grupos;
- 23.786 caminhos;
- 543 conflitos de tipo;
- 20.523 caminhos em `senado/ccj_notas`.

O hash do manifest G01 também foi recalculado e coincidiu com o valor
aprovado. Suas seis referências de saída registram os mesmos nomes, tamanhos,
linhas e hashes usados pela validação que precedeu a geração do catálogo.

Também foram conferidos:

- 23.786 `field_id` únicos;
- zero IDs ausentes ou inventados na reconstrução do catálogo;
- zero caminhos divergentes entre catálogo reconstruído e crosswalk;
- proposta com somente `field_id` existentes;
- invariantes de zero descarte, fusão, prioridade, preenchimento automático,
  leitura de raw e materialização de registro normalizado durante a geração
  do catálogo.

## Contagens da requisição

As três contagens têm escopos diferentes e, por isso, não devem ser
substituídas uma pela outra:

| Medição | Tokens de entrada | Interpretação |
|---|---:|---|
| medição preliminar registrada no caderno | 691.302 | arquivo + prompt, antes do recibo final |
| `upload_token_count.json` preservado | 691.339 | mesmo `file_id` e catálogo enviado |
| `submission_receipt.json` | 692.031 | requisição exata da geração, incluindo o JSON Schema fechado |

O limite conservador adotado foi 922.000 tokens. A geração usou
`truncation=disabled`, `max_output_tokens=32000`, modelo solicitado `gpt-5.6`
e `reasoning_effort=medium`.

## Saída e custo

| Item | Valor conferido |
|---|---|
| estado final | `completed` |
| erro | `null` |
| detalhes de incompletude | `null` |
| modelo resolvido | `gpt-5.6-sol` |
| tokens de entrada | 692.031 |
| tokens de saída | 13.712 |
| tokens de raciocínio | 1.182 |
| custo efetivo registrado | US$ 7,53735 |
| SHA-256 do texto de saída | `e7306e58aec20fe4c6bf808e5b02ecf9dd2aea02f5c787357cfdeb7714a7db2d` |
| proposta aplicada | `false` |
| gate registrado | `needs_human_review` |

O texto extraído de `response_raw.json`:

- reproduz exatamente o objeto de `proposta_schema_global.json`;
- satisfaz o JSON Schema Draft 2020-12 fechado;
- contém 40 candidatos canônicos, 10 famílias e 8 hipóteses de alias;
- mantém o status `proposal`;
- não foi aplicado a nenhum livro de decisões ou dado.

## Integridade dos artefatos JSON

| Artefato | SHA-256 recalculado |
|---|---|
| `status_latest.json` | `025ac1c35bd585af49331e6811070814573aedbbf4b6af4dd0c7a600dc00eac8` |
| `execution.json` | `d74d9a3cf92c534e8da8301b1bf042c9ec3958987c1f53c6f5e37492f1049dbc` |
| `proposta_schema_global.json` | `e4e38d5ca9bee0c1e493ee95b990a2d113aeb00d8a0fe8a6db8200d877df92fe` |
| `response_raw.json` | `751a57695a7548bef89403b8acffd3ad51cff2176a2c2f3bbb104186ae13be36` |
| `submission_receipt.json` | `0e2696633527cffe403062bb07d57192aaca05ff5f723b0880d5fc7f7c7f4f85` |
| `upload_token_count.json` | `052cc672ba32b607f63946826a0ff1ad76805639c58bad7ce6eb518a2bd47cbf` |
| `catalogo_global_manifest.json` | `c5cabb6d337a00b3ce3f2f151d7ec5a847e6ab8d756e2533a14f55b31d17ebff` |

## Resultado desta reconciliação

A chamada global e sua proposta estão reconciliadas e preservadas. Essa
conclusão fecha a conferência da chamada única, mas não fecha G02. Continuam
pendentes as atividades integrais que dependem da leitura do raw e, no
contrato atualmente aprovado, do mapeamento individual dos 23.786
`field_id`.

Naquele ponto da revisão, Batch continuava sem autorização. O pesquisador o
autorizou posteriormente, ainda em 2026-07-25, depois de aprovar integralmente
o vocabulário. A execução e seus limites estão documentados em
`g02_batch_e_auditoria_20260725.md`; ela continua sendo apenas uma proposta
não aplicada.
