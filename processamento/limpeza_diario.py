from __future__ import annotations

import re
import unicodedata
from hashlib import sha256
from typing import Any


DIARY_RECOVERY_METHOD = "diario-congresso-oficial-por-codigo-v1"
DIARY_CLEANING_VERSION = "diario-congresso-limpeza-editorial-v1"
BOUNDARY_NONEMPTY_LINES = 5


def clean_diary_editorial_noise(text: str) -> dict[str, Any]:
    """Remove somente cabeçalhos/rodapés reconhecidos junto a quebras de página.

    O raw extraído do PDF preserva ``\f`` entre páginas. A função não procura
    ruído no corpo do discurso: apenas as primeiras/últimas linhas não vazias
    de cada página interna podem ser removidas.
    """

    original = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not original:
        raise ValueError("Texto do Diário vazio")

    pages = original.split("\f")
    if len(pages) == 1:
        return _result(original=original, cleaned=original, removed_lines=[], page_breaks=0)

    cleaned_pages: list[str] = []
    removed_lines: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        lines = page.splitlines()
        candidates: set[int] = set()
        nonempty = [index for index, line in enumerate(lines) if line.strip()]
        candidates.update(nonempty[:BOUNDARY_NONEMPTY_LINES])
        candidates.update(nonempty[-BOUNDARY_NONEMPTY_LINES:])

        kept: list[str] = []
        for line_index, line in enumerate(lines):
            if line_index in candidates and is_diary_editorial_line(line):
                removed_lines.append(
                    {
                        "page_index": page_index,
                        "line_index": line_index,
                        "text": line.strip(),
                    }
                )
                continue
            kept.append(line.rstrip())
        cleaned_pages.append("\n".join(kept).strip())

    if not removed_lines:
        return _result(
            original=original,
            cleaned=original,
            removed_lines=[],
            page_breaks=len(pages) - 1,
        )

    cleaned = "\n\n".join(page for page in cleaned_pages if page).strip()
    if not cleaned:
        raise ValueError("Limpeza do Diário removeu todo o texto")
    return _result(
        original=original,
        cleaned=cleaned,
        removed_lines=removed_lines,
        page_breaks=len(pages) - 1,
    )


def is_diary_editorial_line(line: str) -> bool:
    compact = " ".join(str(line).split())
    if not compact or len(compact) > 180:
        return False
    normalized = _ascii_upper(compact)

    if re.fullmatch(r"(?:PAGINA\s+)?\d{1,6}", normalized):
        return True
    diary_markers = (
        "DIARIO DO CONGRESSO NACIONAL",
        "DIARIO DO SENADO FEDERAL",
    )
    if any(
        normalized.startswith(marker)
        or re.match(rf"^(?:PAGINA\s+)?\d{{1,6}}\s+{marker}(?:\s+\d{{1,6}})?$", normalized)
        for marker in diary_markers
    ):
        return True
    if re.fullmatch(r"(?:CONGRESSO NACIONAL|SENADO FEDERAL)", normalized):
        return True
    if re.match(
        r"^(?:SEGUNDA|TERCA|QUARTA|QUINTA|SEXTA|SABADO|DOMINGO)(?:-FEIRA)?[, ]",
        normalized,
    ) and re.search(r"\b(?:19|20)\d{2}\b", normalized):
        return True
    if normalized.startswith("BRASILIA") and re.search(r"\b(?:19|20)\d{2}\b", normalized):
        return True
    if normalized.startswith("ANO ") and re.search(r"\b(?:19|20)\d{2}\b", normalized):
        return True
    return False


def _result(
    *,
    original: str,
    cleaned: str,
    removed_lines: list[dict[str, Any]],
    page_breaks: int,
) -> dict[str, Any]:
    return {
        "version": DIARY_CLEANING_VERSION,
        "text": cleaned,
        "changed": cleaned != original,
        "removed_line_count": len(removed_lines),
        "removed_lines": removed_lines,
        "page_breaks": page_breaks,
        "original_sha256": _sha256(original),
        "cleaned_sha256": _sha256(cleaned),
        "original_length": len(original),
        "cleaned_length": len(cleaned),
    }


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _ascii_upper(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(character for character in decomposed if not unicodedata.combining(character)).upper()
