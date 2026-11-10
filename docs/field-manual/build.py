#!/usr/bin/env python3
"""Re-render the public JUPI Field Manual and Digest PDFs from the markdown in this folder.

Requires: python-markdown (pip install markdown), Google Chrome/Chromium (headless print-to-pdf),
IBM Plex Serif/Sans/Mono fonts. Black and white only: do not add color to manual.css.
Usage: python3 build.py
"""
import pathlib, subprocess, shutil, markdown

HERE = pathlib.Path(__file__).resolve().parent
CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
FIT = ('<script>document.querySelectorAll("pre").forEach(function(p){var f=parseFloat(getComputedStyle(p).fontSize);'
       'while(p.scrollWidth>p.clientWidth+1&&f>5.6){f-=0.2;p.style.fontSize=f+"px";}});</script>')

def build(name, body_class, title):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "md_in_html", "attr_list", "sane_lists"])
    css = (HERE / "manual.css").read_text().replace('var(--hdr, "JUPI FIELD MANUAL")', f'"{title.upper()}"')
    body = md.convert((HERE / f"{name}.md").read_text())
    html = HERE / f".{name}.html"
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><style>{css}</style>'
                    f'</head><body class="{body_class}">{body}{FIT}</body></html>')
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=10000",
                    f"--print-to-pdf={HERE / (name + '.pdf')}", html.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    html.unlink()
    print("built", name + ".pdf")

if __name__ == "__main__":
    if not CHROME: raise SystemExit("need google-chrome or chromium on PATH")
    build("JUPI-Field-Manual", "manual", "JUPI Field Manual")
    build("JUPI-Field-Digest", "digest", "JUPI Field Digest")
