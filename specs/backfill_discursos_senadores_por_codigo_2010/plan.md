# Plano: backfill de discursos de senadores por código desde 2010

## Objetivo

Recuperar somente pronunciamentos de senadores que a auditoria oficial por
CodigoParlamentar encontrou, mas que ainda não existem no raw cumulativo de SF
ou CN. A recuperação usa CodigoPronunciamento como identidade do discurso e
nunca consulta, compara ou deduplica por nome.

## População de entrada

1. Rodar a auditoria até uma data de corte explícita.
2. Exigir que errors, invalid_probe_lines, invalid_raw_lines e
   source_conflicts sejam zero.
3. Usar exatamente o arquivo senator_endpoint_missing_ids.jsonl daquela
   auditoria como população fechada.
4. Separar a população por house: SF grava em plenario_discursos e CN grava em
   congresso_discursos.

A execução de 2026-07-14 encontrou 7.580 IDs ausentes: 7.245 em SF e 335 em
CN. Essa é uma evidência datada; o coletor não codifica essas contagens como
constante.

## Recuperação

1. Ler e validar data, casa, dataset, CodigoPronunciamento e metadados brutos.
2. Deduplicar somente por CodigoPronunciamento; duplicatas divergentes falham
   antes de qualquer requisição.
3. Varrer o raw cumulativo para pular IDs já presentes e tornar uma nova
   execução segura depois de uma interrupção.
4. Para cada ID faltante, reutilizar o pipeline oficial de texto integral,
   notas de sessão e fila de transcrição dos coletores do Senado.
5. Gravar o texto em sua partição ano/mês original, com source_id
   SF:pronunciamento:CODIGO ou CN:pronunciamento:CODIGO.
6. Preservar a proveniência da auditoria, CodigoParlamentar e data oficial.

## Aceite

SF e CN rodam em sequência, com locks independentes. Um manifest só é aceito
com status completed e errors igual a zero. Depois dos dois manifests, a mesma
auditoria é executada com resume, strict e require-complete. Não gerar
derivados ou snapshot enquanto houver qualquer lacuna de senador.
