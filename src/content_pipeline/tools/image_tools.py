from __future__ import annotations

import hashlib
import json
import os
import ssl
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..env import load_local_env
from ..models import BrandingProfile, ContentBundle, ImageAsset, SourceContent
from .document_tools import upload_document

try:
    import certifi
except ImportError:  # pragma: no cover - optional runtime dependency
    certifi = None


@dataclass(frozen=True)
class ImageSpec:
    platform: str
    label: str
    width: int
    height: int
    visual_goal: str


IMAGE_SPECS: tuple[ImageSpec, ...] = (
    ImageSpec("blog", "Blog", 1600, 896, "hero editorial image for a blog article"),
    ImageSpec("linkedin", "LinkedIn", 1200, 632, "professional branded visual for a LinkedIn post"),
    ImageSpec("twitter", "X/Twitter", 1600, 896, "bold horizontal social image for an X post"),
    ImageSpec("newsletter", "Newsletter", 1200, 632, "clean header visual for an email newsletter"),
)


def generate_social_images(
    source: SourceContent,
    content: ContentBundle,
    branding: BrandingProfile,
    run_id: str,
    output_dir: Path | str,
    public_dir: Path | str,
    public_base_url: str | None = None,
) -> list[ImageAsset]:
    load_local_env()
    if not _cloudflare_configured():
        return []

    generated_dir = Path(output_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)
    uploaded_dir = Path(public_dir)
    uploaded_dir.mkdir(parents=True, exist_ok=True)

    assets: list[ImageAsset] = []
    for spec in IMAGE_SPECS:
        prompt = _build_image_prompt(spec, source, content, branding)
        image_bytes, extension = _run_cloudflare_image_generation(spec, prompt, run_id)
        file_name = _build_image_filename(source.title, spec.platform, run_id, extension)
        image_path = generated_dir / file_name
        image_path.write_bytes(image_bytes)

        image_base_url = (
            f"{public_base_url.rstrip('/')}/images" if public_base_url else None
        )
        upload = upload_document(
            image_path,
            public_dir=uploaded_dir,
            public_base_url=image_base_url,
        )
        assets.append(
            ImageAsset(
                platform=spec.platform,
                width=spec.width,
                height=spec.height,
                path=image_path,
                url=upload.url,
                prompt=prompt,
            )
        )
    return assets


def _cloudflare_configured() -> bool:
    return bool(os.getenv("CLOUDFLARE_API_TOKEN") and os.getenv("CLOUDFLARE_ACCOUNT_ID"))


def _run_cloudflare_image_generation(
    spec: ImageSpec,
    prompt: str,
    run_id: str,
) -> tuple[bytes, str]:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    model = os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")

    payload = {
        "prompt": prompt,
        "negative_prompt": (
            "blurry, low quality, watermark, extra text, paragraph text, logo, "
            "collage, split panels, distorted anatomy, duplicated objects"
        ),
        "width": spec.width,
        "height": spec.height,
        "num_steps": int(os.getenv("CLOUDFLARE_IMAGE_STEPS", "6")),
        "guidance": float(os.getenv("CLOUDFLARE_IMAGE_GUIDANCE", "4.5")),
        "seed": _seed_for(run_id, spec.platform),
    }

    request = Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120, context=_ssl_context()) as response:
            body = response.read()
            content_type = response.headers.get("content-type", "").lower()
    except HTTPError as exc:
        raise ValueError(f"Cloudflare image generation failed: {_format_http_error(exc)}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Cloudflare image generation failed: {exc}") from exc

    return body, _extension_from_content_type(content_type, body)


def _build_image_prompt(
    spec: ImageSpec,
    source: SourceContent,
    content: ContentBundle,
    branding: BrandingProfile,
) -> str:
    platform_context = {
        "blog": content.blog_post,
        "linkedin": content.linkedin_post,
        "twitter": " ".join(content.twitter_thread[:2]),
        "newsletter": content.newsletter,
    }[spec.platform]
    context_excerpt = shorten(platform_context.replace("\n", " "), width=220, placeholder="...")
    key_points = "; ".join(source.key_points[:3])
    tone = ", ".join(branding.tone_keywords[:4]) or branding.voice

    return (
        f"Create a high-quality {spec.visual_goal}. "
        f"Topic: {source.title}. "
        f"Summary: {source.summary}. "
        f"Key points: {key_points}. "
        f"Brand: {branding.company_name}. Audience: {branding.audience}. "
        f"Voice and tone: {branding.voice}; keywords: {tone}. "
        f"Platform context: {context_excerpt}. "
        "Visual style: modern, polished, editorial, brand-aligned, professional, "
        "high contrast, strong composition, no visible text overlay, no watermark."
    )


def _seed_for(run_id: str, platform: str) -> int:
    digest = hashlib.sha256(f"{run_id}:{platform}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _build_image_filename(title: str, platform: str, run_id: str, extension: str) -> str:
    slug = _slugify(title) or "content-pipeline"
    short_run_id = run_id.split("-")[-1]
    return f"{slug}-{platform}-{short_run_id}.{extension}"


def _slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    sanitized = "".join(char if char.isalnum() else "-" for char in ascii_value)
    return "-".join(part for part in sanitized.split("-") if part)[:60]


def _extension_from_content_type(content_type: str, body: bytes) -> str:
    if "png" in content_type or body.startswith(b"\x89PNG"):
        return "png"
    if "webp" in content_type or body.startswith(b"RIFF"):
        return "webp"
    return "jpg"


def _format_http_error(exc: HTTPError) -> str:
    status = exc.code
    try:
        raw_body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return f"HTTP Error {status}"

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return f"HTTP Error {status}: {' '.join(raw_body.split())[:300]}"

    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                message = first.get("message")
                if message:
                    return f"HTTP Error {status}: {message}"
        result = payload.get("result")
        if isinstance(result, dict):
            message = result.get("message")
            if message:
                return f"HTTP Error {status}: {message}"

    return f"HTTP Error {status}: {' '.join(raw_body.split())[:300]}"


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())
