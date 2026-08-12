# Plano operacional — G03 Parquet em Cloud Run Job

- [x] Congelar em `selection.json` os 30 registros e hashes do piloto R03.
- [x] Criar requisitos, plano e validação próprios para G03.
- [x] Implementar materialização equivalente a partir do gzip local e do raw GCS.
- [x] Implementar schema e escrita Parquet Zstandard determinística.
- [x] Implementar manifesto, publicação create-only e retomada por operation ID.
- [x] Expor o recorte pela CLI com alvos GCP confirmados literalmente.
- [x] Criar imagem OCI reproduzível a partir do lockfile.
- [x] Declarar Artifact Registry, APIs, IAM mínimo e Cloud Run Job em OpenTofu.
- [x] Cobrir formatos, entrada inválida, hashes, schema, falha e retomada com testes sem rede.
- [x] Executar fixture real de 30 registros e registrar hashes localmente.
- [x] Validar Ruff, pytest, lockfile e OpenTofu sem efeitos remotos.
- [ ] Revisar e aprovar o plano remoto, a imagem, a estimativa e a execução única.
- [ ] Criar a infraestrutura G03 aprovada e publicar a imagem por digest.
- [ ] Executar o job uma vez e comparar conteúdo lógico com a execução local.
- [ ] Reexecutar o mesmo operation ID e comprovar reutilização sem nova escrita.

## Gate

Código, testes, container e IaC podem avançar juntos até a validação local. O
primeiro efeito remoto exige somente o gate único descrito em
`requirements.md`; não há aprovações intermediárias para cada etapa do job.

G03 termina quando local e Cloud Run publicam conteúdo lógico equivalente, o
prefixo remoto é imutável, a retomada é comprovada e custo/duração ficam
registrados.

## Estado local em 2026-08-12

O recorte local está pronto para o gate remoto. A execução nativa e a imagem
Linux/amd64 não-root produziram 30 linhas, um row group, Parquet 2.6 Zstandard,
SHA-256 binário
`c518b4211d3fb0982469161fc3f2d0d3832ee75e2b37ad990143238b179044a1`
e fingerprint lógico
`2fb781b8188ec7b4b8029f5b9e4873cab376be742f52b9cd712fbb4197dc0e71`.
A repetição reutilizou as quatro etapas sem nova escrita.

O plano real da fundação, consultando o state remoto sem aplicar, resultou em
`15 add / 0 change / 0 destroy`, sem Cloud Run Job antes da existência da
imagem por digest. O plano binário temporário teve SHA-256
`f82b93ca37b1cccade5ee5a0a0ed5ef41e0118aa0ee7335f8275b82d55ddf7e9`;
ele deve ser regenerado e revisto no gate porque o state pode mudar.
