# Skills do Codex

As instrucoes operacionais para criar e corrigir notebooks Colab/Jupyter do
projeto agora vivem como Skill do Codex.

Fonte versionada no repositorio:

```text
codex-skills/falando-nela-colab-notebooks/
```

Instalacao local usada pelo Codex nesta maquina:

```text
~/.codex/skills/falando-nela-colab-notebooks/
```

Se mudar de maquina ou recriar o ambiente, sincronize a fonte versionada para a
pasta local de Skills do Codex:

```bash
mkdir -p ~/.codex/skills
rsync -a codex-skills/falando-nela-colab-notebooks/ \
  ~/.codex/skills/falando-nela-colab-notebooks/
```

Use a Skill `falando-nela-colab-notebooks` sempre que criar, gerar ou corrigir
notebooks `.ipynb` do projeto, especialmente em `notebooks/coleta/` e
`notebooks/processamento/`.
