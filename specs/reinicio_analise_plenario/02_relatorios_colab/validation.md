# Validação — relatórios operacionais do Colab

Status: **D06 aprovado e biblioteca validada localmente em 2026-07-23**.

## Evidência do contrato

- [`proposta_d06.md`](proposta_d06.md) reúne vocabulário, campos e gate;
- [`catalogo_artefatos.md`](catalogo_artefatos.md) separa os papéis dos
  arquivos;
- os exemplos cobrem [sucesso](exemplos/relatorio_sucesso.md),
  [revisão pendente](exemplos/relatorio_revisao.md) e
  [falha](exemplos/relatorio_falha.md);
- o [manifest de exemplo](exemplos/manifest_revisao.json) deve validar contra
  o [JSON Schema proposto](schema/manifest.schema.json);
- a aprovação humana foi registrada em 2026-07-23;
- o notebook piloto foi implementado e testado com os gates desligados;
- a validação contra o Drive real continua pendente da execução da fase 3.

## Validação local da biblioteca

A implementação está em
[`../../../relatorios_operacionais/core.py`](../../../relatorios_operacionais/core.py)
e os testes em
[`../../../tests/test_relatorios_operacionais.py`](../../../tests/test_relatorios_operacionais.py).

O conjunto local cobre:

- as 21 chaves obrigatórias e a validação pelo JSON Schema;
- a leitura independente de `execution_status` e `scientific_gate`;
- os caminhos canônicos do relatório, manifest, log e artefatos;
- a recusa de sobrescrita implícita;
- a reexecução com novo `operation_id`;
- o JSONL estruturado e a rejeição de segredos;
- o registro mínimo recuperável de uma falha.

## Teste principal: compreensão sem log

Após uma execução de teste, o pesquisador deve conseguir responder usando
somente `relatorio.md` e a célula final:

1. o que foi executado;
2. sobre qual universo e período;
3. quantas unidades entraram, saíram ou foram excluídas;
4. se o programa terminou;
5. se o resultado foi aprovado cientificamente;
6. onde estão as saídas;
7. qual é a próxima ação.

Se for necessário abrir o manifest ou o log para responder, o relatório
reprova.

## Validações automáticas

- validar o manifest contra um JSON Schema versionado;
- verificar unicidade e formato de `operation_id`;
- verificar existência ou resolubilidade de entradas, saídas e referências;
- recalcular contagens centrais a partir dos artefatos de saída;
- confirmar a separação entre `execution_status` e `scientific_gate`;
- rejeitar campos obrigatórios ausentes;
- procurar padrões de segredo nos três artefatos;
- limitar a saída normal do notebook ao resumo definido;
- testar a geração do registro mínimo em uma falha simulada.

## Matriz de evidências

| Requisito | Evidência |
|---|---|
| REL-R01, REL-R02, REL-R03, REL-R04 | relatório de sucesso revisado |
| REL-R05, REL-R06 | relatórios de revisão pendente e falha revisados |
| REL-R07 | comparação com execução anterior no futuro notebook piloto |
| REL-R08, REL-R09, REL-R10 | manifests válidos, identificáveis e rastreáveis |
| REL-R11, REL-R12, REL-R13 | configuração referenciada e JSON Schema |
| REL-R14 | log JSONL separado em teste local |
| REL-R15, REL-R16 | notebook piloto validado localmente; execução real pendente |
| REL-R17 | catálogo de artefatos aprovado |
| REL-R18 | testes de rejeição de segredos |
| REL-R19 | teste de falha simulada com registro mínimo recuperável |

## Critérios de concisão

- o relatório principal deve caber em uma leitura breve;
- tabelas detalhadas ficam em anexos referenciados;
- o manifest não repete configurações ou listas volumosas;
- o log não é usado como interface humana;
- mensagens repetidas são agregadas por tipo e contagem.

## Condições de reprovação

- `succeeded` interpretado como aprovação científica;
- contagens sem universo;
- traceback integral como resumo;
- artefato sem finalidade declarada;
- configuração duplicada integralmente em cada manifest;
- próximo passo ausente;
- segredo ou token exposto.
