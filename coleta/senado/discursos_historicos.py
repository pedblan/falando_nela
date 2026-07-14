from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from coleta.common.http import OpenDataClient


PORTAL_BASE_URL = "https://www25.senado.leg.br/"
PORTAL_SEARCH_ENDPOINT = "web/atividade/pronunciamentos"
PORTLET_PREFIX = "_pronunciamentos_WAR_atividadeportlet_"
PORTLET_PAGE_KEY = f"{PORTLET_PREFIX}p"
PRONUNCIAMENTO_RE = re.compile(r"/pronunciamento/(\d+)(?:[/?#]|$)")
TOTAL_RE = re.compile(r"Total\s+de\s+([\d.]+)\s+registros?\s+encontrados?", re.IGNORECASE)
NO_RESULTS_RE = re.compile(r"Nenhum\s+pronunciamento\s+encontrado", re.IGNORECASE)
INT_RE = re.compile(r"\b([\d.]+)\b")
HOUSE_CODES = {
    "senado federal": "SF",
    "congresso nacional": "CN",
    "câmara dos deputados": "CD",
    "camara dos deputados": "CD",
    "presidência da república": "PR",
    "presidencia da republica": "PR",
    "comissão representativa do congresso": "CR",
    "comissao representativa do congresso": "CR",
    "assembléia nacional constituinte": "AC",
    "assembleia nacional constituinte": "AC",
}
TEXT_URL = "https://legis.senado.leg.br/dadosabertos/discurso/texto-integral/{codigo}"


@dataclass(frozen=True)
class HtmlCell:
    text: str
    links: tuple[str, ...]


@dataclass(frozen=True)
class HtmlDocument:
    rows: tuple[tuple[HtmlCell, ...], ...]
    links: tuple[tuple[str, str], ...]
    text: str


@dataclass(frozen=True)
class PortalAuthor:
    name: str
    url: str
    expected_count: int


@dataclass(frozen=True)
class PortalPage:
    kind: str
    author: str | None
    page: int
    url: str
    response: dict[str, Any]
    html: str


@dataclass(frozen=True)
class PortalDiscovery:
    items: tuple[dict[str, Any], ...]
    pages: tuple[PortalPage, ...]
    expected_count: int
    discovered_count: int
    duplicate_count: int
    truncated: bool


class _PortalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[HtmlCell, ...]] = []
        self.links: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._row: list[HtmlCell] | None = None
        self._cell_text: list[str] | None = None
        self._cell_links: list[str] | None = None
        self._anchor_href: str | None = None
        self._anchor_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value for key, value in attrs}
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_text = []
            self._cell_links = []
        elif tag == "a":
            self._anchor_href = attributes.get("href")
            self._anchor_text = []
            if self._cell_links is not None and self._anchor_href:
                self._cell_links.append(self._anchor_href)

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._cell_text is not None:
            self._cell_text.append(data)
        if self._anchor_text is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor_text is not None:
            if self._anchor_href:
                self.links.append((self._anchor_href, _clean_text(self._anchor_text)))
            self._anchor_href = None
            self._anchor_text = None
        elif tag in {"td", "th"} and self._row is not None and self._cell_text is not None:
            self._row.append(
                HtmlCell(
                    text=_clean_text(self._cell_text),
                    links=tuple(self._cell_links or ()),
                )
            )
            self._cell_text = None
            self._cell_links = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(tuple(self._row))
            self._row = None


def parse_portal_html(html: str) -> HtmlDocument:
    parser = _PortalParser()
    parser.feed(html)
    parser.close()
    return HtmlDocument(
        rows=tuple(parser.rows),
        links=tuple(parser.links),
        text=_clean_text(parser.text_parts),
    )


