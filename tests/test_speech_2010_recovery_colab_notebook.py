from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "coleta" / "09_recuperacao_discursos_plenario_2010_colab.ipynb"
GENERATOR = ROOT / "scripts" / "generate_speech_2010_recovery_colab_notebook.py"


def test_2010_recovery_notebook_is_generated_and_uses_official_ids() -> None:
    namespace: dict[str, object] = {"__file__": str(GENERATOR), "__name__": "not_main"}
    exec(compile(GENERATOR.read_text(encoding="utf-8"), str(GENERATOR), "exec"), namespace)
    assert NOTEBOOK.read_text(encoding="utf-8") == namespace["render"]()

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "backfill-discursos-plenario-2010-20260715" in source
    assert "coleta.camara.plenario_discursos.collect" in source
    assert "--parlamentares-periodos-path" in source
    assert "GET /deputados oficial por período" in source
    assert "CodigoPronunciamento" in source
    assert "deputado:(\\d+):discursos" in source
    assert "congresso_2010_text_inventory.json" in source
    assert "congresso_2010_text_missing_population.jsonl" in source
    assert "coleta.senado.recuperar_textos_diario" in source
    assert "RODAR_RECUPERACAO_CONGRESSO = False" in source
    assert "RODAR_CAMARA_2010 = False" in source
    assert "VALIDAR_RECUPERACAO = False" in source
