"""Assemble the plan: parts/*.html + generated figures + computed values -> HTML -> PDF.
Two passes: pass 1 renders, pdftotext finds each section's page, pass 2 writes the contents page numbers."""
import glob, os, re, subprocess, sys
from calc import V
from svgkit import REG
import figs_a, figs_b, figs_c   # noqa: F401  (registers figures)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
TITLE = "Windshield AR HUD plan · revision 2 · PDF edition"

CSS = """
@page { size: Letter; }
*{box-sizing:border-box}
html{color-scheme:light}
body{margin:0;background:#fff;color:#0b0b0b;font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-size:10.5pt;line-height:1.5;-webkit-print-color-adjust:exact;print-color-adjust:exact}
main{width:680px;margin:0 auto}
h1,h2,h3,h4{font-family:inherit;margin:0;text-wrap:balance}
h2{font-size:21pt;font-weight:700;letter-spacing:-.01em;break-before:page;break-after:avoid;padding:0 0 9px;margin:0 0 14px;border-bottom:1.5px solid #0b7a5c}
h2 .num{color:#0b7a5c;margin-right:8px;font-variant-numeric:tabular-nums}
h3{font-size:13pt;font-weight:600;margin:20px 0 6px;break-after:avoid}
h4{font-size:11pt;font-weight:600;margin:14px 0 4px;break-after:avoid}
p{margin:6px 0;orphans:3;widows:3}
ul,ol{padding-left:20px;margin:6px 0}
li{margin:3px 0}
code{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-size:9.2pt;background:#f2f1ed;padding:0 3px;border-radius:3px}
.lede{font-size:12.5pt;line-height:1.5}
.eyebrow{font-size:8.5pt;text-transform:uppercase;letter-spacing:.12em;color:#52514e;font-weight:500}
table{width:100%;border-collapse:collapse;font-size:9.3pt;margin:8px 0 4px}
thead{display:table-header-group}
tr{break-inside:avoid}
th,td{padding:5px 7px;text-align:left;vertical-align:top;border-bottom:1px solid #e1e0d9}
th{font-size:8pt;text-transform:uppercase;letter-spacing:.05em;color:#52514e;font-weight:600;border-bottom:1.2px solid #c3c2b7;background:#f7f7f4}
td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
figure{margin:14px 0 12px;break-inside:avoid}
figure svg{display:block;width:100%;height:auto}
figcaption{font-size:9pt;color:#52514e;margin-top:6px;line-height:1.4}
figcaption b{color:#0b0b0b}
.callout{border-left:3px solid #0b7a5c;background:#e8f3ef;padding:9px 14px;margin:14px 0;break-inside:avoid;border-radius:0 5px 5px 0}
.callout.warn{border-color:#9a5b00;background:#fbf3e6}
.callout.fix{border-color:#d03b3b;background:#fbeeee}
.callout p{margin:3px 0}
.callout .h{font-weight:700;margin-bottom:2px}
.tag{display:inline-block;font-size:7.5pt;text-transform:uppercase;letter-spacing:.07em;font-weight:600;padding:1px 5px;border-radius:3px;background:#e1e0d9;color:#0b0b0b;vertical-align:1px}
.tag.fix{background:#d03b3b;color:#fff}
.tag.acc{background:#0b7a5c;color:#fff}
.small{font-size:9pt;color:#52514e}
.muted{color:#52514e}
.phase{display:grid;grid-template-columns:105px 1fr;gap:4px 16px;break-inside:avoid;border-top:1px solid #e1e0d9;padding:10px 0}
.phase .when{font-size:9pt;color:#52514e;font-variant-numeric:tabular-nums;padding-top:2px}
.phase h4{margin:0 0 4px}
.kpi{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
.kpi div{border-top:2px solid #0b7a5c;padding-top:7px;break-inside:avoid}
.kpi .v{font-size:22pt;font-weight:600;letter-spacing:-.01em;line-height:1.1}
.kpi .l{font-size:9pt;color:#52514e;margin-top:3px;line-height:1.35}
.formula{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-size:9.1pt;background:#f7f7f4;padding:7px 12px;border-radius:4px;margin:7px 0;break-inside:avoid;white-space:pre-wrap;line-height:1.42}
.cover{height:900px;break-after:page;position:relative}
.cover .band{height:10px;background:#0b7a5c;margin:0 0 40px}
.cover h1{font-size:46pt;line-height:1.02;letter-spacing:-.025em;font-weight:700}
.cover .sub{font-size:14pt;color:#52514e;margin-top:14px;line-height:1.45}
.cover .meta{font-size:9.5pt;color:#52514e;margin-top:22px;line-height:1.5}
.cover figure{margin:30px 0 0}
.toc ol{list-style:none;padding:0;margin:0}
.toc li{display:flex;align-items:baseline;gap:8px;padding:3px 0;border-bottom:1px dotted #c3c2b7;font-size:10.2pt}
.toc li.sub1{padding-left:26px;font-size:9.8pt;color:#52514e;border-bottom:none;padding-top:1px;padding-bottom:1px}
.toc .n{width:30px;color:#52514e;font-variant-numeric:tabular-nums;flex:none}
.toc .t{flex:1}
.toc .p{flex:none;color:#52514e;font-variant-numeric:tabular-nums}
.toc a{color:#0b0b0b;text-decoration:none}
.toc h3{margin:12px 0 0}
a{color:#0b7a5c;text-decoration:none}
dl{margin:6px 0}
dt{font-weight:600;margin-top:6px}
dd{margin:1px 0 0 0}
.glossary dt{display:inline}
.glossary dd{display:inline;margin:0}
.glossary div{margin:5px 0;break-inside:avoid}
.noprint{}
"""

