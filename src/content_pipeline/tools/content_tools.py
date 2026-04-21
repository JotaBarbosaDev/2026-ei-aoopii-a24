from __future__ import annotations

import re
from dataclasses import replace
from textwrap import shorten

from ..models import BrandingProfile, ContentBundle, EvaluationResult, SourceContent


class DemoLLMProvider:
    """Deterministic LLM stand-in for demos without API keys."""

    name = "demo-llm"

    def generate_content(self, source: SourceContent, branding: BrandingProfile) -> ContentBundle:
        output_language = resolve_output_language(source, branding)
        points = source.key_points[:4]
        point_block = "\n".join(f"- {point}" for point in points)
        first_point = points[0] if points else source.summary

        if output_language == "Portuguese":
            blog_post = (
                f"# {source.title}\n\n"
                f"{source.summary}\n\n"
                f"## Porque isto importa\n"
                f"Para {branding.audience}, a principal oportunidade esta em transformar esta "
                f"informacao num passo pratico e util.\n\n"
                f"## Pontos principais\n{point_block}\n\n"
                f"## Enquadramento pratico\n"
                f"A historia deve ser comunicada com uma voz {branding.voice}, "
                f"mantendo a mensagem clara e acionavel."
            )

            linkedin_post = (
                f"{source.title}\n\n"
                f"{first_point}\n\n"
                f"O impacto principal esta na forma como as equipas interpretam o sinal, "
                f"tomam decisoes e comunicam o que mudou.\n\n"
                f"Pontos principais:\n{point_block}\n\n"
                f"Como reagiria a tua equipa a isto?"
            )

            newsletter = (
                f"Assunto: {source.title}\n\n"
                f"Preview: {shorten(source.summary, width=120, placeholder='...')}\n\n"
                f"Esta semana, ha um desenvolvimento que merece atencao: {source.summary}\n\n"
                f"Porque interessa:\n{point_block}\n\n"
                f"Em resumo: isto ajuda {branding.audience} a perceber melhor o que mudou e o que fazer a seguir."
            )
        else:
            blog_post = (
                f"# {source.title}\n\n"
                f"{source.summary}\n\n"
                f"## Why it matters\n"
                f"For {branding.audience}, the main opportunity is to turn this information "
                f"into a practical next step instead of treating it as background noise.\n\n"
                f"## Key takeaways\n{point_block}\n\n"
                f"## Practical angle\n"
                f"The story can be framed with a {branding.voice} voice, keeping the message "
                f"useful, focused, and easy to act on."
            )

            linkedin_post = (
                f"{source.title}\n\n"
                f"{first_point}\n\n"
                f"What matters now is the business impact: teams need to understand the signal, "
                f"decide what changes, and communicate it clearly.\n\n"
                f"Key points:\n{point_block}\n\n"
                f"How would your team respond to this?"
            )

            newsletter = (
                f"Subject: {source.title}\n\n"
                f"Preview: {shorten(source.summary, width=120, placeholder='...')}\n\n"
                f"This week, one development deserves attention: {source.summary}\n\n"
                f"Why readers should care:\n{point_block}\n\n"
                f"Bottom line: this is useful because it gives {branding.audience} a clearer "
                f"way to discuss what changed and what to do next."
            )

        twitter_thread = _make_thread(source, branding)

        return ContentBundle(
            blog_post=blog_post,
            linkedin_post=linkedin_post,
            twitter_thread=twitter_thread,
            newsletter=newsletter,
        )

    def evaluate_content(
        self,
        content: ContentBundle,
        branding: BrandingProfile,
    ) -> EvaluationResult:
        return evaluate_content(content, branding)

    def improve_content(
        self,
        content: ContentBundle,
        evaluation: EvaluationResult,
        branding: BrandingProfile,
        source: SourceContent | None = None,
    ) -> ContentBundle:
        return improve_content(content, evaluation, branding, source=source)


def generate_content(
    source: SourceContent,
    branding: BrandingProfile,
    llm: DemoLLMProvider | None = None,
) -> ContentBundle:
    provider = llm or DemoLLMProvider()
    return provider.generate_content(source, branding)


def evaluate_content(content: ContentBundle, branding: BrandingProfile) -> EvaluationResult:
    combined = _combined_text(content)
    lower = combined.lower()

    clarity = _score_clarity(content)
    engagement = _score_engagement(content, branding)
    brand_score = _score_branding(content, branding)

    issues: list[str] = []
    recommendations: list[str] = []

    if clarity < 8:
        issues.append("The content needs clearer structure or stronger takeaways.")
        recommendations.append("Add headings, bullets, and a concise bottom-line statement.")
    if engagement < 8:
        issues.append("The content needs a stronger call to action or interaction hook.")
        recommendations.append("Add one audience question, platform-specific hashtags, and a clear next step.")
    if brand_score < 8:
        issues.append("The brand voice is present but not explicit enough.")
        recommendations.append("Mention the company, audience, tone, and preferred CTA more directly.")

    forbidden_hits = [phrase for phrase in branding.forbidden_phrases if phrase.lower() in lower]
    if forbidden_hits:
        issues.append(f"Forbidden phrases detected: {', '.join(forbidden_hits)}.")
        recommendations.append("Remove wording that conflicts with the branding guidelines.")

    return EvaluationResult(
        clarity=clarity,
        engagement=engagement,
        branding=brand_score,
        issues=issues,
        recommendations=recommendations,
    )


