from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from urllib.parse import urljoin

import httpx


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class HttpResult:
    url: str
    status_code: int
    headers: dict[str, str]
    data: Any

    @property
    def response_metadata(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "headers": self.headers,
        }


class OpenDataClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        retries: int = 4,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "falando-nela-coleta/0.1",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "OpenDataClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_json(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> HttpResult:
        return self._get(path_or_url, params=params, accept="application/json", response_type="json")

    def get_text(self, path_or_url: str, *, params: dict[str, Any] | None = None) -> HttpResult:
        return self._get(path_or_url, params=params, accept="text/plain", response_type="text")

    def _get(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None,
        accept: str,
        response_type: str,
    ) -> HttpResult:
        url = self._resolve_url(path_or_url)
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self.retries:
            try:
                response = self.client.get(url, params=params, headers={"Accept": accept})
                if response.status_code not in RETRY_STATUS_CODES:
                    response.raise_for_status()
                    return self._result(response, response_type=response_type)

                if attempt == self.retries:
                    response.raise_for_status()

                self._sleep_before_retry(response, attempt)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == self.retries:
                    raise
                self.sleep(self.backoff_seconds * (2**attempt))

            attempt += 1

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Falha inesperada ao acessar {url}")

    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.base_url, path_or_url.lstrip("/"))

    def _sleep_before_retry(self, response: httpx.Response, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                self.sleep(float(retry_after))
                return
            except ValueError:
                pass
        self.sleep(self.backoff_seconds * (2**attempt))

    def _result(self, response: httpx.Response, *, response_type: str) -> HttpResult:
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "date", "link", "retry-after", "x-total-count"}
        }
        if response_type == "text":
            data = response.text if response.content else ""
        else:
            data = response.json() if response.content else None
        return HttpResult(
            url=str(response.url),
            status_code=response.status_code,
            headers=headers,
            data=data,
        )


def iter_camara_pages(
    client: OpenDataClient,
    path_or_url: str,
    *,
    params: dict[str, Any] | None = None,
) -> Iterator[HttpResult]:
    next_url: str | None = path_or_url
    next_params = params

    while next_url:
        result = client.get_json(next_url, params=next_params)
        yield result
        next_url = _next_link(result.data)
        next_params = None


def _next_link(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for link in payload.get("links", []):
        if isinstance(link, dict) and link.get("rel") == "next":
            return link.get("href")
    return None
