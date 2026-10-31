"""Planar tracking: where a flat surface of the rack (a patch-panel face, a switch's port row) is in every frame.

A plane is given on one reference frame as a polygon around the surface. The tracker returns, for every frame of
the clip, the homography H that maps reference-frame pixels to that frame's pixels, or None when the surface is
out of view or too occluded to trust.

    reference frame -> SIFT keypoints inside the polygon (each keeps its exact reference position)
    frame to frame  -> pyramidal Lucas-Kanade with a forward-backward check, H from reference->current
                       point pairs (MAGSAC); points on hands and cables moving over the panel fall out as outliers
    every few frames, or when inliers run low -> SIFT re-match against the reference, which removes drift and
                       re-seeds the tracked points with exact reference positions
    afterwards      -> the polygon's corners are smoothed over +-2 frames (zero-phase) and H refit to them

Tracking runs on a downscaled grey copy (about 1280 px wide); homographies are returned in full-resolution pixels.
"""
import cv2
import numpy as np

LK = dict(winSize=(21, 21), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))


def _scale_h(H, s):
    """H in full-res pixels from H in pixels scaled by s (cv2.resize maps pixel centres: x_s = s x + (s - 1) / 2)."""
    c = 0.5 * s - 0.5
    S = np.array([[s, 0, c], [0, s, c], [0, 0, 1.0]])
    return np.linalg.inv(S) @ H @ S


def _poly_mask(shape, poly, dilate=0):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 255)
    if dilate:
        m = cv2.dilate(m, np.ones((dilate, dilate), np.uint8))
    return m


def _warp_pts(H, p):
    return cv2.perspectiveTransform(p.reshape(-1, 1, 2).astype(np.float64), H).reshape(-1, 2)


class PlaneTracker:
    def __init__(self, grey, ref_index, poly_full, scale, reseed_every=6, min_inliers=14, max_pts=700):
        self.g = grey
        self.max_pts = max_pts
        self.rng = np.random.default_rng(0)
        self.ref = ref_index
        self.s = scale
        self.poly = np.asarray(poly_full, np.float64) * scale + (0.5 * scale - 0.5)
        self.reseed_every = reseed_every
        self.min_inliers = min_inliers
        self.sift = cv2.SIFT_create(nfeatures=3000, contrastThreshold=0.02)
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)
        g0 = self.g[ref_index]
        kp, des = self.sift.detectAndCompute(g0, _poly_mask(g0.shape, self.poly))
        self.ref_kp = np.array([k.pt for k in kp], np.float32)
        self.ref_des = des
        if len(kp) < self.min_inliers:
            raise ValueError(f"only {len(kp)} keypoints inside the plane polygon on the reference frame")

    def _sift_match(self, i, H_guess):
        """H reference->frame i from SIFT matches, restricted to around where the plane is expected."""
        g = self.g[i]
        mask = None
        if H_guess is not None:
            mask = _poly_mask(g.shape, _warp_pts(H_guess, self.poly), dilate=81)
        kp, des = self.sift.detectAndCompute(g, mask)
        if des is None or len(kp) < self.min_inliers:
            return None, None, None
        pairs = self.matcher.knnMatch(self.ref_des, des, k=2)
        good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < self.min_inliers:
            return None, None, None
        a = self.ref_kp[[m.queryIdx for m in good]]
        b = np.array([kp[m.trainIdx].pt for m in good], np.float32)
        H, inl = cv2.findHomography(a, b, cv2.USAC_MAGSAC, 2.0, maxIters=4000, confidence=0.999)
        if H is None or inl.sum() < self.min_inliers:
            return None, None, None
        inl = inl.ravel().astype(bool)
        return H, a[inl], b[inl]

    def _seed(self, i, H):
        """Corner points inside the plane on frame i, with reference positions through H."""
        g = self.g[i]
        mask = _poly_mask(g.shape, _warp_pts(H, self.poly))
        c = cv2.goodFeaturesToTrack(g, 400, 0.01, 7, mask=mask, blockSize=7)
        if c is None:
            return np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32)
        cur = c.reshape(-1, 2).astype(np.float32)
        return _warp_pts(np.linalg.inv(H), cur).astype(np.float32), cur

    def _run(self, order):
        out = {}
        H = np.eye(3)
        ref_pts = self.ref_kp.copy()
        cur_pts = self.ref_kp.copy()
        a, b = self._seed(self.ref, H)
        ref_pts, cur_pts = np.vstack([ref_pts, a]), np.vstack([cur_pts, b])
        out[self.ref] = (H.copy(), len(cur_pts))
        prev = self.ref
        since = 0
        lost = False
        for i in order:
            H_new, n_inl = None, 0
            if not lost and len(cur_pts) >= self.min_inliers:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(self.g[prev], self.g[i], cur_pts.reshape(-1, 1, 2), None, **LK)
                p0, st2, _ = cv2.calcOpticalFlowPyrLK(self.g[i], self.g[prev], p1, None, **LK)
                fb = np.linalg.norm(p0.reshape(-1, 2) - cur_pts, axis=1)
                ok = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 0.6)
                if ok.sum() >= self.min_inliers:
                    rp, cp = ref_pts[ok], p1.reshape(-1, 2)[ok]
                    Hc, inl = cv2.findHomography(rp, cp, cv2.USAC_MAGSAC, 1.5, maxIters=3000, confidence=0.999)
                    if Hc is not None and inl.sum() >= self.min_inliers:
                        inl = inl.ravel().astype(bool)
                        H_new, n_inl = Hc, int(inl.sum())
                        ref_pts, cur_pts = rp[inl], cp[inl]
            since += 1
            if H_new is None or since >= self.reseed_every or n_inl < 3 * self.min_inliers:
                Hs, ra, cb = self._sift_match(i, H_new if H_new is not None else (None if lost else H))
                if Hs is not None:
                    if H_new is not None:
                        # keep LK points that agree with the SIFT fit, then add the SIFT inliers
                        err = np.linalg.norm(_warp_pts(Hs, ref_pts) - cur_pts, axis=1)
                        keep = err < 2.0
                        ref_pts, cur_pts = ref_pts[keep], cur_pts[keep]
                    else:
                        ref_pts, cur_pts = np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32)
                    ref_pts = np.vstack([ref_pts, ra]).astype(np.float32)
                    cur_pts = np.vstack([cur_pts, cb]).astype(np.float32)
                    H_all, inl = cv2.findHomography(ref_pts, cur_pts, cv2.USAC_MAGSAC, 1.5, maxIters=3000, confidence=0.999)
                    H_new = H_all if H_all is not None else Hs
                    n_inl = int(inl.sum()) if inl is not None else len(ra)
                    if inl is not None:
                        keep = inl.ravel().astype(bool)
                        ref_pts, cur_pts = ref_pts[keep], cur_pts[keep]
                    if len(cur_pts) > self.max_pts:
                        keep = self.rng.choice(len(cur_pts), self.max_pts, replace=False)
                        ref_pts, cur_pts = ref_pts[keep], cur_pts[keep]
                    if len(cur_pts) < 150:
                        a, b = self._seed(i, H_new)
                        ref_pts, cur_pts = np.vstack([ref_pts, a]), np.vstack([cur_pts, b])
                    since = 0
            if H_new is None or not self._sane(H_new, i):
                out[i] = (None, 0)
                lost = True
                continue
            lost = False
            H = H_new
            out[i] = (H.copy(), n_inl)
            prev = i
        return out

    def _sane(self, H, i):
        """Reject fits that fold, flip or blow up the plane."""
        q = _warp_pts(H, self.poly)
        if not np.all(np.isfinite(q)):
            return False
        a0 = cv2.contourArea(self.poly.astype(np.float32))
        a1 = cv2.contourArea(q.astype(np.float32))
        if a1 <= 0 or not (0.15 < a1 / a0 < 6.0):
            return False
        h, w = self.g[i].shape
        cx, cy = q.mean(axis=0)
        return -w < cx < 2 * w and -h < cy < 2 * h and cv2.isContourConvex(q.astype(np.float32))

    def track(self, lo=0, hi=None):
        """Track over frames [lo, hi) (default: all); frames outside the range are None."""
        n = len(self.g)
        hi = n if hi is None else min(n, hi)
        lo = max(0, lo)
        fwd = self._run(range(self.ref + 1, hi))
        bwd = self._run(range(self.ref - 1, lo - 1, -1))
        res = {i: (None, 0) for i in range(n)}
        res.update(bwd)
        res.update(fwd)
        Hs = [res[i][0] for i in range(n)]
        inl = [res[i][1] for i in range(n)]
        Hs = smooth(Hs, self.poly)
        return [None if H is None else _scale_h(H, self.s) for H in Hs], inl


