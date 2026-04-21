from __future__ import annotations

from dataclasses import replace

from ..models import ContentBundle, SourceContent

try:
    from deep_translator import GoogleTranslator

    GOOGLE_TRANSLATOR_AVAILABLE = True
except ImportError:  # pragma: no cover - optional runtime dependency
    GoogleTranslator = None
    GOOGLE_TRANSLATOR_AVAILABLE = False


def translate_source_to_portuguese(source: SourceContent) -> SourceContent:
    if source.language != "english":
        return source

    translated_title = _translate_text(source.title)
    translated_summary = _translate_text(source.summary)
    translated_points = [_translate_text(point) for point in source.key_points]

    return replace(
        source,
        title=translated_title or source.title,
        summary=translated_summary or source.summary,
        key_points=[point or original for point, original in zip(translated_points, source.key_points, strict=False)]
        or source.key_points,
    )


def translate_bundle_to_portuguese(content: ContentBundle) -> ContentBundle:
    return replace(
        content,
        blog_post=_translate_text_if_needed(content.blog_post),
        linkedin_post=_translate_text_if_needed(content.linkedin_post),
        twitter_thread=[_translate_text_if_needed(tweet) for tweet in content.twitter_thread],
        newsletter=_translate_text_if_needed(content.newsletter),
    )


def _translate_text(text: str) -> str:
    if not text.strip():
        return text

    if not GOOGLE_TRANSLATOR_AVAILABLE:
        return text

    try:
        translator = GoogleTranslator(source="en", target="pt")
        translated = translator.translate(text)
        return translated.strip() if isinstance(translated, str) else text
    except Exception:
        return text


def _translate_text_if_needed(text: str) -> str:
    if not text.strip():
        return text
    if not _looks_english(text):
        return text
    if not GOOGLE_TRANSLATOR_AVAILABLE:
        return text

    try:
        translator = GoogleTranslator(source="auto", target="pt")
        translated = translator.translate(text)
        return translated.strip() if isinstance(translated, str) else text
    except Exception:
        return text


def _looks_english(text: str) -> bool:
    sample = f" {text.lower()} "
    english_markers = [
        " the ",
        " and ",
        " with ",
        " from ",
        " next step ",
        " branding note ",
        " did you know ",
        " read the full article ",
        " healthy diet ",
        " importance ",
    ]
    portuguese_markers = [
        " de ",
        " para ",
        " com ",
        " que ",
        " proximo passo ",
        " nota de branding ",
        " dieta ",
        " saudavel ",
        " importancia ",
    ]
    en_score = sum(marker in sample for marker in english_markers)
    pt_score = sum(marker in sample for marker in portuguese_markers)
    return en_score > pt_score
