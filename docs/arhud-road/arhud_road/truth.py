"""Ground truth from MetaDrive: the road ahead (every painted boundary along the ego's route), traffic, pedestrians,
cyclists, cones, speed signs and the next route manoeuvre. Everything is in MetaDrive world coordinates (x, y on the
road, z up; the same axes as Panda3D in this MetaDrive version). Perception (sensors.py) turns this into the plan's
noisy, delayed topics; metrics.py uses it unnoised to score registration.
"""
import math
import re

import numpy as np
from metadrive.component.static_object.traffic_object import TrafficObject
from metadrive.component.traffic_participants.cyclist import Cyclist
from metadrive.component.traffic_participants.pedestrian import Pedestrian
from metadrive.component.vehicle.base_vehicle import BaseVehicle
from metadrive.constants import PGLineColor, PGLineType


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def block_kind(node):
    """PG node names look like '3X1_0_' or '>>>': the letter after the block index is the block type."""
    m = re.match(r"-?(\d+)([A-Za-z])", node or "")
    return m.group(2) if m else ""


BLOCK_NAMES = {"X": "intersection", "T": "T-junction", "O": "roundabout", "r": "on-ramp", "R": "exit ramp",
               "y": "merge", "Y": "split", "C": "curve", "S": "straight", "P": "parking lot", "$": "fork"}


def line_kind(ltype, color):
    if ltype == PGLineType.NONE:
        return None
    if ltype == PGLineType.SIDE or ltype == PGLineType.GUARDRAIL:
        return "edge"
    yellow = tuple(color) == tuple(PGLineColor.YELLOW)
    if ltype == PGLineType.CONTINUOUS:
        return "solid_yellow" if yellow else "solid"
    return "dashed_yellow" if yellow else "dashed"


class ChainSample:
    __slots__ = ("a", "lane", "s", "i", "n", "w", "road", "kinds")

    def __init__(self, a, lane, s, i, n, w, road, kinds):
        self.a, self.lane, self.s, self.i, self.n, self.w, self.road, self.kinds = a, lane, s, i, n, w, road, kinds


