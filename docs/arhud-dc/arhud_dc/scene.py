"""A scene: one clip of real footage, the rack surfaces to track in it, the ports on them, and the work order's
timeline. Scenes are JSON files in scenes/; times are seconds from the start of the cut (source.t0).

    "planes":   [{"name": "pp3", "ref_t": 2.0, "poly": [[x, y], ...],            surface outline on frame ref_t,
                  "t_range": [0.0, 9.5]}]                                         tracked only within t_range
    "ports":    {"PP3-24": {"plane": "pp3", "quad": [[x, y] x 4]}}                 tl, tr, br, bl on frame ref_t
                (or on frame at_t, with "at_t": s, carried back to ref_t through the tracking)
    "blocks":   [{"plane": "pp3", "prefix": "PP3-", "corners": [tl, tr, br, bl],   a uniform grid of ports
                  "rows": 2, "cols": 12, "first": 1, "gap": 0.18}]                  numbered row by row
    "timeline": [{"t": 0.3, "step": "2/6", "text": "Unplug  PP3 · 24"},             the one instruction line
                 {"t": 0.8, "target": "PP3-24", "label": "24"},                     brackets on a port
                 {"t": 6.1, "done": "PP3-24"},                                      verified: outline and check
                 {"t": 9.0, "step": "end", "text": "C14 clear", "hold": 2.0},      a closing line, gone after hold
                 {"t": 12.0, "clear": true}]                                        instruction line off

The HUD state is a pure function of time, so any frame can be rendered on its own.
"""
import json
import os

import numpy as np

APPEAR = 0.35     # s, brackets converge onto the port
CONFIRM = 0.6     # s, green outline and check held after the verification event
FADE = 0.3        # s
NEXT_CLEAR = 0.15 # s, a confirmation still showing when the next target appears is cleared this fast
LINE_OUT = 0.12   # s, the old instruction fades out...
LINE_IN = 0.22    # s, ...then the new one fades in: the two strings are never on screen together
LINE_HIDE = 2.5   # s into a step, the line steps aside while its target is locked in view (the brackets say it)
VERIFIED_DIM = 0.4  # the line's level once its step is verified, until the next step replaces it


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
        """What the HUD shows at t.

        lines:   [{"e": step event, "level": 0..1, "since": s, "target": port name or None}]; at most one string at a
                 time is visible (the old one fades out before the new one fades in)
        targets: {port: {"label", "since", "done" (s since verified, or None), "clear" (0..1 left of a confirmation
                 that the next target is pushing off)}}
        """
        steps = [e for e in self.timeline if "step" in e or "clear" in e]
        lines = []
        cur = max((k for k, e in enumerate(steps) if e["t"] <= t), default=None)
        if cur is not None:
            e = steps[cur]
            dt = t - e["t"]
            prev = steps[cur - 1] if cur > 0 else None
            if prev is not None and "step" in prev and dt < LINE_OUT:
                lines.append(self._line_state(prev, t, cur - 1, steps, 1.0 - dt / LINE_OUT))
            if "step" in e:
                lines.append(self._line_state(e, t, cur, steps, _smooth((dt - LINE_OUT) / LINE_IN)))
        targets = {}
        starts = [e["t"] for e in self.timeline if "target" in e]
        for e in self.timeline:
            if e["t"] > t:
                break
            if "target" in e:
                # a new target waits for a confirmation it is pushing off to clear, so the two never overlap
                busy = any(st["done"] is not None and st["done"] - (t - e["t"]) <= CONFIRM + FADE
                           for st in targets.values())
                delay = NEXT_CLEAR if busy else 0.0
                targets[e["target"]] = {"label": e.get("label", ""), "since": t - e["t"] - delay, "done": None,
                                        "note": "", "clear": 1.0}
            elif "done" in e and e["done"] in targets:
                st = targets[e["done"]]
                st["done"] = t - e["t"]
                st["note"] = e.get("note", "")
                nxt = min((s for s in starts if s >= e["t"]), default=None)
                if nxt is not None and nxt <= t:
                    st["clear"] = 1.0 - _smooth((t - nxt) / NEXT_CLEAR)
        for k in list(targets):
            st = targets[k]
            if st["done"] is not None and (st["done"] > CONFIRM + FADE or st["clear"] <= 0.0):
                del targets[k]
        return lines, targets

    def _line_state(self, e, t, k, steps, level):
        """One instruction line: dimmed once its step is verified, faded after its hold, with its step's target."""
        end = steps[k + 1]["t"] if k + 1 < len(steps) else float("inf")
        target = next((x["target"] for x in self.timeline if "target" in x and e["t"] <= x["t"] < end), None)
        done_t = next((x["t"] for x in self.timeline if x.get("done") == target and e["t"] <= x["t"] <= t), None) \
            if target else None
        if done_t is not None:
            level *= 1.0 - (1.0 - VERIFIED_DIM) * _smooth((t - done_t) / 0.2)
        if "hold" in e:
            level *= 1.0 - _smooth((t - e["t"] - e["hold"]) / 0.4)
        return {"e": e, "level": max(0.0, level), "since": t - e["t"], "target": target,
                "verified": done_t is not None}


def _smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


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
