#!/usr/bin/env python3
"""AR HUD road simulator (TFT LCD edition) on MetaDrive.

    ~/.venvs/arhud-metadrive/bin/python run.py                  # interactive
    ~/.venvs/arhud-metadrive/bin/python run.py --map SCrXOTRS   # choose the road (PG block letters)
    ~/.venvs/arhud-metadrive/bin/python run.py --shots tour     # scripted screenshots into --out, then quit

See README.md for the keys, the scenarios and what the numbers mean.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Shot scripts: (sim time s, file name or None, [commands]). Commands are those of App.command().
TOURS = {
    "tour": [
        (2.0, None, ["panels:on"]),
        (14.0, "01-driver-noon.png", []),
        (14.5, None, ["zoom:2", "panels:off"]),
        (16.0, "02-driver-hud-zoom.png", []),
        (16.5, None, ["zoom:1", "panels:on", "view:chase"]),
        (18.0, "03-chase.png", []),
        (18.5, None, ["view:top"]),
        (20.0, "04-top.png", []),
        (20.5, None, ["view:driver", "scenario:lead_brake"]),
        (23.8, "05-lead-follow.png", []),
        (26.0, "06-lead-brake-fcw.png", []),
        (34.0, None, ["scenario:ped_crossing"]),
        (39.5, "07-pedestrian.png", []),
        (41.0, "07b-pedestrian.png", []),
        (48.0, None, ["scenario:lane_drift"]),
        (54.6, "08-lane-drift.png", []),
        (55.6, "08b-lane-drift.png", []),
        (60.0, None, ["scenario:turn"]),
        (65.5, "09-turn-arrows.png", []),
        (67.0, "09b-turn-arrows.png", []),
        (70.0, None, ["scenario:night"]),
        (74.0, "10-night.png", []),
        (75.0, None, ["scenario:cruise", "set:window=traced", "key:b"]),
        (78.0, "11-traced-window.png", []),
        (78.5, None, ["set:window=spec", "key:b", "scenario:sun_patch"]),
        (81.0, "12-sun-patch.png", []),
        (82.0, None, ["scenario:cruise", "set:content=plan"]),
        (85.0, "13-plan-as-written.png", []),
    ],
    "scenes": [
        (4.0, None, ["zoom:0"]),
        (8.0, "s1-wide-60deg.png", []),
        (8.1, None, ["panels:off"]),
        (8.3, "s1b-wide-no-panels.png", []),
        (8.5, None, ["panels:on", "zoom:1", "env:dusk"]),
        (12.0, "s2-dusk.png", []),
        (12.5, None, ["env:overcast"]),
        (15.0, "s3-overcast.png", []),
        (15.5, None, ["env:night", "zoom:0"]),
        (19.0, "s4-night-wide.png", []),
    ],
    "quick": [
        (6.0, "q1-driver.png", []),
        (6.5, None, ["zoom:2"]),
        (8.0, "q2-zoom.png", []),
    ],
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", default="SCrSXSOSCTSRS", help="PG map: block letters or a block count (default %(default)s)")
    ap.add_argument("--seed", type=int, default=3, help="first scenario seed")
    ap.add_argument("--scenarios", type=int, default=20, help="number of seeds [ ] cycles through")
    ap.add_argument("--traffic", type=float, default=0.12, help="traffic density")
    ap.add_argument("--oncoming", action="store_true", help="traffic in the opposite carriageway too")
    ap.add_argument("--lanes", type=int, default=3, help="lanes per carriageway")
    ap.add_argument("--window", type=int, nargs=2, default=(1600, 900), help="window size")
    ap.add_argument("--env", default="noon", choices=["noon", "overcast", "dusk", "night"])
    ap.add_argument("--hud-window", default="spec", choices=["spec", "traced", "stage1"])
    ap.add_argument("--content", default="plus", choices=["plus", "plan"])
    ap.add_argument("--fast", action="store_true", help="do not hold the window to real time")
    ap.add_argument("--single-thread", action="store_true", help="single-threaded rendering")
    ap.add_argument("--no-panels", action="store_true")
    ap.add_argument("--no-camera-inset", action="store_true", help="skip the extra road-camera render")
    ap.add_argument("--shots", default=None, help="scripted screenshots: " + ", ".join(TOURS))
    ap.add_argument("--duration", type=float, default=None, help="quit after this many simulated seconds")
    ap.add_argument("--out", default=os.path.join(HERE, "screenshots"), help="screenshot folder (S key, --shots)")
    ap.add_argument("--log", default=None, help="write per-frame numbers (every 6th frame) to this CSV")
    ap.add_argument("--scenario", default=None, help="start this scenario after 3 s (see README)")
    ap.add_argument("--bench", action="store_true",
                    help="replay the same seeded drive under each condition and print the registration table")
    args = ap.parse_args()
    args.shots = [list(s) for s in TOURS[args.shots]] if args.shots else None
    args.exit_after_shots = bool(args.shots)
    from arhud_road.app import App
    app = App(args)
    if args.bench:
        app.run_bench()
    else:
        app.run()


if __name__ == "__main__":
    main()
