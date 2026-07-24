# Plano — relatórios operacionais do Colab

Status: **fase 2 concluída — validação real pertence à fase 3**.

1. Inventariar os formatos atuais de relatório, manifest e log.
2. Identificar redundâncias, campos sem uso e informações ausentes.
3. Propor o vocabulário de estados e os campos mínimos.
4. Criar exemplos estáticos de relatório de sucesso, revisão pendente e falha.
5. Definir o JSON Schema e o catálogo de artefatos propostos.
6. Fazer o teste de compreensão com o pesquisador.
7. Aprovar D06.
8. Implementar uma biblioteca pequena e reutilizável.
9. Simular localmente sucesso, alerta, falha e reexecução.
10. Aplicar primeiro ao notebook de inventário, como piloto sem custo de API.
11. Só então incorporar o padrão aos demais notebooks novos.

## Estratégia para o legado

Os artefatos antigos serão catalogados pelo submódulo 03. Não serão regravados.
Quando possível, um índice novo apontará para eles e explicará suas limitações.

## Ponto de parada

Se o pesquisador precisar abrir o log para entender uma execução normal, o
modelo de relatório deve ser corrigido antes de avançar para outro notebook.

## Progresso

- [x] Formatos legados inventariados.
- [x] Redundâncias e ambiguidades identificadas.
- [x] Vocabulário e campos mínimos propostos.
- [x] Três relatórios estáticos produzidos.
- [x] JSON Schema e catálogo propostos.
- [x] Teste de compreensão e revisão do pesquisador.
- [x] Aprovação de D06 em 2026-07-23.
- [x] Biblioteca reutilizável implementada.
- [x] Sucesso, alerta, falha e reexecução simulados em testes locais.
- [x] Padrão incorporado ao notebook piloto do inventário do Drive.
- [x] Relatório real validado na operação `drive-inventory-20260724t020749z`.