class Truth:
    def __init__(self, engine, ego):
        self.engine = engine
        self.ego = ego
        self.graph = engine.current_map.road_network.graph
        self.signs = []                    # filled by the scenario manager: dicts with pos (x, y), value, side
        self._kinds_cache = {}

    # ---- the road ahead ---------------------------------------------------------------------------------------
    def _road_lanes(self, lane):
        f, t, _ = lane.index
        return self.graph[f][t]

    def _boundary_kinds(self, lanes):
        key = id(lanes)
        k = self._kinds_cache.get(key)
        if k is None:
            n = len(lanes)
            k = []
            for b in range(n + 1):
                if b == 0:
                    k.append(line_kind(lanes[0].line_types[0], lanes[0].line_colors[0]))
                elif b == n:
                    k.append(line_kind(lanes[n - 1].line_types[1], lanes[n - 1].line_colors[1]))
                else:
                    k.append(line_kind(lanes[b].line_types[0], lanes[b].line_colors[0]))
            self._kinds_cache[key] = k
        return k

    def _next_lane(self, lane):
        f, t, i = lane.index
        nxt = self.graph.get(t)
        if not nxt:
            return None
        cps = getattr(self.ego.navigation, "checkpoints", None) or []
        choice = None
        if t in cps:
            j = cps.index(t)
            if j + 1 < len(cps) and cps[j + 1] in nxt:
                choice = cps[j + 1]
        if choice is None:
            h = lane.heading_theta_at(lane.length)
            choice = min(nxt.keys(), key=lambda k: abs(wrap(nxt[k][0].heading_theta_at(0) - h)))
        lanes = nxt[choice]
        return lanes[min(i, len(lanes) - 1)]

    def chain(self, behind=8.0, ahead=130.0, step=2.0):
        """Samples along the ego's lane following the route: a = arc length from the ego (negative behind)."""
        ego = self.ego
        lane = ego.lane
        s0, lat0 = lane.local_coordinates(ego.position)
        self.ego_s, self.ego_lat = s0, lat0
        out = []
        a = -behind
        cur, s = lane, s0 - behind
        while a <= ahead:
            while cur is not None and s > cur.length:
                s -= cur.length
                cur = self._next_lane(cur)
            if cur is None:
                break
            lanes = self._road_lanes(cur)
            i = min(cur.index[2], len(lanes) - 1)
            out.append(ChainSample(a, cur, s, i, len(lanes), cur.width_at(s), cur.index, self._boundary_kinds(lanes)))
            a += step
            s += step
        return out

    def boundaries(self, chain):
        """Every boundary along the chain as world polylines, keyed by its index counted from the left edge of the
        road (b0 is the left edge / centre line). Returns {key: dict(pts (N x 2), a (N), kind (N), rel (N))} where
        rel is the boundary's position relative to the ego lane (0 = ego left line, 1 = ego right line)."""
        lines = {}
        for cs in chain:
            for b in range(cs.n + 1):
                kind = cs.kinds[b]
                lat = (b - cs.i - 0.5) * cs.w
                p = cs.lane.position(cs.s, lat)
                L = lines.setdefault(b, dict(pts=[], a=[], kind=[], rel=[]))
                L["pts"].append(p)
                L["a"].append(cs.a)
                L["kind"].append(kind)
                L["rel"].append(b - cs.i)
        for L in lines.values():
            L["pts"] = np.array(L["pts"], dtype=float)
            L["a"] = np.array(L["a"], dtype=float)
        return lines

    def centreline(self, chain):
        return np.array([cs.lane.position(cs.s, 0.0) for cs in chain], dtype=float), np.array([cs.a for cs in chain])

    # ---- route manoeuvre --------------------------------------------------------------------------------------
    def next_manoeuvre(self, chain, min_a=2.0):
        """The first junction block ahead on the route (intersection, T-junction, roundabout, exit ramp, split), with
        the turn it makes and where the turn starts. A road (from, to) belongs to the block named by `to`.
        Returns dict(kind, turn (deg, + left), a_turn, a_end, block) or None."""
        groups = []
        for cs in chain:
            m = re.match(r"-?(\d+[A-Za-z$])", cs.road[1] or "")
            bid = m.group(1) if m else ""
            if not groups or groups[-1][0] != bid:
                groups.append([bid, []])
            groups[-1][1].append(cs)
        for bid, samples in groups:
            kind = bid[-1:] if bid else ""
            if kind not in ("X", "T", "O", "R", "Y", "$") or samples[-1].a < min_a:
                continue
            inside = samples[0].a < 0
            samples = [cs for cs in samples if cs.a >= -1.0]          # what is left of the junction from here on
            if len(samples) < 2:
                continue
            h = [cs.lane.heading_theta_at(cs.s) for cs in samples]
            if inside and abs(wrap(max(h, key=lambda x: abs(wrap(x - h[0]))) - h[0])) < math.radians(20):
                continue                                              # already through the turn (or going straight)
            turn, j_turn, j_end = 0.0, None, len(samples) - 1
            for j in range(1, len(samples)):
                d = wrap(h[j] - h[0])
                if j_turn is None and abs(d) > math.radians(4):
                    j_turn = j - 1
                if abs(d) > abs(turn):
                    turn, j_end = d, j
            if j_turn is None:
                j_turn = 0
            # the route may leave the chain before the block ends (chain truncated): still report it
            return dict(kind=BLOCK_NAMES.get(kind, kind), block=kind, turn=math.degrees(turn),
                        a_turn=max(samples[j_turn].a, samples[0].a), a_start=samples[0].a, a_end=samples[j_end].a)
        return None

    # ---- objects ----------------------------------------------------------------------------------------------
    def objects(self):
        out = []
        for oid, o in self.engine.get_objects().items():
            if o is self.ego:
                continue
            if isinstance(o, BaseVehicle):
                L = o.LENGTH
                H = o.HEIGHT
                kind = "truck" if H > 2.3 else ("suv" if H > 1.6 else "car")
            elif isinstance(o, Pedestrian):
                kind = "person"
            elif isinstance(o, Cyclist):
                kind = "bicycle"
            elif isinstance(o, TrafficObject):
                kind = "cone"
            else:
                continue
            try:
                pos = np.array(o.position, dtype=float)
                vel = np.array(o.velocity, dtype=float) if kind != "cone" else np.zeros(2)
                hd = float(o.heading_theta)
            except Exception:
                continue
            if kind == "person" or kind == "bicycle":
                sp = float(np.hypot(*vel))
                if sp > 0.05:
                    hd = math.atan2(vel[1], vel[0])
            out.append(dict(id=oid, kind=kind, pos=pos, vel=vel, heading=hd,
                            length=float(getattr(o, "LENGTH", 0.6) or 0.6),
                            width=float(getattr(o, "WIDTH", 0.6) or 0.6),
                            height=float(getattr(o, "HEIGHT", 1.0) or 1.0)))
        return out
