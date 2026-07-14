# Requisitos: análise comparativa dos discursos em plenário

## Interface e configuração

- A lógica deve ser importável de `analise.discursos_plenario`.
- O CLI deve aceitar `python -m analise.discursos_plenario ETAPA --data-root ... --run-id ...`.
- `config.v1.json` é a fonte única para datas, arenas, sementes, limiares,
  caminhos, modelos e ontologias.
- Entradas canônicas são somente leitura.
- Saídas devem ficar sob `analises/discursos_plenario/v1/{run_id}`.
- Runs existentes não podem ser sobrescritos silenciosamente.
- Manifests e saídas não podem conter credenciais ou o valor de variáveis de ambiente.

## Ambiente Colab

- `requirements-analise.txt` deve fixar conjuntamente `numpy==2.0.2` e
  `pandas==2.2.3`; o par não pode ser afrouxado ou atualizado isoladamente.
- A preparação deve reinstalar esse par sem usar o cache antes de instalar as
  demais dependências.
- Cada caderno deve validar as versões e importar NumPy e pandas no kernel e
  em um subprocesso antes de importar `analise.discursos_plenario`.
- Uma sessão que já tenha outra versão do NumPy carregada deve falhar cedo e
  orientar a reinicialização, sem prosseguir para as etapas analíticas.

## Snapshot

- Exigir as colunas mínimas `texto_id`, `source`, `dataset`, `ambito`, `data` e `texto`.
- Aplicar datas inclusivamente e validar a arena contra `source`, `dataset` e `ambito`.
- Manter `texto_original` imutável e `texto_analitico` separado.
- Aceitar na limpeza apenas regras `hard_cut` explicitamente aprovadas.
- Registrar regra aplicada, hash normalizado, palavras e elegibilidade.
- Marcar 2026 como YTD e excluir 2026 da elegibilidade anual completa.
- Manter `arena` e `casa_origem` em colunas distintas.

## Duplicações

- Auditar `texto_id` com conteúdos divergentes.
- Auditar Senado × Congresso primeiro por `texto_id` e `pronunciamento_id`.
- Exigir conteúdo, data, parlamentar e sessão compatíveis para remoção automática.
- Preservar a ocorrência Congresso quando a outra for uma cópia confirmada.
- Procurar quase duplicatas somente dentro de grupos data-autor compatíveis.
- Manter pares ambíguos no corpus e gravá-los na auditoria.

## Junção temporal e gênero

- Juntar por `source`, `parlamentar_id` e data inclusa em
  `vigencia_inicio…vigencia_fim`.
- Registrar ausência, múltiplos candidatos e critério de desempate.
- Preservar `genero_oficial` sem alterações.
- Aplicar uma camada pesquisada somente a candidatos aprovados por humano.
- `genero_presumido=true` deve significar pesquisa pública revisada, não dado oficial.

## Descritivas

- Produzir discursos, oradores, palavras, discursos por orador, média,
  mediana, desvio-padrão, p25, p75 e p90.
- Produzir taxas por mil dentro do denominador arena-período.
- Produzir diferença para o período anterior e para a mediana histórica.
- Painéis anuais e mensais devem poder receber dimensões adicionais.
- Bootstrap por orador exige texto não vazio no parâmetro `estimand`.
- O padrão é 2.000 reamostragens e semente `20260713`.

## Apartes

- Calcular tabela observada e esperada por independência dos marginais.
- Reportar razão observado/esperado, χ², graus de liberdade, valor-p, menor
  esperado e V de Cramér.
- Aplicar Fisher somente a tabelas 2×2 quando algum esperado for menor que 5.
- Aplicar BH por família declarada e preservar valores-p brutos.
- A ponte da Câmara deve ser derivada e não acrescentar campos ao Parquet canônico.
- Classificar vínculos em `exato`, `provavel_unico`, `ambiguo` e `ausente`.
- Não autorizar denominadores sem conjunto ouro, precisão e cobertura mensuradas.
- Ligar apartes do Senado por `pronunciamento_id` e auditar ambiguidades.
- Segmentar apenas fronteiras explícitas de turno; não inventar falas quando
  marcas taquigráficas estiverem ausentes.
- Extrair o turno do aparte e a resposta subsequente do orador principal como
  campos diferentes.
