from __future__ import annotations

import ast
import json
import os
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..env import first_env, load_local_env, required_env
from ..models import BrandingProfile, ContentBundle, EvaluationResult, SourceContent
from .content_tools import DemoLLMProvider, evaluate_content, improve_content, resolve_output_language

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency at runtime
    certifi = None


class OpenAICompatibleLLMProvider(DemoLLMProvider):
    """Optional provider for OpenAI-compatible chat-completions APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 45,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = f"openai-compatible:{model}"

    def generate_content(self, source: SourceContent, branding: BrandingProfile) -> ContentBundle:
        output_language = resolve_output_language(source, branding)
        prompt = {
            "task": "Generate a branded multi-format content package.",
            "source": {
                "title": source.title,
                "summary": source.summary,
                "key_points": source.key_points,
                "source_url": source.source_url,
                "source_language": source.language,
            },
            "branding": {
                "company_name": branding.company_name,
                "audience": branding.audience,
                "voice": branding.voice,
                "tone_keywords": branding.tone_keywords,
                "forbidden_phrases": branding.forbidden_phrases,
                "call_to_action": branding.call_to_action,
                "language": branding.language,
            },
            "output_language": output_language,
            "output_schema": {
                "blog_post": "string",
                "linkedin_post": "string",
                "twitter_thread": ["string"],
                "newsletter": "string",
            },
        }
        try:
            response = self._complete_json(_GENERATION_SYSTEM_PROMPT, prompt)
        except ValueError:
            return super().generate_content(source, branding)
        try:
            return _content_bundle_from_json(response)
        except (KeyError, TypeError, ValueError):
            return super().generate_content(source, branding)

    def evaluate_content(
        self,
        content: ContentBundle,
        branding: BrandingProfile,
    ) -> EvaluationResult:
        prompt = {
            "task": "Evaluate generated branded content.",
            "content": content.as_dict(),
            "branding": {
                "company_name": branding.company_name,
                "audience": branding.audience,
                "voice": branding.voice,
                "tone_keywords": branding.tone_keywords,
                "forbidden_phrases": branding.forbidden_phrases,
                "call_to_action": branding.call_to_action,
            },
            "score_scale": "0 to 10",
            "output_schema": {
                "clarity": "number",
                "engagement": "number",
                "branding": "number",
                "issues": ["string"],
                "recommendations": ["string"],
            },
        }
        try:
            response = self._complete_json(_EVALUATION_SYSTEM_PROMPT, prompt)
        except ValueError:
            return evaluate_content(content, branding)
        try:
            return EvaluationResult(
                clarity=_score(response["clarity"]),
                engagement=_score(response["engagement"]),
                branding=_score(response["branding"]),
                issues=list(response.get("issues", [])),
                recommendations=list(response.get("recommendations", [])),
            )
        except (KeyError, TypeError, ValueError):
            return evaluate_content(content, branding)

    def improve_content(
        self,
        content: ContentBundle,
        evaluation: EvaluationResult,
        branding: BrandingProfile,
        source: SourceContent | None = None,
    ) -> ContentBundle:
        source_language = source.language if source else "unknown"
        output_language = resolve_output_language(source, branding) if source else branding.language
        prompt = {
            "task": "Improve the content using the evaluation.",
            "content": content.as_dict(),
            "evaluation": evaluation.as_dict(),
            "branding": {
                "company_name": branding.company_name,
                "audience": branding.audience,
                "voice": branding.voice,
                "tone_keywords": branding.tone_keywords,
                "forbidden_phrases": branding.forbidden_phrases,
                "call_to_action": branding.call_to_action,
                "language": branding.language,
            },
            "source_language": source_language,
            "output_language": output_language,
            "output_schema": {
                "blog_post": "string",
                "linkedin_post": "string",
                "twitter_thread": ["string"],
                "newsletter": "string",
            },
        }
        try:
            response = self._complete_json(_IMPROVEMENT_SYSTEM_PROMPT, prompt)
        except ValueError:
            return improve_content(content, evaluation, branding, source=source)
        try:
            return _content_bundle_from_json(response)
        except (KeyError, TypeError, ValueError):
            return improve_content(content, evaluation, branding, source=source)

    def _complete_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/agent-content-pipeline",
                "X-Title": "Agent Content Pipeline",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout, context=_ssl_context()) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ValueError(f"LLM request failed: {self._format_http_error(exc)}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError(f"LLM request failed: {exc}") from exc

        try:
            message = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM response did not include message content.") from exc

        if isinstance(message, list):
            message = "".join(part.get("text", "") for part in message if isinstance(part, dict))
        if not isinstance(message, str):
            raise ValueError("LLM message content was not text.")
        return json.loads(message)

    @staticmethod
    def _format_http_error(exc: HTTPError) -> str:
        status = exc.code
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            return f"HTTP Error {status}"

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            compact = " ".join(raw_body.split())
            return f"HTTP Error {status}: {compact[:300]}"

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("type") or error.get("code")
                if message:
                    return f"HTTP Error {status}: {message}"
            message = payload.get("message")
            if isinstance(message, str) and message:
                return f"HTTP Error {status}: {message}"

        return f"HTTP Error {status}: {' '.join(raw_body.split())[:300]}"


def select_llm_provider() -> DemoLLMProvider:
    load_local_env()
    provider = os.getenv("LLM_PROVIDER", "demo").lower().strip()
    if provider == "demo":
        return DemoLLMProvider()

    if provider == "groq":
        return OpenAICompatibleLLMProvider(
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=first_env("GROQ_API_KEY", "LLM_API_KEY"),
            model=os.getenv("GROQ_MODEL", os.getenv("LLM_MODEL", "llama-3.1-8b-instant")),
        )

    if provider == "openai":
        api_key = required_env("OPENAI_API_KEY")
        model = required_env("OPENAI_MODEL")
        return OpenAICompatibleLLMProvider(
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
            model=model,
        )

    if provider == "openrouter":
        api_key = required_env("OPENROUTER_API_KEY")
        model = required_env("OPENROUTER_MODEL")
        return OpenAICompatibleLLMProvider(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
            model=model,
        )

    if provider == "compatible":
        return OpenAICompatibleLLMProvider(
            base_url=required_env("LLM_BASE_URL"),
            api_key=required_env("LLM_API_KEY"),
            model=required_env("LLM_MODEL"),
        )

    raise ValueError("LLM_PROVIDER must be one of: demo, groq, openai, openrouter, compatible.")


def _content_bundle_from_json(payload: dict[str, Any]) -> ContentBundle:
    thread = _normalize_thread(payload["twitter_thread"])
    return ContentBundle(
        blog_post=_normalize_text_block(payload["blog_post"], heading=True),
        linkedin_post=_normalize_text_block(payload["linkedin_post"]),
        twitter_thread=[str(tweet)[:280] for tweet in thread],
        newsletter=_normalize_text_block(payload["newsletter"]),
    )


def _score(value: Any) -> float:
    return round(max(0.0, min(float(value), 10.0)), 2)


def _normalize_thread(value: Any) -> list[str]:
    parsed = _coerce_structured_value(value)
    if isinstance(parsed, dict):
        for key in ("tweets", "thread", "items"):
            nested = parsed.get(key)
            if isinstance(nested, list):
                parsed = nested
                break
        else:
            parsed = _thread_items_from_dict(parsed)
    if not isinstance(parsed, list):
        raise TypeError("twitter_thread must be a list.")

    normalized: list[str] = []
    for item in parsed:
        if isinstance(item, dict):
            normalized.extend(_thread_items_from_dict(item))
        else:
            normalized.append(str(item).strip())
    return [item for item in normalized if item]


def _normalize_text_block(value: Any, heading: bool = False) -> str:
    parsed = _coerce_structured_value(value)

    if isinstance(parsed, dict):
        parts: list[str] = []
        title = _first_present(parsed, "title", "headline", "subject")
        summary = _first_present(parsed, "summary", "preview", "excerpt")
        content = _first_present(parsed, "content", "body", "text", "message", "post")
        bullets = parsed.get("key_points") or parsed.get("takeaways")
        call_to_action = _first_present(parsed, "call_to_action", "cta")

        if title:
            parts.append(f"# {title}" if heading else title)
        if summary and summary != title:
            parts.append(summary)
        if content and content not in {title, summary}:
            parts.append(content)
        if isinstance(bullets, list):
            bullet_lines = [f"- {str(item).strip()}" for item in bullets if str(item).strip()]
            if bullet_lines:
                parts.append("\n".join(bullet_lines))
        if call_to_action and call_to_action not in {title, summary, content}:
            parts.append(call_to_action)

        if parts:
            return "\n\n".join(parts)

    if isinstance(parsed, list):
        items = [str(item).strip() for item in parsed if str(item).strip()]
        return "\n".join(items)

    text = str(parsed).strip()
    if heading and text and not text.startswith("#"):
        return f"# {text}"
    return text


def _coerce_structured_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text or text[0] not in "{[":
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
    return value


def _first_present(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _thread_items_from_dict(payload: dict[str, Any]) -> list[str]:
    tweet_keys = [key for key in payload if key.lower().startswith("tweet")]
    if tweet_keys:
        ordered = sorted(tweet_keys, key=_tweet_sort_key)
        return [str(payload[key]).strip() for key in ordered if str(payload[key]).strip()]

    text = _first_present(payload, "text", "content", "message", "body")
    return [text] if text else []


def _tweet_sort_key(value: str) -> tuple[int, str]:
    suffix = value[5:]
    if suffix.isdigit():
        return (int(suffix), value)
    return (999, value)


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


_GENERATION_SYSTEM_PROMPT = """
You generate platform-specific marketing content from one source.
Return valid JSON only.
Each output format must be different and suited to its platform.
Respect the brand voice, audience, forbidden phrases, and call to action.
Keep Twitter thread items under 280 characters.
Write all output fields in the requested output_language.
If the source is in English and output_language is Portuguese, translate naturally into Portuguese.
""".strip()

_EVALUATION_SYSTEM_PROMPT = """
You evaluate branded content quality.
Return valid JSON only.
Score clarity, engagement, and branding from 0 to 10.
List concrete issues and recommendations.
Penalize generic rewriting, copied formats, missing brand voice, and forbidden phrases.
""".strip()

_IMPROVEMENT_SYSTEM_PROMPT = """
You improve branded multi-format content.
Return valid JSON only.
Use the evaluation to improve clarity, engagement, and brand alignment.
Keep each platform format distinct.
Respect forbidden phrases and keep Twitter thread items under 280 characters.
Write all output fields in the requested output_language.
If the source is in English and output_language is Portuguese, keep the final version in Portuguese.
""".strip()
