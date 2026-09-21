# -*- coding: utf-8 -*-
"""Liest die Ebay-Kleinanzeigen-Beschreibung (docx) aus."""
from pathlib import Path
import zipfile
import re

p = Path(r"c:\Users\User\Meine Ablage\Immo\VS Code\Immo\objekte\Kerstenhausen\unterlagen\Beschreibung Ebay Kleinanzeigen.docx")
with zipfile.ZipFile(p) as z:
    xml = z.read("word/document.xml").decode("utf-8")
# Absätze trennen
xml = re.sub(r"</w:p>", "\n", xml)
text = re.sub(r"<[^>]+>", "", xml)
import html
text = html.unescape(text)
out = p.parent.parent / "analyse" / "_extraktion" / "ebay_beschreibung.txt"
out.write_text(text, encoding="utf-8")
print(f"{len(text)} Zeichen extrahiert -> {out.name}")