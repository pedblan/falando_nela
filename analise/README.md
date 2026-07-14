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
