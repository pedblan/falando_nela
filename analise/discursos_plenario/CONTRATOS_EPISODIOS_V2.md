# Contratos dos episódios de interação v2

## Invariantes

- O recorte permanece inclusivo em `2010-02-02…2026-07-13`.
- Díades, testes, pontes e universo de candidatos continuam derivados da base
  relacional de apartes.
- `interacoes_segmentadas_ia.parquet`, `revisao_segmentacao_ia.csv` e todo
  `batch_segmentacao*` ou `batch_atos_fala_*` preexistente são v1 somente
  leitura.
- Há no máximo uma requisição de associação por `texto_id`, com todos os
  candidatos daquela transcrição.
- A resposta estruturada contém apenas `texto_id`, IDs de participantes,
  turnos/subturnos, status e listas de IDs; nunca contém trechos.
- Python é a única autoridade para reconstruir texto e offsets Unicode.
- Episódios de candidatos diferentes podem compartilhar turnos ou se
  sobrepor; dentro do mesmo episódio uma unidade não pode ter dois papéis.

## Entradas determinísticas v2

- `candidatos_episodios_v2.parquet`: candidatos ligados e seus participantes
  relacionais.
- `participantes_interacao_v2.parquet`: cadastro normalizado, por transcrição,
  apenas das pessoas conhecidas pela base relacional.
- `turnos_brutos_v2.parquet`: `turno_id`, falante observado, atribuição Python,
  ordem e offsets exatos.
- `unidades_turno_v2.parquet`: turnos e subturnos selecionáveis, com IDs
  estáveis e offsets.
- `fontes_episodios_v2.parquet`: uma linha por `texto_id`, roster, candidatos,
  índices e hashes necessários ao Batch.
- `ancoras_segmentacao_v1_v2.parquet`: projeção somente diagnóstica das
  localizações v1 nas unidades v2.

## Saída estruturada da IA

Cada candidato aparece uma vez com `status` e zero ou mais episódios. Cada
episódio contém:

- `falas_participante_ids`;
- `backchannels_ids`;
- `respostas_orador_ids`;
- `contexto_interveniente_ids`.

A IA também pode atribuir um `participante_id` conhecido a um turno que Python
marcou como ambíguo. Ela não pode substituir atribuições inequívocas nem criar
participantes.

## Saídas reconstruídas

- `episodios_interacao_v2.parquet`: uma linha por episódio, com textos
  reconstruídos por papel e uma visão cronológica.
- `episodio_turnos_v2.parquet`: relação normalizada muitos-para-muitos,
  papel, participante-alvo, ordem cronológica e offsets.
- `atribuicoes_falantes_v2.parquet`: somente ambiguidades resolvidas pela IA.
- `resultados_candidatos_episodios_v2.parquet`: status de todos os candidatos.
- `revisao_episodios_v2.csv`: piloto determinístico de aproximadamente 30
  episódios.

## Gate humano

Uma linha conta como revisada somente quando contém booleanos válidos para:

1. atribuição dos participantes;
2. completude do episódio;
3. atribuição das respostas;
4. suficiência do contexto.

O gate exige 30 revisões, precisão mínima de 95% em cada dimensão e aprovação
dos casos Geovania/Rogério, Júlio Campos e Izalci. Apenas
`qualitative_authorized_v2=true` permite gerar JSONL de atos de fala v2. O
envio ainda exige autorização paga separada e explícita.
