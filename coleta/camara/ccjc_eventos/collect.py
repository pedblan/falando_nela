from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

import httpx

from coleta.common.cli import build_parser, parse_runtime_args
from coleta.common.config import apply_sample_window, month_windows
from coleta.common.documents import decode_text, sha256_bytes
from coleta.common.http import OpenDataClient, iter_camara_pages
from coleta.common.io import CollectionRun, error_summary

SOURCE = "camara"
DATASET = "ccjc_eventos"
CCJC_ORGAO_ID = 2003
BASE_URL = "https://dadosabertos.camara.leg.br/"
ESCRIBA_HTML_URL = "https://escriba.camara.leg.br/escriba-servicosweb/html/{event_id}"
ESCRIBA_PDF_URL = "https://escriba.camara.leg.br/escriba-servicosweb/pdf/{event_id}?isTaquigrafia=false"
ESCRIBA_TEXT_START = date(2019, 1, 1)


def collect() -> None:
    parser = build_parser("Coleta eventos, participantes e notas taquigraficas da CCJC da Camara.")
    runtime = parse_runtime_args(parser)
    run = CollectionRun(
        runtime.output_dir,
        source=SOURCE,
        dataset=DATASET,
        run_id=runtime.run_id,
        resume=runtime.resume,
    )
    windows = apply_sample_window(list(month_windows(runtime.data_inicio, runtime.data_fim)), runtime.sample)
    processed_events = 0
    escriba_status_records = 0
    notas_disponiveis = 0
    status = "completed"
    errors = 0

    try:
        with OpenDataClient(BASE_URL) as client:
            for partition, start, end in windows:
                if runtime.sample_limit is not None and processed_events >= runtime.sample_limit:
                    break
                if run.should_skip_partition(partition):
                    run.log("partition_skipped", partition=partition)
                    continue

                periodo = {"data_inicio": start.isoformat(), "data_fim": end.isoformat()}
                try:
                    remaining = None
                    if runtime.sample_limit is not None:
                        remaining = runtime.sample_limit - processed_events
                    run.log("partition_started", partition=partition, periodo=periodo)
                    events = _collect_event_pages(
                        client,
                        run,
                        partition,
                        periodo,
                        sample=runtime.sample,
                        sample_limit=remaining,
                    )
                    for event in events:
                        event_id = _event_id(event)
                        if event_id is None:
                            run.log("event_without_id", partition=partition, event=event)
                            continue
                        try:
                            detail_payload = _collect_event_detail(client, run, periodo, event_id)
                            event_context = _event_from_detail(detail_payload) or event
                            _collect_event_deputados(client, run, periodo, event_id)
                            stats = _collect_event_escriba(client, run, partition, periodo, event_context)
                            escriba_status_records += stats["status_records"]
                            notas_disponiveis += stats["notas_disponiveis"]
                        except Exception as exc:
                            errors += 1
                            status = "completed_with_errors"
                            run.log("event_failed", event_id=event_id, error=error_summary(exc))
                            continue
                        processed_events += 1

                    run.mark_partition_complete(
                        partition,
                        periodo=periodo,
                        eventos=len(events),
                        eventos_processados=processed_events,
                        escriba_status_records=escriba_status_records,
                        notas_taquigraficas=notas_disponiveis,
                    )
                    run.log(
                        "partition_completed",
                        partition=partition,
                        eventos=len(events),
                        eventos_processados=processed_events,
                        escriba_status_records=escriba_status_records,
                        notas_taquigraficas=notas_disponiveis,
                    )
                except Exception as exc:
                    errors += 1
                    status = "completed_with_errors"
                    run.mark_partition_failed(partition, periodo=periodo, error=error_summary(exc, include_traceback=True))
                    run.log("partition_failed", partition=partition, error=error_summary(exc))
                    continue
    except Exception as exc:
        errors += 1
        status = "failed"
        run.log("run_failed", error=error_summary(exc, include_traceback=True))
    finally:
        run.write_manifest(
            data_inicio=runtime.data_inicio.isoformat(),
            data_fim=runtime.data_fim.isoformat(),
            mode=runtime.mode,
            sample=runtime.sample,
            sample_limit=runtime.sample_limit,
            ccjc_orgao_id=CCJC_ORGAO_ID,
            escriba_text_start=ESCRIBA_TEXT_START.isoformat(),
            eventos_processados=processed_events,
            escriba_status_records=escriba_status_records,
            notas_taquigraficas=notas_disponiveis,
            status=status,
            errors=errors,
        )
        print(run.manifest_path)


