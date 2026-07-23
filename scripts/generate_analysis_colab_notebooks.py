from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from textwrap import dedent

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "notebooks" / "analise"
REPO_URL = "https://github.com/pedblan/falando_nela.git"
SNAPSHOT_VALIDATION_CELL_PATH = OUTPUT_DIR / "celulas" / "00_validacao_snapshot.py"
SNAPSHOT_VALIDATION_CELL = SNAPSHOT_VALIDATION_CELL_PATH.read_text(encoding="utf-8")


def md(source: str, key: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_markdown_cell(dedent(source).strip())
    cell.metadata["falando_nela"] = {"markdown_id": key, "language": "pt-BR"}
    return cell


def code(source: str, role: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_code_cell(dedent(source).strip())
    cell.metadata["falando_nela"] = {"role": role}
    return cell


DRIVE_CELL = code(
    """
    from google.colab import drive

    drive.mount("/content/drive")
    """,
    "mount_drive",
)


SETUP_CELL = code(
    f"""
    import os
    import subprocess
    import sys
    from pathlib import Path

    DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
    REPO_DIR = Path("/content/falando_nela")
    REPO_URL = "{REPO_URL}"
    REPO_REF = ""  # Opcional: branch, tag ou commit; vazio acompanha o default remoto.

    if not REPO_DIR.exists():
        subprocess.run(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
    else:
        subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "--all", "--tags", "--prune"], check=True)
        if not REPO_REF:
            subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], check=True)
    if REPO_REF:
        subprocess.run(["git", "-C", str(REPO_DIR), "checkout", REPO_REF], check=True)

    os.chdir(REPO_DIR)
    os.environ["FALANDO_NELA_DATA_ROOT"] = str(DATA_ROOT)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            "--no-cache-dir",
            "numpy==2.0.2",
            "pandas==2.2.3",
        ],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-analise.txt"], check=True)
    ABI_CHECK = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import numpy as np; import pandas as pd; "
                "assert np.__version__ == '2.0.2', np.__version__; "
                "assert pd.__version__ == '2.2.3', pd.__version__; "
                "print(f'NumPy {{np.__version__}}; pandas {{pd.__version__}}')"
            ),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    import numpy as np
    import pandas as pd

    assert np.__version__ == "2.0.2", f"Reinicie a sessao do Colab: NumPy carregado={{np.__version__}}"
    assert pd.__version__ == "2.2.3", f"Reinicie a sessao do Colab: pandas carregado={{pd.__version__}}"
    print("Data root:", DATA_ROOT)
    print("Commit:", subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip())
    print("ABI:", ABI_CHECK.stdout.strip())
    """,
    "setup_repository",
)


CONTROL_CELL = code(
    """
    from analise.discursos_plenario.config import load_config, resolve_input_paths, resolve_output_root

    RUN_ID = "analise-plenario-20260717-v1"
    CONFIG_PATH = REPO_DIR / "analise" / "discursos_plenario" / "config.v1.json"
    ANALYSIS_CONFIG = load_config(CONFIG_PATH)
    RUN_OUTPUT_ROOT = resolve_output_root(ANALYSIS_CONFIG, DATA_ROOT, RUN_ID)
    INPUT_PATHS = resolve_input_paths(ANALYSIS_CONFIG, DATA_ROOT)
    RODAR_ETAPA = False

    assert ANALYSIS_CONFIG.date_start == "2010-02-02"
    assert ANALYSIS_CONFIG.date_end == "2026-07-13"
    assert ANALYSIS_CONFIG.raw["complete_year_end"] == 2025
    assert ANALYSIS_CONFIG.raw["ytd_year"] == 2026
    print("Run:", RUN_ID)
    print("Saida:", RUN_OUTPUT_ROOT)
    """,
    "configure_run",
)


NOTEBOOKS = [
    {
        "filename": "00_snapshot_discursos_plenario_colab.ipynb",
        "title": "00 — Snapshot dos discursos em plenário",
        "description": "Filtra as três arenas, preserva os textos, audita duplicações e realiza a junção temporal.",
        "method": "Revise primeiro o inventário de entradas. A etapa é imutável por `RUN_ID`: se dados ou configuração mudarem, crie outro run.",
        "preflight": """
            import pandas as pd
            from analise.discursos_plenario.io import input_inventory

            SNAPSHOT_INVENTORY = input_inventory(ANALYSIS_CONFIG, DATA_ROOT)
            display(SNAPSHOT_INVENTORY)
            SNAPSHOT_REQUIRED = ["camara", "senado", "congresso", "parliamentarian_periods"]
            SNAPSHOT_MISSING = SNAPSHOT_INVENTORY.loc[
                SNAPSHOT_INVENTORY["entrada"].isin(SNAPSHOT_REQUIRED) & ~SNAPSHOT_INVENTORY["existe"], "caminho"
            ].tolist()
            assert not SNAPSHOT_MISSING, f"Entradas obrigatorias ausentes: {SNAPSHOT_MISSING}"
        """,
        "run": """
            from analise.discursos_plenario.snapshot import run_snapshot

            SNAPSHOT_RESULT = None
            if RODAR_ETAPA:
                SNAPSHOT_RESULT = run_snapshot(
                    data_root=DATA_ROOT,
                    run_id=RUN_ID,
                    config_path=CONFIG_PATH,
                    overwrite=False,
                )
                print(SNAPSHOT_RESULT["manifest_path"])
            else:
                print("Etapa não executada. Revise o inventário e defina RODAR_ETAPA=True.")
        """,
        "validate": SNAPSHOT_VALIDATION_CELL,
    },
    {
        "filename": "01_enriquecimento_genero_colab.ipynb",
        "title": "01 — Gênero oficial; pesquisa de deputados suspensa",
        "description": "Audita a cobertura do metadado oficial sem pesquisar, inferir ou publicar gênero para deputados.",
        "method": "Nesta rodada, gênero vem somente do metadado oficial já congelado no snapshot. Casos sem informação permanecem `nao_informado`; nome, inclusive casos aparentemente óbvios, não é usado como inferência.",
        "preflight": """
            import pandas as pd

            GENERO_SNAPSHOT_PATH = (
                RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            )
            assert GENERO_SNAPSHOT_PATH.exists(), "Execute e valide o caderno 00."
            GENERO_RESEARCH_POLICY = "suspended_for_camara_official_only"
            GENERO_SNAPSHOT = pd.read_parquet(
                GENERO_SNAPSHOT_PATH,
                columns=["arena", "genero_oficial", "genero_analitico"],
            )
            GENERO_SNAPSHOT["genero_oficial"] = (
                GENERO_SNAPSHOT["genero_oficial"].fillna("nao_informado")
            )
            GENERO_COVERAGE = (
                GENERO_SNAPSHOT.groupby(
                    ["arena", "genero_oficial"], dropna=False, observed=True
                )
                .size()
                .rename("discursos")
                .reset_index()
            )
            display(GENERO_COVERAGE)
            print("Política:", GENERO_RESEARCH_POLICY)
        """,
        "run": """
            assert not RODAR_ETAPA, (
                "A etapa de pesquisa de gênero está suspensa nesta rodada. "
                "Mantenha RODAR_ETAPA=False."
            )
            print(
                "Nenhuma pesquisa ou publicação foi executada. "
                "Prossiga diretamente para o caderno 02."
            )
        """,
        "validate": """
            GENERO_STAGE_PATH = RUN_OUTPUT_ROOT / "01_genero"
            GENERO_EXISTING_ARTIFACTS = (
                sorted(str(path.name) for path in GENERO_STAGE_PATH.iterdir())
                if GENERO_STAGE_PATH.exists()
                else []
            )
            GENERO_SUSPENSION_STATUS = {
                "status": "suspensa",
                "camara_policy": "official_only_no_research",
                "senado_policy": "official_metadata",
                "existing_artifacts_preserved": GENERO_EXISTING_ARTIFACTS,
                "existing_artifacts_consumed_downstream": False,
                "next_notebook": "02_descritivas_discursos_plenario_colab.ipynb",
            }
            display(GENERO_SUSPENSION_STATUS)
        """,
    },
    {
        "filename": "02_descritivas_discursos_plenario_colab.ipynb",
        "title": "02 — Estatística descritiva",
        "description": "Produz painéis exatos anuais, mensais e por dimensões substantivas.",
        "method": "Bootstrap não é automático: use-o apenas para uma pergunta que declare explicitamente sua população de generalização.",
        "preflight": """
            DESCRITIVAS_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert DESCRITIVAS_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
        """,
        "run": """
            from analise.discursos_plenario.descritivas import run_descriptives

            DESCRITIVAS_RESULT = None
            if RODAR_ETAPA:
                DESCRITIVAS_RESULT = run_descriptives(data_root=DATA_ROOT, run_id=RUN_ID, config_path=CONFIG_PATH)
                print(DESCRITIVAS_RESULT["manifest_path"])
            else:
                print("Descritivas não executadas.")
        """,
        "validate": """
            import pandas as pd

            DESCRITIVAS_ANUAL_PATH = RUN_OUTPUT_ROOT / "02_descritivas" / "anual.csv"
            if DESCRITIVAS_ANUAL_PATH.exists():
                DESCRITIVAS_ANUAL = pd.read_csv(DESCRITIVAS_ANUAL_PATH)
                assert DESCRITIVAS_ANUAL["discursos"].ge(0).all()
                display(DESCRITIVAS_ANUAL.tail(12))
        """,
    },
    {
        "filename": "03_apartes_relacionais_colab.ipynb",
        "title": "03 — Apartes relacionais, segmentação e atos de fala",
        "description": "Aplica o recorte temporal, analisa díades, constrói pontes e segmenta com IA apenas os discursos candidatos.",
        "method": "Nem todo discurso contém aparte. A base de apartes define os candidatos; a IA devolve somente IDs de blocos e a máquina local reconstrói texto e offsets. Ponte e segmentação continuam bloqueadas por validação humana.",
        "preflight": """
            APARTES_PATH = INPUT_PATHS["interjections"]
            APARTES_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert APARTES_PATH.exists(), APARTES_PATH
            assert APARTES_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
            GERAR_JSONL_SEGMENTACAO = False
            ENVIAR_BATCH_SEGMENTACAO = False
            BAIXAR_BATCH_SEGMENTACAO = False
            PROCESSAR_BATCH_SEGMENTACAO = False
            VALIDAR_SEGMENTACAO = False
            GERAR_JSONL_ATOS_FALA = False
            ENVIAR_BATCH_ATOS_FALA = False
            BAIXAR_BATCH_ATOS_FALA = False
            PROCESSAR_BATCH_ATOS_FALA = False
            APARTES_SEGMENTATION_MODEL = ANALYSIS_CONFIG.raw["openai"]["interjection_segmentation_model"]
            APARTES_QUALITATIVE_MODEL = ANALYSIS_CONFIG.raw["openai"]["interjection_default_model"]
            APARTES_STAGE_ROOT = RUN_OUTPUT_ROOT / "03_apartes"
            APARTES_SEGMENTATION_SOURCES_PATH = APARTES_STAGE_ROOT / "fontes_segmentacao_ia.parquet"
            APARTES_INTERACTIONS_PATH = APARTES_STAGE_ROOT / "interacoes_segmentadas_ia.parquet"
            APARTES_SEGMENTATION_QUALITY_PATH = APARTES_STAGE_ROOT / "segmentacao_qualidade.json"
            APARTES_SEGMENTATION_REVIEW_PATH = APARTES_STAGE_ROOT / "revisao_segmentacao_ia.csv"
            APARTES_SEGMENTATION_BATCH_REQUEST_PATH = APARTES_STAGE_ROOT / f"batch_segmentacao_{APARTES_SEGMENTATION_MODEL}.jsonl"
            APARTES_SEGMENTATION_REQUEST_MANIFEST_PATH = APARTES_STAGE_ROOT / "batch_segmentacao_requests.json"
            APARTES_SEGMENTATION_BATCH_CONTROL_PATH = APARTES_STAGE_ROOT / "batch_segmentacao.json"
            APARTES_CODEBOOK_PATH = APARTES_STAGE_ROOT / "codebook_atos_fala.csv"
            APARTES_BATCH_REQUEST_PATH = APARTES_STAGE_ROOT / f"batch_atos_fala_{APARTES_QUALITATIVE_MODEL}.jsonl"
            APARTES_REQUEST_MANIFEST_PATH = APARTES_STAGE_ROOT / "batch_atos_fala_requests.json"
            APARTES_BATCH_CONTROL_PATH = APARTES_STAGE_ROOT / "batch_atos_fala.json"
            APARTES_HUMAN_PILOT_PATH = APARTES_STAGE_ROOT / "piloto_atos_fala_ia.csv"
        """,
        "run": """
            from analise.discursos_plenario.apartes import run_interjection_analysis

            APARTES_RESULT = None
            if RODAR_ETAPA:
                APARTES_RESULT = run_interjection_analysis(data_root=DATA_ROOT, run_id=RUN_ID, config_path=CONFIG_PATH)
                print(APARTES_RESULT["manifest_path"])
            else:
                print("Apartes não executados.")
        """,
        "validate": """
            import json
            import pandas as pd

            APARTES_CUT_PATH = RUN_OUTPUT_ROOT / "03_apartes" / "recorte_apartes.csv"
            APARTES_TESTS_PATH = RUN_OUTPUT_ROOT / "03_apartes" / "testes_associacao.csv"
            APARTES_UNIVERSE_PATH = RUN_OUTPUT_ROOT / "03_apartes" / "universo_segmentacao.csv"
            APARTES_BRIDGE_QUALITY_PATH = RUN_OUTPUT_ROOT / "03_apartes" / "ponte_camara_qualidade.json"
            if APARTES_CUT_PATH.exists():
                APARTES_CUT = pd.read_csv(APARTES_CUT_PATH)
                display(APARTES_CUT)
            if APARTES_TESTS_PATH.exists():
                APARTES_TESTS = pd.read_csv(APARTES_TESTS_PATH)
                display(APARTES_TESTS)
            if APARTES_UNIVERSE_PATH.exists():
                APARTES_UNIVERSE = pd.read_csv(APARTES_UNIVERSE_PATH)
                display(APARTES_UNIVERSE)
            if APARTES_BRIDGE_QUALITY_PATH.exists():
                APARTES_BRIDGE_QUALITY = json.loads(APARTES_BRIDGE_QUALITY_PATH.read_text(encoding="utf-8"))
                print(
                    "Denominadores autorizados:",
                    APARTES_BRIDGE_QUALITY.get("denominators_authorized", False),
                )
                display(APARTES_BRIDGE_QUALITY)
            if APARTES_SEGMENTATION_QUALITY_PATH.exists():
                APARTES_SEGMENTATION_QUALITY = json.loads(APARTES_SEGMENTATION_QUALITY_PATH.read_text(encoding="utf-8"))
                print(APARTES_SEGMENTATION_QUALITY)
        """,
        "extra": [
            (
                "Preparar o Batch de segmentação por IA",
                "É gerada uma requisição por discurso ligado, reunindo todos os candidatos daquele texto. O modelo vê blocos numerados e devolve apenas status e limites; não devolve os trechos.",
                """
                import pandas as pd
                from analise.discursos_plenario.apartes_qualitativos import write_segmentation_batch_jsonl
                from analise.discursos_plenario.io import artifact_record, write_json_atomic

                if GERAR_JSONL_SEGMENTACAO:
                    APARTES_SEGMENTATION_SOURCES = pd.read_parquet(APARTES_SEGMENTATION_SOURCES_PATH)
                    APARTES_SEGMENTATION_REQUEST_PATHS = write_segmentation_batch_jsonl(
                        APARTES_SEGMENTATION_SOURCES,
                        APARTES_SEGMENTATION_BATCH_REQUEST_PATH,
                        config=ANALYSIS_CONFIG,
                        model=APARTES_SEGMENTATION_MODEL,
                    )
                    assert APARTES_SEGMENTATION_REQUEST_PATHS, "Nenhum discurso elegível para o Batch."
                    write_json_atomic(
                        APARTES_SEGMENTATION_REQUEST_MANIFEST_PATH,
                        {
                            "model": APARTES_SEGMENTATION_MODEL,
                            "request_paths": [str(path) for path in APARTES_SEGMENTATION_REQUEST_PATHS],
                            "requests": [
                                artifact_record(path)
                                for path in APARTES_SEGMENTATION_REQUEST_PATHS
                            ],
                        },
                    )
                    print("Discursos no Batch:", len(APARTES_SEGMENTATION_SOURCES))
                    print("Partes do Batch:", len(APARTES_SEGMENTATION_REQUEST_PATHS))
                    for APARTES_SEGMENTATION_REQUEST_PATH in APARTES_SEGMENTATION_REQUEST_PATHS:
                        print(APARTES_SEGMENTATION_REQUEST_PATH)
                else:
                    print("JSONL de segmentação não gerado.")
                """,
            ),
            (
                "Enviar o Batch de segmentação",
                "O envio é explícito. A chave já configurada é lida de `OPENAI_API_KEY` no ambiente ou dos Secrets do Colab e nunca é impressa ou gravada.",
                """
                import json
                import os
                from pathlib import Path
                from openai import OpenAI
                from analise.discursos_plenario.figuras import submit_responses_batch
                from analise.discursos_plenario.io import sha256_file, write_json_atomic

                if ENVIAR_BATCH_SEGMENTACAO:
                    assert APARTES_SEGMENTATION_REQUEST_MANIFEST_PATH.exists(), "Gere e inspecione os JSONLs primeiro."
                    APARTES_SEGMENTATION_REQUEST_MANIFEST = json.loads(
                        APARTES_SEGMENTATION_REQUEST_MANIFEST_PATH.read_text(encoding="utf-8")
                    )
                    assert APARTES_SEGMENTATION_REQUEST_MANIFEST["model"] == APARTES_SEGMENTATION_MODEL
                    APARTES_SEGMENTATION_REQUEST_PATHS = [
                        Path(path) for path in APARTES_SEGMENTATION_REQUEST_MANIFEST["request_paths"]
                    ]
                    APARTES_SEGMENTATION_REQUEST_HASHES = {
                        item["path"]: item["sha256"]
                        for item in APARTES_SEGMENTATION_REQUEST_MANIFEST["requests"]
                    }
                    assert APARTES_SEGMENTATION_REQUEST_PATHS
                    assert all(path.exists() for path in APARTES_SEGMENTATION_REQUEST_PATHS)
                    assert all(
                        sha256_file(path) == APARTES_SEGMENTATION_REQUEST_HASHES[str(path)]
                        for path in APARTES_SEGMENTATION_REQUEST_PATHS
                    ), "Um JSONL mudou depois da criação do manifesto."
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            APARTES_SEGMENTATION_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            APARTES_SEGMENTATION_SECRET = None
                        if APARTES_SEGMENTATION_SECRET:
                            os.environ["OPENAI_API_KEY"] = APARTES_SEGMENTATION_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    APARTES_SEGMENTATION_CLIENT = OpenAI()
                    if APARTES_SEGMENTATION_BATCH_CONTROL_PATH.exists():
                        APARTES_SEGMENTATION_BATCH_CONTROL = json.loads(
                            APARTES_SEGMENTATION_BATCH_CONTROL_PATH.read_text(encoding="utf-8")
                        )
                        assert APARTES_SEGMENTATION_BATCH_CONTROL["model"] == APARTES_SEGMENTATION_MODEL
                    else:
                        APARTES_SEGMENTATION_BATCH_CONTROL = {
                            "model": APARTES_SEGMENTATION_MODEL,
                            "batches": [],
                        }
                    APARTES_SEGMENTATION_ALREADY_SUBMITTED = {
                        item["request_path"]: item["request_sha256"]
                        for item in APARTES_SEGMENTATION_BATCH_CONTROL["batches"]
                    }
                    for APARTES_SEGMENTATION_PART_NUMBER, APARTES_SEGMENTATION_REQUEST_PATH in enumerate(
                        APARTES_SEGMENTATION_REQUEST_PATHS,
                        start=1,
                    ):
                        if str(APARTES_SEGMENTATION_REQUEST_PATH) in APARTES_SEGMENTATION_ALREADY_SUBMITTED:
                            assert (
                                APARTES_SEGMENTATION_ALREADY_SUBMITTED[str(APARTES_SEGMENTATION_REQUEST_PATH)]
                                == APARTES_SEGMENTATION_REQUEST_HASHES[str(APARTES_SEGMENTATION_REQUEST_PATH)]
                            ), "A parte já enviada tem conteúdo diferente; use outro RUN_ID."
                            print("Parte já enviada:", APARTES_SEGMENTATION_REQUEST_PATH)
                            continue
                        APARTES_SEGMENTATION_BATCH_SUBMISSION = submit_responses_batch(
                            APARTES_SEGMENTATION_CLIENT,
                            APARTES_SEGMENTATION_REQUEST_PATH,
                            description=(
                                f"{RUN_ID}:segmentacao-apartes:{APARTES_SEGMENTATION_MODEL}:"
                                f"parte-{APARTES_SEGMENTATION_PART_NUMBER:05d}"
                            ),
                        )
                        APARTES_SEGMENTATION_OUTPUT_PATH = APARTES_SEGMENTATION_REQUEST_PATH.with_name(
                            f"{APARTES_SEGMENTATION_REQUEST_PATH.stem}_output.jsonl"
                        )
                        APARTES_SEGMENTATION_BATCH_CONTROL["batches"].append(
                            {
                                "batch_id": APARTES_SEGMENTATION_BATCH_SUBMISSION.id,
                                "request_path": str(APARTES_SEGMENTATION_REQUEST_PATH),
                                "request_sha256": APARTES_SEGMENTATION_REQUEST_HASHES[
                                    str(APARTES_SEGMENTATION_REQUEST_PATH)
                                ],
                                "output_path": str(APARTES_SEGMENTATION_OUTPUT_PATH),
                            }
                        )
                        write_json_atomic(
                            APARTES_SEGMENTATION_BATCH_CONTROL_PATH,
                            APARTES_SEGMENTATION_BATCH_CONTROL,
                        )
                        print("Batch criado:", APARTES_SEGMENTATION_BATCH_SUBMISSION.id)
                else:
                    print("Envio da segmentação desativado.")
                """,
            ),
            (
                "Baixar e reconstruir os segmentos localmente",
                "As respostas podem chegar fora de ordem. A reconciliação usa `custom_id`; os IDs dos blocos viram offsets e os trechos são recortados do texto local, sem aceitar palpites silenciosos.",
                """
                import json
                import os
                from pathlib import Path
                from openai import OpenAI
                from analise.discursos_plenario.apartes_qualitativos import run_segmentation_results
                from analise.discursos_plenario.figuras import download_completed_batch
                from analise.discursos_plenario.io import sha256_file

                APARTES_SEGMENTATION_BATCH_CONTROL_LOADED = None
                if BAIXAR_BATCH_SEGMENTACAO or PROCESSAR_BATCH_SEGMENTACAO:
                    assert APARTES_SEGMENTATION_BATCH_CONTROL_PATH.exists(), APARTES_SEGMENTATION_BATCH_CONTROL_PATH
                    APARTES_SEGMENTATION_BATCH_CONTROL_LOADED = json.loads(
                        APARTES_SEGMENTATION_BATCH_CONTROL_PATH.read_text(encoding="utf-8")
                    )
                    assert APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["model"] == APARTES_SEGMENTATION_MODEL
                    assert APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["batches"]
                    assert all(
                        sha256_file(item["request_path"]) == item["request_sha256"]
                        for item in APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["batches"]
                    ), "Um JSONL mudou depois do envio; não é seguro reconciliar a saída."
                if BAIXAR_BATCH_SEGMENTACAO:
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            APARTES_SEGMENTATION_DOWNLOAD_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            APARTES_SEGMENTATION_DOWNLOAD_SECRET = None
                        if APARTES_SEGMENTATION_DOWNLOAD_SECRET:
                            os.environ["OPENAI_API_KEY"] = APARTES_SEGMENTATION_DOWNLOAD_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    APARTES_SEGMENTATION_DOWNLOAD_CLIENT = OpenAI()
                    for APARTES_SEGMENTATION_BATCH_PART in APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["batches"]:
                        APARTES_SEGMENTATION_BATCH_OUTPUT_PATH = Path(
                            APARTES_SEGMENTATION_BATCH_PART["output_path"]
                        )
                        download_completed_batch(
                            APARTES_SEGMENTATION_DOWNLOAD_CLIENT,
                            APARTES_SEGMENTATION_BATCH_PART["batch_id"],
                            APARTES_SEGMENTATION_BATCH_OUTPUT_PATH,
                        )
                        print(APARTES_SEGMENTATION_BATCH_OUTPUT_PATH)
                APARTES_SEGMENTATION_RESULT = None
                if PROCESSAR_BATCH_SEGMENTACAO:
                    APARTES_SEGMENTATION_REQUEST_PATHS = [
                        Path(item["request_path"])
                        for item in APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["batches"]
                    ]
                    APARTES_SEGMENTATION_BATCH_OUTPUT_PATHS = [
                        Path(item["output_path"])
                        for item in APARTES_SEGMENTATION_BATCH_CONTROL_LOADED["batches"]
                    ]
                    assert all(path.exists() for path in APARTES_SEGMENTATION_REQUEST_PATHS)
                    assert all(path.exists() for path in APARTES_SEGMENTATION_BATCH_OUTPUT_PATHS)
                    APARTES_SEGMENTATION_RESULT = run_segmentation_results(
                        data_root=DATA_ROOT,
                        run_id=RUN_ID,
                        batch_output_path=APARTES_SEGMENTATION_BATCH_OUTPUT_PATHS,
                        request_path=APARTES_SEGMENTATION_REQUEST_PATHS,
                        model=APARTES_SEGMENTATION_MODEL,
                        config_path=CONFIG_PATH,
                    )
                    print(APARTES_SEGMENTATION_RESULT["manifest_path"])
                else:
                    print("Reconstrução da segmentação desativada.")
                """,
            ),
            (
                "Revisar a segmentação dos turnos",
                "Depois da reconstrução, o caderno cria até 200 interações balanceadas. Linhas vazias não contam como revisadas; são necessários 100 casos completos e 95% de precisão em cada trecho.",
                """
                import json
                import pandas as pd
                from analise.discursos_plenario.apartes_qualitativos import segmentation_quality
                from analise.discursos_plenario.io import write_json_atomic

                APARTES_SEGMENTATION_VALIDATION = None
                if VALIDAR_SEGMENTACAO:
                    APARTES_INTERACTIONS = pd.read_parquet(APARTES_INTERACTIONS_PATH)
                    APARTES_SEGMENTATION_GOLD = pd.read_csv(APARTES_SEGMENTATION_REVIEW_PATH, keep_default_na=False)
                    APARTES_SEGMENTATION_CONFIG = ANALYSIS_CONFIG.raw["interjection_segmentation"]
                    APARTES_SEGMENTATION_VALIDATION = segmentation_quality(
                        APARTES_INTERACTIONS,
                        APARTES_SEGMENTATION_GOLD,
                        min_precision=APARTES_SEGMENTATION_CONFIG["min_precision"],
                        min_reviewed=APARTES_SEGMENTATION_CONFIG["min_reviewed"],
                    )
                    APARTES_SEGMENTATION_QUALITY_EXISTING = (
                        json.loads(APARTES_SEGMENTATION_QUALITY_PATH.read_text(encoding="utf-8"))
                        if APARTES_SEGMENTATION_QUALITY_PATH.exists()
                        else {}
                    )
                    APARTES_SEGMENTATION_VALIDATION = {
                        **APARTES_SEGMENTATION_QUALITY_EXISTING,
                        **APARTES_SEGMENTATION_VALIDATION,
                    }
                    write_json_atomic(
                        APARTES_SEGMENTATION_QUALITY_PATH,
                        APARTES_SEGMENTATION_VALIDATION,
                    )
                    print(APARTES_SEGMENTATION_VALIDATION)
                else:
                    print("Validação desativada; preencha primeiro a amostra de revisão.")
                """,
            ),
            (
                "Preparar atos de fala e possível descortesia",
                "Complete o codebook do TD 355. O JSONL contém somente os turnos segmentados; respostas ausentes ficam explicitamente marcadas.",
                """
                import json
                import pandas as pd
                from analise.discursos_plenario.apartes_qualitativos import write_qualitative_batch_jsonl
                from analise.discursos_plenario.io import artifact_record, write_json_atomic

                if GERAR_JSONL_ATOS_FALA:
                    APARTES_SEGMENTATION_GATE = json.loads(APARTES_SEGMENTATION_QUALITY_PATH.read_text(encoding="utf-8"))
                    assert APARTES_SEGMENTATION_GATE["classification_authorized"] is True, "A segmentação ainda não atingiu o gate."
                    APARTES_CODEBOOK = pd.read_csv(APARTES_CODEBOOK_PATH).fillna("")
                    APARTES_CODEBOOK_FIELDS = ["definicao_operacional", "criterio_positivo", "criterio_negativo", "caso_limitrofe"]
                    assert APARTES_CODEBOOK[APARTES_CODEBOOK_FIELDS].apply(lambda column: column.str.strip().ne("").all()).all(), "Complete o codebook."
                    APARTES_INTERACTIONS_FOR_BATCH = pd.read_parquet(APARTES_INTERACTIONS_PATH)
                    APARTES_REQUEST_PATHS = write_qualitative_batch_jsonl(
                        APARTES_INTERACTIONS_FOR_BATCH,
                        APARTES_BATCH_REQUEST_PATH,
                        codebook=APARTES_CODEBOOK.to_csv(index=False),
                        config=ANALYSIS_CONFIG,
                        model=APARTES_QUALITATIVE_MODEL,
                    )
                    assert APARTES_REQUEST_PATHS, "Nenhuma interação elegível para o Batch."
                    write_json_atomic(
                        APARTES_REQUEST_MANIFEST_PATH,
                        {
                            "model": APARTES_QUALITATIVE_MODEL,
                            "request_paths": [str(path) for path in APARTES_REQUEST_PATHS],
                            "requests": [
                                artifact_record(path)
                                for path in APARTES_REQUEST_PATHS
                            ],
                        },
                    )
                    print("Partes do Batch:", len(APARTES_REQUEST_PATHS))
                    for APARTES_REQUEST_PATH in APARTES_REQUEST_PATHS:
                        print(APARTES_REQUEST_PATH)
                else:
                    print("JSONL de atos de fala não gerado.")
                """,
            ),
            (
                "Enviar o Batch de atos de fala",
                "O envio é uma ação separada e explícita. A chave vem do ambiente ou dos Secrets do Colab e não é gravada.",
                """
                import json
                import os
                from pathlib import Path
                from openai import OpenAI
                from analise.discursos_plenario.figuras import submit_responses_batch
                from analise.discursos_plenario.io import sha256_file, write_json_atomic

                if ENVIAR_BATCH_ATOS_FALA:
                    assert APARTES_REQUEST_MANIFEST_PATH.exists(), "Gere e inspecione os JSONLs primeiro."
                    APARTES_REQUEST_MANIFEST = json.loads(
                        APARTES_REQUEST_MANIFEST_PATH.read_text(encoding="utf-8")
                    )
                    assert APARTES_REQUEST_MANIFEST["model"] == APARTES_QUALITATIVE_MODEL
                    APARTES_REQUEST_PATHS = [
                        Path(path) for path in APARTES_REQUEST_MANIFEST["request_paths"]
                    ]
                    APARTES_REQUEST_HASHES = {
                        item["path"]: item["sha256"]
                        for item in APARTES_REQUEST_MANIFEST["requests"]
                    }
                    assert APARTES_REQUEST_PATHS
                    assert all(path.exists() for path in APARTES_REQUEST_PATHS)
                    assert all(
                        sha256_file(path) == APARTES_REQUEST_HASHES[str(path)]
                        for path in APARTES_REQUEST_PATHS
                    ), "Um JSONL mudou depois da criação do manifesto."
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            APARTES_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            APARTES_SECRET = None
                        if APARTES_SECRET:
                            os.environ["OPENAI_API_KEY"] = APARTES_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    APARTES_OPENAI_CLIENT = OpenAI()
                    if APARTES_BATCH_CONTROL_PATH.exists():
                        APARTES_BATCH_CONTROL = json.loads(
                            APARTES_BATCH_CONTROL_PATH.read_text(encoding="utf-8")
                        )
                        assert APARTES_BATCH_CONTROL["model"] == APARTES_QUALITATIVE_MODEL
                    else:
                        APARTES_BATCH_CONTROL = {
                            "model": APARTES_QUALITATIVE_MODEL,
                            "batches": [],
                        }
                    APARTES_ALREADY_SUBMITTED = {
                        item["request_path"]: item["request_sha256"]
                        for item in APARTES_BATCH_CONTROL["batches"]
                    }
                    for APARTES_PART_NUMBER, APARTES_REQUEST_PATH in enumerate(
                        APARTES_REQUEST_PATHS,
                        start=1,
                    ):
                        if str(APARTES_REQUEST_PATH) in APARTES_ALREADY_SUBMITTED:
                            assert (
                                APARTES_ALREADY_SUBMITTED[str(APARTES_REQUEST_PATH)]
                                == APARTES_REQUEST_HASHES[str(APARTES_REQUEST_PATH)]
                            ), "A parte já enviada tem conteúdo diferente; use outro RUN_ID."
                            print("Parte já enviada:", APARTES_REQUEST_PATH)
                            continue
                        APARTES_BATCH_SUBMISSION = submit_responses_batch(
                            APARTES_OPENAI_CLIENT,
                            APARTES_REQUEST_PATH,
                            description=(
                                f"{RUN_ID}:atos-fala:{APARTES_QUALITATIVE_MODEL}:"
                                f"parte-{APARTES_PART_NUMBER:05d}"
                            ),
                        )
                        APARTES_BATCH_OUTPUT_PATH = APARTES_REQUEST_PATH.with_name(
                            f"{APARTES_REQUEST_PATH.stem}_output.jsonl"
                        )
                        APARTES_BATCH_CONTROL["batches"].append(
                            {
                                "batch_id": APARTES_BATCH_SUBMISSION.id,
                                "request_path": str(APARTES_REQUEST_PATH),
                                "request_sha256": APARTES_REQUEST_HASHES[
                                    str(APARTES_REQUEST_PATH)
                                ],
                                "output_path": str(APARTES_BATCH_OUTPUT_PATH),
                            }
                        )
                        write_json_atomic(
                            APARTES_BATCH_CONTROL_PATH,
                            APARTES_BATCH_CONTROL,
                        )
                        print("Batch criado:", APARTES_BATCH_SUBMISSION.id)
                else:
                    print("Envio desativado.")
                """,
            ),
            (
                "Baixar e analisar o Batch concluído",
                "A saída é reconciliada por `custom_id`, gera prevalências anuais e por direção de gênero e, quando o piloto estiver adjudicado, Jaccard, F1 e kappa.",
                """
                import json
                import os
                from pathlib import Path
                from openai import OpenAI
                from analise.discursos_plenario.apartes_qualitativos import run_qualitative_results
                from analise.discursos_plenario.figuras import download_completed_batch
                from analise.discursos_plenario.io import sha256_file

                APARTES_BATCH_CONTROL_LOADED = None
                if BAIXAR_BATCH_ATOS_FALA or PROCESSAR_BATCH_ATOS_FALA:
                    assert APARTES_BATCH_CONTROL_PATH.exists(), APARTES_BATCH_CONTROL_PATH
                    APARTES_BATCH_CONTROL_LOADED = json.loads(
                        APARTES_BATCH_CONTROL_PATH.read_text(encoding="utf-8")
                    )
                    assert APARTES_BATCH_CONTROL_LOADED["model"] == APARTES_QUALITATIVE_MODEL
                    assert APARTES_BATCH_CONTROL_LOADED["batches"]
                    assert all(
                        sha256_file(item["request_path"]) == item["request_sha256"]
                        for item in APARTES_BATCH_CONTROL_LOADED["batches"]
                    ), "Um JSONL mudou depois do envio; não é seguro reconciliar a saída."
                if BAIXAR_BATCH_ATOS_FALA:
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            APARTES_DOWNLOAD_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            APARTES_DOWNLOAD_SECRET = None
                        if APARTES_DOWNLOAD_SECRET:
                            os.environ["OPENAI_API_KEY"] = APARTES_DOWNLOAD_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    APARTES_DOWNLOAD_CLIENT = OpenAI()
                    for APARTES_BATCH_PART in APARTES_BATCH_CONTROL_LOADED["batches"]:
                        APARTES_BATCH_OUTPUT_PATH = Path(APARTES_BATCH_PART["output_path"])
                        download_completed_batch(
                            APARTES_DOWNLOAD_CLIENT,
                            APARTES_BATCH_PART["batch_id"],
                            APARTES_BATCH_OUTPUT_PATH,
                        )
                        print(APARTES_BATCH_OUTPUT_PATH)
                APARTES_QUALITATIVE_RESULT = None
                if PROCESSAR_BATCH_ATOS_FALA:
                    APARTES_REQUEST_PATHS = [
                        Path(item["request_path"])
                        for item in APARTES_BATCH_CONTROL_LOADED["batches"]
                    ]
                    APARTES_BATCH_OUTPUT_PATHS = [
                        Path(item["output_path"])
                        for item in APARTES_BATCH_CONTROL_LOADED["batches"]
                    ]
                    assert all(path.exists() for path in APARTES_REQUEST_PATHS)
                    assert all(path.exists() for path in APARTES_BATCH_OUTPUT_PATHS)
                    APARTES_QUALITATIVE_RESULT = run_qualitative_results(
                        data_root=DATA_ROOT,
                        run_id=RUN_ID,
                        batch_output_path=APARTES_BATCH_OUTPUT_PATHS,
                        request_path=APARTES_REQUEST_PATHS,
                        model=APARTES_QUALITATIVE_MODEL,
                        config_path=CONFIG_PATH,
                    )
                    print(APARTES_QUALITATIVE_RESULT["manifest_path"])
                else:
                    print("Processamento da saída desativado.")
                """,
            ),
        ],
    },
    {
        "filename": "04_nlp_leiturabilidade_morfossintaxe_colab.ipynb",
        "title": "04 — NLP, leiturabilidade e morfossintaxe",
        "description": "Extrai métricas do TextDescriptives, do spaCy e padrões linguísticos específicos.",
        "method": "O mesmo `Doc` de `pt_core_news_lg` alimenta as métricas gerais e customizadas; o processamento completo fica reservado ao Colab.",
        "preflight": """
            import subprocess
            import sys

            NLP_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert NLP_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
            try:
                import pt_core_news_lg  # noqa: F401
            except ImportError:
                subprocess.run([sys.executable, "-m", "spacy", "download", "pt_core_news_lg"], check=True)
            NLP_LIMIT = None
            NLP_BATCH_SIZE = 32
            NLP_N_PROCESS = 1
        """,
        "run": """
            from analise.discursos_plenario.nlp import run_nlp_analysis

            NLP_RESULT = None
            if RODAR_ETAPA:
                NLP_RESULT = run_nlp_analysis(
                    data_root=DATA_ROOT,
                    run_id=RUN_ID,
                    config_path=CONFIG_PATH,
                    model="pt_core_news_lg",
                    limit=NLP_LIMIT,
                    batch_size=NLP_BATCH_SIZE,
                    n_process=NLP_N_PROCESS,
                )
                print(NLP_RESULT["manifest_path"])
            else:
                print("NLP não executado. Para smoke, defina NLP_LIMIT antes de habilitar.")
        """,
        "validate": """
            import pandas as pd

            NLP_FEATURES_PATH = RUN_OUTPUT_ROOT / "04_nlp" / "nlp_features.parquet"
            if NLP_FEATURES_PATH.exists():
                NLP_FEATURES = pd.read_parquet(NLP_FEATURES_PATH)
                NLP_REQUIRED_COLUMNS = {"texto_id", "prop_pron", "prop_adp", "prop_aux", "type_token_ratio"}
                assert NLP_REQUIRED_COLUMNS <= set(NLP_FEATURES.columns)
                display(NLP_FEATURES.head())
        """,
    },
    {
        "filename": "05_inferencia_series_temporais_colab.ipynb",
        "title": "05 — Inferência em séries temporais",
        "description": "Compara trajetórias anuais em níveis e diferenças e estima tendências com erros HAC.",
        "method": "2026 fica fora dos modelos anuais. Correlações e tendências descrevem associação temporal, não causalidade.",
        "preflight": """
            INFERENCIA_FEATURES_PATH = RUN_OUTPUT_ROOT / "04_nlp" / "nlp_features.parquet"
            assert INFERENCIA_FEATURES_PATH.exists(), "Execute o caderno 04."
            INFERENCIA_METRICS = None  # Opcional: lista explícita de colunas numéricas.
        """,
        "run": """
            from analise.discursos_plenario.inferencia import run_temporal_inference

            INFERENCIA_RESULT = None
            if RODAR_ETAPA:
                INFERENCIA_RESULT = run_temporal_inference(
                    data_root=DATA_ROOT,
                    run_id=RUN_ID,
                    metrics=INFERENCIA_METRICS,
                    config_path=CONFIG_PATH,
                )
                print(INFERENCIA_RESULT["manifest_path"])
            else:
                print("Inferência temporal não executada.")
        """,
        "validate": """
            import pandas as pd

            INFERENCIA_CORRELATIONS_PATH = RUN_OUTPUT_ROOT / "05_inferencia" / "correlacoes.csv"
            if INFERENCIA_CORRELATIONS_PATH.exists():
                INFERENCIA_CORRELATIONS = pd.read_csv(INFERENCIA_CORRELATIONS_PATH)
                assert INFERENCIA_CORRELATIONS["year_max"].le(2025).all()
                assert set(INFERENCIA_CORRELATIONS["scale"]) <= {"level", "first_difference"}
                display(INFERENCIA_CORRELATIONS.head())
        """,
    },
    {
        "filename": "06_clusterizacao_discursos_colab.ipynb",
        "title": "06 — Clusterização dos discursos",
        "description": "Avalia `k=2…8` sem impor quantidade ou nomes de perfis.",
        "method": "A decisão final exige leitura conjunta dos índices, da estabilidade, dos centroides e de discursos representativos; ausência de clusters estáveis é um resultado admissível.",
        "preflight": """
            CLUSTER_FEATURES_PATH = RUN_OUTPUT_ROOT / "04_nlp" / "nlp_features.parquet"
            assert CLUSTER_FEATURES_PATH.exists(), "Execute o caderno 04."
            print("Variáveis:", ANALYSIS_CONFIG.raw["clustering"]["features"])
        """,
        "run": """
            from analise.discursos_plenario.clusterizacao import run_clustering

            CLUSTER_RESULT = None
            if RODAR_ETAPA:
                CLUSTER_RESULT = run_clustering(data_root=DATA_ROOT, run_id=RUN_ID, config_path=CONFIG_PATH)
                print(CLUSTER_RESULT["manifest_path"])
            else:
                print("Avaliação de k não executada.")
        """,
        "validate": """
            import pandas as pd

            CLUSTER_EVALUATION_PATH = RUN_OUTPUT_ROOT / "06_clusterizacao" / "avaliacao_k.csv"
            if CLUSTER_EVALUATION_PATH.exists():
                CLUSTER_EVALUATION = pd.read_csv(CLUSTER_EVALUATION_PATH)
                assert CLUSTER_EVALUATION["k"].tolist() == list(range(2, 9))
                display(CLUSTER_EVALUATION)
                print("Preencha decisao_k.csv somente após examinar resultados e casos representativos.")
        """,
    },
    {
        "filename": "07_topicos_bertopic_colab.ipynb",
        "title": "07 — Tópicos com BERTopic",
        "description": "Treina um modelo comum às três arenas usando amostra balanceada de resumos.",
        "method": "Resumo ausente é exclusão, não convite para substituir pelo texto integral. Cobertura e outliers acompanham toda interpretação.",
        "preflight": """
            TOPICOS_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert TOPICOS_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
            TOPICOS_STABILITY_REPETITIONS = 2
        """,
        "run": """
            from analise.discursos_plenario.topicos import run_topic_modeling

            TOPICOS_RESULT = None
            if RODAR_ETAPA:
                TOPICOS_RESULT = run_topic_modeling(
                    data_root=DATA_ROOT,
                    run_id=RUN_ID,
                    config_path=CONFIG_PATH,
                    stability_repetitions=TOPICOS_STABILITY_REPETITIONS,
                )
                print(TOPICOS_RESULT["manifest_path"])
            else:
                print("BERTopic não executado.")
        """,
        "validate": """
            import pandas as pd

            TOPICOS_COVERAGE_PATH = RUN_OUTPUT_ROOT / "07_topicos" / "cobertura.csv"
            if TOPICOS_COVERAGE_PATH.exists():
                TOPICOS_COVERAGE = pd.read_csv(TOPICOS_COVERAGE_PATH)
                assert TOPICOS_COVERAGE.loc[TOPICOS_COVERAGE["ano"].eq(2026), "ytd"].all()
                display(TOPICOS_COVERAGE.tail(12))
        """,
    },
    {
        "filename": "08_figuras_linguagem_gpt56_colab.ipynb",
        "title": "08 — Figuras de linguagem com GPT-5.6",
        "description": "Prepara codebook e piloto humano, compara modelos e gera produção estruturada por Batch API.",
        "method": "GPT-5.6 Sol é o padrão. Luna ou Terra só podem substituí-lo após não inferioridade pareada contra o mesmo piloto humano adjudicado.",
        "preflight": """
            FIGURAS_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert FIGURAS_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
            FIGURAS_MODELS = ANALYSIS_CONFIG.raw["openai"]["figures_candidate_models"]
            FIGURAS_DEFAULT_MODEL = ANALYSIS_CONFIG.raw["openai"]["figures_default_model"]
            FIGURAS_SAMPLE_LIMIT = None
            GERAR_JSONL = False
            ENVIAR_BATCH = False
            BAIXAR_BATCH_FIGURAS = False
            PROCESSAR_BATCH_FIGURAS = False
            FIGURAS_MODEL_FOR_BATCH = FIGURAS_DEFAULT_MODEL
            FIGURAS_BATCH_SCOPE = "piloto"  # piloto | producao
            print("Modelos do piloto:", FIGURAS_MODELS)
        """,
        "run": """
            from analise.discursos_plenario.figuras import prepare_figures_stage

            FIGURAS_SETUP_RESULT = None
            if RODAR_ETAPA:
                FIGURAS_SETUP_RESULT = prepare_figures_stage(
                    data_root=DATA_ROOT,
                    run_id=RUN_ID,
                    config_path=CONFIG_PATH,
                    sample_limit=FIGURAS_SAMPLE_LIMIT,
                )
                print(FIGURAS_SETUP_RESULT["manifest_path"])
            else:
                print("Setup não executado. Complete codebook e piloto antes do Batch.")
        """,
        "validate": """
            import pandas as pd

            FIGURAS_CODEBOOK_PATH = RUN_OUTPUT_ROOT / "08_figuras" / "codebook.csv"
            FIGURAS_PILOT_PATH = RUN_OUTPUT_ROOT / "08_figuras" / "piloto_humano.csv"
            if FIGURAS_CODEBOOK_PATH.exists():
                FIGURAS_CODEBOOK = pd.read_csv(FIGURAS_CODEBOOK_PATH)
                assert set(FIGURAS_CODEBOOK["categoria"]) == set(ANALYSIS_CONFIG.raw["rhetorical_figures"])
                display(FIGURAS_CODEBOOK)
        """,
        "extra": [
            (
                "Preparar o JSONL do Batch",
                "A geração exige codebook preenchido. Crie arquivos separados para cada modelo do piloto e para a produção escolhida.",
                """
                import pandas as pd
                from analise.discursos_plenario.figuras import write_batch_jsonl

                FIGURAS_BATCH_REQUEST_PATH = RUN_OUTPUT_ROOT / "08_figuras" / f"batch_{FIGURAS_MODEL_FOR_BATCH}.jsonl"
                if GERAR_JSONL:
                    FIGURAS_CODEBOOK_READY = pd.read_csv(FIGURAS_CODEBOOK_PATH).fillna("")
                    FIGURAS_CODEBOOK_FIELDS = ["definicao_operacional", "criterio_positivo", "criterio_negativo", "caso_limitrofe"]
                    assert FIGURAS_CODEBOOK_READY[FIGURAS_CODEBOOK_FIELDS].apply(lambda column: column.str.strip().ne("").all()).all(), "Complete o codebook."
                    assert FIGURAS_BATCH_SCOPE in {"piloto", "producao"}
                    FIGURAS_SAMPLE_FILENAME = "amostra_piloto.parquet" if FIGURAS_BATCH_SCOPE == "piloto" else "amostra_elegivel.parquet"
                    FIGURAS_SAMPLE = pd.read_parquet(RUN_OUTPUT_ROOT / "08_figuras" / FIGURAS_SAMPLE_FILENAME)
                    FIGURAS_CODEBOOK_TEXT = FIGURAS_CODEBOOK_READY.to_csv(index=False)
                    write_batch_jsonl(
                        FIGURAS_SAMPLE,
                        FIGURAS_BATCH_REQUEST_PATH,
                        codebook=FIGURAS_CODEBOOK_TEXT,
                        config=ANALYSIS_CONFIG,
                        model=FIGURAS_MODEL_FOR_BATCH,
                    )
                    print(FIGURAS_BATCH_SCOPE, FIGURAS_MODEL_FOR_BATCH, len(FIGURAS_SAMPLE), FIGURAS_BATCH_REQUEST_PATH)
                else:
                    print("JSONL não gerado.")
                """,
            ),
            (
                "Enviar o Batch explicitamente",
                "A chave é lida do ambiente ou dos Secrets do Colab e não é persistida. Guarde o Batch ID no arquivo de controle.",
                """
                import os
                from openai import OpenAI
                from analise.discursos_plenario.figuras import submit_responses_batch
                from analise.discursos_plenario.io import write_json_atomic

                FIGURAS_BATCH_SUBMISSION = None
                if ENVIAR_BATCH:
                    assert FIGURAS_BATCH_REQUEST_PATH.exists(), "Gere e inspecione o JSONL primeiro."
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            FIGURAS_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            FIGURAS_SECRET = None
                        if FIGURAS_SECRET:
                            os.environ["OPENAI_API_KEY"] = FIGURAS_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    FIGURAS_CLIENT = OpenAI()
                    FIGURAS_BATCH_SUBMISSION = submit_responses_batch(
                        FIGURAS_CLIENT,
                        FIGURAS_BATCH_REQUEST_PATH,
                        description=f"{RUN_ID}:{FIGURAS_MODEL_FOR_BATCH}",
                    )
                    FIGURAS_BATCH_CONTROL = {
                        "batch_id": FIGURAS_BATCH_SUBMISSION.id,
                        "model": FIGURAS_MODEL_FOR_BATCH,
                        "request_path": str(FIGURAS_BATCH_REQUEST_PATH),
                    }
                    write_json_atomic(RUN_OUTPUT_ROOT / "08_figuras" / f"batch_{FIGURAS_MODEL_FOR_BATCH}.json", FIGURAS_BATCH_CONTROL)
                    print("Batch criado:", FIGURAS_BATCH_SUBMISSION.id)
                else:
                    print("Envio desativado.")
                """,
            ),
            (
                "Avaliar concordância e não inferioridade",
                "Depois de reconciliar as respostas, compare todos os modelos nos mesmos discursos e oradores. Defina a margem antes de olhar o resultado.",
                """
                from analise.discursos_plenario.figuras import compare_models_against_human

                FIGURAS_NONINFERIORITY_MARGIN = 0.03
                FIGURAS_EVALUATION_READY = False
                FIGURAS_MODEL_SUMMARY = None
                FIGURAS_MODEL_COMPARISONS = None
                if FIGURAS_EVALUATION_READY:
                    FIGURAS_MODEL_SUMMARY, FIGURAS_MODEL_COMPARISONS = compare_models_against_human(
                        FIGURAS_HUMAN_LONG,
                        FIGURAS_RESULTS_LONG,
                        FIGURAS_METADATA,
                        ANALYSIS_CONFIG.raw["rhetorical_figures"],
                        reference_model=FIGURAS_DEFAULT_MODEL,
                        noninferiority_margin=FIGURAS_NONINFERIORITY_MARGIN,
                        repetitions=ANALYSIS_CONFIG.raw["bootstrap_repetitions"],
                        seed=ANALYSIS_CONFIG.seed,
                    )
                    display(FIGURAS_MODEL_SUMMARY)
                    display(FIGURAS_MODEL_COMPARISONS)
                else:
                    print("Carregue piloto humano e resultados reconciliados antes de habilitar a avaliação.")
                """,
            ),
            (
                "Baixar e consolidar o Batch de figuras",
                "A consolidação reconcilia `custom_id`, calcula prevalência por mil palavras, avalia o piloto adjudicado e estima custo somente se a tabela oficial de preços estiver preenchida.",
                """
                import json
                import os
                from openai import OpenAI
                from analise.discursos_plenario.figuras import download_completed_batch, run_figures_results

                FIGURAS_BATCH_CONTROL_PATH = RUN_OUTPUT_ROOT / "08_figuras" / f"batch_{FIGURAS_MODEL_FOR_BATCH}.json"
                FIGURAS_BATCH_OUTPUT_PATH = RUN_OUTPUT_ROOT / "08_figuras" / f"batch_{FIGURAS_MODEL_FOR_BATCH}_output.jsonl"
                if BAIXAR_BATCH_FIGURAS:
                    assert FIGURAS_BATCH_CONTROL_PATH.exists(), FIGURAS_BATCH_CONTROL_PATH
                    if not os.environ.get("OPENAI_API_KEY"):
                        try:
                            from google.colab import userdata
                            FIGURAS_DOWNLOAD_SECRET = userdata.get("OPENAI_API_KEY")
                        except Exception:
                            FIGURAS_DOWNLOAD_SECRET = None
                        if FIGURAS_DOWNLOAD_SECRET:
                            os.environ["OPENAI_API_KEY"] = FIGURAS_DOWNLOAD_SECRET
                    assert os.environ.get("OPENAI_API_KEY"), "Configure OPENAI_API_KEY no ambiente ou nos Secrets do Colab."
                    FIGURAS_DOWNLOAD_CLIENT = OpenAI()
                    FIGURAS_BATCH_CONTROL_LOADED = json.loads(FIGURAS_BATCH_CONTROL_PATH.read_text(encoding="utf-8"))
                    download_completed_batch(
                        FIGURAS_DOWNLOAD_CLIENT,
                        FIGURAS_BATCH_CONTROL_LOADED["batch_id"],
                        FIGURAS_BATCH_OUTPUT_PATH,
                    )
                    print(FIGURAS_BATCH_OUTPUT_PATH)
                FIGURAS_RESULTS_MANIFEST = None
                if PROCESSAR_BATCH_FIGURAS:
                    assert FIGURAS_BATCH_OUTPUT_PATH.exists(), FIGURAS_BATCH_OUTPUT_PATH
                    FIGURAS_RESULTS_MANIFEST = run_figures_results(
                        data_root=DATA_ROOT,
                        run_id=RUN_ID,
                        batch_output_path=FIGURAS_BATCH_OUTPUT_PATH,
                        request_path=FIGURAS_BATCH_REQUEST_PATH,
                        model=FIGURAS_MODEL_FOR_BATCH,
                        config_path=CONFIG_PATH,
                    )
                    print(FIGURAS_RESULTS_MANIFEST["manifest_path"])
                else:
                    print("Consolidação da saída desativada.")
                """,
            ),
        ],
    },
    {
        "filename": "09_sintese_comparativa_colab.ipynb",
        "title": "09 — Síntese comparativa",
        "description": "Integra somente artefatos anteriores e exporta tabelas, HTML e figuras finais.",
        "method": "Resultados permanecem separados por arena; comparações padronizadas são secundárias. Reprodução, robustez e exploração aparecem identificadas.",
        "preflight": """
            SINTESE_SNAPSHOT_PATH = RUN_OUTPUT_ROOT / "00_snapshot" / "discursos_plenario_snapshot.parquet"
            assert SINTESE_SNAPSHOT_PATH.exists(), "Execute o caderno 00."
            SINTESE_MANIFESTS = sorted(RUN_OUTPUT_ROOT.glob("*/manifest*.json"))
            print("Manifests disponíveis:", len(SINTESE_MANIFESTS))
            for SINTESE_MANIFEST_PATH in SINTESE_MANIFESTS:
                print(SINTESE_MANIFEST_PATH.relative_to(RUN_OUTPUT_ROOT))
        """,
        "run": """
            from analise.discursos_plenario.sintese import run_synthesis

            SINTESE_RESULT = None
            if RODAR_ETAPA:
                SINTESE_RESULT = run_synthesis(data_root=DATA_ROOT, run_id=RUN_ID, config_path=CONFIG_PATH)
                print(SINTESE_RESULT["manifest_path"])
            else:
                print("Síntese não executada.")
        """,
        "validate": """
            import pandas as pd

            SINTESE_COVERAGE_PATH = RUN_OUTPUT_ROOT / "09_sintese" / "cobertura.csv"
            if SINTESE_COVERAGE_PATH.exists():
                SINTESE_COVERAGE = pd.read_csv(SINTESE_COVERAGE_PATH)
                assert SINTESE_COVERAGE.loc[SINTESE_COVERAGE["ano"].eq(2026), "ytd"].all()
                SINTESE_EXPECTED = ["cobertura.parquet", "sintese.html", "discursos_por_arena.svg", "discursos_por_arena.png"]
                assert all((RUN_OUTPUT_ROOT / "09_sintese" / name).exists() for name in SINTESE_EXPECTED)
                display(SINTESE_COVERAGE.tail(12))
        """,
    },
]


def build_notebook(spec: dict[str, object]) -> nbformat.NotebookNode:
    stem = Path(str(spec["filename"])).stem
    cells = [
        md(f"# {spec['title']}\n\n{spec['description']}", f"{stem}.title"),
        DRIVE_CELL,
        SETUP_CELL,
        md("## Configuração\n\nUse o mesmo `RUN_ID` em toda a suíte. A configuração versionada é a fonte de verdade.", f"{stem}.configuration"),
        CONTROL_CELL,
        md(f"## Decisão metodológica\n\n{spec['method']}", f"{stem}.method"),
        code(str(spec["preflight"]), "preflight"),
        md("## Execução\n\nA etapa cara permanece desativada até a inspeção das entradas e dos parâmetros acima.", f"{stem}.execution"),
        code(str(spec["run"]), "run_stage"),
        md("## Validação imediata\n\nEsta checagem não substitui os testes sintéticos nem a revisão dos manifests.", f"{stem}.validation"),
        code(str(spec["validate"]), "validate_stage"),
    ]
    for index, (title, description, source) in enumerate(spec.get("extra", []), start=1):
        cells.extend(
            [
                md(f"## {title}\n\n{description}", f"{stem}.extra.{index}"),
                code(source, f"extra_{index}"),
            ]
        )
    notebook = nbformat.v4.new_notebook()
    notebook.metadata.update(
        {
            "colab": {"name": str(spec["filename"]), "provenance": []},
            "falando_nela": {
                "narrative_language": "pt-BR",
                "analysis_config": "analise/discursos_plenario/config.v1.json",
                "markdown_source_of_truth": True,
            },
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        }
    )
    notebook.cells = cells
    return notebook


def serialize_notebook(path: Path, notebook: nbformat.NotebookNode) -> str:
    relative = path.relative_to(ROOT).as_posix()
    for index, cell in enumerate(notebook.cells):
        stable_key = f"{relative}:{index}:{cell.cell_type}:{cell.source}".encode("utf-8")
        cell["id"] = sha256(stable_key).hexdigest()[:16]
    nbformat.validate(notebook)
    return nbformat.writes(notebook) + "\n"


def generate(*, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for spec in NOTEBOOKS:
        path = OUTPUT_DIR / str(spec["filename"])
        content = serialize_notebook(path, build_notebook(spec))
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            changed.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT), "OK" if current == content else ("DIFF" if check else "WRITTEN"))
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = generate(check=args.check)
    if args.check and changed:
        raise SystemExit("Cadernos fora de sincronia com o gerador")


if __name__ == "__main__":
    main()
