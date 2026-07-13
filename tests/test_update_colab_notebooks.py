from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = [
    ROOT / "notebooks" / "coleta" / "00_auditoria_configuracao_atualizacao_colab.ipynb",
    ROOT / "notebooks" / "coleta" / "01_atualizacao_parlamentares_colab.ipynb",
    ROOT / "notebooks" / "coleta" / "02_atualizacao_senado_colab.ipynb",
    ROOT / "notebooks" / "coleta" / "03_backfill_congresso_textos_colab.ipynb",
    ROOT / "notebooks" / "coleta" / "04_atualizacao_camara_demais_bases_colab.ipynb",
    ROOT / "notebooks" / "coleta" / "05_atualizacao_camara_plenario_colab.ipynb",
    ROOT / "notebooks" / "processamento" / "06_processamento_validacao_atualizacao_colab.ipynb",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_cells(notebook: dict) -> list[str]:
    return ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]


def test_update_notebooks_are_valid_json_and_all_code_cells_compile() -> None:
    assert len(NOTEBOOKS) == 7
    for path in NOTEBOOKS:
        notebook = _load(path)
        assert notebook["nbformat"] == 4
        code_cells = _code_cells(notebook)
        assert code_cells
        assert "drive.mount" in code_cells[0]
        for index, source in enumerate(code_cells, start=1):
            ast.parse(source, filename=f"{path.name}::code-{index}")


def test_production_cells_are_protected_and_use_fixed_cycle_contract() -> None:
    combined = "\n".join(source for path in NOTEBOOKS for source in _code_cells(_load(path)))
    assert 'EXPECTED_CYCLE_ID = "20260713"' in combined
    assert '2026-05-01' in combined
    assert '2026-07-13' in combined
    assert 'check=False' in combined
    assert '--resume' in combined
    assert '--no-sample' in combined
    assert 'dataset_lock' in combined

    for path in NOTEBOOKS[1:]:
        source = "\n".join(_code_cells(_load(path)))
        assert "RODAR_" in source
        assert " = False" in source


def test_control_and_final_notebooks_cover_expected_outputs() -> None:
    control = NOTEBOOKS[0].read_text(encoding="utf-8")
    final = NOTEBOOKS[-1].read_text(encoding="utf-8")
    for run_id in [
        "prod-historico-senado-ccj",
        "prod-historico-camara-ccjc",
        "prod-historico-camara-plenario",
        "prod-historico-senado-congresso-textos-v1",
        "processed-textos-v1-current",
    ]:
        assert run_id in control

    for parquet_name in [
        "senado__plenario_discursos.parquet",
        "senado__congresso_discursos.parquet",
        "senado__ccj_notas.parquet",
        "senado__pareceres_pec.parquet",
        "camara__plenario_discursos.parquet",
        "camara__ccjc_eventos.parquet",
        "camara__pareceres_pec.parquet",
    ]:
        assert parquet_name in control
    assert "build_gradio_app" in final
    assert "JSONL_GATE_OK" in final
    assert "texto_id" in final


def test_camara_plenario_recovery_uses_safe_boundary_and_local_mandate_cache() -> None:
    source = "\n".join(_code_cells(_load(NOTEBOOKS[5])))

    assert '"--skip-existing-record-scan"' in source
    assert '"--parlamentares-periodos-path"' in source
    assert "cache_parlamentares_periodos" in source
    assert 'Path("/content/falando_nela_runtime")' in source
    assert "shutil.copyfile" in source


def test_senado_notebook_defers_only_the_exact_historical_ccj_gap() -> None:
    senate = "\n".join(_code_cells(_load(NOTEBOOKS[2])))
    final = "\n".join(_code_cells(_load(NOTEBOOKS[6])))

    assert "REGISTRAR_ADIAMENTO_CCJ_HISTORICA = False" in senate
    assert "DEFERRED_COLLECTION_POLICIES" in senate
    assert '"allowed_unresolved_partitions": ["2015-05"]' in senate
    assert 'unresolved == policy["allowed_unresolved_partitions"]' in senate
    assert '"analysis_excluded": True' in senate
    assert "deferred_collections.json" in senate
    assert "ADIADO, sem nova coleta" in senate
    assert "collection_acceptance(run)" in senate

    assert "STRICT_COLLECTION_GATE_OK" in final
    assert "DEFERRED_GATE_KEYS" in final
    assert '"deferred_collections": read_json(DEFERRED_COLLECTIONS_PATH)' in final


def test_shared_gate_accepts_only_the_exact_deferred_partition(tmp_path: Path) -> None:
    helpers = _code_cells(_load(NOTEBOOKS[2]))[3]
    namespace = {
        "Path": Path,
        "json": json,
        "DATA_ROOT": tmp_path,
        "EXPECTED_CYCLE_ID": "20260713",
        "CONFIG": {"cycle_id": "20260713"},
    }
    exec(helpers, namespace)
    run = {
        "key": "senado_ccj_historico",
        "source": "senado",
        "dataset": "ccj_notas",
        "run_id": "prod-historico-senado-ccj",
        "data_inicio": "1900-01-01",
        "data_fim": "2026-05-28",
    }
    manifest_path = tmp_path / "manifests" / "prod-historico-senado-ccj.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": run["run_id"],
                "status": "completed_with_errors",
                "mode": "prod",
                "sample": False,
                "data_inicio": run["data_inicio"],
                "data_fim": run["data_fim"],
            }
        ),
        encoding="utf-8",
    )
    checkpoint_path = tmp_path / "checkpoints" / "senado" / "ccj_notas.json"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint = {
        "runs": {
            run["run_id"]: {
                "completed_partitions": {"2013-10": {}},
                "failed_partitions": {"2013-10": {}, "2015-05": {}},
            }
        }
    }
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    deferred_path = namespace["DEFERRED_COLLECTIONS_PATH"]
    deferred_path.parent.mkdir(parents=True)
    deferred_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cycle_id": "20260713",
                "items": [
                    {
                        "key": run["key"],
                        "run_id": run["run_id"],
                        "allowed_statuses": ["completed_with_errors"],
                        "allowed_unresolved_partitions": ["2015-05"],
                        "analysis_excluded": True,
                        "analysis_exclusion": "senado/ccj_notas",
                        "reason": "Artigo exclui a CCJ.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    acceptance = namespace["collection_acceptance"](run)
    assert acceptance["deferred"] is True
    assert acceptance["unresolved"] == ["2015-05"]

    checkpoint["runs"][run["run_id"]]["failed_partitions"]["2016-01"] = {}
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(AssertionError, match="actual_unresolved"):
        namespace["collection_acceptance"](run)
