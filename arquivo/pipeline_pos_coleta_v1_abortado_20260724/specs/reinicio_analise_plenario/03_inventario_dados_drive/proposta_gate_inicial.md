# Proposta do gate inicial — inventário do Drive

Status: **aprovada pelo pesquisador em 2026-07-23**.

Este gate autorizou somente a construção e o teste local do notebook de
inventário. A leitura do Drive continua dependendo de uma célula explícita e
separada no Colab.

## Raiz aprovada

```text
/content/drive/MyDrive/falando_nela/data
```

Justificativa: este é o `FALANDO_NELA_DATA_ROOT` declarado pelos coletores,
processadores e notebooks atuais. A primeira versão do inventário não poderá
subir para `falando_nela/`, examinar todo `MyDrive` nem seguir caminhos fora
dessa raiz.

## Taxonomia inicial aprovada

As dimensões são independentes. Um mesmo item recebe um valor em cada uma
delas.

### Classe do item

- `directory`;
- `dataset`;
- `snapshot`;
- `execution`;
- `report`;
- `manifest`;
- `log`;
- `review`;
- `artifact`;
- `unknown`.

### Camada

- `raw`;
- `processed`;
- `snapshot`;
- `analysis`;
- `operational`;
- `unknown`.

### Fonte

- `camara`;
- `senado`;
- `congresso`;
- `derived`;
- `multiple`;
- `unknown`.

### Origem da classificação

- `declared`: declarada no próprio artefato;
- `manifest_reference`: obtida de referência em manifest;
- `path`: extraída de caminho ou nome convencional;
- `inferred`: inferência que exige revisão.

Toda classificação também registra `confidence` como `high`, `medium` ou
`low` e um motivo textual curto. `unknown` é um resultado válido; o notebook
não inventará uma categoria.

## Política de leitura aprovada

### Passagem 1 — metadados

Listar recursivamente, dentro da raiz aprovada:

- ID ou caminho observável;
- nome;
- MIME type ou extensão;
- tamanho;
- data de modificação;
- diretório pai.

Não abrir o conteúdo dos arquivos nessa passagem.

### Passagem 2 — artefatos estruturados selecionados

Abrir somente candidatos a manifest, relatório, configuração ou catálogo
necessários para reconstruir relações:

- JSON, Markdown e CSV de até 5 MiB;
- arquivos maiores somente após serem listados como pendência;
- Parquet, JSONL volumoso, mídia, ZIP e dados brutos permanecem fechados;
- hashes existentes são reutilizados; nenhum hash integral em massa.

## Saída do primeiro piloto

Para manter o Drive somente leitura, o piloto grava apenas no armazenamento
temporário do Colab:

```text
/content/falando_nela_inventory/<operation_id>/
```

Esse diretório conterá o padrão D06:

```text
relatorio.md
manifest.json
logs/execution.jsonl
artifacts/
```

Nenhum resultado será copiado ao Drive sem um gate posterior.

## O que esta aprovação não autoriza

- executar a varredura real do Drive;
- escrever, mover, renomear ou apagar itens no Drive;
- calcular hashes em massa;
- declarar uma base canônica;
- criar o snapshot v2;
- executar qualquer chamada à OpenAI.

## Decisão registrada

O pesquisador aprovou:

1. a única raiz `/content/drive/MyDrive/falando_nela/data`;
2. as quatro dimensões da taxonomia;
3. o limite de 5 MiB para leitura de artefatos estruturados;
4. a saída temporária local do Colab.

A aprovação não foi interpretada como autorização para executar a varredura
real.
