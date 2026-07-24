# Pipeline pós-coleta v1 — encerrado em 2026-07-24

## Estado

**Encerrado sem promoção científica.**

Este diretório é um arquivo histórico. Nenhum módulo, caderno, schema,
manifest ou resultado aqui contido constitui entrada aprovada para a próxima
normalização ou para uma nova análise.

## Motivo do encerramento

O smoke do snapshot v2 mostrou que a camada processada não distinguia com
segurança:

- parlamentar associado ao registro;
- orador efetivo;
- documento ou cabeçalho editorial;
- intervenção individual e documento multiorador.

Também foi identificado que uma recuperação oficial de orador no corpus do
Congresso era mantida em metadados auxiliares, mas não propagada para o campo
processado usado no snapshot. Corrigir somente o snapshot esconderia um
problema anterior, na normalização.

## Conteúdo preservado

- `processamento/`: implementação completa da normalização e dos derivados v1;
- `notebooks/processamento/`: cadernos operacionais pós-coleta;
- `notebooks/dados/`: inventário, censo e smoke do snapshot v2;
- `relatorios_operacionais/`: formato experimental de relatórios e manifests;
- `specs/`: contratos do ciclo de atualização e do primeiro reinício;
- `scripts/`: geradores específicos dos cadernos arquivados;
- `tests/`: testes correspondentes;
- `data/schemas/`: contrato da camada processada v1.

As specs arquivadas estão congeladas. Não devem ser atualizadas para refletir
decisões futuras.

## Conteúdo que permaneceu ativo

- dados brutos no Drive;
- módulos em `coleta/`;
- cadernos de coleta e recuperação raw em `notebooks/coleta/`;
- specs próprias das fontes e coletores;
- metadados de proveniência necessários para interpretar a coleta.

Alguns cadernos históricos de coleta continham, no final, células que chamavam
o processamento v1. Essas células não estão mais aprovadas e não devem ser
executadas. Os trechos de coleta continuam preservados.

## Execuções diagnósticas preservadas

| Operação | Resultado técnico | Uso futuro |
|---|---|---|
| `drive-inventory-20260724t020749z` | concluída | diagnóstico do layout do Drive |
| `snapshot-census-20260724t024812z` | concluída | contagens das três bases processadas |
| `snapshot-v2-smoke-20260724t031154z` | concluída | evidência dos problemas de normalização |

O sucesso técnico dessas operações não equivale a aprovação científica.

## Próxima linha de trabalho

A próxima etapa começará novamente nos dados brutos:

```text
raw preservado
  → contrato novo de normalização
  → piloto pequeno e auditável
  → validação humana
  → normalização integral autorizada
  → snapshot novo
  → análise
```

Não existe, após este arquivamento, uma normalização canônica ativa no
repositório.
