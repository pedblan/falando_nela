# Dicionario de dados: `processed/textos_parlamentares/v1`

Cada linha representa uma unidade textual analitica normalizada.

| Campo | Descricao |
| --- | --- |
| `texto_id` | Identificador estavel da unidade textual, independente do `run_id` bruto. |
| `dataset_version` | Versao do contrato processed; nesta entrega, sempre `v1`. |
| `source` | Fonte bruta: `senado` ou `camara`. |
| `dataset` | Dataset bruto de origem, como `plenario_discursos`, `ccj_notas`, `ccjc_eventos` ou `pareceres_pec`. |
| `casa` | Casa parlamentar normalizada. |
| `ambito` | Ambito institucional: `plenario`, `congresso`, `ccj`, `ccjc`, `comissao_especial` ou `indeterminado`. |
| `orgao_sigla` | Sigla do orgao quando disponivel. |
| `orgao_nome` | Nome do orgao quando disponivel. |
| `documento_tipo` | Familia textual comum: `discurso`, `notas_taquigraficas` ou `parecer_pec`. |
| `unidade_analitica` | Granularidade: `pronunciamento`, `discurso`, `reuniao`, `evento` ou `parecer`. |
| `data` | Data ISO usada para analise temporal. |
| `data_hora` | Data/hora original quando a fonte fornece esse nivel de detalhe. |
| `ano` | Ano derivado de `data`, usado para particionamento. |
| `mes` | Mes derivado de `data`, usado para particionamento. |
| `titulo` | Titulo, identificacao ou descricao curta da unidade textual. |
| `resumo` | Resumo, ementa ou sumario quando fornecido pela fonte. |
| `indexacao` | Palavras-chave ou indexacao oficial quando disponivel. |
| `tipo_discurso` | Tipo de discurso/evento quando fornecido pela Camara ou pela fonte de notas. |
| `tipo_uso_palavra` | Classificacao de uso da palavra no Senado. |
| `fase_evento` | Fase do evento da Camara quando disponivel. |
| `parlamentar_id` | Identificador do parlamentar quando a unidade textual tem autoria individual. |
| `parlamentar_nome` | Nome parlamentar normalizado a partir da fonte. |
| `parlamentar_partido` | Partido do parlamentar quando disponivel. |
| `parlamentar_uf` | Unidade federativa do parlamentar quando disponivel. |
| `parlamentar_cargo` | Cargo informado ou inferido, como Senador(a) ou Deputado(a). |
| `pronunciamento_id` | Codigo do pronunciamento no Senado. |
| `sessao_id` | Codigo da sessao no Senado. |
| `reuniao_id` | Codigo de reuniao, usado principalmente para CCJ do Senado. |
| `evento_id` | Codigo de evento, usado principalmente para Camara. |
| `proposicao_id` | Identificador da proposicao/processo quando aplicavel. |
| `materia_id` | Codigo da materia no Senado quando aplicavel. |
| `documento_id` | Identificador do documento oficial quando aplicavel. |
| `proposicao_sigla` | Sigla da proposicao, como `PEC`. |
| `proposicao_numero` | Numero da proposicao. |
| `proposicao_ano` | Ano da proposicao. |
| `proposicao_identificacao` | Identificacao humana da proposicao, como `PEC 38/2011`. |
| `documento_classe` | Classe canonica de parecer/documento, como `parecer`, `relatorio`, `avulso_parecer` ou `voto_em_separado`. |
| `status_deliberativo` | Status canonico do parecer: `aprovado`, `rejeitado`, `proposto`, `vencedor`, `vencido` ou `indeterminado`. |
| `vencido` | Booleano derivado de `status_deliberativo == vencido`. |
| `texto` | Texto integral usado como corpus analitico. |
| `texto_tamanho` | Numero de caracteres de `texto`. |
| `texto_status` | Status textual herdado da coleta, como `disponivel`, `ausente` ou `erro`. |
| `forma` | Forma do conteudo na coleta, como `texto`, `documento` ou `sem_texto`. |
| `metodo_obtencao` | Metodo usado para obter o texto, como API textual, HTML do Escriba ou extracao de documento. |
| `url_texto` | URL oficial mais direta para o texto/documento. |
| `url_audio` | URL de audio quando aplicavel. |
| `url_video` | URL de video quando aplicavel. |
| `url_origem` | URL oficial de contexto ou origem principal. |
| `fontes` | Objeto com URLs oficiais preservadas em estrutura nativa. |
| `raw_run_id` | `run_id` do arquivo bruto usado. |
| `raw_record_type` | `record_type` bruto. |
| `raw_source_id` | `source_id` bruto. |
| `raw_partition` | Particao bruta original. |
| `raw_collected_at` | Timestamp de coleta bruta. |
| `raw_checksum` | Checksum calculado na coleta bruta sobre o payload. |
| `raw_path` | Caminho relativo do arquivo JSONL bruto. |
| `raw_response_url` | URL final registrada na resposta de coleta. |

