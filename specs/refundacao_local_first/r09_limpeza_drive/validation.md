# Validação — R09 limpeza de versões antigas no Drive

- [x] Confirmar os dez IDs; a soma listada de 33.715 objetos e 76.816.050.775 bytes inclui uma subárvore duas vezes, enquanto o universo único é de 24.190 objetos e ao menos 76.137.269.495 bytes.
- [x] Confirmar 106 notebooks ou objetos Colab na seleção de preservação.
- [x] Confirmar que nenhum caminho relativo colide após o prefixo de origem.
- [x] Validar JSON de todos os arquivos preservados, sem exceções.
- [x] Comparar SHA-256 do staging local com download da biblioteca remota, sem ausências ou divergências.
- [x] Confirmar que nove alvos foram enviados diretamente à Lixeira e o décimo acompanhou uma dessas raízes como descendente.
- [x] Confirmar que nenhum ID fora da tabela foi alterado.
- [x] Confirmar que `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq` permanece fora da Lixeira.
- [x] Confirmar 2.887 objetos e 14.686.043.352 bytes no raw canônico.
- [x] Confirmar que a biblioteca de consulta permanece acessível depois da limpeza.

Resultado: 106 arquivos JSON válidos, 84.622.105 bytes e zero divergência na
biblioteca de consulta. A busca regular não retornou nenhum dos dez IDs antigos;
o raw canônico reconciliou caminho, tamanho e hashes contra o catálogo R03.
