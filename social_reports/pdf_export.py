"""PDF export using fpdf2 with ValueWats brand identity.

Converts the markdown report to a styled PDF with brand colors,
logo header, and clean typography.
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

logger = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).resolve().parent.parent / "value logo.png"

# Brand Colors (RGB tuples)
BG_DARK    = (35, 35, 24)
LIME       = (226, 243, 0)
TEXT_CREAM = (255, 254, 217)
OLIVE      = (122, 120, 57)
MUTED      = (183, 181, 126)
CARD_BG    = (42, 42, 31)
WHITE      = (255, 255, 255)
BLACK      = (20, 20, 20)
RED_ACC    = (239, 68, 68)
GREEN_ACC  = (16, 185, 129)


class BrandedPDF(FPDF):
    """FPDF subclass with ValueWats branded header/footer."""

    def __init__(self, client_name: str = "", period: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.client_name = client_name
        self.period = period
        self.set_auto_page_break(auto=True, margin=20)

        # Register a Unicode font for Arabic support
        # fpdf2 ships with built-in Unicode support via standard fonts
        self.add_page()

    def header(self):
        # Dark header bar
        self.set_fill_color(*BG_DARK)
        self.rect(0, 0, 210, 18, "F")

        # Lime accent line
        self.set_fill_color(*LIME)
        self.rect(0, 18, 210, 1, "F")

        # Logo (if exists)
        if LOGO_PATH.exists():
            try:
                self.image(str(LOGO_PATH), x=5, y=2, h=14)
            except Exception:
                pass

        # Client name
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEXT_CREAM)
        self.set_xy(140, 4)
        self.cell(65, 5, self.client_name, align="R")

        # Period
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.set_xy(140, 10)
        self.cell(65, 5, self.period, align="R")

        self.ln(22)

    def footer(self):
        self.set_y(-15)
        # Footer bar
        self.set_fill_color(*BG_DARK)
        self.rect(0, self.h - 12, 210, 12, "F")
        self.set_fill_color(*LIME)
        self.rect(0, self.h - 12, 210, 0.5, "F")

        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Value Marketing Solutions | Page {self.page_no()}/{{nb}}", align="C")


def _parse_markdown_to_pdf(pdf: BrandedPDF, markdown: str):
    """Parse markdown content and render it to the PDF."""

    lines = markdown.split("\n")
    in_table = False
    table_rows: list[list[str]] = []
    table_headers: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            if in_table and table_headers:
                _render_table(pdf, table_headers, table_rows)
                in_table = False
                table_rows = []
                table_headers = []
            pdf.ln(3)
            continue

        # Table rows
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            # Skip separator row
            if all(c.replace("-", "").replace(":", "").strip() == "" for c in cells):
                continue
            if not in_table:
                table_headers = cells
                in_table = True
            else:
                table_rows.append(cells)
            continue

        # Flush any pending table
        if in_table and table_headers:
            _render_table(pdf, table_headers, table_rows)
            in_table = False
            table_rows = []
            table_headers = []

        # Headings
        if stripped.startswith("# ") and not stripped.startswith("## "):
            text = stripped.lstrip("# ").strip()
            pdf.set_font("Helvetica", "B", 20)
            pdf.set_text_color(*BG_DARK)
            pdf.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")
            # Lime underline
            pdf.set_fill_color(*LIME)
            pdf.rect(pdf.l_margin, pdf.get_y(), 50, 1, "F")
            pdf.ln(4)
            continue

        if stripped.startswith("## "):
            text = stripped.lstrip("# ").strip()
            pdf.set_font("Helvetica", "B", 15)
            pdf.set_text_color(*BG_DARK)
            pdf.ln(4)
            pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
            # Olive underline
            pdf.set_fill_color(*OLIVE)
            pdf.rect(pdf.l_margin, pdf.get_y(), 35, 0.5, "F")
            pdf.ln(3)
            continue

        if stripped.startswith("### "):
            text = stripped.lstrip("# ").strip()
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*OLIVE)
            pdf.ln(2)
            pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        # Bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:].strip()
            # Clean markdown links
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*BLACK)
            pdf.set_x(pdf.l_margin + 4)
            # Lime bullet
            pdf.set_fill_color(*LIME)
            pdf.rect(pdf.get_x() - 3, pdf.get_y() + 2.5, 1.5, 1.5, "F")
            pdf.multi_cell(0, 5, f"  {text}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        # Numbered items
        num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if num_match:
            num, text = num_match.group(1), num_match.group(2)
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*LIME)
            pdf.set_x(pdf.l_margin + 2)
            pdf.cell(8, 5, f"{num}.")
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*BLACK)
            pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        # Code blocks / inline code
        if stripped.startswith("`") and stripped.endswith("`"):
            text = stripped.strip("`")
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(*OLIVE)
            pdf.cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
            continue

        # Regular paragraph
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', stripped)
        text = text.replace("`", "")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*BLACK)
        pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    # Flush last table
    if in_table and table_headers:
        _render_table(pdf, table_headers, table_rows)


def _render_table(pdf: BrandedPDF, headers: list[str], rows: list[list[str]]):
    """Render a table with branded styling."""
    n_cols = len(headers)
    if n_cols == 0:
        return

    available = 190 - pdf.l_margin
    col_w = available / n_cols
    col_w = min(col_w, 45)
    row_h = 6

    # Check if table fits on current page
    needed = row_h * (len(rows) + 1) + 5
    if pdf.get_y() + needed > pdf.h - 25:
        pdf.add_page()

    # Header row
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*LIME)
    pdf.set_text_color(*BG_DARK)
    for header in headers:
        pdf.cell(col_w, row_h, header[:20], border=0, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 8)
    for i, row in enumerate(rows[:15]):
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 235)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(*BLACK)
        for j, cell in enumerate(row):
            text = str(cell)[:25]
            pdf.cell(col_w, row_h, text, border=0, fill=True)
        pdf.ln()

    pdf.ln(3)


def generate_pdf_from_markdown(
    markdown_content: str,
    output_path: Path,
    client_name: str = "",
    period: str = "",
) -> bool:
    """Generate a branded PDF from markdown report content."""
    if not FPDF_AVAILABLE:
        logger.warning("fpdf2 is not installed. Skipping PDF generation.")
        return False

    try:
        pdf = BrandedPDF(client_name=client_name, period=period)
        pdf.alias_nb_pages()
        _parse_markdown_to_pdf(pdf, markdown_content)
        pdf.output(str(output_path))
        logger.info(f"PDF saved to {output_path}")
        return True
    except Exception as error:
        logger.error(f"PDF generation failed: {error}")
        return False
