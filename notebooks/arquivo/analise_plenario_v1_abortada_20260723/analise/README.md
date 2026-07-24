# Análises

`analise/discursos_plenario` contém a lógica reutilizável da suíte comparativa
de discursos. As especificações metodológicas ficam em
`analise/discursos_plenario_comparativo/`; os notebooks em
`notebooks/analise/` apenas configuram e chamam esses módulos.

Para ver as etapas disponíveis:

```bash
python -m analise.discursos_plenario --help
```

Resultados completos devem ser gerados no Drive/Colab, sob um `data_root`
externo ao repositório. Testes locais usam dados sintéticos ou amostras.

## Apartes: episódios de interação v2

A segunda metade do caderno 03 usa
`analise.discursos_plenario.apartes_episodios`. Python cria turnos e subturnos
determinísticos com IDs e offsets; uma única requisição por `texto_id` reúne
todos os candidatos e pede à IA somente associações de IDs. Textos de
participantes, backchannels, respostas e contexto são reconstruídos do
snapshot local.

Os resultados v2 são paralelos e normalizados em participantes, turnos,
episódios e vínculos episódio–turno. Os arquivos
`interacoes_segmentadas_ia.parquet`, `revisao_segmentacao_ia.csv` e os Batches
anteriores são diagnósticos v1 somente leitura. Atos de fala v2 permanecem
bloqueados até a aprovação de aproximadamente 30 episódios nas quatro
dimensões da nova revisão humana. Veja
[`CONTRATOS_EPISODIOS_V2.md`](discursos_plenario/CONTRATOS_EPISODIOS_V2.md).
