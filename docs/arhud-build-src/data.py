"""Tables and values the guide reads from the project's own data instead of retyping them:
the CAD housing (docs/arhud-cad/out/housing.json), the plan's cost list (calc.COST), and the optical layout the CAD
was built around (docs/arhud-cad/layout.json)."""
import json, os, subprocess
from html import escape

import calc

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
CAD = json.load(open(os.path.join(DOCS, "arhud-cad", "out", "housing.json")))
LAYOUT = json.load(open(os.path.join(DOCS, "arhud-cad", "layout.json")))


def _mm(x):
    return f"{x * 1000:.0f}"


# ---- values that are not in the plan's calc.V ----------------------------------------------------
L = LAYOUT
EXTRA = {
    "cad_size": " × ".join(str(v) for v in CAD["summary"]["sizeMm"]),
    "cad_len": str(CAD["summary"]["sizeMm"][0]),
    "cad_h": str(CAD["summary"]["sizeMm"][1]),
    "cad_w": str(CAD["summary"]["sizeMm"][2]),
    "cad_parts": str(CAD["summary"]["printedParts"]),
    "cad_pieces": str(CAD["summary"]["printedPieces"]),
    "cad_mass_kg": f"{CAD['summary']['printedMassG'] / 1000:.1f}",
    "cad_hours": str(CAD["summary"]["printHoursRough"]),
    "cad_fasteners": str(CAD["summary"]["fasteners"]),
    "cad_rays": str(CAD["checks"]["beam"]["rays"]),
    "cad_blocked": str(CAD["checks"]["beam"]["blocked"]),
    "cad_panel_rays": str(CAD["checks"]["beam"]["panel"]),
    "cad_glass_clear": f"{CAD['checks']['envelope']['glassClearMm']:.0f}",
    "cad_hood_clear": f"{CAD['checks']['envelope']['hoodClearMm']:.0f}",
    "cad_dash_clear": f"{CAD['checks']['envelope']['dashClearMm']:.0f}",
    "cad_nearest": f"{min(CAD['checks']['beam']['nearest'].values()):.1f}",
    "cad_glass_l": _mm(CAD["glass"]["L"]),
    "cad_glass_w": _mm(CAD["glass"]["W"]),
    "cad_shutter_l": _mm(CAD["shutter"]["L"]),
    "cad_shutter_w": _mm(CAD["shutter"]["W"]),
    "lay_rt": _mm(L["mirror"]["toroid"]["Rt"]),
    "lay_rs": _mm(L["mirror"]["toroid"]["Rs"]),
    "lay_inc": f"{L['mirror']['incDeg']:.1f}",
    "lay_fold_inc": f"{L['fold']['incDeg']:.0f}",
    "lay_fold_w": f"{(L['fold']['u1'] - L['fold']['u0']) * 1000:.0f}",
    "lay_fold_h": f"{(L['fold']['v1'] - L['fold']['v0']) * 1000:.0f}",
    "lay_fold_to_panel": _mm(L["fold"]["C"][1] - L["panel"]["C"][1]),
    "lay_ap_l": _mm(L["layout"]["L"]),
    "lay_ap_w": _mm(L["layout"]["W"]),
    "lay_eye_glass": "750",
    "lay_glass_mirror": "310",
    "lay_path": "1,060",
    "lay_bl_depth": f"{L['panel']['backlightDepth'] * 1000:.1f}",
}


