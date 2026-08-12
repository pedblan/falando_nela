# Requisitos — R09 limpeza de versões antigas no Drive

## Objetivo

Preservar todos os notebooks legados numa área única de consulta e enviar à
Lixeira do Google Drive as dez raízes antigas autorizadas, mantendo somente a
árvore canônica criada pelo R03.

## Destino preservado

- **R09-DRIVE-01:** a raiz canônica preservada é `falando_nela`, ID
  `17gLzQZSTmM59KTDhErPXEUi8QsBiMBWq`.
- **R09-DRIVE-02:** o raw canônico preservado contém 2.887 objetos e
  14.686.043.352 bytes.
- **R09-DRIVE-03:** os notebooks serão copiados para
  `falando_nela/notebooks/consulta_legacy/`, com prefixo distinto por raiz de
  origem para impedir colisões.
- **R09-DRIVE-04:** a preservação deverá cobrir 106 notebooks ou arquivos Colab,
  incluindo os três objetos `Untitled` sem extensão encontrados em
  `falando_nela_arquivo`.
- **R09-DRIVE-05:** cada objeto preservado será validado por caminho, tamanho e
  SHA-256 calculado por download; payload de células não entrará no manifest.

## Raízes autorizadas para limpeza

| Nome inventariado | ID | Objetos | Bytes |
|---|---|---:|---:|
| `falando_nela_refundacao` | `1zt4au5VQxXj3W1QHCzMD_eg2M2De66nH` | 0 | 0 |
| `falando_nela_arquivo` | `15QW3SAIFIw_bzRhlI7m2sVMTL9UKjnzB` | 5.091 | 37.302.838.317 |
| `falando_nela` antiga de 2026-02 | `1w5anCDGua55QB7S36uZ_kd00qJMo_R8j` | 6.464 | 14.557.819.649 |
| `falando_nela_OLD` | `1meI-qwF6qceOCEUYBGpsrwZ19xsPolYB` | 12.186 | 9.651.843.896 |
| `falando_nela` antiga de 2025-12 | `1FboMunlM30H86v6PUn8oT95sQrAFR1Z7` | 9.525 | 678.781.280 |
| `falando_nela_OLD_10_2025` | `18uh1KYC8xRLyjeWEga7Xh7PtzaPAeatT` | 335 | 14.376.504.931 |
| `falando_nela_old` | `1qR2aESzgw2j64Jrrq2Q7MNCImuUTmJsk` | 54 | 199.138.059, mais um objeto sem tamanho |
| `falando_nela_5_2025` | `1Tu2I_JqdTajOf3QKXKoAFdj_lLHQwIf5` | 46 | 35.334.609 |
| `falando_nela_1` | `1g83E1q0DHVfBgOAOy0AmbxcsbMIEKjDX` | 8 | 13.537.006 |
| `falando_nela_2` | `15us6huqjACQ8mBgcUN8Re22Nj2xh5IYz` | 6 | 253.028 |

- **R09-DRIVE-06:** a autorização humana para todos os dez IDs, inclusive
  `falando_nela_arquivo`, foi confirmada em `2026-08-03`.
- **R09-DRIVE-07:** a soma simples das dez linhas é 33.715 objetos e ao menos
  76.816.050.775 bytes, mas inclui duas vezes a raiz de 2025-12, que está
  contida em `falando_nela_OLD`. O universo físico único é de 24.190 objetos e
  ao menos 76.137.269.495 bytes; a operação não inferirá alvos adicionais por
  nome.
- **R09-DRIVE-08:** cada raiz será enviada à Lixeira, não apagada
  permanentemente, e a operação interromperá se a interface disponível não
  oferecer essa semântica.

## Segurança e auditoria

- **R09-DRIVE-09:** nenhuma exclusão começará antes de a cópia dos notebooks ser
  reconciliada integralmente.
- **R09-DRIVE-10:** manifests ficarão sob `data_samples/operations/` e
  temporários sob `data_samples/tmp/`; nenhum segredo ou payload parlamentar
  será registrado.
- **R09-DRIVE-11:** a árvore canônica será relistada depois da limpeza e deverá
  manter raw, contagem, bytes e hashes do R03.
- **R09-DRIVE-12:** falha parcial será registrada por ID, sem ampliar ou repetir
  automaticamente a remoção de uma raiz já confirmada na Lixeira.

## Fora do escopo

- Esvaziar a Lixeira do Google Drive.
- Apagar a raiz canônica ou a nova biblioteca de notebooks.
- Remover branches, tags ou notebooks do Git.

## Resultado em 2026-08-03

Os 106 notebooks foram reconciliados em `consulta_legacy`; nove raízes foram
movidas diretamente para a Lixeira e a raiz antiga de 2025-12 acompanhou sua
ancestral `falando_nela_OLD`. A Lixeira não foi esvaziada. A raiz canônica e o
raw R03 permaneceram fora da Lixeira e íntegros.