def _collect_event_pages(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    *,
    sample: bool,
    sample_limit: int | None,
) -> list[dict[str, Any]]:
    path = f"api/v2/orgaos/{CCJC_ORGAO_ID}/eventos"
    params = {
        "dataInicio": periodo["data_inicio"],
        "dataFim": periodo["data_fim"],
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "dataHoraInicio",
    }
    events: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    limit = sample_limit if sample_limit is not None else 3 if sample else None

    for page_index, result in enumerate(iter_camara_pages(client, path, params=params), start=1):
        run.write_record(
            partition="metadata",
            source_id=f"ccjc:eventos:{partition}:pagina:{page_index}",
            request={"method": "GET", "path": path, "params": params},
            response=result.response_metadata,
            periodo=periodo,
            payload=result.data,
            record_type="eventos_page",
        )
        for event in _dados(result.data):
            event_id = event.get("id")
            if not isinstance(event_id, int) or event_id in seen_ids:
                continue
            events.append(event)
            seen_ids.add(event_id)
            if limit is not None and len(events) >= limit:
                return events
    return events


def _collect_event_detail(
    client: OpenDataClient,
    run: CollectionRun,
    periodo: dict[str, str],
    event_id: int,
) -> dict[str, Any] | None:
    path = f"api/v2/eventos/{event_id}"
    source_id = f"ccjc:evento:{event_id}:detalhe"
    if run.has_record(source_id=source_id, record_type="evento_detalhe"):
        run.log("record_resume_skipped", source_id=source_id, record_type="evento_detalhe")
        return None
    try:
        result = client.get_json(path)
    except httpx.HTTPStatusError as exc:
        run.log("event_detail_failed", event_id=event_id, status_code=exc.response.status_code)
        return None

    run.write_record(
        partition="metadata",
        source_id=source_id,
        request={"method": "GET", "path": path, "params": {}},
        response=result.response_metadata,
        periodo=periodo,
        payload=result.data,
        record_type="evento_detalhe",
    )
    return result.data if isinstance(result.data, dict) else None


def _collect_event_deputados(
    client: OpenDataClient,
    run: CollectionRun,
    periodo: dict[str, str],
    event_id: int,
) -> None:
    path = f"api/v2/eventos/{event_id}/deputados"
    try:
        pages = iter_camara_pages(client, path)
        for page_index, result in enumerate(pages, start=1):
            source_id = f"ccjc:evento:{event_id}:deputados:pagina:{page_index}"
            run.write_record(
                partition="metadata",
                source_id=source_id,
                request={"method": "GET", "path": path, "params": {}},
                response=result.response_metadata,
                periodo=periodo,
                payload=result.data,
                record_type="evento_deputados_page",
            )
    except httpx.HTTPStatusError as exc:
        run.log("event_deputies_failed", event_id=event_id, status_code=exc.response.status_code)
        return