# ---- tables ----------------------------------------------------------------------------------------
def _table(head, rows, cls="", widths=None, num=()):
    h = "".join(
        f'<th{" class=num" if i in num else ""}{f" style=width:{widths[i]}" if widths and widths[i] else ""}>{c}</th>'
        for i, c in enumerate(head))
    body = []
    for r in rows:
        body.append("<tr>" + "".join(
            f'<td{" class=num" if i in num else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>")
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def t_cost():
    rows = []
    for name, lo, hi, tag in calc.COST:
        price = f"${lo:,}" if lo == hi else f"${lo:,}–{hi:,}"
        rows.append([escape(name.replace(" x2", " ×2").replace(" x ", " × ")), price, tag])
    rows.append(["<b>Total of the listed ranges</b>", f"<b>${calc.V['cost_low']}–{calc.V['cost_high']}</b>", ""])
    return _table(["Item (plan list)", "Last seen, USD", "Basis"], rows, widths=["62%", "22%", ""], num=(1,))


def t_printed():
    rows = []
    for p in CAD["parts"]:
        if p["kind"] != "printed":
            continue
        pr = p["print"]
        bed = " × ".join(f"{v:.0f}" for v in pr["bedMm"])
        mat = "TPU 95A" if p["step"] == "grommets" and p["id"].startswith("grommet") else "ASA"
        rows.append([escape(p["name"]), str(p.get("qty", 1)), bed, pr["supports"], mat, f"{p['massG']:.0f}",
                     f"<code>{escape(pr['file'].split('/')[-1])}</code>"])
    return _table(["Part", "Qty", "Bed footprint, mm", "Supports", "Material", "g", "STL"], rows, cls="tight",
                  widths=["28%", "5%", "17%", "16%", "8%", "5%", ""], num=(1, 5))


def t_fasteners():
    rows = []
    for k, v in sorted(CAD["hardware"].items()):
        rows.append([escape(k), str(v)])
    return _table(["Fastener or fixing (from the CAD)", "Qty"], rows, cls="tight", widths=["80%", ""], num=(1,))


def cad_step(step_id):
    step = next(s for s in CAD["steps"] if s["id"] == step_id)
    parts = [p for p in CAD["parts"] if p["step"] == step_id]
    rows = []
    for p in parts:
        kind = {"printed": "printed", "hardware": "hardware", "bought": "bought", "sheet": "sheet metal"}[p["kind"]]
        spec = p.get("spec") or p.get("desc") or ""
        rows.append([escape(p["name"]), kind, str(p.get("qty", 1)), escape(spec)])
    if not rows:
        return ""
    return _table(["Item", "Kind", "Qty", "Specification"], rows, cls="tight", widths=["34%", "12%", "6%", ""], num=(2,))


def t_gpu():
    rows = [[escape(n), f"{a}–{b} ms", ""] for n, a, b in calc.GPU]
    rows.append(["<b>Serial total (plan estimate)</b>", f"<b>{calc.GPU_MIN}–{calc.GPU_MAX} ms</b>", ""])
    return _table(["Job on the GPU", "Plan estimate per frame", "Measured"], rows, widths=["55%", "25%", ""], num=(1, 2))


def t_lat():
    rows = [[escape(n), f"{a}–{b} ms", ""] for n, a, b in calc.LAT]
    rows.append(["<b>Total, uncompensated</b>", f"<b>{calc.LAT_MIN}–{calc.LAT_MAX} ms</b>", ""])
    return _table(["Stage of the chain", "Plan estimate", "Measured"], rows, widths=["55%", "25%", ""], num=(1, 2))


class _Tables(dict):
    def __contains__(self, k):
        return dict.__contains__(self, k) or k.startswith("cadstep_")

    def __getitem__(self, k):
        if k.startswith("cadstep_"):
            return lambda: cad_step(k[len("cadstep_"):])
        return dict.__getitem__(self, k)


TABLES = _Tables(cost=t_cost, printed=t_printed, fasteners=t_fasteners, gpu=t_gpu, lat=t_lat)


def cad_step_text(step_id):
    s = next(s for s in CAD["steps"] if s["id"] == step_id)
    return s["title"], s["text"]


# ---- images ----------------------------------------------------------------------------------------
def as_jpeg(path, outdir, width=1400):
    """Embed photos and renders as JPEG to keep the PDF small (sips is on every Mac)."""
    os.makedirs(os.path.join(outdir, "img"), exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path))
    dst = os.path.join(outdir, "img", f"{parent}-{base}.jpg")
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(path):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "--resampleWidth", str(width),
                        path, "--out", dst], check=True, capture_output=True)
    return dst