def improve_content(
    content: ContentBundle,
    evaluation: EvaluationResult,
    branding: BrandingProfile,
    source: SourceContent | None = None,
) -> ContentBundle:
    output_language = resolve_output_language(source, branding) if source else branding.language

    if output_language == "Portuguese":
        localized_audience = _localize_portuguese_text(branding.audience)
        localized_tone = _localize_portuguese_text(", ".join(branding.tone_keywords[:3]) or branding.voice)
        localized_cta = _localize_portuguese_cta(branding.call_to_action, branding.company_name)
        brand_note = (
            f"\n\nNota de branding: {branding.company_name} deve enquadrar este tema para "
            f"{localized_audience} com um tom {localized_tone}."
        )
        cta = f"\n\nProximo passo: {localized_cta}"
        linkedin_note = (
            f"\n\nNa {branding.company_name}, isto liga-se a uma pergunta simples: "
            "que decisao pode o leitor tomar hoje?"
        )
        newsletter_note = (
            f"\n\nDa perspetiva da {branding.company_name}: usa este documento como "
            f"briefing pratico para {localized_audience}."
        )
        thread_takeaway = f"Conclusao da {branding.company_name}: {localized_cta}"
    else:
        tone = ", ".join(branding.tone_keywords[:3]) or branding.voice
        brand_note = (
            f"\n\nBranding note: {branding.company_name} should frame this for "
            f"{branding.audience} with a {tone} tone."
        )
        cta = f"\n\nNext step: {branding.call_to_action}"
        linkedin_note = (
            f"\n\nAt {branding.company_name}, this connects to a simple question: "
            "what decision can readers make today?"
        )
        newsletter_note = (
            f"\n\nFrom {branding.company_name}: use this as a practical briefing for "
            f"{branding.audience}."
        )
        thread_takeaway = f"{branding.company_name} takeaway: {branding.call_to_action}"

    hashtag = _hashtag(branding.company_name)

    improved_blog = _remove_forbidden(_append_once(_append_once(content.blog_post, brand_note), cta), branding)
    improved_linkedin = _remove_forbidden(
        _append_once(
            _append_once(
                _append_once(content.linkedin_post, linkedin_note),
                cta,
            ),
            f"\n\n#{hashtag} #ContentStrategy #AI",
        ),
        branding,
    )

    raw_thread = [_strip_tweet_prefix(tweet) for tweet in content.twitter_thread]
    takeaway_line = f"{thread_takeaway} #{hashtag}"
    if not any(thread_takeaway in tweet for tweet in raw_thread):
        raw_thread.append(takeaway_line)
    improved_thread = _renumber_thread([_remove_forbidden(tweet, branding) for tweet in raw_thread])

    improved_newsletter = _remove_forbidden(
        _append_once(_append_once(content.newsletter, newsletter_note), cta),
        branding,
    )

    return replace(
        content,
        blog_post=improved_blog,
        linkedin_post=improved_linkedin,
        twitter_thread=improved_thread,
        newsletter=improved_newsletter,
    )


def normalize_bundle_for_portuguese(
    content: ContentBundle,
    branding: BrandingProfile,
) -> ContentBundle:
    return replace(
        content,
        blog_post=_localize_generated_text(content.blog_post, branding),
        linkedin_post=_localize_generated_text(content.linkedin_post, branding),
        twitter_thread=[_localize_generated_text(tweet, branding) for tweet in content.twitter_thread],
        newsletter=_localize_generated_text(content.newsletter, branding),
    )


def resolve_output_language(source: SourceContent, branding: BrandingProfile) -> str:
    if source.language in {"english", "portuguese"}:
        return "Portuguese"
    return branding.language


def _make_thread(source: SourceContent, branding: BrandingProfile) -> list[str]:
    points = source.key_points[:4]
    if resolve_output_language(source, branding) == "Portuguese":
        raw_tweets = [
            f"Novo sinal: {source.title}. Eis o que importa para {branding.audience}.",
            f"Contexto: {source.summary}",
        ]
        raw_tweets.extend(f"Ponto-chave: {point}" for point in points[:3])
    else:
        raw_tweets = [
            f"New signal: {source.title}. Here is what matters for {branding.audience}.",
            f"Context: {source.summary}",
        ]
        raw_tweets.extend(f"Takeaway: {point}" for point in points[:3])
    return [_tweet(index + 1, len(raw_tweets), tweet) for index, tweet in enumerate(raw_tweets)]


def _tweet(index: int, total: int, text: str) -> str:
    prefix = f"{index}/{total} "
    return prefix + shorten(text, width=280 - len(prefix), placeholder="...")


