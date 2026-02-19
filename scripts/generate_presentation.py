#!/usr/bin/env python3
"""
Generate PDF presentation from PRESENTATION.md

Usage:
    pip install markdown weasyprint
    python scripts/generate_presentation.py

Or manually convert:
    pandoc docs/PRESENTATION.md -o docs/presentation.pdf
"""

import sys
from pathlib import Path

PRESENTATION_MD = Path(__file__).parent.parent / "docs" / "PRESENTATION.md"
OUTPUT_PDF = Path(__file__).parent.parent / "docs" / "presentation.pdf"
OUTPUT_HTML = Path(__file__).parent.parent / "docs" / "presentation.html"


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Smart Receipts AI - Presentation</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 1cm;
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            max-width: 100%;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            page-break-before: always;
        }}
        h1:first-of-type {{
            page-break-before: avoid;
        }}
        h2 {{
            color: #34495e;
            margin-top: 20px;
        }}
        h3 {{
            color: #7f8c8d;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        hr {{
            border: none;
            border-top: 2px solid #3498db;
            margin: 30px 0;
            page-break-after: always;
        }}
        ul, ol {{
            margin: 10px 0;
            padding-left: 25px;
        }}
        li {{
            margin: 5px 0;
        }}
        .slide {{
            page-break-after: always;
            min-height: 90vh;
        }}
    </style>
</head>
<body>
{content}
</body>
</html>
"""


def convert_md_to_html(md_content: str) -> str:
    """Convert markdown to HTML."""
    try:
        import markdown
        html = markdown.markdown(
            md_content,
            extensions=['tables', 'fenced_code', 'codehilite']
        )
        return html
    except ImportError:
        print("markdown package not installed. Using basic conversion.")
        return f"<pre>{md_content}</pre>"


def generate_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Generate PDF from HTML using weasyprint."""
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True
    except ImportError:
        print("weasyprint not installed. Skipping PDF generation.")
        print("Install with: pip install weasyprint")
        return False
    except Exception as e:
        print(f"PDF generation failed: {e}")
        return False


def main():
    if not PRESENTATION_MD.exists():
        print(f"ERROR: {PRESENTATION_MD} not found")
        sys.exit(1)

    print(f"Reading: {PRESENTATION_MD}")
    md_content = PRESENTATION_MD.read_text()

    print("Converting to HTML...")
    html_content = convert_md_to_html(md_content)
    full_html = HTML_TEMPLATE.format(content=html_content)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(full_html)
    print(f"HTML saved: {OUTPUT_HTML}")

    print("Generating PDF...")
    if generate_pdf(OUTPUT_HTML, OUTPUT_PDF):
        print(f"PDF saved: {OUTPUT_PDF}")
    else:
        print("\nAlternative: Use pandoc to generate PDF:")
        print(f"  pandoc {PRESENTATION_MD} -o {OUTPUT_PDF}")
        print("\nOr open the HTML file in a browser and print to PDF:")
        print(f"  {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
