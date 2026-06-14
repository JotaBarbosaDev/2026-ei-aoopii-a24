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

from ..environment import PROJECT_ROOT, load_local_env
from ..models import BrandingProfile, ContentBundle, ImageAsset, SourceContent
from .document_tools import upload_document

try:
    import certifi
except ImportError:  # pragma: no cover - optional runtime dependency
    certifi = None

try:
    from PIL import Image, ImageDraw

    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional runtime dependency
    Image = None
    ImageDraw = None
    PIL_AVAILABLE = False


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

STYLE_PRESETS = {
    "anime": {
        "positive": (
            "Japanese anime illustration, 2D manga key visual, clean black line art, "
            "cel shading, expressive anime lighting, vibrant colors, cinematic anime scene. "
            "The image must look clearly anime, not realistic"
        ),
        "negative": (
            "photorealistic, real photo, stock photo, realistic camera look, 3D render, "
            "flat corporate illustration, minimalist poster"
        ),
    },
    "futuristic": {
        "positive": (
            "futuristic sci-fi concept art, high-tech environment, holographic interfaces, "
            "neon lighting, metallic surfaces, cyberpunk atmosphere, advanced technology scene. "
            "The image must look clearly futuristic"
        ),
        "negative": (
            "anime, manga, cartoon, old-fashioned, vintage, plain office, realistic stock photo, "
            "minimalist poster"
        ),
    },
    "illustration": {
        "positive": (
            "modern editorial illustration, vector art, flat design, clean geometric shapes, "
            "bold simplified forms, graphic magazine composition. "
            "The image must look clearly illustrated, not photographic"
        ),
        "negative": (
            "photorealistic, real photo, anime, manga, cyberpunk, 3D render, messy details"
        ),
    },
    "photographic": {
        "positive": (
            "realistic professional photography, documentary photo style, real-world camera look, "
            "natural lighting, realistic materials, sharp details, authentic scene. "
            "The image must look like a real photograph"
        ),
        "negative": (
            "anime, manga, cartoon, illustration, vector art, flat design, 3D render, painting"
        ),
    },
    "minimalist": {
        "positive": (
            "minimalist modern poster, simple symbolic visual, clean empty space, few elements, "
            "elegant composition, subtle shapes, premium minimal design. "
            "The image must look clearly minimalist"
        ),
        "negative": (
            "busy scene, crowded composition, photorealistic detail, anime, manga, cyberpunk, "
            "complex background, clutter"
        ),
    },
}

FIGMA_FRAMES_CACHE = PROJECT_ROOT / ".figma_cache"
FIGMA_LOCAL_FRAMES_DIR = PROJECT_ROOT / "assets" / "figma_frames"
FIGMA_API_TOKEN_ENV = "FIGMA_API_TOKEN"
FIGMA_FILE_KEY_ENV = "FIGMA_FILE_KEY"
FIGMA_FRAME_PATH_ENV_PREFIX = "FIGMA_FRAME_PATH_"
FIGMA_NODE_ID_ENV_PREFIX = "FIGMA_NODE_ID_"
LOGO_MAX_WIDTH_RATIO = 0.22
LOGO_MAX_HEIGHT_RATIO = 0.20
LOGO_WHITE_THRESHOLD = 248


def generate_social_images(
    source: SourceContent,
    content: ContentBundle,
    branding: BrandingProfile,
    run_id: str,
    output_dir: Path | str,
    public_dir: Path | str,
    public_base_url: str | None = None,
    image_style_instruction: str | None = None,
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
        prompt = _build_image_prompt(spec,source,content,branding,image_style_instruction)
        debug_prompt_path = generated_dir / f"{run_id}-{spec.platform}-prompt.txt"
        debug_prompt_path.write_text(prompt, encoding="utf-8")
        negative_prompt = _build_negative_prompt(image_style_instruction)
        image_bytes, extension = _run_cloudflare_image_generation(
            spec,
            prompt,
            run_id,
            negative_prompt,
        )
        file_name = _build_image_filename(source.title, spec.platform, run_id, extension)
        image_path = generated_dir / file_name
        image_path.write_bytes(image_bytes)
        _apply_figma_frame(image_path, spec.width, spec.height)

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
    negative_prompt: str,
) -> tuple[bytes, str]:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    model = os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/bytedance/stable-diffusion-xl-lightning")

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": spec.width,
        "height": spec.height,
        "num_steps": int(os.getenv("CLOUDFLARE_IMAGE_STEPS", "16")),
        "guidance": float(os.getenv("CLOUDFLARE_IMAGE_GUIDANCE", "8")),
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

def _build_negative_prompt(image_style_instruction: str | None) -> str:
    style = _get_style_preset(image_style_instruction)

    base_negative = (
        "blurry, low quality, watermark, visible text, letters, words, captions, "
        "paragraph text, logo, brand logo, collage, split panels, distorted anatomy, "
        "duplicated objects, unrelated subject, unrelated scene, off-topic image, "
        "generic abstract background, random decorative elements"
    )

    return f"{base_negative}, {style['negative']}"