def _renumber_thread(tweets: list[str]) -> list[str]:
    total = len(tweets)
    return [_tweet(index + 1, total, tweet) for index, tweet in enumerate(tweets)]


def _strip_tweet_prefix(tweet: str) -> str:
    return re.sub(r"^\d+/\d+\s+", "", tweet)


def _score_clarity(content: ContentBundle) -> float:
    score = 6.0
    if "##" in content.blog_post:
        score += 1.0
    if "- " in content.blog_post:
        score += 0.7
    if content.newsletter.lower().startswith(("subject:", "assunto:")):
        score += 0.5
    if len(content.twitter_thread) >= 4:
        score += 0.6
    if len(content.blog_post.split()) > 100:
        score += 0.7
    return round(min(score, 10.0), 2)


def _score_engagement(content: ContentBundle, branding: BrandingProfile) -> float:
    combined = _combined_text(content).lower()
    score = 5.5
    if "?" in content.linkedin_post:
        score += 0.8
    if "#" in content.linkedin_post or any("#" in tweet for tweet in content.twitter_thread):
        score += 0.8
    if branding.call_to_action.lower() in combined:
        score += 1.4
    if any(
        marker in value.lower()
        for value in [content.blog_post, content.newsletter]
        for marker in ["next step", "proximo passo"]
    ):
        score += 0.7
    if len(content.twitter_thread) >= 5:
        score += 0.8
    return round(min(score, 10.0), 2)


def _score_branding(content: ContentBundle, branding: BrandingProfile) -> float:
    combined = _combined_text(content).lower()
    score = 5.5
    score += min(combined.count(branding.company_name.lower()) * 0.9, 2.2)
    if branding.audience.lower() in combined:
        score += 0.7
    matched_keywords = sum(1 for word in branding.tone_keywords if word.lower() in combined)
    score += min(matched_keywords * 0.45, 1.2)
    score += 0.6

    forbidden_hits = sum(1 for phrase in branding.forbidden_phrases if phrase.lower() in combined)
    score -= forbidden_hits * 2.0
    return round(max(0.0, min(score, 10.0)), 2)


def _combined_text(content: ContentBundle) -> str:
    return "\n".join(
        [
            content.blog_post,
            content.linkedin_post,
            "\n".join(content.twitter_thread),
            content.newsletter,
        ]
    )


def _hashtag(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value)
    return cleaned or "Brand"


def _remove_forbidden(value: str, branding: BrandingProfile) -> str:
    result = value
    for phrase in branding.forbidden_phrases:
        result = re.sub(re.escape(phrase), "clear", result, flags=re.IGNORECASE)
    return result


def _append_once(base: str, snippet: str) -> str:
    normalized_snippet = snippet.strip()
    if not normalized_snippet:
        return base
    if normalized_snippet in base:
        return base
    return base + snippet


def _localize_portuguese_text(value: str) -> str:
    replacements = {
        "marketing and product teams": "equipas de marketing e produto",
        "clear": "claro",
        "practical": "pratico",
        "confident": "seguro",
        "human": "humano",
        "voice": "voz",
        "tone": "tom",
    }
    result = value
    for original, translated in replacements.items():
        result = re.sub(re.escape(original), translated, result, flags=re.IGNORECASE)
    return result


def _localize_portuguese_cta(call_to_action: str, company_name: str) -> str:
    normalized = call_to_action.strip()
    if not normalized:
        return f"Agenda uma breve conversa estrategica com {company_name}."

    pattern = rf"book a short strategy call with\s+{re.escape(company_name)}\.?"
    if re.fullmatch(pattern, normalized, flags=re.IGNORECASE):
        return f"Agenda uma breve conversa estrategica com {company_name}."

    translated = _localize_portuguese_text(normalized)
    if translated == normalized and not re.search(r"[ãõáéíóúâêôç]", normalized.lower()):
        return f"Agenda uma breve conversa estrategica com {company_name}."
    return translated


def _localize_generated_text(value: str, branding: BrandingProfile) -> str:
    localized_cta = _localize_portuguese_cta(branding.call_to_action, branding.company_name)
    replacements = {
        branding.call_to_action: localized_cta,
        f"Book a short strategy call with {branding.company_name}.": localized_cta,
        f"Book a short strategy call with {branding.company_name}": localized_cta,
        f"{branding.company_name} takeaway:": f"Conclusao da {branding.company_name}:",
        "Takeaway:": "Ponto-chave:",
        "Why it matters": "Porque isto importa",
        "Key takeaways": "Pontos principais",
        "Practical angle": "Enquadramento pratico",
        "marketing and product teams": "equipas de marketing e produto",
        "clear, practical, and confident": "claro, pratico e seguro",
        "clear, practical, confident": "claro, pratico, seguro",
    }

    result = value
    for original, translated in replacements.items():
        result = re.sub(re.escape(original), translated, result, flags=re.IGNORECASE)
    return result
