# Requisitos operacionais — G03 Parquet em Cloud Run Job

## Objetivo

Executar o primeiro processamento cloud-first do Falando Nela: ler os 30
pronunciamentos já aprovados no piloto R03, produzir um Parquet Zstandard
determinístico e publicá-lo com proveniência sob prefixo imutável. O mesmo
código deve funcionar com fixture local e dentro de um Cloud Run Job.

## Recorte congelado

- **G03-INPUT-01:** `selection.json` é a seleção auditável do piloto
  `pilot-senado-plenario-discursos-2010-11cdb7c533c2b1b0`: 30 registros do
  Senado, `plenario_discursos`, `pronunciamento_texto`, ano substantivo 2010.
- **G03-INPUT-02:** cada seleção fixa locator raw, linha, identidade e SHA-256
  dos bytes JSON. A execução GCS lê apenas os locators necessários sob
  `data/raw/v1/` e recusa registro ausente ou divergente.
- **G03-INPUT-03:** a execução local pode ler diretamente o gzip aprovado da
  amostra, cujo SHA-256 armazenado é
  `09ce1293e61ca8d8ef8691b35d87319c957e89bbc3bd109b239ae7623ed9b0cc`.
  Local e GCS devem reconstruir o mesmo JSONL selecionado, com SHA-256
  descompactado
  `1f887cd8363fce4aeb4e5ceb7d704be50a363af921beecddbda2cf75005ac484`.
- **G03-INPUT-04:** nenhuma API parlamentar, Drive ou coleta integra este
  processamento. A fonte oficial é o raw imutável no bucket GCS aprovado em
  G02.

## Transformação e saída

- **G03-DATA-01:** o pipeline será código Python sob `src/falando_nela/`, não
  uma transformação embutida em caderno.
- **G03-DATA-02:** a tabela terá schema explícito e estreito para o piloto,
  preservando proveniência, IDs oficiais, sessão, autoria, partido/UF, tipo da
  fala, texto e hashes. Mudança do schema exige nova versão do contrato.
- **G03-DATA-03:** as linhas serão ordenadas por `source_id`; texto e metadados
  da fonte serão transportados sem inferência semântica.
- **G03-DATA-04:** o arquivo usará Parquet 2.6, páginas v2 e compressão
  Zstandard. Uma mesma versão de código, dependências, entrada e configuração
  deve produzir o mesmo hash binário; versões distintas devem ao menos manter
  o mesmo fingerprint lógico.
- **G03-DATA-05:** a saída será criada em
  `data/processed/v1/g03/senado/plenario_discursos/ano=2010/operation_id=<id>/`
  e o manifesto fechado em `manifests/processing/g03/<id>/manifest.json`.
  Objetos existentes só podem ser reutilizados após igualdade byte a byte.
- **G03-DATA-06:** temporários permanecem no diretório de trabalho. Nenhum
  Parquet parcial ou não validado será publicado.

## Operação recuperável

```text
materialize_input -> write_parquet -> validate -> publish
```

- **G03-OPS-01:** cada etapa registra `running` antes do trabalho e
  `completed` somente depois de persistir e conferir o artefato.
- **G03-OPS-02:** o manifesto local registra operation ID, versões,
  fingerprints de entrada/configuração, tentativas, horários, hashes e erros.
- **G03-OPS-03:** uma retomada reaproveita etapa concluída quando o artefato e
  seu hash continuam válidos. Entrada, configuração ou versão divergente
  bloqueia o mesmo operation ID.
- **G03-OPS-04:** publicação usa criação condicional. Se a resposta remota for
  interrompida, a retomada reconcilia o conteúdo antes de tentar novamente;
  não duplica nem substitui objetos.
- **G03-OPS-05:** o protocolo não exige aprovação entre etapas locais. Há um
  único gate humano remoto após revisão do plano OpenTofu, da imagem candidata,
  da estimativa e do comando de execução.

## Container e infraestrutura

- **G03-RUN-01:** a imagem usa Python 3.13, `uv.lock` e entrada pela CLI
  `falando-nela parquet-pilot`; a referência de produção será um digest do
  Artifact Registry associado ao commit.
- **G03-RUN-02:** OpenTofu declara APIs necessárias, repositório regional,
  service accounts `fn-builder` e `fn-pipeline`, IAM condicionado aos prefixos
  e Cloud Run Job. O pacote-fonte do build usa somente
  `operations/builds/g03/` no bucket já existente.
- **G03-RUN-03:** o job fica em `southamerica-east1`, com uma tarefa, sem
  paralelismo, uma tentativa, 1 CPU, 1 GiB e timeout de 10 minutos.
- **G03-RUN-04:** o runtime usa credencial curta da service account anexada,
  sem chave JSON, ADC gravada ou projeto implícito.
- **G03-RUN-05:** logs principais contêm IDs, contagens, hashes, duração e
  estado; não imprimem texto integral, token ou URL assinada.

## Gate remoto enxuto

Uma aprovação cobre a sequência delimitada de criação da infraestrutura G03,
build único, publicação por digest e uma execução do job. Antes dela devem
estar visíveis: diff/plan, imagem candidata, estimativa abaixo de US$ 0,10,
máximo de uma tentativa e condição de parada. Qualquer recurso ou gasto fora
desse envelope exige nova decisão.

## Modelo e esforço por requisito

| ID | Modelo | Nível de esforço |
| --- | --- | --- |
| G03-INPUT-01 | GPT-5.3-Codex-Spark | Baixo |
| G03-INPUT-02 | GPT-5.3-Codex-Spark | Médio |
| G03-INPUT-03 | GPT-5.3-Codex-Spark | Baixo |
| G03-INPUT-04 | GPT-5.3-Codex-Spark | Baixo |
| G03-DATA-01 | GPT-5.3-Codex-Spark | Médio |
| G03-DATA-02 | GPT-5.3-Codex-Spark | Médio |
| G03-DATA-03 | GPT-5.3-Codex-Spark | Médio |
| G03-DATA-04 | GPT-5.3-Codex-Spark | Médio |
| G03-DATA-05 | GPT-5.3-Codex-Spark | Médio |
| G03-DATA-06 | GPT-5.3-Codex-Spark | Médio |
| G03-OPS-01 | GPT-5.3-Codex-Spark | Médio |
| G03-OPS-02 | GPT-5.3-Codex-Spark | Médio |
| G03-OPS-03 | GPT-5.3-Codex-Spark | Alto |
| G03-OPS-04 | GPT-5.3-Codex-Spark | Alto |
| G03-OPS-05 | GPT-5.3-Codex-Spark | Médio |
| G03-RUN-01 | GPT-5.3-Codex-Spark | Médio |
| G03-RUN-02 | GPT-5.3-Codex-Spark | Alto |
| G03-RUN-03 | GPT-5.3-Codex-Spark | Médio |
| G03-RUN-04 | GPT-5.3-Codex-Spark | Médio |
| G03-RUN-05 | GPT-5.3-Codex-Spark | Médio |
| G03-GATE-01 | GPT-5.3-Codex-Spark | Médio |

## Não objetivos

- Processar outros anos, casas, datasets ou o corpus integral.
- Alterar o schema normalizado global do pipeline v3.
- Criar BigQuery, Dataflow, Batch, serviço Marimo ou agendamento periódico.
- Atualizar, remover ou reescrever o raw no GCS ou o arquivo no Drive.
- Executar o apply, build remoto ou job antes do gate remoto acima.
