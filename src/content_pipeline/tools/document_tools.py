from __future__ import annotations

import re
import shutil
import textwrap
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from ..models import ContentBundle, DocumentArtifact, EvaluationResult, UploadResult

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - optional runtime dependency
    REPORTLAB_AVAILABLE = False


def create_document(
    content: ContentBundle,
    evaluation: EvaluationResult,
    output_dir: Path | str,
    run_id: str,
    title_hint: str | None = None,
    summary_hint: str | None = None,
    prefer_title_hint: bool = False,
) -> DocumentArtifact:
    """Create a Markdown copy and a small text-based PDF for demo sharing."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    inferred_title = _infer_document_title(content)
    effective_title = title_hint if prefer_title_hint and title_hint else inferred_title or title_hint or ""
    document_title = _normalize_document_title(effective_title)
    document_summary = _normalize_document_summary(summary_hint or _infer_document_summary(content))
    stem, download_name = _build_document_names(document_title, run_id)
    markdown_path = directory / f"{stem}.md"
    pdf_path = directory / f"{stem}.pdf"

    markdown = render_markdown(content, evaluation, document_title, document_summary)
    markdown_path.write_text(markdown, encoding="utf-8")
    if REPORTLAB_AVAILABLE:
        _write_rich_pdf(pdf_path, content, evaluation, document_title, document_summary)
    else:
        _write_simple_pdf(pdf_path, _markdown_to_pdf_lines(markdown))

    return DocumentArtifact(
        path=pdf_path,
        markdown_path=markdown_path,
        format="pdf",
        download_name=download_name,
    )


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


def render_markdown(
    content: ContentBundle,
    evaluation: EvaluationResult,
    document_title: str,
    document_summary: str,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    thread = "\n".join(f"{index}. {tweet}" for index, tweet in enumerate(content.twitter_thread, start=1))

    return "\n\n".join(
        [
            f"# {document_title}",
            document_summary,
            f"Gerado em: {generated_at}",
            "## Avaliacao de Qualidade",
            f"- Pontuacao global: {evaluation.overall}/10",
            f"- Clareza: {evaluation.clarity}/10",
            f"- Engagement: {evaluation.engagement}/10",
            f"- Branding: {evaluation.branding}/10",
            "## Artigo para Blog",
            content.blog_post,
            "## Publicacao para LinkedIn",
            content.linkedin_post,
            "## Thread para X/Twitter",
            thread,
            "## Newsletter",
            content.newsletter,
        ]
    )


def _write_rich_pdf(
    path: Path,
    content: ContentBundle,
    evaluation: EvaluationResult,
    document_title: str,
    document_summary: str,
) -> None:
    styles = _build_pdf_styles()
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=document_title,
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story = [
        Paragraph(escape(document_title), styles["title"]),
        Spacer(1, 4 * mm),
        Paragraph(escape(document_summary), styles["subtitle"]),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Documento gerado automaticamente a partir de um unico input.<br/>Gerado em {generated_at}",
            styles["meta"],
        ),
        Spacer(1, 7 * mm),
        Paragraph("Avaliacao de Qualidade", styles["section"]),
        Spacer(1, 2 * mm),
        _build_score_table(evaluation, styles),
        Spacer(1, 6 * mm),
    ]

    sections = [
        ("Artigo para Blog", content.blog_post),
        ("Publicacao para LinkedIn", content.linkedin_post),
        ("Thread para X/Twitter", "\n".join(f"{idx}. {tweet}" for idx, tweet in enumerate(content.twitter_thread, start=1))),
        ("Newsletter", content.newsletter),
    ]

    for index, (title, body) in enumerate(sections):
        story.extend(_render_section(title, body, styles))
        if index != len(sections) - 1:
            story.append(Spacer(1, 4 * mm))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#D0D7E2")))
            story.append(Spacer(1, 4 * mm))

    document.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)


def _build_pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AgentTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#14213D"),
            spaceAfter=0,
        ),
        "subtitle": ParagraphStyle(
            "AgentSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4F5D75"),
        ),
        "meta": ParagraphStyle(
            "AgentMeta",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6B7280"),
        ),
        "section": ParagraphStyle(
            "AgentSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#1F3A5F"),
            spaceAfter=4,
        ),
        "subheading": ParagraphStyle(
            "AgentSubheading",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=colors.HexColor("#203047"),
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "AgentBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "AgentBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            leftIndent=12,
            firstLineIndent=0,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=2,
        ),
    }


def _build_score_table(
    evaluation: EvaluationResult,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        ["Metrica", "Score"],
        ["Overall", f"{evaluation.overall}/10"],
        ["Clareza", f"{evaluation.clarity}/10"],
        ["Engagement", f"{evaluation.engagement}/10"],
        ["Branding", f"{evaluation.branding}/10"],
    ]
    table = Table(rows, colWidths=[95 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F7F9FC"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CDD5DF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CDD5DF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _render_section(
    title: str,
    body: str,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    blocks: list[object] = [Paragraph(title, styles["section"]), Spacer(1, 1.5 * mm)]
    for chunk in _split_blocks(body):
        if chunk.startswith("#"):
            blocks.append(Paragraph(escape(chunk.lstrip("# ").strip()), styles["subheading"]))
            continue

        if _is_bullet_block(chunk):
            for line in chunk.splitlines():
                bullet_text = line.strip()[2:].strip()
                if bullet_text:
                    blocks.append(Paragraph(f"&bull; {escape(bullet_text)}", styles["bullet"]))
            continue

        formatted = escape(chunk).replace("\n", "<br/>")
        blocks.append(Paragraph(formatted, styles["body"]))
    return blocks


def _split_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    return blocks or ["Sem conteudo gerado."]


def _is_bullet_block(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(line.startswith("- ") for line in lines)


def _draw_page_footer(canvas: object, document: object) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(195 * mm, 10 * mm, f"Pagina {canvas.getPageNumber()}")
    canvas.restoreState()


def _infer_document_title(content: ContentBundle) -> str:
    lines = [line.strip() for line in content.blog_post.splitlines() if line.strip()]
    if not lines:
        return "Documento Content Pipeline"

    first_line = lines[0]
    if first_line.startswith("#"):
        return first_line.lstrip("# ").strip()
    return "Documento Content Pipeline"


def _infer_document_summary(content: ContentBundle) -> str:
    lines = [line.strip() for line in content.blog_post.splitlines() if line.strip()]
    for line in lines[1:]:
        if line.startswith("#") or line.startswith("##"):
            continue
        if line.startswith("- "):
            continue
        return _normalize_document_summary(line)

    newsletter_lines = [line.strip() for line in content.newsletter.splitlines() if line.strip()]
    for line in newsletter_lines:
        if ":" in line and len(line.split(":", 1)[0]) <= 12:
            continue
        return _normalize_document_summary(line)

    return "Documento final preparado a partir do tema recebido."


def _build_document_names(title: str, run_id: str) -> tuple[str, str]:
    normalized_title = _normalize_document_title(title)
    slug = _slugify_filename(normalized_title) or "documento-content-pipeline"
    short_run_id = run_id.split("-")[-1]
    file_stem = f"{slug}-{short_run_id}"
    download_name = f"{slug}.pdf"
    return file_stem, download_name


def _normalize_document_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip(" -_")
    return cleaned[:80] if cleaned else "Documento Content Pipeline"


def _normalize_document_summary(summary: str) -> str:
    cleaned = re.sub(r"\s+", " ", summary).strip(" -_")
    if not cleaned:
        return "Documento final preparado a partir do tema recebido."
    return textwrap.shorten(cleaned, width=180, placeholder="...")


def _slugify_filename(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return ascii_value[:60].strip("-")


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