- Revisar amostra balanceada de 200 interações por arena, período e direção de gênero.
- Exigir pelo menos 100 revisões e precisão de 95% para aparte e resposta antes
  de liberar a classificação qualitativa.
- Manter exatamente as dez categorias de aparte e nove categorias de resposta
  registradas no config, além de `possivel_descortesia`.
- Não converter automaticamente “sem resposta explícita” em ato `ignorar`.
- Classificação de ato presente exige evidência textual da unidade correta.
- Gerar piloto humano adjudicado, avaliação por modelo, prevalência anual,
  diferença para mediana histórica e painéis por direção de gênero.

## NLP

- O pipeline oficial é `pt_core_news_lg`.
- TextDescriptives deve ser registrado como componente spaCy.
- Métricas customizadas devem usar tokens e dependências do mesmo `Doc`.
- A etapa deve aceitar processamento em lotes, limite de smoke e `n_process` explícito.
- O artefato principal deve manter `texto_id`, arena, ano e identificador do orador.

## Inferência

- Agregar métricas à média arena-ano antes de correlacionar trajetórias.
- Reportar Pearson, Spearman, valor-p, quantidade e faixa de anos.
- Repetir em primeiras diferenças.
- Aplicar BH separadamente a cada família declarada.
- Estimar tendência por OLS com covariância HAC/Newey–West e lag registrado.
- Reestimar sem 2020–2021.
- Excluir 2026 de todas essas análises.
- Não apresentar resultados como causais.

## Clusterização

- Usar `prop_pron`, `prop_adp` e `prop_aux` como configuração inicial.
- Padronizar as variáveis antes do K-Means.
- Avaliar todos os `k` de 2 a 8 com cinco critérios definidos na spec.
- Fixar sementes e registrar repetições de estabilidade.
- A etapa de avaliação não deve escolher `k` nem rótulos automaticamente.

## Tópicos

- Excluir resumo ausente ou vazio, sem usar texto integral como substituto.
- Amostrar no máximo 2.000 itens por arena-ano com semente fixa.
- Treinar um único modelo comum às três arenas.
- Fixar encoder, UMAP, HDBSCAN, vectorizer e stopwords.
- Persistir amostra, atribuições, tópicos, prevalência, cobertura e estabilidade.

## Figuras de linguagem e API

- A ontologia contém exatamente as 14 categorias do config.
- O schema estruturado deve avaliar todas as categorias e registrar presença,
  contagem, até três evidências e confiança.
- O padrão de produção é `gpt-5.6-sol`.
- Luna e Terra são candidatos de comparação, não substitutos automáticos.
- O piloto humano deve conter até 200 discursos balanceados por arena, período
  e faixa de extensão e produzir uma linha por discurso-categoria.
- A chave deve ser lida de `OPENAI_API_KEY` apenas em tempo de execução.
- Nenhuma chamada ocorre ao importar módulos ou executar testes.
- Produção usa arquivo JSONL com `custom_id` único e endpoint `/v1/responses`.
- A reconciliação deve tolerar respostas fora de ordem e separar erros.
- Custos devem ser calculados a partir de tabela de preços oficial com URL e
  data de consulta; nenhum preço fica congelado no código.
- A escolha de modelo menor exige piloto humano adjudicado e não inferioridade pré-registrada.
- Os mesmos requisitos de modelo, Structured Outputs, Batch, piloto e
  não inferioridade valem para a classificação dos atos de fala dos apartes.

## Jaccard

- Calcular por discurso e omitir vazio-vazio da média, reportando sua contagem.
- Reportar métricas por categoria e agregações micro/macro.
- Bootstrap de diferença entre modelos deve ser pareado e clusterizado por orador.
- Permutações devem preservar os estratos declarados.
- Reportar semente, repetições, intervalo e direção da diferença.

## Portabilidade e tradução

- Toda célula Markdown deve ter ID estável e `language=pt-BR`.
- Toda etapa cara depende de um booleano de execução explícita.
- Código substantivo não deve existir exclusivamente no notebook.
- Notebooks não devem depender de magias IPython.
- Variantes inglesas futuras alteram somente Markdown.
- Código das variantes deve ter hash idêntico e mesma ordem de células.
- Conversões Marimo futuras devem rodar como script e com `marimo run`.
