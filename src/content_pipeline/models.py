from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BrandingProfile:
    company_name: str
    audience: str
    voice: str
    tone_keywords: list[str] = field(default_factory=list)
    forbidden_phrases: list[str] = field(default_factory=list)
    call_to_action: str = "Contact us to learn more."
    language: str = "English"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrandingProfile":
        return cls(
            company_name=str(payload.get("company_name", "Example Company")),
            audience=str(payload.get("audience", "business readers")),
            voice=str(payload.get("voice", "clear, helpful, and practical")),
            tone_keywords=list(payload.get("tone_keywords", [])),
            forbidden_phrases=list(payload.get("forbidden_phrases", [])),
            call_to_action=str(payload.get("call_to_action", "Contact us to learn more.")),
            language=str(payload.get("language", "English")),
        )


@dataclass(frozen=True)
class SourceContent:
    raw_input: str
    source_type: str
    title: str
    summary: str
    key_points: list[str]
    source_url: str | None = None


@dataclass(frozen=True)
class ContentBundle:
    blog_post: str
    linkedin_post: str
    twitter_thread: list[str]
    newsletter: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "blog_post": self.blog_post,
            "linkedin_post": self.linkedin_post,
            "twitter_thread": self.twitter_thread,
            "newsletter": self.newsletter,
        }


@dataclass(frozen=True)
class EvaluationResult:
    clarity: float
    engagement: float
    branding: float
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        return round((self.clarity + self.engagement + self.branding) / 3, 2)

    def passed(self, threshold: float) -> bool:
        return self.overall >= threshold

    def as_dict(self) -> dict[str, Any]:
        return {
            "clarity": self.clarity,
            "engagement": self.engagement,
            "branding": self.branding,
            "overall": self.overall,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


@dataclass(frozen=True)
class DocumentArtifact:
    path: Path
    markdown_path: Path | None = None
    format: str = "pdf"


@dataclass(frozen=True)
class UploadResult:
    url: str
    public_path: Path


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    source: SourceContent
    content: ContentBundle
    evaluation: EvaluationResult
    document: DocumentArtifact
    upload: UploadResult
    iterations: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": {
                "source_type": self.source.source_type,
                "title": self.source.title,
                "summary": self.source.summary,
                "key_points": self.source.key_points,
                "source_url": self.source.source_url,
            },
            "content": self.content.as_dict(),
            "evaluation": self.evaluation.as_dict(),
            "document_path": str(self.document.path),
            "markdown_path": str(self.document.markdown_path) if self.document.markdown_path else None,
            "url": self.upload.url,
            "iterations": self.iterations,
        }
