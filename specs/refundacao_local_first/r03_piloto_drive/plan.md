# Plano operacional — R03 piloto raw do Drive

- [x] Delimitar o estrato piloto e corrigir seu `record_type` pelo contrato do coletor.
- [x] Registrar baseline, pasta, partições e limites conhecidos sem baixar raw.
- [x] Implementar a base do adaptador local e do adaptador `rclone` estritamente read-only.
- [x] Implementar reconciliação da baseline G01 por caminho e tamanho.
- [x] Implementar manifesto atômico reutilizável com estados de etapa explícitos.
- [x] Implementar inventário streaming sem materializar a população integral.
- [x] Implementar ranking determinístico e congelamento de exatamente 1%.
- [x] Implementar segunda passagem e gzip determinístico somente dos selecionados.
- [x] Implementar validação, publicação imutável, retomada e bloqueio por divergência.
- [x] Cobrir o fluxo com fixtures, falhas injetadas e contadores de leitura.
- [x] Validar localmente sem rede, credencial ou pasta de produção.
- [x] Concluir e reconciliar a organização copy-first que precede o piloto.
- [x] Registrar a raiz antiga como `falando_nela_arquivo`, preservando seu ID, e a pasta `falando_nela_refundacao` como reserva fora da operação.
- [x] Criar pelo remote `drive.file` a nova raiz operacional `falando_nela` e registrar seu ID por readback.
- [x] Comprovar acesso canônico `rclone` com `drive.readonly` e ID literal.
- [x] Executar o preflight real e reconciliar os 2.891 arquivos da baseline.
- [x] Executar o piloto real de 2010 e revisar os artefatos antes de fechar R03.

## Gate

O código local pode ser concluído com fixtures, mas nenhum conteúdo raw remoto
será lido antes da conclusão e reconciliação da organização. O ID da nova pasta
operacional já foi confirmado como `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
A listagem de metadados pelo conector é somente descoberta e não substitui o
preflight reproduzível por `rclone`.

Evidência local de `2026-08-03`: `sample pilot` implementa preflight autenticado
pelo catálogo, ledger SQLite sem payload, ranking estável, duas passagens,
gzip determinístico, publicação imutável e quota. Fixtures com 100 registros
comprovaram seleção independente da ordem, reexecução sem terceira leitura,
bloqueio de duplicata, entrada alterada, destino divergente e espaço
insuficiente.

Evidência real de `2026-08-03`: a organização publicou e autenticou o catálogo
dos 2.887 JSONL antes de qualquer leitura de conteúdo. A operação
`r03-sample-pilot-2010-20260803`, usando o remote `drive.readonly` fixado no ID
canônico, reconciliou 11 arquivos e 89.253.442 bytes, contou `N=2.996`, congelou
`k=30` e publicou a amostra imutável
`pilot-senado-plenario-discursos-2010-11cdb7c533c2b1b0`. O gzip tem 169.507
bytes, SHA-256 armazenado
`09ce1293e61ca8d8ef8691b35d87319c957e89bbc3bd109b239ae7623ed9b0cc` e
SHA-256 descompactado
`1f887cd8363fce4aeb4e5ceb7d704be50a363af921beecddbda2cf75005ac484`.
A reexecução fez zero stream remoto e preservou o mesmo arquivo.
