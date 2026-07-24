from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest

from coleta.common.http import HttpResult
from coleta.senado import discursos
from coleta.senado.auditoria_discursos_historicos import extract_pronunciamento_codes
from coleta.senado.discursos_historicos import (
    discover_portal_pronunciamentos,
    extract_portal_authors,
    extract_portal_pronunciamentos,
    merge_primary_and_portal,
)
from processamento.reconciliacao_discursos import (
    LAYERS,
    TARGETS,
    build_camara_control,
    build_reconciliation,
    camara_control_gates,
    reconcile_discursos,
    reconciliation_gates,
)


INDEX_HTML = """
<table><tr><th>Autor</th><th>Quantidade</th></tr>
<tr><td><a href="/web/atividade/pronunciamentos?p_p_id=pronunciamentos_WAR_atividadeportlet&amp;_pronunciamentos_WAR_atividadeportlet_autor=1&amp;_pronunciamentos_WAR_atividadeportlet_nomeAutor=MARIA">Maria da Silva</a></td><td>2</td></tr>
</table>
"""


def _results_html(*, code: str, day: str, house: str, next_page: bool = False) -> str:
    pagination = (
        '<a href="https://www25.senado.leg.br/web/atividade/pronunciamentos?'
        '_pronunciamentos_WAR_atividadeportlet_p=2">Última</a>'
        if next_page
        else ""
    )
    return f"""
    <p>Total de 2 registros encontrados</p>
    <table><tr><th>Data</th><th>Casa</th><th>Partido/UF</th><th>Resumo</th></tr>
    <tr><td><a href="/web/atividade/pronunciamentos/-/p/pronunciamento/{code}">{day}</a></td>
    <td>{house}</td><td>PT/RS</td><td>Resumo oficial.</td></tr></table>{pagination}
    """


class _PortalClient:
    def __enter__(self) -> "_PortalClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_text(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
        if path == "web/atividade/pronunciamentos":
            assert params == {
                "p_p_id": "pronunciamentos_WAR_atividadeportlet",
                "p_p_lifecycle": 0,
                "p_p_state": "normal",
                "p_p_mode": "view",
                "p_p_col_id": "column-1",
                "p_p_col_count": 1,
                "total": 1,
                "dataInicial": "01/03/2015",
                "dataFinal": "31/03/2015",
            }
            return HttpResult("https://www25.senado.leg.br/web/atividade/pronunciamentos", 200, {}, INDEX_HTML)
        page = parse_qs(urlsplit(path).query).get("_pronunciamentos_WAR_atividadeportlet_p", ["1"])[0]
        if page == "2":
            return HttpResult(path, 200, {}, _results_html(code="411219", day="31/03/2015", house="Congresso Nacional"))
        return HttpResult(path, 200, {}, _results_html(code="414849", day="30/03/2015", house="Senado Federal", next_page=True))