def _collect_event_escriba(
    client: OpenDataClient,
    run: CollectionRun,
    partition: str,
    periodo: dict[str, str],
    event: dict[str, Any],
) -> dict[str, int]:
    event_id = _event_id(event)
    if event_id is None:
        return {"status_records": 0, "notas_disponiveis": 0}

    status_source_id = f"ccjc:evento:{event_id}:escriba_status"
    html_source_id = f"ccjc:evento:{event_id}:escriba_html"
    notes_source_id = f"ccjc:evento:{event_id}:notas_taquigraficas"
    if run.has_record(source_id=status_source_id, record_type="escriba_status"):
        run.log("record_resume_skipped", source_id=status_source_id, record_type="escriba_status")
        return {"status_records": 0, "notas_disponiveis": 0}

    fontes = build_fontes_evento(event_id, event)
    event_date = _event_date(event)
    request = {"method": "GET", "path": fontes["escriba_html"], "params": {}}
    if event_date is not None and event_date < ESCRIBA_TEXT_START:
        payload = build_escriba_status_payload(
            event_id,
            event,
            texto_status="fora_escopo",
            motivo="antes_de_2019",
            fontes=fontes,
        )
        written = run.write_record(
            partition="metadata",
            source_id=status_source_id,
            request=request,
            response={"url": fontes["escriba_html"], "status_code": None, "headers": {}},
            periodo=periodo,
            payload=payload,
            record_type="escriba_status",
        )
        return {"status_records": int(written), "notas_disponiveis": 0}

    try:
        result = client.get_bytes(fontes["escriba_html"])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        response = payload_response(exc)
        payload = build_escriba_status_payload(
            event_id,
            event,
            texto_status="ausente",
            motivo="escriba_404",
            fontes=fontes,
        )
        written = run.write_record(
            partition="metadata",
            source_id=status_source_id,
            request=request,
            response=response,
            periodo=periodo,
            payload=payload,
            record_type="escriba_status",
        )
        run.log("escriba_notes_absent", event_id=event_id, status_code=404)
        return {"status_records": int(written), "notas_disponiveis": 0}

    content = result.data if isinstance(result.data, bytes) else b""
    html = decode_text(content)
    parsed = parse_escriba_html(html, event=event, url=result.url)
    html_written = run.write_record(
        partition="metadata",
        source_id=html_source_id,
        request=request,
        response=result.response_metadata,
        periodo=periodo,
        payload={
            "evento_id": event_id,
            "url": result.url,
            "content_type": result.headers.get("content-type"),
            "tamanho_bytes": len(content),
            "sha256": sha256_bytes(content),
            "html": html,
        },
        record_type="escriba_html",
    )

    notes_written = False
    if parsed["texto_status"] == "disponivel":
        notes_written = run.write_record(
            partition=partition,
            source_id=notes_source_id,
            request=request,
            response=result.response_metadata,
            periodo=periodo,
            payload=parsed,
            record_type="notas_taquigraficas",
        )
    else:
        run.log("escriba_notes_without_text", event_id=event_id, source_id=notes_source_id)

    status_payload = build_escriba_status_payload(
        event_id,
        event,
        texto_status=parsed["texto_status"],
        motivo="disponivel" if parsed["texto_status"] == "disponivel" else "html_sem_nota_valida",
        fontes=parsed["fontes"],
        cabecalho=parsed["metadata"].get("cabecalho"),
        segmentos=len(parsed.get("segmentos", [])),
    )
    status_written = run.write_record(
        partition="metadata",
        source_id=status_source_id,
        request=request,
        response=result.response_metadata,
        periodo=periodo,
        payload=status_payload,
        record_type="escriba_status",
    )
    return {
        "status_records": int(status_written),
        "notas_disponiveis": int(notes_written),
        "html_records": int(html_written),
    }


def parse_escriba_html(html: str, *, event: dict[str, Any] | None = None, url: str | None = None) -> dict[str, Any]:
    root = parse_html_tree(html)
    event = event or {}
    event_id = _event_id(event)
    fontes = build_fontes_evento(event_id, event, html_url=url) if event_id is not None else {"escriba_html": url}
    cabecalho = parse_header(root)
    quartos: list[dict[str, Any]] = []
    segmentos: list[dict[str, Any]] = []
    audios: list[str] = []
    videos: list[str] = []
    table = _first_node(root, lambda node: node.tag == "table" and node.attrs.get("id") == "tabelaQuartos")
    rows = _find_all(table, lambda node: node.tag == "tr") if table else []

    for row in rows:
        cells = _children(row, tag="td")
        hora_cell = next((cell for cell in cells if _has_class(cell, "hora")), None)
        text_cell = next((cell for cell in cells if _has_class(cell, "justificado")), None)
        horario = extract_horario(hora_cell)
        status_revisao = extract_status_revisao(hora_cell)
        row_audios = extract_audio_urls(hora_cell)
        row_videos = extract_video_refs(hora_cell)
        audios.extend(url for url in row_audios if url not in audios)
        videos.extend(video for video in row_videos if video not in videos)
        quarto_segmentos: list[dict[str, Any]] = []

        if text_cell is not None:
            for segment_node in _find_all(text_cell, is_segment_node):
                text = _text_content(segment_node)
                if not text:
                    continue
                speaker = extract_speaker(segment_node)
                segment = {
                    "ordem": len(segmentos) + 1,
                    "id_segmento": extract_anchor_name(segment_node),
                    "horario": horario,
                    "tipo": segment_type(segment_node),
                    "orador": speaker,
                    "texto": text,
                }
                segmentos.append(segment)
                quarto_segmentos.append(segment)

        if horario or quarto_segmentos:
            quartos.append(
                {
                    "ordem": len(quartos) + 1,
                    "id_quarto": row.attrs.get("id"),
                    "horario": horario,
                    "status_revisao": status_revisao,
                    "fontes": {"audios": row_audios, "videos": row_videos},
                    "segmentos": quarto_segmentos,
                }
            )

    fontes["audios"] = audios
    fontes["videos"] = videos
    texto = "\n\n".join(segment["texto"] for segment in segmentos).strip()
    return {
        "CodigoEvento": event_id,
        "evento_id": event_id,
        "TextoIntegral": texto or None,
        "texto": texto or None,
        "forma": "texto" if texto else "sem_texto",
        "metodo_obtencao": "scraping_escriba_html",
        "texto_status": "disponivel" if texto else "ausente",
        "metadata": {
            "evento": event,
            "cabecalho": cabecalho,
        },
        "fontes": fontes,
        "quartos": quartos,
        "segmentos": segmentos,
    }