def _build_image_prompt(
    spec: ImageSpec,
    source: SourceContent,
    content: ContentBundle,
    branding: BrandingProfile,
    image_style_instruction: str | None = None,
) -> str:
    style = _get_style_preset(image_style_instruction)
    visual_topic = _build_visual_topic(source, content)

    return (
        f"{style['positive']}.\n\n"

        "Create an image about this exact topic:\n"
        f"{visual_topic}\n\n"

        "The topic above is mandatory. "
        "The image must show the main event, subject, place, person, object, or situation described in that topic. "
        "Do not ignore the topic. "
        "Do not create a generic social media image. "
        "Do not create a random decorative scene.\n\n"

        f"Image purpose: {spec.visual_goal}.\n"
        f"Image size: {spec.width}x{spec.height}.\n\n"

        "Composition requirements: "
        "one clear main subject, relevant background, direct connection to the topic, strong composition, high quality.\n\n"

        "Forbidden: visible text, words, captions, letters, watermark, logo, unrelated people, unrelated robots, "
        "random city skyline, generic abstract background, random decorative elements, off-topic scene."
    )
     
def _get_style_preset(image_style_instruction: str | None) -> dict[str, str]:
    style_key = (image_style_instruction or "").strip().lower()

    return STYLE_PRESETS.get(
        style_key,
        STYLE_PRESETS["photographic"],
    )


def _build_visual_topic(source: SourceContent, content: ContentBundle) -> str:
    title = getattr(source, "title", "").strip()
    summary = getattr(source, "summary", "").strip()
    key_points = getattr(source, "key_points", []) or []
    raw_input = getattr(source, "raw_input", "").strip()

    topic_parts = []

    if title:
        topic_parts.append(title)

    if summary:
        topic_parts.append(summary)

    if key_points:
        topic_parts.append("; ".join(key_points[:3]))

    if not topic_parts and raw_input and not raw_input.startswith(("http://", "https://")):
        topic_parts.append(raw_input)

    topic = " | ".join(topic_parts).strip()

    if not topic:
        topic = "the main topic of the article"

    return shorten(topic.replace("\n", " "), width=420, placeholder="...")

def _normalize_visual_style(image_style_instruction: str | None) -> str:
    if not image_style_instruction or not image_style_instruction.strip():
        return "realistic professional photography, social-media-ready, clean composition"

    style = image_style_instruction.strip()
    lower_style = style.lower()

    hints: list[str] = []

    if any(word in lower_style for word in ["realista", "realistic", "fotografia", "fotográfico", "photography"]):
        hints.append(
            "photorealistic photography, realistic materials, natural lighting, real-world camera look"
        )

    if any(word in lower_style for word in ["anime", "manga"]):
        hints.append(
            "anime illustration, manga-inspired, clean line art, vibrant colors, expressive lighting"
        )

    if any(word in lower_style for word in ["cartoon", "desenho animado"]):
        hints.append(
            "cartoon illustration, playful shapes, colorful, friendly, stylized characters and objects"
        )

    if any(word in lower_style for word in ["cyberpunk", "futurista", "futuristic", "neon"]):
        hints.append(
            "futuristic cyberpunk style, neon lighting, dark technological atmosphere, cinematic sci-fi mood"
        )

    if any(word in lower_style for word in ["minimalista", "minimalist", "simples", "clean"]):
        hints.append(
            "minimalist visual style, clean shapes, simple composition, modern and uncluttered"
        )

    if any(word in lower_style for word in ["3d", "render", "renderizado"]):
        hints.append(
            "high-quality 3D render, realistic depth, polished surfaces, studio lighting"
        )

    if hints:
        return f"{'; '.join(hints)}. Extra user details: {style}"

    return f"{style}. Follow this visual style literally and consistently."

def _build_image_subject(source: SourceContent, content: ContentBundle) -> str:
    title = getattr(source, "title", "").strip()
    summary = getattr(source, "summary", "").strip()
    key_points = "; ".join(getattr(source, "key_points", [])[:3])

    blog_excerpt = shorten(
        content.blog_post.replace("\n", " "),
        width=220,
        placeholder="...",
    )

    parts = []

    if title:
        parts.append(f"title: {title}")

    if summary:
        parts.append(f"summary: {summary}")

    if key_points:
        parts.append(f"key points: {key_points}")

    if blog_excerpt:
        parts.append(f"article content: {blog_excerpt}")

    if parts:
        return " | ".join(parts)

    raw_input = getattr(source, "raw_input", "").strip()

    if raw_input and not raw_input.startswith(("http://", "https://")):
        return raw_input

    return "the main topic of the article"
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