class _ApiClient:
    def __enter__(self) -> "_ApiClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_json(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
        assert params == {"siglaCasa": "SF", "v": 4}
        return HttpResult(f"https://legis.senado.leg.br/{path}", 200, {}, {"DiscursosSessao": {"Sessoes": None}})

    def get_text(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
        assert path.endswith("/414849")
        return HttpResult(f"https://legis.senado.leg.br/{path}", 200, {}, "Texto oficial recuperado")


def test_portal_parser_extracts_authors_house_date_and_provenance() -> None:
    authors = extract_portal_authors(INDEX_HTML)
    assert [(author.name, author.expected_count) for author in authors] == [("Maria da Silva", 2)]

    items = extract_portal_pronunciamentos(
        _results_html(code="414849", day="30/03/2015", house="Senado Federal"),
        page_url="https://www25.senado.leg.br/resultado",
        author="Maria da Silva",
        author_url=authors[0].url,
    )
    assert items[0]["codigo_pronunciamento"] == "414849"
    assert items[0]["metadata"]["sessao"]["SiglaCasa"] == "SF"
    assert items[0]["metadata"]["pronunciamento"]["Data"] == "2015-03-30"
    assert items[0]["fontes"]["portal_detalhe"].endswith("/pronunciamento/414849")


def test_senator_endpoint_probe_extracts_codes_from_nested_payload() -> None:
    payload = {
        "DiscursosParlamentar": {
            "Parlamentar": {
                "Pronunciamentos": {
                    "Pronunciamento": [
                        {"CodigoPronunciamento": 414849},
                        {"CodigoPronunciamento": "422757"},
                    ]
                }
            }
        }
    }
    assert extract_pronunciamento_codes(payload) == ["414849", "422757"]


def test_portal_discovery_follows_all_pages_and_reconciles_houses() -> None:
    discovery = discover_portal_pronunciamentos(
        _PortalClient(), start=date(2015, 3, 1), end=date(2015, 3, 31)
    )
    assert discovery.expected_count == 2
    assert discovery.discovered_count == 2
    assert len(discovery.pages) == 3
    assert {item["codigo_pronunciamento"] for item in discovery.items} == {"414849", "411219"}

    senate, senate_audit = merge_primary_and_portal([], list(discovery.items), sigla_casa="SF", require_parity=True)
    congress, congress_audit = merge_primary_and_portal([], list(discovery.items), sigla_casa="CN", require_parity=True)
    assert [item["codigo_pronunciamento"] for item in senate] == ["414849"]
    assert [item["codigo_pronunciamento"] for item in congress] == ["411219"]
    assert senate_audit["primary_empty_portal_nonempty"]
    assert congress_audit["primary_empty_portal_nonempty"]


def test_portal_discovery_probes_page_after_legacy_paginator_repeats_first_page() -> None:
    index_html = INDEX_HTML.replace(">2</td>", ">3</td>")

    def results_html(codes: list[str], *, total: int = 3, max_page: int | None = None) -> str:
        rows = "".join(
            f'<tr><td><a href="/web/atividade/pronunciamentos/-/p/pronunciamento/{code}">'
            f'30/03/2015</a></td><td>Senado Federal</td><td>PT/RS</td><td>Resumo.</td></tr>'
            for code in codes
        )
        pagination = (
            '<a href="https://www25.senado.leg.br/web/atividade/pronunciamentos?'
            f'_pronunciamentos_WAR_atividadeportlet_p={max_page}">Última</a>'
            if max_page is not None
            else ""
        )
        return f"<p>Total de {total} registros encontrados</p><table>{rows}</table>{pagination}"

    class RepeatingFirstPageClient:
        def get_text(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
            if path == "web/atividade/pronunciamentos":
                return HttpResult("https://www25.senado.leg.br/web/atividade/pronunciamentos", 200, {}, index_html)
            page = parse_qs(urlsplit(path).query).get("_pronunciamentos_WAR_atividadeportlet_p", ["1"])[0]
            if page == "3":
                return HttpResult(path, 200, {}, results_html(["414850", "414851"]))
            return HttpResult(path, 200, {}, results_html(["414849"], max_page=2))

    discovery = discover_portal_pronunciamentos(
        RepeatingFirstPageClient(), start=date(2015, 3, 1), end=date(2015, 3, 31)
    )

    assert discovery.expected_count == 3
    assert discovery.discovered_count == 3
    assert discovery.duplicate_count == 1
    assert [page.page for page in discovery.pages] == [1, 1, 2, 3]


def test_historical_parity_rejects_primary_identifier_missing_from_portal() -> None:
    with pytest.raises(ValueError, match="nao reproduziu"):
        merge_primary_and_portal(
            [{"codigo_pronunciamento": "999", "metadata": {}, "fontes": {}}],
            [],
            sigla_casa="SF",
            require_parity=True,
        )


def test_out_of_scope_house_is_excluded_and_audited() -> None:
    items = extract_portal_pronunciamentos(
        _results_html(code="500000", day="30/03/2015", house="Câmara dos Deputados"),
        page_url="https://www25.senado.leg.br/resultado",
        author="Deputada Exemplo",
        author_url="https://www25.senado.leg.br/autora",
    )
    merged, audit = merge_primary_and_portal([], items, sigla_casa="SF", require_parity=True)
    assert merged == []
    assert audit["portal_other_houses"] == {"CD": 1}


def test_portal_discovery_rejects_malformed_empty_response() -> None:
    class MalformedClient:
        def get_text(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
            return HttpResult("https://www25.senado.leg.br/web/atividade/pronunciamentos", 200, {}, "<html><body>formulário</body></html>")

    with pytest.raises(ValueError, match="sem autores"):
        discover_portal_pronunciamentos(
            MalformedClient(), start=date(2015, 3, 1), end=date(2015, 3, 31)
        )


def test_portal_discovery_accepts_explicit_empty_result() -> None:
    class EmptyClient:
        def get_text(self, path: str, *, params: dict[str, object] | None = None) -> HttpResult:
            return HttpResult(
                "https://www25.senado.leg.br/web/atividade/pronunciamentos",
                200,
                {},
                '<div class="alert alert-warning">Nenhum pronunciamento encontrado!</div>',
            )

    discovery = discover_portal_pronunciamentos(
        EmptyClient(), start=date(1900, 1, 1), end=date(1900, 1, 31)
    )
    assert discovery.expected_count == 0
    assert discovery.items == ()


def test_shared_collector_archives_historical_discovery_and_marks_source_anomaly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def client_factory(base_url: str, **_: object) -> object:
        return _PortalClient() if "www25.senado" in base_url else _ApiClient()

    monkeypatch.setattr(discursos, "OpenDataClient", client_factory)
    manifest_path = discursos.collect_discursos(
        dataset="plenario_discursos",
        sigla_casa="SF",
        description="teste",
        argv=[
            "--mode",
            "dev",
            "--output-dir",
            str(tmp_path),
            "--data-inicio",
            "2015-03-01",
            "--data-fim",
            "2015-03-31",
            "--run-id",
            "historical-test",
            "--discovery-strategy",
            "historical-official",
        ],
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["discovery_strategy"] == "historical-official"
    assert manifest["source_anomaly_partitions"] == ["2015-03"]
    metadata_path = tmp_path / "raw" / "senado" / "plenario_discursos" / "metadata" / "historical-test.jsonl"
    metadata = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    assert any(record["record_type"] == "discursos_portal_page" for record in metadata)
    summary = next(record for record in metadata if record["record_type"] == "discursos_historical_discovery")
    assert summary["payload"]["ids"] == ["414849"]
    corpus_path = (
        tmp_path
        / "raw"
        / "senado"
        / "plenario_discursos"
        / "ano=2015"
        / "mes=03"
        / "historical-test.jsonl"
    )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    assert corpus["source_id"] == "SF:pronunciamento:414849"
    assert corpus["payload"]["texto"] == "Texto oficial recuperado"


def test_reconciliation_classifies_each_loss_and_requires_sentinels() -> None:
    layers = {layer: {dataset: {} for dataset in TARGETS} for layer in LAYERS}
    text_id = "senado:plenario_discursos:pronunciamento:414849"
    row = {"texto_id": text_id, "data": "2015-06-01", "ano": 2015, "mes": 6}
    for layer in ("discovered", "raw", "raw_text", "processed"):
        layers[layer]["plenario_discursos"][text_id] = row

    reconciliation = build_reconciliation(layers)
    assert reconciliation.loc[0, "status"] == "parquet_loss"
    gates = reconciliation_gates(reconciliation, snapshot_required=False)
    assert gates["processed_equals_parquet"] is False
    assert gates["sentinels"] is False


def test_camara_control_requires_both_target_years_unique_ids_and_text(tmp_path: Path) -> None:
    parquet_path = (
        tmp_path
        / "processed"
        / "textos_parlamentares"
        / "v1"
        / "parquet"
        / "camara__plenario_discursos.parquet"
    )
    parquet_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "texto_id": "camara:2015",
                "data": "2015-06-01",
                "texto": "Ação e Constituição em 2015.",
                "parlamentar_nome": "Conceição Sampaio",
            },
            {
                "texto_id": "camara:2016",
                "data": "2016-06-01",
                "texto": "Cidadãs e cidadãos em 2016.",
                "parlamentar_nome": "Conceição Sampaio",
            },
        ]
    ).to_parquet(parquet_path, index=False)

    control = build_camara_control(tmp_path, phase="pre")

    assert control.set_index("ano")["rows"].to_dict() == {2015: 1, 2016: 1}
    assert all(camara_control_gates(control).values())


def test_reconciliation_writes_required_artifacts_and_passes_complete_chain(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    speeches = {
        "plenario_discursos": [("414849", "2015-06-01"), ("422757", "2016-06-01")],
        "congresso_discursos": [("411219", "2015-07-01"), ("426642", "2016-07-01")],
    }
    processed_rows: list[dict[str, object]] = []
    snapshot_rows: list[dict[str, object]] = []
    for dataset, items in speeches.items():
        target = TARGETS[dataset]
        metadata_path = data_root / "raw" / "senado" / dataset / "metadata" / "historical.jsonl"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        discovery_items = [
            {
                "codigo_pronunciamento": code,
                "metadata": {
                    "sessao": {"SiglaCasa": target["house"], "DataSessao": day},
                    "pronunciamento": {"CodigoPronunciamento": code, "Data": day},
                },
            }
            for code, day in items
        ]
        metadata_path.write_text(
            json.dumps(
                {
                    "record_type": "discursos_historical_discovery",
                    "source": "senado",
                    "dataset": dataset,
                    "payload": {"house": target["house"], "partition": "target", "items": discovery_items},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        for code, day in items:
            raw_path = (
                data_root
                / "raw"
                / "senado"
                / dataset
                / f"ano={day[:4]}"
                / f"mes={day[5:7]}"
                / "historical.jsonl"
            )
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with raw_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "record_type": "pronunciamento_texto",
                            "run_id": "historical",
                            "payload": {
                                "CodigoPronunciamento": code,
                                "codigo_pronunciamento": code,
                                "texto": f"Texto {code}",
                                "texto_status": "disponivel",
                                "metodo_obtencao": "api_texto_integral",
                                "metadata": {
                                    "sessao": {"SiglaCasa": target["house"], "DataSessao": day},
                                    "pronunciamento": {"CodigoPronunciamento": code, "Data": day},
                                },
                            },
                        }
                    )
                    + "\n"
                )
            text_id = f"senado:{dataset}:pronunciamento:{code}"
            processed_rows.append(
                {
                    "texto_id": text_id,
                    "source": "senado",
                    "dataset": dataset,
                    "pronunciamento_id": code,
                    "data": day,
                    "texto": f"Texto {code}",
                }
            )
            snapshot_rows.append(
                {"texto_id": text_id, "arena": target["arena"], "data": day, "data_analise": day}
            )

    processed_path = data_root / "processed" / "textos_parlamentares" / "v1" / "ano=2015" / "mes=01" / "current.jsonl"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(
        "".join(json.dumps(row) + "\n" for row in processed_rows), encoding="utf-8"
    )
    parquet_root = data_root / "processed" / "textos_parlamentares" / "v1" / "parquet"
    parquet_root.mkdir(parents=True)
    for dataset in TARGETS:
        pd.DataFrame([row for row in processed_rows if row["dataset"] == dataset]).to_parquet(
            parquet_root / f"senado__{dataset}.parquet", index=False
        )
    camara_rows = [
        {
            "texto_id": f"camara:plenario_discursos:discurso:{year}",
            "source": "camara",
            "dataset": "plenario_discursos",
            "data": f"{year}-06-01",
            "texto": f"Ação da Câmara em {year}",
            "parlamentar_nome": "Conceição Sampaio",
        }
        for year in (2015, 2016)
    ]
    pd.DataFrame(camara_rows).to_parquet(
        parquet_root / "camara__plenario_discursos.parquet", index=False
    )
    snapshot_rows.extend(
        {
            "texto_id": row["texto_id"],
            "arena": "camara",
            "data": row["data"],
            "data_analise": row["data"],
        }
        for row in camara_rows
    )
    snapshot_path = data_root / "analises" / "run" / "00_snapshot" / "discursos_plenario_snapshot.parquet"
    snapshot_path.parent.mkdir(parents=True)
    pd.DataFrame(snapshot_rows).to_parquet(snapshot_path, index=False)

    cycle_dir = data_root / "operations" / "cycle"
    reconcile_discursos(
        data_root=data_root,
        cycle_dir=cycle_dir,
        phase="pre",
        snapshot_path=None,
        strict=False,
    )
    result = reconcile_discursos(
        data_root=data_root,
        cycle_dir=cycle_dir,
        phase="post",
        snapshot_path=snapshot_path,
        strict=True,
    )
    assert result["passed"] is True
    for filename in (
        "coverage_pre.csv",
        "inventory_pre.json",
        "coverage_post.csv",
        "camara_control_pre.csv",
        "camara_control_post.csv",
        "inventory_post.json",
        "reconciliation_ids.parquet",
        "source_probes.jsonl",
        "source_conflicts.jsonl",
        "summary.json",
    ):
        assert (cycle_dir / filename).exists()
