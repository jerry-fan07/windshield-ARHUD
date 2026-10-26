"""Builds every part of the housing and records how it goes together.

Each Part carries: what it is (printed, bought, hardware, sheet), its solid in the car frame, the housing assembly
step it belongs to, the simulator's HUD-unit group it joins, an explode offset, and for printed parts the face that
goes on the print bed.
"""
import time

import numpy as np

from . import geo as g
from . import internals as it
from . import shell as sh
from .kit import Hardware, Part, aabb, cyl, union

# Assembly steps, ground up. Each part lists one of these ids.
STEPS = [
    ("inserts", "Heat-set inserts",
     "Print the four body quarters (side wall down, no supports) and press the brass inserts into every boss with a "
     "soldering iron at 245 °C: seams, cap tabs, feet, bay and stand mounts."),
    ("body", "Join the body",
     "Bolt the quarters together along the internal seam strips: M3 button screws into the inserts. The rear quarters' "
     "front strip is the stray-light baffle; the continuous strips also keep light out of the seams."),
    ("feet", "Levelling feet",
     "Four M5 rubber levelling feet screw into the floor. Set them so the housing sits level and still on this dash, "
     "with 14 mm under the floor for the fan's air."),
    ("bay", "PGU bay",
     "The sealed bay for the backlight's heat sink, fan and HDMI board bolts to the floor over the floor opening. The "
     "fan blows out through the grille in the duct; fresh air comes in through the slots fore and aft."),
    ("grommets", "Cable grommets and access plugs",
     "TPU grommets seal the HDMI and LED lead exits in the bay floor and the sensor-lead port in the left wall. Three "
     "plugs close the front-wall holes that a ball-end key uses to reach the mirror adjusters."),
    ("carrier", "Panel carrier",
     "The carrier closes the bay. Its pocket holds the cell by the edges at the traced height, 0.5 mm over the "
     "backlight's IR-cut glass."),
    ("mask", "Panel mask",
     "The mask clamps the cell's edges. Its opening is the traced footprint on the panel plus 3 mm, so it never clips "
     "a ray from the eye box."),
    ("fold", "Fold bracket",
     "The bracket holds the cold mirror 50 mm over the panel at 35° incidence. Its cheeks stand on the carrier and "
     "share the bay's corner screws, so panel and fold are one rigid module."),
    ("stand", "Mirror stand",
     "The stand screws to the front floor across the centre seam. Its legs sit outboard of the adjusters so a key can "
     "reach every screw head."),
    ("strongback", "Strongback and adjusters",
     "The mirror is bonded to the ribbed strongback on three RTV pads. Three M4 screws with springs, bed-levelling "
     "style, pull it against the stand and set its tilt during calibration."),
    ("clips", "Mirror edge clips",
     "Two clips catch the mirror's bottom edge, outside the traced footprint, in case the bond lets go."),
    ("vanes", "Light-trap vanes",
     "Saw-tooth vanes on the side walls of the mirror bay trap sunlight that would otherwise light the walls the "
     "driver sees round the mirror."),
    ("lid", "Lid pieces",
     "The four lid pieces print face down. They join with half laps and countersunk screws, so the underside the "
     "shutter runs on stays flat."),
    ("rails", "Shutter rails and brackets",
     "Two rails per side screw under the lid, with a slot for each leaf. The servo hangs from a bracket under the "
     "right rail; the spring's anchor post sits under the front rim."),
    ("leaves", "Shutter leaves",
     "Two 0.5 mm black-anodised aluminium leaves, laser cut, slide into the rails. The front leaf carries the slot "
     "the servo's lever pin drives."),
    ("capOn", "Lid onto the body",
     "The lid's spigot tabs drop inside the body walls; M3 button screws through the walls hold it. No tools are "
     "needed to lift the housing off the dash, only to open it."),
    ("glass", "Dust-cover glass",
     "3 mm glass with the s-pass polariser laminated underneath sits in the lid's rebate on a foam gasket, flush with "
     "the top. Eight clamps hold its edges."),
    ("als", "Light-sensor pod",
     "The ambient-light sensor's pod sits on the lid behind the glass; its lead runs down the left wall's channel."),
]
STEP_IDS = [s[0] for s in STEPS]


