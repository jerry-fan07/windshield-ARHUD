"""Loaders for config/calibration.yaml (appendix B: the rig, measured or assumed) and config/bench.yaml (how the
bench is run), with the date and provenance of every field.

Provenance lives in a `provenance:` map at the end of each file, keyed by dotted field path:

    provenance:
      warp.homography_pr: {date: 2026-10-27, source: "identity rig (vertical mirror), brief STAGE-PROJECTION-PLAN"}

`Config.set(path, value, source)` updates the value and its provenance together; `Config.save()` writes the file back
(PyYAML drops comments, so the files carry their explanations in provenance and a fixed header).

Environment: ARHUD_CONFIG overrides the config directory (default: hud/config next to the package).
"""
from __future__ import annotations

import copy
import datetime
import os

import numpy as np
import yaml

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # .../hud
CONFIG_DIR = os.environ.get("ARHUD_CONFIG", os.path.join(PKG_ROOT, "config"))
SHOTS_DIR = os.path.join(PKG_ROOT, "shots")
RUNS_DIR = os.path.join(PKG_ROOT, "runs")

HEADER = {
    "calibration.yaml": "# Tabletop AR HUD bench calibration (design appendix B, with the flip matrix corrected).\n"
                        "# Every field's date and source is in `provenance:` at the end. Written by hud tools;\n"
                        "# edit values by hand only together with their provenance entry.\n",
    "bench.yaml": "# How the tabletop bench runs: source, mode, gain, eye distance, data root, windows, lag defaults.\n"
                  "# Values derived from docs/arhud-tabletop-src/tcalc.py by hud/tools/gen_config.py.\n",
}


def today():
    return datetime.date.today().isoformat()


def _plain(v):
    """numpy -> plain Python for YAML."""
    if isinstance(v, np.ndarray):
        return [_plain(x) for x in v.tolist()]
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


class Config(dict):
    """A YAML file as a dict, with dotted access and per-field provenance."""

    def __init__(self, data, path=None):
        super().__init__(data or {})
        self.path = path
        self.setdefault("provenance", {})

    @classmethod
    def load(cls, name_or_path):
        path = name_or_path if os.path.sep in name_or_path else os.path.join(CONFIG_DIR, name_or_path)
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(data, path)

    def get_path(self, dotted, default=None):
        cur = self
        for k in dotted.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, dotted, value, source, date=None):
        keys = dotted.split(".")
        cur = self
        for k in keys[:-1]:
            if not isinstance(cur.get(k), dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = _plain(value)
        self["provenance"][dotted] = {"date": date or today(), "source": source}

    def provenance(self, dotted):
        """Provenance of a field: its own entry, else the nearest parent's."""
        keys = dotted.split(".")
        for n in range(len(keys), 0, -1):
            p = self["provenance"].get(".".join(keys[:n]))
            if p:
                return p
        return None

    def save(self, path=None):
        path = path or self.path
        data = {k: _plain(v) for k, v in self.items() if k != "provenance"}
        data["provenance"] = dict(sorted(self["provenance"].items()))
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(HEADER.get(os.path.basename(path), ""))
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=None, width=120)
        os.replace(tmp, path)
        self.path = path

    def copy(self):
        return Config(copy.deepcopy(dict(self)), self.path)


def load_calibration(path=None):
    return Config.load(path or "calibration.yaml")


def load_bench(path=None):
    return Config.load(path or "bench.yaml")


def data_root(bench=None):
    bench = bench or load_bench()
    return os.path.expanduser(os.environ.get("ARHUD_DATA", bench.get("data_root", "~/data/arhud")))


def lag_ms(calib, which, bench=None):
    """timing.lag_<which>_ms, or the bench default (0) when it has not been measured. Returns (value, measured)."""
    v = calib.get_path(f"timing.lag_{which}_ms")
    if v is None:
        bench = bench or load_bench()
        return float(bench.get("lag_default_ms", 0.0)), False
    return float(v), True


def homography_pr(calib):
    """warp.homography_pr as a 3 x 3 array (road-monitor px -> PGU px, flip inside); built from warp.flip if null."""
    from .geometry import flip_matrix
    H = calib.get_path("warp.homography_pr")
    W, Hh = calib["monitors"]["pgu"]["px"]
    if H is None:
        return flip_matrix(calib.get_path("warp.flip", "vertical"), W, Hh)
    return np.asarray(H, dtype=float)


def source_camera_mount(calib, name):
    """(Camera, Mount, config dict) for sources.<name>, with null mount fields left to the caller's defaults."""
    from .geometry import Camera, Mount
    s = calib["sources"][name]
    return Camera.from_dict(s["camera"]), Mount.from_dict(s.get("mount")), s


def bench_geometry(calib=None, bench=None):
    from .geometry import Bench
    calib = calib or load_calibration()
    bench = bench if bench is not None else load_bench()
    return Bench.from_config(calib, bench)
