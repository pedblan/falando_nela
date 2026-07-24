# Plano: enriquecimento revisado de gênero parlamentar

## Objetivo

Criar uma camada derivada e auditável para casos em que
`parlamentares/v1` registra gênero oficial desconhecido. A camada canônica
permanece intacta e continua representando apenas informação oficial.

## Fluxo

1. Selecionar `parlamentar_key` com `genero=nao_informado` ou vazio.
2. Reconsultar endpoints e páginas oficiais identificados pela fonte.
3. Separar casos ainda desconhecidos.
4. Pesquisar informação pública textual com `gpt-5.6-sol` e ferramenta de busca web.
5. Permitir `nao_identificado` quando a evidência for insuficiente.
6. Exportar candidato, fontes, trecho, prompt, modelo e data.
7. Revisar humanamente todos os candidatos.
8. Publicar apenas linhas aprovadas; preservar rejeitadas na auditoria.

É proibido concluir gênero apenas por nome, fotografia, aparência ou forma de
tratamento. A evidência precisa ser textual, pública, citável e claramente
referente à pessoa desambiguada.

## Saídas

Em `analises/discursos_plenario/v1/{run_id}/01_genero/`:

- `parlamentares_genero_desconhecido.csv`;
- `revisao_genero.csv`;
- `genero_enriquecido_aprovado.parquet`, somente após revisão;
- manifests de preparação, pesquisa e publicação;
- respostas brutas ou IDs recuperáveis, sem credenciais.

`genero_presumido=true` significa “valor derivado de pesquisa pública e
aprovado por humano”. O termo não implica incerteza do gênero da pessoa; indica
apenas que o valor não veio do campo oficial canônico.
