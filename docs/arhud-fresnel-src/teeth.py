"""Tooth-level 2D ray trace of the Fresnel sheet in a meridional plane (r, z).

Unlike optics.py, which collapses the grooves onto a plane, this builds the real profile: in
zone k (r_k = k * pitch) the facet runs from height h_k at the inner edge down to 0 at the outer
edge, following the continuous asphere; a vertical draft wall then climbs to the next tooth.
Rays are followed through every surface they meet (refraction, or reflection on TIR), so light
that strikes a draft wall, or re-enters the next tooth, is caught. Fresnel partial reflections
are not followed (main path only)."""
import math
import numpy as np
import optics as O

def sag(r):
    """Continuous asphere the facets replace (negative, mm), from the solved slopes."""
    rr = O.R_TAB
    s = -np.concatenate([[0], np.cumsum(np.tan(O.G_TAB[1:]) * np.diff(rr))])
    return np.interp(r, rr, s)

def profile(ra, rb, pitch=O.PITCH, draft_deg=0.0, nfacet=20):
    """Top surface points from ra to rb (tooth tips above z = 0). Returns list of (r, z)."""
    pts = []
    k0 = int(math.floor(ra / pitch)); k1 = int(math.ceil(rb / pitch))
    for k in range(k0, k1):
        r0, r1 = k * pitch, (k + 1) * pitch
        base = sag(r1)
        tw = math.tan(math.radians(draft_deg))
        h0 = sag(r0) - base
        # draft wall at r0 (inner side of this tooth), leaning by draft_deg
        rr = np.linspace(r0 + h0 * tw, r1, nfacet)
        zz = sag(rr) - base
        if k > k0 or True:
            pts.append((r0, 0.0))
        pts.extend(zip(rr, zz))
    return pts

class Lens2D:
    def __init__(self, ra, rb, flipped=False, pitch=O.PITCH, draft_deg=0.0, t=O.T, n=O.N_D):
        top = profile(ra, rb, pitch, draft_deg)
        top = [(r, z) for r, z in top if ra - 1e-9 <= r <= rb + 1e-9]
        poly = [(ra, -t)] + [(ra, 0.0)] + top + [(rb, 0.0), (rb, -t)]
        if flipped:                                    # teeth face the panel: mirror about the mid-plane
            poly = [(r, -t - z) for r, z in poly]
        self.poly = np.array(poly)
        self.n = n; self.t = t; self.flipped = flipped
        a = self.poly; b = np.roll(self.poly, -1, axis=0)
        self.A, self.B = a, b
        e = b - a
        L = np.linalg.norm(e, axis=1)
        keep = L > 1e-9
        self.A, self.B, e, L = self.A[keep], self.B[keep], e[keep], L[keep]
        self.E = e
        # classify segments: draft walls are steep (near-vertical), facets are not
        self.kind = np.where(np.abs(e[:, 0]) < 1e-6 * L + 1e-12, "wall", "facet")
        flat_z = 0.0 if flipped else -t
        self.kind = np.where(np.abs(self.A[:, 1] - flat_z) + np.abs(self.B[:, 1] - flat_z) < 1e-9, "flat", self.kind)
        side = (np.abs(self.A[:, 0] - self.B[:, 0]) < 1e-12) & ((np.abs(self.A[:, 0] - ra) < 1e-9) | (np.abs(self.A[:, 0] - rb) < 1e-9))
        self.kind = np.where(side, "side", self.kind)

    def inside(self, p):
        x, y = p; c = False
        P = self.poly; n = len(P)
        for i in range(n):
            x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c

    def hit(self, p, d):
        # ray p + s d against all segments A + u E, u in [0, 1]
        den = d[0] * self.E[:, 1] - d[1] * self.E[:, 0]
        w = self.A - p
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (w[:, 0] * self.E[:, 1] - w[:, 1] * self.E[:, 0]) / den
            u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den
        ok = (np.abs(den) > 1e-14) & (s > 1e-7) & (u >= -1e-9) & (u <= 1 + 1e-9)
        if not ok.any():
            return None
        i = int(np.argmin(np.where(ok, s, np.inf)))
        return i, s[i]

    def trace(self, p, d, max_events=14):
        """Follow one ray. Returns (path points, events list, final dir, status)."""
        p = np.array(p, float); d = np.array(d, float) / np.linalg.norm(d)
        path = [p.copy()]; events = []
        inside = self.inside(p)
        for _ in range(max_events):
            h = self.hit(p, d)
            if h is None:
                return path + [p + d * 6.0], events, d, "escaped"
            i, s = h
            q = p + s * d
            path.append(q.copy())
            kind = self.kind[i]
            if kind == "side":
                return path, events + [("stop", "side")], d, "side"
            e = self.E[i] / np.linalg.norm(self.E[i])
            nrm = np.array([e[1], -e[0]])
            n1, n2 = (self.n, 1.0) if inside else (1.0, self.n)
            c = float(np.dot(d, nrm))
            if c > 0:
                nrm = -nrm; c = -c
            cosi = -c; eta = n1 / n2; k = 1 - eta * eta * (1 - cosi * cosi)
            if k < 0:
                d = d + 2 * cosi * nrm
                events.append(("tir", kind))
            else:
                d = eta * d + (eta * cosi - math.sqrt(k)) * nrm
                d /= np.linalg.norm(d)
                inside = not inside
                events.append(("refr", kind))
            p = q
        return path, events, d, "maxed"