def _apply_figma_frame(image_path: Path, width: int, height: int) -> None:
    if not PIL_AVAILABLE:
        return

    size_key = f"{width}x{height}"
    frame_path = _fetch_figma_frame(size_key)
    if frame_path is None:
        return

    try:
        with Image.open(image_path) as source_image:
            output_format = source_image.format or _pil_format_from_suffix(image_path.suffix)
            canvas = source_image.convert("RGBA")

        with Image.open(frame_path) as frame_overlay:
            overlay = frame_overlay.convert("RGBA")
    except OSError:
        return

    if overlay.size != canvas.size:
        overlay = overlay.resize(canvas.size, Image.Resampling.LANCZOS)

    composited = Image.alpha_composite(canvas, overlay)
    _save_composited_image(composited, image_path, output_format)


def _fetch_figma_frame(size_key: str) -> Path | None:
    cache_dir = FIGMA_FRAMES_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"frame_{size_key}.png"

    local_frame = _resolve_local_figma_frame(size_key)
    if local_frame is not None:
        return local_frame

    if cache_file.exists():
        return cache_file

    api_token = os.getenv(FIGMA_API_TOKEN_ENV)
    file_key = os.getenv(FIGMA_FILE_KEY_ENV)
    node_id = os.getenv(f"{FIGMA_NODE_ID_ENV_PREFIX}{size_key}")

    if not (api_token and file_key and node_id):
        return None

    try:
        return _download_figma_frame(api_token, file_key, node_id, cache_file)
    except Exception:
        return None


def _download_figma_frame(api_token: str, file_key: str, node_id: str, cache_file: Path) -> Path | None:
    figma_node_id = _normalize_figma_node_id(node_id)
    request_url = f"https://api.figma.com/v1/images/{file_key}?ids={figma_node_id}&format=png"
    request = Request(
        request_url,
        headers={"X-Figma-Token": api_token, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=30, context=_ssl_context()) as response:
            payload = json.load(response)
    except (HTTPError, URLError, OSError):
        return None

    images = payload.get("images") or {}
    image_url = images.get(figma_node_id) or images.get(node_id)
    if not image_url:
        return None

    try:
        with urlopen(Request(image_url), timeout=30, context=_ssl_context()) as image_response:
            image_bytes = image_response.read()
    except (HTTPError, URLError, OSError):
        return None

    cache_file.write_bytes(image_bytes)
    return cache_file


def _resolve_local_figma_frame(size_key: str) -> Path | None:
    configured_path = os.getenv(f"{FIGMA_FRAME_PATH_ENV_PREFIX}{size_key}")
    if configured_path:
        candidate = Path(configured_path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if candidate.exists():
            return candidate

    for file_name in (f"frame_{size_key}.png", f"{size_key}.png"):
        candidate = FIGMA_LOCAL_FRAMES_DIR / file_name
        if candidate.exists():
            return candidate

    expected_names = {
        _normalize_frame_name(size_key),
        _normalize_frame_name(f"frame_{size_key}"),
        _normalize_frame_name(f"frame-{size_key}"),
        _normalize_frame_name(f"frame{size_key}"),
    }
    for candidate in FIGMA_LOCAL_FRAMES_DIR.glob("*.png"):
        if _normalize_frame_name(candidate.stem) in expected_names:
            return candidate

    return None


def _normalize_figma_node_id(node_id: str) -> str:
    return node_id.replace("-", ":")


def _normalize_frame_name(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _prepare_logo(logo_image: Image.Image, canvas_size: tuple[int, int]) -> Image.Image | None:
    prepared = _remove_white_background(logo_image)
    if prepared is None:
        return None

    max_width = max(1, int(canvas_size[0] * LOGO_MAX_WIDTH_RATIO))
    max_height = max(1, int(canvas_size[1] * LOGO_MAX_HEIGHT_RATIO))
    prepared.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return prepared


def _remove_white_background(logo_image: Image.Image) -> Image.Image | None:
    rgba = logo_image.convert("RGBA")
    cleaned_pixels = []
    for red, green, blue, alpha in rgba.getdata():
        if red >= LOGO_WHITE_THRESHOLD and green >= LOGO_WHITE_THRESHOLD and blue >= LOGO_WHITE_THRESHOLD:
            cleaned_pixels.append((255, 255, 255, 0))
        else:
            cleaned_pixels.append((red, green, blue, alpha))
    rgba.putdata(cleaned_pixels)

    bbox = rgba.getbbox()
    if bbox is None:
        return None
    return rgba.crop(bbox)


def _save_composited_image(image: Image.Image, image_path: Path, output_format: str) -> None:
    normalized_format = output_format.upper()
    if normalized_format in {"JPG", "JPEG"}:
        flattened = Image.new("RGB", image.size, "white")
        flattened.paste(image, mask=image.getchannel("A"))
        flattened.save(image_path, format="JPEG", quality=95, subsampling=0)
        return
    if normalized_format == "WEBP":
        image.save(image_path, format="WEBP", quality=95)
        return
    image.save(image_path, format="PNG")


def _pil_format_from_suffix(suffix: str) -> str:
    normalized_suffix = suffix.lower().lstrip(".")
    if normalized_suffix in {"jpg", "jpeg"}:
        return "JPEG"
    if normalized_suffix == "webp":
        return "WEBP"
    return "PNG"
