# Requisitos — R09 limpeza local do legado

## Objetivo

Aposentar cópias locais antigas depois da conclusão do R03, mantendo um único
checkout canônico e preservando os notebooks históricos apenas para consulta.

## Autorização e escopo

- **R09-LOCAL-01:** a autorização humana foi confirmada em `2026-08-03` para
  retirar os dados legados locais e a worktree temporária.
- **R09-LOCAL-02:** os alvos de dados são exatamente
  `/Users/pedblan/PycharmProjects/falando_nela/data/dev` e
  `/Users/pedblan/PycharmProjects/falando_nela/data/samples/textos_parlamentares`.
- **R09-LOCAL-03:** os alvos serão movidos para uma pasta exclusiva sob
  `/Users/pedblan/.Trash/`; não haverá exclusão permanente nesta operação.
- **R09-LOCAL-04:** o catálogo anterior à remoção registrará caminho, tamanho e
  SHA-256 sob `data_samples/operations/`, sem registrar payload parlamentar.

## Preservação

- **R09-LOCAL-05:** `data_samples/`, seus manifests e a amostra publicada pelo
  R03 permanecerão intactos.
- **R09-LOCAL-06:** os arquivos `.gitkeep` e schemas rastreados sob `data/`
  permanecerão no checkout.
- **R09-LOCAL-07:** todos os notebooks rastreados permanecerão no Git, serão
  classificados como consulta legada e não serão entrypoints operacionais.
- **R09-LOCAL-08:** a tag `legacy-colab-final`, branches e histórico Git não
  serão removidos nem reescritos.
- **R09-LOCAL-09:** a alteração preexistente em `.idea/falando_nela.iml` será
  preservada.

## Consolidação do checkout

- **R09-LOCAL-10:** o checkout canônico `falando_nela` avançará por
  fast-forward até o commit validado da limpeza.
- **R09-LOCAL-11:** a worktree `falando_nela_refundacao` só será retirada por
  `git worktree remove`, depois de estar limpa e sem commits exclusivos em
  relação ao checkout canônico.
- **R09-LOCAL-12:** ambientes e caches da worktree temporária são reconstruíveis
  e podem ser removidos junto com ela.

## Fora do escopo

- Remover notebooks, tags, branches ou histórico Git.
- Alterar a amostra R03 ou materializar o corpus integral no Mac.
- Iniciar R04, Marimo ou Google Cloud Batch.
