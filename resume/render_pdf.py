"""Render the DeLibero resume markdown files to clean, ATS-safe PDFs.

Not a general markdown-to-PDF tool — tailored to this resume's specific
structure (name/contact header, ## section headings, **bold** run-in labels,
- bullets, plain paragraph lines).
"""
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

NAME_STYLE = ParagraphStyle("name", fontName=FONT_BOLD, fontSize=15.5, alignment=TA_CENTER, spaceAfter=13)
CONTACT_STYLE = ParagraphStyle("contact", fontName=FONT, fontSize=8.5, alignment=TA_CENTER, spaceAfter=6)
HEADING_STYLE = ParagraphStyle("heading", fontName=FONT_BOLD, fontSize=10.5, spaceBefore=6, spaceAfter=2, textColor="#1a1a1a")
BODY_STYLE = ParagraphStyle("body", fontName=FONT, fontSize=8.7, leading=11, spaceAfter=1.5)
BULLET_STYLE = ParagraphStyle("bullet", fontName=FONT, fontSize=8.7, leading=11, leftIndent=14, spaceAfter=1.5, bulletIndent=2)


def inline_markdown_to_html(text: str) -> str:
    # Escape XML special chars first — reportlab Paragraphs parse their input
    # as markup, so a raw "&" (e.g. "H&H Diesel") corrupts rendering otherwise.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # **bold** -> <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # [label](url) -> <link href="url">label</link>
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<link href="\2">\1</link>', text)
    return text


def render(md_path: Path, pdf_path: Path):
    lines = md_path.read_text().splitlines()
    story = []

    # First non-empty line = name, second = contact line
    body_lines = [l for l in lines if l.strip() != ""]
    name, contact, *rest = body_lines

    story.append(Paragraph(inline_markdown_to_html(name), NAME_STYLE))
    story.append(Paragraph(inline_markdown_to_html(contact), CONTACT_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.75, color="#666666", spaceAfter=8))

    for line in rest:
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline_markdown_to_html(line[3:].upper()), HEADING_STYLE))
        elif line.startswith("- "):
            story.append(Paragraph("&bull;&nbsp;&nbsp;" + inline_markdown_to_html(line[2:]), BULLET_STYLE))
        else:
            story.append(Paragraph(inline_markdown_to_html(line), BODY_STYLE))

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=LETTER,
        topMargin=0.4 * inch, bottomMargin=0.4 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        title=md_path.stem,
    )
    doc.build(story)
    print(f"wrote {pdf_path}")


if __name__ == "__main__":
    here = Path(__file__).parent
    for name in ["DeLibero_Resume_personality", "DeLibero_Resume_formal"]:
        render(here / f"{name}.md", here / f"{name}.pdf")
