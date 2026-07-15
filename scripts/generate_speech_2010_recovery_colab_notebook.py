from __future__ import annotations

import argparse
import textwrap
from hashlib import sha256
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "coleta" / "09_recuperacao_discursos_plenario_2010_colab.ipynb"


def clean(value: str) -> str:
    return textwrap.dedent(value).strip()


def code(value: str, role: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_code_cell(clean(value))
    cell.metadata["falando_nela"] = {"role": role}
    return cell


def markdown(value: str) -> nbformat.NotebookNode:
    cell = nbformat.v4.new_markdown_cell(clean(value))
    cell.metadata["language"] = "pt-BR"
    return cell


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        markdown(
            """
            # Recuperação verificável dos discursos de plenário de 2010

            Este caderno recupera o ano de 2010 que continuou fora do snapshot.
            Para Câmara, a fonte é a API oficial por `id` do deputado — nunca
            por nome. Para Congresso, ele audita o raw já coletado por
            `CodigoParlamentar` e separa texto disponível de um item que a fonte
            oficial só oferece em vídeo.

            Não rode o caderno 07 até este caderno terminar seus dois gates. O
            caderno 07 atualizado exigirá 2010 no Parquet e no snapshot.
            """
        ),
        code(
            """
            from google.colab import drive

            drive.mount("/content/drive")
            """,
            "mount_drive",
        ),
        code(
            """
            from pathlib import Path
            import os
            import subprocess
            import sys

            REPO_URL = "https://github.com/pedblan/falando_nela.git"
            REPO_REF = "2015_2016"
            REPO_DIR = Path("/content/falando_nela")

            if not REPO_DIR.exists():
                subprocess.run(
                    ["git", "clone", "--branch", REPO_REF, "--single-branch", REPO_URL, str(REPO_DIR)],
                    check=True,
                )
            else:
                dirty = subprocess.check_output(
                    ["git", "-C", str(REPO_DIR), "status", "--porcelain"], text=True
                ).strip()
                assert not dirty, f"Clone efêmero com alterações locais: {dirty}"
                subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "origin", REPO_REF], check=True)
                branches = subprocess.check_output(
                    ["git", "-C", str(REPO_DIR), "branch", "--format=%(refname:short)"], text=True
                ).splitlines()
                if REPO_REF in branches:
                    subprocess.run(["git", "-C", str(REPO_DIR), "switch", REPO_REF], check=True)
                else:
                    subprocess.run(
                        ["git", "-C", str(REPO_DIR), "switch", "--track", f"origin/{REPO_REF}"],
                        check=True,
                    )
                subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only", "origin", REPO_REF], check=True)

            assert subprocess.check_output(
                ["git", "-C", str(REPO_DIR), "branch", "--show-current"], text=True
            ).strip() == REPO_REF
            for required in [
                REPO_DIR / "coleta" / "camara" / "plenario_discursos" / "collect.py",
                REPO_DIR / "processamento" / "normalizacao.py",
            ]:
                assert required.exists(), required
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")],
                check=True,
            )
            os.chdir(REPO_DIR)
            if str(REPO_DIR) not in sys.path:
                sys.path.insert(0, str(REPO_DIR))
            print("Commit:", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
            """,
            "prepare_repository",
        ),
        code(
            """
            from pathlib import Path

            DATA_ROOT = Path("/content/drive/MyDrive/falando_nela/data")
            DATA_INICIO = "2010-01-01"
            DATA_FIM = "2010-12-31"
            RECOVERY_ID = "backfill-discursos-plenario-2010-20260715"
            RECOVERY_DIR = (
                DATA_ROOT / "operations" / "backfills" / "discursos_plenario_2010" / RECOVERY_ID
            )
            CAMARA_RUN_ID = f"{RECOVERY_ID}-camara"
            CAMARA_PERIODOS_DRIVE = (
                DATA_ROOT / "processed" / "parlamentares" / "v1" / "parquet" / "parlamentares_periodos.parquet"
            )
            CAMARA_PERIODOS_LOCAL = Path("/content/parlamentares_periodos_2010.parquet")

            RODAR_AUDITORIA_CONGRESSO = False
            RODAR_CAMARA_2010 = False
            VALIDAR_RECUPERACAO = False
            CONFIRM_RECOVERY_ID = ""

            assert DATA_ROOT.exists(), DATA_ROOT
            RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
            print("Recuperação:", RECOVERY_ID)
            print("Câmara run_id:", CAMARA_RUN_ID)
            print("Saída operacional:", RECOVERY_DIR)
            """,
            "configure",
        ),
        code(
            """
            import json
            import re
            import shutil
            import subprocess
            from collections import Counter
            from datetime import datetime, timezone

            from IPython.display import display

            def confirmed():
                assert CONFIRM_RECOVERY_ID == RECOVERY_ID, (
                    "Preencha CONFIRM_RECOVERY_ID com o valor exato de RECOVERY_ID."
                )

            def run_command(command):
                print("Executando:", " ".join(map(str, command)), flush=True)
                process = subprocess.Popen(
                    list(map(str, command)),
                    cwd=REPO_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="", flush=True)
                returncode = process.wait()
                print("returncode:", returncode)
                return returncode

            def write_operation_json(name, payload):
                path = RECOVERY_DIR / name
                payload = dict(payload)
                payload["recovery_id"] = RECOVERY_ID
                payload["written_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
                return path

            def iter_jsonl(path):
                with Path(path).open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"JSONL inválido em {path}, linha {line_number}") from exc
                        if not isinstance(record, dict):
                            raise ValueError(f"Registro não é objeto em {path}, linha {line_number}")
                        yield record

            def congress_text_inventory():
                root = DATA_ROOT / "raw" / "senado" / "congresso_discursos" / "ano=2010"
                assert root.exists(), f"Raw CN/2010 ausente: {root}"
                by_code = {}
                invalid = []
                for path in sorted(root.rglob("*.jsonl")):
                    try:
                        records = iter_jsonl(path)
                        for record in records:
                            if record.get("record_type") != "pronunciamento_texto":
                                continue
                            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                            code = str(payload.get("codigo_pronunciamento") or payload.get("CodigoPronunciamento") or record.get("source_id") or "").strip()
                            if not code:
                                invalid.append({"path": str(path), "reason": "codigo_ausente"})
                                continue
                            text = payload.get("texto") or payload.get("TextoIntegral")
                            previous = by_code.get(code)
                            candidate = {
                                "texto_disponivel": isinstance(text, str) and bool(text.strip()),
                                "texto_status": payload.get("texto_status"),
                                "metodo_obtencao": payload.get("metodo_obtencao"),
                            }
                            if previous is None or candidate["texto_disponivel"]:
                                by_code[code] = candidate
                    except ValueError as exc:
                        invalid.append({"path": str(path), "reason": str(exc)})
                statuses = Counter(row.get("texto_status") or "sem_status" for row in by_code.values())
                available = sorted(code for code, row in by_code.items() if row["texto_disponivel"])
                unavailable = sorted(code for code, row in by_code.items() if not row["texto_disponivel"])
                report = {
                    "house": "CN",
                    "year": 2010,
                    "source_ids": len(by_code),
                    "textos_disponiveis": len(available),
                    "textos_indisponiveis_na_fonte": len(unavailable),
                    "texto_status": dict(statuses),
                    "codigos_sem_texto": unavailable,
                    "invalid_records": invalid,
                }
                assert not invalid, report
                assert available, (
                    "O raw CN/2010 existe, mas a fonte não entregou nenhum texto analítico. "
                    "Veja congresso_2010_text_inventory.json antes de continuar."
                )
                return report

            def prepare_camara_periodos():
                if not CAMARA_PERIODOS_DRIVE.exists():
                    print("parlamentares_periodos não encontrado; o coletor usará GET /deputados oficial por período.")
                    return None
                shutil.copy2(CAMARA_PERIODOS_DRIVE, CAMARA_PERIODOS_LOCAL)
                assert CAMARA_PERIODOS_LOCAL.exists() and CAMARA_PERIODOS_LOCAL.stat().st_size > 0
                return CAMARA_PERIODOS_LOCAL

            def camara_command():
                command = [
                    sys.executable, "-u", "-m", "coleta.camara.plenario_discursos.collect",
                    "--mode", "prod", "--output-dir", str(DATA_ROOT),
                    "--data-inicio", DATA_INICIO, "--data-fim", DATA_FIM,
                    "--run-id", CAMARA_RUN_ID, "--no-sample", "--resume",
                ]
                periodos_path = prepare_camara_periodos()
                if periodos_path is not None:
                    command.extend(["--parlamentares-periodos-path", str(periodos_path)])
                return command

            def assert_camara_complete():
                manifest_path = DATA_ROOT / "manifests" / f"{CAMARA_RUN_ID}.json"
                checkpoint_path = DATA_ROOT / "checkpoints" / "camara" / "plenario_discursos.json"
                assert manifest_path.exists(), manifest_path
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                current = checkpoint.get("runs", {}).get(CAMARA_RUN_ID, {})
                failed = set(current.get("failed_partitions", {})) - set(current.get("completed_partitions", {}))
                assert manifest["status"] == "completed" and manifest["errors"] == 0, manifest
                assert not failed, failed

                root = DATA_ROOT / "raw" / "camara" / "plenario_discursos" / "ano=2010"
                pages = 0
                speeches = 0
                transcriptions = 0
                deputy_ids = set()
                dates_outside_2010 = []
                for path in sorted(root.rglob(f"{CAMARA_RUN_ID}.jsonl")):
                    for record in iter_jsonl(path):
                        assert record.get("record_type") == "discursos_page", record
                        source_id = str(record.get("source_id") or "")
                        match = re.match(r"^deputado:(\\d+):discursos:", source_id)
                        assert match, source_id
                        deputy_ids.add(match.group(1))
                        pages += 1
                        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                        for item in payload.get("dados", []):
                            if not isinstance(item, dict):
                                continue
                            data_hora = str(item.get("dataHoraInicio") or "")
                            if not data_hora.startswith("2010-"):
                                dates_outside_2010.append(data_hora)
                                continue
                            speeches += 1
                            transcriptions += int(bool(str(item.get("transcricao") or "").strip()))
                report = {
                    "house": "camara",
                    "year": 2010,
                    "run_id": CAMARA_RUN_ID,
                    "pages": pages,
                    "discursos": speeches,
                    "discursos_com_transcricao": transcriptions,
                    "deputados_por_id": len(deputy_ids),
                    "datas_fora_de_2010": dates_outside_2010[:100],
                    "manifest": str(manifest_path),
                }
                assert not dates_outside_2010, report
                assert speeches > 0 and transcriptions > 0, report
                return manifest, report
            """,
            "helpers",
        ),
        markdown(
            """
            ## Auditar o Congresso Nacional em 2010

            Esta etapa não coleta nem reescreve o raw. Ela responde se os
            `CodigoPronunciamento` que a auditoria anterior encontrou possuem
            texto oficial disponível. Itens sem texto ficam registrados como
            limitação da fonte, e não como uma falsa recuperação concluída.
            """
        ),
        code(
            """
            if RODAR_AUDITORIA_CONGRESSO:
                confirmed()
                report = congress_text_inventory()
                path = write_operation_json("congresso_2010_text_inventory.json", report)
                display(report)
                print("Auditado:", path)
            else:
                print("Auditoria CN/2010 protegida.")
            """,
            "audit_congresso",
        ),
        markdown(
            """
            ## Coletar Câmara em 2010

            A coleta é anual, retomável e usa somente identificadores oficiais:
            primeiro os períodos de mandato processados, se disponíveis; caso
            contrário, a própria lista oficial de deputados da API para 2010.
            Nenhum nome é usado como chave. Em caso de falha, execute a mesma
            célula novamente: o ano permanece marcado como falho até terminar
            sem erros.
            """
        ),
        code(
            """
            if RODAR_CAMARA_2010:
                confirmed()
                returncode = run_command(camara_command())
                assert returncode == 0, (
                    "A coleta preservou o progresso. Reexecute esta mesma célula com o mesmo "
                    "CAMARA_RUN_ID até o manifest ficar completed sem erros."
                )
                manifest, report = assert_camara_complete()
                path = write_operation_json("camara_2010_raw_inventory.json", report)
                display(report)
                print("Coleta aceita:", path)
            else:
                print("Coleta Câmara/2010 protegida.")
            """,
            "collect_camara",
        ),
        markdown(
            """
            ## Gate antes dos derivados

            Quando ambos os relatórios estiverem aprovados, abra a versão
            atualizada do caderno 07. Ela reconstruirá processed/Parquet e só
            aceitará o snapshot se Câmara, Senado e Congresso tiverem cobertura
            em 2010, 2015 e 2016.
            """
        ),
        code(
            """
            if VALIDAR_RECUPERACAO:
                confirmed()
                congress = congress_text_inventory()
                _, camara = assert_camara_complete()
                summary_path = write_operation_json("summary.json", {
                    "congresso_2010": congress,
                    "camara_2010": camara,
                    "next_notebook": "notebooks/processamento/07_derivados_backfill_discursos_senadores_por_codigo_colab.ipynb",
                })
                display({"congresso_2010": congress, "camara_2010": camara})
                print("Gate aprovado:", summary_path)
            else:
                print("Validação protegida.")
            """,
            "validate",
        ),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.update(
        {
            "colab": {"name": OUTPUT.name, "provenance": []},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        }
    )
    for index, cell in enumerate(notebook.cells):
        stable = f"{OUTPUT.relative_to(ROOT)}:{index}:{cell.cell_type}:{cell.source}".encode("utf-8")
        cell["id"] = sha256(stable).hexdigest()[:16]
    nbformat.validate(notebook)
    return notebook


def render() -> str:
    return nbformat.writes(build_notebook()) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
    if args.check:
        if current != content:
            raise SystemExit(f"Notebook fora de sincronia: {OUTPUT}")
        return
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
