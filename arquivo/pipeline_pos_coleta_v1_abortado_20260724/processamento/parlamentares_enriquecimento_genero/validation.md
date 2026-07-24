# Validação: enriquecimento revisado de gênero parlamentar

- Selecionar apenas valores oficiais desconhecidos.
- Deduplicar por `parlamentar_key`.
- Simular reconsulta oficial antes da pesquisa geral.
- Validar o schema estruturado com resposta identificada e não identificada.
- Rejeitar identificação sem evidência completa.
- Rejeitar valor fora da enumeração.
- Rejeitar publicação sem revisão humana completa.
- Confirmar que `genero_oficial` permanece idêntico ao canônico.
- Confirmar que apenas linhas aprovadas alteram `genero_analitico`.
- Confirmar que a saída e os manifests não contêm a chave da API.
- Inspecionar manualmente URL, desambiguação e trecho de 100% dos candidatos.
