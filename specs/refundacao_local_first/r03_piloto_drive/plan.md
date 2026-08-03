# Plano operacional — R03 piloto raw do Drive

- [x] Delimitar o estrato piloto e corrigir seu `record_type` pelo contrato do coletor.
- [x] Registrar baseline, pasta, partições e limites conhecidos sem baixar raw.
- [x] Implementar a base do adaptador local e do adaptador `rclone` estritamente read-only.
- [x] Implementar reconciliação da baseline G01 por caminho e tamanho.
- [x] Implementar manifesto atômico reutilizável com estados de etapa explícitos.
- [ ] Implementar inventário streaming sem materializar a população integral.
- [ ] Implementar ranking determinístico e congelamento de exatamente 1%.
- [ ] Implementar segunda passagem e gzip determinístico somente dos selecionados.
- [ ] Implementar validação, publicação imutável, retomada e bloqueio por divergência.
- [ ] Cobrir o fluxo com fixtures, falhas injetadas e contadores de leitura.
- [ ] Validar localmente sem rede, credencial ou pasta de produção.
- [ ] Concluir e reconciliar a organização copy-first que precede o piloto.
- [x] Registrar a raiz antiga como `falando_nela_arquivo`, preservando seu ID, e a pasta `falando_nela_refundacao` como reserva fora da operação.
- [x] Criar pelo remote `drive.file` a nova raiz operacional `falando_nela` e registrar seu ID por readback.
- [ ] Configurar e comprovar o remote canônico `rclone` com `drive.readonly`.
- [ ] Executar o preflight real e reconciliar os 2.891 arquivos da baseline.
- [ ] Executar o piloto real de 2010 e revisar os artefatos antes de fechar R03.

## Gate

O código local pode ser concluído com fixtures, mas nenhum conteúdo raw remoto
será lido antes da conclusão e reconciliação da organização. O ID da nova pasta
operacional já foi confirmado como `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
A listagem de metadados pelo conector é somente descoberta e não substitui o
preflight reproduzível por `rclone`.
