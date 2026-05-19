# Cadernos Jupyter: quebras de linha em `source`

Use estas instrucoes sempre que criar, gerar ou corrigir notebooks `.ipynb`,
especialmente os cadernos de coleta em `notebooks/coleta/*.ipynb`.

## Objetivo

Evitar que literais Python como `"\n"` virem quebras reais dentro de strings no
codigo da celula. Esse erro costuma aparecer no Colab/Jupyter como
`SyntaxError: unterminated string literal`.

## Modelo mental

Um notebook `.ipynb` e JSON. Uma celula de codigo nao guarda um arquivo `.py`;
ela guarda `cell.source`, que pode ser uma lista de strings. O Jupyter monta o
codigo final com:

```python
codigo_da_celula = "".join(cell["source"])
```

Por isso ha duas quebras de linha diferentes:

- Quebra de linha da celula: fica no fim de um item de `source`, como `\n`.
- Quebra de linha dentro de literal Python: precisa continuar como os dois
  caracteres `\\n` no JSON do notebook.

## Exemplo principal

Codigo Python desejado dentro da celula:

```python
print("\nArquivo:", path)
```

Representacao correta no JSON do `.ipynb`:

```json
{
  "cell_type": "code",
  "source": [
    "print(\"\\nArquivo:\", path)\n"
  ]
}
```

Representacao incorreta:

```json
{
  "cell_type": "code",
  "source": [
    "print(\"\n",
    "Arquivo:\", path)\n"
  ]
}
```

A forma incorreta concatena para isto, que nao e Python valido:

```python
print("
Arquivo:", path)
```

## Ao gerar notebooks por script

Crie o texto da celula como codigo Python e so depois converta para
`source` com `splitlines(keepends=True)`.

Prefira raw strings para templates de celula que contenham `\n` dentro de
literais Python:

```python
cell_code = r'''print("\nArquivo:", path)
print("\nUltimas linhas do log:")
'''
source = cell_code.splitlines(keepends=True)
```

Ou escape a barra explicitamente:

```python
source = [
    'print("\\nArquivo:", path)\n',
    'print("\\nUltimas linhas do log:")\n',
]
```

Evite templates normais quando houver `"\n"` dentro do codigo da celula:

```python
cell_code = '''print("\nArquivo:", path)
'''
```

Esse ultimo exemplo transforma `\n` em quebra real antes de serializar o
notebook.

## Ao editar `.ipynb` direto

- Nunca quebre um item de `source` no meio de uma string Python delimitada por
  aspas simples ou duplas.
- Se uma linha da celula contem `print("\n...")`, o JSON deve mostrar
  `print(\"\\n...\")`, nao `print(\"\n`.
- Uma linha fisica de codigo normalmente vira um item de `source` terminado em
  `\n`.
- Multi-line string intencional dentro da celula deve usar sintaxe Python valida,
  como triple quotes, e ainda assim o JSON deve preservar a fonte resultante.
- Prefira serializar com `json.dumps`, `nbformat` ou outro escritor de notebook;
  nao monte JSON manualmente com concatenacao de strings.

## Pontos comuns nos cadernos de coleta

Revise com cuidado helpers que imprimem separadores ou logs, pois eles costumam
usar literais com newline:

```python
print("\nArquivo:", path)
print("\nUltimas linhas do log:")
print("\n".join(log_path.read_text(encoding="utf-8").splitlines()[-10:]))
```

No JSON do notebook, esses trechos precisam aparecer com barras escapadas:
`"\\nArquivo:"`, `"\\nUltimas linhas do log:"` e `"\\n".join(...)`.

## Validacao obrigatoria

Depois de alterar notebooks, valide primeiro o JSON:

```bash
python3 -m json.tool notebooks/coleta/coleta_senado_ccj.ipynb >/tmp/notebook.json
```

Depois compile todas as celulas de codigo. Essa checagem pega exatamente o caso
de `\n` convertido em quebra real dentro de literal Python:

```bash
python3 - <<'PY'
import ast
import json
from pathlib import Path

for path in Path("notebooks/coleta").glob("*.ipynb"):
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        try:
            ast.parse(source)
        except SyntaxError as exc:
            raise SystemExit(f"{path}: cell {index}: {exc}")
print("ok")
PY
```

## Checklist rapido

- `cell.source` concatena strings; nao trate como lista arbitraria de linhas.
- Newline de fim de linha do notebook: `\n`.
- Newline dentro de string Python da celula: `\\n` no JSON.
- Templates geradores com `"\n"` devem ser raw strings ou usar barra escapada.
- Rode `json.tool` e `ast.parse` antes de considerar o notebook corrigido.
