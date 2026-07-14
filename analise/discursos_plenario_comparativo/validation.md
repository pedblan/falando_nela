# Validação: análise comparativa dos discursos em plenário

## Estrutural

```bash
.venv/bin/python -m pytest tests/test_analysis_colab_notebooks.py
.venv/bin/python -m pytest tests/test_discursos_plenario.py
```

- Abrir cada `.ipynb` com `nbformat`.
- Compilar por `ast.parse` todas as células Python.
- Confirmar Drive na primeira célula executável.
- Confirmar `numpy==2.0.2` e `pandas==2.2.3` em `requirements-analise.txt` e
  na célula compartilhada de preparação dos dez cadernos.
- Confirmar reinstalação sem cache e smoke de importação no kernel e em
  subprocesso antes de `analise.discursos_plenario`.
- Confirmar IDs únicos, metadados `language=pt-BR` e controle explícito das etapas caras.
- Confirmar ausência de magias indispensáveis e credenciais literais.
- Executar o gerador em modo de conferência e exigir árvore limpa.

## Snapshot sintético

- Incluir exatamente `2010-02-02` e `2026-07-13`.
- Excluir `2010-02-01` e `2026-07-14`.
- Excluir fontes, datasets e âmbitos incompatíveis com a arena.
- Uma fixture com `senado/2015=0` ou `congresso/2016=0` deve falhar com arena e
  ano na mensagem; a matriz completa deve passar.
- `run_snapshot` deve persistir `annual_coverage.csv`,
  `missing_complete_years.csv` e `coverage_gate` no manifest antes de falhar.
- A célula autônoma do caderno 00 deve aplicar o mesmo gate aos anos completos,
  sem reprovar apenas pela ausência parcial do ano YTD.
- Preservar Câmara, Senado e Congresso separadamente.
- Exigir a presença exata das três arenas, sem aceitar subconjuntos.
- Mostrar resumo por arena, matriz completa de 2010–2026 e lista explícita de
  anos sem discursos em cada arena; não truncar a tabela com `tail`.
- Executar a célula autônoma contra um snapshot já pronto sem reexecutar a
  geração nem a instalação de dependências.
- Marcar 2026 YTD e nunca elegível à inferência anual completa.
- Demonstrar que `texto_original` não muda após um `hard_cut` aprovado.
- Rejeitar regra não aprovada ou com ação diferente.

## Duplicação

- Remover a cópia Senado somente quando ID, conteúdo, data, autor e sessão concordarem.
- Não remover falas semelhantes em sessões diferentes.
- Enviar hash exato sem ID concordante para revisão.
- Enviar quase duplicata compatível para revisão.
- Reportar conflito quando o mesmo `texto_id` tiver conteúdo divergente.

## Junção temporal e gênero

- Testar datas nas duas bordas do intervalo de vigência.
- Testar parlamentar sem ID, data ausente, ausência de período e múltiplos períodos.
- Demonstrar que `genero_oficial` permanece inalterado.
- Rejeitar candidato identificado sem URL, título e trecho.
- Rejeitar publicação sem `revisor` e `revisado_em`.
- Demonstrar que candidatos pendentes e rejeitados não alteram o snapshot.
- Simular cliente GPT; não realizar pesquisa web em testes automatizados.

## Estatística sintética

- Comparar média, mediana, desvio-padrão e quantis a valores calculados manualmente.
- Exigir `estimand` para bootstrap e confirmar reprodutibilidade da semente.
- Para uma tabela 2×2 conhecida, comparar esperado, razão O/E, χ², Fisher e V de Cramér.
- Para uma tabela maior, demonstrar que Fisher não é aplicado.
- Comparar BH a exemplo conhecido e confirmar monotonicidade na ordem dos valores-p.

## Ponte

