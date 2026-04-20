from __future__ import annotations

import re
from dataclasses import replace
from textwrap import shorten

from ..models import BrandingProfile, ContentBundle, EvaluationResult, SourceContent


class DemoLLMProvider:
    """Deterministic LLM stand-in for demos without API keys."""

    name = "demo-llm"

    def generate_content(self, source: SourceContent, branding: BrandingProfile) -> ContentBundle:
        points = source.key_points[:4]
        point_block = "\n".join(f"- {point}" for point in points)
        first_point = points[0] if points else source.summary

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

        twitter_thread = _make_thread(source, branding)

        newsletter = (
            f"Subject: {source.title}\n\n"
            f"Preview: {shorten(source.summary, width=120, placeholder='...')}\n\n"
            f"This week, one development deserves attention: {source.summary}\n\n"
            f"Why readers should care:\n{point_block}\n\n"
            f"Bottom line: this is useful because it gives {branding.audience} a clearer "
            f"way to discuss what changed and what to do next."
        )

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
    ) -> ContentBundle:
        return improve_content(content, evaluation, branding)


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
) -> ContentBundle:
    tone = ", ".join(branding.tone_keywords[:3]) or branding.voice
    brand_note = (
        f"\n\nBranding note: {branding.company_name} should frame this for "
        f"{branding.audience} with a {tone} tone."
    )
    cta = f"\n\nNext step: {branding.call_to_action}"
    hashtag = _hashtag(branding.company_name)

    improved_blog = _remove_forbidden(content.blog_post + brand_note + cta, branding)
    improved_linkedin = _remove_forbidden(
        content.linkedin_post
        + f"\n\nAt {branding.company_name}, this connects to a simple question: "
        + "what decision can readers make today?"
        + cta
        + f"\n\n#{hashtag} #ContentStrategy #AI",
        branding,
    )

    raw_thread = [_strip_tweet_prefix(tweet) for tweet in content.twitter_thread]
    raw_thread.append(f"{branding.company_name} takeaway: {branding.call_to_action} #{hashtag}")
    improved_thread = _renumber_thread([_remove_forbidden(tweet, branding) for tweet in raw_thread])

    improved_newsletter = _remove_forbidden(
        content.newsletter
        + f"\n\nFrom {branding.company_name}: use this as a practical briefing for "
        + f"{branding.audience}."
        + cta,
        branding,
    )

    return replace(
        content,
        blog_post=improved_blog,
        linkedin_post=improved_linkedin,
        twitter_thread=improved_thread,
        newsletter=improved_newsletter,
    )


def _make_thread(source: SourceContent, branding: BrandingProfile) -> list[str]:
    points = source.key_points[:4]
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
    if content.newsletter.lower().startswith("subject:"):
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
    if any("next step" in value.lower() for value in [content.blog_post, content.newsletter]):
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
