"""Video in and out through ffmpeg pipes, and sRGB <-> linear light.

Frames are RGB uint8 arrays of shape (h, w, 3). Reading seeks to the segment start with -ss before -i, which is
frame-accurate with re-encoded input in current ffmpeg.
"""
import json
import subprocess
from fractions import Fraction

import numpy as np


def probe(path):
    """Width, height, frame rate and duration of the first video stream."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames:format=duration", "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    num, den = (s.get("avg_frame_rate") or s["r_frame_rate"]).split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": fps, "duration": float(d["format"]["duration"])}


def read_frames(path, t0=0.0, t1=None, size=None, fps=None):
    """Yield RGB uint8 frames of [t0, t1). size=(w, h) rescales, fps resamples."""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", path]
    if t1 is not None:
        cmd += ["-t", f"{t1 - t0:.3f}"]
    vf = []
    if fps:
        vf.append(f"fps={fps}")
    if size:
        vf.append(f"scale={size[0]}:{size[1]}:flags=lanczos")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    info = probe(path)
    w, h = size or (info["w"], info["h"])
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        if p.poll() is None:
            p.kill()          # stopped early: don't let ffmpeg complain about the closed pipe
        p.stdout.close()
        p.wait()


class Writer:
    """H.264 writer; audio (optional) is cut from the source over the same segment."""

    def __init__(self, path, w, h, fps, audio=None, t0=0.0, t1=None, crf=16):
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
               "-r", str(Fraction(fps).limit_denominator(1001)), "-i", "-"]
        if audio:
            cmd += ["-ss", f"{t0:.3f}"] + (["-t", f"{t1 - t0:.3f}"] if t1 is not None else []) + ["-i", audio,
                                                                                                 "-map", "0:v", "-map", "1:a?",
                                                                                                 "-c:a", "aac", "-b:a", "160k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", path]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, rgb):
        self.p.stdin.write(np.ascontiguousarray(rgb, np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


_x = np.arange(256, dtype=np.float32) / 255.0
_DECODE = np.where(_x <= 0.04045, _x / 12.92, ((_x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def to_linear(rgb8):
    return _DECODE[rgb8]


_q = np.arange(16384, dtype=np.float64) / 16383.0
_ENCODE = (np.where(_q <= 0.0031308, _q * 12.92, 1.055 * np.power(_q, 1 / 2.4) - 0.055) * 255.0 + 0.5).astype(np.uint8)


def to_srgb8(lin):
    return _ENCODE[(np.clip(lin, 0.0, 1.0) * 16383.0 + 0.5).astype(np.uint16)]