- Criar casos exato, provável único, ambíguo e ausente.
- Verificar que sessão diferente impede remoção/ligação automática indevida.
- Medir precisão contra um conjunto ouro sintético.
- Demonstrar que ausência de conjunto ouro bloqueia denominadores.
- Testar limiares imediatamente abaixo, no valor e acima do corte.
- Segmentar transcrição sintética com aparte e resposta marcados.
- Testar texto sem marcador, aparteante ausente, múltiplos turnos candidatos e
  resposta não explícita.
- Confirmar que o texto inteiro do discurso nunca substitui `texto_aparte`.
- Revisar 200 casos balanceados e exigir ao menos 100 preenchidos no gate.
- Testar o gate de 95% separadamente para aparte e resposta.
- Validar que o schema contém todas as dez categorias de aparte, nove de
  resposta e `possivel_descortesia`, sem duplicatas.
- Confirmar que ato presente sem evidência é rejeitado pelo pós-processamento.
- Comparar Jaccard, F1 e kappa do piloto humano para cada unidade.
- Verificar prevalências, diferenças para a mediana e estratos de direção de gênero.

## NLP

- Anotar exemplos mínimos para pronomes sujeito, interrogativa, perífrase com
  `ir`, passiva com `ser`, cópula avaliativa e os dois padrões literais.
- Validar que proporções têm denominador de tokens alfabéticos.
- Rodar smoke no Colab com `pt_core_news_lg` e comparar colunas esperadas.
- Registrar versão do modelo e dos pacotes no manifest do ambiente.

## Séries e clusters

- Comparar Pearson e Spearman a vetores conhecidos.
- Confirmar primeira diferença e exclusão de 2026.
- Confirmar sensibilidade sem 2020–2021.
- Comparar coeficiente HAC a ajuste `statsmodels` equivalente.
- Em dados sintéticos separáveis, avaliar todos os `k=2…8`.
- Em dados sem estrutura, aceitar decisão humana de ausência de clusters estáveis.
- Confirmar que nenhum rótulo substantivo é criado automaticamente.

## Tópicos

- Demonstrar exclusão de resumo vazio.
- Demonstrar teto por arena-ano e reprodutibilidade da amostra.
- Confirmar um único modelo para todas as arenas.
- Verificar outliers, prevalências que somam um por arena-ano e marca YTD.
- Rodar smoke reduzido; reservar resultados científicos ao corpus completo no Drive.

## Batch e avaliação

- Validar JSONL, unicidade de `custom_id`, schema e endpoint.
- Simular upload e criação de Batch.
- Confirmar balanceamento do piloto e suas 14 linhas por discurso.
- Rejeitar cálculo de custo com preço, URL ou data ausentes.
- Simular respostas completas, com erro, inválidas e fora de ordem.
- Confirmar que vazio-vazio não aumenta a média de Jaccard.
- Comparar precisão, recall, F1 e kappa a casos manuais.
- Confirmar bootstrap pareado por orador e permutação dentro de estratos.
- Testar erro absoluto médio e viés em contagens conhecidas.

## Execução completa no Colab

1. Em uma sessão nova, rodar a preparação e exigir a linha
   `ABI: NumPy 2.0.2; pandas 2.2.3`.
2. Rodar 00 e revisar inventário, duplicações e junção temporal.
3. Congelar o manifest do snapshot.
4. Rodar 01, realizar revisão humana e publicar somente aprovados.
5. Rodar 02–07, revisando cada manifest antes da etapa seguinte.
6. Completar codebook e piloto do 08 antes de qualquer Batch de produção.
7. Registrar a decisão entre Luna, Terra e Sol.
8. Rodar 09 e conferir CSV, Parquet, HTML, SVG e PNG.
9. Reexecutar top-to-bottom com o mesmo config; exigir mesmas contagens e
   equivalência numérica dentro das tolerâncias registradas.

## Portabilidade futura

- Converter cópia com `marimo convert`, revisar dependências e executar com
  `python` e `marimo run`.
- Comparar manifests, schemas, contagens e métricas.
- Na variante inglesa, comparar hashes de todas as células de código, ordem de
  células, parâmetros e saídas; exigir tradução para cada ID Markdown e passar
  o glossário metodológico.
