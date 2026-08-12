# Requisitos operacionais — G04 app Marimo privado

## Objetivo

Criar localmente e depois publicar o primeiro app Marimo do ciclo GCP-first para
consultar o recorte G03 (30 discursos de 2010) diretamente do Parquet aprovado no
GCS, sem leitura do Drive e sem persistência de estado local relevante. O primeiro
recorte verificável é o app no Mac via ADC; container, IAM e Cloud Run formam o
recorte remoto seguinte do mesmo G04.

## Recorte e fonte oficial

- **G04-INPUT-01:** o app terá como único dataset aprovado o parquet em
  `data/processed/v1/g03/senado/plenario_discursos/ano=2010/operation_id=g03-pilot-20260812-t120`
  no bucket `falando-nela-pedblan-data`.
- **G04-INPUT-02:** o app usará um `operation_id` explícito e recusará caminho
  vazio/indefinido.
- **G04-INPUT-03:** qualquer ajuste de caminho de entrada em produção exige mudança
  contratual em spec.
- **G04-INPUT-04:** a execução interativa local usa GCS por padrão. Testes sem
  GCP/ADC selecionam explicitamente `FALANDO_NELA_G04_SOURCE=fixture` e informam
  `FALANDO_NELA_G04_FIXTURE`; não existe fallback automático entre fontes.
- **G04-INPUT-05:** o dataset deve retornar 30 registros e preservar metadados de
  autoria, data e fonte.
- **G04-INPUT-06:** project ID, bucket, `operation_id`, locator, schema e contagem
  esperada permanecem congelados no contrato `config/gcp.toml` versão 6.

## Comportamento funcional

- **G04-FUNC-01:** app exibe resumo simples (número de registros, ano, dataset,
  `operation_id` e horário de carga local).
- **G04-FUNC-02:** exibe no mínimo uma visualização tabular dos discursos (colunas
  principais) com ordenação estável por `source_id`.
- **G04-FUNC-03:** filtros locais de texto, partido e UF são opcionais e não alteram
  o contrato nem escrevem na fonte.
- **G04-FUNC-04:** recusa explicitamente arquivo indisponível, parquet vazio ou schema
  incompatível com versão conhecida.
- **G04-FUNC-05:** não grava nem tenta gravar no GCS; não usa filesystem como fonte
  de confiança.
- **G04-FUNC-06:** o script correspondente deve validar imports, contrato e leitura
  com fixture explicitamente configurada e sair com sucesso sem sessão interativa.

## Operação e execução

- **G04-RUN-01:** o notebook deve rodar com `marimo edit --host 127.0.0.1`
  localmente e, no recorte remoto posterior, com `marimo run --host 0.0.0.0 -p 8080`.
- **G04-RUN-02:** o app terá política de escala inicial `0` e máximo `1` na primeira
  etapa.
- **G04-RUN-03:** o recurso Cloud Run deverá ter somente requisição autenticada
  via IAM (sem anônimo).
- **G04-RUN-04:** o runtime usará service account dedicada (`fn-marimo`) com somente
  leitura no prefixo `data/processed/v1/g03/` e manifests auxiliares.
- **G04-RUN-05:** logs do serviço incluirão contagem, operação e duração do
  carregamento, sem texto integral de discurso ou credenciais.

## Segurança e contrato

- **G04-SEC-01:** identidade de execução sem chave JSON.
- **G04-SEC-02:** bloqueio explícito de `allUsers`/`allAuthenticatedUsers`.
- **G04-SEC-03:** sem editor remoto e sem exposição por URL pública.
- **G04-SEC-04:** sem acesso de escrita ao raw, operação de coleta e serviço
  `fn-migrator`.

## Gates de revisão enxutos

O recorte local fica pronto para avaliação quando houver:

1. validação local de `marimo check` e execução do script;
2. smoke local via ADC confirmando 30 registros do GCS contratado;
3. revisão visual em `127.0.0.1`, sem exposição na rede local;
4. testes provando fixture explícita, ausência de fallback e recusa de contrato
   divergente.

O G04 completo continua exigindo, no recorte remoto posterior, plano de
infraestrutura, identidade `fn-marimo`, publicação privada e smoke autenticado.

Não há aprovações intermediárias para cada microajuste de layout; a revisão ocorre
apenas sobre contrato de leitura, segurança e disponibilidade.

## Modelo e esforço por requisito

| ID | Modelo | Nível de esforço |
| --- | --- | --- |
| G04-INPUT-01 | GPT-5.3-Codex-Spark | Baixo |
| G04-INPUT-02 | GPT-5.3-Codex-Spark | Baixo |
| G04-INPUT-03 | GPT-5.3-Codex-Spark | Médio |
| G04-INPUT-04 | GPT-5.3-Codex-Spark | Médio |
| G04-INPUT-05 | GPT-5.3-Codex-Spark | Baixo |
| G04-INPUT-06 | GPT-5.3-Codex-Spark | Médio |
| G04-FUNC-01 | GPT-5.3-Codex-Spark | Médio |
| G04-FUNC-02 | GPT-5.3-Codex-Spark | Médio |
| G04-FUNC-03 | GPT-5.3-Codex-Spark | Baixo |
| G04-FUNC-04 | GPT-5.3-Codex-Spark | Médio |
| G04-FUNC-05 | GPT-5.3-Codex-Spark | Baixo |
| G04-RUN-01 | GPT-5.3-Codex-Spark | Médio |
| G04-RUN-02 | GPT-5.3-Codex-Spark | Médio |
| G04-RUN-03 | GPT-5.3-Codex-Spark | Alto |
| G04-RUN-04 | GPT-5.3-Codex-Spark | Alto |
| G04-RUN-05 | GPT-5.3-Codex-Spark | Médio |
| G04-SEC-01 | GPT-5.3-Codex-Spark | Médio |
| G04-SEC-02 | GPT-5.3-Codex-Spark | Médio |
| G04-SEC-03 | GPT-5.3-Codex-Spark | Médio |
| G04-SEC-04 | GPT-5.3-Codex-Spark | Alto |
| G04-GATE-01 | GPT-5.3-Codex-Spark | Médio |

## Não objetivos

- Não ampliar para consulta completa, agregações permanentes ou atualização
  periódica.
- Não usar o Drive como fonte operacional nem como fallback automático em produção.
- Não abrir o app ao público ou remover autenticação.
- Não incluir mutações de dados no app (sincronização, escrita ou cache persistente).
