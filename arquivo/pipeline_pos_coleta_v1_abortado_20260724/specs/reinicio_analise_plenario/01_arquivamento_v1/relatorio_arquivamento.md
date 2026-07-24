# Relatório do arquivamento da análise v1

Status: **concluído e validado em 2026-07-23**.

## Resultado

A tentativa v1 foi retirada das áreas ativas e preservada em:

`notebooks/arquivo/analise_plenario_v1_abortada_20260723/`

O arquivo contém índice próprio, marcador científico, estrutura original e os
53 artefatos aprovados no mapa.

## Reconciliação

| Verificação | Resultado |
|---|---:|
| Arquivos no mapa | 53 |
| Bytes esperados e encontrados | 794.298 |
| SHA-256 divergentes | 0 |
| Destinos ausentes | 0 |
| Origens mantidas por engano | 0 |
| Arquivos antigos apagados | 0 |

`tests/test_discursos_historicos.py` foi preservado integralmente no arquivo e
recriado na suíte ativa sem o import e o teste exclusivos do snapshot v1.

## Atualizações ativas

- o caderno 09 de recuperação de 2010 agora encerra no gate e instrui aguardar
  o snapshot v2;
- seu gerador foi atualizado e está sincronizado;
- READMEs de coleta e processamento apontam o estado arquivado;
- specs de processamento não apresentam mais a suíte v1 como análise ativa;
- o roadmap passou a apontar para o reinício controlado.

## Validação

- 13 notebooks movidos ou regenerados passaram no schema `nbformat`;
- 102 células Python desses notebooks passaram em `ast.parse`;
- o gerador do caderno 09 passou em `--check`;
- nenhuma importação executável de `analise.discursos_plenario` permanece fora
  do arquivo;
- o pytest não coleta os testes arquivados;
- **222 testes ativos passaram**.

Uma verificação mais ampla encontrou uma inconsistência preexistente em
`notebooks/coleta/coleta_senado_plenario.ipynb`: um output salvo contém o campo
`metadata` não aceito pelo schema atual. Esse caderno não foi alterado nem
movido e o achado não compromete o arquivamento; deve ser tratado em tarefa
própria.

## Marcador no Drive

Pasta verificada:
[`analise-plenario-20260717-v1`](https://drive.google.com/drive/folders/1LVULojH62hRTJ4mVhZSVo09KrXCpefS-)

Marcador criado e relido:
[`ENCERRADA_SEM_VALIDACAO_CIENTIFICA.md`](https://drive.google.com/file/d/1JJN7_SFKmwWeutJuyuNz5fhbCr1t_5lJ/view?usp=drivesdk)

- ID: `1JJN7_SFKmwWeutJuyuNz5fhbCr1t_5lJ`;
- parent confirmado: `1LVULojH62hRTJ4mVhZSVo09KrXCpefS-`;
- MIME type: `text/markdown`;
- tamanho no Drive: 639 bytes.

Nenhuma subpasta, saída, manifest, log ou dado da execução foi movido,
apagado ou regravado.

## Próximo gate

O submódulo 01 está encerrado. O próximo trabalho é aprovar D06 no submódulo
02 e, depois, as raízes do Drive para executar o inventário somente leitura do
submódulo 03.