def build():
    t0 = time.time()
    hw = Hardware()
    parts = []

    def add(**kw):
        p = Part(**kw)
        parts.append(p)
        return p

    # ---- internals first: the body needs their footprints -----------------------------------------------------------
    bay = it.build_bay(hw)
    stand, stand_feet = it.build_stand(hw)
    b = it.BAY
    keep = union([aabb(b["x0"] - 1, b["x1"] + 1, g.FLOOR_BOT - 2, b["y1"], b["z0"] - 10, b["z1"] + 10),
                  aabb(900.0, 990.0, g.FLOOR_BOT - 2, 900.0, -135.0, 135.0)])
    mounts = [(x, 0.0, z) for x, z in it.BAY_FLOOR_SCREWS] + [(x, 0.0, z) for x, z in stand_feet]
    keepouts = it.Keepouts(keep, mounts, b)
    print(f"  internals (bay, stand): {time.time() - t0:.1f} s")

    # ---- shell ------------------------------------------------------------------------------------------------------
    hw_body, hw_cap = Hardware(), Hardware()
    body, cap = sh.build_shell(keepouts, hw_body)
    print(f"  shell: {time.time() - t0:.1f} s")
    # mirror-adjuster access holes in the front wall, sensor-lead hole in the lid
    access = it.adjuster_access()
    holes = [cyl(h, d, 5.0 if i < 2 else 4.0, 120.0) for i, (h, d) in enumerate(access)]
    body = [(i, n, s.cut(holes[0]).cut(holes[1]).cut(holes[2]) if "Front" in i else s) for i, n, s in body]
    wire = it.pod_wire_hole()
    cap = [(i, n, s.cut(cyl(wire - g.LID_N * 1, g.LID_N, 2.0, 10.0)) if i == "capRearLeft" else s) for i, n, s in cap]
    for i, n, s in body:
        side = -1 if "Left" in i else 1
        fx = 0.06 if "Front" in i else -0.06
        add(id=i, name=n, kind="printed", solid=s, step="inserts", hud="housingBase", explode=(fx, -0.02, side * 0.07),
            down=(0, 0, side), desc="Floor, walls and seam strips; prints on its side wall.")
    for i, n, s in cap:
        side = -1 if "Left" in i else 1
        fx = 0.05 if "Front" in i else -0.05
        add(id=i, name=n, kind="printed", solid=s, step="lid", hud="lid", explode=(fx, 0.30, side * 0.06),
            down=tuple(g.LID_N), desc="Lid with the glass rebate, skirt and spigot tabs; prints face down.")
    # the shell's fasteners: inserts at step 1, seam screws at 'body', cap screws at 'capOn'
    _hw_groups(add, hw_body, {"body z seam": ("body", "housingBase", "inserts", "housingBase"),
                              "body x seam": ("body", "housingBase", "inserts", "housingBase"),
                              "floor mounts": ("inserts", "housingBase"),
                              "cap to body": ("capOn", "lid", "lid", "lid"), "lid lap": ("lid", "lid", "lid", "lid"),
                              "shutter rail": ("rails", "shutter", "lid", "lid"), "glass clamp": ("glass", "dustCover", "lid", "lid")},
               explode=(0, 0.02, 0), prefix="hwShell")

    # ---- bay, carrier, mask --------------------------------------------------------------------------------------------
    add(id="bay", name="PGU bay", kind="printed", solid=bay, step="bay", hud="housingBase", explode=(0, 0.12, 0),
        down=(0, -1, 0), desc="Sealed tub for heat sink, fan and HDMI board; duct and grilles to the floor.")
    hw_c = Hardware()
    add(id="carrier", name="Panel carrier", kind="printed", solid=it.build_carrier(hw_c), step="carrier", hud="housingBase",
        explode=(0, 0.20, 0), down=(0, -1, 0), desc="Holds the cell by its edges over the backlight.")
    add(id="mask", name="Panel mask", kind="printed", solid=it.build_mask(hw_c), step="mask", hud="pgu",
        explode=(0, 0.26, 0), down=(0, -1, 0), desc="Clamps the cell; opening = traced footprint + 3 mm.")
    add(id="foldBracket", name="Fold bracket", kind="printed", solid=it.build_fold_bracket(hw_c), step="fold", hud="coldMirror",
        explode=(0, 0.34, 0), down=(0, -1, 0), supports="tree supports under the bottom rail",
        desc="Cheeks, side rails with lips, absorber tabs; 35° incidence, 50 mm over the panel.")
    _hw_groups(add, hw, {"bay top": ("bay", "housingBase"), "bay to floor": ("bay", "housingBase"),
                         "heat sink to posts (self-tapping)": ("bay", "housingBase"),
                         "HDMI board (M2.5 self-tapping)": ("bay", "housingBase")}, explode=(0, 0.12, 0), prefix="hwBay")
    _hw_groups(add, hw_c, {"mask": ("mask", "pgu"), "fold bracket and carrier to bay": ("fold", "coldMirror"),
                           "absorber to bracket (with nut)": ("fold", "coldMirror")}, explode=(0, 0.26, 0), prefix="hwPanel")

    # ---- mirror mount -------------------------------------------------------------------------------------------------
    hw_m = Hardware()
    add(id="mirrorStand", name="Mirror stand", kind="printed", solid=stand, step="stand", hud="concaveMirror",
        explode=(0.10, 0.0, 0), down=(0, -1, 0), supports="tree supports under the triangle",
        desc="Triangle of adjuster bosses on two outboard legs.")
    add(id="strongback", name="Mirror strongback", kind="printed", solid=it.build_strongback(hw_m), step="strongback",
        hud="concaveMirror", explode=tuple(-g.MIRROR_N * 0.08), down=tuple(g.MIRROR_N),
        desc="Ribbed plate bonded to the mirror's back; M4 inserts for the adjusters.")
    for k, c in enumerate(it.build_clips(hw_m)):
        add(id=f"mirrorClip{'LR'[k]}", name=f"Mirror edge clip, {('left', 'right')[k]}", kind="printed", solid=c,
            step="clips", hud="concaveMirror", explode=tuple(-g.MIRROR_V * 0.05), down=(0, 0, 1),
            desc="Catches the mirror's bottom edge outside the traced footprint.")
    _hw_groups(add, hw, {"mirror stand to floor": ("stand", "concaveMirror"), "mirror adjuster": ("strongback", "concaveMirror"),
                         "mirror bond": ("strongback", "concaveMirror")}, explode=(0.10, 0, 0), prefix="hwMirrorA")
    _hw_groups(add, hw_m, {"mirror adjuster": ("strongback", "concaveMirror"), "mirror clip": ("clips", "concaveMirror"),
                           "mirror bond": ("strongback", "concaveMirror")}, explode=tuple(-g.MIRROR_N * 0.08), prefix="hwMirrorB")

    # ---- vanes, grommets, plugs, feet ---------------------------------------------------------------------------------
    for k, v in enumerate(it.build_vanes()):
        side = (-1, 1)[k]
        add(id=f"vane{'LR'[k]}", name=f"Light-trap vanes, {('left', 'right')[k]}", kind="printed", solid=v, step="vanes",
            hud="baffles", explode=(0, 0.05, side * 0.08), down=(0, 0, side), desc="Saw-tooth light trap, held by VHB tape.")
    for gid, gs in it.build_grommets().items():
        add(id=gid, name={"grommetWall": "Grommet, left wall", "grommetHdmi": "Grommet, HDMI exit", "grommetLed": "Grommet, LED and fan leads"}[gid],
            kind="printed", material="tpu", solid=gs, step="grommets", hud="housingBase", explode=(0, -0.04, 0),
            down=(0, -1, 0), desc="TPU 95A, slit for the cable.")
    for k, (p, d, plug) in enumerate(it.build_plugs(access)):
        add(id=f"accessPlug{k + 1}", name=f"Adjuster access plug {k + 1}", kind="printed", material="tpu", solid=plug,
            step="grommets", hud="housingBase", explode=tuple(np.array(d) * 0.05), down=tuple(np.array(d)),
            desc="Closes a front-wall hole the ball-end key uses.")
    hw_f = Hardware()
    feet = it.build_feet(hw_f)
    add(id="feet", name="Levelling feet (4)", kind="bought", material="rubber", solid=union(feet), step="feet",
        hud="housingBase", explode=(0, -0.05, 0), qty=4, spec="M5 threaded rubber levelling foot, 20 mm pad")
    _hw_groups(add, hw_f, {"foot": ("feet", "housingBase")}, explode=(0, -0.05, 0), prefix="hwFeet")

    # ---- shutter rails and brackets ------------------------------------------------------------------------------------
    hw_s = Hardware()
    for (side, end), r in it.build_rails(hw_s):
        sg = -1 if side == "Left" else 1
        add(id=f"rail{side}{end.capitalize()}", name=f"Shutter rail, {side.lower()} {end}", kind="printed", solid=r,
            step="rails", hud="shutter", explode=tuple(-g.LID_N * 0.04 + np.array([0, 0, sg * 0.03])),
            down=tuple(g.LID_N), desc="Two leaf slots; screws to the lid from below.")
    add(id="servoBracket", name="Servo bracket", kind="printed", solid=it.build_servo_bracket(hw_s), step="rails",
        hud="shutter", explode=tuple(-g.LID_N * 0.06), down=tuple(-g.LID_N), desc="Holds the SG90 under the right rail.")
    anchor, _ = it.build_spring_anchor(hw_s)
    add(id="springAnchor", name="Spring anchor post", kind="printed", solid=anchor, step="rails", hud="shutter",
        explode=tuple(-g.LID_N * 0.05), down=tuple(g.LID_N), desc="Holds the constant-force spring's end.")
    _hw_groups(add, hw_s, {"shutter rail": ("rails", "shutter"), "servo bracket": ("rails", "shutter"),
                           "servo tabs (M2 self-tapping)": ("rails", "shutter"), "spring anchor": ("rails", "shutter", "lid", "lid")},
               explode=tuple(-g.LID_N * 0.04), prefix="hwShutter")

    # ---- leaves (sheet), glass and polariser (bought), clamps, pod -----------------------------------------------------
    for k, (nm, n0, n1) in enumerate((("Rear", *it.SLOT_REAR), ("Front", *it.SLOT_FRONT))):
        lf = leaf_solid(nm)
        add(id=f"leaf{nm}", name=f"Shutter leaf, {nm.lower()}", kind="sheet", material="alu", solid=lf, step="leaves",
            hud="shutter", explode=tuple(g.LID_N * (0.03 + 0.02 * k)), sim=False,
            spec="0.5 mm aluminium 5052, black anodised, laser cut", desc="Runs in the rails; DXF in out/.")
    gr = sh.glass_rect()
    glass = sh.lid_box(gr["s0"], gr["s1"], sh.TL - sh.GLASS_T - 0.1, sh.TL - 0.1, gr["z0"], gr["z1"])
    add(id="coverGlass", name="Dust-cover glass", kind="bought", material="glass", solid=glass, step="glass",
        hud="dustCover", explode=tuple(g.LID_N * 0.10), sim=False,
        spec=f"3 mm float glass, {gr['s1'] - gr['s0']:.0f} x {gr['z1'] - gr['z0']:.0f} mm, arrised edges, s-pass polariser laminated underneath")
    hw_g = Hardware()
    clamps = it.build_clamps(hw_g)
    add(id="clamps", name="Glass clamps (8)", kind="printed", solid=union(clamps), step="glass", hud="dustCover",
        explode=tuple(g.LID_N * 0.13), down=tuple(-g.LID_N), qty=8, desc="Hold the glass edges on its gasket.",
        extra={"one": clamps[0]})
    _hw_groups(add, hw_g, {"glass clamp": ("glass", "dustCover")}, explode=tuple(g.LID_N * 0.13), prefix="hwClamps")
    add(id="alsPod", name="Light-sensor pod", kind="printed", solid=it.build_als_pod(hw_g), step="als", hud="dustCover",
        explode=tuple(g.LID_N * 0.08), down=tuple(-g.LID_N), desc="TSL2591 board under a 6 mm window.")
    print(f"  all parts: {time.time() - t0:.1f} s")
    return parts


