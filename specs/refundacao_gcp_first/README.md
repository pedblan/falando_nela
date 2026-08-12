# Refundação GCP-first do Falando Nela

## Estado

Contrato GCP-first aprovado pelo pesquisador em `2026-08-11`. G00–G02 estão
concluídos: o raw integral foi reconciliado no GCS, que agora é a fonte oficial,
e o Drive permanece intacto como rollback. G03 está implementado e validado
localmente; fundação, build e execução remotos aguardam seu gate único.

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
- `g03_parquet_cloud_run/`: contrato, seleção auditável e validação do primeiro
  Parquet em Cloud Run Job.

## Baseline observada

Antes de G01, o projeto estava ativo e faturado, sem buckets, datasets BigQuery
ou contas de serviço; os dois nomes planejados retornavam `404`. Depois de G01,
existem os dois buckets previstos, a service account migradora sem chave, IAM
mínimo, budget e seis APIs gerenciadas. Depois de G02, o bucket de dados contém
os 2.887 objetos raw reconciliados e manifests de migração/corte. Não há dataset
BigQuery nem serviço de processamento; esses recursos não serão criados antes
do gate remoto G03.
