# Cadernos do pipeline de dados v3

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
reconta incluindo o JSON Schema. Batch só poderá ser usado depois da revisão
do vocabulário global. G02 continua pendente mesmo quando todas as células
técnicas terminam.

Um `git pull` atualiza o arquivo `.ipynb` no clone, mas não acrescenta células
à interface de um caderno que já está aberto. Nesse caso, mantenha o runtime e
use `python -m pipeline_dados_v3.schema_normalizado global-submit` e
`global-status` em uma célula curta. Os subcomandos usam os mesmos caminhos,
gates, recibos, validações e regra de não aplicação das células 12 e 13.