def extract_portal_authors(html: str, *, page_url: str = PORTAL_BASE_URL) -> list[PortalAuthor]:
    document = parse_portal_html(html)
    authors: list[PortalAuthor] = []
    seen: set[str] = set()
    for row in document.rows:
        for index, cell in enumerate(row):
            href = next(
                (
                    link
                    for link in cell.links
                    if f"{PORTLET_PREFIX}autor=1" in link and f"{PORTLET_PREFIX}nomeAutor=" in link
                ),
                None,
            )
            if not href:
                continue
            url = urljoin(page_url, href)
            if url in seen:
                continue
            count = _first_integer(row[index + 1 :])
            if count is None:
                raise ValueError(f"Portal sem quantidade para o autor: {cell.text or url}")
            authors.append(PortalAuthor(name=cell.text, url=url, expected_count=count))
            seen.add(url)
    return authors


def extract_portal_pronunciamentos(
    html: str,
    *,
    page_url: str,
    author: str,
    author_url: str,
) -> list[dict[str, Any]]:
    document = parse_portal_html(html)
    items: list[dict[str, Any]] = []
    for row in document.rows:
        speech_link: str | None = None
        speech_cell_index: int | None = None
        codigo: str | None = None
        for index, cell in enumerate(row):
            for link in cell.links:
                match = PRONUNCIAMENTO_RE.search(link)
                if match:
                    speech_link = urljoin(page_url, link)
                    speech_cell_index = index
                    codigo = match.group(1)
                    break
            if codigo:
                break
        if codigo is None or speech_cell_index is None or speech_link is None:
            continue
        if len(row) <= speech_cell_index + 1:
            raise ValueError(f"Linha incompleta do pronunciamento {codigo}")

        data = _parse_portal_date(row[speech_cell_index].text)
        house_name = row[speech_cell_index + 1].text
        if not house_name:
            raise ValueError(f"Casa ausente no pronunciamento {codigo}")
        sigla_casa = HOUSE_CODES.get(house_name.casefold(), "OUT_OF_SCOPE")
        party_uf = row[speech_cell_index + 2].text if len(row) > speech_cell_index + 2 else ""
        resumo = row[speech_cell_index + 3].text if len(row) > speech_cell_index + 3 else ""
        partido, uf = _split_party_uf(party_uf)
        items.append(
            {
                "codigo_pronunciamento": codigo,
                "metadata": {
                    "sessao": {
                        "DataSessao": data.isoformat(),
                        "SiglaCasa": sigla_casa,
                        "NomeCasa": house_name,
                    },
                    "pronunciamento": {
                        "CodigoPronunciamento": codigo,
                        "Data": data.isoformat(),
                        "NomeAutor": author,
                        "Partido": partido,
                        "UF": uf,
                        "Resumo": resumo,
                        "Casa": house_name,
                    },
                    "descoberta_historica": {
                        "estrategia": "portal_pronunciamentos_por_autor",
                        "autor_url": author_url,
                        "pagina_url": page_url,
                    },
                },
                "fontes": {
                    "texto_integral_txt": TEXT_URL.format(codigo=codigo),
                    "texto_integral_html": speech_link,
                    "texto_binario": None,
                    "video": None,
                    "notas_sessao_api": None,
                    "videos_sessao_api": None,
                    "portal_detalhe": speech_link,
                    "portal_busca_autor": author_url,
                },
            }
        )
    return items


