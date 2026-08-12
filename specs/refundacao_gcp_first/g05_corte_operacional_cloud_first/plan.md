# Plano operacional — G05 corte cloud-first

## Estado e fronteira

As specs foram criadas em `2026-08-12`. O candidato G00–G04 foi revisado e
consolidado nos commits `a4482b9` e `fa2527a`; a implementação continua na
branch dedicada `codex/refundacao-g05-cloud-first`. G05 produz um único
resultado: o caminho cloud-first reproduzível integrado em `main`.

## Modelo e esforço por tarefa

| ID | Tarefa | Modelo | Nível de esforço |
| --- | --- | --- | --- |
| G05-P01 | Criar `requirements.md`, `plan.md` e `validation.md` próprios e sincronizar as specs-raiz. | GPT-5.3-Codex-Spark | Baixo |
| G05-P02 | Consolidar o candidato G00–G04 sem descartar alterações e criar a branch dedicada de G05. | GPT-5.6-Codex | Médio |
| G05-P03 | Auditar entrypoints, defaults, metadata e documentação que ainda descrevem operação local-first. | GPT-5.3-Codex-Spark | Médio |
| G05-P04 | Tornar GCS o default de produção onde aplicável e manter fixture local explícita, com testes direcionados. | GPT-5.6-Codex | Médio |
| G05-P05 | Criar o README canônico e atualizar descrição do pacote, apresentação do núcleo e índice de notebooks. | GPT-5.3-Codex-Spark | Médio |
| G05-P06 | Documentar execução, deploy existente, acesso ao Marimo, rollback, custo e diagnóstico. | GPT-5.3-Codex-Spark | Médio |
| G05-P07 | Auditar referências a Colab/Drive e preservar somente usos históricos ou de manutenção claramente rotulados. | GPT-5.3-Codex-Spark | Médio |
| G05-P08 | Executar testes direcionados de defaults, divergências de alvo e fixture sem credenciais. | GPT-5.6-Codex | Médio |
| G05-P09 | Revisar o diff por escopo, segredos, state, caches e artefatos acidentais. | GPT-5.3-Codex-Spark | Médio |
| G05-P10 | Commitar o candidato e criar clone limpo local a partir do commit exato. | GPT-5.6-Codex | Alto |
| G05-P11 | Executar instalação, Ruff, pytest, doctor, Marimo e OpenTofu no clone limpo. | GPT-5.6-Codex | Alto |
| G05-P12 | Apresentar evidências e obter o gate humano único para integrar e publicar `main`. | GPT-5.3-Codex-Spark | Baixo |
| G05-P13 | Integrar o candidato aprovado em `main` sem reescrever histórico e publicar no GitHub. | GPT-5.6-Codex | Alto |
| G05-P14 | Verificar igualdade entre `main` e `origin/main` e fechar os checklists das specs. | GPT-5.3-Codex-Spark | Médio |

## Acompanhamento

- [x] Criar `requirements.md`, `plan.md` e `validation.md` próprios e sincronizar as specs-raiz.
- [x] Consolidar o candidato G00–G04 sem descartar alterações e criar a branch dedicada de G05.
- [ ] Auditar entrypoints, defaults, metadata e documentação que ainda descrevem operação local-first.
- [ ] Tornar GCS o default de produção onde aplicável e manter fixture local explícita, com testes direcionados.
- [ ] Criar o README canônico e atualizar descrição do pacote, apresentação do núcleo e índice de notebooks.
- [ ] Documentar execução, deploy existente, acesso ao Marimo, rollback, custo e diagnóstico.
- [ ] Auditar referências a Colab/Drive e preservar somente usos históricos ou de manutenção claramente rotulados.
- [ ] Executar testes direcionados de defaults, divergências de alvo e fixture sem credenciais.
- [ ] Revisar o diff por escopo, segredos, state, caches e artefatos acidentais.
- [ ] Commitar o candidato e criar clone limpo local a partir do commit exato.
- [ ] Executar instalação, Ruff, pytest, doctor, Marimo e OpenTofu no clone limpo.
- [ ] Apresentar evidências e obter o gate humano único para integrar e publicar `main`.
- [ ] Integrar o candidato aprovado em `main` sem reescrever histórico e publicar no GitHub.
- [ ] Verificar igualdade entre `main` e `origin/main` e fechar os checklists das specs.

`[x]` exige evidência no repositório ou na execução; `[ ]` permanece pendente
até que o critério literal seja cumprido. Checkboxes não autorizam push, merge
ou qualquer efeito remoto.

## Sequência de execução

A execução acompanha os checkboxes acima: primeiro consolida a base e ajusta o
menor recorte de comportamento; depois atualiza documentação, valida o commit em
clone limpo e apresenta uma única revisão antes da integração e do push.

Falhas localizadas voltam apenas à etapa afetada. A suíte completa será repetida
depois de mudanças capazes de afetá-la, evitando ciclos cerimoniais sem hipótese
nova.

## Gate único

O gate G05 ocorre depois do clone limpo e antes da integração em `main`. A
aprovação cobre somente o commit apresentado, a estratégia de integração sem
reescrita e o push para `origin/main`. Se o commit mudar depois da aprovação,
validar o delta e reapresentar o candidato.

## Envelope de custo e interrupção

```text
Hipótese: o corte é documental, de defaults e Git; não precisa alterar a GCP.
Amostra mínima: testes direcionados antes da suíte completa em um clone limpo.
Número máximo de operações remotas novas: um push aprovado para origin/main.
Estimativa de gasto GCP: US$ 0,00; nenhum build, deploy, job ou upload.
Condição de parada: regressão sem correção localizada, credencial/artefato no diff,
necessidade de mudar infraestrutura ou três falhas equivalentes sem hipótese nova.
```
