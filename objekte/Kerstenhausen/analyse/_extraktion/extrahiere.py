# -*- coding: utf-8 -*-
"""Extrahiert Text aus den Kerstenhausen-PDFs (pypdf)."""
from pathlib import Path
import pypdf

BASE = Path(r"c:\Users\User\Meine Ablage\Immo\VS Code\Immo\objekte\Kerstenhausen\unterlagen")
OUT = Path(r"c:\Users\User\Meine Ablage\Immo\VS Code\Immo\objekte\Kerstenhausen\analyse\_extraktion")

for pdf in sorted(BASE.glob("*.pdf")):
    r = pypdf.PdfReader(str(pdf))
    n = len(r.pages)
    text = "\n\n".join((p.extract_text() or "") for p in r.pages)
    name = "pdf1.txt" if pdf.name.startswith("0ce7") else "pdf2.txt"
    (OUT / name).write_text(f"=== {pdf.name} ({n} Seiten, {len(text)} Zeichen Text) ===\n\n{text}", encoding="utf-8")
    print(f"{pdf.name}: {n} Seiten, {len(text)} Zeichen extrahiert -> {name}")