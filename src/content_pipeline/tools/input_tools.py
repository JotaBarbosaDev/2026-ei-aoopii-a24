from __future__ import annotations

import re
from textwrap import shorten
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..models import SourceContent


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
    )


def _extract_first_url(value: str) -> str | None:
    match = re.search(r"https?://[^\s)>\]]+", value)
    return match.group(0).rstrip(".,") if match else None


def _fetch_url_text(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": "AgentContentPipeline/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
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
