# Refundação GCP-first do Falando Nela

## Estado

Contrato GCP-first aprovado pelo pesquisador em `2026-08-11`, encerrando G00.
A implementação local de G01 e G02 está disponível, mas seus gates remotos
continuam pendentes: nenhum recurso, upload ou gasto foi executado. A execução
de G02 permanece bloqueada até a conclusão integral de G01 e até as aprovações
humanas registradas no contrato operacional.

## Direção aprovada

- projeto explícito `falando-nela-pedblan`;
- região única `southamerica-east1` (São Paulo);
- Cloud Storage como fonte oficial após migração integral e gate humano;
- Parquet no Cloud Storage como primeira camada analítica;
- Cloud Run Jobs para processamento fechado;
- Marimo editado localmente, versionado em Git e servido como app privado no
  Cloud Run;
- OpenTofu como executor de infraestrutura declarativa;
- Google Drive preservado como arquivo somente leitura após o corte;
- BigQuery adiado até o schema e as consultas justificarem sua adoção.

## Relação com a refundação anterior

Este contrato substitui somente as etapas ainda não iniciadas R04–R08 de
`specs/refundacao_local_first/`. As evidências concluídas de R00–R03 e R09,
incluindo a organização canônica do Drive, o piloto amostral e a limpeza
recuperável, continuam válidas e constituem a entrada desta refundação.

O executável atual continua local-first até o corte G05. A existência destas
specs não autoriza tratá-lo antecipadamente como cloud-first.

## Documentos

- `requirements.md`: comportamento e limites obrigatórios;
- `tech-stack.md`: recursos, ferramentas e topologia escolhidos;
- `plan.md`: sequência de unidades de trabalho e gates;
- `validation.md`: evidências necessárias para cada gate.
- `g01_fundacao_sentinela/`: contrato operacional da primeira fundação e do
  lote sentinela Drive→GCS.
- `g02_migracao_integral_corte/`: contrato operacional da cópia integral,
  reconciliação, restauração e corte humano da autoridade raw para o GCS.

## Baseline observada

Em `2026-08-11`, o projeto GCP estava ativo e com faturamento habilitado, sem
buckets, datasets BigQuery ou contas de serviço. Os nomes globais
`falando-nela-pedblan-data` e `falando-nela-pedblan-tfstate` retornaram `404`
em consulta explícita ao projeto; a disponibilidade deve ser revalidada
imediatamente antes de cada criação.