def discover_portal_pronunciamentos(
    client: OpenDataClient,
    *,
    start: date,
    end: date,
    limit: int | None = None,
) -> PortalDiscovery:
    params = portal_search_params(start, end)
    initial = client.get_text(PORTAL_SEARCH_ENDPOINT, params=params)
    pages: list[PortalPage] = [
        PortalPage(
            kind="author_index",
            author=None,
            page=1,
            url=str(initial.response_metadata.get("url") or PORTAL_SEARCH_ENDPOINT),
            response=initial.response_metadata,
            html=str(initial.data),
        )
    ]
    authors = extract_portal_authors(str(initial.data), page_url=pages[0].url)
    if not authors and not NO_RESULTS_RE.search(parse_portal_html(str(initial.data)).text):
        raise ValueError("Resposta do portal sem autores e sem marcador explicito de resultado vazio")
    expected_count = sum(author.expected_count for author in authors)
    discovered: dict[str, dict[str, Any]] = {}
    duplicate_count = 0

    for author in authors:
        if limit is not None and len(discovered) >= limit:
            break
        first = client.get_text(author.url)
        first_url = str(first.response_metadata.get("url") or author.url)
        first_html = str(first.data)
        pages.append(
            PortalPage(
                kind="author_results",
                author=author.name,
                page=1,
                url=first_url,
                response=first.response_metadata,
                html=first_html,
            )
        )
        author_items = extract_portal_pronunciamentos(
            first_html,
            page_url=first_url,
            author=author.name,
            author_url=author.url,
        )
        reported_total = extract_reported_total(first_html)
        if reported_total is not None and reported_total != author.expected_count:
            raise ValueError(
                f"Contagem divergente para {author.name}: indice={author.expected_count}, pagina={reported_total}"
            )

        page_count = extract_max_page(first_html, page_url=first_url)
        if page_count == 1 and author.expected_count > len(author_items) and author_items:
            page_count = math.ceil(author.expected_count / len(author_items))
        for item in author_items:
            duplicate_count += _insert_discovered(discovered, item)

        for page_number in range(2, page_count + 1):
            if limit is not None and len(discovered) >= limit:
                break
            page_url = set_page_number(first_url, page_number)
            result = client.get_text(page_url)
            resolved_url = str(result.response_metadata.get("url") or page_url)
            html = str(result.data)
            pages.append(
                PortalPage(
                    kind="author_results",
                    author=author.name,
                    page=page_number,
                    url=resolved_url,
                    response=result.response_metadata,
                    html=html,
                )
            )
            for item in extract_portal_pronunciamentos(
                html,
                page_url=resolved_url,
                author=author.name,
                author_url=author.url,
            ):
                duplicate_count += _insert_discovered(discovered, item)

        if limit is None:
            author_codes = {
                code
                for code, item in discovered.items()
                if item["metadata"]["descoberta_historica"]["autor_url"] == author.url
            }
            if len(author_codes) != author.expected_count:
                raise ValueError(
                    f"Descoberta incompleta para {author.name}: esperado={author.expected_count}, obtido={len(author_codes)}"
                )

    truncated = limit is not None and len(discovered) < expected_count
    items = list(discovered.values())
    items.sort(
        key=lambda item: (
            item["metadata"]["pronunciamento"]["Data"],
            item["codigo_pronunciamento"],
        )
    )
    if limit is not None:
        items = items[:limit]
    if limit is None and len(items) != expected_count:
        raise ValueError(f"Descoberta incompleta no portal: esperado={expected_count}, obtido={len(items)}")
    return PortalDiscovery(
        items=tuple(items),
        pages=tuple(pages),
        expected_count=expected_count,
        discovered_count=len(items),
        duplicate_count=duplicate_count,
        truncated=truncated,
    )


def portal_search_params(start: date, end: date) -> dict[str, Any]:
    return {
        "p_p_id": "pronunciamentos_WAR_atividadeportlet",
        "p_p_lifecycle": 0,
        "p_p_state": "normal",
        "p_p_mode": "view",
        "p_p_col_id": "column-1",
        "p_p_col_count": 1,
        "total": 1,
        "dataInicial": start.strftime("%d/%m/%Y"),
        "dataFinal": end.strftime("%d/%m/%Y"),
    }


def extract_reported_total(html: str) -> int | None:
    match = TOTAL_RE.search(parse_portal_html(html).text)
    return _parse_integer(match.group(1)) if match else None


