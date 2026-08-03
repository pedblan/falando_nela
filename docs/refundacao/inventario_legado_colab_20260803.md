# Inventário da última linha Colab — 2026-08-03

## Finalidade

Este inventário identifica as fontes recuperáveis da arquitetura centrada em
Google Colab imediatamente antes da refundação local-first. A tag anotada
`legacy-colab-final` apontará para o commit que contém este documento.

A tag preserva código e documentação; dados de produção, credenciais,
artefatos do Drive e ambientes Python continuam fora do Git.

## Estado validado

- branch de fechamento: `main`;
- remote preservado: `https://github.com/pedblan/falando_nela.git`;
- comando de teste: `PYTHONPATH=. python -m pytest -q`;
- resultado em 2026-08-03: 176 testes aprovados;
- raw alterado pela validação: não;
- APIs parlamentares chamadas pela validação: não;
- Drive ou Google Cloud acessado pela validação: não.

G01 permanece aprovado. O vocabulário conceitual de G02 foi aprovado, e sua
execução técnica foi reconciliada, mas o gate operacional humano de G02
permanece aberto. A tag não promove propostas, não inicia G03, não materializa
normalização e não declara o pipeline v3 concluído.

## Superfície preservada

| Área | Quantidade observada | Papel na migração |
|---|---:|---|
| notebooks oficiais fora de `notebooks/arquivo` | 27 `.ipynb` | referência operacional e de parâmetros; portar somente por necessidade |
| notebooks arquivados | 12 `.ipynb` | caracterização histórica; não reativar automaticamente |
| geradores Colab em `scripts/` | 9 módulos | fonte dos notebooks gerados e de seus contratos repetíveis |
| módulos Python em `coleta/` | 37 arquivos | leitores, coletores e contratos raw reutilizáveis |
| módulos em `pipeline_dados_v3/` | 3 arquivos | inventário e schema v3 ainda auditáveis |
| testes ativos no nível principal de `tests/` | 25 arquivos | caracterização executável da linha legada |
| specs Markdown sob `specs/` | 28 arquivos | autoridade sobre gates, decisões e bloqueios |

## Pontos de entrada que permanecem fontes

- `coleta/common/`: configuração, HTTP, I/O raw, documentos, CLI e retomada;
- `coleta/camara/` e `coleta/senado/`: contratos específicos das fontes;
- `pipeline_dados_v3/inventario_metadados_raw.py`: inventário somente leitura;
- `pipeline_dados_v3/schema_normalizado.py`: ferramenta e evidências de G02;
- `notebooks/dados_v3/`: entrada Colab para G01 e G02;
- `notebooks/coleta/`: operações históricas de coleta e manutenção;
- `scripts/generate_*_colab_notebook.py`: geradores que caracterizam notebooks
  gerados;
- `specs/pipeline_dados_v3/`: sequência, decisões e gates ainda abertos.

## Regras para a refundação

1. Não executar nova coleta histórica para substituir o raw existente.
2. Não converter os 27 notebooks em massa; portar somente o recorte exigido
   pela etapa local-first corrente.
3. Preservar `coleta/common/io.py` como referência do envelope raw, mas não
   herdar caminhos de Drive ou estado de notebook como interface nova.
4. Tratar arquivos em `notebooks/arquivo/` e `arquivo/` como história, não como
   caminhos oficiais.
5. Manter G02 explicitamente aberto até suas validações e decisões humanas
   restantes, mesmo que a linha Colab deixe de ser o ambiente padrão.
6. Usar a tag `legacy-colab-final` para reproduzir ou consultar esta linha sem
   reescrever a história publicada.

## Recuperação

Depois da publicação da tag:

```bash
git fetch origin --tags
git switch --detach legacy-colab-final
PYTHONPATH=. python -m pytest -q
```

O checkout destacado é apenas para inspeção ou reprodução. Correções futuras
do legado deverão partir de branch própria, nunca alterar a tag existente.
