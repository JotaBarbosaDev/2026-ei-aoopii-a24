from __future__ import annotations

import shutil
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from ..models import ContentBundle, DocumentArtifact, EvaluationResult, UploadResult


def create_document(
    content: ContentBundle,
    evaluation: EvaluationResult,
    output_dir: Path | str,
    run_id: str,
) -> DocumentArtifact:
    """Create a Markdown copy and a small text-based PDF for demo sharing."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = directory / f"{run_id}.md"
    pdf_path = directory / f"{run_id}.pdf"

    markdown = render_markdown(content, evaluation)
    markdown_path.write_text(markdown, encoding="utf-8")
    _write_simple_pdf(pdf_path, _markdown_to_pdf_lines(markdown))

    return DocumentArtifact(path=pdf_path, markdown_path=markdown_path, format="pdf")


def upload_document(
    file_path: Path | str,
    public_dir: Path | str,
    public_base_url: str | None = None,
) -> UploadResult:
    """Copy the document to a public folder and return a shareable demo URL."""

    source = Path(file_path)
    destination_dir = Path(public_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    shutil.copy2(source, destination)

    if public_base_url:
        url = public_base_url.rstrip("/") + "/" + quote(destination.name)
    else:
        url = destination.resolve().as_uri()

    return UploadResult(url=url, public_path=destination)


def render_markdown(content: ContentBundle, evaluation: EvaluationResult) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    thread = "\n".join(f"{index}. {tweet}" for index, tweet in enumerate(content.twitter_thread, start=1))

    return "\n\n".join(
        [
            "# Agent: Content Pipeline Output",
            f"Generated at: {generated_at}",
            "## Quality Evaluation",
            f"- Overall score: {evaluation.overall}/10",
            f"- Clarity: {evaluation.clarity}/10",
            f"- Engagement: {evaluation.engagement}/10",
            f"- Branding: {evaluation.branding}/10",
            "## Blog Post",
            content.blog_post,
            "## LinkedIn Post",
            content.linkedin_post,
            "## Twitter Thread",
            thread,
            "## Newsletter",
            content.newsletter,
        ]
    )


def _markdown_to_pdf_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        line = line.replace("# ", "").replace("## ", "").replace("- ", "  - ")
        lines.extend(textwrap.wrap(line, width=88) or [""])
    return lines


def _write_simple_pdf(path: Path, lines: list[str]) -> None:
    page_line_limit = 47
    pages = [lines[index : index + page_line_limit] for index in range(0, len(lines), page_line_limit)]
    if not pages:
        pages = [["No content generated."]]

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    font_obj_number = 3
    first_page_obj_number = 4
    kids = []
    for page_index in range(len(pages)):
        page_obj_number = first_page_obj_number + page_index * 2
        kids.append(f"{page_obj_number} 0 R")
    objects.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_index, page_lines in enumerate(pages):
        page_obj_number = first_page_obj_number + page_index * 2
        content_obj_number = page_obj_number + 1
        stream = _pdf_text_stream(page_lines)
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj_number} 0 R >> >> "
            f"/Contents {content_obj_number} 0 R >>"
        )
        content_obj = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        objects.append(page_obj.encode("latin-1"))
        objects.append(content_obj)

    _assemble_pdf(path, objects)


def _pdf_text_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "72 740 Td", "14 TL"]
    for line in lines:
        safe_line = _escape_pdf_text(line)
        commands.append(f"({safe_line}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _escape_pdf_text(value: str) -> str:
    encoded = value.encode("latin-1", errors="replace").decode("latin-1")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _assemble_pdf(path: Path, objects: list[bytes]) -> None:
    content = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("latin-1"))
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )
    path.write_bytes(bytes(content))
