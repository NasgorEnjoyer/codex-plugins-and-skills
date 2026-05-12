#!/usr/bin/env python3
"""Render a DOCX to PDF and optional PNG page previews through LibreOffice."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_soffice(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def convert_to_pdf(docx: Path, output_dir: Path, soffice: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(docx),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "LibreOffice conversion failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    pdf = output_dir / f"{docx.stem}.pdf"
    if not pdf.exists():
        matches = sorted(output_dir.glob("*.pdf"))
        if not matches:
            raise RuntimeError("LibreOffice completed but no PDF was produced")
        pdf = matches[-1]
    return pdf


def render_png_pages(pdf: Path, output_dir: Path, dpi: int) -> list[Path]:
    try:
        import fitz  # type: ignore
    except Exception:
        return []

    page_paths: list[Path] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    document = fitz.open(pdf)
    try:
        for index, page in enumerate(document, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            page_path = output_dir / f"{pdf.stem}-page-{index:03d}.png"
            pix.save(page_path)
            page_paths.append(page_path)
    finally:
        document.close()
    return page_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path, help="DOCX file to render")
    parser.add_argument("--output-dir", type=Path, default=Path("rendered-docx"), help="Directory for rendered files")
    parser.add_argument("--soffice", help="Path to soffice/libreoffice executable")
    parser.add_argument("--dpi", type=int, default=144, help="PNG render DPI when PyMuPDF is installed")
    parser.add_argument("--pdf-only", action="store_true", help="Skip PNG preview rendering")
    args = parser.parse_args()

    soffice = find_soffice(args.soffice)
    if not soffice:
        print("error: LibreOffice soffice executable was not found", file=sys.stderr)
        return 1

    try:
        pdf = convert_to_pdf(args.docx, args.output_dir, soffice)
        pages = [] if args.pdf_only else render_png_pages(pdf, args.output_dir, args.dpi)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"pdf: {pdf}")
    if args.pdf_only:
        return 0
    if pages:
        print("png_pages:")
        for page in pages:
            print(f"  {page}")
    else:
        print("png_pages: not rendered; install PyMuPDF to enable page PNG output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
