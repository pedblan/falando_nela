# Gate de arquivamento do Drive

Nenhum item preexistente no Google Drive foi movido pelo conector. A pasta de
destino foi criada, mas o conector não recebeu permissão de escrita sobre os
itens antigos; a operação deverá ser executada pelo Drive montado no Colab.

Raiz protegida:

```text
/content/drive/MyDrive/falando_nela/data
```

Destino:

```text
/content/drive/MyDrive/falando_nela/arquivo/data_pos_coleta_v1_arquivado_20260724
```

## Regra aprovada

- preservar integralmente `data/raw/**`;
- mover todos os demais filhos diretos de `data/`;
- não apagar nenhum item;
- preservar nomes e estrutura interna no destino;
- registrar fingerprint estrutural de `raw/` antes e depois.

## Classificação inicial

| Filho direto observado | Decisão |
|---|---|
| `raw/` | preservar |
| `reference/` | arquivar |
| `locks/` | arquivar |
| `analises/` | arquivar |
| `operations/` | arquivar |
| `Untitled0.ipynb` | arquivar |
| `processed/` | arquivar |
| `manifests/` | arquivar |
| `logs/` | arquivar |
| `checkpoints/` | arquivar |

## Próximo gate

Use `notebooks/manutencao/00_arquivar_pos_coleta_v1_colab.ipynb`. O caderno:

1. monta o Drive;
2. mede `raw/` e gera o plano sem movimentar;
3. exibe os filhos não-raw;
4. exige confirmação literal do `operation_id`;
5. move os nove itens;
6. verifica que apenas `raw/` permaneceu em `data/`;
7. grava o manifest no destino.
