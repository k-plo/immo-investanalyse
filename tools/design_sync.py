"""Embed the shared visual layer in active, standalone property HTML files.

Run from any directory: python3 tools/design_sync.py
Archived snapshots and business logic are deliberately left untouched.
"""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent.parent
START = "<!-- SHARED-DESIGN:START -->"
END = "<!-- SHARED-DESIGN:END -->"

def main():
    css = (BASE / "assets/dashboard.css").read_text(encoding="utf-8")
    theme = (BASE / "assets/theme.js").read_text(encoding="utf-8")
    print_css = (BASE / "assets/print_report.css").read_text(encoding="utf-8")
    print_js = (BASE / "assets/print_report.js").read_text(encoding="utf-8")
    block = (f'{START}\n<style>\n{css}</style>\n'
             f'<style>\n{print_css}</style>\n'
             f'<script data-dashboard-theme>\n{theme}</script>\n'
             f'<script data-print-report>\n{print_js}</script>\n{END}')
    for path in sorted((BASE / "objekte").glob("*/*_Übersicht.html")):
        source = path.read_text(encoding="utf-8")
        if START in source:
            source = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, source, flags=re.S)
        else:
            source = source.replace("</head>", block + "\n</head>", 1)
        # Only static markup, never the JavaScript that populates these tables.
        markup, script = source.split("<script>", 1)
        if 'class="table-scroll"' not in markup:
            markup = re.sub(r"<table\b[^>]*>.*?</table>", lambda m: '<div class="table-scroll" tabindex="0" role="region" aria-label="Analysetabelle – horizontal scrollbar">' + m[0] + '</div>', markup, flags=re.S)
        path.write_text(markup + "<script>" + script, encoding="utf-8")
        print(path.relative_to(BASE))

if __name__ == "__main__":
    main()
