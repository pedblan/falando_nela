# Requisitos gerais do pipeline de dados v3

## Estado

Proposta para revisão humana.

## Objetivo

Produzir uma nova linha de dados derivados, incompatível com as versões
arquivadas, usando exclusivamente os dados brutos preservados como fonte.

## Escopo

- Inventariar todas as coleções existentes sob
  `/content/drive/MyDrive/falando_nela/data/raw`.
- Criar futuros derivados sob contratos `v3`.
- Tratar normalização de metadados e interpretação da estrutura textual como
  problemas separados.
- Adiar recortes científicos de período, arena ou unidade para o contrato do
  snapshot.

## Nomenclatura

- `raw/` não será renomeado nem reversionado.
- Novas tabelas normalizadas usarão `v3`.
- Novos schemas, manifests e snapshots usarão `v3`.
- Nenhum artefato v1 ou da tentativa v2 poderá ser entrada científica da v3.

## Invariantes

### Raw

- O `raw/` é imutável.
- Nenhuma etapa v3 corrige, regrava, move ou exclui registros brutos.
- Toda saída deve preservar a proveniência até o arquivo e o caminho do campo
  original.

### Metadados

- Python pode ler e analisar campos estruturados recebidos na coleta.
- Python só pode preencher uma categoria normalizada quando existir metadado
  de origem não vazio e uma regra aprovada para esse campo ou valor.
- Metadado ausente permanece ausente.
- É proibido usar texto livre como fallback para completar metadados oficiais
  ausentes.
- Toda transformação deverá preservar `valor_original`, regra, versão e
  método.

### Texto

Python pode:

- transportar, armazenar, contar caracteres, gerar hashes e dividir textos
  para envio;
- converter posições entre representações técnicas documentadas;
- validar limites e igualdade literal de trechos retornados;
- aplicar mecanicamente uma transformação já definida.

Python não pode:

- usar regex, listas de expressões ou heurísticas para descobrir marcadores;
- inferir orador, participante, papel, seção ou fronteira discursiva;
- interpretar cabeçalhos, separadores, notas editoriais ou mudanças de turno;
- preencher metadados ausentes a partir do texto.

### GPT-5.6

- A interpretação da estrutura textual caberá ao GPT-5.6.
- A análise ocorrerá por texto, ainda que o processamento técnico use chunks.
- O modelo deverá retornar um plano declarativo de transformação em JSON, não
  código executável.
- O plano deverá conter os marcadores efetivamente observados, incluindo
  trecho literal, posição inicial, posição final, tipo de marcador e ação
  proposta dentro de um vocabulário fechado e aprovado.
- Um único motor Python, versionado e testado, aplicará os planos válidos.
- É proibido solicitar ou executar um programa Python diferente para cada
  texto.
- Se uma família nova de padrões exigir lógica adicional, a mudança será feita
  uma vez no motor comum, com revisão humana e testes antes da execução.
- A unidade de posição e a política de chunking serão aprovadas no submódulo
  correspondente.
- Python deverá rejeitar qualquer marcador cujo trecho não seja idêntico a
  `texto[inicio:fim]`.
- Python deverá rejeitar ações fora do vocabulário aprovado, campos adicionais
  não permitidos e qualquer conteúdo que pareça código executável.
- O modelo poderá responder que não há marcador ou que o caso é indeterminado.
- Nenhum batch amplo será enviado antes de piloto, validação humana e
  estimativa de custo.

Formato conceitual mínimo, ainda sujeito à spec do submódulo:

```json
{
  "texto_id": "identificador",
  "marcadores": [
    {
      "inicio": 0,
      "fim": 12,
      "trecho_literal": "texto exato",
      "tipo": "tipo_aprovado",
      "acao": "acao_aprovada"
    }
  ],
  "estado": "concluido",
  "revisao_necessaria": false
}
```

Esse objeto descreve o que deve ser feito; ele não contém funções, comandos,
expressões regulares ou trechos de programa.

### Controle de custo da interpretação textual

- O piloto registrará tokens de entrada, tokens de entrada em cache, tokens de
  saída, tokens de raciocínio quando informados, custo efetivo, latência e taxa
  de casos válidos.
- A projeção integral será calculada a partir de estratos representativos de
  fonte, dataset, período e comprimento do texto.
- O piloto comparará os tiers GPT-5.6 autorizados que atendam ao schema, sem
  presumir que o modelo mais caro seja necessário para todos os casos.
- Prompts estáveis e respostas compactas serão preferidos, desde que não
  reduzam a validade ou a auditabilidade.
- Batch e cache só poderão ser adotados depois de validação funcional e
  registro de sua política efetiva de preço.
- O orçamento máximo e a regra de interrupção serão aprovados em G04.

## Categorias normalizadas

As categorias não serão definidas antecipadamente. Elas serão propostas apenas
depois do inventário completo dos metadados observados.

Cada futuro valor normalizado deverá permitir registrar:

- valor original;
- valor normalizado;
- campo de origem;
- método (`python_regra_aprovada`, `gpt_5_6` ou `revisao_humana`);
- versão da regra ou prompt;
- estado de validação;
- necessidade de revisão.

## Não objetivos

- Corrigir a coleta raw.
- Reutilizar automaticamente schemas v1.
- Criar snapshot antes da normalização v3.
- Usar GPT para tarefas puramente estruturais ou determinísticas.
- Usar Python como interpretador semântico de texto.
- Gerar ou executar código específico para cada discurso.