def build_escriba_status_payload(
    event_id: int,
    event: dict[str, Any],
    *,
    texto_status: str,
    motivo: str,
    fontes: dict[str, Any],
    cabecalho: dict[str, Any] | None = None,
    segmentos: int = 0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "evento_id": event_id,
        "texto_status": texto_status,
        "motivo": motivo,
        "escopo_textual_inicio": ESCRIBA_TEXT_START.isoformat(),
        "metadata": {"evento": event},
        "fontes": fontes,
    }
    if cabecalho:
        payload["metadata"]["cabecalho"] = cabecalho
    if segmentos:
        payload["segmentos"] = segmentos
    return payload


def build_fontes_evento(
    event_id: int,
    event: dict[str, Any],
    *,
    html_url: str | None = None,
) -> dict[str, Any]:
    fontes: dict[str, Any] = {
        "evento_api": BASE_URL + f"api/v2/eventos/{event_id}",
        "evento_deputados_api": BASE_URL + f"api/v2/eventos/{event_id}/deputados",
        "escriba_html": html_url or ESCRIBA_HTML_URL.format(event_id=event_id),
        "escriba_pdf": ESCRIBA_PDF_URL.format(event_id=event_id),
    }
    url_registro = event.get("urlRegistro")
    if isinstance(url_registro, str) and url_registro.strip():
        fontes["urlRegistro"] = url_registro
    return fontes


def parse_header(root: "HtmlNode") -> dict[str, Any]:
    title = _first_node(root, lambda node: node.tag == "div" and _has_class(node, "contentTitle"))
    if title is None:
        return {"texto": "", "linhas": []}
    lines = [_collapse_spaces(fragment) for fragment in _text_fragments(title) if _collapse_spaces(fragment)]
    return {
        "texto": _collapse_spaces(" ".join(lines)),
        "linhas": lines,
    }


def extract_horario(node: "HtmlNode | None") -> str | None:
    if node is None:
        return None
    match = re.search(r"\b\d{1,2}:\d{2}\b", _text_content(node))
    return match.group(0) if match else None


def extract_status_revisao(node: "HtmlNode | None") -> dict[str, str] | None:
    if node is None:
        return None
    status = _first_node(node, lambda child: child.tag == "span" and bool(child.attrs.get("title")))
    if status is None:
        return None
    return {
        "sigla": _text_content(status),
        "descricao": status.attrs.get("title", ""),
    }


def extract_audio_urls(node: "HtmlNode | None") -> list[str]:
    if node is None:
        return []
    urls: list[str] = []
    for anchor in _find_all(node, lambda child: child.tag == "a"):
        href = anchor.attrs.get("href", "")
        match = re.search(r"abreAudio\(['\"]([^'\"]+)['\"]\)", href)
        if match and match.group(1) not in urls:
            urls.append(match.group(1))
    return urls