def ideal_exit_dir(r_flat, flipped=False):
    """Exit direction of the thin-facet model for a ray from the on-axis panel point to r_flat."""
    P = np.array([[0.0, 0.0, O.Z_PANEL]])
    d = O.unit(np.array([[r_flat, 0.0, -O.Z_PANEL - O.T]]))
    fw = O.trace_forward(P, d, flipped=flipped)
    return math.degrees(math.atan2(fw["d"][0, 0], fw["d"][0, 2]))

def fan(r0, flipped=False, width=2.5, nrays=41, src=(0.0, O.Z_PANEL), draft_deg=0.0, margin=4.0):
    """Rays from a panel point (r, z) aimed across [r0 - width/2, r0 + width/2] on the panel-side face."""
    L = Lens2D(r0 - width / 2 - margin, r0 + width / 2 + margin, flipped=flipped, draft_deg=draft_deg)
    out = []
    face_z = -O.T if not flipped else -O.T - 1.2       # aim just below the first surface
    for rt in np.linspace(r0 - width / 2, r0 + width / 2, nrays):
        p0 = np.array(src, float)
        d = np.array([rt - p0[0], face_z - p0[1]]); d /= np.linalg.norm(d)
        # start the ray 3 mm below the sheet so the plot shows the incoming leg
        s0 = (face_z - 3.0 - p0[1]) / d[1]
        p = p0 + s0 * d
        path, ev, dfin, status = L.trace(p, d)
        ang = math.degrees(math.atan2(dfin[0], dfin[1]))
        out.append(dict(path=np.array(path), events=ev, ang=ang, status=status, aim=rt))
    return L, out

def classify(rays, ideal, tol=0.5):
    good = stray = tir = lost = 0
    for ry in rays:
        walls = any(k == "wall" for _, k in ry["events"])
        tirs = any(t == "tir" for t, _ in ry["events"])
        up = ry["status"] == "escaped" and ry["path"][-1][1] > ry["path"][-2][1]
        if up and not walls and not tirs and abs(ry["ang"] - ideal) < tol:
            good += 1
        elif tirs and not up:
            tir += 1
        elif up:
            stray += 1
        else:
            lost += 1
    n = len(rays)
    return dict(good=good / n, stray=stray / n, tir=tir / n, lost=lost / n)

def survey(flipped, radii=None, nrays=400, draft_deg=0.0):
    radii = np.arange(5, 211, 5) if radii is None else radii
    rows = []
    for r0 in radii:
        L, rays = fan(float(r0), flipped=flipped, width=2.0, nrays=nrays, draft_deg=draft_deg)
        c = classify(rays, ideal_exit_dir(r0, flipped))
        rows.append((float(r0), c["good"], c["stray"], c["tir"], c["lost"]))
    return rows

if __name__ == "__main__":
    for fl in (False, True):
        rows = survey(fl, radii=[10, 50, 100, 150, 200], nrays=200)
        print("flipped" if fl else "correct", [(r, round(g, 3), round(s, 3), round(t, 3), round(l, 3)) for r, g, s, t, l in rows])

def eye_fan(r0, width=2.0, nrays=200, eye_x=0.0, eye_z=None, flipped=False, margin=6.0):
    """Reverse rays from the eye (unfolded, on the +z side) to lens radii around r0. Each ray is
    followed through the real teeth and the flat face, then on to the panel plane."""
    eye_z = O.EYE_Z if eye_z is None else eye_z
    L = Lens2D(r0 - width / 2 - margin, r0 + width / 2 + margin, flipped=flipped)
    top = 1.2
    out = []
    for rt in np.linspace(r0 - width / 2, r0 + width / 2, nrays):
        d = np.array([rt - eye_x, top - eye_z]); d /= np.linalg.norm(d)
        p = np.array([eye_x, eye_z]) + d * ((eye_z - (top + 2.0)) / -d[1] * -1)
        p = np.array([rt, top]) - d * 2.0
        path, ev, dfin, status = L.trace(p, d)
        land = None
        if status == "escaped" and dfin[1] < 0:
            q = path[-2] if len(path) > 1 else p
            # continue from the last surface point to the panel plane
            last = np.array(path[-2]) if len(path) >= 2 else p
            s = (O.Z_PANEL - last[1]) / dfin[1]
            land = last[0] + s * dfin[0]
        walls = any(k == "wall" for _, k in ev)
        tirs = any(t == "tir" for t, _ in ev)
        out.append(dict(path=np.array(path), events=ev, walls=walls, tir=tirs, land=land, aim=rt, status=status))
    return L, out

def eye_wall_fraction(r0, nrays=400, eye_x=0.0):
    _, rays = eye_fan(r0, nrays=nrays, eye_x=eye_x)
    return sum(1 for r in rays if r["walls"]) / len(rays)
