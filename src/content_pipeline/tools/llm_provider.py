from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..models import BrandingProfile, ContentBundle, EvaluationResult, SourceContent
from .content_tools import DemoLLMProvider, evaluate_content, improve_content


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
        prompt = {
            "task": "Generate a branded multi-format content package.",
            "source": {
                "title": source.title,
                "summary": source.summary,
                "key_points": source.key_points,
                "source_url": source.source_url,
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
            "output_schema": {
                "blog_post": "string",
                "linkedin_post": "string",
                "twitter_thread": ["string"],
                "newsletter": "string",
            },
        }
        response = self._complete_json(_GENERATION_SYSTEM_PROMPT, prompt)
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
        response = self._complete_json(_EVALUATION_SYSTEM_PROMPT, prompt)
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
    ) -> ContentBundle:
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
            "output_schema": {
                "blog_post": "string",
                "linkedin_post": "string",
                "twitter_thread": ["string"],
                "newsletter": "string",
            },
        }
        response = self._complete_json(_IMPROVEMENT_SYSTEM_PROMPT, prompt)
        try:
            return _content_bundle_from_json(response)
        except (KeyError, TypeError, ValueError):
            return improve_content(content, evaluation, branding)

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
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
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


def select_llm_provider() -> DemoLLMProvider:
    provider = os.getenv("LLM_PROVIDER", "demo").lower().strip()
    if provider == "demo":
        return DemoLLMProvider()

    if provider == "openai":
        api_key = _required_env("OPENAI_API_KEY")
        model = _required_env("OPENAI_MODEL")
        return OpenAICompatibleLLMProvider(
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
            model=model,
        )

    if provider == "openrouter":
        api_key = _required_env("OPENROUTER_API_KEY")
        model = _required_env("OPENROUTER_MODEL")
        return OpenAICompatibleLLMProvider(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
            model=model,
        )

    if provider == "compatible":
        return OpenAICompatibleLLMProvider(
            base_url=_required_env("LLM_BASE_URL"),
            api_key=_required_env("LLM_API_KEY"),
            model=_required_env("LLM_MODEL"),
        )

    raise ValueError("LLM_PROVIDER must be one of: demo, openai, openrouter, compatible.")


def _content_bundle_from_json(payload: dict[str, Any]) -> ContentBundle:
    thread = payload["twitter_thread"]
    if not isinstance(thread, list):
        raise TypeError("twitter_thread must be a list.")
    return ContentBundle(
        blog_post=str(payload["blog_post"]),
        linkedin_post=str(payload["linkedin_post"]),
        twitter_thread=[str(tweet)[:280] for tweet in thread],
        newsletter=str(payload["newsletter"]),
    )


def _score(value: Any) -> float:
    return round(max(0.0, min(float(value), 10.0)), 2)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


_GENERATION_SYSTEM_PROMPT = """
You generate platform-specific marketing content from one source.
Return valid JSON only.
Each output format must be different and suited to its platform.
Respect the brand voice, audience, forbidden phrases, and call to action.
Keep Twitter thread items under 280 characters.
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
""".strip()