def leaf_solid(which):
    """A shutter leaf in its closed position (simulator kinematics: rear leaf covers the rear half)."""
    L = it.SL
    leaf_len = L / 2 + 10.0
    n0, n1 = it.SLOT_REAR if which == "Rear" else it.SLOT_FRONT
    nc = (n0 + n1) / 2
    sc = it.SC + (-L / 4 - 2.5 if which == "Rear" else L / 4 + 2.5)
    w = it.LEAF_W / 2
    lf = sh.lid_box(sc - leaf_len / 2, sc + leaf_len / 2, nc - 0.25, nc + 0.25, -w, w)
    if which == "Front":                     # yoke slot for the lever pin, 9.5 mm from the rear edge
        s = sc - leaf_len / 2 + 9.5
        lf = lf.cut(sh.lid_box(s - 2.25, s + 2.25, nc - 1, nc + 1, it.SG["pivot_z"] - (L / 2 + 3.0) - 4.0, it.SG["pivot_z"] + 4.0))
    return lf


def _hw_groups(add, hw, mapping, explode, prefix, step=None, hud=None):
    """One Part per (note, kind) group of a Hardware list, so the explode and the build steps move them together.
    mapping: note -> (step, hud) or (step, hud, insert_step, insert_hud); inserts are pressed in before assembly."""
    from build123d import Compound
    groups = {}
    for kind, spec, solid, note in hw.items:
        if mapping is not None and note not in mapping:
            continue
        key = (note, "insert" if kind == "insert" else "fixing")
        groups.setdefault(key, []).append((kind, spec, solid))
    for k, ((note, cls), items) in enumerate(groups.items()):
        m = mapping.get(note) if mapping else None
        st, hd = (m[0], m[1]) if m else (step or "body", hud or "housingBase")
        if cls == "insert" and m and len(m) > 2:
            st, hd = m[2], m[3]
        kinds = {kk for kk, _, _ in items}
        bom = {}
        for kk, spec, _ in items:
            bom[spec] = bom.get(spec, 0) + 1
        mat = "brass" if kinds == {"insert"} else ("rtv" if kinds == {"bought"} else "steel")
        what = "inserts" if cls == "insert" else "fixings"
        add(id=f"{prefix}{k}", name=f"{what.capitalize()}: {note}", kind="hardware", material=mat,
            solid=Compound([s for _, _, s in items]), step=st, hud=hd, explode=explode, qty=len(items),
            spec="; ".join(f"{n} x {sp}" for sp, n in bom.items()), extra={"note": note, "bom": bom})
