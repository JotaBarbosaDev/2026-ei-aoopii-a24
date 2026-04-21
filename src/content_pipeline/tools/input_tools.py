from __future__ import annotations

import re
import ssl
from textwrap import shorten
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..models import SourceContent

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency at runtime
    certifi = None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts)


def extract_input(payload: str, timeout: int = 8) -> SourceContent:
    """Turn a raw message, pasted article, or URL into normalized source content."""

    value = payload.strip()
    source_url = _extract_first_url(value)
    if source_url:
        text = _fetch_url_text(source_url, timeout=timeout)
        if not text:
            text = value
        source_type = "link"
    else:
        text = value
        source_type = "text"

    clean_text = _normalize_whitespace(text)
    title = _derive_title(clean_text, source_url)
    key_points = _extract_key_points(clean_text)
    summary = _summarize(clean_text, key_points)

    return SourceContent(
        raw_input=clean_text,
        source_type=source_type,
        title=title,
        summary=summary,
        key_points=key_points,
        source_url=source_url,
        language=_detect_language(clean_text or title),
    )


def _extract_first_url(value: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", value)
    return match.group(0).rstrip(".,") if match else None


def _fetch_url_text(url: str, timeout: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read(250_000)
    except (OSError, URLError, TimeoutError):
        return ""

    decoded = body.decode("utf-8", errors="replace")
    if "html" not in content_type:
        return decoded

    parser = _TextExtractor()
    parser.feed(decoded)
    return parser.text()


def _derive_title(text: str, source_url: str | None) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line and len(first_line) <= 120:
        return first_line

    first_sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip()
    if first_sentence:
        return _shorten(first_sentence, 90)

    if source_url:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or "source"
        path = parsed.path.strip("/").replace("-", " ").replace("_", " ")
        if path:
            return path.split("/")[-1].title()
        return hostname

    return "Source content"


def _extract_key_points(text: str, limit: int = 5) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    points: list[str] = []
    for sentence in sentences:
        normalized = sentence.strip(" -\n\t")
        if len(normalized) < 35:
            continue
        points.append(_shorten(normalized, 190))
        if len(points) == limit:
            break

    if points:
        return points

    fallback = _shorten(text, 190)
    return [fallback] if fallback else ["No detailed source text was provided."]


def _summarize(text: str, key_points: list[str]) -> str:
    if len(text) <= 280:
        return text
    return " ".join(key_points[:2])


def _shorten(value: str, limit: int) -> str:
    value = _normalize_whitespace(value)
    return shorten(value, width=limit, placeholder="...")


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _detect_language(text: str) -> str:
    sample = text.lower()
    if not sample:
        return "unknown"

    portuguese_markers = [
        " de ",
        " para ",
        " uma ",
        " com ",
        " que ",
        " não ",
        " missão ",
        " rumo ",
        " lança ",
        " sucesso ",
        " notícia ",
    ]
    english_markers = [
        " the ",
        " and ",
        " for ",
        " with ",
        " from ",
        " this ",
        " that ",
        " mission ",
        " success ",
        " article ",
        " news ",
    ]

    pt_score = sum(marker in f" {sample} " for marker in portuguese_markers)
    en_score = sum(marker in f" {sample} " for marker in english_markers)

    if re.search(r"[ãõáéíóúâêôç]", sample):
        pt_score += 2

    if pt_score > en_score:
        return "portuguese"
    if en_score > pt_score:
        return "english"
    return "unknown"
