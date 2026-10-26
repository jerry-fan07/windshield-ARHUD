"""Exports: STEP assembly, print-ready STL per printed part, DXF for the sheet parts, the simulator's GLB and
manifest, a bill of materials and the check report."""
import json
import math
import struct
from datetime import date
from pathlib import Path

import numpy as np

from . import geo as g
from . import internals as it
from . import shell as sh
from .assembly import STEPS
from .checks import mesh_of, print_orient
from .mesh import tessellate, write_glb

DENSITY = {"asa": 1.07, "tpu": 1.21}


def quat_from_matrix(R):
    """Unit quaternion (x, y, z, w) of a proper rotation matrix."""
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w, x, y, z = (m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w, x, y, z = (m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w, x, y, z = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s
    return [x, y, z, w]


def write_stl(path, P, I):
    tri = P[I]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = (n / ln).astype(np.float32)
    with open(path, "wb") as f:
        f.write(b"ARHUD housing, docs/arhud-cad".ljust(80, b" "))
        f.write(struct.pack("<I", len(I)))
        rec = np.zeros(len(I), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        rec["n"], rec["v"] = n, tri.astype(np.float32)
        f.write(rec.tobytes())


def leaf_dxf(path):
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    L = it.SL / 2 + 10.0
    W = it.LEAF_W
    y = 0.0
    for name in ("REAR", "FRONT"):
        msp.add_lwpolyline([(0, y), (L, y), (L, y + W), (0, y + W)], close=True, dxfattribs={"layer": "CUT"})
        if name == "FRONT":
            s = 9.5
            z0 = it.SG["pivot_z"] - (it.SL / 2 + 3.0) - 4.0 + W / 2
            z1 = it.SG["pivot_z"] + 4.0 + W / 2
            msp.add_lwpolyline([(s - 2.25, y + z0), (s + 2.25, y + z0), (s + 2.25, y + z1), (s - 2.25, y + z1)],
                               close=True, dxfattribs={"layer": "CUT"})
        msp.add_text(f"SHUTTER LEAF {name}  0.5 mm 5052 black anodised  {L:.1f} x {W:.1f}",
                     dxfattribs={"layer": "NOTE", "height": 4}).set_placement((5, y + W / 2))
        y += W + 15
    doc.saveas(path)


def export_all(parts, checks, out_dir, sim_dir):
    out_dir, sim_dir = Path(out_dir), Path(sim_dir)
    (out_dir / "stl").mkdir(parents=True, exist_ok=True)
    sim_dir.mkdir(parents=True, exist_ok=True)

    # ---- simulator GLB, one node per part, car frame in metres --------------------------------------------------
    meshes = []
    for p in parts:
        lin, ang = (0.12, 0.4) if p.kind == "printed" else (0.08, 0.6)
        P, N, I = tessellate(p.solid, lin, ang)
        if len(P) == 0:
            continue
        meshes.append(dict(name=p.id, positions=P, normals=N, indices=I, extras={"kind": p.kind, "material": p.material}))
        if "one" in p.extra:                                      # one piece of a set, for the simulator's print-bed view
            P1, N1, I1 = tessellate(p.extra["one"], lin, ang)
            meshes.append(dict(name=p.id + "One", positions=P1, normals=N1, indices=I1, extras={"kind": p.kind, "material": p.material, "oneOf": p.id}))
    glb_size = write_glb(sim_dir / "housing.glb", meshes, extras={"source": "docs/arhud-cad"})
    # the artifact host serves text but not .glb, so the simulator reads this base64 copy first
    import base64
    (sim_dir / "housing.glb.txt").write_text(base64.b64encode((sim_dir / "housing.glb").read_bytes()).decode())
    tri_count = int(sum(len(m["indices"]) for m in meshes))

    # ---- print files ----------------------------------------------------------------------------------------------
    rows = []
    for p in parts:
        info = dict(id=p.id, name=p.name, kind=p.kind, material=p.material, step=p.step, hud=p.hud, unit=p.sim,
                    explode=[round(float(x), 4) for x in p.explode], qty=p.qty, spec=p.spec, desc=p.desc)
        bb = p.solid.bounding_box()
        info["bboxMm"] = [round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)]
        vol = p.extra["one"].volume / 1000.0 if "one" in p.extra else p.solid.volume / 1000.0
        info["volumeCm3"] = round(vol, 1)
        if p.kind == "printed":
            info["massG"] = round(vol * DENSITY.get(p.material, 1.07), 0)
            po = print_orient(p)
            P, N, I = tessellate(p.extra.get("one", p.solid), 0.03, 0.2)
            Q = P @ po["R"].T + po["offset"]
            fn = f"{p.id}.stl"
            write_stl(out_dir / "stl" / fn, Q, I)
            info["print"] = dict(file=f"stl/{fn}", bedMm=po["size"], fits=po["fits"], supports=p.supports,
                                 quat=quat_from_matrix(po["R"]), offsetM=[round(float(x) / 1000, 5) for x in po["offset"]],
                                 material=g.MATERIAL if p.material == "asa" else "TPU 95A")
        rows.append(info)

    # ---- STEP assembly ----------------------------------------------------------------------------------------------
    from build123d import Compound, export_step
    kids = []
    for p in parts:
        s = p.solid
        s.label = p.id
        kids.append(s)
    asm = Compound(children=kids)
    asm.label = "arhud_housing"
    export_step(asm, out_dir / "arhud-housing.step")

    leaf_dxf(out_dir / "shutter-leaves.dxf")

    # ---- manifest for the simulator ---------------------------------------------------------------------------------
    printed = [r for r in rows if r["kind"] == "printed"]
    hw = {}
    for p in parts:
        if p.kind == "hardware":
            for spec, n in p.extra.get("bom", {}).items():
                hw[spec] = hw.get(spec, 0) + n
    gr = sh.glass_rect()
    sg = it.SG
    overall = [g.XF - g.XR, g.lid_top(g.XR) - g.FLOOR_BOT, 2 * g.ZW]
    manifest = dict(
        generated=str(date.today()), source="docs/arhud-cad (build123d " + _b3d_version() + ")",
        frame="X forward, Y up, Z right, metres; origin on the road under the nominal eye (the simulator's frame)",
        material=g.MATERIAL, bed=list(g.BED),
        summary=dict(sizeMm=[round(x) for x in overall],
                     printedPieces=sum(r["qty"] for r in printed), printedParts=len(printed),
                     printedMassG=round(sum(r.get("massG", 0) for r in printed)),
                     printHoursRough=round(sum(r["volumeCm3"] for r in printed) / 15.0),
                     fasteners=sum(n for n in hw.values()), triangles=tri_count, glbBytes=glb_size),
        hardware=dict(sorted(hw.items())),
        steps=[dict(id=s, title=t, text=x, parts=[p.id for p in parts if p.step == s]) for s, t, x in STEPS],
        parts=rows, checks=checks,
        shutter=dict(sc=round(it.SC / 1000, 5), L=round(it.SL / 1000, 5), W=round(it.SW / 1000, 5),
                     pivotZ=round(sg["pivot_z"] / 1000, 5)),
        glass=dict(sc=round((gr["s0"] + gr["s1"]) / 2000, 5), L=round((gr["s1"] - gr["s0"]) / 1000, 5),
                   W=round((gr["z1"] - gr["z0"]) / 1000, 5), n0=round((sh.TL - sh.GLASS_T - 0.1) / 1000, 5)),
        board=dict(c=[round(it.BOARD["cx"] / 1000, 5), round(it.BOARD["cy"] / 1000, 5), round(it.BOARD["z_pcb"] / 1000, 5)],
                   note="HDMI board stood on edge against the bay's right wall, HDMI facing the floor"),
        layout=dict(floorBot=g.FLOOR_BOT / 1000, stepX=g.STEP_X / 1000, overBot=g.OVER_BOT / 1000, xSeam=g.X_SEAM / 1000,
                    aperture=dict(s0=round(sh.AP["s0"] / 1000, 5), s1=round(sh.AP["s1"] / 1000, 5),
                                  z0=round(sh.AP["z0"] / 1000, 5), z1=round(sh.AP["z1"] / 1000, 5))),
    )
    (sim_dir / "housing.json").write_text(json.dumps(manifest, indent=1))
    (out_dir / "housing.json").write_text(json.dumps(manifest, indent=1))
    write_bom(out_dir / "BOM.md", rows, hw, manifest)
    return manifest


def _b3d_version():
    import build123d
    return build123d.__version__


def write_bom(path, rows, hw, man):
    L = ["# ARHUD housing: bill of materials", "",
         f"Generated by `make.py` on {man['generated']}. Printed parts are {man['material']}, "
         f"each fits a {man['bed'][0]:.0f} × {man['bed'][1]:.0f} × {man['bed'][2]:.0f} mm build volume in the orientation of its STL.", "",
         "## Printed", "", "| Part | Qty | Bed footprint (mm) | Supports | Mass (g, solid) |", "|---|---|---|---|---|"]
    for r in rows:
        if r["kind"] == "printed":
            pr = r["print"]
            L.append(f"| {r['name']} (`{pr['file']}`) | {r['qty']} | {pr['bedMm'][0]:.0f} × {pr['bedMm'][1]:.0f} × {pr['bedMm'][2]:.0f}"
                     f"{'' if pr['fits'] else ' DOES NOT FIT'} | {r.get('print', {}).get('supports', 'none')} | {r['massG']:.0f} |")
    L += ["", "## Bought and sheet parts", "", "| Part | Qty | Specification |", "|---|---|---|"]
    for r in rows:
        if r["kind"] in ("bought", "sheet"):
            L.append(f"| {r['name']} | {r['qty']} | {r['spec']} |")
    L += ["", "## Fasteners", "", "| Item | Qty |", "|---|---|"]
    for spec, n in sorted(hw.items()):
        L.append(f"| {spec} | {n} |")
    Path(path).write_text("\n".join(L) + "\n")
