# Cadernos do pipeline de dados v3 — consulta legada

> **Status desde R09:** estes notebooks permanecem disponíveis apenas para
> consulta histórica. Seus comandos Colab não constituem o fluxo operacional
> cloud-first.

Estes cadernos reconstruirão a linha pós-coleta usando somente
`/content/drive/MyDrive/falando_nela/data/raw` como entrada imutável.

## Passo 01 — inventário de metadados raw

`01_inventario_metadados_raw_colab.ipynb`:

- verifica que `data/` contém somente `raw/`;
- faz um smoke determinístico por fonte, dataset e formato;
- grava os sete artefatos temporários somente sob `/content`;
- não chama a OpenAI;
- não escreve no Drive;
- mantém a execução completa bloqueada até a revisão humana do smoke.

Não use `Run all` para autorizar uma operação. As flags de smoke e execução
completa nascem desligadas e cada gate exige a cópia literal do respectivo
`operation_id`.

## Passo 02 — evidências para o schema normalizado

`02_schema_normalizado_colab.ipynb`:

- confere a operação G01 aprovada e o fingerprint atual do `raw/`;
- relê os registros estruturados em modo somente leitura;
- produz livro de campos, conflitos, rejeições, aliases, samples e pacotes de
  proposta;
- separa amostras estruturais `evidence` de previews `context_only`;
- mantém a preparação, a aprovação de previews, o piloto GPT-5.6 e a avaliação
  A/B em gates independentes, desligados por padrão;
- reutiliza as variáveis já validadas de G01 para gerar, sem reler o raw, um
  catálogo TXT compacto com os 23.786 caminhos e um crosswalk integral;
- usa o perfil `schema_core` para manter no TXT apenas as estatísticas
  necessárias ao desenho global, preservando todas as métricas no crosswalk;
- separa o upload `user_data` e a contagem exata de tokens da futura chamada
  global, permitindo interromper antes de qualquer geração;
- submete, quando explicitamente confirmado, uma única chamada global em
  background e grava imediatamente catálogo e `response_id` no Drive;
- consulta a chamada em célula separada, valida a proposta contra o crosswalk
  e registra uso e custo sem aplicar o resultado;
- não materializa dados normalizados nem aplica propostas do modelo.

O piloto reutiliza `OPENAI_API_KEY` apenas do cofre de secrets do Colab. A
chave não é exibida nem escrita em artefatos. Uma tabela JSON de preços,
versionada pelo pesquisador, é obrigatória para registrar o custo calculado.
O catálogo global é enviado como TXT, não CSV. A execução `schema_core` medida
em 2026-07-24 teve 691.302 tokens para arquivo + prompt; a célula de submissão
recontou 692.031 tokens incluindo o JSON Schema. A chamada terminou sem
truncamento e permaneceu não aplicada. Depois da revisão e da autorização
específica, o mapeamento integral foi preparado em 99 requisições Batch com
`gpt-5.6-sol`. A tentativa principal e dois reparos disjuntos reconciliaram
23.786 propostas únicas, que continuam não aplicadas e não avaliadas
humanamente. G02 continua pendente mesmo quando todas as células técnicas
terminam.

Um `git pull` atualiza o arquivo `.ipynb` no clone, mas não acrescenta células
à interface de um caderno que já está aberto. Nesse caso, mantenha o runtime e
use `python -m pipeline_dados_v3.schema_normalizado global-submit` e
`global-status` em uma célula curta. Os subcomandos usam os mesmos caminhos,
gates, recibos, validações e regra de não aplicação das células 12 e 13.

Para a continuação controlada do mapeamento integral, a CLI também oferece:

- `batch-prepare`, que congela o vocabulário, cria a entrada JSONL e não chama
  a API;
- `batch-count`, que conta a entrada exata e registra a estimativa de custo;
- `batch-submit`, que exige `--execute-batch` e confirmação literal da
  operação;
- `batch-status`, que consulta, baixa e reconcilia a saída quando ela termina.
- `batch-repair-prepare`, que cria um lote menor somente com os IDs ainda não
  validados;
- `batch-merge`, que exige a união disjunta das tentativas e comprova a
  cobertura final.

Nenhum desses comandos aplica o schema, modifica o raw ou materializa
Parquets.