def extract_video_refs(node: "HtmlNode | None") -> list[str]:
    if node is None:
        return []
    refs: list[str] = []
    for anchor in _find_all(node, lambda child: child.tag == "a"):
        ref = anchor.attrs.get("urlvideo")
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def extract_anchor_name(node: "HtmlNode") -> str | None:
    anchor = _first_node(node, lambda child: child.tag == "a" and bool(child.attrs.get("name")))
    return anchor.attrs.get("name") if anchor is not None else None


def extract_speaker(node: "HtmlNode") -> dict[str, Any] | None:
    bold = _first_node(node, lambda child: child.tag == "b")
    if bold is None:
        return None
    link = _first_node(bold, lambda child: child.tag == "a" and bool(child.attrs.get("href")))
    speaker: dict[str, Any] = {"nome": _text_content(bold)}
    if link is not None:
        href = link.attrs.get("href")
        speaker["url"] = href
        match = re.search(r"[?&]id=(\d+)", href or "")
        if match:
            speaker["id_deputado"] = int(match.group(1))
    return speaker


def is_segment_node(node: "HtmlNode") -> bool:
    classes = set(_classes(node))
    return bool(
        classes
        & {
            "principalStyle",
            "intercorrenciaMesmoSegmentoStyle",
            "intercorrenciaCentralizadoStyle",
        }
    )


def segment_type(node: "HtmlNode") -> str:
    if _has_class(node, "principalStyle"):
        return "fala"
    return "intercorrencia"


def _dados(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("dados", []) if isinstance(item, dict)]


def _event_id(event: dict[str, Any]) -> int | None:
    event_id = event.get("id")
    return event_id if isinstance(event_id, int) else None


def _event_from_detail(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    event = payload.get("dados")
    return event if isinstance(event, dict) else None


def _event_date(event: dict[str, Any]) -> date | None:
    value = event.get("dataHoraInicio")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def payload_response(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    return {
        "url": str(exc.request.url),
        "status_code": exc.response.status_code,
        "headers": {
            key: value
            for key, value in exc.response.headers.items()
            if key.lower()
            in {
                "content-disposition",
                "content-length",
                "content-type",
                "date",
                "link",
                "location",
                "retry-after",
                "x-total-count",
            }
        },
    }


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Any] = field(default_factory=list)
    parent: "HtmlNode | None" = None


class _TreeBuilder(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("document")
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        node = HtmlNode(
            normalized,
            {key.lower(): value or "" for key, value in attrs},
            parent=self.current,
        )
        self.current.children.append(node)
        if normalized not in self.VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(
            tag.lower(),
            {key.lower(): value or "" for key, value in attrs},
            parent=self.current,
        )
        self.current.children.append(node)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        node = self.current
        while node.parent is not None and node.tag != normalized:
            node = node.parent
        if node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.current.children.append(data)


def parse_html_tree(html: str) -> HtmlNode:
    parser = _TreeBuilder()
    parser.feed(html)
    return parser.root


def _find_all(node: HtmlNode | None, predicate: Any) -> list[HtmlNode]:
    if node is None:
        return []
    matches: list[HtmlNode] = []
    for child in node.children:
        if not isinstance(child, HtmlNode):
            continue
        if predicate(child):
            matches.append(child)
        matches.extend(_find_all(child, predicate))
    return matches


def _first_node(node: HtmlNode | None, predicate: Any) -> HtmlNode | None:
    for child in _find_all(node, predicate):
        return child
    return None


def _children(node: HtmlNode, *, tag: str | None = None) -> list[HtmlNode]:
    return [
        child
        for child in node.children
        if isinstance(child, HtmlNode) and (tag is None or child.tag == tag)
    ]


def _classes(node: HtmlNode) -> list[str]:
    return node.attrs.get("class", "").split()


def _has_class(node: HtmlNode, class_name: str) -> bool:
    return class_name in _classes(node)


def _text_content(node: HtmlNode | None) -> str:
    if node is None:
        return ""
    return _collapse_spaces(" ".join(_text_fragments(node)))


def _text_fragments(node: HtmlNode) -> list[str]:
    if node.tag in {"script", "style", "noscript"}:
        return []
    fragments: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            fragments.append(child)
        elif isinstance(child, HtmlNode):
            fragments.extend(_text_fragments(child))
    return fragments


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


if __name__ == "__main__":
    collect()
