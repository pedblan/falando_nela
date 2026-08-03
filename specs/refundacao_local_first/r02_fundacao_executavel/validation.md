# Validação operacional — R02 fundação executável local

## Comandos

```bash
uv sync --locked --all-groups
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run falando-nela doctor --json
```

## Critérios

- [x] Instalação limpa usa Python 3.13 e o lockfile sem resolução implícita.
- [x] Testes não fazem DNS, HTTP, Drive, Cloud ou chamadas parlamentares.
- [x] `doctor --json` não mistura texto humano em stdout.
- [x] Ausência de data root, caminho relativo e raiz dentro do clone falham.
- [x] Raiz externa válida informa limites de 4 GiB, quatro threads, quota de
  2 GiB e reserva de 5 GiB.
- [x] Profile `full` falha sem opt-in explícito.
- [x] gzip determinístico produz o mesmo objeto e recupera conteúdo idêntico.
- [x] `git diff --check` passa e nenhum dado, segredo ou ambiente entra no diff.

## Evidência

Em `2026-08-03`, uma cópia sem `.venv` instalou 104 pacotes locked, executou
Ruff e formatação sem divergência, passou 183 testes e concluiu o diagnóstico
estruturado sem criar a raiz de dados. Depois do merge
`c0563d249c8a0d0af36af9e37e24acba94b5ffef`, um clone limpo do estado
integrado passou nas mesmas verificações e em 189 testes; os seis testes
adicionais pertencem ao fechamento G02 já presente em `main`.

## Bloqueios

- Dependência de Colab ou Drive no diagnóstico local.
- Criação silenciosa de diretório de produção.
- Escrita não atômica de configuração ou manifest.
- Saída gzip variável para a mesma entrada.
- Teste que dependa de rede ou credencial.
