# Gate de arquivamento do Drive

Nenhum item no Google Drive foi movido por este commit.

Raiz protegida:

```text
/content/drive/MyDrive/falando_nela/data
```

## Exclusões obrigatórias

Estes itens não podem entrar em uma operação de arquivamento pós-coleta:

- `raw/**`;
- arquivos de referência indispensáveis para interpretar o raw;
- manifests, logs e checkpoints que sejam a única proveniência de uma coleta;
- código ou configuração necessários para decodificar o payload oficial.

## Classificação inicial

| Família | Decisão inicial |
|---|---|
| `raw/**` | preservar |
| `processed/**` | candidato a arquivamento |
| `analise/**`, `analises/**`, `analysis/**` | candidato a arquivamento |
| caminhos contendo `snapshot` | candidato a arquivamento |
| `operations/**` | revisão manual, pois mistura coleta e derivados |
| `logs/**`, `manifests/**`, `checkpoints/**`, `locks/**` | revisão manual por proveniência |
| `reference/**` | preservar até revisão específica |
| itens não classificados | revisão manual |

## Próximo gate

O arquivo `artifacts/catalogo_dados.csv` produzido pelo inventário
`drive-inventory-20260724t020749z` deve ser fornecido ao script
`scripts/prepare_drive_archive_candidates.py`.

O script é somente leitura em relação ao Drive. Ele gera uma tabela com uma
linha por arquivo e uma destas decisões:

- `preserve`;
- `archive_candidate`;
- `manual_review`.

No mesmo runtime Colab usado no inventário, o comando esperado é:

```bash
python scripts/prepare_drive_archive_candidates.py \
  /content/falando_nela_inventory/drive-inventory-20260724t020749z/artifacts/catalogo_dados.csv \
  /content/falando_nela_drive_archive_plan/drive-archive-plan-20260724/candidatos.csv
```

Se o runtime anterior tiver sido encerrado, o inventário deverá ser refeito em
modo somente leitura ou o `catalogo_dados.csv` deverá ser restaurado antes
deste comando.

Somente depois da revisão e aprovação explícita dessa tabela poderá existir
uma operação de movimentação no Drive. A movimentação deverá ter destino
versionado, manifest antes/depois e rollback documentado.
