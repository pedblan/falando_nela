# Requisitos: enriquecimento revisado de gênero parlamentar

## Contrato derivado

Campos mínimos:

- `parlamentar_key`;
- `genero_oficial`;
- `genero_enriquecido`;
- `genero_analitico`;
- `genero_origem`;
- `genero_presumido`;
- `evidencia_url`;
- `evidencia_titulo`;
- `evidencia_trecho`;
- `fontes_consultadas`;
- `consultado_em`;
- `modelo`;
- `prompt_version`;
- `revisao_status`;
- `revisor`;
- `revisado_em`;
- `observacao_revisao`.

## Invariantes

- `parlamentares/v1` nunca é regravado por essa etapa.
- `genero_oficial` é cópia fiel do valor canônico.
- Valores pesquisados permitidos: `feminino`, `masculino`, `nao_identificado`.
- Candidato identificado exige URL, título e trecho textual.
- Publicação exige `revisao_status=aprovado`, revisor e data de revisão.
- Candidato aprovado e identificado recebe
  `genero_origem=pesquisa_publica_revisada` e `genero_presumido=true`.
- Candidato pendente, rejeitado ou não identificado não substitui o dado analítico.
- Nome, foto, aparência e tratamento são evidências inválidas quando isolados.

## API

- O modelo padrão é `gpt-5.6-sol`.
- Pesquisa usa web search e Structured Outputs.
- A chave vem exclusivamente de `OPENAI_API_KEY` no ambiente.
- Prompt e schema são versionados.
- Importar o módulo, gerar a fila ou rodar testes não chama a API.
- Erros e recusas permanecem auditáveis e podem ser retomados.
