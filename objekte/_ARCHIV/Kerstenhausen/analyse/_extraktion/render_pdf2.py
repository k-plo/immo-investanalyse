# -*- coding: utf-8 -*-
"""Rendert pdf2 (8 Seiten, gescannt) als PNGs für visuelle Analyse (pymupdf, dpi 150)."""
from pathlib import Path
import fitz  # pymupdf

BASE = Path(__file__).resolve().parents[2] / "unterlagen"
OUT = Path(__file__).resolve().parent

pdf = next(p for p in BASE.glob("*.pdf") if p.name.startswith("2a2b"))
doc = fitz.open(str(pdf))
for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=150)
    pix.save(str(OUT / f"pdf2_seite{i}.png"))
    print(f"Seite {i} gerendert ({pix.width}x{pix.height})")