def smooth(Hs, poly, radius=2):
    """Zero-phase smoothing of the plane's projected corners over +-radius frames, then H refit.

    Gaps (None) are not bridged; each run of tracked frames is smoothed on its own, with the window shrunk at its ends.
    """
    n = len(Hs)
    corners = np.array([_warp_pts(H, poly) if H is not None else np.full((len(poly), 2), np.nan) for H in Hs])
    out = list(Hs)
    w = np.array([1, 4, 6, 4, 1], np.float64)[2 - radius:3 + radius] if radius <= 2 else np.ones(2 * radius + 1)
    for i in range(n):
        if Hs[i] is None:
            continue
        acc, wsum = np.zeros_like(corners[i]), 0.0
        for k in range(-radius, radius + 1):
            j = i + k
            if 0 <= j < n and Hs[j] is not None:
                # only use neighbours on the same unbroken run
                if all(Hs[m] is not None for m in range(min(i, j), max(i, j) + 1)):
                    acc += w[k + radius] * corners[j]
                    wsum += w[k + radius]
        sm = acc / wsum
        out[i] = cv2.getPerspectiveTransform(poly[:4].astype(np.float32), sm[:4].astype(np.float32)) if len(poly) == 4 \
            else cv2.findHomography(poly, sm)[0]
    return out


def load_grey(frames, scale):
    return [cv2.resize(cv2.cvtColor(f, cv2.COLOR_RGB2GRAY), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            for f in frames]


def track_planes(frames_iter, planes, width):
    """planes: [{'name', 'ref_frame', 'poly': [[x, y], ...], 'range': (lo, hi) frames or None}] in full-res
    pixels. Returns {name: (Hs, inliers)}."""
    scale = min(1.0, 1280.0 / width)
    grey = load_grey(frames_iter, scale)
    out = {}
    for p in planes:
        t = PlaneTracker(grey, p["ref_frame"], p["poly"], scale)
        out[p["name"]] = t.track(*(p.get("range") or (0, None)))
    return out
