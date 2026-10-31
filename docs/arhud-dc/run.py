#!/usr/bin/env python3
"""AR display for data center cabling, composited onto real first-person footage.

    python3 run.py fetch  scenes/<scene>.json            # download the source clip into footage/ (S3 or yt-dlp)
    python3 run.py frames scenes/<scene>.json --every 1  # reference frames with a pixel grid, for authoring
    python3 run.py track  scenes/<scene>.json            # track the scene's planes (cached in cache/)
    python3 run.py trackviz scenes/<scene>.json          # out/<scene>-track.mp4: tracked outlines and ports
    python3 run.py stills scenes/<scene>.json 3.2 7.5    # composited stills at those times (--compare: side by side)
    python3 run.py render scenes/<scene>.json            # the whole cut to out/<scene>.mp4

See README.md for the display model, the scene format and the design of the HUD.
"""
import argparse
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from arhud_dc.render import Renderer  # noqa: E402
from arhud_dc.scene import Scene  # noqa: E402
from arhud_dc.video import read_frames  # noqa: E402


def fetch(sc, args):
    out = sc.footage
    if os.path.exists(out) and not args.force:
        print(f"{out} exists")
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if "mp4" in sc.src:
        # a direct file (e.g. a YFCC100M video from Multimedia Commons on S3)
        print(f"{sc.src['mp4']} -> {out}")
        urllib.request.urlretrieve(sc.src["mp4"], out)
        return
    cmd = ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]",
           "--merge-output-format", "mp4", "-o", out, sc.src["url"]]
    if "t1" in sc.src and not args.whole:
        # only the cut, with a second of margin either side
        cmd[1:1] = ["--download-sections", f"*{max(0, sc.t0 - 1):.2f}-{sc.src['t1'] + 1:.2f}", "--force-keyframes-at-cuts"]
        print("note: with --download-sections the clip starts ~1 s before t0; scenes written against the full video "
              "need --whole")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def frames(sc, args):
    r = Renderer(sc)
    d = os.path.join(HERE, "out", sc.name, "frames")
    os.makedirs(d, exist_ok=True)
    step = max(1, int(round(args.every * r.fps)))
    for i, rgb in enumerate(read_frames(sc.footage, sc.t0, r.t1, size=(r.W, r.H))):
        if i % step:
            continue
        img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        if args.grid:
            for x in range(0, r.W, 100):
                cv2.line(img, (x, 0), (x, r.H), (0, 255, 255) if x % 500 == 0 else (0, 160, 160), 1)
                cv2.putText(img, str(x), (x + 2, 14), cv2.FONT_HERSHEY_PLAIN, 0.9, (0, 255, 255), 1)
            for y in range(0, r.H, 100):
                cv2.line(img, (0, y), (r.W, y), (0, 255, 255) if y % 500 == 0 else (0, 160, 160), 1)
                cv2.putText(img, str(y), (2, y - 3), cv2.FONT_HERSHEY_PLAIN, 0.9, (0, 255, 255), 1)
        cv2.putText(img, f"t={i / r.fps:.2f}s f={i}", (10, r.H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imwrite(os.path.join(d, f"{i / r.fps:06.2f}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(d)


def track(sc, args):
    r = Renderer(sc)
    for k, v in r.track(os.path.join(HERE, "cache")).items():
        print(f"{k}: {v}")
    return r


def stills(sc, args):
    r = Renderer(sc)
    r.track(os.path.join(HERE, "cache"))
    d = os.path.join(HERE, "out", sc.name, "stills")
    os.makedirs(d, exist_ok=True)
    only = {int(round(float(t) * r.fps)) for t in args.times}
    n = r.render(None, only=only, stills_dir=d, compare=args.compare)
    print(f"{n} stills in {d}")


def render(sc, args):
    r = Renderer(sc)
    r.track(os.path.join(HERE, "cache"))
    out = args.out or os.path.join(HERE, "out", f"{sc.name}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = r.render(out, audio=not args.mute, crf=args.crf)
    print(f"{n} frames -> {out}")


def trackviz(sc, args):
    """Tracking check: every frame with each plane's outline, its ports and the inlier count."""
    from arhud_dc.video import Writer
    r = Renderer(sc)
    r.track(os.path.join(HERE, "cache"))
    out = os.path.join(HERE, "out", f"{sc.name}-track.mp4")
    w = Writer(out, r.W, r.H, r.fps, crf=22)
    colors = [(0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 160, 0), (80, 160, 255)]
    planes = {p["name"]: p for p in sc.cfg.get("planes", [])}
    for i, rgb in enumerate(r.frames()):
        img = rgb.copy()
        for k, (name, Hs) in enumerate(r.Hs.items()):
            c = colors[k % len(colors)]
            if i < len(Hs) and Hs[i] is not None:
                poly = cv2.perspectiveTransform(np.asarray(planes[name]["poly"], np.float64).reshape(-1, 1, 2), Hs[i])
                cv2.polylines(img, [np.round(poly).astype(np.int32)], True, c, 1, cv2.LINE_AA)
                for pn, p in sc.ports.items():
                    if p["plane"] == name:
                        q = cv2.perspectiveTransform(np.asarray(p["quad"], np.float64).reshape(-1, 1, 2), Hs[i])
                        cv2.polylines(img, [np.round(q).astype(np.int32)], True, c, 2, cv2.LINE_AA)
                        cv2.putText(img, pn, tuple(np.round(q[0, 0]).astype(int) - [0, 6]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)
            cv2.putText(img, f"{name}: {r.inliers[name][i] if Hs[i] is not None else 'lost'}", (12, 30 + 26 * k),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
        cv2.putText(img, f"t={i / r.fps:.2f}", (12, r.H - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        w.write(img)
    w.close()
    print(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name):
        p = sub.add_parser(name)
        p.add_argument("scene")
        return p
    p = cmd("fetch")
    p.add_argument("--force", action="store_true")
    p.add_argument("--whole", action="store_true", help="download the whole video, not just the cut")
    p = cmd("frames")
    p.add_argument("--every", type=float, default=1.0, help="seconds between frames")
    p.add_argument("--no-grid", dest="grid", action="store_false")
    cmd("track")
    cmd("trackviz")
    p = cmd("stills")
    p.add_argument("times", nargs="+")
    p.add_argument("--compare", action="store_true", help="source and composite side by side")
    p = cmd("render")
    p.add_argument("--out")
    p.add_argument("--mute", action="store_true")
    p.add_argument("--crf", type=int, default=16)
    args = ap.parse_args()
    sc = Scene(args.scene)
    {"fetch": fetch, "frames": frames, "track": track, "trackviz": trackviz, "stills": stills,
     "render": render}[args.cmd](sc, args)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
