#!/usr/bin/env python3
"""Tracker check against known ground truth.

A flat textured image (any photo) is placed on a plane and filmed by a simulated head-mounted camera: smooth head
motion with walk sway and quick glances, motion blur along the image motion, a skin-coloured occluder sweeping
across the plane like a hand, sensor noise and JPEG-like blocking. The tracker gets the reference polygon on frame 0
and must recover every frame's homography. Error is the distance between tracked and true positions of a grid of
points on the plane (full-res pixels).

    python3 tools/synth_track_test.py path/to/texture.jpg [--frames 240]
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from arhud_dc.track import track_planes  # noqa: E402

W, H = 1920, 1080


def camera_path(n, rng):
    t = np.arange(n) / 30.0
    yaw = 2.5 * np.sin(2 * np.pi * 0.21 * t) + 0.8 * np.sin(2 * np.pi * 0.9 * t + 1)
    pitch = 1.5 * np.sin(2 * np.pi * 0.17 * t + 2) + 0.5 * np.sin(2 * np.pi * 1.7 * t)
    roll = 1.2 * np.sin(2 * np.pi * 0.13 * t)
    dist = 0.75 + 0.12 * np.sin(2 * np.pi * 0.08 * t)
    # a quick glance away and back around t = 4 s
    g = np.exp(-((t - 4.0) / 0.35) ** 2)
    yaw += 9.0 * g
    yaw += np.cumsum(rng.normal(0, 0.05, n))
    return yaw, pitch, roll, dist


def homography(yaw, pitch, roll, dist, tex_w, tex_h, f=1100.0):
    """Plane of width 0.6 m at distance dist in front of a pinhole camera, rotated by the head angles."""
    ry, rp, rr = np.radians([yaw, pitch, roll])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(rp), -np.sin(rp)], [0, np.sin(rp), np.cos(rp)]])
    Rz = np.array([[np.cos(rr), -np.sin(rr), 0], [np.sin(rr), np.cos(rr), 0], [0, 0, 1]])
    R = Rz @ Rx @ Ry
    m_per_px = 0.6 / tex_w
    # plane points (u, v) -> world (x, y, 0) centred, then camera = R @ (world + [0, 0, dist]) with a slight tilt
    tilt = np.radians(18)
    Rt = np.array([[1, 0, 0], [0, np.cos(tilt), -np.sin(tilt)], [0, np.sin(tilt), np.cos(tilt)]])
    A = np.array([[m_per_px, 0, -tex_w / 2 * m_per_px], [0, m_per_px, -tex_h / 2 * m_per_px], [0, 0, 0]])
    M = R @ Rt @ A
    M[:, 2] += R @ np.array([0, 0, dist])
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
    Hm = K @ M
    return Hm / Hm[2, 2]


def render(tex, Hm, Hm_prev, i, n, rng):
    bg = np.full((H, W, 3), 38, np.uint8)
    img = cv2.warpPerspective(tex, Hm, (W, H), dst=bg, borderMode=cv2.BORDER_TRANSPARENT, flags=cv2.INTER_LINEAR)
    # motion blur: average of 5 warps between previous and current pose
    if Hm_prev is not None:
        acc = img.astype(np.float32)
        for a in (0.25, 0.5, 0.75):
            Hi = (1 - a) * Hm_prev + a * Hm
            acc += cv2.warpPerspective(tex, Hi, (W, H), dst=bg.copy(), borderMode=cv2.BORDER_TRANSPARENT).astype(np.float32)
        img = (acc / 4).astype(np.uint8)
    # hand-like occluder sweeping across the middle third of the clip
    if n // 3 < i < 2 * n // 3:
        u = (i - n // 3) / (n // 3)
        cx, cy = int(W * (0.2 + 0.6 * u)), int(H * (0.55 + 0.1 * np.sin(6 * u)))
        cv2.ellipse(img, (cx, cy), (170, 110), 30, 0, 360, (150, 110, 95), -1, cv2.LINE_AA)
        cv2.rectangle(img, (cx - 60, cy), (cx + 60, H), (140, 100, 88), -1)
    img = img.astype(np.float32) + rng.normal(0, 3.0, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return cv2.cvtColor(cv2.imdecode(enc, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texture")
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--ref", type=int, default=0)
    ap.add_argument("--write", help="also save the synthetic clip (H.264) for renderer tests, and skip tracking")
    args = ap.parse_args()
    rng = np.random.default_rng(1)
    tex = cv2.imread(args.texture)
    tex = cv2.resize(tex, (1200, int(1200 * tex.shape[0] / tex.shape[1])))
    th, tw = tex.shape[:2]
    yaw, pitch, roll, dist = camera_path(args.frames, rng)
    Ht = [homography(yaw[i], pitch[i], roll[i], dist[i], tw, th) for i in range(args.frames)]
    frames = [render(tex, Ht[i], Ht[i - 1] if i else None, i, args.frames, rng) for i in range(args.frames)]
    # a blurred frame shows the exposure-average pose (samples at 0.25, 0.5, 0.75 and 1 of the way from i-1 to i)
    Hm = [Ht[0]] + [0.375 * Ht[i - 1] + 0.625 * Ht[i] for i in range(1, args.frames)]
    if args.write:
        from arhud_dc.video import Writer
        w = Writer(args.write, W, H, 30.0)
        for f in frames:
            w.write(f)
        w.close()
        poly = cv2.perspectiveTransform(np.array([[[0, 0]], [[tw, 0]], [[tw, th]], [[0, th]]], np.float64), Hm[args.ref])
        print("plane polygon on frame", args.ref, np.round(poly.reshape(-1, 2), 1).tolist())
        return
    corners = np.array([[0, 0], [tw, 0], [tw, th], [0, th]], np.float64)
    poly_ref = cv2.perspectiveTransform(corners.reshape(-1, 1, 2), Hm[args.ref]).reshape(-1, 2)
    res = track_planes(frames, [{"name": "p", "ref_frame": args.ref, "poly": poly_ref.tolist()}], W)
    Hs, inl = res["p"]
    gu, gv = np.meshgrid(np.linspace(0.1, 0.9, 7) * tw, np.linspace(0.1, 0.9, 5) * th)
    grid = np.stack([gu.ravel(), gv.ravel()], 1).reshape(-1, 1, 2)
    ref_grid = cv2.perspectiveTransform(grid, Hm[args.ref])
    errs, lost = [], 0
    for i in range(args.frames):
        if Hs[i] is None:
            lost += 1
            continue
        truth = cv2.perspectiveTransform(grid, Hm[i]).reshape(-1, 2)
        est = cv2.perspectiveTransform(ref_grid, Hs[i]).reshape(-1, 2)
        errs.append(np.linalg.norm(truth - est, axis=1))
    e = np.concatenate(errs)
    per = np.array([x.max() for x in errs])
    print(f"frames {args.frames}, lost {lost}")
    print(f"grid error px: median {np.median(e):.2f}  p95 {np.percentile(e, 95):.2f}  max {e.max():.2f}")
    print(f"worst frame max error {per.max():.2f} px at frame {int(per.argmax())}; inliers min {min(x for x in inl if x)}")


if __name__ == "__main__":
    main()
