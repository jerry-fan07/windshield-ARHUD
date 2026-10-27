"""Assemble the tabletop design: parts/*.html + figures + values + tables -> HTML -> PDF.

Numbers come from calc.py here, which imports the TFT plan's calc.py (../arhud-plan-tft-src) for everything shared.
Placeholders in the parts:
  {{key}}            a value from calc.V (the plan's own V is available underneath; local keys win)
  [[FIG name]]       an inline SVG figure from figs_tt.py
  [[TBL name]]       a table from tables.py
  [[TOC]]            the contents list (page numbers filled on the second pass)
Two passes: pass 1 renders, pdftotext finds each heading's page, pass 2 writes the page numbers."""
import glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DOCS, "arhud-plan-tft-src"))
sys.path.insert(0, HERE)
from svgkit import REG                  # noqa: E402
import tcalc as calc                    # noqa: E402
import figs_tt                          # noqa: E402,F401
import tables                           # noqa: E402

OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
TITLE = "Windshield AR HUD · Tabletop two-monitor design · 2026-10-27"

CSS = open(os.path.join(HERE, "style.css"), encoding="utf-8").read()


def fill_figs(html):
    def rep(m):
        name = m.group(1)
        if name not in REG:
            raise SystemExit(f"unknown figure {name}")
        return REG[name]().render()
    return re.sub(r"\[\[FIG ([\w]+)\]\]", rep, html)


def fill_tables(html):
    def rep(m):
        name = m.group(1)
        if name not in tables.TABLES:
            raise SystemExit(f"unknown table {name}")
        return tables.TABLES[name]()
    return re.sub(r"\[\[TBL ([\w]+)\]\]", rep, html)


def fill_vals(html):
    vals = dict(calc.P.V)
    vals.update(calc.V)
    missing = set()

    def rep(m):
        k = m.group(1)
        if k not in vals:
            missing.add(k)
            return "??"
        return str(vals[k])
    out = re.sub(r"\{\{(\w+)\}\}", rep, html)
    if missing:
        raise SystemExit(f"missing values: {sorted(missing)}")
    return out


def read_parts():
    names = sorted(glob.glob(os.path.join(HERE, "parts", "*.html")))
    text = "\n".join(open(n, encoding="utf-8").read() for n in names)
    return re.sub(r'(<h2 id="[^"]+"><span class="num">[^<]*</span>)', r"\1 ", text)


HEAD_RE = re.compile(r'<h2 id="([\w-]+)"><span class="num">([^<]*)</span>(.*?)</h2>', re.S)
PART_RE = re.compile(r'<div class="part" data-toc="([^"]+)">')


def toc_html(pages):
    body = read_parts()
    items = []
    marks = [(m.start(), "part", m.group(1)) for m in PART_RE.finditer(body)]
    marks += [(m.start(), "h2", m.groups()) for m in HEAD_RE.finditer(body)]
    for _, kind, g in sorted(marks, key=lambda t: t[0]):
        if kind == "part":
            items.append(f'<li class="pt">{g}</li>')
            continue
        hid, num, title = g
        t = re.sub(r"<[^>]+>", "", title).strip()
        pg = pages.get(hid, "") if pages else ""
        items.append(f'<li><span class="n">{num}</span><a class="t" href="#{hid}">{t}</a><span class="p">{pg}</span></li>')
    return '<div class="toc"><ol>' + "".join(items) + "</ol></div>"


def assemble(pages=None):
    body = read_parts()
    body = body.replace("[[TOC]]", toc_html(pages))
    body = fill_figs(body)
    body = fill_tables(body)
    body = fill_vals(body)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Windshield AR HUD Tabletop Design</title><style>' + CSS + '</style></head>'
            '<body><main>' + body + '</main></body></html>')


def render(html_path, pdf_path):
    subprocess.run(["node", os.path.join(HERE, "render.js"), html_path, pdf_path, TITLE], check=True)


def find_pages(pdf_path, ids_titles):
    txt = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, check=True).stdout
    pages = txt.split("\f")
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    npages = [norm(p) for p in pages]
    found = {}
    part1 = [i for i, p in enumerate(npages) if re.sub(r"\s", "", p).upper().startswith("PARTITHERIG")]
    start = part1[0] if part1 else 0
    for hid, num, title in ids_titles:
        key = norm(f"{num} {title}")[:30]
        for i in range(start, len(npages)):
            if key and key in npages[i][:90]:
                found[hid] = str(i + 1)
                start = i
                break
    return found, len(pages) - (1 if pages and not pages[-1].strip() else 0)


def main():
    html_path = os.path.join(OUT, "tabletop.html")
    pdf_path = os.path.join(OUT, "tabletop.pdf")
    open(html_path, "w", encoding="utf-8").write(assemble(None))
    render(html_path, pdf_path)
    ids = [(hid, num, re.sub(r"<[^>]+>", "", t).strip()) for hid, num, t in HEAD_RE.findall(read_parts())]
    pages, npages = find_pages(pdf_path, ids)
    missing = [h for h, _, _ in ids if h not in pages]
    print("pass1 pages:", npages, "missing headings:", missing)
    open(html_path, "w", encoding="utf-8").write(assemble(pages))
    render(html_path, pdf_path)
    pages2, n2 = find_pages(pdf_path, ids)
    print("pass2 pages:", n2, "stable:", pages2 == pages)


if __name__ == "__main__":
    main()
