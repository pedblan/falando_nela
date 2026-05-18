from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from typing import Any
from urllib.parse import urljoin

import httpx

from coleta.common.http import OpenDataClient


@dataclass(frozen=True)
class TextExtraction:
    text: str
    method: str
    error: str | None = None


@dataclass(frozen=True)
class DocumentTextResult:
    request: dict[str, Any]
    response: dict[str, Any]
    text: str
    method: str
    text_status: str
    fontes: dict[str, Any]
    document: dict[str, Any]
    attempts: list[dict[str, Any]]
    error: dict[str, Any] | None = None


def sha256_bytes(content: bytes) -> str:
    return sha256(content).hexdigest()


def download_and_extract_document(client: OpenDataClient, url: str) -> DocumentTextResult:
    request = {"method": "GET", "path": url, "params": {}}
    attempts: list[dict[str, Any]] = []
    fontes: dict[str, Any] = {"documento": url}

    try:
        result = client.get_bytes(url)
    except httpx.HTTPStatusError as exc:
        response = _response_from_error(exc)
        attempts.append({"metodo_obtencao": "document_download", "texto_status": "erro", "response": response})
        return DocumentTextResult(
            request=request,
            response=response,
            text="",
            method="document_download",
            text_status="erro",
            fontes=fontes,
            document={},
            attempts=attempts,
            error={"tipo": "http_status", "mensagem": str(exc), "status_code": exc.response.status_code},
        )

    content = result.data if isinstance(result.data, bytes) else b""
    content_type = result.headers.get("content-type", "")
    attempts.append(
        {
            "metodo_obtencao": "document_download",
            "texto_status": "baixado",
            "response": result.response_metadata,
        }
    )

    refresh_url = extract_meta_refresh_url(content, base_url=result.url) if looks_like_html(content) else None
    if refresh_url:
        fontes["documento_resolvido"] = refresh_url
        try:
            result = client.get_bytes(refresh_url)
            content = result.data if isinstance(result.data, bytes) else b""
            content_type = result.headers.get("content-type", "")
            attempts.append(
                {
                    "metodo_obtencao": "document_meta_refresh",
                    "texto_status": "baixado",
                    "response": result.response_metadata,
                }
            )
        except httpx.HTTPStatusError as exc:
            response = _response_from_error(exc)
            attempts.append(
                {
                    "metodo_obtencao": "document_meta_refresh",
                    "texto_status": "erro",
                    "response": response,
                }
            )
            return DocumentTextResult(
                request=request,
                response=response,
                text="",
                method="document_meta_refresh",
                text_status="erro",
                fontes=fontes,
                document={},
                attempts=attempts,
                error={"tipo": "http_status", "mensagem": str(exc), "status_code": exc.response.status_code},
            )

    extraction = extract_text_from_document(content, content_type=content_type, url=result.url)
    text_status = "disponivel" if extraction.text else "erro" if extraction.error else "ausente"
    document = {
        "url_final": result.url,
        "content_type": content_type,
        "tamanho_bytes": len(content),
        "sha256": sha256_bytes(content),
        "metodo_extracao": extraction.method,
    }
    error = {"tipo": "text_extraction", "mensagem": extraction.error} if extraction.error else None
    attempts.append(
        {
            "metodo_obtencao": extraction.method,
            "texto_status": text_status,
            "response": result.response_metadata,
        }
    )
    return DocumentTextResult(
        request=request,
        response=result.response_metadata,
        text=extraction.text,
        method=extraction.method,
        text_status=text_status,
        fontes=fontes,
        document=document,
        attempts=attempts,
        error=error,
    )


def extract_text_from_document(content: bytes, *, content_type: str | None, url: str) -> TextExtraction:
    media_type = _media_type(content_type)
    if media_type == "application/pdf" or content.startswith(b"%PDF"):
        return extract_text_from_pdf_bytes(content)
    if media_type in {"text/html", "application/xhtml+xml"} or looks_like_html(content):
        return TextExtraction(
            text=extract_text_from_html_bytes(content),
            method="html_text_extraction",
        )
    if media_type.startswith("text/"):
        return TextExtraction(
            text=decode_text(content).strip(),
            method="text_document_download",
        )
    return TextExtraction(
        text="",
        method="unsupported_document_type",
        error=f"Tipo de documento nao suportado para extracao textual: {content_type or 'desconhecido'} ({url})",
    )


def extract_text_from_pdf_bytes(content: bytes) -> TextExtraction:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        return TextExtraction(
            text="",
            method="pdf_text_extraction",
            error=f"Dependencia ausente para extrair PDF: {exc}",
        )

    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(page for page in pages if page)
        return TextExtraction(text=text, method="pdf_text_extraction")
    except Exception as exc:
        return TextExtraction(text="", method="pdf_text_extraction", error=str(exc))


def extract_text_from_html_bytes(content: bytes) -> str:
    parser = _VisibleTextParser()
    parser.feed(decode_text(content))
    return "\n".join(_collapse_spaces(fragment) for fragment in parser.fragments if fragment.strip()).strip()


def extract_meta_refresh_url(content: bytes, *, base_url: str) -> str | None:
    parser = _MetaRefreshParser(base_url=base_url)
    parser.feed(decode_text(content))
    return parser.url


def looks_like_html(content: bytes) -> bool:
    prefix = content.lstrip()[:80].lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<meta" in prefix


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _media_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _response_from_error(exc: httpx.HTTPStatusError) -> dict[str, Any]:
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


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fragments: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.fragments.append(data)


class _MetaRefreshParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.url or tag.lower() != "meta":
            return
        attrs_dict = {key.lower(): value for key, value in attrs if value is not None}
        if attrs_dict.get("http-equiv", "").lower() != "refresh":
            return
        content = attrs_dict.get("content", "")
        match = re.search(r"url\s*=\s*([^;]+)$", content, flags=re.IGNORECASE)
        if match:
            self.url = urljoin(self.base_url, match.group(1).strip().strip("'\""))
