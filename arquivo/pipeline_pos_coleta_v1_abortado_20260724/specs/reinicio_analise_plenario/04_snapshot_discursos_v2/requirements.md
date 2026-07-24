# Requisitos — snapshot de discursos v2

Status: **schema aprovado — smoke implementado; execução real pendente**.

## Objetivo

Gerar um snapshot novo, imutável e auditável dos discursos disponíveis nas
bases textuais canônicas aprovadas. O snapshot v2 deve corrigir a falta de
clareza sobre o universo do corpus sem incorporar decisões da análise
abortada.

## Decisões prévias

O pesquisador aprovou:

- **D03:** três bases e a unidade comum de intervenção textual oficial;
- **D04:** período inclusivo de `2010-01-01` a `2026-07-13`;
- **D05:** preservar todos os IDs, sem deduplicação entre fontes.

O schema aprovado está em
[`proposta_schema_snapshot_v2.md`](proposta_schema_snapshot_v2.md).

Essa aprovação permite um smoke determinístico, com até 20 registros elegíveis
e 20 excluídos por base, gravado fora do Drive. Ela não permite executar ou
promover o snapshot integral.

## Censo de entrada autorizado

O gate
[`proposta_gate_censo.md`](proposta_gate_censo.md)
autoriza medir, sem criar snapshot:

- `camara__plenario_discursos.parquet`;
- `senado__plenario_discursos.parquet`;
- `senado__congresso_discursos.parquet`.

O censo leu somente metadados e colunas de controle, gravou fora do Drive e foi
revisado antes da aprovação de D03–D05. CCJ, CCJC, pareceres, apartes
relacionais, amostras e a análise v1 não são entradas.

## Contrato funcional

- **SNP-R01 — fontes aprovadas:** somente bases processadas inspecionadas
  diretamente na fase 4 e aprovadas pelo pesquisador podem alimentar o
  snapshot. O inventário exploratório orienta a busca, mas não decide
  canonicidade.
- **SNP-R02 — independência:** manifests, segmentações, revisões e
  classificações da análise v1 não podem ser entradas.
- **SNP-R03 — preservação:** o snapshot anterior permanece imutável e
  identificável; v2 é um novo artefato, não uma sobrescrita.
- **SNP-R04 — unidade:** deve existir exatamente uma definição aprovada de
  “discurso” e uma regra explícita para cada fonte que a materializa.
- **SNP-R05 — identificador estável:** cada discurso deve ter ID determinístico
  ou ID canônico de origem, com estratégia documentada para colisões.
- **SNP-R06 — proveniência por linha:** cada registro deve permitir localizar
  fonte, dataset, arquivo ou objeto de origem e identificador original.
- **SNP-R07 — campos mínimos:** ID, fonte, arena, data, texto, autor quando
  disponível, identificador original e campos de proveniência devem ter tipos
  e nulabilidade documentados.
- **SNP-R08 — regras visíveis:** normalização, exclusão e deduplicação devem ser
  aplicadas em etapas nomeadas, com contagens antes/depois e motivo.
- **SNP-R09 — duplicidade conservadora:** equivalências incertas são
  preservadas e sinalizadas. Apenas duplicatas comprovadas pela regra D05
  podem ser removidas.
- **SNP-R10 — sem elegibilidade analítica:** apartes, disponibilidade de
  transcrição, comprimento, gênero inferido, sucesso de NLP ou adequação a um
  prompt não podem restringir o snapshot.
- **SNP-R11 — corte temporal:** datas inválidas, ausentes e fora do corte devem
  ter tratamento explícito e contagens separadas.
- **SNP-R12 — texto:** texto vazio, ilegível ou anormal deve ser sinalizado;
  exclusão exige regra aprovada e relatório.
- **SNP-R13 — identidade da versão:** `snapshot_id`, data de geração, commit,
  versão da spec, hashes das entradas e hash da saída devem ser registrados.
- **SNP-R14 — cobertura:** o relatório deve mostrar contagens por fonte,
  dataset, arena, ano e estado de qualidade, além do total geral.
- **SNP-R15 — comparação:** diferenças em relação ao snapshot anterior devem
  ser explicadas por fonte e por regra, sem pressupor que o anterior está
  correto.
- **SNP-R16 — separação de execuções:** `snapshot_id` não pode ser usado como
  `analysis_run_id`; análises futuras referenciam o snapshot sem modificá-lo.

## Artefatos

- snapshot principal em Parquet;
- schema legível e validável;
- `relatorio.md` de cobertura;
- `manifest.json` compacto;
- tabelas de contagens por etapa;
- tabela de registros problemáticos ou decisões pendentes;
- comparação com o snapshot anterior.

## Fora de escopo

- segmentar apartes ou turnos;
- chamar modelos OpenAI;
- selecionar amostra analítica;
- inferir relações entre participantes;
- classificar atos de fala;
- substituir bases processadas de origem.
