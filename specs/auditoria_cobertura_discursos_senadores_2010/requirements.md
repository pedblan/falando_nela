# Requirements: auditoria de cobertura de discursos de senadores desde 2010

## CLI

    python -m coleta.senado.auditoria_discursos_historicos \
      --cycle-dir CAMINHO \
      --data-root /content/drive/MyDrive/falando_nela/data \
      --data-inicio 2010-01-01 --data-fim AAAA-MM-DD \
      --houses SF CN --resume --strict

- cycle-dir recebe apenas artefatos operacionais da auditoria.
- data-root habilita a comparação com o raw; sem ele, a execução somente
  inventaria a fonte.
- houses aceita SF, CN ou ambas.
- strict falha depois de persistir os artefatos se houver erro de fonte, JSONL
  inválido ou conflito de casa/data.
- require-complete exige também que todo ano/casa tenha estado complete e só
  pode ser usado com data-root.

## Identidade e fonte

- A única chave de consulta de parlamentar é CodigoParlamentar.
- A única chave de comparação de discursos é CodigoPronunciamento.
- Nomes, inclusive nomes com diacríticos, são conteúdo bruto; não podem
  aparecer em busca, deduplicação ou critério de completude.
- Uma resposta de lista de senadores com erro torna inconclusivos os anos
  afetados pela legislatura.

## Critérios por ano/casa

- complete: fonte não vazia, sem erro/conflito e todos os IDs de senador no
  raw e no ano oficial.
- incomplete: há ID de senador ausente ou em ano errado no raw.
- inconclusive: erro de requisição, conflito ou JSONL inválido.
- empty_source: a fonte válida não devolveu ID algum; exige investigação.
- source_only: data-root não foi informado.

O raw é imutável: a auditoria nunca cria pronunciamento_texto, checkpoint,
manifest de coleta, Parquet ou snapshot.