def fill_figs(html):
    def rep(m):
        name = m.group(1)
        if name not in REG:
            raise SystemExit(f"unknown figure {name}")
        return REG[name]().render()
    return re.sub(r"\[\[FIG ([\w]+)\]\]", rep, html)

def fill_vals(html):
    missing = set()
    def rep(m):
        k = m.group(1)
        if k not in V:
            missing.add(k)
            return "??"
        return str(V[k])
    out = re.sub(r"\{\{(\w+)\}\}", rep, html)
    if missing:
        raise SystemExit(f"missing values: {sorted(missing)}")
    return out

def read_parts():
    names = sorted(glob.glob(os.path.join(HERE, "parts", "*.html")))
    text = "\n".join(open(n, encoding="utf-8").read() for n in names)
    # a plain space after each heading number, so PDF bookmarks read "1 Recommendation"
    return re.sub(r'(<h2 id="[^"]+"><span class="num">[^<]*</span>)', r"\1 ", text)

HEAD_RE = re.compile(r'<h2 id="([\w-]+)"><span class="num">([^<]*)</span>(.*?)</h2>', re.S)

def toc_html(pages):
    body = read_parts()
    items = []
    for hid, num, title in HEAD_RE.findall(body):
        t = re.sub(r"<[^>]+>", "", title).strip()
        pg = pages.get(hid, "") if pages else ""
        items.append(f'<li><span class="n">{num}</span><a class="t" href="#{hid}">{t}</a><span class="p">{pg}</span></li>')
    return ('<div class="toc" style="margin-top:22px"><div class="eyebrow">Contents</div><ol>' + "".join(items) + "</ol></div>")

def assemble(pages=None):
    body = read_parts()
    body = body.replace("[[TOC]]", toc_html(pages))
    body = fill_figs(body)
    body = fill_vals(body)
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Windshield AR HUD Plan</title><style>' + CSS + '</style></head>'
            '<body><main>' + body + '</main></body></html>')
    return html

def render(html_path, pdf_path):
    subprocess.run(["node", os.path.join(HERE, "render.js"), html_path, pdf_path, TITLE], check=True)

def find_pages(pdf_path, ids_titles):
    txt = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True, check=True).stdout
    pages = txt.split("\f")
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    npages = [norm(p) for p in pages]
    found = {}
    # the contents page starts with its own "Contents" label; search only after it,
    # and only near the top of each page, so the contents entries never match
    toc_pages = [i for i, p in enumerate(npages) if p.upper().startswith("CONTENTS")]
    start = (toc_pages[0] + 1) if toc_pages else 0
    for hid, num, title in ids_titles:
        key = norm(f"{num} {title}")[:30]
        for i in range(start, len(npages)):
            if key and key in npages[i][:90]:
                found[hid] = str(i + 1)
                start = i
                break
    return found, len(pages) - (1 if pages and not pages[-1].strip() else 0)

def main():
    html_path = os.path.join(OUT, "plan.html")
    pdf_path = os.path.join(OUT, "plan.pdf")
    pass1 = assemble(None)
    open(html_path, "w", encoding="utf-8").write(pass1)
    render(html_path, pdf_path)
    ids = [(hid, num, re.sub(r"<[^>]+>", "", t).strip()) for hid, num, t in HEAD_RE.findall(read_parts())]
    pages, npages = find_pages(pdf_path, ids)
    missing = [h for h, _, _ in ids if h not in pages]
    print("pass1 pages:", npages, "missing headings:", missing)
    html2 = assemble(pages)
    open(html_path, "w", encoding="utf-8").write(html2)
    render(html_path, pdf_path)
    pages2, n2 = find_pages(pdf_path, ids)
    print("pass2 pages:", n2, "stable:", pages2 == pages)

if __name__ == "__main__":
    main()
