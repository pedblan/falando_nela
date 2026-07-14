# Plano: auditoria de cobertura de discursos de senadores desde 2010

## Objetivo

Detectar pronunciamentos de senadores que existem na fonte oficial, mas não
existem no raw cumulativo. A auditoria abrange SF e CN de 2010-01-01 até um
corte explícito e não altera raw, derivados ou snapshots.

## Método

1. Determinar as legislaturas que interceptam a janela.
2. Para cada legislatura, consultar a lista oficial de senadores e extrair
   apenas CodigoParlamentar.
3. Para cada ano, casa e código ativo, consultar o endpoint individual de
   discursos com janela anual e versão 5.
4. Inventariar CodigoPronunciamento, data e casa retornados.
5. Ler somente pronunciamento_texto do raw de plenario_discursos (SF) e
   congresso_discursos (CN).
6. Comparar a fonte com o raw pelo identificador do pronunciamento, sem usar
   nome de parlamentar como chave.

## Limite de cobertura

O endpoint por senador fecha a população de discursos de senadores. Em CN,
ele não cobre deputados nem outras autoridades; portanto
raw_ids_not_in_senator_endpoint é uma observação, não uma perda. A condição
de completude é a direção inversa: cada ID encontrado por senador deve estar
no raw da casa correspondente.

## Retomada e saídas

Cada resposta é anexada imediatamente a
operations/auditorias/discursos_senadores/{audit_id}/senator_endpoint_probes.jsonl.
Em --resume, respostas válidas são reutilizadas e erros anteriores são
tentados novamente.

O diretório também contém coverage.csv, missing_ids.jsonl, conflicts.jsonl,
errors.jsonl e summary.json. Um backfill posterior deve usar
senator_endpoint_missing_ids.jsonl como população fechada; esta auditoria não
executa esse backfill.
