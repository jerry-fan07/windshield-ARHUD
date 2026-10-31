"""A scene: one clip of real footage, the rack surfaces to track in it, the ports on them, and the work order's
timeline. Scenes are JSON files in scenes/; times are seconds from the start of the cut (source.t0).

    "planes":   [{"name": "pp3", "ref_t": 2.0, "poly": [[x, y], ...],            surface outline on frame ref_t,
                  "t_range": [0.0, 9.5]}]                                         tracked only within t_range
    "ports":    {"PP3-24": {"plane": "pp3", "quad": [[x, y] x 4]}}                 tl, tr, br, bl on frame ref_t
                (or on frame at_t, with "at_t": s, carried back to ref_t through the tracking)
    "blocks":   [{"plane": "pp3", "prefix": "PP3-", "corners": [tl, tr, br, bl],   a uniform grid of ports
                  "rows": 2, "cols": 12, "first": 1, "gap": 0.18}]                  numbered row by row
    "timeline": [{"t": 0.3, "step": "2/6", "text": "PP3-24  ->  SW2-17"},           the one instruction line
                 {"t": 0.8, "target": "PP3-24", "label": "24"},                     brackets on a port
                 {"t": 6.1, "done": "PP3-24", "note": "Link up"},                   confirmation, then gone
                 {"t": 9.0, "clear": true}]                                         instruction line off

The HUD state is a pure function of time, so any frame can be rendered on its own.
"""
import json
import os

import numpy as np

APPEAR = 0.35     # s, brackets converge onto the port
CONFIRM = 0.8     # s, green outline and check held after the verification event
FADE = 0.35       # s
LINE_FADE = 0.3   # s, instruction cross-fade
LINE_DIM = 3.0    # s, after which the instruction steps back to half brightness while the hands work


class Scene:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(os.path.dirname(self.path))
        self.name = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            self.cfg = json.load(f)
        self.src = self.cfg["source"]
        self.t0 = float(self.src.get("t0", 0.0))
        self.t1 = self.src.get("t1")
        self.ports = {}
        for name, p in self.cfg.get("ports", {}).items():
            self.ports[name] = {"plane": p["plane"], "quad": np.asarray(p["quad"], np.float64)}
            if "at_t" in p:
                self.ports[name]["at_t"] = float(p["at_t"])
        for b in self.cfg.get("blocks", []):
            self.ports.update(grid_ports(b))
        self.timeline = sorted(self.cfg.get("timeline", []), key=lambda e: e["t"])

    @property
    def footage(self):
        f = self.src["file"]
        return f if os.path.isabs(f) else os.path.join(self.dir, f)

    def state(self, t):
        """What the HUD shows at t: the instruction line(s) with levels, and each port's bracket state."""
        lines = []
        steps = [e for e in self.timeline if "step" in e or "clear" in e]
        cur = None
        for i, e in enumerate(steps):
            if e["t"] > t:
                break
            cur = i
        if cur is not None:
            e = steps[cur]
            a = min(1.0, (t - e["t"]) / LINE_FADE)
            if "step" in e:
                lines.append((e, a))
            if a < 1.0 and cur > 0 and "step" in steps[cur - 1]:
                lines.append((steps[cur - 1], 1.0 - a))
        targets = {}
        for e in self.timeline:
            if e["t"] > t:
                break
            if "target" in e:
                targets[e["target"]] = {"label": e.get("label", ""), "since": t - e["t"], "done": None, "note": ""}
            elif "done" in e and e["done"] in targets:
                targets[e["done"]]["done"] = t - e["t"]
                targets[e["done"]]["note"] = e.get("note", "")
        for k in list(targets):
            d = targets[k]["done"]
            if d is not None and d > CONFIRM + FADE:
                del targets[k]
        return lines, targets


def grid_ports(b):
    """Ports of a uniform block by bilinear interpolation of its corners; each port shrunk by gap (fraction of pitch)."""
    tl, tr, br, bl = (np.asarray(p, np.float64) for p in b["corners"])
    rows, cols, gap = b["rows"], b["cols"], b.get("gap", 0.18)
    first = b.get("first", 1)
    out = {}

    def at(u, v):
        top = tl + (tr - tl) * u
        bot = bl + (br - bl) * u
        return top + (bot - top) * v
    for r in range(rows):
        for c in range(cols):
            u0, u1 = (c + gap / 2) / cols, (c + 1 - gap / 2) / cols
            v0, v1 = (r + gap / 2) / rows, (r + 1 - gap / 2) / rows
            n = first + (r * cols + c if b.get("order", "row") == "row" else c * rows + r)
            out[f"{b.get('prefix', '')}{n}"] = {"plane": b["plane"],
                                               "quad": np.array([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)])}
    return out