def extract_max_page(html: str, *, page_url: str) -> int:
    document = parse_portal_html(html)
    pages = [1]
    for href, _ in document.links:
        query = dict(parse_qsl(urlsplit(urljoin(page_url, href)).query, keep_blank_values=True))
        value = query.get(PORTLET_PAGE_KEY)
        if value and value.isdigit():
            pages.append(int(value))
    return max(pages)


def set_page_number(url: str, page: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[PORTLET_PAGE_KEY] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def merge_primary_and_portal(
    primary_items: list[dict[str, Any]],
    portal_items: list[dict[str, Any]],
    *,
    sigla_casa: str,
    require_parity: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    primary = {
        str(item["codigo_pronunciamento"]): item
        for item in primary_items
        if item.get("codigo_pronunciamento")
    }
    portal = {
        str(item["codigo_pronunciamento"]): item
        for item in portal_items
        if item.get("codigo_pronunciamento")
        and item.get("metadata", {}).get("sessao", {}).get("SiglaCasa") == sigla_casa
    }
    other_houses = Counter(
        str(item.get("metadata", {}).get("sessao", {}).get("SiglaCasa") or "UNKNOWN")
        for item in portal_items
        if item.get("codigo_pronunciamento")
        and item.get("metadata", {}).get("sessao", {}).get("SiglaCasa") != sigla_casa
    )
    missing_in_portal = sorted(set(primary).difference(portal))
    if require_parity and missing_in_portal:
        raise ValueError(
            f"Portal historico nao reproduziu {len(missing_in_portal)} IDs da fonte primaria: {missing_in_portal[:10]}"
        )

    merged: list[dict[str, Any]] = []
    for code in sorted(set(primary).union(portal), key=int):
        if code in primary and code in portal:
            item = dict(primary[code])
            item["metadata"] = dict(item.get("metadata") or {})
            item["metadata"]["descoberta_historica"] = portal[code]["metadata"]["descoberta_historica"]
            item["fontes"] = {**portal[code]["fontes"], **(item.get("fontes") or {})}
            item["fontes"]["portal_detalhe"] = portal[code]["fontes"]["portal_detalhe"]
            item["fontes"]["portal_busca_autor"] = portal[code]["fontes"]["portal_busca_autor"]
            merged.append(item)
        else:
            merged.append(primary.get(code) or portal[code])

    audit = {
        "primary_count": len(primary),
        "portal_house_count": len(portal),
        "merged_count": len(merged),
        "primary_missing_in_portal": missing_in_portal,
        "portal_additional_ids": sorted(set(portal).difference(primary), key=int),
        "portal_other_houses": dict(sorted(other_houses.items())),
        "primary_empty_portal_nonempty": not primary and bool(portal),
    }
    return merged, audit


def _insert_discovered(discovered: dict[str, dict[str, Any]], item: dict[str, Any]) -> int:
    code = str(item["codigo_pronunciamento"])
    current = discovered.get(code)
    if current is None:
        discovered[code] = item
        return 0
    current_pron = current["metadata"]["pronunciamento"]
    new_pron = item["metadata"]["pronunciamento"]
    if (current_pron["Data"], current_pron["Casa"]) != (new_pron["Data"], new_pron["Casa"]):
        raise ValueError(f"Conflito de data/casa para o pronunciamento {code}")
    return 1


def _first_integer(cells: tuple[HtmlCell, ...]) -> int | None:
    for cell in cells:
        match = INT_RE.search(cell.text)
        if match:
            return _parse_integer(match.group(1))
    return None


def _parse_integer(value: str) -> int:
    return int(value.replace(".", ""))


def _parse_portal_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError(f"Data invalida no portal: {value!r}") from exc


def _split_party_uf(value: str) -> tuple[str | None, str | None]:
    if "/" not in value:
        return value.strip() or None, None
    party, uf = value.rsplit("/", 1)
    return party.strip() or None, uf.strip() or None


def _clean_text(parts: list[str]) -> str:
    return " ".join(" ".join(parts).split())
